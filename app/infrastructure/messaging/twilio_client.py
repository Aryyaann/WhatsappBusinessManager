from twilio.rest import Client
from twilio.request_validator import RequestValidator

from app.core.config import settings


class TwilioClient:
    # Cliente oficial de Twilio. Se instancia una vez con las credenciales
    # de settings y se reutiliza en todas las llamadas.
    def __init__(self):
        self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self._validator = RequestValidator(settings.twilio_auth_token)
        self._from_number = f"whatsapp:{settings.twilio_whatsapp_number}"

    def send_text(self, to_number: str, body: str) -> str:
        # Envía un mensaje de texto por WhatsApp.
        # to_number debe incluir el prefijo internacional: "+34612345678"
        # Devuelve el SID del mensaje para trazabilidad.
        message = self._client.messages.create(
            from_=self._from_number,
            to=f"whatsapp:{to_number}",
            body=body,
        )
        return message.sid

    def send_media(self, to_number: str, body: str, media_url: str) -> str:
        # Envía un mensaje con imagen adjunta por WhatsApp.
        # media_url debe ser una URL pública — usaremos presigned URLs de S3.
        message = self._client.messages.create(
            from_=self._from_number,
            to=f"whatsapp:{to_number}",
            body=body,
            media_url=[media_url],
        )
        return message.sid

    def validate_webhook(self, url: str, params: dict, signature: str) -> bool:
        # Valida la firma HMAC-SHA1 que Twilio añade a cada webhook.
        # Si devuelve False, el request no viene de Twilio — se rechaza con 403.
        return self._validator.validate(url, params, signature)


# Instancia única compartida por todo el proceso.
twilio_client = TwilioClient()