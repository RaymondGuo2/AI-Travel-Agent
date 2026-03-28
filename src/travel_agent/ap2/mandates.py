from __future__ import annotations

import uuid
from datetime import datetime, timezone

from travel_agent.ap2.models import (
    CartContents,
    CartMandate,
    IntentMandate,
    PaymentDetailsInit,
    PaymentItem,
    PaymentMandate,
    PaymentResponse,
)
from travel_agent.travel.models import TripRequest


class MandateManager:
    """Creates and manages AP2 mandates for travel bookings."""

    def create_intent_mandate(
        self,
        request: TripRequest,
        max_amount_cents: int,
        currency: str = "USD",
        allowed_merchant_ids: list[str] | None = None,
        expiry: datetime | None = None,
    ) -> IntentMandate:
        """
        Create an Intent Mandate for a pre-approved autonomous trip.
        The agent can purchase within the stated conditions without real-time human approval.
        """
        if expiry is None:
            # Default: expires at departure date
            expiry = datetime(
                request.departure_date.year,
                request.departure_date.month,
                request.departure_date.day,
                23, 59, 59,
                tzinfo=timezone.utc,
            )

        return IntentMandate(
            id=str(uuid.uuid4()),
            natural_language_description=(
                f"Book business travel for {request.traveler_name}: "
                f"{request.origin} to {request.destination} on {request.departure_date} "
                f"for purpose: {request.purpose}"
            ),
            max_amount_cents=max_amount_cents,
            currency=currency,
            allowed_merchant_ids=allowed_merchant_ids or [],
            allowed_categories=self._categories_for_request(request),
            intent_expiry=expiry,
            user_cart_confirmation_required=False,
            created_at=datetime.now(timezone.utc),
        )

    def _categories_for_request(self, request: TripRequest) -> list[str]:
        categories = ["flights"]
        if request.needs_hotel:
            categories.append("hotels")
        if request.needs_ground_transport:
            categories.append("ground_transport")
        return categories

    def create_cart_mandate(
        self,
        checkout_session_id: str,
        merchant_id: str,
        merchant_name: str,
        items: list[PaymentItem],
        total: PaymentItem,
        merchant_authorization: str | None = None,
    ) -> CartMandate:
        """
        Create a Cart Mandate for human approval.
        Used when a trip exceeds policy thresholds.
        """
        cart = CartContents(
            items=items,
            total=total,
            merchant_id=merchant_id,
            merchant_name=merchant_name,
            checkout_session_id=checkout_session_id,
            payment_request=PaymentDetailsInit(
                total=total,
                display_items=items,
            ),
        )
        return CartMandate(
            id=str(uuid.uuid4()),
            cart_contents=cart,
            merchant_authorization=merchant_authorization,
            requires_human_approval=True,
            created_at=datetime.now(timezone.utc),
        )

    def create_payment_mandate(
        self,
        checkout_session_id: str,
        merchant_id: str,
        total_cents: int,
        currency: str,
        payment_method: str = "simulated",
        modality: str = "human_not_present",
    ) -> PaymentMandate:
        """
        Create the final Payment Mandate to submit to the payment network.
        This is always the last step before checkout completion.
        """
        return PaymentMandate(
            id=str(uuid.uuid4()),
            payment_details_total=PaymentItem(
                label="Total",
                amount_cents=total_cents,
                currency=currency,
            ),
            payment_response=PaymentResponse(
                method_name=payment_method,
                details={"simulated": True},
            ),
            merchant_id=merchant_id,
            checkout_session_id=checkout_session_id,
            modality=modality,
            created_at=datetime.now(timezone.utc),
        )
