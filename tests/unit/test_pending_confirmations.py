from decimal import Decimal
from unittest.mock import patch

from app.domain.catalog.pending_confirmations import (
    PENDING_TTL_SECONDS,
    PendingConfirmationService,
)


@patch("app.domain.catalog.pending_confirmations.redis_client")
def test_enqueue_creates_queue_when_empty(mock_redis):
    mock_redis.get_json.return_value = None
    service = PendingConfirmationService()

    service.enqueue(
        phone="+34600000001",
        business_id="business-1",
        created_by="user-1",
        product_name="Producto 1",
        quantity=Decimal("2"),
        unit_cost=Decimal("100"),
    )

    mock_redis.set_json.assert_called_once()
    args, kwargs = mock_redis.set_json.call_args
    assert args[0] == "pending_products:+34600000001"
    saved_queue = args[1]
    assert len(saved_queue) == 1
    assert saved_queue[0]["product_name"] == "Producto 1"
    assert saved_queue[0]["quantity"] == "2"
    assert saved_queue[0]["unit_cost"] == "100"
    assert kwargs["ttl_seconds"] == PENDING_TTL_SECONDS


@patch("app.domain.catalog.pending_confirmations.redis_client")
def test_enqueue_appends_to_existing_queue(mock_redis):
    mock_redis.get_json.return_value = [{"product_name": "Producto Existente"}]
    service = PendingConfirmationService()

    service.enqueue(
        phone="+34600000001",
        business_id="business-1",
        created_by="user-1",
        product_name="Producto Nuevo",
        quantity=Decimal("1"),
        unit_cost=Decimal("50"),
    )

    saved_queue = mock_redis.set_json.call_args[0][1]
    assert len(saved_queue) == 2
    assert saved_queue[0]["product_name"] == "Producto Existente"
    assert saved_queue[1]["product_name"] == "Producto Nuevo"


@patch("app.domain.catalog.pending_confirmations.redis_client")
def test_peek_next_returns_none_when_queue_empty(mock_redis):
    mock_redis.get_json.return_value = None
    service = PendingConfirmationService()

    assert service.peek_next("+34600000001") is None


@patch("app.domain.catalog.pending_confirmations.redis_client")
def test_peek_next_does_not_remove_item(mock_redis):
    mock_redis.get_json.return_value = [{"product_name": "A"}, {"product_name": "B"}]
    service = PendingConfirmationService()

    result = service.peek_next("+34600000001")

    assert result == {"product_name": "A"}
    mock_redis.set_json.assert_not_called()
    mock_redis.delete.assert_not_called()


@patch("app.domain.catalog.pending_confirmations.redis_client")
def test_pop_next_removes_first_item_and_keeps_rest(mock_redis):
    mock_redis.get_json.return_value = [{"product_name": "A"}, {"product_name": "B"}]
    service = PendingConfirmationService()

    result = service.pop_next("+34600000001")

    assert result == {"product_name": "A"}
    mock_redis.set_json.assert_called_once_with(
        "pending_products:+34600000001", [{"product_name": "B"}], ttl_seconds=PENDING_TTL_SECONDS
    )
    mock_redis.delete.assert_not_called()


@patch("app.domain.catalog.pending_confirmations.redis_client")
def test_pop_next_deletes_queue_when_it_becomes_empty(mock_redis):
    mock_redis.get_json.return_value = [{"product_name": "A"}]
    service = PendingConfirmationService()

    result = service.pop_next("+34600000001")

    assert result == {"product_name": "A"}
    mock_redis.delete.assert_called_once_with("pending_products:+34600000001")
    mock_redis.set_json.assert_not_called()


@patch("app.domain.catalog.pending_confirmations.redis_client")
def test_pop_next_returns_none_when_queue_empty(mock_redis):
    mock_redis.get_json.return_value = None
    service = PendingConfirmationService()

    assert service.pop_next("+34600000001") is None


@patch("app.domain.catalog.pending_confirmations.redis_client")
def test_has_pending_true_and_false(mock_redis):
    service = PendingConfirmationService()

    mock_redis.get_json.return_value = [{"product_name": "A"}]
    assert service.has_pending("+34600000001") is True

    mock_redis.get_json.return_value = None
    assert service.has_pending("+34600000001") is False