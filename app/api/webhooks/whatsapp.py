from fastapi import APIRouter, Form, Header, HTTPException, Request
from typing import Optional
from sqlalchemy import select

from app.infrastructure.messaging.twilio_client import twilio_client
from app.infrastructure.storage.sqs_client import sqs_client
from app.core.database import get_db_session
from app.models.business import Business

router = APIRouter()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(default=""),
    NumMedia: int = Form(default=0),
    MediaUrl0: Optional[str] = Form(default=None),
    MediaContentType0: Optional[str] = Form(default=None),
    x_twilio_signature: str = Header(...),
):
    # Paso 1 — validar firma Twilio
    url = str(request.url)
    params = dict(await request.form())
    if not twilio_client.validate_webhook(url, params, x_twilio_signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # Paso 2 — buscar el negocio por número de teléfono del remitente.
    # El número viene con prefijo "whatsapp:+34..." — lo limpiamos.
    sender_phone = From.replace("whatsapp:", "")
    business_id = None

    async with get_db_session() as db:
        result = await db.execute(
            select(Business).where(Business.whatsapp_number == sender_phone)
        )
        business = result.scalar_one_or_none()
        if business:
            business_id = str(business.id)

    # Paso 3 — si hay imagen, encolar job en SQS con business_id
    if NumMedia > 0 and MediaUrl0:
        payload = {
            "sender_phone": sender_phone,
            "media_url": MediaUrl0,
            "content_type": MediaContentType0,
            "body": Body,
            "business_id": business_id,
        }
        message_id = sqs_client.send_message(payload)
        return {"status": "queued", "message_id": message_id}

    return {"status": "received", "body": Body}