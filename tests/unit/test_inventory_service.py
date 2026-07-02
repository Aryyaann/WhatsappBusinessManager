import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.inventory.service import InventoryService
from app.schemas.albaran import AlbaranExtraction, AlbaranLine, AlbaranProcessingResult


def make_result(lines_auto, lines_pending=None):
    return AlbaranProcessingResult(
        s3_key="test/key",
        extraction=AlbaranExtraction(lines=lines_auto + (lines_pending or [])),
        lines_auto_confirmed=lines_auto,
        lines_pending_review=lines_pending or [],
    )


@pytest.mark.asyncio
async def test_apply_albaran_product_not_found():
    db = AsyncMock(spec=AsyncSession)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_execute_result

    service = InventoryService(db)
    line = AlbaranLine(product_name="Producto Desconocido", quantity=Decimal("5"), unit_cost=Decimal("3"))
    result = make_result([line])

    outcome = await service.apply_albaran("business-1", result, "user-1")

    assert outcome["applied"] == []
    assert "Producto Desconocido" in outcome["skipped"]


@pytest.mark.asyncio
async def test_apply_albaran_product_found_updates_stock():
    db = AsyncMock(spec=AsyncSession)
    mock_product = MagicMock()
    mock_product.id = "product-uuid-1"
    mock_stock = MagicMock()
    mock_stock.quantity = Decimal("0")
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_product)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_stock)),
    ]

    service = InventoryService(db)
    line = AlbaranLine(product_name="Tinte Rubio", quantity=Decimal("10"), unit_cost=Decimal("5"))
    result = make_result([line])

    outcome = await service.apply_albaran("business-1", result, "user-1")

    assert "Tinte Rubio" in outcome["applied"]
    assert outcome["skipped"] == []
    assert mock_stock.quantity == Decimal("10")


@pytest.mark.asyncio
async def test_apply_albaran_no_auto_lines():
    db = AsyncMock(spec=AsyncSession)
    service = InventoryService(db)

    line = AlbaranLine(product_name="X", quantity=Decimal("1"), unit_cost=Decimal("1"), confidence_score=0.5)
    result = make_result([], lines_pending=[line])

    outcome = await service.apply_albaran("business-1", result, "user-1")

    assert outcome["applied"] == []
    assert outcome["skipped"] == []
    db.execute.assert_not_called()