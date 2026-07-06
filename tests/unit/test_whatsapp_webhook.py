import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# El SDK de OpenAI valida la api_key al construir el cliente, y este módulo
# importa (indirectamente, vía CatalogService/InventoryService) el
# singleton embedding_client.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from app.api.webhooks.whatsapp import (
    _interpret_reply,
    _handle_pending_confirmation_reply,
    _handle_conversational_query,
)


class FakeDBSessionCtx:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        return False


def make_pending_item(**overrides):
    item = {
        "business_id": "business-1",
        "created_by": "user-1",
        "product_name": "Producto 1",
        "quantity": "2",
        "unit_cost": "100",
        "expiry_date": None,
        "lot_number": None,
    }
    item.update(overrides)
    return item


@pytest.mark.parametrize("text,expected", [
    ("si", True), ("SI", True), (" Sí ", True), ("yes", True), ("vale", True),
    ("no", False), ("NO", False), ("cancelar", False),
    ("quizás", None), ("", None), ("hola", None),
])
def test_interpret_reply(text, expected):
    assert _interpret_reply(text) == expected


@pytest.mark.asyncio
@patch("app.api.webhooks.whatsapp.pending_confirmation_service")
async def test_no_pending_returns_none(mock_pending):
    mock_pending.peek_next.return_value = None

    result = await _handle_pending_confirmation_reply("+34600000001", "si")

    assert result is None
    mock_pending.pop_next.assert_not_called()


@pytest.mark.asyncio
@patch("app.api.webhooks.whatsapp.pending_confirmation_service")
async def test_ambiguous_reply_does_not_pop_and_repeats_question(mock_pending):
    mock_pending.peek_next.return_value = make_pending_item()

    result = await _handle_pending_confirmation_reply("+34600000001", "no entiendo")

    assert "Producto 1" in result
    assert "SI" in result and "NO" in result
    mock_pending.pop_next.assert_not_called()


@pytest.mark.asyncio
@patch("app.api.webhooks.whatsapp.pending_confirmation_service")
async def test_rejects_product_without_touching_db(mock_pending):
    mock_pending.peek_next.side_effect = [make_pending_item(), None]
    mock_pending.pop_next.return_value = make_pending_item()

    result = await _handle_pending_confirmation_reply("+34600000001", "no")

    assert "Descartado" in result
    assert "Producto 1" in result
    mock_pending.pop_next.assert_called_once_with("+34600000001")


@pytest.mark.asyncio
@patch("app.api.webhooks.whatsapp.InventoryService")
@patch("app.api.webhooks.whatsapp.CatalogService")
@patch("app.api.webhooks.whatsapp.get_db_session")
@patch("app.api.webhooks.whatsapp.pending_confirmation_service")
async def test_confirms_product_creates_it_and_applies_stock(
    mock_pending, mock_get_db, mock_catalog_cls, mock_inventory_cls
):
    item = make_pending_item()
    # peek_next: primera llamada (para leer la pregunta pendiente),
    # segunda llamada (para ver si hay otra cola después de resolver esta).
    mock_pending.peek_next.side_effect = [item, None]
    mock_pending.pop_next.return_value = item

    mock_db = AsyncMock()
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    mock_product = MagicMock(id="product-new-1")
    mock_catalog_cls.return_value.create_product = AsyncMock(return_value=mock_product)
    mock_inventory_cls.return_value.apply_confirmed_new_product = AsyncMock()

    result = await _handle_pending_confirmation_reply("+34600000001", "si")

    mock_catalog_cls.return_value.create_product.assert_called_once_with(
        business_id="business-1",
        name="Producto 1",
        cost_price=Decimal("100"),
    )
    mock_inventory_cls.return_value.apply_confirmed_new_product.assert_called_once_with(
        business_id="business-1",
        product_id="product-new-1",
        quantity=Decimal("2"),
        unit_cost=Decimal("100"),
        created_by="user-1",
        expiry_date=None,
        lot_number=None,
    )
    assert "Producto añadido" in result
    assert "Producto 1" in result


