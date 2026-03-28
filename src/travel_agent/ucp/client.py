from __future__ import annotations

import uuid
from typing import Any

import httpx

from travel_agent.ucp.models import (
    CatalogItem,
    CatalogSearchParams,
    CheckoutCreateRequest,
    CheckoutSession,
    CheckoutUpdateRequest,
    UCPDiscoveryProfile,
)


class UCPError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"UCP error {status_code}: {message}")


class UCPClient:
    """Low-level async HTTP client for UCP protocol endpoints."""

    AGENT_ID = "ai-travel-agent/0.1.0"

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.AsyncClient(timeout=timeout)

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        return {
            "UCP-Agent": self.AGENT_ID,
            "request-id": str(uuid.uuid4()),
            "idempotency-key": idempotency_key or str(uuid.uuid4()),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _get(self, url: str, params: dict | None = None) -> dict:
        response = await self._client.get(url, headers=self._headers(), params=params)
        if response.status_code >= 400:
            raise UCPError(response.status_code, response.text)
        return response.json()

    async def _post(self, url: str, body: dict, idempotency_key: str | None = None) -> dict:
        response = await self._client.post(
            url, json=body, headers=self._headers(idempotency_key)
        )
        if response.status_code >= 400:
            raise UCPError(response.status_code, response.text)
        return response.json()

    async def _put(self, url: str, body: dict) -> dict:
        response = await self._client.put(url, json=body, headers=self._headers())
        if response.status_code >= 400:
            raise UCPError(response.status_code, response.text)
        return response.json()

    async def _delete(self, url: str) -> dict:
        response = await self._client.delete(url, headers=self._headers())
        if response.status_code >= 400:
            raise UCPError(response.status_code, response.text)
        return response.json() if response.content else {}

    # --- Discovery ---

    async def discover(self, merchant_base_url: str) -> UCPDiscoveryProfile:
        url = merchant_base_url.rstrip("/") + "/.well-known/ucp"
        data = await self._get(url)
        return UCPDiscoveryProfile.model_validate(data)

    # --- Catalog ---

    async def search_catalog(
        self, catalog_url: str, params: CatalogSearchParams
    ) -> list[CatalogItem]:
        data = await self._get(catalog_url, params=params.model_dump(exclude_none=True))
        items = data.get("items", data) if isinstance(data, dict) else data
        return [CatalogItem.model_validate(item) for item in items]

    # --- Checkout ---

    async def create_checkout_session(
        self,
        checkout_url: str,
        request: CheckoutCreateRequest,
        idempotency_key: str | None = None,
    ) -> CheckoutSession:
        data = await self._post(
            checkout_url, request.model_dump(), idempotency_key=idempotency_key
        )
        return CheckoutSession.model_validate(data)

    async def get_checkout_session(
        self, checkout_url: str, session_id: str
    ) -> CheckoutSession:
        url = f"{checkout_url.rstrip('/')}/{session_id}"
        data = await self._get(url)
        return CheckoutSession.model_validate(data)

    async def update_checkout_session(
        self, checkout_url: str, session_id: str, request: CheckoutUpdateRequest
    ) -> CheckoutSession:
        url = f"{checkout_url.rstrip('/')}/{session_id}"
        data = await self._put(url, request.model_dump(exclude_none=True))
        return CheckoutSession.model_validate(data)

    async def complete_checkout_session(
        self,
        checkout_url: str,
        session_id: str,
        payment_data: dict[str, Any],
    ) -> CheckoutSession:
        url = f"{checkout_url.rstrip('/')}/{session_id}/complete"
        data = await self._post(url, payment_data)
        return CheckoutSession.model_validate(data)

    async def cancel_checkout_session(
        self, checkout_url: str, session_id: str
    ) -> dict:
        url = f"{checkout_url.rstrip('/')}/{session_id}"
        return await self._delete(url)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()
