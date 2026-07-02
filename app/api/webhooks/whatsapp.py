from fastapi import APIRouter, Form, Header, HTTPException, Request
from typing import Optional

from app.infrastructure.messaging.twilio_client import twilio_client
from app.infrastructure.storage.sqs_client import sqs_client

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
    # Paso 1 — validar que el request viene realmente de Twilio.
    # Si la firma no es válida, rechazamos con 403 inmediatamente.
    url = str(request.url)
    params = dict(await request.form())
    if not twilio_client.validate_webhook(url, params, x_twilio_signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # Paso 2 — si el mensaje contiene una imagen, encolamos el job en SQS.
    # No procesamos aquí — respondemos en <500ms y el worker lo hace async.
    if NumMedia > 0 and MediaUrl0:
        payload = {
            "sender_phone": From.replace("whatsapp:", ""),
            "media_url": MediaUrl0,
            "content_type": MediaContentType0,
            "body": Body,
        }
        message_id = sqs_client.send_message(payload)
        return {"status": "queued", "message_id": message_id}

    # Paso 3 — si es texto plano, por ahora solo confirmamos recepción.
    # El flujo conversacional completo viene en Fase 2.
    return {"status": "received", "body": Body}