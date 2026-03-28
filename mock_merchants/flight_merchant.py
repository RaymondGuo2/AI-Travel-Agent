"""
Mock UCP-compliant flight merchant server.
Run: uvicorn mock_merchants.flight_merchant:app --port 8001
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from mock_merchants.base import CheckoutSessionStore, make_ucp_discovery_response

BASE_URL = "http://localhost:8001"
MERCHANT_ID = "skyway-airlines"
MERCHANT_NAME = "SkyWay Airlines"

app = FastAPI(title="Mock Flight Merchant (UCP)")
store = CheckoutSessionStore(MERCHANT_ID)

INVENTORY = json.loads(
    (Path(__file__).parent / "inventory.json").read_text()
)["flights"]


@app.get("/.well-known/ucp")
async def ucp_discovery():
    return make_ucp_discovery_response(MERCHANT_ID, MERCHANT_NAME, BASE_URL, ["flights"])


@app.get("/catalog")
async def search_catalog(
    origin: str | None = None,
    destination: str | None = None,
    date: str | None = None,
    cabin_class: str = "economy",
    adults: int = 1,
    max_results: int = 10,
):
    results = []
    for flight in INVENTORY:
        if origin and flight["origin"].upper() != origin.upper():
            continue
        if destination and flight["destination"].upper() != destination.upper():
            continue

        price_cents = flight["cabin_classes"].get(cabin_class.lower())
        if price_cents is None:
            continue

        results.append({
            "id": flight["id"],
            "name": f"{flight['airline_name']} {flight['flight_number']}",
            "description": (
                f"{flight['origin']} → {flight['destination']} | "
                f"Dep: {flight['departure_time']} Arr: {flight['arrival_time']} | "
                f"Duration: {flight['duration_minutes']}min | {cabin_class.title()}"
            ),
            "category": "flights",
            "price_cents": price_cents * adults,
            "currency": "USD",
            "availability": True,
            "metadata": {
                "airline": flight["airline"],
                "flight_number": flight["flight_number"],
                "origin": flight["origin"],
                "destination": flight["destination"],
                "departure_time": flight["departure_time"],
                "arrival_time": flight["arrival_time"],
                "duration_minutes": flight["duration_minutes"],
                "cabin_class": cabin_class,
                "is_refundable": flight["is_refundable"],
                "baggage_included": flight["baggage_included"],
                "date": date,
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
    tax = int(subtotal * 0.08)
    return {
        "subtotal_cents": subtotal,
        "tax_cents": tax,
        "fees_cents": 0,
        "total_cents": subtotal + tax,
        "currency": "USD",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
