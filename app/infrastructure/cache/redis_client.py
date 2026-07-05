import json
from typing import Any, Optional

import redis

from app.core.config import settings


class RedisClient:
    # Cliente síncrono de redis-py. Se usa tanto desde el webhook (FastAPI)
    # como desde el worker de Celery, así que un cliente síncrono simple
    # evita duplicar lógica async/sync — mismo criterio que ya se sigue con
    # boto3 en S3Client y TextractClient.
    def __init__(self):
        self._client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        # Guarda cualquier valor serializable como JSON, con expiración
        # obligatoria — no queremos estados de confirmación pendientes
        # acumulándose para siempre si el dueño nunca contesta.
        self._client.set(key, json.dumps(value), ex=ttl_seconds)

    def get_json(self, key: str) -> Optional[Any]:
        # Devuelve None si la key no existe o ya expiró.
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def delete(self, key: str) -> None:
        self._client.delete(key)


# Instancia única compartida por todo el proceso.
redis_client = RedisClient()