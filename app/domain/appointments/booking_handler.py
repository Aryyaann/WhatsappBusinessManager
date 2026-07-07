from datetime import date, datetime, time

from app.infrastructure.llm.anthropic_client import anthropic_client
from app.domain.appointments.lookup_service import AppointmentLookupService
from app.domain.appointments.availability_service import AvailabilityService
from app.domain.appointments.booking_service import BookingService, SlotNoLongerAvailableError

SYSTEM_PROMPT_APPOINTMENTS = """
Eres el asistente de WhatsApp de un negocio que ayuda a gestionar citas.
Cuando te pidan reservar una cita, primero usa consultar_disponibilidad_citas
para ver qué horas hay libres, y ofrécelas. Solo usa reservar_cita cuando el
cliente haya confirmado explícitamente una hora concreta de las disponibles.
Responde siempre en español, de forma breve y natural.
"""

CONSULTAR_DISPONIBILIDAD_TOOL = {
    "name": "consultar_disponibilidad_citas",
    "description": (
        "Consulta los huecos libres de un empleado para un servicio concreto "
        "en una fecha dada. Úsala antes de reservar, para saber qué horas ofrecer."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "employee_name": {"type": "string", "description": "Nombre del empleado"},
            "service_name": {"type": "string", "description": "Nombre del servicio"},
            "date": {"type": "string", "description": "Fecha en formato YYYY-MM-DD"},
        },
        "required": ["employee_name", "service_name", "date"],
    },
}

RESERVAR_CITA_TOOL = {
    "name": "reservar_cita",
    "description": (
        "Reserva una cita para el cliente actual con un empleado, servicio, "
        "fecha y hora concretos. Solo úsala después de confirmar que el hueco "
        "existe (con consultar_disponibilidad_citas) y que el cliente ha "
        "confirmado la hora exacta."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "employee_name": {"type": "string"},
            "service_name": {"type": "string"},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "time": {"type": "string", "description": "HH:MM, 24 horas"},
            "customer_name": {"type": "string", "description": "Nombre del cliente, si lo ha dado"},
        },
        "required": ["employee_name", "service_name", "date", "time"],
    },
}

APPOINTMENT_TOOLS = [CONSULTAR_DISPONIBILIDAD_TOOL, RESERVAR_CITA_TOOL]

# Límite de idas y vueltas con Claude en una sola solicitud (consultar
# disponibilidad + reservar puede necesitar 2, dejamos margen sin permitir
# bucles infinitos si algo va mal).
MAX_TURNS = 4


def _extract_text(response) -> str:
    text_block = next((block for block in response.content if block.type == "text"), None)
    return text_block.text if text_block else ""


async def _execute_tool(db, business_id: str, customer_phone: str, tool_name: str, tool_input: dict) -> str:
    lookup_service = AppointmentLookupService(db)

    if tool_name == "consultar_disponibilidad_citas":
        employee = await lookup_service.find_employee_by_name(business_id, tool_input["employee_name"])
        if employee is None:
            return f"No encuentro a ningún empleado llamado '{tool_input['employee_name']}'."

        service = await lookup_service.find_service_by_name(business_id, tool_input["service_name"])
        if service is None:
            return f"No encuentro el servicio '{tool_input['service_name']}'."

        target_date = date.fromisoformat(tool_input["date"])
        availability_service = AvailabilityService(db)
        slots = await availability_service.get_available_slots(
            str(employee.id), target_date, service.duration_minutes
        )
        if not slots:
            return f"{employee.name} no tiene huecos libres el {target_date.strftime('%d/%m/%Y')} para {service.name}."

        slot_list = ", ".join(s.strftime("%H:%M") for s in slots)
        return (
            f"Huecos disponibles para {employee.name} - {service.name} el "
            f"{target_date.strftime('%d/%m/%Y')}: {slot_list}"
        )

    if tool_name == "reservar_cita":
        employee = await lookup_service.find_employee_by_name(business_id, tool_input["employee_name"])
        if employee is None:
            return f"No encuentro a ningún empleado llamado '{tool_input['employee_name']}'."

        service = await lookup_service.find_service_by_name(business_id, tool_input["service_name"])
        if service is None:
            return f"No encuentro el servicio '{tool_input['service_name']}'."

        target_date = date.fromisoformat(tool_input["date"])
        hour, minute = map(int, tool_input["time"].split(":"))
        start_at = datetime.combine(target_date, time(hour, minute))

        booking_service = BookingService(db)
        try:
            appointment = await booking_service.book_appointment(
                business_id=business_id,
                user_id=str(employee.id),
                customer_phone=customer_phone,
                start_at=start_at,
                duration_minutes=service.duration_minutes,
                customer_name=tool_input.get("customer_name"),
                service_id=str(service.id),
            )
        except SlotNoLongerAvailableError as exc:
            return str(exc)

        return (
            f"Cita reservada: {service.name} con {employee.name} el "
            f"{start_at.strftime('%d/%m/%Y a las %H:%M')}."
        )

    return f"Herramienta desconocida: {tool_name}"


async def handle_appointment_request(db, business_id: str, customer_phone: str, message_text: str) -> dict:
    # Orquesta el ciclo de function calling con Claude, permitiendo varias
    # idas y vueltas (consultar disponibilidad, luego reservar) dentro de
    # una misma solicitud del cliente.
    messages = [{"role": "user", "content": message_text}]
    tokens_input = 0
    tokens_output = 0
    tools_called = []

    for _ in range(MAX_TURNS):
        response = anthropic_client.chat_with_tools(
            messages=messages,
            tools=APPOINTMENT_TOOLS,
            system_prompt=SYSTEM_PROMPT_APPOINTMENTS,
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

    # Se agotaron los turnos sin que Claude diera una respuesta final —
    # mejor esto que quedarse colgado o entrar en bucle infinito.
    return {
        "reply": "No he podido completar la solicitud. ¿Puedes intentarlo de nuevo, con menos pasos?",
        "tools_called": tools_called,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
    }