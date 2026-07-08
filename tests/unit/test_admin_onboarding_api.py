import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.auth import get_verified_claims

client = TestClient(app)


class FakeDBSessionCtx:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        return False


@patch("app.api.admin.onboarding.get_db_session")
def test_create_business_creates_business_and_owner(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)
    app.dependency_overrides[get_verified_claims] = lambda: {"sub": "cognito-sub-nuevo"}

    try:
        response = client.post(
            "/api/admin/businesses",
            json={
                "business_name": "Peluquería Nueva",
                "owner_name": "María",
                "whatsapp_number": "+34600111222",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["business_name"] == "Peluquería Nueva"
    assert data["owner_name"] == "María"
    assert "business_id" in data
    mock_db.add.assert_called()
    mock_db.commit.assert_awaited_once()


@patch("app.api.admin.onboarding.get_db_session")
def test_create_business_rejects_when_cognito_user_already_linked(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock()))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)
    app.dependency_overrides[get_verified_claims] = lambda: {"sub": "cognito-sub-existente"}

    try:
        response = client.post(
            "/api/admin/businesses",
            json={
                "business_name": "Otro Negocio",
                "owner_name": "Pedro",
                "whatsapp_number": "+34600333444",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    mock_db.add.assert_not_called()


@patch("app.api.admin.onboarding.get_db_session")
def test_create_business_rejects_duplicate_whatsapp_number(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.commit.side_effect = IntegrityError("stmt", "params", Exception("duplicate key"))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)
    app.dependency_overrides[get_verified_claims] = lambda: {"sub": "cognito-sub-nuevo"}

    try:
        response = client.post(
            "/api/admin/businesses",
            json={
                "business_name": "Peluquería Duplicada",
                "owner_name": "Ana",
                "whatsapp_number": "+34677453127",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    mock_db.rollback.assert_awaited_once()


def test_create_business_requires_authentication():
    response = client.post(
        "/api/admin/businesses",
        json={"business_name": "X", "owner_name": "Y", "whatsapp_number": "+34600000000"},
    )

    assert response.status_code == 401


def test_create_business_rejects_missing_fields():
    app.dependency_overrides[get_verified_claims] = lambda: {"sub": "cognito-sub-nuevo"}
    try:
        response = client.post("/api/admin/businesses", json={"business_name": "Solo esto"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422