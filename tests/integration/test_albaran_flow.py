import pytest
from pathlib import Path

from app.infrastructure.storage.s3_client import s3_client
from app.infrastructure.ocr.textract_client import textract_client
from app.infrastructure.llm.anthropic_client import anthropic_client

SYSTEM_PROMPT_ALBARAN = """
Eres un asistente especializado en extraer datos de albaranes de proveedores españoles.
Se te proporcionará el texto y las tablas extraídas de un albarán mediante OCR.
Debes devolver un JSON con esta estructura exacta, sin texto adicional:
{
    "supplier_name": "nombre del proveedor o null",
    "order_date": "fecha en formato YYYY-MM-DD o null",
    "lines": [
        {
            "product_name": "nombre del producto",
            "quantity": 0.0,
            "unit_cost": 0.0,
            "expiry_date": "YYYY-MM-DD o null",
            "lot_number": "número de lote o null"
        }
    ]
}
"""


def test_s3_upload_and_download():
    # Verifica que podemos subir bytes a S3 y recuperarlos.
    test_bytes = b"test image content"
    key = s3_client.upload_file(
        file_bytes=test_bytes,
        prefix="test",
        content_type="image/jpeg",
    )
    assert key.startswith("test/")

    downloaded = s3_client.download_file(key)
    assert downloaded == test_bytes


def test_s3_presigned_url():
    # Verifica que la URL firmada se genera correctamente.
    test_bytes = b"test image content"
    key = s3_client.upload_file(
        file_bytes=test_bytes,
        prefix="test",
        content_type="image/jpeg",
    )
    url = s3_client.generate_presigned_url(key)
    assert url.startswith("https://")
    assert "whatsapp-bm-dev-uploads" in url


def test_full_albaran_flow():
    # Test end-to-end: carga una imagen de prueba del disco,
    # la pasa por Textract y luego por Claude.
    # Necesitas una imagen real en tests/fixtures/albaran_sample.jpg
    fixture_path = Path("tests/fixtures/albaran_sample.jpg")
    if not fixture_path.exists():
        pytest.skip("No hay imagen de prueba en tests/fixtures/albaran_sample.jpg")

    image_bytes = fixture_path.read_bytes()

    # Paso 1 — subir a S3
    key = s3_client.upload_file(
        file_bytes=image_bytes,
        prefix="test/albaranes",
        content_type="image/jpeg",
    )
    assert key.startswith("test/albaranes/")

    # Paso 2 — Textract
    textract_output = textract_client.extract_text_and_tables(image_bytes)
    assert "raw_text" in textract_output
    assert "tables" in textract_output

    # Paso 3 — Claude
    llm_response = anthropic_client.extract_albaran(
        textract_output=textract_output,
        system_prompt=SYSTEM_PROMPT_ALBARAN,
    )
    assert "content" in llm_response
    assert "usage" in llm_response
    print(f"\nRespuesta de Claude:\n{llm_response['content']}")