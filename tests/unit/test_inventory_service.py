import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# El SDK de OpenAI valida la api_key al construir el cliente, y este módulo
# importa el singleton embedding_client. Ver test_embedding_client.py.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

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
@patch("app.domain.inventory.service.embedding_client")
async def test_apply_albaran_product_not_found_no_semantic_match(mock_embedding_client):
    # Ni match exacto ni semántico: no hay ninguna fila candidata en pgvector.
    mock_embedding_client.embed_text.return_value = [0.1, 0.2]
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # match exacto
        MagicMock(first=MagicMock(return_value=None)),  # match semántico
    ]

    service = InventoryService(db)
    line = AlbaranLine(product_name="Producto Desconocido", quantity=Decimal("5"), unit_cost=Decimal("3"))
    result = make_result([line])

    outcome = await service.apply_albaran("business-1", result, "user-1")

    assert outcome["applied"] == []
    assert "Producto Desconocido" in outcome["skipped"]
    mock_embedding_client.embed_text.assert_called_once_with("Producto Desconocido")


@pytest.mark.asyncio
@patch("app.domain.inventory.service.embedding_client")
async def test_apply_albaran_semantic_match_below_threshold_is_skipped(mock_embedding_client):
    # Hay una fila candidata, pero está demasiado lejos semánticamente
    # (distancia > 0.15) para considerarla el mismo producto.
    mock_embedding_client.embed_text.return_value = [0.1, 0.2]
    fake_row = MagicMock(distance=0.42)
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # match exacto
        MagicMock(first=MagicMock(return_value=fake_row)),  # match semántico, lejos
    ]

    service = InventoryService(db)
    line = AlbaranLine(product_name="Producto Rarísimo", quantity=Decimal("2"), unit_cost=Decimal("1"))
    result = make_result([line])

    outcome = await service.apply_albaran("business-1", result, "user-1")

    assert outcome["applied"] == []
    assert "Producto Rarísimo" in outcome["skipped"]


@pytest.mark.asyncio
@patch("app.domain.inventory.service.embedding_client")
async def test_apply_albaran_semantic_match_within_threshold_updates_stock(mock_embedding_client):
    # El nombre del albarán no coincide literal, pero pgvector encuentra un
    # producto lo bastante cercano (distancia <= 0.15) como para aplicarlo.
    mock_embedding_client.embed_text.return_value = [0.1, 0.2]
    mock_product = MagicMock()
    mock_product.id = "product-uuid-2"
    fake_row = MagicMock(distance=0.05, Product=mock_product)
    mock_stock = MagicMock()
    mock_stock.quantity = Decimal("0")

    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # match exacto: no
        MagicMock(first=MagicMock(return_value=fake_row)),  # match semántico: sí
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_stock)),  # stock lookup
    ]

    service = InventoryService(db)
    line = AlbaranLine(product_name="Tinte Rubio N7", quantity=Decimal("8"), unit_cost=Decimal("4"))
    result = make_result([line])

    outcome = await service.apply_albaran("business-1", result, "user-1")

    assert "Tinte Rubio N7" in outcome["applied"]
    assert outcome["skipped"] == []
    assert mock_stock.quantity == Decimal("8")


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