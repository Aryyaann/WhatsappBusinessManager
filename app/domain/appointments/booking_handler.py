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

Si consultar_disponibilidad_citas te dice que el empleado pedido NO tiene
horario planificado esa semana (eso es distinto de "está completo"), usa
buscar_empleados_alternativos para ver si otro empleado sí tiene hueco ese
mismo día, y ofrécelo al cliente. Si el cliente prefiere esperar igualmente
al empleado original, o si tampoco hay alternativa disponible, usa
crear_cita_pendiente para dejar la petición pendiente de confirmación por
parte del negocio — deja claro que no es una reserva confirmada todavía,
que el negocio la confirmará en cuanto planifique el horario de esa semana.

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

BUSCAR_EMPLEADOS_ALTERNATIVOS_TOOL = {
    "name": "buscar_empleados_alternativos",
    "description": (
        "Busca qué otros empleados tienen huecos libres para un servicio en "
        "una fecha dada. Úsala cuando consultar_disponibilidad_citas te haya "
        "dicho que el empleado pedido no tiene horario planificado esa "
        "semana, para poder ofrecer una alternativa antes de dejar la cita "
        "pendiente."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "service_name": {"type": "string"},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        "required": ["service_name", "date"],
    },
}

CREAR_CITA_PENDIENTE_TOOL = {
    "name": "crear_cita_pendiente",
    "description": (
        "Deja una petición de cita pendiente de confirmación por parte del "
        "negocio. Úsala cuando ni el empleado pedido ni ninguna alternativa "
        "tengan horario planificado esa semana, o cuando el cliente prefiera "
        "esperar igualmente a un empleado concreto. NO reserva un hueco "
        "real — el dueño la confirmará o reasignará más tarde desde el panel."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "service_name": {"type": "string"},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "time": {"type": "string", "description": "HH:MM, hora deseada por el cliente (orientativa)"},
            "employee_name": {
                "type": "string",
                "description": "Empleado preferido, si el cliente insiste en uno concreto. Omitir si no tiene preferencia.",
            },
            "customer_name": {"type": "string"},
        },
        "required": ["service_name", "date", "time"],
    },
}

APPOINTMENT_TOOLS = [
    CONSULTAR_DISPONIBILIDAD_TOOL,
    RESERVAR_CITA_TOOL,
    BUSCAR_EMPLEADOS_ALTERNATIVOS_TOOL,
    CREAR_CITA_PENDIENTE_TOOL,
]

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
            # Distinguimos "no hay horario planificado esa semana" (Pieza B:
            # aquí es donde entra buscar alternativas / cita pendiente) de
            # "tiene horario pero está completo ese día" — son casos
            # distintos y el bot debe reaccionar de forma distinta.
            has_schedule = await availability_service.has_schedule_for_date(str(employee.id), target_date)
            if not has_schedule:
                return (
                    f"{employee.name} no tiene horario planificado todavía para "
                    f"el {target_date.strftime('%d/%m/%Y')} (esa semana no se ha "
                    f"organizado en el panel). No hay un hueco real que ofrecer "
                    f"— usa buscar_empleados_alternativos para ver si otro "
                    f"empleado sí tiene, o crear_cita_pendiente si el cliente "
                    f"prefiere esperar a que se confirme."
                )
            return (
                f"{employee.name} tiene horario planificado pero no tiene "
                f"huecos libres el {target_date.strftime('%d/%m/%Y')} para "
                f"{service.name} — está completo ese día."
            )

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

    if tool_name == "buscar_empleados_alternativos":
        service = await lookup_service.find_service_by_name(business_id, tool_input["service_name"])
        if service is None:
            return f"No encuentro el servicio '{tool_input['service_name']}'."

        target_date = date.fromisoformat(tool_input["date"])
        availability_service = AvailabilityService(db)
        employees = await lookup_service.list_employees(business_id)

        alternatives = []
        for employee in employees:
            slots = await availability_service.get_available_slots(
                str(employee.id), target_date, service.duration_minutes
            )
            if slots:
                sample = ", ".join(s.strftime("%H:%M") for s in slots[:3])
                alternatives.append(f"{employee.name} ({sample})")

        if not alternatives:
            return (
                f"Ningún empleado tiene horario planificado o huecos libres el "
                f"{target_date.strftime('%d/%m/%Y')} para {service.name}."
            )
        return "Empleados con hueco ese día: " + "; ".join(alternatives)

    if tool_name == "crear_cita_pendiente":
        service = await lookup_service.find_service_by_name(business_id, tool_input["service_name"])
        if service is None:
            return f"No encuentro el servicio '{tool_input['service_name']}'."

        employee = None
        employee_name = tool_input.get("employee_name")
        if employee_name:
            employee = await lookup_service.find_employee_by_name(business_id, employee_name)
            if employee is None:
                return f"No encuentro a ningún empleado llamado '{employee_name}'."

        target_date = date.fromisoformat(tool_input["date"])
        hour, minute = map(int, tool_input["time"].split(":"))
        start_at = datetime.combine(target_date, time(hour, minute))

        reason_note = "Pendiente: la semana solicitada no tiene horario planificado todavía."
        if employee is not None:
            reason_note += f" El cliente prefiere específicamente a {employee.name}."

        booking_service = BookingService(db)
        await booking_service.create_pending_appointment(
            business_id=business_id,
            customer_phone=customer_phone,
            start_at=start_at,
            duration_minutes=service.duration_minutes,
            user_id=str(employee.id) if employee else None,
            customer_name=tool_input.get("customer_name"),
            service_id=str(service.id),
            reason_note=reason_note,
        )

        quien = f"con {employee.name}" if employee else "todavía sin empleado asignado"
        return (
            f"Petición registrada como pendiente: {service.name} {quien} el "
            f"{start_at.strftime('%d/%m/%Y a las %H:%M')}. No es una reserva "
            f"confirmada — el negocio la confirmará en cuanto organice el "
            f"horario de esa semana."
        )

    return f"Herramienta desconocida: {tool_name}"


async def handle_appointment_request(db, business_id: str, customer_phone: str, message_text: str) -> dict:
    # Orquesta el ciclo de function calling con Claude, permitiendo varias
    # idas y vueltas (consultar disponibilidad, luego reservar) dentro de
    # una misma solicitud del cliente.
    #
    # NOTA: esta función NO es la que se usa en producción — el webhook real
    # (app/api/webhooks/whatsapp.py) llama a
    # app.domain.conversations.assistant_handler.handle_assistant_request,
    # que junta estas mismas herramientas con las de stock en una sola
    # conversación. Esta función se mantiene por sus tests, que ejercitan
    # _execute_tool (la lógica real y compartida) de forma aislada.
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