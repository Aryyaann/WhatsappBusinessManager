from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.stock import StockLevel, StockMovement
from app.models.product import Product
from app.schemas.albaran import AlbaranProcessingResult, AlbaranLine


class InventoryService:

    def __init__(self, db: AsyncSession):
        # La sesión de base de datos se inyecta — no se crea aquí.
        # Esto facilita los tests y mantiene el control de transacciones
        # en el caller.
        self.db = db

    async def apply_albaran(
        self,
        business_id: str,
        result: AlbaranProcessingResult,
        created_by: str,
    ) -> dict:
        # Procesa solo las líneas auto-confirmadas (confidence >= 0.85).
        # Las pendientes de revisión no tocan stock hasta que el dueño confirme.
        applied = []
        skipped = []

        for line in result.lines_auto_confirmed:
            product = await self._find_product(business_id, line.product_name)
            if product is None:
                # Producto no reconocido — va a la lista de skipped.
                # El dueño tendrá que añadirlo al catálogo manualmente.
                skipped.append(line.product_name)
                continue

            await self._update_stock(business_id, product.id, line.quantity)
            await self._create_movement(
                business_id=business_id,
                product_id=product.id,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                created_by=created_by,
            )
            applied.append(line.product_name)

        await self.db.commit()
        return {"applied": applied, "skipped": skipped}

    async def _find_product(self, business_id: str, name: str):
        # Búsqueda exacta por nombre dentro del negocio.
        # En Fase 2 añadiremos fuzzy match con pgvector.
        result = await self.db.execute(
            select(Product).where(
                Product.business_id == business_id,
                Product.name == name,
                Product.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def _update_stock(
        self, business_id: str, product_id: str, quantity: Decimal
    ) -> None:
        # Suma la cantidad recibida al stock actual.
        # Si no existe registro en stock_levels, lo crea con la cantidad.
        result = await self.db.execute(
            select(StockLevel).where(
                StockLevel.business_id == business_id,
                StockLevel.product_id == product_id,
            )
        )
        stock = result.scalar_one_or_none()
        if stock:
            stock.quantity += quantity
        else:
            self.db.add(StockLevel(
                business_id=business_id,
                product_id=product_id,
                quantity=quantity,
            ))

    async def _create_movement(
        self,
        business_id: str,
        product_id: str,
        quantity: Decimal,
        unit_cost: Decimal,
        created_by: str,
    ) -> None:
        # Crea un registro inmutable en stock_movements.
        # movement_type="purchase" porque viene de un albarán de proveedor.
        movement = StockMovement(
            business_id=business_id,
            product_id=product_id,
            movement_type="purchase",
            quantity=quantity,
            unit_cost=unit_cost,
            created_by=created_by,
        )
        self.db.add(movement)