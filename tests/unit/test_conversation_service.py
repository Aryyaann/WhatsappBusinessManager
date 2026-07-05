from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.conversations.service import ConversationService
from app.models.conversation import Conversation


@pytest.mark.asyncio
async def test_get_or_create_returns_existing_conversation():
    existing = MagicMock(spec=Conversation)
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=existing))

    service = ConversationService(db)
    result = await service.get_or_create_conversation(
        business_id="business-1",
        participant_phone="+34600000001",
        participant_type="owner",
    )

    assert result is existing
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_creates_new_conversation_when_none_exists():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    service = ConversationService(db)
    result = await service.get_or_create_conversation(
        business_id="business-1",
        participant_phone="+34600000001",
        participant_type="owner",
    )

    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    added_conversation = db.add.call_args[0][0]
    assert added_conversation.business_id == "business-1"
    assert added_conversation.participant_phone == "+34600000001"
    assert added_conversation.message_count == 0
    # No debe fallar por pasar started_at: Conversation no tiene esa columna,
    # solo hereda created_at/updated_at de BaseModel.
    assert not hasattr(added_conversation, "started_at") or added_conversation.started_at is None


@pytest.mark.asyncio
async def test_log_message_increments_conversation_counters():
    mock_conversation = MagicMock()
    mock_conversation.message_count = 3
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one=MagicMock(return_value=mock_conversation))

    service = ConversationService(db)
    message = await service.log_message(
        conversation_id="conv-1",
        direction="inbound",
        content_type="text",
        content_text="¿qué me queda de tinte rubio?",
    )

    assert message.content_text == "¿qué me queda de tinte rubio?"
    db.add.assert_called_once_with(message)
    assert mock_conversation.message_count == 4
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_log_message_accepts_optional_llm_metadata():
    mock_conversation = MagicMock()
    mock_conversation.message_count = 0
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one=MagicMock(return_value=mock_conversation))

    service = ConversationService(db)
    message = await service.log_message(
        conversation_id="conv-1",
        direction="outbound",
        content_type="text",
        content_text="Te quedan 12 unidades.",
        llm_intent="consultar_stock",
        llm_tool_called="consultar_stock",
        llm_tokens_input=150,
        llm_tokens_output=40,
        llm_cost_usd=0.002,
    )

    assert message.llm_intent == "consultar_stock"
    assert message.llm_tool_called == "consultar_stock"
    assert message.llm_tokens_input == 150
    assert message.llm_tokens_output == 40
    assert message.llm_cost_usd == 0.002