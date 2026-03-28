from __future__ import annotations

from travel_agent.ucp.models import OrderEvent, OrderStatus


class OrderTracker:
    """In-memory order event log. Persisted via the webhook handler."""

    def __init__(self):
        self._events: dict[str, list[OrderEvent]] = {}

    def record(self, event: OrderEvent) -> None:
        self._events.setdefault(event.order_id, []).append(event)

    def latest_status(self, order_id: str) -> OrderStatus | None:
        events = self._events.get(order_id, [])
        return events[-1].status if events else None

    def history(self, order_id: str) -> list[OrderEvent]:
        return self._events.get(order_id, [])
