import uuid

from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class Supplier(BaseModel):
    __tablename__ = "suppliers"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_format_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    average_delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    business: Mapped["Business"] = relationship("Business")