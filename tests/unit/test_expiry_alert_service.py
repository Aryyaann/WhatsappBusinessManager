from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.alerts.expiry_alert_service import ExpiryAlertService


def make_row(name, expiry_date, lot_number, current_stock):
    # SimpleNamespace en vez de MagicMock porque 'name' es un kwarg
    # reservado por MagicMock (fija el nombre interno del mock, no crea un
    # atributo .name real) — ver test_query_handler.py para el mismo caso.
    return SimpleNamespace(
        name=name, expiry_date=expiry_date, lot_number=lot_number, current_stock=current_stock
    )


@pytest.mark.asyncio
async def test_includes_product_expiring_soon_with_stock():
    db = AsyncMock(spec=AsyncSession)
    soon = date.today() + timedelta(days=3)
    rows = [make_row("Mascarilla Keratina", soon, "LOTE-1", Decimal("5"))]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = ExpiryAlertService(db)
    results = await service.get_expiring_products("business-1")

    assert len(results) == 1
    assert results[0]["product_name"] == "Mascarilla Keratina"
    assert results[0]["expiry_date"] == soon
    assert results[0]["lot_number"] == "LOTE-1"
    assert results[0]["current_stock"] == Decimal("5")


@pytest.mark.asyncio
async def test_excludes_expiring_product_with_zero_current_stock():
    db = AsyncMock(spec=AsyncSession)
    soon = date.today() + timedelta(days=2)
    rows = [make_row("Aceite Argán", soon, "LOTE-2", Decimal("0"))]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = ExpiryAlertService(db)
    results = await service.get_expiring_products("business-1")

    assert results == []


@pytest.mark.asyncio
async def test_excludes_product_with_no_stock_row_at_all():
    db = AsyncMock(spec=AsyncSession)
    soon = date.today() + timedelta(days=2)
    rows = [make_row("Producto Sin Fila Stock", soon, None, None)]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = ExpiryAlertService(db)
    results = await service.get_expiring_products("business-1")

    assert results == []


@pytest.mark.asyncio
async def test_includes_already_expired_lot_with_stock():
    db = AsyncMock(spec=AsyncSession)
    past = date.today() - timedelta(days=1)
    rows = [make_row("Producto Caducado", past, "LOTE-3", Decimal("2"))]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = ExpiryAlertService(db)
    results = await service.get_expiring_products("business-1")

    assert len(results) == 1
    assert results[0]["expiry_date"] == past


@pytest.mark.asyncio
async def test_returns_empty_list_when_no_candidates():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))

    service = ExpiryAlertService(db)
    results = await service.get_expiring_products("business-1")

    assert results == []


@pytest.mark.asyncio
async def test_custom_days_ahead_is_passed_through_without_error():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))

    service = ExpiryAlertService(db)
    results = await service.get_expiring_products("business-1", days_ahead=30)

    assert results == []
    db.execute.assert_called_once()