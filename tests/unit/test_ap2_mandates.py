from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

import pytest

from travel_agent.ap2.mandates import MandateManager
from travel_agent.ap2.models import MandateType, PaymentStatus
from travel_agent.ap2.signing import VDCSigner
from travel_agent.travel.models import TripRequest


@pytest.fixture
def mandate_manager():
    return MandateManager()


@pytest.fixture
def signer(tmp_path):
    return VDCSigner(key_path=tmp_path / "test_key.pem")


@pytest.fixture
def trip_request():
    return TripRequest(
        traveler_name="Alice",
        traveler_email="alice@company.com",
        origin="SFO",
        destination="JFK",
        departure_date=date(2026, 8, 15),
        purpose="conference",
    )


class TestIntentMandate:
    def test_creates_with_correct_type(self, mandate_manager, trip_request):
        mandate = mandate_manager.create_intent_mandate(
            request=trip_request,
            max_amount_cents=500000,
        )
        assert mandate.type == MandateType.INTENT
        assert mandate.max_amount_cents == 500000
        assert not mandate.user_cart_confirmation_required

    def test_description_contains_trip_details(self, mandate_manager, trip_request):
        mandate = mandate_manager.create_intent_mandate(
            request=trip_request,
            max_amount_cents=300000,
        )
        assert "SFO" in mandate.natural_language_description
        assert "JFK" in mandate.natural_language_description
        assert "Alice" in mandate.natural_language_description

    def test_expiry_set_to_departure_date(self, mandate_manager, trip_request):
        mandate = mandate_manager.create_intent_mandate(
            request=trip_request,
            max_amount_cents=300000,
        )
        assert mandate.intent_expiry.date() == trip_request.departure_date

    def test_categories_include_flight(self, mandate_manager, trip_request):
        mandate = mandate_manager.create_intent_mandate(
            request=trip_request,
            max_amount_cents=300000,
        )
        assert "flights" in mandate.allowed_categories

    def test_categories_include_hotel_when_needed(self, mandate_manager, trip_request):
        trip_request.needs_hotel = True
        mandate = mandate_manager.create_intent_mandate(
            request=trip_request,
            max_amount_cents=300000,
        )
        assert "hotels" in mandate.allowed_categories


class TestCartMandate:
    def test_creates_with_correct_type(self, mandate_manager):
        from travel_agent.ap2.models import PaymentItem
        items = [PaymentItem(label="Flight UA 415", amount_cents=45000)]
        total = PaymentItem(label="Total", amount_cents=45000)
        mandate = mandate_manager.create_cart_mandate(
            checkout_session_id="sess-123",
            merchant_id="skyway",
            merchant_name="SkyWay Airlines",
            items=items,
            total=total,
        )
        assert mandate.type == MandateType.CART
        assert mandate.requires_human_approval
        assert mandate.cart_contents.checkout_session_id == "sess-123"


class TestPaymentMandate:
    def test_creates_with_correct_fields(self, mandate_manager):
        mandate = mandate_manager.create_payment_mandate(
            checkout_session_id="sess-456",
            merchant_id="skyway",
            total_cents=48600,
            currency="USD",
        )
        assert mandate.type == MandateType.PAYMENT
        assert mandate.payment_details_total.amount_cents == 48600
        assert mandate.checkout_session_id == "sess-456"
        assert mandate.user_authorization is None  # Not signed yet

    def test_modality_human_not_present_by_default(self, mandate_manager):
        mandate = mandate_manager.create_payment_mandate(
            checkout_session_id="sess-789",
            merchant_id="skyway",
            total_cents=50000,
            currency="USD",
        )
        assert mandate.modality == "human_not_present"


class TestVDCSigning:
    def test_sign_and_verify(self, signer):
        token = signer.sign({"sub": "test-mandate-id", "type": "payment_mandate_authorization"})
        assert isinstance(token, str)
        payload = signer.verify(token)
        assert payload["sub"] == "test-mandate-id"

    def test_sign_payment_mandate(self, signer):
        token = signer.sign_payment_mandate(
            mandate_id="mandate-123",
            total_cents=50000,
            currency="USD",
            merchant_id="skyway",
        )
        payload = signer.verify(token)
        assert payload["sub"] == "mandate-123"
        assert payload["total_cents"] == 50000
        assert payload["merchant_id"] == "skyway"

    def test_tampered_token_fails(self, signer):
        import jwt
        token = signer.sign({"sub": "test"})
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(Exception):
            signer.verify(tampered)
