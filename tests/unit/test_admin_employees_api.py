import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.auth import get_current_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_as_business_1():
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


@patch("app.api.admin.employees.get_db_session")
def test_list_employees_returns_only_employees(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    employee = MagicMock(id="emp-1")
    employee.name = "Ana"
    mock_db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[employee])))
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/employees")

    assert response.status_code == 200
    assert response.json() == [{"id": "emp-1", "name": "Ana"}]


def test_list_employees_requires_authentication():
    app.dependency_overrides.clear()
    response = client.get("/api/admin/employees")

    assert response.status_code == 401


@patch("app.api.admin.employees.get_db_session")
def test_create_employee_with_schedule_creates_user_and_schedule_rows(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.post(
        "/api/admin/employees",
        json={
            "name": "Lucía",
            "whatsapp_number": "+34600222333",
            "schedule": [
                {"day_of_week": 0, "start_time": "09:00:00", "end_time": "14:00:00"},
                {"day_of_week": 2, "start_time": "09:00:00", "end_time": "14:00:00"},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Lucía"
    assert data["schedule_slots_created"] == 2
    # User + 2 filas de EmployeeSchedule = 3 llamadas a add()
    assert mock_db.add.call_count == 3
    mock_db.commit.assert_awaited_once()


@patch("app.api.admin.employees.get_db_session")
def test_create_employee_without_schedule_still_works(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.post(
        "/api/admin/employees",
        json={"name": "Pedro", "whatsapp_number": "+34600444555"},
    )

    assert response.status_code == 200
    assert response.json()["schedule_slots_created"] == 0


def test_create_employee_rejects_end_time_before_start_time():
    response = client.post(
        "/api/admin/employees",
        json={
            "name": "Lucía",
            "whatsapp_number": "+34600222333",
            "schedule": [
                {"day_of_week": 0, "start_time": "14:00:00", "end_time": "09:00:00"},
            ],
        },
    )

    assert response.status_code == 422


def test_create_employee_rejects_invalid_day_of_week():
    response = client.post(
        "/api/admin/employees",
        json={
            "name": "Lucía",
            "whatsapp_number": "+34600222333",
            "schedule": [
                {"day_of_week": 7, "start_time": "09:00:00", "end_time": "14:00:00"},
            ],
        },
    )

    assert response.status_code == 422


def test_create_employee_rejects_empty_name():
    response = client.post(
        "/api/admin/employees",
        json={"name": "", "whatsapp_number": "+34600222333"},
    )

    assert response.status_code == 422


def test_create_employee_requires_authentication():
    app.dependency_overrides.clear()
    response = client.post(
        "/api/admin/employees",
        json={"name": "Lucía", "whatsapp_number": "+34600222333"},
    )

    assert response.status_code == 401