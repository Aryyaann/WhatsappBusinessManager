from app.infrastructure.llm.anthropic_client import anthropic_client
from app.domain.inventory.stock_query_service import StockQueryService

SYSTEM_PROMPT_CONVERSATIONAL = """
Eres el asistente de WhatsApp de un negocio que ayuda al dueño a consultar su inventario.
Cuando pregunten por el stock de un producto, usa la herramienta consultar_stock.
Responde de forma breve y natural en español, citando las cantidades reales que te
devuelva la herramienta. Si la herramienta no encuentra nada relevante, dilo
claramente y sugiere revisar el nombre del producto.
"""

CONSULTAR_STOCK_TOOL = {
    "name": "consultar_stock",
    "description": (
        "Busca productos en el catálogo del negocio y devuelve su stock actual. "
        "Úsala cuando el dueño pregunte cuánto queda de un producto."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Texto de búsqueda del producto, tal como lo menciona el dueño",
            }
        },
        "required": ["query"],
    },
}


def _serialize_stock_results(results: list[dict]) -> str:
    # Convierte los resultados de StockQueryService a texto plano para
    # devolvérselo a Claude como tool_result. Decimal no es JSON-serializable
    # directamente, así que formateamos a mano en vez de usar json.dumps.
    if not results:
        return "No se encontraron productos que coincidan con la búsqueda."
    lines = [f"- {r['product_name']}: {r['quantity']} {r['unit']} en stock" for r in results]
    return "\n".join(lines)


def _extract_text(response) -> str:
    text_block = next((block for block in response.content if block.type == "text"), None)
    return text_block.text if text_block else ""


async def handle_stock_query(db, business_id: str, query_text: str) -> dict:
    # Orquesta el ciclo completo de function calling: primera llamada a
    # Claude, ejecución de la tool si la pide, segunda llamada con el
    # resultado real de la base de datos para obtener la respuesta final
    # en lenguaje natural.
    messages = [{"role": "user", "content": query_text}]

    first_response = anthropic_client.chat_with_tools(
        messages=messages,
        tools=[CONSULTAR_STOCK_TOOL],
        system_prompt=SYSTEM_PROMPT_CONVERSATIONAL,
    )

    tool_use_block = next(
        (block for block in first_response.content if block.type == "tool_use"),
        None,
    )

    tokens_input = first_response.usage.input_tokens
    tokens_output = first_response.usage.output_tokens

    if tool_use_block is None:
        # Claude respondió directamente sin necesitar la herramienta
        # (ej. un saludo, o una pregunta que no es sobre stock).
        return {
            "reply": _extract_text(first_response),
            "tool_called": None,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
        }

    # Ejecuta la tool de verdad contra la base de datos del negocio.
    stock_service = StockQueryService(db)
    results = await stock_service.query_stock(business_id, tool_use_block.input["query"])
    tool_result_text = _serialize_stock_results(results)

    messages.append({"role": "assistant", "content": first_response.content})
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_block.id,
                "content": tool_result_text,
            }
        ],
    })

    second_response = anthropic_client.chat_with_tools(
        messages=messages,
        tools=[CONSULTAR_STOCK_TOOL],
        system_prompt=SYSTEM_PROMPT_CONVERSATIONAL,
    )

    return {
        "reply": _extract_text(second_response),
        "tool_called": tool_use_block.name,
        "tokens_input": tokens_input + second_response.usage.input_tokens,
        "tokens_output": tokens_output + second_response.usage.output_tokens,
    }