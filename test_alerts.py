import asyncio
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy import select
from app.core.database import get_db_session
from app.models.product import Product
from app.models.stock import StockLevel, StockMovement
from app.workers.alerts_worker import _send_all_alerts

BUSINESS_ID = "d62a4701-f49a-4f90-8503-9d59346f91e5"
PRODUCT_ID = "29fba3bb-ee92-486a-918c-3ef997d5c700"

async def setup():
    async with get_db_session() as db:
        # 1. Umbral mínimo alto a propósito, para forzar que salte la alerta
        product = (await db.execute(select(Product).where(Product.id == PRODUCT_ID))).scalar_one()
        product.min_stock_threshold = 20

        # 2. Stock bajo (por debajo de ese umbral)
        stock = (await db.execute(select(StockLevel).where(StockLevel.product_id == PRODUCT_ID))).scalar_one_or_none()
        if stock:
            stock.quantity = Decimal("3")
        else:
            db.add(StockLevel(business_id=BUSINESS_ID, product_id=PRODUCT_ID, quantity=Decimal("3")))

        # 3. Un movimiento con caducidad próxima, para probar también esa alerta
        db.add(StockMovement(
            business_id=BUSINESS_ID,
            product_id=PRODUCT_ID,
            movement_type="purchase",
            quantity=Decimal("3"),
            unit_cost=Decimal("5.00"),
            expiry_date=date.today() + timedelta(days=3),
            lot_number="LOTE-PRUEBA",
        ))

        await db.commit()
        print("Datos de prueba listos: stock=3, umbral=20, caduca en 3 días", flush=True)

async def main():
    await setup()
    alerts_sent = await _send_all_alerts()
    print(f"Alertas enviadas: {alerts_sent}", flush=True)

asyncio.run(main())