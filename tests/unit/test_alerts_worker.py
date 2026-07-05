import os
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from app.workers.alerts_worker import _send_all_alerts, _build_alert_message


class FakeDBSessionCtx:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        return False


def make_low_stock_item(name="Tinte Rubio", quantity=Decimal("2"), threshold=5):
    return {"product_name": name, "quantity": quantity, "min_stock_threshold": threshold}


def make_expiring_item(name="Mascarilla Keratina", expiry=None, lot="LOTE-1", stock=Decimal("3")):
    return {
        "product_name": name,
        "expiry_date": expiry or (date.today() + timedelta(days=2)),
        "lot_number": lot,
        "current_stock": stock,
    }


def test_build_alert_message_includes_both_sections():
    message = _build_alert_message([make_low_stock_item()], [make_expiring_item()])

    assert "Stock bajo" in message
    assert "Tinte Rubio" in message
    assert "Próximas caducidades" in message
    assert "Mascarilla Keratina" in message
    assert "LOTE-1" in message


def test_build_alert_message_only_low_stock_omits_expiry_section():
    message = _build_alert_message([make_low_stock_item()], [])

    assert "Stock bajo" in message
    assert "Próximas caducidades" not in message


def test_build_alert_message_only_expiring_omits_low_stock_section():
    message = _build_alert_message([], [make_expiring_item()])

    assert "Próximas caducidades" in message
    assert "Stock bajo" not in message


def test_build_alert_message_without_lot_number_omits_lot_text():
    item = make_expiring_item(lot=None)
    message = _build_alert_message([], [item])

    assert "lote" not in message.lower()


@pytest.mark.asyncio
@patch("app.workers.alerts_worker.twilio_client")
@patch("app.workers.alerts_worker.ExpiryAlertService")
@patch("app.workers.alerts_worker.LowStockAlertService")
@patch("app.workers.alerts_worker.get_db_session")
async def test_sends_combined_alert_when_business_has_both(
    mock_get_db, mock_low_stock_cls, mock_expiry_cls, mock_twilio
):
    business = MagicMock(id="business-1", whatsapp_number="+34600000001", is_active=True)

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[business])))
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    mock_low_stock_cls.return_value.get_low_stock_products = AsyncMock(return_value=[make_low_stock_item()])
    mock_expiry_cls.return_value.get_expiring_products = AsyncMock(return_value=[make_expiring_item()])

    alerts_sent = await _send_all_alerts()

    assert alerts_sent == 1
    mock_twilio.send_text.assert_called_once()
    body = mock_twilio.send_text.call_args.kwargs["body"]
    assert "Tinte Rubio" in body
    assert "Mascarilla Keratina" in body


@pytest.mark.asyncio
@patch("app.workers.alerts_worker.twilio_client")
@patch("app.workers.alerts_worker.ExpiryAlertService")
@patch("app.workers.alerts_worker.LowStockAlertService")
@patch("app.workers.alerts_worker.get_db_session")
async def test_no_alert_sent_when_business_has_neither(
    mock_get_db, mock_low_stock_cls, mock_expiry_cls, mock_twilio
):
    business = MagicMock(id="business-1", whatsapp_number="+34600000001", is_active=True)

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[business])))
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    mock_low_stock_cls.return_value.get_low_stock_products = AsyncMock(return_value=[])
    mock_expiry_cls.return_value.get_expiring_products = AsyncMock(return_value=[])

    alerts_sent = await _send_all_alerts()

    assert alerts_sent == 0
    mock_twilio.send_text.assert_not_called()


@pytest.mark.asyncio
@patch("app.workers.alerts_worker.twilio_client")
@patch("app.workers.alerts_worker.ExpiryAlertService")
@patch("app.workers.alerts_worker.LowStockAlertService")
@patch("app.workers.alerts_worker.get_db_session")
async def test_sends_alert_with_only_expiry_and_no_low_stock(
    mock_get_db, mock_low_stock_cls, mock_expiry_cls, mock_twilio
):
    business = MagicMock(id="business-1", whatsapp_number="+34600000001", is_active=True)

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[business])))
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    mock_low_stock_cls.return_value.get_low_stock_products = AsyncMock(return_value=[])
    mock_expiry_cls.return_value.get_expiring_products = AsyncMock(return_value=[make_expiring_item()])

    alerts_sent = await _send_all_alerts()

    assert alerts_sent == 1
    body = mock_twilio.send_text.call_args.kwargs["body"]
    assert "Próximas caducidades" in body
    assert "Stock bajo" not in body