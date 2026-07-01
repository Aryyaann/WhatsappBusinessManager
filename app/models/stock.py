import enum
import uuid

from sqlalchemy import Enum, Numeric, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class MovementTypeEnum(str, enum.Enum):
    purchase = "purchase"
    sale = "sale"
    adjustment = "adjustment"
    waste = "waste"
    return_ = "return"


class StockLevel(BaseModel):
    __tablename__ = "stock_levels"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), default=0, nullable=False)

    product: Mapped["Product"] = relationship("Product")
    business: Mapped["Business"] = relationship("Business")


class StockMovement(BaseModel):
    __tablename__ = "stock_movements"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    movement_type: Mapped[MovementTypeEnum] = mapped_column(
        Enum(MovementTypeEnum),
        nullable=False,
    )
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    product: Mapped["Product"] = relationship("Product")
    business: Mapped["Business"] = relationship("Business")
    user: Mapped["User"] = relationship("User")