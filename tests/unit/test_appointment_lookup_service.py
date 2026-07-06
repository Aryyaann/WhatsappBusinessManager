from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.appointments.lookup_service import AppointmentLookupService


@pytest.mark.asyncio
async def test_find_employee_by_name_returns_match():
    mock_user = MagicMock()
    mock_user.name = "Ana"
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_user))))

    service = AppointmentLookupService(db)
    result = await service.find_employee_by_name("business-1", "ana")

    assert result is mock_user


@pytest.mark.asyncio
async def test_find_employee_by_name_returns_none_when_no_match():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None))))

    service = AppointmentLookupService(db)
    result = await service.find_employee_by_name("business-1", "nadie")

    assert result is None


@pytest.mark.asyncio
async def test_find_service_by_name_returns_match():
    mock_service = MagicMock()
    mock_service.name = "Corte de pelo"
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_service))))

    service = AppointmentLookupService(db)
    result = await service.find_service_by_name("business-1", "corte")

    assert result is mock_service


@pytest.mark.asyncio
async def test_find_service_by_name_returns_none_when_no_match():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None))))

    service = AppointmentLookupService(db)
    result = await service.find_service_by_name("business-1", "manicura egipcia")

    assert result is None