"""
Mock UCP-compliant hotel merchant server.
Run: uvicorn mock_merchants.hotel_merchant:app --port 8002
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from mock_merchants.base import CheckoutSessionStore, make_ucp_discovery_response

BASE_URL = "http://localhost:8002"
MERCHANT_ID = "staywell-hotels"
MERCHANT_NAME = "StayWell Hotels"

app = FastAPI(title="Mock Hotel Merchant (UCP)")
store = CheckoutSessionStore(MERCHANT_ID)

INVENTORY = json.loads(
    (Path(__file__).parent / "inventory.json").read_text()
)["hotels"]


@app.get("/.well-known/ucp")
async def ucp_discovery():
    return make_ucp_discovery_response(MERCHANT_ID, MERCHANT_NAME, BASE_URL, ["hotels"])


@app.get("/catalog")
async def search_catalog(
    city: str | None = None,
    check_in: str | None = None,
    check_out: str | None = None,
    room_type: str = "standard",
    guests: int = 1,
    max_results: int = 10,
):
    results = []
    for hotel in INVENTORY:
        if city and hotel["city"].lower() != city.lower():
            continue

        price_per_night_cents = hotel["room_types"].get(room_type.lower())
        if price_per_night_cents is None:
            price_per_night_cents = list(hotel["room_types"].values())[0]

        # Calculate nights (default 1 if dates not provided)
        nights = 1
        if check_in and check_out:
            from datetime import date
            try:
                d_in = date.fromisoformat(check_in)
                d_out = date.fromisoformat(check_out)
                nights = max(1, (d_out - d_in).days)
            except ValueError:
                pass

        total_price_cents = price_per_night_cents * nights

        results.append({
            "id": hotel["id"],
            "name": hotel["name"],
            "description": (
                f"{hotel['star_rating']}-star {hotel['chain'] or 'hotel'} in {hotel['city']} | "
                f"{room_type.title()} room | {nights} night(s) | ${price_per_night_cents/100:.0f}/night"
            ),
            "category": "hotels",
            "price_cents": total_price_cents,
            "currency": "USD",
            "availability": True,
            "metadata": {
                "hotel_name": hotel["name"],
                "chain": hotel["chain"],
                "address": hotel["address"],
                "city": hotel["city"],
                "star_rating": hotel["star_rating"],
                "room_type": room_type,
                "check_in": check_in,
                "check_out": check_out,
                "nights": nights,
                "price_per_night_cents": price_per_night_cents,
                "is_refundable": hotel["is_refundable"],
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
    tax = int(subtotal * 0.12)  # Hotel tax rate
    return {
        "subtotal_cents": subtotal,
        "tax_cents": tax,
        "fees_cents": 0,
        "total_cents": subtotal + tax,
        "currency": "USD",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
