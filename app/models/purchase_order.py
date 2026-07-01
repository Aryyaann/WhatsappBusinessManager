import enum
import uuid

from sqlalchemy import Enum, String, Numeric, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class OrderStatusEnum(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    confirmed = "confirmed"
    processed = "processed"


class OrderSourceEnum(str, enum.Enum):
    whatsapp_photo = "whatsapp_photo"
    manual = "manual"
    email = "email"


class PurchaseOrder(BaseModel):
    __tablename__ = "purchase_orders"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[OrderStatusEnum] = mapped_column(
        Enum(OrderStatusEnum),
        default=OrderStatusEnum.draft,
        nullable=False,
    )
    source: Mapped[OrderSourceEnum] = mapped_column(
        Enum(OrderSourceEnum),
        default=OrderSourceEnum.whatsapp_photo,
        nullable=False,
    )
    raw_image_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    textract_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_extraction: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    order_date: Mapped[str | None] = mapped_column(Date, nullable=True)

    business: Mapped["Business"] = relationship("Business")
    supplier: Mapped["Supplier"] = relationship("Supplier")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship("PurchaseOrderLine", back_populates="order")


class PurchaseOrderLine(BaseModel):
    __tablename__ = "purchase_order_lines"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    expiry_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    lot_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)

    order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="lines")
    product: Mapped["Product"] = relationship("Product")