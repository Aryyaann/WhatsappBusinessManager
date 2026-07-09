from datetime import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select

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


class ScheduleBlockCreateRequest(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, end_time: time, info):
        start_time = info.data.get("start_time")
        if start_time is not None and end_time <= start_time:
            raise ValueError("end_time debe ser posterior a start_time")
        return end_time


class ScheduleBlockUpdateRequest(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
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
    # Lista para poblar desplegables (ej. crear cita) y la ficha de detalle
    # del empleado en el panel. Solo role=employee — el dueño no se agenda
    # a sí mismo.
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        stmt = (
            select(User)
            .where(User.business_id == business_id, User.role == RoleEnum.employee)
            .order_by(User.name)
        )
        employees = (await db.execute(stmt)).scalars().all()
        return [{"id": str(e.id), "name": e.name, "whatsapp_number": e.whatsapp_number} for e in employees]


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


@router.get("/api/admin/employees/schedule")
async def get_weekly_schedule(current_user: User = Depends(get_current_user)):
    # Horario semanal completo de todos los empleados, para pintar el
    # Gantt. Cada bloque lleva su propio id, así que un empleado puede
    # tener varios bloques el mismo día (turno partido).
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        employees = (
            await db.execute(
                select(User).where(User.business_id == business_id, User.role == RoleEnum.employee).order_by(User.name)
            )
        ).scalars().all()

        schedules = (
            await db.execute(
                select(EmployeeSchedule).where(
                    EmployeeSchedule.user_id.in_([e.id for e in employees])
                )
            )
        ).scalars().all()

        schedule_by_employee: dict[str, list] = {str(e.id): [] for e in employees}
        for slot in schedules:
            schedule_by_employee[str(slot.user_id)].append(
                {
                    "id": str(slot.id),
                    "day_of_week": slot.day_of_week,
                    "start_time": slot.start_time.isoformat(),
                    "end_time": slot.end_time.isoformat(),
                }
            )

        return [
            {"employee_id": str(e.id), "employee_name": e.name, "schedule": schedule_by_employee[str(e.id)]}
            for e in employees
        ]


@router.post("/api/admin/employees/{employee_id}/schedule")
async def create_schedule_block(
    employee_id: str,
    body: ScheduleBlockCreateRequest,
    current_user: User = Depends(get_current_user),
):
    # Crea un bloque de horario nuevo (arrastrar desde el menú de empleados
    # al Gantt llama aquí). No reemplaza nada — un empleado puede tener
    # varios bloques el mismo día para turnos partidos.
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        employee = (
            await db.execute(
                select(User).where(
                    User.id == employee_id, User.business_id == business_id, User.role == RoleEnum.employee
                )
            )
        ).scalar_one_or_none()
        if employee is None:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        block = EmployeeSchedule(
            user_id=employee_id,
            day_of_week=body.day_of_week,
            start_time=body.start_time,
            end_time=body.end_time,
        )
        db.add(block)
        await db.commit()
        await db.refresh(block)
        return {
            "id": str(block.id),
            "day_of_week": block.day_of_week,
            "start_time": block.start_time.isoformat(),
            "end_time": block.end_time.isoformat(),
        }


@router.patch("/api/admin/employees/{employee_id}/schedule/{block_id}")
async def update_schedule_block(
    employee_id: str,
    block_id: str,
    body: ScheduleBlockUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    # Mover un bloque ya colocado (arrastrarlo a otro día/hora) llama aquí.
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        employee = (
            await db.execute(
                select(User).where(
                    User.id == employee_id, User.business_id == business_id, User.role == RoleEnum.employee
                )
            )
        ).scalar_one_or_none()
        if employee is None:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        block = (
            await db.execute(
                select(EmployeeSchedule).where(
                    EmployeeSchedule.id == block_id, EmployeeSchedule.user_id == employee_id
                )
            )
        ).scalar_one_or_none()
        if block is None:
            raise HTTPException(status_code=404, detail="Bloque de horario no encontrado")

        block.day_of_week = body.day_of_week
        block.start_time = body.start_time
        block.end_time = body.end_time
        await db.commit()
        return {
            "id": str(block.id),
            "day_of_week": block.day_of_week,
            "start_time": block.start_time.isoformat(),
            "end_time": block.end_time.isoformat(),
        }


@router.delete("/api/admin/employees/{employee_id}/schedule/{block_id}")
async def delete_schedule_block(
    employee_id: str,
    block_id: str,
    current_user: User = Depends(get_current_user),
):
    # Quita un bloque colocado (el botón X en el Gantt). El empleado sigue
    # disponible en el menú de abajo para volver a arrastrarlo.
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        employee = (
            await db.execute(
                select(User).where(
                    User.id == employee_id, User.business_id == business_id, User.role == RoleEnum.employee
                )
            )
        ).scalar_one_or_none()
        if employee is None:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        result = await db.execute(
            delete(EmployeeSchedule).where(
                EmployeeSchedule.id == block_id, EmployeeSchedule.user_id == employee_id
            )
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bloque de horario no encontrado")
        await db.commit()
        return {"status": "ok"}