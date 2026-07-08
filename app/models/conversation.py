import enum
import uuid

from sqlalchemy import Enum, String, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime

from app.models.base import BaseModel


class ParticipantTypeEnum(str, enum.Enum):
    owner = "owner"
    employee = "employee"
    customer = "customer"


class ContentTypeEnum(str, enum.Enum):
    text = "text"
    image = "image"
    audio = "audio"


class DirectionEnum(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class Conversation(BaseModel):
    __tablename__ = "conversations"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    participant_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    participant_type: Mapped[ParticipantTypeEnum] = mapped_column(
        Enum(ParticipantTypeEnum),
        nullable=False,
    )
    last_message_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    business: Mapped["Business"] = relationship("Business")
    messages: Mapped[list["ConversationMessage"]] = relationship("ConversationMessage", back_populates="conversation")


class ConversationMessage(BaseModel):
    __tablename__ = "conversation_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction: Mapped[DirectionEnum] = mapped_column(Enum(DirectionEnum), nullable=False)
    content_type: Mapped[ContentTypeEnum] = mapped_column(Enum(ContentTypeEnum), nullable=False)
    content_text: Mapped[str | None] = mapped_column(String, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    llm_intent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_tool_called: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")