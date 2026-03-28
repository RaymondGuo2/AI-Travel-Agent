from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MerchantInfo:
    url: str
    name: str
    category: str  # flights | hotels | ground_transport
    merchant_id: str


class MerchantRegistry:
    """Registry of known UCP-compliant travel merchants."""

    def __init__(self, merchant_configs: dict | None = None):
        self._merchants: list[MerchantInfo] = []
        if merchant_configs:
            self._load_from_config(merchant_configs)

    def _load_from_config(self, config: dict) -> None:
        for category in ("flight", "hotel", "ground_transport"):
            info = config.get(category)
            if info:
                self._merchants.append(
                    MerchantInfo(
                        url=info["url"],
                        name=info["name"],
                        category=category if category != "flight" else "flights",
                        merchant_id=info["url"].split("//")[-1].split(":")[0],
                    )
                )

    def register(self, merchant: MerchantInfo) -> None:
        self._merchants.append(merchant)

    def get_by_category(self, category: str) -> list[MerchantInfo]:
        # Normalize: "flight" -> "flights"
        norm = category if category.endswith("s") else category + "s"
        return [m for m in self._merchants if m.category == norm or m.category == category]

    def all(self) -> list[MerchantInfo]:
        return list(self._merchants)
