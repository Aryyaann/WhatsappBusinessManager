import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from app.domain.conversations.query_handler import handle_stock_query, CONSULTAR_STOCK_TOOL


def make_text_block(text):
    return MagicMock(type="text", text=text)


def make_tool_use_block(name, input_dict, block_id="toolu_1"):
    # OJO: 'name' es un kwarg reservado por MagicMock (fija el nombre interno
    # del mock para su repr), no crea un atributo .name real. Hay que
    # asignarlo aparte para que block.name devuelva el string esperado.
    block = MagicMock(type="tool_use", input=input_dict, id=block_id)
    block.name = name
    return block


def make_response(content_blocks, input_tokens=100, output_tokens=20):
    return MagicMock(
        content=content_blocks,
        usage=MagicMock(input_tokens=input_tokens, output_tokens=output_tokens),
    )


@pytest.mark.asyncio
@patch("app.domain.conversations.query_handler.StockQueryService")
@patch("app.domain.conversations.query_handler.anthropic_client")
async def test_returns_direct_text_when_no_tool_needed(mock_anthropic, mock_stock_cls):
    mock_anthropic.chat_with_tools.return_value = make_response(
        [make_text_block("¡Hola! ¿En qué puedo ayudarte?")],
        input_tokens=50, output_tokens=10,
    )

    result = await handle_stock_query(db=MagicMock(), business_id="business-1", query_text="hola")

    assert result["reply"] == "¡Hola! ¿En qué puedo ayudarte?"
    assert result["tool_called"] is None
    assert result["tokens_input"] == 50
    assert result["tokens_output"] == 10
    mock_anthropic.chat_with_tools.assert_called_once()
    mock_stock_cls.assert_not_called()


@pytest.mark.asyncio
@patch("app.domain.conversations.query_handler.StockQueryService")
@patch("app.domain.conversations.query_handler.anthropic_client")
async def test_executes_tool_and_returns_final_text(mock_anthropic, mock_stock_cls):
    tool_block = make_tool_use_block("consultar_stock", {"query": "tinte rubio"})
    first_response = make_response([tool_block], input_tokens=100, output_tokens=15)
    second_response = make_response(
        [make_text_block("Te quedan 12 unidades de Tinte Rubio 100ml.")],
        input_tokens=130, output_tokens=25,
    )
    mock_anthropic.chat_with_tools.side_effect = [first_response, second_response]

    mock_stock_instance = mock_stock_cls.return_value
    mock_stock_instance.query_stock = AsyncMock(return_value=[
        {"product_name": "Tinte Rubio 100ml", "quantity": Decimal("12"), "unit": "unidad", "sale_price": Decimal("9")}
    ])

    result = await handle_stock_query(db=MagicMock(), business_id="business-1", query_text="qué me queda de tinte rubio")

    mock_stock_instance.query_stock.assert_called_once_with("business-1", "tinte rubio")
    assert result["reply"] == "Te quedan 12 unidades de Tinte Rubio 100ml."
    assert result["tool_called"] == "consultar_stock"
    assert result["tokens_input"] == 100 + 130
    assert result["tokens_output"] == 15 + 25
    assert mock_anthropic.chat_with_tools.call_count == 2

    # La segunda llamada debe incluir el tool_result con el texto correcto.
    second_call_messages = mock_anthropic.chat_with_tools.call_args_list[1].kwargs["messages"]
    tool_result_content = second_call_messages[-1]["content"][0]["content"]
    assert "Tinte Rubio 100ml" in tool_result_content
    assert "12" in tool_result_content


@pytest.mark.asyncio
@patch("app.domain.conversations.query_handler.StockQueryService")
@patch("app.domain.conversations.query_handler.anthropic_client")
async def test_tool_with_no_results_still_gets_final_response(mock_anthropic, mock_stock_cls):
    tool_block = make_tool_use_block("consultar_stock", {"query": "algo raro"})
    first_response = make_response([tool_block])
    second_response = make_response([make_text_block("No encontré ningún producto llamado así.")])
    mock_anthropic.chat_with_tools.side_effect = [first_response, second_response]

    mock_stock_instance = mock_stock_cls.return_value
    mock_stock_instance.query_stock = AsyncMock(return_value=[])

    result = await handle_stock_query(db=MagicMock(), business_id="business-1", query_text="algo raro")

    assert result["reply"] == "No encontré ningún producto llamado así."
    second_call_messages = mock_anthropic.chat_with_tools.call_args_list[1].kwargs["messages"]
    tool_result_content = second_call_messages[-1]["content"][0]["content"]
    assert "No se encontraron productos" in tool_result_content


def test_tool_schema_has_required_query_field():
    assert CONSULTAR_STOCK_TOOL["name"] == "consultar_stock"
    assert CONSULTAR_STOCK_TOOL["input_schema"]["required"] == ["query"]