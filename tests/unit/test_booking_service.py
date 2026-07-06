from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.appointments.booking_service import BookingService, SlotNoLongerAvailableError
from app.models.appointment import AppointmentStatusEnum


@pytest.mark.asyncio
@patch("app.domain.appointments.booking_service.AvailabilityService")
async def test_books_appointment_when_slot_is_available(mock_availability_cls):
    requested_slot = datetime(2026, 7, 6, 9, 0)
    mock_availability_cls.return_value.get_available_slots = AsyncMock(
        return_value=[requested_slot, datetime(2026, 7, 6, 9, 30)]
    )
    db = AsyncMock(spec=AsyncSession)

    service = BookingService(db)
    appointment = await service.book_appointment(
        business_id="business-1",
        user_id="user-1",
        customer_phone="+34600000099",
        start_at=requested_slot,
        duration_minutes=30,
        customer_name="Lucía",
    )

    assert appointment.status == AppointmentStatusEnum.pending
    assert appointment.customer_phone == "+34600000099"
    assert appointment.customer_name == "Lucía"
    assert appointment.end_at == datetime(2026, 7, 6, 9, 30)
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.domain.appointments.booking_service.AvailabilityService")
async def test_raises_when_slot_no_longer_available(mock_availability_cls):
    requested_slot = datetime(2026, 7, 6, 9, 0)
    mock_availability_cls.return_value.get_available_slots = AsyncMock(
        return_value=[datetime(2026, 7, 6, 9, 30)]  # el hueco pedido ya no está
    )
    db = AsyncMock(spec=AsyncSession)

    service = BookingService(db)
    with pytest.raises(SlotNoLongerAvailableError):
        await service.book_appointment(
            business_id="business-1",
            user_id="user-1",
            customer_phone="+34600000099",
            start_at=requested_slot,
            duration_minutes=30,
        )

    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.domain.appointments.booking_service.AvailabilityService")
async def test_cancel_appointment_sets_status_cancelled(mock_availability_cls):
    mock_appointment = MagicMock(status=AppointmentStatusEnum.pending)
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_appointment))

    service = BookingService(db)
    result = await service.cancel_appointment("appt-1")

    assert result is mock_appointment
    assert mock_appointment.status == AppointmentStatusEnum.cancelled
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.domain.appointments.booking_service.AvailabilityService")
async def test_cancel_appointment_returns_none_when_not_found(mock_availability_cls):
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    service = BookingService(db)
    result = await service.cancel_appointment("missing-id")

    assert result is None
    db.commit.assert_not_awaited()