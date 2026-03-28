from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class EscalationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class EscalationRequest(BaseModel):
    id: str
    trip_id: str
    reason: str
    details: dict[str, Any]
    cart_mandate_json: dict | None = None
    status: EscalationStatus = EscalationStatus.PENDING
    approver_email: str | None = None
    decided_at: datetime | None = None
    created_at: datetime


class ApprovalDecision(BaseModel):
    approved: bool
    approver_email: str | None = None
    notes: str | None = None
