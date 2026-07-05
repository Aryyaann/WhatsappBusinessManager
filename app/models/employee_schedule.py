import uuid
from datetime import time

from sqlalchemy import Integer, Time, ForeignKey
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
    # Convención de Python (date.weekday()): 0 = lunes ... 6 = domingo.
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # Un mismo empleado puede tener varias filas el mismo día (ej. turno
    # partido: 9:00-14:00 y 16:00-20:00), por eso no hay unique en día.
    user: Mapped["User"] = relationship("User")