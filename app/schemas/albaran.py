from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class AlbaranLine(BaseModel):
    # Una línea del albarán — un producto con su cantidad, precio y opcionales.
    product_name: str
    quantity: Decimal
    unit_cost: Decimal
    expiry_date: Optional[date] = None
    lot_number: Optional[str] = None
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class AlbaranExtraction(BaseModel):
    # El JSON completo que devuelve Claude después de procesar el albarán.
    # supplier_name y order_date son opcionales — Claude puede no encontrarlos.
    supplier_name: Optional[str] = None
    order_date: Optional[date] = None
    lines: list[AlbaranLine] = Field(default_factory=list)


class AlbaranProcessingResult(BaseModel):
    # Lo que devuelve el worker después de procesar el albarán completo.
    # Incluye la extracción de Claude, la key de S3, y las líneas que
    # necesitan confirmación humana (confidence < 0.85).
    s3_key: str
    extraction: AlbaranExtraction
    lines_auto_confirmed: list[AlbaranLine] = Field(default_factory=list)
    lines_pending_review: list[AlbaranLine] = Field(default_factory=list)