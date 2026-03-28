from __future__ import annotations

from datetime import date

from travel_agent.travel.merchants import MerchantInfo, MerchantRegistry
from travel_agent.travel.models import (
    FlightDetails,
    GroundTransportDetails,
    HotelDetails,
    Money,
    SearchResult,
)
from travel_agent.ucp.client import UCPClient
from travel_agent.ucp.discovery import MerchantDiscovery
from travel_agent.ucp.models import CatalogSearchParams


class TravelSearchService:
    """Searches UCP-compliant merchants for travel options."""

    def __init__(
        self,
        client: UCPClient,
        discovery: MerchantDiscovery,
        registry: MerchantRegistry,
    ):
        self._client = client
        self._discovery = discovery
        self._registry = registry

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        cabin_class: str = "economy",
        adults: int = 1,
    ) -> list[SearchResult]:
        results = []
        merchants = self._registry.get_by_category("flights")

        for merchant in merchants:
            try:
                profile = await self._discovery.discover(merchant.url)
                catalog_url = self._discovery.get_catalog_url(profile)
                if not catalog_url:
                    continue

                params = CatalogSearchParams(
                    origin=origin,
                    destination=destination,
                    date=departure_date.isoformat(),
                    category="flights",
                )
                # Pass extra search params via query string
                import httpx
                response = await self._client._get(
                    catalog_url,
                    params={
                        "origin": origin,
                        "destination": destination,
                        "date": departure_date.isoformat(),
                        "cabin_class": cabin_class,
                        "adults": adults,
                    },
                )
                items = response.get("items", [])

                for item in items:
                    meta = item.get("metadata", {})
                    details = FlightDetails(
                        airline=meta.get("airline", ""),
                        flight_number=meta.get("flight_number", ""),
                        origin=meta.get("origin", origin),
                        destination=meta.get("destination", destination),
                        departure_datetime=_parse_flight_datetime(
                            departure_date, meta.get("departure_time", "00:00")
                        ),
                        arrival_datetime=_parse_flight_datetime(
                            departure_date, meta.get("arrival_time", "00:00")
                        ),
                        cabin_class=meta.get("cabin_class", cabin_class),
                        duration_minutes=meta.get("duration_minutes", 0),
                        is_refundable=meta.get("is_refundable", False),
                        baggage_included=meta.get("baggage_included", True),
                    )
                    results.append(
                        SearchResult(
                            merchant_url=merchant.url,
                            merchant_name=merchant.name,
                            segment_type="flight",
                            details=details,
                            cost=Money(amount_cents=item["price_cents"], currency="USD"),
                        )
                    )
            except Exception:
                continue

        return results

    async def search_hotels(
        self,
        city: str,
        check_in: date,
        check_out: date,
        room_type: str = "standard",
    ) -> list[SearchResult]:
        results = []
        merchants = self._registry.get_by_category("hotels")

        for merchant in merchants:
            try:
                profile = await self._discovery.discover(merchant.url)
                catalog_url = self._discovery.get_catalog_url(profile)
                if not catalog_url:
                    continue

                response = await self._client._get(
                    catalog_url,
                    params={
                        "city": city,
                        "check_in": check_in.isoformat(),
                        "check_out": check_out.isoformat(),
                        "room_type": room_type,
                    },
                )
                items = response.get("items", [])

                for item in items:
                    meta = item.get("metadata", {})
                    details = HotelDetails(
                        name=meta.get("hotel_name", item.get("name", "")),
                        chain=meta.get("chain"),
                        address=meta.get("address", ""),
                        city=meta.get("city", city),
                        star_rating=meta.get("star_rating", 3),
                        check_in_date=check_in,
                        check_out_date=check_out,
                        room_type=meta.get("room_type", room_type),
                        is_refundable=meta.get("is_refundable", False),
                    )
                    results.append(
                        SearchResult(
                            merchant_url=merchant.url,
                            merchant_name=merchant.name,
                            segment_type="hotel",
                            details=details,
                            cost=Money(amount_cents=item["price_cents"], currency="USD"),
                        )
                    )
            except Exception:
                continue

        return results

    async def search_ground_transport(
        self,
        pickup_location: str,
        dropoff_location: str,
        pickup_date: date,
        days: int = 1,
        transport_type: str | None = None,
    ) -> list[SearchResult]:
        results = []
        merchants = self._registry.get_by_category("ground_transport")

        for merchant in merchants:
            try:
                profile = await self._discovery.discover(merchant.url)
                catalog_url = self._discovery.get_catalog_url(profile)
                if not catalog_url:
                    continue

                params: dict = {
                    "pickup_location": pickup_location,
                    "dropoff_location": dropoff_location,
                    "pickup_date": pickup_date.isoformat(),
                    "days": days,
                }
                if transport_type:
                    params["transport_type"] = transport_type

                response = await self._client._get(catalog_url, params=params)
                items = response.get("items", [])

                for item in items:
                    meta = item.get("metadata", {})
                    from datetime import datetime, time
                    details = GroundTransportDetails(
                        provider=meta.get("provider", ""),
                        type=meta.get("type", "car_rental"),
                        pickup_location=pickup_location,
                        dropoff_location=dropoff_location,
                        pickup_datetime=datetime.combine(pickup_date, time(9, 0)),
                        vehicle_type=meta.get("vehicle_type"),
                        is_refundable=meta.get("is_refundable", False),
                    )
                    results.append(
                        SearchResult(
                            merchant_url=merchant.url,
                            merchant_name=merchant.name,
                            segment_type="ground_transport",
                            details=details,
                            cost=Money(amount_cents=item["price_cents"], currency="USD"),
                        )
                    )
            except Exception:
                continue

        return results


def _parse_flight_datetime(dep_date: date, time_str: str):
    from datetime import datetime
    hour, minute = map(int, time_str.split(":"))
    return datetime(dep_date.year, dep_date.month, dep_date.day, hour, minute)
