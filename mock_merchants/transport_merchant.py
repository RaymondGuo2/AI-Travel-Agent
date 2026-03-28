"""
Mock UCP-compliant ground transport merchant server.
Run: uvicorn mock_merchants.transport_merchant:app --port 8003
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from mock_merchants.base import CheckoutSessionStore, make_ucp_discovery_response

BASE_URL = "http://localhost:8003"
MERCHANT_ID = "rideright-transport"
MERCHANT_NAME = "RideRight Transport"

app = FastAPI(title="Mock Ground Transport Merchant (UCP)")
store = CheckoutSessionStore(MERCHANT_ID)

INVENTORY = json.loads(
    (Path(__file__).parent / "inventory.json").read_text()
)["ground_transport"]


@app.get("/.well-known/ucp")
async def ucp_discovery():
    return make_ucp_discovery_response(
        MERCHANT_ID, MERCHANT_NAME, BASE_URL, ["ground_transport"]
    )


@app.get("/catalog")
async def search_catalog(
    pickup_location: str | None = None,
    dropoff_location: str | None = None,
    pickup_date: str | None = None,
    days: int = 1,
    transport_type: str | None = None,
    max_results: int = 10,
):
    results = []
    for item in INVENTORY:
        if transport_type and item["type"] != transport_type:
            continue

        if item["type"] == "car_rental":
            price_cents = item["price_per_day_cents"] * days
            desc = f"{item['vehicle_type']} rental | {days} day(s) | ${item['price_per_day_cents']/100:.0f}/day"
        else:
            price_cents = item.get("price_cents", 0)
            desc = f"{item['vehicle_type']} | {item['type'].replace('_', ' ').title()}"

        results.append({
            "id": item["id"],
            "name": f"{item['provider']} — {item['vehicle_type']}",
            "description": desc,
            "category": "ground_transport",
            "price_cents": price_cents,
            "currency": "USD",
            "availability": True,
            "metadata": {
                "provider": item["provider"],
                "type": item["type"],
                "vehicle_type": item["vehicle_type"],
                "pickup_location": pickup_location,
                "dropoff_location": dropoff_location,
                "pickup_date": pickup_date,
                "days": days,
                "is_refundable": item["is_refundable"],
            },
        })

    return {"items": results[:max_results]}


@app.post("/checkout-sessions")
async def create_checkout(request: Request):
    body = await request.json()
    if not body.get("line_items") or not body.get("buyer_email"):
        raise HTTPException(status_code=400, detail="Missing required fields")

    totals = _compute_totals(body["line_items"])
    session = store.create({
        "line_items": body["line_items"],
        "buyer_name": body.get("buyer_name"),
        "buyer_email": body.get("buyer_email"),
        "payment_handler_id": body.get("payment_handler_id"),
        "totals": totals,
    })
    return session


@app.get("/checkout-sessions/{session_id}")
async def get_checkout(session_id: str):
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.put("/checkout-sessions/{session_id}")
async def update_checkout(session_id: str, request: Request):
    body = await request.json()
    session = store.update(session_id, body)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/checkout-sessions/{session_id}/complete")
async def complete_checkout(session_id: str, request: Request):
    body = await request.json()
    session = store.complete(session_id, body)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or not ready")
    return session


@app.delete("/checkout-sessions/{session_id}")
async def cancel_checkout(session_id: str):
    ok = store.cancel(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"canceled": True}


def _compute_totals(line_items: list[dict]) -> dict:
    subtotal = sum(item.get("unit_price_cents", 0) * item.get("quantity", 1) for item in line_items)
    tax = int(subtotal * 0.10)
    return {
        "subtotal_cents": subtotal,
        "tax_cents": tax,
        "fees_cents": 0,
        "total_cents": subtotal + tax,
        "currency": "USD",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
