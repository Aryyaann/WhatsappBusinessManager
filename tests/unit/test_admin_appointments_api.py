import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from fastapi.testclient import TestClient

from app.main import app
from app.models.appointment import AppointmentStatusEnum

client = TestClient(app)


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
    # Row-like objeto que soporta tanto acceso por atributo (row.Appointment)
    # como por índice (row[1], row[2]) porque select(Appointment, User.name,
    # Service.name) devuelve una Row así.
    row = MagicMock()
    row.Appointment = appointment
    row.__getitem__ = lambda self, idx: [appointment, employee_name, service_name][idx]
    return row


@patch("app.api.admin.appointments.get_db_session")
def test_list_appointments_returns_serialized_appointments(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(all=MagicMock(return_value=[make_row()]))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/appointments", params={"business_id": "business-1"})

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

    response = client.get("/api/admin/appointments", params={"business_id": "business-1"})

    assert response.status_code == 200
    assert response.json()[0]["service_name"] is None


@patch("app.api.admin.appointments.get_db_session")
def test_list_appointments_returns_empty_list_when_no_appointments(mock_get_db):
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    response = client.get("/api/admin/appointments", params={"business_id": "business-1"})

    assert response.status_code == 200
    assert response.json() == []


def test_list_appointments_requires_business_id_param():
    response = client.get("/api/admin/appointments")

    assert response.status_code == 422


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
        params={"business_id": "business-1"},
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
        params={"business_id": "business-1"},
        json={"status": "confirmed"},
    )

    assert response.status_code == 404


def test_update_status_rejects_invalid_status_value():
    response = client.patch(
        "/api/admin/appointments/appt-1/status",
        params={"business_id": "business-1"},
        json={"status": "not_a_real_status"},
    )

    assert response.status_code == 422