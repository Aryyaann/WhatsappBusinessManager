import asyncio

from celery.schedules import crontab
from sqlalchemy import select

from app.core.database import get_db_session
from app.models.business import Business
from app.domain.alerts.low_stock_service import LowStockAlertService
from app.domain.alerts.expiry_alert_service import ExpiryAlertService
from app.infrastructure.messaging.twilio_client import twilio_client
from app.workers.albaran_worker import celery_app

# Reutilizamos el mismo celery_app que albaran_worker (mismo broker SQS) en
# vez de crear una segunda instancia de Celery — un único worker puede
# procesar tanto el procesado de albaranes como esta tarea programada.
celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "send-daily-alerts": {
        "task": "app.workers.alerts_worker.send_daily_alerts",
        "schedule": crontab(hour=9, minute=0),  # todos los días a las 9:00
    },
}


def _build_alert_message(low_stock_items: list[dict], expiring_items: list[dict]) -> str:
    # Un único mensaje agrupado con ambos tipos de aviso — no mandamos dos
    # mensajes separados para no saturar el WhatsApp del dueño.
    sections = []

    if low_stock_items:
        lines = ["⚠️ *Stock bajo:*"]
        for item in low_stock_items:
            lines.append(
                f"- {item['product_name']}: quedan {item['quantity']} "
                f"(mínimo configurado: {item['min_stock_threshold']})"
            )
        sections.append("\n".join(lines))

    if expiring_items:
        lines = ["⏳ *Próximas caducidades:*"]
        for item in expiring_items:
            lot_info = f" (lote {item['lot_number']})" if item["lot_number"] else ""
            lines.append(
                f"- {item['product_name']}{lot_info}: caduca el "
                f"{item['expiry_date'].strftime('%d/%m/%Y')}, quedan {item['current_stock']}"
            )
        sections.append("\n".join(lines))

    sections.append("Revisa si necesitas hacer un pedido o dar salida a algún producto.")
    return "\n\n".join(sections)


async def _send_all_alerts() -> int:
    # Recorre todos los negocios activos y manda un único mensaje agrupado
    # por negocio (no uno por producto ni uno por tipo de alerta) para no
    # saturar el WhatsApp del dueño. Devuelve cuántos avisos se enviaron,
    # útil para logging/tests.
    alerts_sent = 0
    async with get_db_session() as db:
        businesses = (
            await db.execute(select(Business).where(Business.is_active == True))
        ).scalars().all()

        low_stock_service = LowStockAlertService(db)
        expiry_service = ExpiryAlertService(db)

        for business in businesses:
            business_id = str(business.id)
            low_stock_items = await low_stock_service.get_low_stock_products(business_id)
            expiring_items = await expiry_service.get_expiring_products(business_id)

            if not low_stock_items and not expiring_items:
                continue

            twilio_client.send_text(
                to_number=business.whatsapp_number,
                body=_build_alert_message(low_stock_items, expiring_items),
            )
            alerts_sent += 1

    return alerts_sent


@celery_app.task
def send_daily_alerts():
    return asyncio.run(_send_all_alerts())