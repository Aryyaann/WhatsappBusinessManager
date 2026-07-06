from fastapi import APIRouter

from app.core.database import get_db_session
from app.models.product import Product
from app.models.stock import StockLevel
from sqlalchemy import select

router = APIRouter()


@router.get("/api/admin/products")
async def list_products(business_id: str):
    # NOTA: sin autenticación todavía. business_id llega como query param sin
    # verificar contra ninguna sesión — es un placeholder deliberado hasta
    # que montemos login/sesión para el panel (paso posterior de Fase 5).
    # No usar este endpoint tal cual en producción.
    async with get_db_session() as db:
        stmt = (
            select(Product, StockLevel.quantity)
            .outerjoin(
                StockLevel,
                (StockLevel.product_id == Product.id) & (StockLevel.business_id == business_id),
            )
            .where(Product.business_id == business_id, Product.is_active == True)
            .order_by(Product.name)
        )
        rows = (await db.execute(stmt)).all()

        return [
            {
                "id": str(row.Product.id),
                "name": row.Product.name,
                "sku": row.Product.sku,
                "unit": row.Product.unit,
                "quantity": float(row.quantity) if row.quantity is not None else 0.0,
                "min_stock_threshold": row.Product.min_stock_threshold,
                "sale_price": float(row.Product.sale_price) if row.Product.sale_price is not None else None,
            }
            for row in rows
        ]