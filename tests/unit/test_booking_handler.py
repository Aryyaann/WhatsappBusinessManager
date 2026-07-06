import os
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from app.domain.appointments.booking_handler import handle_appointment_request
from app.domain.appointments.booking_service import SlotNoLongerAvailableError


def make_text_block(text):
    return MagicMock(type="text", text=text)


def make_tool_use_block(name, input_dict, block_id="toolu_1"):
    block = MagicMock(type="tool_use", input=input_dict, id=block_id)
    block.name = name
    return block


def make_response(content_blocks, input_tokens=100, output_tokens=20):
    return MagicMock(
        content=content_blocks,
        usage=MagicMock(input_tokens=input_tokens, output_tokens=output_tokens),
    )


@pytest.mark.asyncio
@patch("app.domain.appointments.booking_handler.AppointmentLookupService")
@patch("app.domain.appointments.booking_handler.anthropic_client")
async def test_returns_direct_text_when_no_tool_needed(mock_anthropic, mock_lookup_cls):
    mock_anthropic.chat_with_tools.return_value = make_response(
        [make_text_block("¡Hola! ¿En qué puedo ayudarte?")]
    )

    result = await handle_appointment_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099", message_text="hola"
    )

    assert result["reply"] == "¡Hola! ¿En qué puedo ayudarte?"
    assert result["tools_called"] == []
    mock_lookup_cls.assert_not_called()


@pytest.mark.asyncio
@patch("app.domain.appointments.booking_handler.AvailabilityService")
@patch("app.domain.appointments.booking_handler.AppointmentLookupService")
@patch("app.domain.appointments.booking_handler.anthropic_client")
async def test_checks_availability_and_reports_slots(mock_anthropic, mock_lookup_cls, mock_availability_cls):
    tool_block = make_tool_use_block(
        "consultar_disponibilidad_citas",
        {"employee_name": "Ana", "service_name": "Corte", "date": "2026-07-06"},
    )
    first_response = make_response([tool_block])
    second_response = make_response([make_text_block("Ana tiene hueco a las 9:00 y a las 9:30.")])
    mock_anthropic.chat_with_tools.side_effect = [first_response, second_response]

    mock_employee = MagicMock(id="user-1", name="Ana")
    mock_service = MagicMock(id="service-1", name="Corte", duration_minutes=30)
    mock_lookup_cls.return_value.find_employee_by_name = AsyncMock(return_value=mock_employee)
    mock_lookup_cls.return_value.find_service_by_name = AsyncMock(return_value=mock_service)
    mock_availability_cls.return_value.get_available_slots = AsyncMock(return_value=[
        datetime(2026, 7, 6, 9, 0), datetime(2026, 7, 6, 9, 30),
    ])

    result = await handle_appointment_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099",
        message_text="quiero un corte con Ana el lunes",
    )

    assert result["reply"] == "Ana tiene hueco a las 9:00 y a las 9:30."
    assert result["tools_called"] == ["consultar_disponibilidad_citas"]
    mock_availability_cls.return_value.get_available_slots.assert_called_once_with(
        "user-1", date(2026, 7, 6), 30
    )

    # El tool_result que se le devuelve a Claude debe incluir ambas horas.
    second_call_messages = mock_anthropic.chat_with_tools.call_args_list[1].kwargs["messages"]
    tool_result_text = second_call_messages[-1]["content"][0]["content"]
    assert "09:00" in tool_result_text
    assert "09:30" in tool_result_text


@pytest.mark.asyncio
@patch("app.domain.appointments.booking_handler.AppointmentLookupService")
@patch("app.domain.appointments.booking_handler.anthropic_client")
async def test_availability_check_reports_unknown_employee(mock_anthropic, mock_lookup_cls):
    tool_block = make_tool_use_block(
        "consultar_disponibilidad_citas",
        {"employee_name": "Fulanito", "service_name": "Corte", "date": "2026-07-06"},
    )
    first_response = make_response([tool_block])
    second_response = make_response([make_text_block("No tenemos a nadie con ese nombre, ¿puedes confirmarlo?")])
    mock_anthropic.chat_with_tools.side_effect = [first_response, second_response]

    mock_lookup_cls.return_value.find_employee_by_name = AsyncMock(return_value=None)

    result = await handle_appointment_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099",
        message_text="cita con Fulanito",
    )

    second_call_messages = mock_anthropic.chat_with_tools.call_args_list[1].kwargs["messages"]
    tool_result_text = second_call_messages[-1]["content"][0]["content"]
    assert "No encuentro a ningún empleado" in tool_result_text
    assert "Fulanito" in tool_result_text


