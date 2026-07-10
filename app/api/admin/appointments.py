from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db_session
from app.domain.appointments.availability_service import AvailabilityService
from app.domain.appointments.booking_service import BookingService, SlotNoLongerAvailableError
from app.infrastructure.messaging.twilio_client import twilio_client
from app.models.appointment import Appointment, AppointmentStatusEnum
from app.models.service import Service
from app.models.user import RoleEnum, User

router = APIRouter()


class AppointmentStatusUpdateRequest(BaseModel):
    status: AppointmentStatusEnum


class AppointmentConfirmRequest(BaseModel):
    employee_id: Optional[str] = None


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


@router.patch("/api/admin/appointments/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: str,
    body: AppointmentConfirmRequest,
    current_user: User = Depends(get_current_user),
):
    # Confirma una cita (normalmente una pendiente creada por Pieza B, sin
    # horario planificado en su momento) y opcionalmente la reasigna a otro
    # empleado. Manda un WhatsApp de confirmación al cliente — si falla el
    # envío, la confirmación en sí NO se deshace (mejor una cita confirmada
    # sin aviso que perder la confirmación por un problema de Twilio).
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

        target_employee_id = body.employee_id or (
            str(appointment.assigned_to) if appointment.assigned_to else None
        )
        if target_employee_id is None:
            raise HTTPException(
                status_code=400, detail="Hay que asignar un empleado antes de confirmar."
            )

        employee = (
            await db.execute(
                select(User).where(
                    User.id == target_employee_id,
                    User.business_id == business_id,
                    User.role == RoleEnum.employee,
                )
            )
        ).scalar_one_or_none()
        if employee is None:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        # Solo revalidamos disponibilidad si estamos asignando a alguien
        # nuevo (reasignación, o primera asignación de una cita que llegó
        # sin empleado). Si se confirma con el MISMO empleado que ya tenía,
        # no revalidamos — la propia cita pendiente ya "ocupa" ese hueco en
        # el cálculo de disponibilidad, así que se marcaría a sí misma como
        # conflicto; además, si el dueño confirma a mano, se fía de su
        # propio criterio.
        is_new_assignment = body.employee_id is not None and (
            appointment.assigned_to is None or str(appointment.assigned_to) != body.employee_id
        )
        if is_new_assignment:
            duration_minutes = int((appointment.end_at - appointment.start_at).total_seconds() // 60)
            availability_service = AvailabilityService(db)
            slots = await availability_service.get_available_slots(
                target_employee_id, appointment.start_at.date(), duration_minutes
            )
            if appointment.start_at.replace(tzinfo=None) not in slots:
                raise HTTPException(
                    status_code=409,
                    detail=f"{employee.name} no tiene ese hueco libre — elige otra hora o empleado.",
                )

        appointment.assigned_to = target_employee_id
        appointment.status = AppointmentStatusEnum.confirmed
        await db.commit()

        service = None
        if appointment.service_id:
            service = (
                await db.execute(select(Service).where(Service.id == appointment.service_id))
            ).scalar_one_or_none()

        whatsapp_sent = False
        whatsapp_error = None
        if appointment.customer_phone:
            try:
                service_label = service.name if service else "tu cita"
                twilio_client.send_text(
                    appointment.customer_phone,
                    (
                        f"¡Hola! Tu cita de {service_label} el "
                        f"{appointment.start_at.strftime('%d/%m/%Y')} a las "
                        f"{appointment.start_at.strftime('%H:%M')} con {employee.name} ha sido "
                        f"confirmada. ¡Te esperamos!"
                    ),
                )
                whatsapp_sent = True
            except Exception as exc:  # noqa: BLE001 — best-effort, no debe tumbar la confirmación
                whatsapp_error = str(exc)

        return {
            "id": str(appointment.id),
            "status": appointment.status.value,
            "employee_name": employee.name,
            "whatsapp_sent": whatsapp_sent,
            "whatsapp_error": whatsapp_error,
        }


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