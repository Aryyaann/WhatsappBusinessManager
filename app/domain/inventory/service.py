from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.stock import StockLevel, StockMovement
from app.models.product import Product
from app.schemas.albaran import AlbaranProcessingResult, AlbaranLine
from app.infrastructure.embeddings.openai_client import embedding_client

# Distancia coseno máxima para aceptar un match semántico como válido.
# pgvector calcula cosine_distance = 1 - cosine_similarity, así que 0.15
# equivale a exigir similitud >= 0.85. Umbral conservador a propósito:
# mejor marcar como no reconocido de más que mezclar stock de productos
# distintos. Se ajustará con datos reales cuando haya catálogos en producción.
SEMANTIC_MATCH_THRESHOLD = 0.15


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
        skipped_lines = []

        for line in result.lines_auto_confirmed:
            product = await self._find_product(business_id, line.product_name)
            if product is None:
                # Producto no reconocido — va a la lista de skipped.
                # skipped_lines guarda la línea completa (cantidad, coste,
                # caducidad, lote), no solo el nombre, porque el worker la
                # necesita entera para encolarla como confirmación pendiente.
                skipped.append(line.product_name)
                skipped_lines.append(line)
                continue

            await self._update_stock(business_id, product.id, line.quantity)
            await self._create_movement(
                business_id=business_id,
                product_id=product.id,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                created_by=created_by,
                expiry_date=line.expiry_date,
                lot_number=line.lot_number,
            )
            applied.append(line.product_name)

        await self.db.commit()
        return {"applied": applied, "skipped": skipped, "skipped_lines": skipped_lines}

    async def apply_confirmed_new_product(
        self,
        business_id: str,
        product_id: str,
        quantity: Decimal,
        unit_cost: Decimal,
        created_by: str,
        expiry_date=None,
        lot_number: str = None,
    ) -> None:
        # Se usa cuando el dueño confirma por WhatsApp un producto que antes
        # no existía en el catálogo (ver PendingConfirmationService). El
        # producto ya se ha creado en CatalogService; aquí solo aplicamos el
        # movimiento de stock, igual que si hubiera hecho match desde el
        # principio.
        await self._update_stock(business_id, product_id, quantity)
        await self._create_movement(
            business_id=business_id,
            product_id=product_id,
            quantity=quantity,
            unit_cost=unit_cost,
            created_by=created_by,
            expiry_date=expiry_date,
            lot_number=lot_number,
        )
        await self.db.commit()

    async def set_stock_quantity(
        self,
        business_id: str,
        product_id: str,
        new_quantity: Decimal,
        adjusted_by: str = None,
    ) -> None:
        # Ajuste manual desde el panel: fija el stock a un valor absoluto
        # (a diferencia de los albaranes, que suman). Deja constancia del
        # cambio como movimiento tipo "adjustment" para no perder
        # trazabilidad — un stock que cambia solo, sin rastro, es peor que
        # uno que no cambia nunca.
        result = await self.db.execute(
            select(StockLevel).where(
                StockLevel.business_id == business_id,
                StockLevel.product_id == product_id,
            )
        )
        stock = result.scalar_one_or_none()
        previous_quantity = stock.quantity if stock else Decimal("0")
        delta = new_quantity - previous_quantity

        if stock:
            stock.quantity = new_quantity
        else:
            self.db.add(StockLevel(
                business_id=business_id,
                product_id=product_id,
                quantity=new_quantity,
            ))

        self.db.add(StockMovement(
            business_id=business_id,
            product_id=product_id,
            movement_type="adjustment",
            quantity=delta,
            created_by=adjusted_by,
        ))
        await self.db.commit()

    async def _find_product(self, business_id: str, name: str):
        # 1. Match exacto primero: más rápido y sin ambigüedad cuando el
        # nombre del albarán coincide literal con el catálogo.
        result = await self.db.execute(
            select(Product).where(
                Product.business_id == business_id,
                Product.name == name,
                Product.is_active == True,
            )
        )
        product = result.scalar_one_or_none()
        if product is not None:
            return product

        # 2. Sin match exacto, buscamos por similitud semántica contra los
        # embeddings del catálogo (pgvector, distancia coseno). Cubre casos
        # como "Tinte Rubio N7" en el albarán vs "Tinte Rubio Nº7 100ml" en
        # el catálogo.
        query_embedding = embedding_client.embed_text(name)
        distance = Product.embedding.cosine_distance(query_embedding)
        stmt = (
            select(Product, distance.label("distance"))
            .where(
                Product.business_id == business_id,
                Product.is_active == True,
                Product.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(1)
        )
        row = (await self.db.execute(stmt)).first()
        if row is None or row.distance > SEMANTIC_MATCH_THRESHOLD:
            return None
        return row.Product

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
        expiry_date=None,
        lot_number: str = None,
    ) -> None:
        # Crea un registro inmutable en stock_movements.
        # movement_type="purchase" porque viene de un albarán de proveedor.
        # expiry_date/lot_number son opcionales — no todos los proveedores
        # los indican en el albarán.
        movement = StockMovement(
            business_id=business_id,
            product_id=product_id,
            movement_type="purchase",
            quantity=quantity,
            unit_cost=unit_cost,
            created_by=created_by,
            expiry_date=expiry_date,
            lot_number=lot_number,
        )
        self.db.add(movement)