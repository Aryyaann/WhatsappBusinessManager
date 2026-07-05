from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.product import Product
from app.models.stock import StockLevel
from app.infrastructure.embeddings.openai_client import embedding_client

# Cuántos productos candidatos devolvemos como máximo por consulta. Con esto
# alcanza incluso si el dueño pregunta por algo genérico ("tintes") que
# podría matchear varios productos parecidos.
MAX_RESULTS = 5

# Distancia coseno máxima para considerar un producto relevante para la
# consulta. Más permisivo que el matching de albaranes (0.15) porque aquí
# el objetivo es sugerir candidatos razonables para que el dueño elija,
# no decidir automáticamente una acción sobre el stock.
QUERY_MATCH_THRESHOLD = 0.35


class StockQueryService:
    # Servicio de solo lectura: consultas de stock en lenguaje natural.
    # Se apoya en los mismos embeddings del catálogo que ya usa
    # InventoryService para el matching de albaranes (misma "memoria").

    def __init__(self, db: AsyncSession):
        self.db = db

    async def query_stock(self, business_id: str, query_text: str) -> list[dict]:
        # Convierte la pregunta del dueño ("tinte rubio") en un vector y
        # busca los productos del catálogo más cercanos semánticamente,
        # trayendo su stock actual en la misma consulta (LEFT JOIN porque
        # un producto puede no tener fila en stock_levels todavía).
        query_embedding = embedding_client.embed_text(query_text)
        distance = Product.embedding.cosine_distance(query_embedding)

        stmt = (
            select(Product, StockLevel.quantity, distance.label("distance"))
            .outerjoin(
                StockLevel,
                (StockLevel.product_id == Product.id) & (StockLevel.business_id == business_id),
            )
            .where(
                Product.business_id == business_id,
                Product.is_active == True,
                Product.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(MAX_RESULTS)
        )
        rows = (await self.db.execute(stmt)).all()

        results = []
        for row in rows:
            if row.distance > QUERY_MATCH_THRESHOLD:
                continue
            results.append({
                "product_name": row.Product.name,
                "quantity": row.quantity if row.quantity is not None else Decimal("0"),
                "unit": row.Product.unit,
                "sale_price": row.Product.sale_price,
            })
        return results