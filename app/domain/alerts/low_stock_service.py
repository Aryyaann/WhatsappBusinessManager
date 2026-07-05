from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.product import Product
from app.models.stock import StockLevel


class LowStockAlertService:
    # Servicio de solo lectura: detecta qué productos de un negocio están
    # en o por debajo de su umbral mínimo configurado (min_stock_threshold).
    # min_stock_threshold=0 significa "sin alerta configurada para este
    # producto" — por eso se filtra fuera desde la propia consulta SQL.

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_low_stock_products(self, business_id: str) -> list[dict]:
        stmt = (
            select(Product, StockLevel.quantity)
            .outerjoin(
                StockLevel,
                (StockLevel.product_id == Product.id) & (StockLevel.business_id == business_id),
            )
            .where(
                Product.business_id == business_id,
                Product.is_active == True,
                Product.min_stock_threshold > 0,
            )
        )
        rows = (await self.db.execute(stmt)).all()

        results = []
        for row in rows:
            # Un producto sin fila en stock_levels todavía se trata como 0
            # unidades (nunca ha entrado stock de él, o se agotó del todo).
            quantity = row.quantity if row.quantity is not None else Decimal("0")
            if quantity <= row.Product.min_stock_threshold:
                results.append({
                    "product_id": str(row.Product.id),
                    "product_name": row.Product.name,
                    "quantity": quantity,
                    "min_stock_threshold": row.Product.min_stock_threshold,
                })
        return results