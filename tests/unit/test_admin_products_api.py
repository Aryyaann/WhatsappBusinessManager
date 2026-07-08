import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_as_business_1():
    # La mayoría de tests de este archivo asumen un usuario ya autenticado
    # perteneciente a "business-1" — los tests que quieran probar el caso
    # sin autenticación limpian el override ellos mismos.
    mock_user = MagicMock(business_id="business-1")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.clear()


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

    response = client.get("/api/admin/products")

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

    response = client.get("/api/admin/products")

    assert response.status_code == 200
    assert response.json()[0]["quantity"] == 0.0


@patch("app.api.admin.products.get_db_session")
def test_list_products_returns_empty_list_when_no_products(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/products")

    assert response.status_code == 200
    assert response.json() == []


def test_list_products_requires_authentication():
    # Sin override de get_current_user (y sin header Authorization real),
    # el endpoint debe rechazar la petición antes de tocar la base de datos.
    app.dependency_overrides.clear()
    response = client.get("/api/admin/products")

    assert response.status_code == 401


@patch("app.api.admin.products.CatalogService")
@patch("app.api.admin.products.get_db_session")
def test_create_product_creates_and_returns_it(mock_get_db, mock_catalog_cls):
    mock_db = AsyncMock()
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)
    created = MagicMock()
    created.id = "product-nuevo"
    created.sku = "SKU-9"
    created.unit = MagicMock(value="unidad")
    created.min_stock_threshold = 5
    created.sale_price = Decimal("12.50")
    created.name = "Champú Anticaspa"
    mock_catalog_cls.return_value.create_product = AsyncMock(return_value=created)

    response = client.post(
        "/api/admin/products",
        json={"name": "Champú Anticaspa", "sale_price": 12.5, "min_stock_threshold": 5},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Champú Anticaspa"
    assert data["sale_price"] == 12.5
    assert data["unit"] == "unidad"
    mock_catalog_cls.return_value.create_product.assert_awaited_once()


def test_create_product_rejects_empty_name():
    response = client.post("/api/admin/products", json={"name": ""})

    assert response.status_code == 422


def test_create_product_rejects_negative_price():
    response = client.post(
        "/api/admin/products",
        json={"name": "X", "sale_price": -3},
    )

    assert response.status_code == 422


def test_create_product_requires_authentication():
    app.dependency_overrides.clear()
    response = client.post("/api/admin/products", json={"name": "X"})

    assert response.status_code == 401


@patch("app.api.admin.products.InventoryService")
@patch("app.api.admin.products.get_db_session")
def test_adjust_stock_updates_quantity(mock_get_db, mock_inventory_cls):
    mock_db = AsyncMock()
    mock_product = MagicMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_product))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)
    mock_inventory_cls.return_value.set_stock_quantity = AsyncMock()

    response = client.patch(
        "/api/admin/products/product-1/stock",
        json={"quantity": 15},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "product_id": "product-1", "quantity": 15.0}
    mock_inventory_cls.return_value.set_stock_quantity.assert_called_once_with(
        business_id="business-1", product_id="product-1", new_quantity=Decimal("15")
    )


@patch("app.api.admin.products.get_db_session")
def test_adjust_stock_returns_404_when_product_not_found(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.patch(
        "/api/admin/products/missing-id/stock",
        json={"quantity": 15},
    )

    assert response.status_code == 404


def test_adjust_stock_rejects_negative_quantity():
    response = client.patch(
        "/api/admin/products/product-1/stock",
        json={"quantity": -5},
    )

    assert response.status_code == 422


@patch("app.api.admin.products.get_db_session")
def test_update_threshold_sets_new_value(mock_get_db):
    mock_db = AsyncMock()
    mock_product = MagicMock(min_stock_threshold=0)
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_product))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.patch(
        "/api/admin/products/product-1/threshold",
        json={"min_stock_threshold": 10},
    )

    assert response.status_code == 200
    assert mock_product.min_stock_threshold == 10
    mock_db.commit.assert_awaited_once()


@patch("app.api.admin.products.get_db_session")
def test_update_threshold_returns_404_when_product_not_found(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.patch(
        "/api/admin/products/missing-id/threshold",
        json={"min_stock_threshold": 10},
    )

    assert response.status_code == 404