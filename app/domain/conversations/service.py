from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.conversation import Conversation, ConversationMessage


class ConversationService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_conversation(
        self,
        business_id: str,
        participant_phone: str,
        participant_type: str,
    ) -> Conversation:
        # Busca una conversación activa para este número en este negocio.
        # Si no existe, la crea. "Activa" significa que hubo un mensaje
        # en las últimas 24h — si no, se abre una conversación nueva.
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.business_id == business_id,
                Conversation.participant_phone == participant_phone,
            ).order_by(Conversation.last_message_at.desc())
        )
        conversation = result.scalar_one_or_none()

        if conversation is None:
            conversation = Conversation(
                business_id=business_id,
                participant_phone=participant_phone,
                participant_type=participant_type,
                last_message_at=datetime.now(timezone.utc),
                message_count=0,
            )
            self.db.add(conversation)
            await self.db.flush()

        return conversation

    async def log_message(
        self,
        conversation_id: str,
        direction: str,
        content_type: str,
        content_text: str = None,
        s3_key: str = None,
        llm_intent: str = None,
        llm_tool_called: str = None,
        llm_tokens_input: int = None,
        llm_tokens_output: int = None,
        llm_cost_usd: float = None,
    ) -> ConversationMessage:
        # Loguea un mensaje en conversation_messages con todos sus metadatos.
        # Los campos de IA son opcionales — no todos los mensajes pasan por LLM.
        message = ConversationMessage(
            conversation_id=conversation_id,
            direction=direction,
            content_type=content_type,
            content_text=content_text,
            s3_key=s3_key,
            llm_intent=llm_intent,
            llm_tool_called=llm_tool_called,
            llm_tokens_input=llm_tokens_input,
            llm_tokens_output=llm_tokens_output,
            llm_cost_usd=llm_cost_usd,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(message)

        # Actualiza el contador y timestamp de la conversación padre.
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one()
        conversation.message_count += 1
        conversation.last_message_at = datetime.now(timezone.utc)

        await self.db.flush()
        return message