@pytest.mark.asyncio
@patch("app.api.webhooks.whatsapp.InventoryService")
@patch("app.api.webhooks.whatsapp.CatalogService")
@patch("app.api.webhooks.whatsapp.get_db_session")
@patch("app.api.webhooks.whatsapp.pending_confirmation_service")
async def test_confirms_product_and_chains_next_question(
    mock_pending, mock_get_db, mock_catalog_cls, mock_inventory_cls
):
    item = make_pending_item(product_name="Producto 1")
    next_item = make_pending_item(product_name="Producto 2", quantity="4", unit_cost="50")
    mock_pending.peek_next.side_effect = [item, next_item]
    mock_pending.pop_next.return_value = item

    mock_db = AsyncMock()
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)
    mock_catalog_cls.return_value.create_product = AsyncMock(return_value=MagicMock(id="p1"))
    mock_inventory_cls.return_value.apply_confirmed_new_product = AsyncMock()

    result = await _handle_pending_confirmation_reply("+34600000001", "si")

    assert "Producto 1" in result
    assert "Producto 2" in result  # la siguiente pregunta va encadenada

@pytest.mark.asyncio
@patch("app.api.webhooks.whatsapp.handle_assistant_request")
@patch("app.api.webhooks.whatsapp.ConversationService")
@patch("app.api.webhooks.whatsapp.get_db_session")
async def test_conversational_query_logs_both_sides_and_returns_reply(
    mock_get_db, mock_conversation_cls, mock_handle_query
):
    mock_db = AsyncMock()
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    mock_conversation = MagicMock(id="conv-1")
    mock_conversation_cls.return_value.get_or_create_conversation = AsyncMock(return_value=mock_conversation)
    mock_conversation_cls.return_value.log_message = AsyncMock()

    mock_handle_query.return_value = {
        "reply": "Te quedan 12 unidades de Tinte Rubio 100ml.",
        "tools_called": ["consultar_stock"],
        "tokens_input": 200,
        "tokens_output": 30,
    }

    result = await _handle_conversational_query("business-1", "+34600000001", "qué me queda de tinte rubio")

    assert result == "Te quedan 12 unidades de Tinte Rubio 100ml."
    mock_conversation_cls.return_value.get_or_create_conversation.assert_called_once_with(
        business_id="business-1",
        participant_phone="+34600000001",
        participant_type="owner",
    )
    assert mock_conversation_cls.return_value.log_message.await_count == 2

    inbound_call = mock_conversation_cls.return_value.log_message.call_args_list[0].kwargs
    assert inbound_call["direction"] == "inbound"
    assert inbound_call["content_text"] == "qué me queda de tinte rubio"

    outbound_call = mock_conversation_cls.return_value.log_message.call_args_list[1].kwargs
    assert outbound_call["direction"] == "outbound"
    assert outbound_call["content_text"] == "Te quedan 12 unidades de Tinte Rubio 100ml."
    assert outbound_call["llm_tool_called"] == "consultar_stock"
    assert outbound_call["llm_tokens_input"] == 200
    assert outbound_call["llm_tokens_output"] == 30

    mock_db.commit.assert_awaited_once()

@pytest.mark.asyncio
@patch("app.api.webhooks.whatsapp.InventoryService")
@patch("app.api.webhooks.whatsapp.CatalogService")
@patch("app.api.webhooks.whatsapp.get_db_session")
@patch("app.api.webhooks.whatsapp.pending_confirmation_service")
async def test_confirms_product_passes_expiry_date_and_lot_number(
    mock_pending, mock_get_db, mock_catalog_cls, mock_inventory_cls
):
    item = make_pending_item(expiry_date="2026-12-31", lot_number="LOTE-42")
    mock_pending.peek_next.side_effect = [item, None]
    mock_pending.pop_next.return_value = item

    mock_db = AsyncMock()
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)
    mock_catalog_cls.return_value.create_product = AsyncMock(return_value=MagicMock(id="product-new-1"))
    mock_inventory_cls.return_value.apply_confirmed_new_product = AsyncMock()

    await _handle_pending_confirmation_reply("+34600000001", "si")

    from datetime import date
    mock_inventory_cls.return_value.apply_confirmed_new_product.assert_called_once_with(
        business_id="business-1",
        product_id="product-new-1",
        quantity=Decimal("2"),
        unit_cost=Decimal("100"),
        created_by="user-1",
        expiry_date=date(2026, 12, 31),
        lot_number="LOTE-42",
    )