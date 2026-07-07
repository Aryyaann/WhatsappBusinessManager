from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.database import get_db_session
from app.models.appointment import Appointment, AppointmentStatusEnum
from app.models.user import User
from app.models.service import Service

router = APIRouter()


class AppointmentStatusUpdateRequest(BaseModel):
    status: AppointmentStatusEnum


@router.get("/api/admin/appointments")
async def list_appointments(business_id: str):
    # NOTA: sin autenticación todavía, igual que /api/admin/products — mismo
    # placeholder deliberado hasta que montemos login/sesión (Fase 5).
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
async def update_appointment_status(appointment_id: str, body: AppointmentStatusUpdateRequest, business_id: str):
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