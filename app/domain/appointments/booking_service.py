from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.appointment import Appointment, AppointmentStatusEnum
from app.domain.appointments.availability_service import AvailabilityService


class SlotNoLongerAvailableError(Exception):
    # Se lanza cuando, entre que se mostraron los huecos disponibles y el
    # cliente confirma, ese hueco ya fue ocupado por otra reserva.
    pass


class BookingService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.availability_service = AvailabilityService(db)

    async def book_appointment(
        self,
        business_id: str,
        user_id: str,
        customer_phone: str,
        start_at: datetime,
        duration_minutes: int,
        customer_name: Optional[str] = None,
        notes: Optional[str] = None,
        service_id: Optional[str] = None,
    ) -> Appointment:
        # Revalidamos que el hueco sigue libre justo antes de reservar —
        # entre que el cliente vio los huecos disponibles y confirma,
        # alguien más (u otra conversación) podría haberlo cogido ya.
        available_slots = await self.availability_service.get_available_slots(
            user_id=user_id,
            target_date=start_at.date(),
            duration_minutes=duration_minutes,
        )
        if start_at not in available_slots:
            raise SlotNoLongerAvailableError(
                f"El hueco de las {start_at.strftime('%H:%M')} ya no está disponible."
            )

        appointment = Appointment(
            business_id=business_id,
            assigned_to=user_id,
            service_id=service_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
            start_at=start_at,
            end_at=start_at + timedelta(minutes=duration_minutes),
            status=AppointmentStatusEnum.pending,
            notes=notes,
        )
        self.db.add(appointment)
        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment

    async def cancel_appointment(self, appointment_id: str) -> Optional[Appointment]:
        result = await self.db.execute(
            select(Appointment).where(Appointment.id == appointment_id)
        )
        appointment = result.scalar_one_or_none()
        if appointment is None:
            return None

        appointment.status = AppointmentStatusEnum.cancelled
        await self.db.commit()
        return appointment