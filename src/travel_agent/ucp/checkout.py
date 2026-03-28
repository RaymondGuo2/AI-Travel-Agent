from __future__ import annotations

import asyncio
import uuid
from typing import Any

from travel_agent.ucp.client import UCPClient, UCPError
from travel_agent.ucp.discovery import MerchantDiscovery
from travel_agent.ucp.models import (
    CheckoutCreateRequest,
    CheckoutSession,
    CheckoutStatus,
    CheckoutUpdateRequest,
    LineItem,
)


class CheckoutError(Exception):
    pass


class CheckoutEscalationRequired(Exception):
    def __init__(self, session: CheckoutSession):
        self.session = session
        reason = session.escalation_reason
        msg = reason.message if reason else "Merchant requires human action"
        super().__init__(msg)


class CheckoutManager:
    """Manages the full UCP checkout session lifecycle."""

    def __init__(self, client: UCPClient, discovery: MerchantDiscovery, webhook_base_url: str = ""):
        self._client = client
        self._discovery = discovery
        self._webhook_base_url = webhook_base_url

    async def create_and_populate(
        self,
        merchant_url: str,
        items: list[LineItem],
        buyer_name: str,
        buyer_email: str,
        currency: str = "USD",
    ) -> CheckoutSession:
        """Create a checkout session and add traveler details."""
        profile = await self._discovery.discover(merchant_url)
        checkout_url = self._discovery.get_checkout_url(profile)
        if not checkout_url:
            raise CheckoutError(f"Merchant {merchant_url} does not support checkout")

        payment_handler_id = self._discovery.get_ap2_payment_handler(profile)
        webhook_url = (
            f"{self._webhook_base_url}/ucp/orders" if self._webhook_base_url else None
        )

        request = CheckoutCreateRequest(
            line_items=items,
            buyer_name=buyer_name,
            buyer_email=buyer_email,
            currency=currency,
            payment_handler_id=payment_handler_id,
            webhook_url=webhook_url,
        )

        idempotency_key = str(uuid.uuid4())
        session = await self._client.create_checkout_session(
            checkout_url, request, idempotency_key=idempotency_key
        )

        if session.status == CheckoutStatus.REQUIRES_ESCALATION:
            raise CheckoutEscalationRequired(session)

        return session

    async def wait_for_ready(
        self,
        checkout_url: str,
        session_id: str,
        max_polls: int = 10,
        poll_interval: float = 1.0,
    ) -> CheckoutSession:
        """Poll until the session is ready_for_complete or terminal."""
        for _ in range(max_polls):
            session = await self._client.get_checkout_session(checkout_url, session_id)

            if session.status == CheckoutStatus.READY_FOR_COMPLETE:
                return session
            if session.status == CheckoutStatus.REQUIRES_ESCALATION:
                raise CheckoutEscalationRequired(session)
            if session.status in (CheckoutStatus.COMPLETED, CheckoutStatus.CANCELED):
                raise CheckoutError(f"Session ended unexpectedly with status: {session.status}")

            await asyncio.sleep(poll_interval)

        raise CheckoutError("Checkout session did not reach ready_for_complete in time")

    async def complete(
        self,
        merchant_url: str,
        session_id: str,
        payment_data: dict[str, Any],
    ) -> CheckoutSession:
        """Complete a checkout session with payment."""
        profile = await self._discovery.discover(merchant_url)
        checkout_url = self._discovery.get_checkout_url(profile)
        if not checkout_url:
            raise CheckoutError(f"Merchant {merchant_url} does not have a checkout URL")

        session = await self._client.complete_checkout_session(
            checkout_url, session_id, payment_data
        )

        if session.status not in (
            CheckoutStatus.COMPLETE_IN_PROGRESS,
            CheckoutStatus.COMPLETED,
        ):
            raise CheckoutError(f"Unexpected status after completion: {session.status}")

        return session

    async def cancel(self, merchant_url: str, session_id: str) -> None:
        """Cancel a checkout session."""
        profile = await self._discovery.discover(merchant_url)
        checkout_url = self._discovery.get_checkout_url(profile)
        if checkout_url:
            try:
                await self._client.cancel_checkout_session(checkout_url, session_id)
            except UCPError:
                pass  # Best-effort cancellation
