from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from travel_agent.ucp.models import OrderEvent
from travel_agent.ucp.orders import OrderTracker

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Module-level tracker; replaced by app state in production
_order_tracker = OrderTracker()


def get_order_tracker() -> OrderTracker:
    return _order_tracker


@router.post("/ucp/orders")
async def receive_order_event(
    request: Request,
    tracker: OrderTracker = Depends(get_order_tracker),
) -> dict:
    """Receive UCP order lifecycle events from merchants."""
    try:
        body = await request.json()
        event = OrderEvent.model_validate(body)
        tracker.record(event)
        return {"received": True, "order_id": event.order_id, "status": event.status}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/ucp/orders/{order_id}/status")
async def get_order_status(
    order_id: str,
    tracker: OrderTracker = Depends(get_order_tracker),
) -> dict:
    status = tracker.latest_status(order_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order_id": order_id, "status": status, "history": tracker.history(order_id)}
