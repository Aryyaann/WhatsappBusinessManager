import enum
import uuid

from sqlalchemy import Enum, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime

from app.models.base import BaseModel


class AppointmentStatusEnum(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"


class Appointment(BaseModel):
    __tablename__ = "appointments"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Servicio reservado (ej. "Corte de pelo"). Nullable porque las citas
    # creadas antes de este campo no lo tienen, y porque un servicio podría
    # borrarse en el futuro sin que queramos perder el historial de la cita.
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatusEnum] = mapped_column(
        Enum(AppointmentStatusEnum),
        default=AppointmentStatusEnum.pending,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_sent_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped["Business"] = relationship("Business")
    assigned_user: Mapped["User"] = relationship("User")
    service: Mapped["Service"] = relationship("Service")