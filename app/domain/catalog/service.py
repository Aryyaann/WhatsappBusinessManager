from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.product import Product, UnitEnum
from app.infrastructure.embeddings.openai_client import embedding_client


class CatalogService:

    def __init__(self, db: AsyncSession):
        # Misma convención que InventoryService: la sesión se inyecta,
        # no se crea aquí. Facilita los tests y mantiene el control de
        # transacciones en el caller.
        self.db = db

    async def create_product(
        self,
        business_id: str,
        name: str,
        description: Optional[str] = None,
        sku: Optional[str] = None,
        barcode: Optional[str] = None,
        category: Optional[str] = None,
        unit: UnitEnum = UnitEnum.unidad,
        cost_price: Optional[Decimal] = None,
        sale_price: Optional[Decimal] = None,
        min_stock_threshold: int = 0,
    ) -> Product:
        # El embedding se genera a partir de name + description (si la hay),
        # porque es el texto que mejor representa semánticamente el producto
        # para el matching contra los nombres que vienen en los albaranes.
        embedding = embedding_client.embed_text(self._embedding_text(name, description))

        product = Product(
            business_id=business_id,
            name=name,
            description=description,
            sku=sku,
            barcode=barcode,
            category=category,
            unit=unit,
            cost_price=cost_price,
            sale_price=sale_price,
            min_stock_threshold=min_stock_threshold,
            embedding=embedding,
        )
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def update_product_name_or_description(
        self,
        product_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Product]:
        result = await self.db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if product is None:
            return None

        # Solo regeneramos el embedding si el texto que lo alimenta cambia
        # de verdad — evita llamadas innecesarias (y coste) a OpenAI cuando
        # se actualiza otro campo del producto (precio, sku, etc.).
        name_changed = name is not None and name != product.name
        description_changed = description is not None and description != product.description

        if name is not None:
            product.name = name
        if description is not None:
            product.description = description

        if name_changed or description_changed:
            product.embedding = embedding_client.embed_text(
                self._embedding_text(product.name, product.description)
            )

        await self.db.commit()
        await self.db.refresh(product)
        return product

    @staticmethod
    def _embedding_text(name: str, description: Optional[str]) -> str:
        # Texto combinado que alimenta el embedding. La descripción aporta
        # contexto semántico extra (ej. "500ml", "para pelo rizado") que
        # ayuda al matching cuando el nombre del albarán es ambiguo.
        if description:
            return f"{name}. {description}"
        return name