from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class MandateType(str, Enum):
    INTENT = "intent"
    CART = "cart"
    PAYMENT = "payment"


class PaymentItem(BaseModel):
    label: str
    amount_cents: int
    currency: str = "USD"


class PaymentDetailsInit(BaseModel):
    """Mirrors the W3C PaymentDetailsInit structure used in AP2."""
    total: PaymentItem
    display_items: list[PaymentItem] = []
    modifiers: list[dict[str, Any]] = []


class IntentMandate(BaseModel):
    """
    AP2 Intent Mandate — authorizes autonomous purchasing within stated conditions.
    Created when a trip is within policy. Allows the agent to act without real-time
    human approval as long as conditions are satisfied.
    """
    id: str
    type: MandateType = MandateType.INTENT
    natural_language_description: str
    max_amount_cents: int
    currency: str = "USD"
    allowed_merchant_ids: list[str] = []  # Empty = any merchant
    allowed_categories: list[str] = []   # e.g. ["flights", "hotels"]
    intent_expiry: datetime
    user_cart_confirmation_required: bool = False
    created_at: datetime
    issuer: str = "ai-travel-agent"


class CartContents(BaseModel):
    """Contents of a shopping cart to be presented for human approval."""
    items: list[PaymentItem]
    total: PaymentItem
    merchant_id: str
    merchant_name: str
    checkout_session_id: str
    payment_request: PaymentDetailsInit


class CartMandate(BaseModel):
    """
    AP2 Cart Mandate — requires explicit human approval of exact cart contents.
    Used when a trip exceeds policy thresholds or when merchant requires it.
    """
    id: str
    type: MandateType = MandateType.CART
    cart_contents: CartContents
    merchant_authorization: str | None = None  # Merchant's JWT signature over cart
    requires_human_approval: bool = True
    created_at: datetime


class PaymentResponse(BaseModel):
    """Payment method details selected for this transaction."""
    method_name: str  # e.g. "ap2", "basic-card"
    details: dict[str, Any]  # Payment method specific data


class PaymentMandate(BaseModel):
    """
    AP2 Payment Mandate — the final mandate submitted to the payment network.
    Contains the total, payment method, and cryptographic user authorization.
    """
    id: str
    type: MandateType = MandateType.PAYMENT
    payment_details_total: PaymentItem
    payment_response: PaymentResponse
    merchant_id: str
    checkout_session_id: str
    user_authorization: str | None = None  # VDC-signed JWT (set after signing)
    modality: str = "human_not_present"  # or "human_present"
    created_at: datetime


class PaymentStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    FAILURE = "failure"


class PaymentReceipt(BaseModel):
    """Receipt returned after payment execution."""
    mandate_id: str
    merchant_confirmation_id: str
    amount_cents: int
    currency: str
    status: PaymentStatus
    timestamp: datetime
    raw_response: dict[str, Any] = {}
