from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from travel_agent.escalation.models import (
    ApprovalDecision,
    EscalationRequest,
    EscalationStatus,
)


class EscalationHandler:
    """
    Manages human-in-the-loop approval requests.

    In this implementation, escalations are stored in memory and
    exposed via the REST API. In production, this would also send
    email/Slack notifications to approvers.
    """

    def __init__(self):
        self._escalations: dict[str, EscalationRequest] = {}

    async def request_approval(
        self,
        trip_id: str,
        reason: str,
        details: dict[str, Any],
        cart_mandate_json: dict | None = None,
    ) -> str:
        escalation = EscalationRequest(
            id=str(uuid.uuid4()),
            trip_id=trip_id,
            reason=reason,
            details=details,
            cart_mandate_json=cart_mandate_json,
            created_at=datetime.now(timezone.utc),
        )
        self._escalations[escalation.id] = escalation
        return escalation.id

    def get(self, escalation_id: str) -> EscalationRequest | None:
        return self._escalations.get(escalation_id)

    def get_by_trip(self, trip_id: str) -> list[EscalationRequest]:
        return [e for e in self._escalations.values() if e.trip_id == trip_id]

    def list_pending(self) -> list[EscalationRequest]:
        return [e for e in self._escalations.values() if e.status == EscalationStatus.PENDING]

    async def process_decision(
        self, escalation_id: str, decision: ApprovalDecision
    ) -> EscalationRequest | None:
        escalation = self._escalations.get(escalation_id)
        if not escalation:
            return None

        escalation.status = (
            EscalationStatus.APPROVED if decision.approved else EscalationStatus.REJECTED
        )
        escalation.approver_email = decision.approver_email
        escalation.decided_at = datetime.now(timezone.utc)
        return escalation

    async def check_status(self, escalation_id: str) -> EscalationStatus | None:
        escalation = self._escalations.get(escalation_id)
        return escalation.status if escalation else None
