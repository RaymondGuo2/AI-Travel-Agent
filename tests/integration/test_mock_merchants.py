"""
Integration tests using the mock merchant servers.
These tests spin up the mock FastAPI apps in-process using httpx.AsyncClient.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def flight_app():
    from mock_merchants.flight_merchant import app
    return app


@pytest.fixture
def hotel_app():
    from mock_merchants.hotel_merchant import app
    return app


@pytest.fixture
def transport_app():
    from mock_merchants.transport_merchant import app
    return app


class TestFlightMerchantUCP:
    async def test_discovery_returns_profile(self, flight_app):
        async with AsyncClient(transport=ASGITransport(app=flight_app), base_url="http://test") as client:
            r = await client.get("/.well-known/ucp")
            assert r.status_code == 200
            data = r.json()
            assert data["merchant_id"] == "skyway-airlines"
            assert "checkout" in data["capabilities"]
            assert "dev.ucp.shopping" in data["services"]

    async def test_catalog_search_sfo_jfk(self, flight_app):
        async with AsyncClient(transport=ASGITransport(app=flight_app), base_url="http://test") as client:
            r = await client.get("/catalog", params={"origin": "SFO", "destination": "JFK", "cabin_class": "economy"})
            assert r.status_code == 200
            items = r.json()["items"]
            assert len(items) >= 1
            assert all(i["category"] == "flights" for i in items)

    async def test_catalog_filters_by_origin(self, flight_app):
        async with AsyncClient(transport=ASGITransport(app=flight_app), base_url="http://test") as client:
            r = await client.get("/catalog", params={"origin": "LAX", "destination": "ORD"})
            assert r.status_code == 200
            items = r.json()["items"]
            assert all(i["metadata"]["origin"] == "LAX" for i in items)

    async def test_checkout_lifecycle(self, flight_app):
        async with AsyncClient(transport=ASGITransport(app=flight_app), base_url="http://test") as client:
            # 1. Create session
            r = await client.post("/checkout-sessions", json={
                "line_items": [{"id": "FL001", "name": "UA 415 Economy", "unit_price_cents": 45000, "quantity": 1}],
                "buyer_name": "Alice Smith",
                "buyer_email": "alice@company.com",
            })
            assert r.status_code == 200
            session = r.json()
            assert session["status"] == "ready_for_complete"
            session_id = session["id"]

            # 2. Complete
            r = await client.post(f"/checkout-sessions/{session_id}/complete", json={
                "payment_mandate_id": "mandate-123",
                "payment_method": "simulated",
                "amount_cents": 45000,
            })
            assert r.status_code == 200
            completed = r.json()
            assert completed["status"] == "completed"
            assert completed["order_id"] is not None

    async def test_checkout_cancel(self, flight_app):
        async with AsyncClient(transport=ASGITransport(app=flight_app), base_url="http://test") as client:
            r = await client.post("/checkout-sessions", json={
                "line_items": [{"id": "FL001", "name": "UA 415", "unit_price_cents": 45000, "quantity": 1}],
                "buyer_name": "Bob",
                "buyer_email": "bob@co.com",
            })
            session_id = r.json()["id"]
            r = await client.delete(f"/checkout-sessions/{session_id}")
            assert r.status_code == 200


class TestHotelMerchantUCP:
    async def test_discovery(self, hotel_app):
        async with AsyncClient(transport=ASGITransport(app=hotel_app), base_url="http://test") as client:
            r = await client.get("/.well-known/ucp")
            assert r.status_code == 200
            data = r.json()
            assert "hotels" in data["capabilities"]

    async def test_catalog_search_by_city(self, hotel_app):
        async with AsyncClient(transport=ASGITransport(app=hotel_app), base_url="http://test") as client:
            r = await client.get("/catalog", params={
                "city": "New York",
                "check_in": "2026-06-15",
                "check_out": "2026-06-18",
            })
            assert r.status_code == 200
            items = r.json()["items"]
            assert len(items) >= 1
            assert all(i["metadata"]["city"] == "New York" for i in items)

    async def test_nightly_rate_calculated_correctly(self, hotel_app):
        async with AsyncClient(transport=ASGITransport(app=hotel_app), base_url="http://test") as client:
            r = await client.get("/catalog", params={
                "city": "New York",
                "check_in": "2026-06-15",
                "check_out": "2026-06-18",
                "room_type": "standard",
            })
            items = r.json()["items"]
            # 3 nights * standard rate
            for item in items:
                meta = item["metadata"]
                if meta["hotel_name"] == "Marriott Marquis":
                    assert meta["nights"] == 3
                    assert item["price_cents"] == meta["price_per_night_cents"] * 3


class TestTransportMerchantUCP:
    async def test_discovery(self, transport_app):
        async with AsyncClient(transport=ASGITransport(app=transport_app), base_url="http://test") as client:
            r = await client.get("/.well-known/ucp")
            assert r.status_code == 200
            data = r.json()
            assert "ground_transport" in data["capabilities"]

    async def test_catalog_car_rental(self, transport_app):
        async with AsyncClient(transport=ASGITransport(app=transport_app), base_url="http://test") as client:
            r = await client.get("/catalog", params={
                "pickup_location": "JFK Airport",
                "dropoff_location": "Manhattan",
                "pickup_date": "2026-06-15",
                "days": 3,
                "transport_type": "car_rental",
            })
            assert r.status_code == 200
            items = r.json()["items"]
            assert all(i["metadata"]["type"] == "car_rental" for i in items)
