from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db_session
from app.domain.appointments.booking_service import BookingService, SlotNoLongerAvailableError
from app.models.appointment import Appointment, AppointmentStatusEnum
from app.models.service import Service
from app.models.user import RoleEnum, User

router = APIRouter()


class AppointmentStatusUpdateRequest(BaseModel):
    status: AppointmentStatusEnum


class AppointmentCreateRequest(BaseModel):
    employee_id: str
    service_id: str
    start_at: datetime
    customer_name: Optional[str] = Field(default=None, max_length=255)
    customer_phone: str = Field(min_length=1, max_length=20)
    notes: Optional[str] = None


@router.get("/api/admin/appointments")
async def list_appointments(current_user: User = Depends(get_current_user)):
    # business_id ya NO llega como query param del cliente — se deriva del
    # usuario autenticado, igual que en admin/products.py.
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        stmt = (
            select(Appointment, User.name, Service.name)
            .outerjoin(User, User.id == Appointment.assigned_to)
            .outerjoin(Service, Service.id == Appointment.service_id)
            .where(Appointment.business_id == business_id)
            .order_by(Appointment.start_at)
        )
        rows = (await db.execute(stmt)).all()

        return [
            {
                "id": str(row.Appointment.id),
                "customer_name": row.Appointment.customer_name,
                "customer_phone": row.Appointment.customer_phone,
                "employee_name": row[1],
                "service_name": row[2],
                "start_at": row.Appointment.start_at.isoformat(),
                "end_at": row.Appointment.end_at.isoformat(),
                "status": row.Appointment.status.value,
                "notes": row.Appointment.notes,
            }
            for row in rows
        ]


@router.patch("/api/admin/appointments/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: str,
    body: AppointmentStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        appointment = (
            await db.execute(
                select(Appointment).where(
                    Appointment.id == appointment_id, Appointment.business_id == business_id
                )
            )
        ).scalar_one_or_none()
        if appointment is None:
            raise HTTPException(status_code=404, detail="Cita no encontrada")

        appointment.status = body.status
        await db.commit()
        return {"status": "ok", "appointment_id": appointment_id, "new_status": body.status.value}


@router.get("/api/admin/employees")
async def list_employees(current_user: User = Depends(get_current_user)):
    # Lista simple para poblar el desplegable "empleado" al crear una cita
    # a mano. Solo role=employee — el dueño no se agenda a sí mismo.
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        stmt = (
            select(User)
            .where(User.business_id == business_id, User.role == RoleEnum.employee)
            .order_by(User.name)
        )
        employees = (await db.execute(stmt)).scalars().all()
        return [{"id": str(e.id), "name": e.name} for e in employees]


@router.get("/api/admin/services")
async def list_services(current_user: User = Depends(get_current_user)):
    # Lista simple para poblar el desplegable "servicio" al crear una cita
    # a mano (necesitamos duration_minutes para calcular el hueco).
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        stmt = (
            select(Service)
            .where(Service.business_id == business_id, Service.is_active == True)
            .order_by(Service.name)
        )
        services = (await db.execute(stmt)).scalars().all()
        return [
            {
                "id": str(s.id),
                "name": s.name,
                "duration_minutes": s.duration_minutes,
                "price": float(s.price) if s.price is not None else None,
            }
            for s in services
        ]


@router.post("/api/admin/appointments")
async def create_appointment(
    body: AppointmentCreateRequest,
    current_user: User = Depends(get_current_user),
):
    # Crea una cita manual desde el panel, reutilizando BookingService — el
    # mismo servicio que usa el flujo de WhatsApp, así que las reglas de
    # disponibilidad (sin solapes, dentro del horario del empleado) son
    # exactamente las mismas en ambos canales.
    business_id = str(current_user.business_id)
    async with get_db_session() as db:
        service = (
            await db.execute(
                select(Service).where(Service.id == body.service_id, Service.business_id == business_id)
            )
        ).scalar_one_or_none()
        if service is None:
            raise HTTPException(status_code=404, detail="Servicio no encontrado")

        employee = (
            await db.execute(
                select(User).where(
                    User.id == body.employee_id,
                    User.business_id == business_id,
                    User.role == RoleEnum.employee,
                )
            )
        ).scalar_one_or_none()
        if employee is None:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        booking_service = BookingService(db)
        try:
            appointment = await booking_service.book_appointment(
                business_id=business_id,
                user_id=body.employee_id,
                customer_phone=body.customer_phone,
                start_at=body.start_at,
                duration_minutes=service.duration_minutes,
                customer_name=body.customer_name,
                notes=body.notes,
                service_id=body.service_id,
            )
        except SlotNoLongerAvailableError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        return {
            "id": str(appointment.id),
            "employee_name": employee.name,
            "service_name": service.name,
            "start_at": appointment.start_at.isoformat(),
            "end_at": appointment.end_at.isoformat(),
            "status": appointment.status.value,
        }