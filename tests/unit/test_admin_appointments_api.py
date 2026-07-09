import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.models.appointment import AppointmentStatusEnum

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


def make_row(
    customer_name="Lucía",
    customer_phone="+34600000099",
    employee_name="Ana",
    service_name="Corte de pelo",
    status=AppointmentStatusEnum.confirmed,
    notes=None,
):
    appointment = MagicMock()
    appointment.id = "appt-1"
    appointment.customer_name = customer_name
    appointment.customer_phone = customer_phone
    appointment.start_at = datetime(2026, 7, 13, 9, 0)
    appointment.end_at = datetime(2026, 7, 13, 9, 30)
    appointment.status = status
    appointment.notes = notes
    row = MagicMock()
    row.Appointment = appointment
    row.__getitem__ = lambda self, idx: [appointment, employee_name, service_name][idx]
    return row


@patch("app.api.admin.appointments.get_db_session")
def test_list_appointments_returns_serialized_appointments(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(all=MagicMock(return_value=[make_row()]))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/appointments")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["customer_name"] == "Lucía"
    assert data[0]["employee_name"] == "Ana"
    assert data[0]["service_name"] == "Corte de pelo"
    assert data[0]["status"] == "confirmed"
    assert data[0]["start_at"] == "2026-07-13T09:00:00"


@patch("app.api.admin.appointments.get_db_session")
def test_list_appointments_allows_null_service_name(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(
        all=MagicMock(return_value=[make_row(service_name=None)])
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/appointments")

    assert response.status_code == 200
    assert response.json()[0]["service_name"] is None


@patch("app.api.admin.appointments.get_db_session")
def test_list_appointments_returns_empty_list_when_no_appointments(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/appointments")

    assert response.status_code == 200
    assert response.json() == []


def test_list_appointments_requires_authentication():
    app.dependency_overrides.clear()
    response = client.get("/api/admin/appointments")

    assert response.status_code == 401


@patch("app.api.admin.appointments.get_db_session")
def test_update_status_sets_new_value(mock_get_db):
    mock_db = AsyncMock()
    mock_appointment = MagicMock(status=AppointmentStatusEnum.pending)
    mock_db.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=mock_appointment)
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.patch(
        "/api/admin/appointments/appt-1/status",
        json={"status": "confirmed"},
    )

    assert response.status_code == 200
    assert mock_appointment.status == AppointmentStatusEnum.confirmed
    mock_db.commit.assert_awaited_once()


@patch("app.api.admin.appointments.get_db_session")
def test_update_status_returns_404_when_appointment_not_found(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.patch(
        "/api/admin/appointments/missing-id/status",
        json={"status": "confirmed"},
    )

    assert response.status_code == 404


def test_update_status_rejects_invalid_status_value():
    response = client.patch(
        "/api/admin/appointments/appt-1/status",
        json={"status": "not_a_real_status"},
    )

    assert response.status_code == 422


@patch("app.api.admin.appointments.get_db_session")
def test_list_employees_returns_only_employees(mock_get_db):
    mock_db = AsyncMock()
    employee = MagicMock(id="emp-1")
    employee.name = "Ana"
    mock_db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[employee])))
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/employees")

    assert response.status_code == 200
    assert response.json() == [{"id": "emp-1", "name": "Ana"}]


@patch("app.api.admin.appointments.get_db_session")
def test_list_services_returns_active_services(mock_get_db):
    mock_db = AsyncMock()
    service = MagicMock(id="service-1", duration_minutes=30, price=None)
    service.name = "Corte de pelo"
    mock_db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[service])))
    )
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/services")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "service-1", "name": "Corte de pelo", "duration_minutes": 30, "price": None}
    ]


@patch("app.api.admin.appointments.BookingService")
@patch("app.api.admin.appointments.get_db_session")
def test_create_appointment_books_it(mock_get_db, mock_booking_cls):
    mock_db = AsyncMock()
    mock_service = MagicMock(id="service-1", duration_minutes=30)
    mock_service.name = "Corte de pelo"
    mock_employee = MagicMock(id="emp-1")
    mock_employee.name = "Ana"
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_service)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_employee)),
    ]
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    created = MagicMock(
        id="appt-nueva",
        start_at=datetime(2026, 7, 13, 10, 0),
        end_at=datetime(2026, 7, 13, 10, 30),
        status=AppointmentStatusEnum.pending,
    )
    mock_booking_cls.return_value.book_appointment = AsyncMock(return_value=created)

    response = client.post(
        "/api/admin/appointments",
        json={
            "employee_id": "emp-1",
            "service_id": "service-1",
            "start_at": "2026-07-13T10:00:00",
            "customer_name": "Marcos",
            "customer_phone": "+34600000001",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["employee_name"] == "Ana"
    assert data["service_name"] == "Corte de pelo"
    assert data["status"] == "pending"
    mock_booking_cls.return_value.book_appointment.assert_awaited_once()


@patch("app.api.admin.appointments.get_db_session")
def test_create_appointment_returns_404_when_service_not_found(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.post(
        "/api/admin/appointments",
        json={
            "employee_id": "emp-1",
            "service_id": "missing-service",
            "start_at": "2026-07-13T10:00:00",
            "customer_phone": "+34600000001",
        },
    )

    assert response.status_code == 404


@patch("app.api.admin.appointments.BookingService")
@patch("app.api.admin.appointments.get_db_session")
def test_create_appointment_returns_409_when_slot_taken(mock_get_db, mock_booking_cls):
    from app.domain.appointments.booking_service import SlotNoLongerAvailableError

    mock_db = AsyncMock()
    mock_service = MagicMock(id="service-1", duration_minutes=30)
    mock_employee = MagicMock(id="emp-1")
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_service)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_employee)),
    ]
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)
    mock_booking_cls.return_value.book_appointment = AsyncMock(
        side_effect=SlotNoLongerAvailableError("El hueco de las 10:00 ya no está disponible.")
    )

    response = client.post(
        "/api/admin/appointments",
        json={
            "employee_id": "emp-1",
            "service_id": "service-1",
            "start_at": "2026-07-13T10:00:00",
            "customer_phone": "+34600000001",
        },
    )

    assert response.status_code == 409


def test_create_appointment_requires_authentication():
    app.dependency_overrides.clear()
    response = client.post(
        "/api/admin/appointments",
        json={
            "employee_id": "emp-1",
            "service_id": "service-1",
            "start_at": "2026-07-13T10:00:00",
            "customer_phone": "+34600000001",
        },
    )

    assert response.status_code == 401