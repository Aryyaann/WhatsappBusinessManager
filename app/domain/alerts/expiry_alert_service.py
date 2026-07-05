from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.product import Product
from app.models.stock import StockMovement, StockLevel

# Con cuántos días de antelación avisamos de una caducidad próxima.
DEFAULT_DAYS_AHEAD = 7


class ExpiryAlertService:
    # Servicio de solo lectura: detecta lotes cuya fecha de caducidad cae
    # dentro de los próximos N días (incluye los ya caducados, por si un
    # aviso de un día concreto no llegó a mandarse). Solo tiene sentido
    # avisar de un lote si el producto todavía tiene stock en el negocio —
    # si ya se vendió/usó todo, no hay nada que tirar.

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_expiring_products(
        self, business_id: str, days_ahead: int = DEFAULT_DAYS_AHEAD
    ) -> list[dict]:
        limit_date = date.today() + timedelta(days=days_ahead)

        stmt = (
            select(
                Product.name,
                StockMovement.expiry_date,
                StockMovement.lot_number,
                StockLevel.quantity.label("current_stock"),
            )
            .join(Product, Product.id == StockMovement.product_id)
            .outerjoin(
                StockLevel,
                (StockLevel.product_id == Product.id) & (StockLevel.business_id == business_id),
            )
            .where(
                StockMovement.business_id == business_id,
                StockMovement.expiry_date.is_not(None),
                StockMovement.expiry_date <= limit_date,
                Product.is_active == True,
            )
            .order_by(StockMovement.expiry_date)
        )
        rows = (await self.db.execute(stmt)).all()

        results = []
        for row in rows:
            current_stock = row.current_stock if row.current_stock is not None else Decimal("0")
            if current_stock <= 0:
                # Sin stock actual, no tiene sentido avisar de este lote.
                continue
            results.append({
                "product_name": row.name,
                "expiry_date": row.expiry_date,
                "lot_number": row.lot_number,
                "current_stock": current_stock,
            })
        return results