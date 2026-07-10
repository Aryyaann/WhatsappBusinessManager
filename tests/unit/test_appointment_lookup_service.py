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

@pytest.mark.asyncio
async def test_list_employees_returns_all_employees_of_business():
    ana = MagicMock()
    ana.name = "Ana"
    pedro = MagicMock()
    pedro.name = "Pedro"
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[ana, pedro]))))

    service = AppointmentLookupService(db)
    result = await service.list_employees("business-1")

    assert result == [ana, pedro]


@pytest.mark.asyncio
async def test_list_employees_returns_empty_list_when_none():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))

    service = AppointmentLookupService(db)
    result = await service.list_employees("business-1")

    assert result == []