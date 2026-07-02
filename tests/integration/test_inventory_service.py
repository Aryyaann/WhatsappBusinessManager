import pytest
import asyncio
from decimal import Decimal
from uuid import uuid4

from app.core.database import get_db_session
from app.domain.inventory.service import InventoryService
from app.schemas.albaran import AlbaranExtraction, AlbaranLine, AlbaranProcessingResult
from app.models.business import Business
from app.models.product import Product
from app.models.stock import StockLevel, StockMovement
from app.models.user import User
from sqlalchemy import select


@pytest.fixture
def sample_result():
    line = AlbaranLine(
        product_name="Tinte Rubio 100ml",
        quantity=Decimal("10"),
        unit_cost=Decimal("5.50"),
        confidence_score=0.95,
    )
    extraction = AlbaranExtraction(
        supplier_name="Proveedor Test",
        lines=[line],
    )
    return AlbaranProcessingResult(
        s3_key="test/albaranes/test-key",
        extraction=extraction,
        lines_auto_confirmed=[line],
        lines_pending_review=[],
    )


@pytest.mark.asyncio
async def test_apply_albaran_creates_stock_movement(sample_result):
    async with get_db_session() as db:
        business = Business(
            id=str(uuid4()),
            name="Peluquería Test",
            whatsapp_number="+34600000000",
            plan="starter",
            timezone="Europe/Madrid",
        )
        db.add(business)
        await db.flush()

        user = User(
            id=str(uuid4()),
            business_id=business.id,
            whatsapp_number="+34600000001",
            name="Dueño Test",
            role="owner",
        )
        db.add(user)
        await db.flush()

        product = Product(
            id=str(uuid4()),
            business_id=business.id,
            name="Tinte Rubio 100ml",
            category="tintes",
            unit="unidad",
            cost_price=Decimal("5.00"),
            sale_price=Decimal("9.00"),
            min_stock_threshold=5,
            is_active=True,
        )
        db.add(product)
        await db.flush()

        service = InventoryService(db)
        result = await service.apply_albaran(
            business_id=business.id,
            result=sample_result,
            created_by=user.id,
        )

        assert "Tinte Rubio 100ml" in result["applied"]
        assert result["skipped"] == []

        stock_result = await db.execute(
            select(StockLevel).where(
                StockLevel.business_id == business.id,
                StockLevel.product_id == product.id,
            )
        )
        stock = stock_result.scalar_one_or_none()
        assert stock is not None
        assert stock.quantity == Decimal("10")

        movement_result = await db.execute(
            select(StockMovement).where(
                StockMovement.business_id == business.id,
                StockMovement.product_id == product.id,
            )
        )
        movement = movement_result.scalar_one_or_none()
        assert movement is not None
        assert movement.movement_type == "purchase"
        assert movement.quantity == Decimal("10")

        await db.rollback()