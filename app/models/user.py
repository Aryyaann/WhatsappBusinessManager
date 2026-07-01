import enum
import uuid

from sqlalchemy import Enum, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class RoleEnum(str, enum.Enum):
    owner = "owner"
    employee = "employee"


class User(BaseModel):
    __tablename__ = "users"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    whatsapp_number: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False)
    cognito_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    business: Mapped["Business"] = relationship("Business", back_populates="users")