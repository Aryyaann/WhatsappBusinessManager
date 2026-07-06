from datetime import date

from app.infrastructure.llm.anthropic_client import anthropic_client
from app.domain.inventory.stock_query_service import StockQueryService
from app.domain.conversations.query_handler import CONSULTAR_STOCK_TOOL, _serialize_stock_results
from app.domain.appointments.booking_handler import (
    CONSULTAR_DISPONIBILIDAD_TOOL,
    RESERVAR_CITA_TOOL,
    _execute_tool as _execute_appointment_tool,
)

# Reutiliza las herramientas y la lógica de ejecución ya probadas en
# query_handler.py y booking_handler.py — este módulo solo las junta en una
# única conversación, para que Claude pueda atender tanto preguntas de stock
# como de citas sin que el dueño tenga que "elegir" de antemano de qué tema
# va a hablar.
def _build_system_prompt() -> str:
    # La fecha de hoy se inyecta dinámicamente porque Claude no tiene
    # noción de "hoy" por sí solo — sin esto no puede resolver expresiones
    # como "mañana" o "el lunes que viene".
    today = date.today()
    return f"""
Eres el asistente de WhatsApp de un negocio. Hoy es {today.strftime('%A %d de %B de %Y')} ({today.isoformat()}).
Ayudas al dueño con dos cosas:

1. Consultar el stock de productos — usa consultar_stock.
2. Gestionar citas — usa consultar_disponibilidad_citas para ver huecos
   libres, y reservar_cita solo cuando el cliente haya confirmado
   explícitamente una hora concreta de las disponibles. Si el cliente da
   una fecha relativa ("mañana", "el lunes"), calcúlala tú mismo a partir
   de la fecha de hoy — no se lo preguntes salvo que sea genuinamente ambiguo.

Responde siempre en español, de forma breve y natural.
"""


ALL_TOOLS = [CONSULTAR_STOCK_TOOL, CONSULTAR_DISPONIBILIDAD_TOOL, RESERVAR_CITA_TOOL]

# Límite de idas y vueltas con Claude en una sola solicitud (ej. consultar
# disponibilidad + reservar puede necesitar 2). Evita bucles infinitos.
MAX_TURNS = 4


def _extract_text(response) -> str:
    text_block = next((block for block in response.content if block.type == "text"), None)
    return text_block.text if text_block else ""


async def _execute_tool(db, business_id: str, customer_phone: str, tool_name: str, tool_input: dict) -> str:
    if tool_name == "consultar_stock":
        stock_service = StockQueryService(db)
        results = await stock_service.query_stock(business_id, tool_input["query"])
        return _serialize_stock_results(results)

    if tool_name in ("consultar_disponibilidad_citas", "reservar_cita"):
        return await _execute_appointment_tool(db, business_id, customer_phone, tool_name, tool_input)

    return f"Herramienta desconocida: {tool_name}"


async def handle_assistant_request(
    db, business_id: str, customer_phone: str, message_text: str, history: list[dict] = None
) -> dict:
    # Mismo patrón de bucle multi-turno que booking_handler.handle_appointment_request,
    # pero con el conjunto combinado de herramientas y, opcionalmente, el
    # historial reciente de la conversación (para que Claude recuerde lo
    # que ya se dijo en mensajes anteriores de WhatsApp).
    messages = list(history) if history else []
    messages.append({"role": "user", "content": message_text})
    tokens_input = 0
    tokens_output = 0
    tools_called = []
    system_prompt = _build_system_prompt()

    for _ in range(MAX_TURNS):
        response = anthropic_client.chat_with_tools(
            messages=messages,
            tools=ALL_TOOLS,
            system_prompt=system_prompt,
        )
        tokens_input += response.usage.input_tokens
        tokens_output += response.usage.output_tokens

        tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
        if not tool_use_blocks:
            return {
                "reply": _extract_text(response),
                "tools_called": tools_called,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
            }

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in tool_use_blocks:
            tools_called.append(block.name)
            result_text = await _execute_tool(db, business_id, customer_phone, block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })
        messages.append({"role": "user", "content": tool_results})

    return {
        "reply": "No he podido completar la solicitud. ¿Puedes intentarlo de nuevo, con menos pasos?",
        "tools_called": tools_called,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
    }