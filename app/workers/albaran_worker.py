import json
import httpx
from celery import Celery

from app.core.config import settings
from app.infrastructure.storage.s3_client import s3_client
from app.infrastructure.storage.sqs_client import sqs_client
from app.infrastructure.ocr.textract_client import textract_client
from app.infrastructure.llm.anthropic_client import anthropic_client
from app.infrastructure.messaging.twilio_client import twilio_client
from app.schemas.albaran import AlbaranExtraction, AlbaranProcessingResult

celery_app = Celery("albaran_worker")
celery_app.conf.broker_url = f"sqs://{settings.aws_access_key_id}:{settings.aws_secret_access_key}@"
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

CONFIDENCE_THRESHOLD = 0.85


@celery_app.task(bind=True, max_retries=3)
def process_albaran(self, payload: dict):
    sender_phone = payload["sender_phone"]
    media_url = payload["media_url"]
    content_type = payload.get("content_type", "image/jpeg")

    try:
        # Paso 1 — descargar imagen de Twilio
        with httpx.Client() as client:
            response = client.get(
                media_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            image_bytes = response.content

        # Paso 2 — subir a S3
        s3_key = s3_client.upload_file(
            file_bytes=image_bytes,
            prefix="albaranes",
            content_type=content_type,
        )

        # Paso 3 — Textract
        textract_output = textract_client.extract_text_and_tables(image_bytes)

        # Paso 4 — Claude extrae el JSON estructurado
        llm_response = anthropic_client.extract_albaran(
            textract_output=textract_output,
            system_prompt=SYSTEM_PROMPT_ALBARAN,
        )

        # Paso 5 — parsear y validar con Pydantic.
        # Limpiamos posibles backticks que Claude añade a veces.
        raw_content = llm_response["content"].strip().removeprefix("```json").removesuffix("```").strip()
        extraction = AlbaranExtraction.model_validate_json(raw_content)

        # Paso 6 — separar líneas por confidence_score.
        # Las líneas con score >= 0.85 se confirman automáticamente.
        # Las demás van a revisión humana.
        auto = [l for l in extraction.lines if l.confidence_score >= CONFIDENCE_THRESHOLD]
        pending = [l for l in extraction.lines if l.confidence_score < CONFIDENCE_THRESHOLD]

        result = AlbaranProcessingResult(
            s3_key=s3_key,
            extraction=extraction,
            lines_auto_confirmed=auto,
            lines_pending_review=pending,
        )

        # Paso 7 — responder al dueño con el resumen
        resumen = f"✅ Albarán procesado\n"
        resumen += f"Proveedor: {extraction.supplier_name or 'No detectado'}\n"
        resumen += f"Líneas registradas: {len(auto)}\n"
        if pending:
            resumen += f"⚠️ Líneas pendientes de revisión: {len(pending)}"

        twilio_client.send_text(to_number=sender_phone, body=resumen)
        return result.model_dump()

    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)