import os
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


def test_build_alert_message_lists_all_items():
    items = [
        {"product_name": "Tinte Rubio 100ml", "quantity": Decimal("2"), "min_stock_threshold": 5},
        {"product_name": "Mascarilla Keratina", "quantity": Decimal("0"), "min_stock_threshold": 3},
    ]

    message = _build_alert_message(items)

    assert "Tinte Rubio 100ml" in message
    assert "Mascarilla Keratina" in message
    assert "quedan 2" in message
    assert "quedan 0" in message
    assert "mínimo configurado: 5" in message


@pytest.mark.asyncio
@patch("app.workers.alerts_worker.twilio_client")
@patch("app.workers.alerts_worker.LowStockAlertService")
@patch("app.workers.alerts_worker.get_db_session")
async def test_sends_alert_only_for_businesses_with_low_stock(
    mock_get_db, mock_service_cls, mock_twilio
):
    business_with_alert = MagicMock(id="business-1", whatsapp_number="+34600000001", is_active=True)
    business_without_alert = MagicMock(id="business-2", whatsapp_number="+34600000002", is_active=True)

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(
            return_value=[business_with_alert, business_without_alert]
        )))
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    mock_service_instance = mock_service_cls.return_value
    mock_service_instance.get_low_stock_products = AsyncMock(side_effect=[
        [{"product_name": "Tinte Rubio", "quantity": Decimal("1"), "min_stock_threshold": 5}],
        [],
    ])

    alerts_sent = await _send_all_alerts()

    assert alerts_sent == 1
    mock_twilio.send_text.assert_called_once()
    call_kwargs = mock_twilio.send_text.call_args.kwargs
    assert call_kwargs["to_number"] == "+34600000001"
    assert "Tinte Rubio" in call_kwargs["body"]


@pytest.mark.asyncio
@patch("app.workers.alerts_worker.twilio_client")
@patch("app.workers.alerts_worker.LowStockAlertService")
@patch("app.workers.alerts_worker.get_db_session")
async def test_no_alerts_sent_when_no_business_has_low_stock(
    mock_get_db, mock_service_cls, mock_twilio
):
    business = MagicMock(id="business-1", whatsapp_number="+34600000001", is_active=True)

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[business])))
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    mock_service_cls.return_value.get_low_stock_products = AsyncMock(return_value=[])

    alerts_sent = await _send_all_alerts()

    assert alerts_sent == 0
    mock_twilio.send_text.assert_not_called()