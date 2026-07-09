import uuid
from datetime import date as date_type, time

from sqlalchemy import Date, Time, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class EmployeeSchedule(BaseModel):
    __tablename__ = "employee_schedules"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Turno de una fecha CONCRETA, no recurrente — el horario de un
    # empleado cambia de una semana a otra, así que cada bloque pertenece
    # a un día real del calendario (se planifica semana a semana desde el
    # panel), no a "todos los lunes" de forma indefinida.
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # Un mismo empleado puede tener varias filas el mismo día (ej. turno
    # partido: 9:00-14:00 y 16:00-20:00), por eso no hay unique en fecha.
    user: Mapped["User"] = relationship("User")