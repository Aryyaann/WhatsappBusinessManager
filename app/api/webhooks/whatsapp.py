from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Form, Header, HTTPException, Request
from sqlalchemy import select

from app.infrastructure.messaging.twilio_client import twilio_client
from app.workers.albaran_worker import process_albaran
from app.core.database import get_db_session
from app.models.business import Business
from app.domain.catalog.pending_confirmations import pending_confirmation_service
from app.domain.catalog.service import CatalogService
from app.domain.inventory.service import InventoryService
from app.domain.conversations.service import ConversationService
from app.domain.conversations.assistant_handler import handle_assistant_request

router = APIRouter()

# Palabras que interpretamos como confirmación o rechazo. En minúsculas y
# sin acentos porque normalizamos el texto antes de comparar.
CONFIRM_WORDS = {"si", "sí", "yes", "ok", "vale", "confirmo"}
REJECT_WORDS = {"no", "cancelar", "descartar"}


def _interpret_reply(body: str) -> Optional[bool]:
    # True = confirma, False = rechaza, None = no se entiende la respuesta.
    normalized = body.strip().lower()
    if normalized in CONFIRM_WORDS:
        return True
    if normalized in REJECT_WORDS:
        return False
    return None


async def _handle_pending_confirmation_reply(sender_phone: str, body: str) -> Optional[str]:
    # Si el dueño tiene una pregunta pendiente sobre un producto nuevo,
    # interpreta su respuesta. Devuelve el mensaje a enviar, o None si no
    # había ninguna pregunta pendiente (el webhook sigue su flujo normal).
    pending_item = pending_confirmation_service.peek_next(sender_phone)
    if pending_item is None:
        return None

    decision = _interpret_reply(body)
    if decision is None:
        # Respuesta ambigua: no quitamos el item de la cola, solo repetimos
        # la pregunta para no perder la confirmación pendiente.
        return (
            f"No te he entendido. Sobre *{pending_item['product_name']}*: "
            f"responde *SI* para añadirlo al catálogo o *NO* para descartarlo."
        )

    # Ya tenemos una respuesta clara — sacamos el item de la cola.
    item = pending_confirmation_service.pop_next(sender_phone)

    if decision is False:
        reply = f"❌ Descartado: *{item['product_name']}* no se ha añadido al catálogo."
    else:
        try:
            quantity = Decimal(item["quantity"])
            unit_cost = Decimal(item["unit_cost"])
        except InvalidOperation:
            reply = f"⚠️ No pude procesar los datos de *{item['product_name']}*. Añádelo manualmente desde el panel."
        else:
            async with get_db_session() as db:
                catalog_service = CatalogService(db)
                product = await catalog_service.create_product(
                    business_id=item["business_id"],
                    name=item["product_name"],
                    cost_price=unit_cost,
                )
                inventory_service = InventoryService(db)
                await inventory_service.apply_confirmed_new_product(
                    business_id=item["business_id"],
                    product_id=product.id,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    created_by=item["created_by"],
                    expiry_date=date.fromisoformat(item["expiry_date"]) if item.get("expiry_date") else None,
                    lot_number=item.get("lot_number"),
                )
            reply = (
                f"✅ Producto añadido: *{item['product_name']}*\n"
                f"Stock inicial: {item['quantity']} unidades."
            )

    # Si quedan más productos pendientes de un albarán anterior, encadenamos
    # la siguiente pregunta justo después de resolver esta.
    next_item = pending_confirmation_service.peek_next(sender_phone)
    if next_item:
        reply += "\n\n" + _next_question_text(next_item)

    return reply


def _next_question_text(item: dict) -> str:
    return (
        f"📦 Producto nuevo detectado: *{item['product_name']}*\n"
        f"Cantidad: {item['quantity']} | Coste unidad: {item['unit_cost']}€\n\n"
        f"¿Lo añado al catálogo? Responde *SI* para confirmar o *NO* para descartarlo."
    )


async def _handle_conversational_query(business_id: str, sender_phone: str, body: str) -> str:
    # Trata el mensaje como una pregunta en lenguaje natural (stock o citas,
    # ver assistant_handler.py) usando Claude con function calling. Loguea
    # ambos lados de la conversación en conversation_messages para poder
    # analizar coste y calidad de las respuestas más adelante.
    # participant_type="owner" por ahora: la resolución de business_id
    # actual solo identifica al número registrado como dueño del negocio;
    # diferenciar empleado/cliente final llega cuando haya un número de
    # WhatsApp Business dedicado por negocio.
    async with get_db_session() as db:
        conversation_service = ConversationService(db)
        conversation = await conversation_service.get_or_create_conversation(
            business_id=business_id,
            participant_phone=sender_phone,
            participant_type="owner",
        )

        # Recuperamos el historial ANTES de loguear el mensaje actual, para
        # no duplicarlo en la lista que le pasamos a Claude. Sin esto,
        # cada mensaje de WhatsApp era una conversación nueva para Claude
        # aunque nosotros sí tuviéramos todo guardado en base de datos.
        recent_messages = await conversation_service.get_recent_messages(conversation.id)
        history = [
            {"role": "user" if m.direction == "inbound" else "assistant", "content": m.content_text}
            for m in recent_messages
        ]

        await conversation_service.log_message(
            conversation_id=conversation.id,
            direction="inbound",
            content_type="text",
            content_text=body,
        )

        result = await handle_assistant_request(
            db, business_id=business_id, customer_phone=sender_phone, message_text=body, history=history
        )
        # dict.fromkeys() en vez de set(): quita duplicados manteniendo el
        # orden de primera aparición. Sin esto, si Claude llama la misma
        # herramienta varias veces en un turno (ej. comprobando varios
        # huecos de disponibilidad), el string repetido puede superar el
        # límite de la columna y tumbar el guardado del mensaje entero.
        unique_tools = list(dict.fromkeys(result["tools_called"])) if result["tools_called"] else []
        tools_called_str = ", ".join(unique_tools) if unique_tools else None

        await conversation_service.log_message(
            conversation_id=conversation.id,
            direction="outbound",
            content_type="text",
            content_text=result["reply"],
            llm_intent=tools_called_str,
            llm_tool_called=tools_called_str,
            llm_tokens_input=result["tokens_input"],
            llm_tokens_output=result["tokens_output"],
        )
        await db.commit()
        return result["reply"]


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
        task = process_albaran.delay(payload)
        return {"status": "queued", "task_id": task.id}

    # Paso 4 — si no hay imagen, comprobar si es respuesta a una pregunta
    # de confirmación de producto nuevo pendiente.
    confirmation_reply = await _handle_pending_confirmation_reply(sender_phone, Body)
    if confirmation_reply is not None:
        twilio_client.send_text(to_number=sender_phone, body=confirmation_reply)
        return {"status": "confirmation_handled"}

    # Paso 5 — si no era una confirmación pendiente y conocemos el negocio,
    # tratamos el mensaje como una consulta conversacional (Fase 2).
    if business_id and Body.strip():
        reply = await _handle_conversational_query(business_id, sender_phone, Body)
        twilio_client.send_text(to_number=sender_phone, body=reply)
        return {"status": "query_handled"}

    return {"status": "received", "body": Body}