from datetime import date, datetime, time, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.appointments.availability_service import AvailabilityService
from app.models.appointment import AppointmentStatusEnum

# Lunes fijo para que los tests no dependan del día en que se ejecuten.
MONDAY = date(2026, 7, 6)
assert MONDAY.weekday() == 0


def make_schedule(start_h, start_m, end_h, end_m):
    return MagicMock(start_time=time(start_h, start_m), end_time=time(end_h, end_m))


def make_appointment(start_h, start_m, end_h, end_m, target_date=MONDAY):
    return MagicMock(
        start_at=datetime.combine(target_date, time(start_h, start_m)),
        end_at=datetime.combine(target_date, time(end_h, end_m)),
    )


def mock_execute_sequence(db, schedule_rows, appointment_rows):
    db.execute.side_effect = [
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=schedule_rows)))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=appointment_rows)))),
    ]


@pytest.mark.asyncio
async def test_no_schedule_returns_empty_and_skips_appointment_query():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))

    service = AvailabilityService(db)
    slots = await service.get_available_slots("user-1", MONDAY, duration_minutes=30)

    assert slots == []
    assert db.execute.call_count == 1  # no llegó a consultar citas


@pytest.mark.asyncio
async def test_full_day_free_generates_slots_at_duration_steps():
    db = AsyncMock(spec=AsyncSession)
    mock_execute_sequence(db, [make_schedule(9, 0, 10, 0)], [])

    service = AvailabilityService(db)
    slots = await service.get_available_slots("user-1", MONDAY, duration_minutes=30)

    assert slots == [
        datetime(2026, 7, 6, 9, 0),
        datetime(2026, 7, 6, 9, 30),
    ]


@pytest.mark.asyncio
async def test_existing_appointment_splits_available_slots():
    db = AsyncMock(spec=AsyncSession)
    # Horario 9:00-11:00, cita ocupada de 9:30 a 10:00.
    mock_execute_sequence(
        db,
        [make_schedule(9, 0, 11, 0)],
        [make_appointment(9, 30, 10, 0)],
    )

    service = AvailabilityService(db)
    slots = await service.get_available_slots("user-1", MONDAY, duration_minutes=30)

    assert datetime(2026, 7, 6, 9, 0) in slots
    assert datetime(2026, 7, 6, 9, 30) not in slots  # ocupado
    assert datetime(2026, 7, 6, 10, 0) in slots
    assert datetime(2026, 7, 6, 10, 30) in slots


@pytest.mark.asyncio
async def test_existing_appointment_with_timezone_aware_datetimes_does_not_crash():
    # Regresión: Postgres devuelve start_at/end_at con tzinfo (columna
    # TIMESTAMP WITH TIME ZONE) aunque el código las construya naive al
    # calcular huecos. Sin la normalización a naive, esto lanzaba
    # "TypeError: can't compare offset-naive and offset-aware datetimes"
    # en real, algo que los tests con mocks naive no detectaban.
    db = AsyncMock(spec=AsyncSession)
    aware_appointment = MagicMock(
        start_at=datetime(2026, 7, 6, 9, 30, tzinfo=timezone.utc),
        end_at=datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
    )
    mock_execute_sequence(
        db,
        [make_schedule(9, 0, 11, 0)],
        [aware_appointment],
    )

    service = AvailabilityService(db)
    slots = await service.get_available_slots("user-1", MONDAY, duration_minutes=30)

    assert datetime(2026, 7, 6, 9, 0) in slots
    assert datetime(2026, 7, 6, 9, 30) not in slots  # ocupado
    assert datetime(2026, 7, 6, 10, 0) in slots


@pytest.mark.asyncio
async def test_duration_that_does_not_fit_produces_no_slot_at_the_end():
    db = AsyncMock(spec=AsyncSession)
    # Hueco de 45 min, servicio de 30 min -> solo cabe un slot, no dos.
    mock_execute_sequence(db, [make_schedule(9, 0, 9, 45)], [])

    service = AvailabilityService(db)
    slots = await service.get_available_slots("user-1", MONDAY, duration_minutes=30)

    assert slots == [datetime(2026, 7, 6, 9, 0)]


@pytest.mark.asyncio
async def test_split_shift_generates_slots_in_both_blocks():
    db = AsyncMock(spec=AsyncSession)
    mock_execute_sequence(
        db,
        [make_schedule(9, 0, 10, 0), make_schedule(16, 0, 17, 0)],
        [],
    )

    service = AvailabilityService(db)
    slots = await service.get_available_slots("user-1", MONDAY, duration_minutes=60)

    assert datetime(2026, 7, 6, 9, 0) in slots
    assert datetime(2026, 7, 6, 16, 0) in slots
    assert len(slots) == 2


@pytest.mark.asyncio
async def test_appointment_fully_covering_schedule_leaves_no_slots():
    db = AsyncMock(spec=AsyncSession)
    mock_execute_sequence(
        db,
        [make_schedule(9, 0, 10, 0)],
        [make_appointment(9, 0, 10, 0)],
    )

    service = AvailabilityService(db)
    slots = await service.get_available_slots("user-1", MONDAY, duration_minutes=30)

    assert slots == []


@pytest.mark.asyncio
async def test_cancelled_appointment_does_not_block_slot():
    # No probamos el filtro SQL directamente (eso ya lo hace la query),
    # pero confirmamos que si no llegan citas "bloqueantes" (porque la
    # cancelada quedó fuera del WHERE), el hueco sigue libre.
    db = AsyncMock(spec=AsyncSession)
    mock_execute_sequence(db, [make_schedule(9, 0, 9, 30)], [])

    service = AvailabilityService(db)
    slots = await service.get_available_slots("user-1", MONDAY, duration_minutes=30)

    assert slots == [datetime(2026, 7, 6, 9, 0)]

@pytest.mark.asyncio
async def test_has_schedule_for_date_returns_true_when_schedule_exists():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value="block-1"))

    service = AvailabilityService(db)
    result = await service.has_schedule_for_date("user-1", MONDAY)

    assert result is True


@pytest.mark.asyncio
async def test_has_schedule_for_date_returns_false_when_no_schedule():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    service = AvailabilityService(db)
    result = await service.has_schedule_for_date("user-1", MONDAY)

    assert result is False