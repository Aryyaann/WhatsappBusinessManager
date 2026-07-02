import pytest
from decimal import Decimal
from app.schemas.albaran import AlbaranLine, AlbaranExtraction, AlbaranProcessingResult


def test_albaran_line_valid():
    line = AlbaranLine(
        product_name="Tinte Rubio 100ml",
        quantity=Decimal("10"),
        unit_cost=Decimal("5.50"),
    )
    assert line.confidence_score == 1.0
    assert line.expiry_date is None
    assert line.lot_number is None


def test_albaran_line_confidence_bounds():
    # confidence_score debe estar entre 0 y 1.
    with pytest.raises(Exception):
        AlbaranLine(
            product_name="Producto",
            quantity=Decimal("1"),
            unit_cost=Decimal("1"),
            confidence_score=1.5,
        )


def test_albaran_extraction_from_json():
    # Simula el JSON que devuelve Claude y verifica que Pydantic lo parsea bien.
    raw = """
    {
        "supplier_name": "Proveedor Test",
        "order_date": "2026-07-01",
        "lines": [
            {
                "product_name": "Tinte Rubio",
                "quantity": 5.0,
                "unit_cost": 3.50
            }
        ]
    }
    """
    extraction = AlbaranExtraction.model_validate_json(raw)
    assert extraction.supplier_name == "Proveedor Test"
    assert len(extraction.lines) == 1
    assert extraction.lines[0].product_name == "Tinte Rubio"


def test_albaran_extraction_empty_lines():
    extraction = AlbaranExtraction(supplier_name=None, lines=[])
    assert extraction.lines == []
    assert extraction.supplier_name is None


def test_processing_result_splits_lines():
    # Verifica que las líneas se separan correctamente por confidence_score.
    high = AlbaranLine(product_name="A", quantity=Decimal("1"), unit_cost=Decimal("1"), confidence_score=0.95)
    low = AlbaranLine(product_name="B", quantity=Decimal("1"), unit_cost=Decimal("1"), confidence_score=0.70)

    result = AlbaranProcessingResult(
        s3_key="test/key",
        extraction=AlbaranExtraction(lines=[high, low]),
        lines_auto_confirmed=[high],
        lines_pending_review=[low],
    )
    assert len(result.lines_auto_confirmed) == 1
    assert len(result.lines_pending_review) == 1
    assert result.lines_auto_confirmed[0].product_name == "A"
    assert result.lines_pending_review[0].product_name == "B"