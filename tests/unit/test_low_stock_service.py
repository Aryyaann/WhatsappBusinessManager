from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.alerts.low_stock_service import LowStockAlertService


def make_row(name, quantity, min_stock_threshold, product_id="prod-1"):
    product = MagicMock()
    product.id = product_id
    product.name = name
    product.min_stock_threshold = min_stock_threshold
    return MagicMock(Product=product, quantity=quantity)


@pytest.mark.asyncio
async def test_includes_product_below_threshold():
    db = AsyncMock(spec=AsyncSession)
    rows = [make_row("Tinte Rubio 100ml", Decimal("2"), min_stock_threshold=5)]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = LowStockAlertService(db)
    results = await service.get_low_stock_products("business-1")

    assert len(results) == 1
    assert results[0]["product_name"] == "Tinte Rubio 100ml"
    assert results[0]["quantity"] == Decimal("2")
    assert results[0]["min_stock_threshold"] == 5


@pytest.mark.asyncio
async def test_includes_product_exactly_at_threshold():
    db = AsyncMock(spec=AsyncSession)
    rows = [make_row("Mascarilla Keratina", Decimal("5"), min_stock_threshold=5)]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = LowStockAlertService(db)
    results = await service.get_low_stock_products("business-1")

    assert len(results) == 1


@pytest.mark.asyncio
async def test_excludes_product_above_threshold():
    db = AsyncMock(spec=AsyncSession)
    rows = [make_row("Aceite Argán", Decimal("20"), min_stock_threshold=5)]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = LowStockAlertService(db)
    results = await service.get_low_stock_products("business-1")

    assert results == []


@pytest.mark.asyncio
async def test_treats_missing_stock_row_as_zero():
    db = AsyncMock(spec=AsyncSession)
    rows = [make_row("Producto Sin Stock", None, min_stock_threshold=3)]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = LowStockAlertService(db)
    results = await service.get_low_stock_products("business-1")

    assert len(results) == 1
    assert results[0]["quantity"] == Decimal("0")


@pytest.mark.asyncio
async def test_returns_empty_list_when_no_candidates():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))

    service = LowStockAlertService(db)
    results = await service.get_low_stock_products("business-1")

    assert results == []