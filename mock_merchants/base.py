from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class CheckoutSessionStore:
    """Simple in-memory checkout session store for mock merchants."""

    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self._sessions: dict[str, dict] = {}

    def create(self, data: dict) -> dict:
        session_id = str(uuid.uuid4())
        session = {
            "id": session_id,
            "merchant_id": self.merchant_id,
            "status": "incomplete",
            "order_id": None,
            "escalation_reason": None,
            **data,
        }
        self._sessions[session_id] = session
        # Transition to ready_for_complete if all required fields present
        self._update_status(session)
        return session

    def get(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    def update(self, session_id: str, updates: dict) -> dict | None:
        session = self._sessions.get(session_id)
        if not session:
            return None
        session.update({k: v for k, v in updates.items() if v is not None})
        self._update_status(session)
        return session

    def complete(self, session_id: str, payment_data: dict) -> dict | None:
        session = self._sessions.get(session_id)
        if not session:
            return None
        if session["status"] != "ready_for_complete":
            return None
        session["status"] = "complete_in_progress"
        session["payment_data"] = payment_data
        session["order_id"] = f"ORD-{session_id[:8].upper()}"
        session["status"] = "completed"
        return session

    def cancel(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session["status"] = "canceled"
        return True

    def _update_status(self, session: dict) -> None:
        if session["status"] in ("completed", "canceled", "requires_escalation"):
            return
        if session.get("buyer_name") and session.get("buyer_email") and session.get("line_items"):
            session["status"] = "ready_for_complete"
        else:
            session["status"] = "incomplete"


def make_ucp_discovery_response(
    merchant_id: str,
    merchant_name: str,
    base_url: str,
    categories: list[str],
) -> dict:
    return {
        "version": "2026-01-11",
        "merchant_id": merchant_id,
        "merchant_name": merchant_name,
        "services": {
            "dev.ucp.shopping": {
                "checkout_url": f"{base_url}/checkout-sessions",
                "catalog_url": f"{base_url}/catalog",
                "orders_url": f"{base_url}/orders",
            }
        },
        "capabilities": ["checkout", "catalog", "orders"] + categories,
        "payment_handlers": [
            {"id": "ap2-handler", "type": "ap2", "display_name": "AP2 Payments"},
            {"id": "simulated-handler", "type": "simulated", "display_name": "Simulated Payment"},
        ],
    }
