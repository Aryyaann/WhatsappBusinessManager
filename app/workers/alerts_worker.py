import asyncio

from celery.schedules import crontab
from sqlalchemy import select

from app.core.database import get_db_session
from app.models.business import Business
from app.domain.alerts.low_stock_service import LowStockAlertService
from app.infrastructure.messaging.twilio_client import twilio_client
from app.workers.albaran_worker import celery_app

# Reutilizamos el mismo celery_app que albaran_worker (mismo broker SQS) en
# vez de crear una segunda instancia de Celery — un único worker puede
# procesar tanto el procesado de albaranes como esta tarea programada.
celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "send-low-stock-alerts-daily": {
        "task": "app.workers.alerts_worker.send_low_stock_alerts",
        "schedule": crontab(hour=9, minute=0),  # todos los días a las 9:00
    },
}


def _build_alert_message(items: list[dict]) -> str:
    lines = ["⚠️ *Aviso de stock bajo*\n"]
    for item in items:
        lines.append(
            f"- {item['product_name']}: quedan {item['quantity']} "
            f"(mínimo configurado: {item['min_stock_threshold']})"
        )
    lines.append("\nRevisa si necesitas hacer un pedido a tu proveedor.")
    return "\n".join(lines)


async def _send_all_alerts() -> int:
    # Recorre todos los negocios activos y manda un único mensaje agrupado
    # por negocio (no uno por producto) para no saturar el WhatsApp del
    # dueño. Devuelve cuántos avisos se enviaron, útil para logging/tests.
    alerts_sent = 0
    async with get_db_session() as db:
        businesses = (
            await db.execute(select(Business).where(Business.is_active == True))
        ).scalars().all()

        alert_service = LowStockAlertService(db)
        for business in businesses:
            low_stock_items = await alert_service.get_low_stock_products(str(business.id))
            if not low_stock_items:
                continue

            twilio_client.send_text(
                to_number=business.whatsapp_number,
                body=_build_alert_message(low_stock_items),
            )
            alerts_sent += 1

    return alerts_sent


@celery_app.task
def send_low_stock_alerts():
    return asyncio.run(_send_all_alerts())