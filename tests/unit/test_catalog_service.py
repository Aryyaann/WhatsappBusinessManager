import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Mismo motivo que en test_embedding_client.py: el SDK de OpenAI valida la
# api_key al construir el cliente, y CatalogService importa el singleton
# embedding_client (que instancia EmbeddingClient a nivel de módulo).
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from app.domain.catalog.service import CatalogService


@pytest.mark.asyncio
@patch("app.domain.catalog.service.embedding_client")
async def test_create_product_generates_embedding_from_name_only(mock_embedding_client):
    mock_embedding_client.embed_text.return_value = [0.1, 0.2, 0.3]
    db = AsyncMock(spec=AsyncSession)

    service = CatalogService(db)
    product = await service.create_product(business_id="business-1", name="Tinte Rubio 100ml")

    mock_embedding_client.embed_text.assert_called_once_with("Tinte Rubio 100ml")
    assert product.embedding == [0.1, 0.2, 0.3]
    assert product.name == "Tinte Rubio 100ml"
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.domain.catalog.service.embedding_client")
async def test_create_product_embedding_text_combines_name_and_description(mock_embedding_client):
    mock_embedding_client.embed_text.return_value = [0.4, 0.5]
    db = AsyncMock(spec=AsyncSession)

    service = CatalogService(db)
    await service.create_product(
        business_id="business-1",
        name="Mascarilla Keratina",
        description="Bote 500ml, uso profesional",
    )

    mock_embedding_client.embed_text.assert_called_once_with(
        "Mascarilla Keratina. Bote 500ml, uso profesional"
    )


@pytest.mark.asyncio
@patch("app.domain.catalog.service.embedding_client")
async def test_update_product_not_found_returns_none(mock_embedding_client):
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    service = CatalogService(db)
    result = await service.update_product_name_or_description("missing-id", name="Nuevo nombre")

    assert result is None
    mock_embedding_client.embed_text.assert_not_called()


@pytest.mark.asyncio
@patch("app.domain.catalog.service.embedding_client")
async def test_update_product_regenerates_embedding_when_name_changes(mock_embedding_client):
    mock_embedding_client.embed_text.return_value = [0.9, 0.9]
    mock_product = MagicMock()
    mock_product.name = "Nombre Viejo"
    mock_product.description = None

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_product))

    service = CatalogService(db)
    result = await service.update_product_name_or_description("product-1", name="Nombre Nuevo")

    assert mock_product.name == "Nombre Nuevo"
    mock_embedding_client.embed_text.assert_called_once_with("Nombre Nuevo")
    assert mock_product.embedding == [0.9, 0.9]
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.domain.catalog.service.embedding_client")
async def test_update_product_skips_embedding_when_only_price_relevant_fields_unchanged(mock_embedding_client):
    # Simula que se llama a update sin pasar name ni description (ej. si en el
    # futuro el método creciera para aceptar otros campos) — aquí simplemente
    # no se pasa nada de texto, así que no debe regenerar el embedding.
    mock_product = MagicMock()
    mock_product.name = "Nombre Igual"
    mock_product.description = "Descripcion Igual"

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_product))

    service = CatalogService(db)
    result = await service.update_product_name_or_description("product-1")

    mock_embedding_client.embed_text.assert_not_called()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.domain.catalog.service.embedding_client")
async def test_update_product_skips_embedding_when_name_passed_but_identical(mock_embedding_client):
    mock_product = MagicMock()
    mock_product.name = "Mismo Nombre"
    mock_product.description = None

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_product))

    service = CatalogService(db)
    await service.update_product_name_or_description("product-1", name="Mismo Nombre")

    mock_embedding_client.embed_text.assert_not_called()