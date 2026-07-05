from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal
from typing import Optional

from app.infrastructure.cache.redis_client import redis_client

# Tiempo que se mantiene en cola una confirmación pendiente antes de
# descartarla si el dueño nunca contesta. 24h da margen suficiente sin
# acumular basura indefinidamente en Redis.
PENDING_TTL_SECONDS = 24 * 60 * 60


def _queue_key(phone: str) -> str:
    return f"pending_products:{phone}"


@dataclass
class PendingProductLine:
    # Representación serializable de una línea de albarán con producto no
    # reconocido, a la espera de que el dueño confirme si se da de alta.
    # quantity/unit_cost van como str porque Decimal no es serializable a
    # JSON directamente.
    business_id: str
    created_by: str
    product_name: str
    quantity: str
    unit_cost: str
    expiry_date: Optional[str] = None
    lot_number: Optional[str] = None


class PendingConfirmationService:
    # Cola de productos "no reconocidos" esperando que el dueño confirme
    # por WhatsApp si se añaden al catálogo o no. Una cola por número de
    # teléfono, porque un mismo albarán puede traer varias líneas nuevas.

    def enqueue(
        self,
        phone: str,
        business_id: str,
        created_by: str,
        product_name: str,
        quantity: Decimal,
        unit_cost: Decimal,
        expiry_date: Optional[date] = None,
        lot_number: Optional[str] = None,
    ) -> None:
        item = PendingProductLine(
            business_id=business_id,
            created_by=created_by,
            product_name=product_name,
            quantity=str(quantity),
            unit_cost=str(unit_cost),
            expiry_date=expiry_date.isoformat() if expiry_date else None,
            lot_number=lot_number,
        )
        queue = redis_client.get_json(_queue_key(phone)) or []
        queue.append(asdict(item))
        redis_client.set_json(_queue_key(phone), queue, ttl_seconds=PENDING_TTL_SECONDS)

    def peek_next(self, phone: str) -> Optional[dict]:
        # Consulta la primera línea pendiente sin quitarla de la cola.
        queue = redis_client.get_json(_queue_key(phone))
        if not queue:
            return None
        return queue[0]

    def pop_next(self, phone: str) -> Optional[dict]:
        # Quita y devuelve la primera línea pendiente. Se usa cuando el
        # dueño ya respondió (SI/NO) y hay que pasar a la siguiente.
        queue = redis_client.get_json(_queue_key(phone))
        if not queue:
            return None
        item = queue.pop(0)
        if queue:
            redis_client.set_json(_queue_key(phone), queue, ttl_seconds=PENDING_TTL_SECONDS)
        else:
            redis_client.delete(_queue_key(phone))
        return item

    def has_pending(self, phone: str) -> bool:
        return self.peek_next(phone) is not None


# Instancia única compartida por todo el proceso.
pending_confirmation_service = PendingConfirmationService()