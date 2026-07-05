import json
import httpx
from celery import Celery

from app.core.config import settings
from app.core.database import get_db_session
from app.infrastructure.storage.s3_client import s3_client
from app.infrastructure.ocr.textract_client import textract_client
from app.infrastructure.llm.anthropic_client import anthropic_client
from app.infrastructure.messaging.twilio_client import twilio_client
from app.schemas.albaran import AlbaranExtraction, AlbaranProcessingResult
from app.domain.inventory.service import InventoryService
from app.domain.catalog.pending_confirmations import pending_confirmation_service

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
    business_id = payload.get("business_id")

    try:
        # Paso 1 — descargar imagen de Twilio
        with httpx.Client(follow_redirects=True) as client:
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

        # Paso 5 — parsear y validar con Pydantic
        raw_content = llm_response["content"].strip().removeprefix("```json").removesuffix("```").strip()
        extraction = AlbaranExtraction.model_validate_json(raw_content)

        # Paso 6 — separar líneas por confidence_score
        auto = [l for l in extraction.lines if l.confidence_score >= CONFIDENCE_THRESHOLD]
        pending = [l for l in extraction.lines if l.confidence_score < CONFIDENCE_THRESHOLD]

        result = AlbaranProcessingResult(
            s3_key=s3_key,
            extraction=extraction,
            lines_auto_confirmed=auto,
            lines_pending_review=pending,
        )

        # Paso 7 — actualizar stock en base de datos si tenemos business_id
        db_result = {"applied": [], "skipped": [], "skipped_lines": []}
        if business_id:
            import asyncio
            from sqlalchemy import select
            from app.models.user import User

            async def _apply():
                async with get_db_session() as db:
                    user_result = await db.execute(
                        select(User).where(
                            User.business_id == business_id,
                            User.whatsapp_number == sender_phone,
                        )
                    )
                    user = user_result.scalar_one_or_none()
                    if user is None:
                        return {"applied": [], "skipped": [], "skipped_lines": [], "error": "user_not_found"}

                    service = InventoryService(db)
                    result_dict = await service.apply_albaran(
                        business_id=business_id,
                        result=result,
                        created_by=user.id,
                    )
                    result_dict["created_by"] = user.id
                    return result_dict
            db_result = asyncio.run(_apply())

        # Paso 7bis — encolar como confirmación pendiente cada producto no
        # reconocido, para poder preguntarle al dueño si lo da de alta.
        # Solo mandamos la pregunta de WhatsApp si la cola estaba vacía antes
        # de este albarán — si ya había preguntas pendientes de un albarán
        # anterior, no interrumpimos esa conversación con una pregunta nueva.
        skipped_lines = db_result.get("skipped_lines", [])
        if skipped_lines and business_id and db_result.get("created_by"):
            had_pending_before = pending_confirmation_service.has_pending(sender_phone)
            for line in skipped_lines:
                pending_confirmation_service.enqueue(
                    phone=sender_phone,
                    business_id=business_id,
                    created_by=db_result["created_by"],
                    product_name=line.product_name,
                    quantity=line.quantity,
                    unit_cost=line.unit_cost,
                    expiry_date=line.expiry_date,
                    lot_number=line.lot_number,
                )
            if not had_pending_before:
                next_item = pending_confirmation_service.peek_next(sender_phone)
                if next_item:
                    twilio_client.send_text(
                        to_number=sender_phone,
                        body=_build_confirmation_question(next_item),
                    )

        # Paso 8 — responder al dueño con el resumen
        resumen = f"✅ Albarán procesado\n"
        resumen += f"Proveedor: {extraction.supplier_name or 'No detectado'}\n"
        resumen += f"Líneas registradas: {len(db_result['applied'])}\n"
        if db_result["skipped"]:
            resumen += f"⚠️ Productos no reconocidos (te preguntaré si añadirlos): {', '.join(db_result['skipped'])}\n"
        if pending:
            resumen += f"⚠️ Líneas pendientes de revisión: {len(pending)}"

        twilio_client.send_text(to_number=sender_phone, body=resumen)
        return result.model_dump()

    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


def _build_confirmation_question(item: dict) -> str:
    # Mensaje que se envía al dueño cuando hay un producto nuevo esperando
    # confirmación. item viene de PendingConfirmationService (ver
    # app/domain/catalog/pending_confirmations.py) — quantity/unit_cost son
    # strings ahí porque se serializan a JSON en Redis.
    return (
        f"📦 Producto nuevo detectado: *{item['product_name']}*\n"
        f"Cantidad: {item['quantity']} | Coste unidad: {item['unit_cost']}€\n\n"
        f"¿Lo añado al catálogo? Responde *SI* para confirmar o *NO* para descartarlo."
    )