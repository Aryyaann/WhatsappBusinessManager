import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from app.domain.conversations.assistant_handler import handle_assistant_request


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
@patch("app.domain.conversations.assistant_handler.anthropic_client")
async def test_direct_text_when_no_tool_needed(mock_anthropic):
    mock_anthropic.chat_with_tools.return_value = make_response([make_text_block("¡Hola!")])

    result = await handle_assistant_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099", message_text="hola"
    )

    assert result["reply"] == "¡Hola!"
    assert result["tools_called"] == []


@pytest.mark.asyncio
@patch("app.domain.conversations.assistant_handler.StockQueryService")
@patch("app.domain.conversations.assistant_handler.anthropic_client")
async def test_routes_to_stock_tool(mock_anthropic, mock_stock_cls):
    tool_block = make_tool_use_block("consultar_stock", {"query": "tinte rubio"})
    first_response = make_response([tool_block])
    second_response = make_response([make_text_block("Te quedan 12 unidades.")])
    mock_anthropic.chat_with_tools.side_effect = [first_response, second_response]

    mock_stock_cls.return_value.query_stock = AsyncMock(return_value=[
        {"product_name": "Tinte Rubio", "quantity": Decimal("12"), "unit": "unidad", "sale_price": Decimal("9")}
    ])

    result = await handle_assistant_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099",
        message_text="qué me queda de tinte rubio",
    )

    assert result["reply"] == "Te quedan 12 unidades."
    assert result["tools_called"] == ["consultar_stock"]
    mock_stock_cls.return_value.query_stock.assert_called_once_with("business-1", "tinte rubio")


@pytest.mark.asyncio
@patch("app.domain.conversations.assistant_handler._execute_appointment_tool")
@patch("app.domain.conversations.assistant_handler.anthropic_client")
async def test_routes_to_appointment_tool(mock_anthropic, mock_execute_appointment):
    tool_block = make_tool_use_block(
        "consultar_disponibilidad_citas",
        {"employee_name": "Ana", "service_name": "Corte", "date": "2026-07-13"},
    )
    first_response = make_response([tool_block])
    second_response = make_response([make_text_block("Ana tiene hueco a las 9:00.")])
    mock_anthropic.chat_with_tools.side_effect = [first_response, second_response]
    mock_execute_appointment.return_value = "Huecos disponibles: 09:00"

    db = MagicMock()
    result = await handle_assistant_request(
        db=db, business_id="business-1", customer_phone="+34600000099",
        message_text="quiero un corte con Ana",
    )

    assert result["reply"] == "Ana tiene hueco a las 9:00."
    assert result["tools_called"] == ["consultar_disponibilidad_citas"]
    mock_execute_appointment.assert_called_once_with(
        db, "business-1", "+34600000099", "consultar_disponibilidad_citas",
        {"employee_name": "Ana", "service_name": "Corte", "date": "2026-07-13"},
    )

@pytest.mark.asyncio
@patch("app.domain.conversations.assistant_handler.anthropic_client")
async def test_history_is_prepended_to_messages(mock_anthropic):
    mock_anthropic.chat_with_tools.return_value = make_response([make_text_block("¡Hola de nuevo!")])
    history = [
        {"role": "user", "content": "quiero un corte con Ana"},
        {"role": "assistant", "content": "¿Para qué fecha?"},
    ]

    await handle_assistant_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099",
        message_text="para mañana", history=history,
    )

    sent_messages = mock_anthropic.chat_with_tools.call_args.kwargs["messages"]
    assert sent_messages[0] == history[0]
    assert sent_messages[1] == history[1]
    assert sent_messages[2] == {"role": "user", "content": "para mañana"}


@pytest.mark.asyncio
@patch("app.domain.conversations.assistant_handler.anthropic_client")
async def test_no_history_defaults_to_just_the_new_message(mock_anthropic):
    mock_anthropic.chat_with_tools.return_value = make_response([make_text_block("Hola")])

    await handle_assistant_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099",
        message_text="hola",
    )

    sent_messages = mock_anthropic.chat_with_tools.call_args.kwargs["messages"]
    assert sent_messages == [{"role": "user", "content": "hola"}]


def test_system_prompt_includes_todays_date():
    from app.domain.conversations.assistant_handler import _build_system_prompt
    from datetime import date

    prompt = _build_system_prompt()
    assert date.today().isoformat() in prompt

@pytest.mark.asyncio
@patch("app.domain.conversations.assistant_handler.anthropic_client")
async def test_unknown_tool_name_returns_placeholder_without_crashing(mock_anthropic):
    tool_block = make_tool_use_block("herramienta_inventada", {})
    first_response = make_response([tool_block])
    second_response = make_response([make_text_block("No puedo hacer eso todavía.")])
    mock_anthropic.chat_with_tools.side_effect = [first_response, second_response]

    result = await handle_assistant_request(
        db=MagicMock(), business_id="business-1", customer_phone="+34600000099",
        message_text="haz algo raro",
    )

    assert result["reply"] == "No puedo hacer eso todavía."
    second_call_messages = mock_anthropic.chat_with_tools.call_args_list[1].kwargs["messages"]
    tool_result_text = second_call_messages[-1]["content"][0]["content"]
    assert "Herramienta desconocida" in tool_result_text

@pytest.mark.asyncio
@patch("app.domain.conversations.assistant_handler._execute_appointment_tool")
@patch("app.domain.conversations.assistant_handler.anthropic_client")
async def test_routes_new_pending_tools_to_appointment_handler(mock_anthropic, mock_execute_appointment):
    # Pieza B: buscar_empleados_alternativos y crear_cita_pendiente también
    # deben enrutarse al handler de citas, igual que las dos herramientas
    # originales.
    tool_block = make_tool_use_block(
        "buscar_empleados_alternativos",
        {"service_name": "Corte", "date": "2026-07-20"},
    )
    first_response = make_response([tool_block])
    second_response = make_response([make_text_block("Juan tiene hueco a las 10:00.")])
    mock_anthropic.chat_with_tools.side_effect = [first_response, second_response]
    mock_execute_appointment.return_value = "Empleados con hueco ese día: Juan (10:00)"

    db = MagicMock()
    result = await handle_assistant_request(
        db=db, business_id="business-1", customer_phone="+34600000099",
        message_text="¿algún otro empleado libre?",
    )

    assert result["tools_called"] == ["buscar_empleados_alternativos"]
    mock_execute_appointment.assert_called_once_with(
        db, "business-1", "+34600000099", "buscar_empleados_alternativos",
        {"service_name": "Corte", "date": "2026-07-20"},
    )


def test_all_tools_includes_pending_appointment_tools():
    from app.domain.conversations.assistant_handler import ALL_TOOLS

    tool_names = {tool["name"] for tool in ALL_TOOLS}
    assert "buscar_empleados_alternativos" in tool_names
    assert "crear_cita_pendiente" in tool_names