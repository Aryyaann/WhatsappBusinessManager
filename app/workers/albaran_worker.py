import httpx
from celery import Celery

from app.core.config import settings
from app.infrastructure.storage.s3_client import s3_client
from app.infrastructure.storage.sqs_client import sqs_client
from app.infrastructure.ocr.textract_client import textract_client
from app.infrastructure.llm.anthropic_client import anthropic_client
from app.infrastructure.messaging.twilio_client import twilio_client

# Instancia de Celery con SQS como broker.
# La URL del broker sigue el formato que celery[sqs] espera.
celery_app = Celery("albaran_worker")
celery_app.conf.broker_url = f"sqs://{ settings.aws_access_key_id}:{settings.aws_secret_access_key}@"
celery_app.conf.broker_transport_options = {
    "region": settings.aws_region,
    "predefined_queues": {
        "whatsapp-bm-dev-jobs": {
            "url": settings.sqs_queue_url,
        }
    },
}
celery_app.conf.task_default_queue = "whatsapp-bm-dev-jobs"

SYSTEM_PROMPT_ALBARAN = """
Eres un asistente especializado en extraer datos de albaranes de proveedores españoles.
Se te proporcionará el texto y las tablas extraídas de un albarán mediante OCR.
Debes devolver un JSON con esta estructura exacta, sin texto adicional:
{
    "supplier_name": "nombre del proveedor o null",
    "order_date": "fecha en formato YYYY-MM-DD o null",
    "lines": [
        {
            "product_name": "nombre del producto",
            "quantity": 0.0,
            "unit_cost": 0.0,
            "expiry_date": "YYYY-MM-DD o null",
            "lot_number": "número de lote o null"
        }
    ]
}
"""


@celery_app.task(bind=True, max_retries=3)
def process_albaran(self, payload: dict):
    sender_phone = payload["sender_phone"]
    media_url = payload["media_url"]
    content_type = payload.get("content_type", "image/jpeg")

    try:
        # Paso 1 — descargar la imagen desde la URL de Twilio.
        # Twilio requiere autenticación básica para acceder a los media.
        with httpx.Client() as client:
            response = client.get(
                media_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            image_bytes = response.content

        # Paso 2 — subir la imagen original a S3 antes de procesarla.
        # Así nunca perdemos la foto aunque el procesamiento falle.
        s3_key = s3_client.upload_file(
            file_bytes=image_bytes,
            prefix="albaranes",
            content_type=content_type,
        )

        # Paso 3 — pasar la imagen por Textract para extraer texto y tablas.
        # Textract devuelve texto estructurado — más barato y preciso que
        # mandar la imagen cruda a Claude.
        textract_output = textract_client.extract_text_and_tables(image_bytes)

        # Paso 4 — llamar a Claude con el output de Textract.
        # Claude extrae los datos estructurados del albarán.
        llm_response = anthropic_client.extract_albaran(
            textract_output=textract_output,
            system_prompt=SYSTEM_PROMPT_ALBARAN,
        )

        # Paso 5 — confirmar al dueño por WhatsApp qué se ha procesado.
        # Mensaje simple con el texto que Claude devolvió.
        twilio_client.send_text(
            to_number=sender_phone,
            body=f"✅ Albarán procesado:\n\n{llm_response['content']}",
        )

    except Exception as exc:
        # Si algo falla, reintentamos con backoff exponencial: 1s, 2s, 4s.
        # Después de 3 intentos el job va a la DLQ automáticamente.
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)