import asyncio
from sqlalchemy import select
from app.core.database import get_db_session
from app.models.product import Product
from app.models.business import Business


async def main():
    async with get_db_session() as db:
        businesses = (await db.execute(select(Business))).scalars().all()
        print("Negocios encontrados:")
        for b in businesses:
            print(f"  - {b.id} | {b.name} | whatsapp: {b.whatsapp_number}")

        products = (await db.execute(select(Product))).scalars().all()
        print(f"\nProductos encontrados: {len(products)}")
        for p in products:
            tiene_embedding = "SÍ" if p.embedding is not None else "NO"
            print(f"  - {p.name} | embedding: {tiene_embedding} | business_id: {p.business_id}")

asyncio.run(main())