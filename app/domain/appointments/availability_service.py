from datetime import date as date_type, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.employee_schedule import EmployeeSchedule
from app.models.appointment import Appointment, AppointmentStatusEnum

# Estados de cita que realmente ocupan hueco en la agenda. Una cita
# cancelada, completada o "no_show" no debe seguir bloqueando el horario.
BLOCKING_STATUSES = [AppointmentStatusEnum.pending, AppointmentStatusEnum.confirmed]


class AvailabilityService:
    # Servicio de solo lectura: calcula los huecos libres de un empleado en
    # un día concreto, para un servicio de una duración dada. Cruza el
    # horario semanal del empleado (EmployeeSchedule) con sus citas ya
    # reservadas ese día.

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_available_slots(
        self,
        user_id: str,
        target_date: date_type,
        duration_minutes: int,
    ) -> list[datetime]:
        # 1. Horario del empleado para ese día de la semana (puede tener
        # varios tramos, ej. turno partido).
        day_of_week = target_date.weekday()
        schedule_result = await self.db.execute(
            select(EmployeeSchedule).where(
                EmployeeSchedule.user_id == user_id,
                EmployeeSchedule.day_of_week == day_of_week,
            )
        )
        schedules = schedule_result.scalars().all()
        if not schedules:
            # Sin horario ese día (ej. es su día libre) — ni merece la pena
            # consultar citas.
            return []

        # 2. Citas ya existentes ese día que ocupan hueco.
        day_start = datetime.combine(target_date, time.min)
        day_end = datetime.combine(target_date, time.max)
        appt_result = await self.db.execute(
            select(Appointment).where(
                Appointment.assigned_to == user_id,
                Appointment.start_at >= day_start,
                Appointment.start_at <= day_end,
                Appointment.status.in_(BLOCKING_STATUSES),
            )
        )
        busy_intervals = [(a.start_at, a.end_at) for a in appt_result.scalars().all()]

        # 3. Para cada tramo de horario, restar las citas ocupadas y trocear
        # el resto en huecos exactos del tamaño del servicio pedido.
        slots = []
        service_duration = timedelta(minutes=duration_minutes)
        for schedule in schedules:
            interval_start = datetime.combine(target_date, schedule.start_time)
            interval_end = datetime.combine(target_date, schedule.end_time)
            free_intervals = self._subtract_busy(interval_start, interval_end, busy_intervals)
            for free_start, free_end in free_intervals:
                slots.extend(self._slice_into_slots(free_start, free_end, service_duration))

        return sorted(slots)

    @staticmethod
    def _subtract_busy(
        interval_start: datetime,
        interval_end: datetime,
        busy_intervals: list[tuple[datetime, datetime]],
    ) -> list[tuple[datetime, datetime]]:
        # Recorta [interval_start, interval_end) quitando cualquier solape
        # con las citas ya ocupadas, devolviendo los huecos libres restantes.
        free = [(interval_start, interval_end)]
        for busy_start, busy_end in sorted(busy_intervals):
            new_free = []
            for free_start, free_end in free:
                if busy_end <= free_start or busy_start >= free_end:
                    # Sin solape con este tramo libre — se queda igual.
                    new_free.append((free_start, free_end))
                    continue
                if busy_start > free_start:
                    new_free.append((free_start, busy_start))
                if busy_end < free_end:
                    new_free.append((busy_end, free_end))
            free = new_free
        return free

    @staticmethod
    def _slice_into_slots(
        free_start: datetime,
        free_end: datetime,
        duration: timedelta,
    ) -> list[datetime]:
        # Genera horas de inicio válidas cada `duration` dentro del hueco
        # libre, mientras quepa el servicio completo antes de que acabe.
        slots = []
        current = free_start
        while current + duration <= free_end:
            slots.append(current)
            current += duration
        return slots