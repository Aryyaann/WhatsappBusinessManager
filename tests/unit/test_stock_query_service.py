import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# El SDK de OpenAI valida la api_key al construir el cliente, y este módulo
# importa el singleton embedding_client.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from app.domain.inventory.stock_query_service import StockQueryService, QUERY_MATCH_THRESHOLD


def make_row(name, quantity, distance, unit="unidad", sale_price=Decimal("9.00")):
    product = MagicMock()
    product.name = name
    product.unit = unit
    product.sale_price = sale_price
    return MagicMock(Product=product, quantity=quantity, distance=distance)


@pytest.mark.asyncio
@patch("app.domain.inventory.stock_query_service.embedding_client")
async def test_query_stock_generates_embedding_from_query_text(mock_embedding_client):
    mock_embedding_client.embed_text.return_value = [0.1, 0.2]
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))

    service = StockQueryService(db)
    await service.query_stock("business-1", "tinte rubio")

    mock_embedding_client.embed_text.assert_called_once_with("tinte rubio")


@pytest.mark.asyncio
@patch("app.domain.inventory.stock_query_service.embedding_client")
async def test_query_stock_filters_out_results_above_threshold(mock_embedding_client):
    mock_embedding_client.embed_text.return_value = [0.1, 0.2]
    db = AsyncMock(spec=AsyncSession)
    rows = [
        make_row("Tinte Rubio 100ml", Decimal("12"), distance=0.05),
        make_row("Producto Lejano", Decimal("3"), distance=0.60),
    ]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = StockQueryService(db)
    results = await service.query_stock("business-1", "tinte rubio")

    assert len(results) == 1
    assert results[0]["product_name"] == "Tinte Rubio 100ml"
    assert results[0]["quantity"] == Decimal("12")


@pytest.mark.asyncio
@patch("app.domain.inventory.stock_query_service.embedding_client")
async def test_query_stock_defaults_quantity_to_zero_when_no_stock_row(mock_embedding_client):
    mock_embedding_client.embed_text.return_value = [0.1, 0.2]
    db = AsyncMock(spec=AsyncSession)
    rows = [make_row("Producto Sin Stock", None, distance=0.10)]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = StockQueryService(db)
    results = await service.query_stock("business-1", "algo")

    assert results[0]["quantity"] == Decimal("0")


@pytest.mark.asyncio
@patch("app.domain.inventory.stock_query_service.embedding_client")
async def test_query_stock_returns_empty_list_when_no_candidates(mock_embedding_client):
    mock_embedding_client.embed_text.return_value = [0.1, 0.2]
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))

    service = StockQueryService(db)
    results = await service.query_stock("business-1", "algo raro")

    assert results == []


@pytest.mark.asyncio
@patch("app.domain.inventory.stock_query_service.embedding_client")
async def test_query_stock_result_right_at_threshold_boundary_is_excluded(mock_embedding_client):
    mock_embedding_client.embed_text.return_value = [0.1, 0.2]
    db = AsyncMock(spec=AsyncSession)
    rows = [make_row("Justo En El Limite", Decimal("1"), distance=QUERY_MATCH_THRESHOLD + 0.001)]
    db.execute.return_value = MagicMock(all=MagicMock(return_value=rows))

    service = StockQueryService(db)
    results = await service.query_stock("business-1", "algo")

    assert results == []