@pytest.mark.asyncio
@patch("app.domain.appointments.booking_handler.BookingService")
@patch("app.domain.appointments.booking_handler.AppointmentLookupService")
@patch("app.domain.appointments.booking_handler.anthropic_client")
async def test_books_appointment_successfully(mock_anthropic, mock_lookup_cls, mock_booking_cls):
    tool_block = make_tool_use_block(
        "reservar_cita",
        {"employee_name": "Ana", "service_name": "Corte", "date": "2026-07-06", "time": "09:00", "customer_name": "Lucía"},
    )
    first_response = make_response([tool_block])
    second_response = make_response([make_text_block("¡Listo! Cita confirmada para el lunes a las 9:00.")])
    mock_anthropic.chat_with_tools.side_effect = [first_response, second_response]

    mock_employee = MagicMock(id="user-1", name="Ana")
    mock_service = MagicMock(id="service-1", name="Corte", duration_minutes=30)
    mock_lookup_cls.return_value.find_employee_by_name = AsyncMock(return_value=mock_employee)
    mock_lookup_cls.return_value.find_service_by_name = AsyncMock(return_value=mock_service)

    mock_appointment = MagicMock()
    mock_booking_cls.return_value.book_appointment = AsyncMock(return_value=mock_appointment)

    result = await handle_appointment_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099",
        message_text="resérvame el hueco de las 9 con Ana para un corte, soy Lucía",
    )

    assert result["reply"] == "¡Listo! Cita confirmada para el lunes a las 9:00."
    mock_booking_cls.return_value.book_appointment.assert_called_once_with(
        business_id="business-1",
        user_id="user-1",
        customer_phone="+34600000099",
        start_at=datetime(2026, 7, 6, 9, 0),
        duration_minutes=30,
        customer_name="Lucía",
    )


@pytest.mark.asyncio
@patch("app.domain.appointments.booking_handler.BookingService")
@patch("app.domain.appointments.booking_handler.AppointmentLookupService")
@patch("app.domain.appointments.booking_handler.anthropic_client")
async def test_booking_slot_no_longer_available_is_reported_to_claude(mock_anthropic, mock_lookup_cls, mock_booking_cls):
    tool_block = make_tool_use_block(
        "reservar_cita",
        {"employee_name": "Ana", "service_name": "Corte", "date": "2026-07-06", "time": "09:00"},
    )
    first_response = make_response([tool_block])
    second_response = make_response([make_text_block("Vaya, ese hueco ya no está libre. ¿Quieres otra hora?")])
    mock_anthropic.chat_with_tools.side_effect = [first_response, second_response]

    mock_lookup_cls.return_value.find_employee_by_name = AsyncMock(return_value=MagicMock(id="user-1", name="Ana"))
    mock_lookup_cls.return_value.find_service_by_name = AsyncMock(
        return_value=MagicMock(id="service-1", name="Corte", duration_minutes=30)
    )
    mock_booking_cls.return_value.book_appointment = AsyncMock(
        side_effect=SlotNoLongerAvailableError("El hueco de las 09:00 ya no está disponible.")
    )

    result = await handle_appointment_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099",
        message_text="resérvame a las 9 con Ana",
    )

    assert result["reply"] == "Vaya, ese hueco ya no está libre. ¿Quieres otra hora?"
    second_call_messages = mock_anthropic.chat_with_tools.call_args_list[1].kwargs["messages"]
    tool_result_text = second_call_messages[-1]["content"][0]["content"]
    assert "ya no está disponible" in tool_result_text


@pytest.mark.asyncio
@patch("app.domain.appointments.booking_handler.AppointmentLookupService")
@patch("app.domain.appointments.booking_handler.anthropic_client")
async def test_gives_up_after_max_turns_without_final_answer(mock_anthropic, mock_lookup_cls):
    tool_block = make_tool_use_block(
        "consultar_disponibilidad_citas",
        {"employee_name": "Ana", "service_name": "Corte", "date": "2026-07-06"},
    )
    # Claude sigue pidiendo la misma tool una y otra vez sin dar respuesta final.
    mock_anthropic.chat_with_tools.return_value = make_response([tool_block])
    mock_lookup_cls.return_value.find_employee_by_name = AsyncMock(return_value=None)

    result = await handle_appointment_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099",
        message_text="cita rara",
    )

    assert "No he podido completar" in result["reply"]
    assert mock_anthropic.chat_with_tools.call_count == 4  # MAX_TURNS