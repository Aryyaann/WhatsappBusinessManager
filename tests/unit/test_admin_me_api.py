import os
from unittest.mock import MagicMock

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.models.user import RoleEnum

client = TestClient(app)


def test_get_me_returns_current_user_data():
    mock_user = MagicMock(
        id="user-1",
        role=RoleEnum.employee,
        business_id="business-1",
    )
    mock_user.name = "Ana"
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        response = client.get("/api/admin/me")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Ana"
        assert data["role"] == "employee"
        assert data["business_id"] == "business-1"
    finally:
        app.dependency_overrides.clear()


def test_get_me_requires_authentication_when_not_overridden():
    # Sin dependency_override y sin header Authorization real, la
    # dependencia get_current_user debe rechazar la petición.
    response = client.get("/api/admin/me")

    assert response.status_code == 401