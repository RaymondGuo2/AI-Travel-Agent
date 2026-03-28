from __future__ import annotations

import time
from typing import TYPE_CHECKING

from travel_agent.ucp.models import UCPDiscoveryProfile

if TYPE_CHECKING:
    from travel_agent.ucp.client import UCPClient

CACHE_TTL_SECONDS = 300  # 5 minutes


class MerchantDiscovery:
    """Fetches and caches UCP discovery profiles for merchants."""

    def __init__(self, client: UCPClient):
        self._client = client
        self._cache: dict[str, tuple[UCPDiscoveryProfile, float]] = {}

    async def discover(self, merchant_url: str, force_refresh: bool = False) -> UCPDiscoveryProfile:
        now = time.monotonic()
        if not force_refresh and merchant_url in self._cache:
            profile, cached_at = self._cache[merchant_url]
            if now - cached_at < CACHE_TTL_SECONDS:
                return profile

        profile = await self._client.discover(merchant_url)
        self._cache[merchant_url] = (profile, now)
        return profile

    def invalidate(self, merchant_url: str) -> None:
        self._cache.pop(merchant_url, None)

    def has_capability(self, profile: UCPDiscoveryProfile, capability: str) -> bool:
        return capability in profile.capabilities

    def supports_checkout(self, profile: UCPDiscoveryProfile) -> bool:
        return "checkout" in profile.capabilities or bool(profile.services)

    def get_checkout_url(self, profile: UCPDiscoveryProfile) -> str | None:
        service = profile.services.get("dev.ucp.shopping") or next(
            iter(profile.services.values()), None
        )
        return service.checkout_url if service else None

    def get_catalog_url(self, profile: UCPDiscoveryProfile) -> str | None:
        service = profile.services.get("dev.ucp.shopping") or next(
            iter(profile.services.values()), None
        )
        return service.catalog_url if service else None

    def get_ap2_payment_handler(self, profile: UCPDiscoveryProfile) -> str | None:
        for handler in profile.payment_handlers:
            if handler.type == "ap2":
                return handler.id
        return None
