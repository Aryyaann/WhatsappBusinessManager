import os
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.auth import get_current_user

client = TestClient(app)

MONDAY = "2026-07-06"


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
    employee = MagicMock(id="emp-1", whatsapp_number="+34600111222")
    employee.name = "Ana"
    mock_db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[employee])))
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/employees")

    assert response.status_code == 200
    assert response.json() == [{"id": "emp-1", "name": "Ana", "whatsapp_number": "+34600111222"}]


def test_list_employees_requires_authentication():
    app.dependency_overrides.clear()
    response = client.get("/api/admin/employees")

    assert response.status_code == 401


@patch("app.api.admin.employees.get_db_session")
def test_create_employee_creates_user_without_schedule(mock_get_db):
    # Ya no se fija horario al crear — se planifica después desde el
    # Gantt, así que crear un empleado es solo nombre + WhatsApp.
    mock_db = AsyncMock(spec=AsyncSession)

    async def fake_refresh(employee):
        employee.id = "emp-nuevo"

    mock_db.refresh.side_effect = fake_refresh
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.post(
        "/api/admin/employees",
        json={"name": "Lucía", "whatsapp_number": "+34600222333"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Lucía"
    assert data["whatsapp_number"] == "+34600222333"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


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


@patch("app.api.admin.employees.get_db_session")
def test_get_weekly_schedule_groups_slots_by_employee(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    ana = MagicMock(id="emp-1")
    ana.name = "Ana"
    slot = MagicMock(id="block-1", user_id="emp-1", date=date(2026, 7, 6))
    slot.start_time = time(9, 0)
    slot.end_time = time(17, 0)
    mock_db.execute.side_effect = [
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[ana])))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[slot])))),
    ]
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/employees/schedule", params={"week_start": MONDAY})

    assert response.status_code == 200
    data = response.json()
    assert data == [
        {
            "employee_id": "emp-1",
            "employee_name": "Ana",
            "schedule": [
                {"id": "block-1", "date": "2026-07-06", "start_time": "09:00:00", "end_time": "17:00:00"}
            ],
        }
    ]


def test_get_weekly_schedule_requires_week_start_param():
    response = client.get("/api/admin/employees/schedule")

    assert response.status_code == 422


@patch("app.api.admin.employees.get_db_session")
def test_get_weekly_schedule_supports_multiple_blocks_same_day(mock_get_db):
    # Turno partido: dos bloques el mismo día para el mismo empleado.
    mock_db = AsyncMock(spec=AsyncSession)
    ana = MagicMock(id="emp-1")
    ana.name = "Ana"
    morning = MagicMock(id="block-1", user_id="emp-1", date=date(2026, 7, 6))
    morning.start_time = time(9, 0)
    morning.end_time = time(13, 0)
    afternoon = MagicMock(id="block-2", user_id="emp-1", date=date(2026, 7, 6))
    afternoon.start_time = time(16, 0)
    afternoon.end_time = time(20, 0)
    mock_db.execute.side_effect = [
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[ana])))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[morning, afternoon])))),
    ]
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/employees/schedule", params={"week_start": MONDAY})

    assert response.status_code == 200
    assert len(response.json()[0]["schedule"]) == 2


@patch("app.api.admin.employees.get_db_session")
def test_create_schedule_block_adds_new_block(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    employee = MagicMock(id="emp-1")

    async def fake_refresh(block):
        block.id = "block-nuevo"

    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
    mock_db.refresh.side_effect = fake_refresh
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.post(
        "/api/admin/employees/emp-1/schedule",
        json={"date": "2026-07-08", "start_time": "10:00:00", "end_time": "18:00:00"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "block-nuevo"
    assert data["date"] == "2026-07-08"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@patch("app.api.admin.employees.get_db_session")
def test_create_schedule_block_returns_404_when_employee_not_found(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.post(
        "/api/admin/employees/missing-id/schedule",
        json={"date": "2026-07-08", "start_time": "10:00:00", "end_time": "18:00:00"},
    )

    assert response.status_code == 404


def test_create_schedule_block_rejects_end_before_start():
    response = client.post(
        "/api/admin/employees/emp-1/schedule",
        json={"date": "2026-07-08", "start_time": "18:00:00", "end_time": "10:00:00"},
    )

    assert response.status_code == 422


def test_create_schedule_block_requires_authentication():
    app.dependency_overrides.clear()
    response = client.post(
        "/api/admin/employees/emp-1/schedule",
        json={"date": "2026-07-08", "start_time": "10:00:00", "end_time": "18:00:00"},
    )

    assert response.status_code == 401


@patch("app.api.admin.employees.get_db_session")
def test_update_schedule_block_moves_it(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    employee = MagicMock(id="emp-1")
    block = MagicMock(id="block-1")
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=employee)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=block)),
    ]
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.patch(
        "/api/admin/employees/emp-1/schedule/block-1",
        json={"date": "2026-07-09", "start_time": "11:00:00", "end_time": "19:00:00"},
    )

    assert response.status_code == 200
    assert block.date == date(2026, 7, 9)
    mock_db.commit.assert_awaited_once()


@patch("app.api.admin.employees.get_db_session")
def test_update_schedule_block_returns_404_when_block_not_found(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    employee = MagicMock(id="emp-1")
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=employee)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
    ]
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.patch(
        "/api/admin/employees/emp-1/schedule/missing-block",
        json={"date": "2026-07-09", "start_time": "11:00:00", "end_time": "19:00:00"},
    )

    assert response.status_code == 404


@patch("app.api.admin.employees.get_db_session")
def test_delete_schedule_block_removes_it(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    employee = MagicMock(id="emp-1")
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=employee)),
        MagicMock(rowcount=1),
    ]
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.delete("/api/admin/employees/emp-1/schedule/block-1")

    assert response.status_code == 200
    mock_db.commit.assert_awaited_once()


@patch("app.api.admin.employees.get_db_session")
def test_delete_schedule_block_returns_404_when_employee_not_found(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.delete("/api/admin/employees/missing-id/schedule/block-1")

    assert response.status_code == 404


@patch("app.api.admin.employees.get_db_session")
def test_delete_schedule_block_returns_404_when_block_not_found(mock_get_db):
    mock_db = AsyncMock(spec=AsyncSession)
    employee = MagicMock(id="emp-1")
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=employee)),
        MagicMock(rowcount=0),
    ]
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.delete("/api/admin/employees/emp-1/schedule/missing-block")

    assert response.status_code == 404