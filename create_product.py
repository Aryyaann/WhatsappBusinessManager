import asyncio
from decimal import Decimal
from app.core.database import get_db_session
from app.domain.catalog.service import CatalogService
from app.models.stock import StockLevel

BUSINESS_ID = "d62a4701-f49a-4f90-8503-9d59346f91e5"
STOCK_INICIAL = Decimal("12")

async def main():
    async with get_db_session() as db:
        service = CatalogService(db)
        product = await service.create_product(
            business_id=BUSINESS_ID,
            name="Tinte Rubio 100ml",
            cost_price=Decimal("5.00"),
            sale_price=Decimal("9.00"),
        )
        print(f"Producto creado: {product.id} — {product.name}", flush=True)

        db.add(StockLevel(
            business_id=BUSINESS_ID,
            product_id=product.id,
            quantity=STOCK_INICIAL,
        ))
        await db.commit()
        print(f"Stock inicial asignado: {STOCK_INICIAL} unidades", flush=True)

asyncio.run(main())