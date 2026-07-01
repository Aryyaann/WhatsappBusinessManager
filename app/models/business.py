import enum

from sqlalchemy import Enum, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class PlanEnum(str, enum.Enum):
    starter = "starter"
    professional = "professional"
    enterprise = "enterprise"


class Business(BaseModel):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    whatsapp_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    plan: Mapped[PlanEnum] = mapped_column(Enum(PlanEnum), default=PlanEnum.starter, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Madrid", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    users: Mapped[list["User"]] = relationship("User", back_populates="business")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="business")