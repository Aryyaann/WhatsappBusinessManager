from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.database import get_db_session
from app.models.product import Product
from app.models.stock import StockLevel
from app.domain.inventory.service import InventoryService
from sqlalchemy import select

router = APIRouter()


class StockAdjustmentRequest(BaseModel):
    quantity: Decimal = Field(ge=0, description="Nuevo stock absoluto, no un delta")


class ThresholdUpdateRequest(BaseModel):
    min_stock_threshold: int = Field(ge=0)


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


@router.patch("/api/admin/products/{product_id}/stock")
async def adjust_stock(product_id: str, body: StockAdjustmentRequest, business_id: str):
    # Ajuste manual del stock (ej. corregir un conteo tras un inventario
    # físico). Fija un valor absoluto, no suma — y queda registrado como
    # movimiento tipo "adjustment" en InventoryService.set_stock_quantity.
    async with get_db_session() as db:
        product = (
            await db.execute(
                select(Product).where(Product.id == product_id, Product.business_id == business_id)
            )
        ).scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        service = InventoryService(db)
        await service.set_stock_quantity(
            business_id=business_id,
            product_id=product_id,
            new_quantity=body.quantity,
        )
        return {"status": "ok", "product_id": product_id, "quantity": float(body.quantity)}


@router.patch("/api/admin/products/{product_id}/threshold")
async def update_threshold(product_id: str, body: ThresholdUpdateRequest, business_id: str):
    async with get_db_session() as db:
        product = (
            await db.execute(
                select(Product).where(Product.id == product_id, Product.business_id == business_id)
            )
        ).scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        product.min_stock_threshold = body.min_stock_threshold
        await db.commit()
        return {"status": "ok", "product_id": product_id, "min_stock_threshold": body.min_stock_threshold}