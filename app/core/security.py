from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.messaging.twilio_client import twilio_client


async def set_rls_business_id(db: AsyncSession, business_id: str) -> None:
    # Inyecta el business_id en la sesión de PostgreSQL.
    # Las políticas RLS de PostgreSQL usan este valor para filtrar
    # automáticamente todas las queries — un tenant nunca ve datos de otro.
    await db.execute(
        f"SET LOCAL app.current_business_id = '{business_id}'"
    )


def validate_twilio_signature(url: str, params: dict, signature: str) -> bool:
    # Wrapper centralizado para la validación de firma Twilio.
    # Todo el código que necesite validar webhooks importa de aquí,
    # no del twilio_client directamente.
    return twilio_client.validate_webhook(url, params, signature)