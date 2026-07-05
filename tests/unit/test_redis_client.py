import json
from unittest.mock import MagicMock, patch

from app.infrastructure.cache.redis_client import RedisClient


@patch("app.infrastructure.cache.redis_client.redis.Redis")
def test_set_json_serializes_value_and_sets_ttl(mock_redis_cls):
    mock_conn = MagicMock()
    mock_redis_cls.from_url.return_value = mock_conn

    client = RedisClient()
    client.set_json("pending:+34600000000", {"product_name": "Tinte Rubio"}, ttl_seconds=3600)

    mock_conn.set.assert_called_once_with(
        "pending:+34600000000", json.dumps({"product_name": "Tinte Rubio"}), ex=3600
    )


@patch("app.infrastructure.cache.redis_client.redis.Redis")
def test_get_json_returns_none_when_key_missing(mock_redis_cls):
    mock_conn = MagicMock()
    mock_conn.get.return_value = None
    mock_redis_cls.from_url.return_value = mock_conn

    client = RedisClient()
    result = client.get_json("missing-key")

    assert result is None


@patch("app.infrastructure.cache.redis_client.redis.Redis")
def test_get_json_deserializes_existing_value(mock_redis_cls):
    mock_conn = MagicMock()
    mock_conn.get.return_value = json.dumps({"product_name": "Tinte Rubio"})
    mock_redis_cls.from_url.return_value = mock_conn

    client = RedisClient()
    result = client.get_json("pending:+34600000000")

    assert result == {"product_name": "Tinte Rubio"}


@patch("app.infrastructure.cache.redis_client.redis.Redis")
def test_delete_calls_underlying_client(mock_redis_cls):
    mock_conn = MagicMock()
    mock_redis_cls.from_url.return_value = mock_conn

    client = RedisClient()
    client.delete("pending:+34600000000")

    mock_conn.delete.assert_called_once_with("pending:+34600000000")