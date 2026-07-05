import os
import json
from unittest.mock import AsyncMock, MagicMock, patch

# El SDK de OpenAI valida la api_key al construir el cliente, y este módulo
# importa (indirectamente, vía InventoryService) el singleton embedding_client.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from app.workers import albaran_worker


class FakeDBSessionCtx:
    # Sustituye a get_db_session() como context manager async.
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        return False


def make_payload(business_id="business-1"):
    return {
        "sender_phone": "+34600000001",
        "media_url": "https://api.twilio.com/fake-media",
        "content_type": "image/jpeg",
        "business_id": business_id,
    }


def make_llm_response():
    body = {
        "supplier_name": "Proveedor Test",
        "order_date": "2026-07-01",
        "lines": [
            {
                "product_name": "Producto 1",
                "quantity": 2.0,
                "unit_cost": 100.0,
                "confidence_score": 0.95,
            }
        ],
    }
    return {"content": json.dumps(body), "usage": {}}


def patch_common(mock_httpx_client_cls, mock_s3, mock_textract, mock_anthropic, mock_inventory_cls, mock_get_db):
    mock_response = MagicMock(content=b"fake-image-bytes")
    mock_client_instance = MagicMock()
    mock_client_instance.get.return_value = mock_response
    mock_httpx_client_cls.return_value.__enter__.return_value = mock_client_instance

    mock_s3.upload_file.return_value = "albaranes/fake-key"
    mock_textract.extract_text_and_tables.return_value = {"raw_text": "...", "tables": []}
    mock_anthropic.extract_albaran.return_value = make_llm_response()

    mock_user = MagicMock(id="user-1")
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_user))
    mock_get_db.return_value = FakeDBSessionCtx(mock_db)

    mock_service_instance = mock_inventory_cls.return_value
    return mock_service_instance


@patch("app.workers.albaran_worker.pending_confirmation_service")
@patch("app.workers.albaran_worker.twilio_client")
@patch("app.workers.albaran_worker.get_db_session")
@patch("app.workers.albaran_worker.InventoryService")
@patch("app.workers.albaran_worker.anthropic_client")
@patch("app.workers.albaran_worker.textract_client")
@patch("app.workers.albaran_worker.s3_client")
@patch("app.workers.albaran_worker.httpx.Client")
def test_sends_confirmation_question_when_queue_was_empty(
    mock_httpx_client_cls, mock_s3, mock_textract, mock_anthropic,
    mock_inventory_cls, mock_get_db, mock_twilio, mock_pending,
):
    from app.schemas.albaran import AlbaranLine

    mock_service_instance = patch_common(
        mock_httpx_client_cls, mock_s3, mock_textract, mock_anthropic, mock_inventory_cls, mock_get_db
    )
    skipped_line = AlbaranLine(product_name="Producto 1", quantity=2, unit_cost=100, confidence_score=0.95)
    mock_service_instance.apply_albaran = AsyncMock(
        return_value={"applied": [], "skipped": ["Producto 1"], "skipped_lines": [skipped_line]}
    )

    mock_pending.has_pending.return_value = False
    mock_pending.peek_next.return_value = {"product_name": "Producto 1", "quantity": "2", "unit_cost": "100"}

    albaran_worker.process_albaran(make_payload())

    mock_pending.enqueue.assert_called_once_with(
        phone="+34600000001",
        business_id="business-1",
        created_by="user-1",
        product_name="Producto 1",
        quantity=skipped_line.quantity,
        unit_cost=skipped_line.unit_cost,
        expiry_date=None,
        lot_number=None,
    )
    # Dos mensajes: la pregunta de confirmación + el resumen final.
    assert mock_twilio.send_text.call_count == 2
    first_call_body = mock_twilio.send_text.call_args_list[0].kwargs["body"]
    assert "Producto 1" in first_call_body
    assert "SI" in first_call_body


@patch("app.workers.albaran_worker.pending_confirmation_service")
@patch("app.workers.albaran_worker.twilio_client")
@patch("app.workers.albaran_worker.get_db_session")
@patch("app.workers.albaran_worker.InventoryService")
@patch("app.workers.albaran_worker.anthropic_client")
@patch("app.workers.albaran_worker.textract_client")
@patch("app.workers.albaran_worker.s3_client")
@patch("app.workers.albaran_worker.httpx.Client")
def test_does_not_resend_question_when_queue_already_had_pending(
    mock_httpx_client_cls, mock_s3, mock_textract, mock_anthropic,
    mock_inventory_cls, mock_get_db, mock_twilio, mock_pending,
):
    from app.schemas.albaran import AlbaranLine

    mock_service_instance = patch_common(
        mock_httpx_client_cls, mock_s3, mock_textract, mock_anthropic, mock_inventory_cls, mock_get_db
    )
    skipped_line = AlbaranLine(product_name="Producto 1", quantity=2, unit_cost=100, confidence_score=0.95)
    mock_service_instance.apply_albaran = AsyncMock(
        return_value={"applied": [], "skipped": ["Producto 1"], "skipped_lines": [skipped_line]}
    )

    mock_pending.has_pending.return_value = True

    albaran_worker.process_albaran(make_payload())

    mock_pending.enqueue.assert_called_once()
    mock_pending.peek_next.assert_not_called()
    # Solo un mensaje: el resumen final. No se interrumpe la conversación
    # pendiente con una pregunta nueva.
    assert mock_twilio.send_text.call_count == 1


@patch("app.workers.albaran_worker.pending_confirmation_service")
@patch("app.workers.albaran_worker.twilio_client")
@patch("app.workers.albaran_worker.get_db_session")
@patch("app.workers.albaran_worker.InventoryService")
@patch("app.workers.albaran_worker.anthropic_client")
@patch("app.workers.albaran_worker.textract_client")
@patch("app.workers.albaran_worker.s3_client")
@patch("app.workers.albaran_worker.httpx.Client")
def test_no_enqueue_when_nothing_skipped(
    mock_httpx_client_cls, mock_s3, mock_textract, mock_anthropic,
    mock_inventory_cls, mock_get_db, mock_twilio, mock_pending,
):
    mock_service_instance = patch_common(
        mock_httpx_client_cls, mock_s3, mock_textract, mock_anthropic, mock_inventory_cls, mock_get_db
    )
    mock_service_instance.apply_albaran = AsyncMock(
        return_value={"applied": ["Producto 1"], "skipped": [], "skipped_lines": []}
    )

    albaran_worker.process_albaran(make_payload())

    mock_pending.enqueue.assert_not_called()
    mock_pending.has_pending.assert_not_called()
    assert mock_twilio.send_text.call_count == 1