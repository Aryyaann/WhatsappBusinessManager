import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class FakeDBSessionCtx:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        return False


def make_row(name, quantity, sku="SKU-1", unit="unidad", min_stock_threshold=0, sale_price=Decimal("9.00")):
    product = MagicMock()
    product.id = "product-1"
    product.name = name
    product.sku = sku
    product.unit = unit
    product.min_stock_threshold = min_stock_threshold
    product.sale_price = sale_price
    return MagicMock(Product=product, quantity=quantity)


@patch("app.api.admin.products.get_db_session")
def test_list_products_returns_serialized_products(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(all=MagicMock(return_value=[
        make_row("Tinte Rubio 100ml", Decimal("12")),
    ]))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/products", params={"business_id": "business-1"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Tinte Rubio 100ml"
    assert data[0]["quantity"] == 12.0
    assert data[0]["sale_price"] == 9.0


@patch("app.api.admin.products.get_db_session")
def test_list_products_defaults_quantity_to_zero_when_no_stock_row(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(all=MagicMock(return_value=[
        make_row("Producto Sin Stock", None),
    ]))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/products", params={"business_id": "business-1"})

    assert response.status_code == 200
    assert response.json()[0]["quantity"] == 0.0


@patch("app.api.admin.products.get_db_session")
def test_list_products_returns_empty_list_when_no_products(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/products", params={"business_id": "business-1"})

    assert response.status_code == 200
    assert response.json() == []


def test_list_products_requires_business_id_param():
    response = client.get("/api/admin/products")

    assert response.status_code == 422