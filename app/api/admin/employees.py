from datetime import date as date_type, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select

from app.core.auth import get_current_user
from app.core.database import get_db_session
from app.models.employee_schedule import EmployeeSchedule
from app.models.user import RoleEnum, User

router = APIRouter()


class ScheduleBlockCreateRequest(BaseModel):
    date: date_type
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
    date: date_type
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
    # Ya no se fija un horario recurrente al crear el empleado — el
    # horario se planifica semana a semana desde el Gantt del panel.


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
    # Crea un empleado nuevo, sin horario todavía — se planifica después
    # semana a semana desde el Gantt. Hasta que tenga algún bloque
    # planificado, AvailabilityService no le ofrecerá huecos por WhatsApp.
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        employee = User(
            business_id=business_id,
            whatsapp_number=body.whatsapp_number,
            name=body.name,
            role=RoleEnum.employee,
        )
        db.add(employee)
        await db.commit()
        await db.refresh(employee)
        return {
            "id": str(employee.id),
            "name": employee.name,
            "whatsapp_number": employee.whatsapp_number,
        }


@router.get("/api/admin/employees/schedule")
async def get_weekly_schedule(week_start: date_type, current_user: User = Depends(get_current_user)):
    # Horario de todos los empleados para la semana que empieza en
    # week_start (normalmente un lunes — el frontend siempre manda el
    # lunes de la semana que se está viendo). Cada bloque lleva su propio
    # id, así que un empleado puede tener varios el mismo día (turno
    # partido).
    week_end = week_start + timedelta(days=6)
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
                    EmployeeSchedule.user_id.in_([e.id for e in employees]),
                    EmployeeSchedule.date >= week_start,
                    EmployeeSchedule.date <= week_end,
                )
            )
        ).scalars().all()

        schedule_by_employee: dict[str, list] = {str(e.id): [] for e in employees}
        for slot in schedules:
            schedule_by_employee[str(slot.user_id)].append(
                {
                    "id": str(slot.id),
                    "date": slot.date.isoformat(),
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
            date=body.date,
            start_time=body.start_time,
            end_time=body.end_time,
        )
        db.add(block)
        await db.commit()
        await db.refresh(block)
        return {
            "id": str(block.id),
            "date": block.date.isoformat(),
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

        block.date = body.date
        block.start_time = body.start_time
        block.end_time = body.end_time
        await db.commit()
        return {
            "id": str(block.id),
            "date": block.date.isoformat(),
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