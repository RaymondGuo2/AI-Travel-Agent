from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


# --- UCP Discovery ---

class UCPService(BaseModel):
    checkout_url: str
    catalog_url: str | None = None
    orders_url: str | None = None


class UCPPaymentHandler(BaseModel):
    id: str
    type: str  # e.g. "ap2", "card", "paypal"
    display_name: str | None = None


class UCPDiscoveryProfile(BaseModel):
    version: str
    merchant_id: str
    merchant_name: str
    services: dict[str, UCPService] = {}
    capabilities: list[str] = []
    payment_handlers: list[UCPPaymentHandler] = []
    webhook_url: str | None = None  # Where merchant will send order updates


# --- UCP Checkout ---

class LineItem(BaseModel):
    id: str
    name: str
    description: str | None = None
    quantity: int = 1
    unit_price_cents: int
    currency: str = "USD"
    metadata: dict[str, Any] = {}


class CheckoutTotals(BaseModel):
    subtotal_cents: int
    tax_cents: int = 0
    fees_cents: int = 0
    total_cents: int
    currency: str = "USD"

    @property
    def total(self) -> float:
        return self.total_cents / 100


class CheckoutStatus(str, Enum):
    INCOMPLETE = "incomplete"
    REQUIRES_ESCALATION = "requires_escalation"
    READY_FOR_COMPLETE = "ready_for_complete"
    COMPLETE_IN_PROGRESS = "complete_in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"


class EscalationReason(BaseModel):
    code: str
    message: str
    continue_url: str | None = None  # Redirect user here for manual action


class CheckoutSession(BaseModel):
    id: str
    merchant_id: str
    status: CheckoutStatus
    line_items: list[LineItem] = []
    totals: CheckoutTotals | None = None
    buyer_name: str | None = None
    buyer_email: str | None = None
    payment_handler_id: str | None = None
    order_id: str | None = None  # Set when completed
    escalation_reason: EscalationReason | None = None
    metadata: dict[str, Any] = {}


class CheckoutCreateRequest(BaseModel):
    line_items: list[LineItem]
    buyer_name: str
    buyer_email: str
    currency: str = "USD"
    payment_handler_id: str | None = None
    webhook_url: str | None = None
    metadata: dict[str, Any] = {}


class CheckoutUpdateRequest(BaseModel):
    buyer_name: str | None = None
    buyer_email: str | None = None
    payment_handler_id: str | None = None
    metadata: dict[str, Any] | None = None


# --- UCP Orders ---

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    FULFILLED = "fulfilled"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class OrderEvent(BaseModel):
    order_id: str
    merchant_id: str
    checkout_session_id: str
    status: OrderStatus
    details: dict[str, Any] = {}
    timestamp: str


# --- UCP Catalog ---

class CatalogSearchParams(BaseModel):
    query: str | None = None
    category: str | None = None
    origin: str | None = None
    destination: str | None = None
    date: str | None = None
    return_date: str | None = None
    adults: int = 1
    max_results: int = 10


class CatalogItem(BaseModel):
    id: str
    name: str
    description: str | None = None
    category: str
    price_cents: int
    currency: str = "USD"
    availability: bool = True
    metadata: dict[str, Any] = {}
