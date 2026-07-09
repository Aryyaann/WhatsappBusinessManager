from datetime import time
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db_session
from app.models.employee_schedule import EmployeeSchedule
from app.models.user import RoleEnum, User

router = APIRouter()


class ScheduleSlotInput(BaseModel):
    day_of_week: int = Field(ge=0, le=6, description="0 = lunes ... 6 = domingo")
    start_time: time
    end_time: time

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, end_time: time, info):
        start_time = info.data.get("start_time")
        if start_time is not None and end_time <= start_time:
            raise ValueError("end_time debe ser posterior a start_time")
        return end_time


class EmployeeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    whatsapp_number: str = Field(min_length=1, max_length=20)
    schedule: List[ScheduleSlotInput] = Field(default_factory=list)


@router.get("/api/admin/employees")
async def list_employees(current_user: User = Depends(get_current_user)):
    # Lista simple para poblar desplegables (ej. crear cita). Solo
    # role=employee — el dueño no se agenda a sí mismo.
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        stmt = (
            select(User)
            .where(User.business_id == business_id, User.role == RoleEnum.employee)
            .order_by(User.name)
        )
        employees = (await db.execute(stmt)).scalars().all()
        return [{"id": str(e.id), "name": e.name} for e in employees]


@router.post("/api/admin/employees")
async def create_employee(body: EmployeeCreateRequest, current_user: User = Depends(get_current_user)):
    # Crea un empleado nuevo con su horario semanal. Sin al menos un tramo
    # de horario, AvailabilityService nunca ofrecerá huecos para este
    # empleado (ver test_no_schedule_returns_empty), así que dejamos crear
    # el empleado sin horario si el dueño lo prefiere añadir luego, pero
    # avisamos de que no podrá recibir citas hasta entonces.
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        employee = User(
            business_id=business_id,
            whatsapp_number=body.whatsapp_number,
            name=body.name,
            role=RoleEnum.employee,
        )
        db.add(employee)
        await db.flush()  # para obtener employee.id antes de crear el horario

        for slot in body.schedule:
            db.add(
                EmployeeSchedule(
                    user_id=employee.id,
                    day_of_week=slot.day_of_week,
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                )
            )

        await db.commit()
        return {
            "id": str(employee.id),
            "name": employee.name,
            "whatsapp_number": employee.whatsapp_number,
            "schedule_slots_created": len(body.schedule),
        }