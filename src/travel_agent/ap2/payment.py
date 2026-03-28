from __future__ import annotations

from datetime import datetime, timezone

from travel_agent.ap2.mandates import MandateManager
from travel_agent.ap2.models import (
    CartMandate,
    IntentMandate,
    PaymentItem,
    PaymentMandate,
    PaymentReceipt,
    PaymentStatus,
)
from travel_agent.ap2.signing import VDCSigner
from travel_agent.ucp.models import CheckoutSession


class PaymentError(Exception):
    pass


class PaymentOrchestrator:
    """
    Coordinates the full AP2 payment flow.

    Intent Mandate path (autonomous):
      - Verify intent mandate conditions are satisfied
      - Create Payment Mandate
      - Sign with VDC
      - Simulate payment network authorization
      - Return receipt

    Cart Mandate path (human-approved):
      - Cart mandate already approved by human
      - Create Payment Mandate from approved cart
      - Sign with VDC
      - Simulate payment network authorization
      - Return receipt
    """

    def __init__(self, signer: VDCSigner, mandate_manager: MandateManager):
        self._signer = signer
        self._mandate_manager = mandate_manager

    def _verify_intent_mandate(
        self, intent: IntentMandate, total_cents: int, merchant_id: str
    ) -> None:
        now = datetime.now(timezone.utc)
        if now > intent.intent_expiry:
            raise PaymentError(f"Intent mandate {intent.id} has expired")

        if total_cents > intent.max_amount_cents:
            raise PaymentError(
                f"Total {total_cents} exceeds intent mandate limit {intent.max_amount_cents}"
            )

        if intent.allowed_merchant_ids and merchant_id not in intent.allowed_merchant_ids:
            raise PaymentError(
                f"Merchant {merchant_id!r} is not in intent mandate allowed list"
            )

    async def pay_with_intent_mandate(
        self,
        checkout_session: CheckoutSession,
        intent_mandate: IntentMandate,
    ) -> tuple[PaymentMandate, PaymentReceipt]:
        """Execute payment using a pre-approved Intent Mandate (no human needed)."""
        if not checkout_session.totals:
            raise PaymentError("Checkout session has no totals; cannot determine payment amount")

        total_cents = checkout_session.totals.total_cents
        self._verify_intent_mandate(intent_mandate, total_cents, checkout_session.merchant_id)

        mandate = self._mandate_manager.create_payment_mandate(
            checkout_session_id=checkout_session.id,
            merchant_id=checkout_session.merchant_id,
            total_cents=total_cents,
            currency=checkout_session.totals.currency,
            modality="human_not_present",
        )

        mandate.user_authorization = self._signer.sign_payment_mandate(
            mandate_id=mandate.id,
            total_cents=total_cents,
            currency=mandate.payment_details_total.currency,
            merchant_id=mandate.merchant_id,
        )

        receipt = self._simulate_payment(mandate)
        return mandate, receipt

    async def pay_with_cart_mandate(
        self,
        checkout_session: CheckoutSession,
        cart_mandate: CartMandate,
    ) -> tuple[PaymentMandate, PaymentReceipt]:
        """Execute payment after a human has approved a Cart Mandate."""
        if not checkout_session.totals:
            raise PaymentError("Checkout session has no totals")

        total_cents = checkout_session.totals.total_cents
        mandate = self._mandate_manager.create_payment_mandate(
            checkout_session_id=checkout_session.id,
            merchant_id=checkout_session.merchant_id,
            total_cents=total_cents,
            currency=checkout_session.totals.currency,
            modality="human_present",
        )

        mandate.user_authorization = self._signer.sign_payment_mandate(
            mandate_id=mandate.id,
            total_cents=total_cents,
            currency=mandate.payment_details_total.currency,
            merchant_id=mandate.merchant_id,
        )

        receipt = self._simulate_payment(mandate)
        return mandate, receipt

    def _simulate_payment(self, mandate: PaymentMandate) -> PaymentReceipt:
        """
        Simulate payment network authorization.
        In production, this submits the mandate to the AP2-compatible payment handler.
        """
        return PaymentReceipt(
            mandate_id=mandate.id,
            merchant_confirmation_id=f"CONF-{mandate.checkout_session_id[:8].upper()}",
            amount_cents=mandate.payment_details_total.amount_cents,
            currency=mandate.payment_details_total.currency,
            status=PaymentStatus.SUCCESS,
            timestamp=datetime.now(timezone.utc),
            raw_response={"simulated": True, "mandate_id": mandate.id},
        )

    def build_payment_data(self, mandate: PaymentMandate) -> dict:
        """Build the payment_data dict to pass to UCP complete_checkout_session."""
        return {
            "payment_mandate_id": mandate.id,
            "payment_method": mandate.payment_response.method_name,
            "user_authorization": mandate.user_authorization,
            "amount_cents": mandate.payment_details_total.amount_cents,
            "currency": mandate.payment_details_total.currency,
        }
