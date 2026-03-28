from __future__ import annotations

from datetime import date, datetime

import pytest

from travel_agent.policy.models import CompanyPolicy, FlightPolicy, TripPolicy
from travel_agent.policy.engine import PolicyEngine
from travel_agent.travel.models import (
    FlightDetails,
    HotelDetails,
    Money,
    TripPlan,
    TripRequest,
    TripSegment,
)


@pytest.fixture
def engine(policy_engine):
    return policy_engine


class TestFlightPolicy:
    def test_preferred_airline_passes(self, engine, sample_flight):
        result = engine.evaluate_flight(sample_flight)
        assert result.passed

    def test_non_preferred_airline_fails(self, engine, sample_flight):
        sample_flight.airline = "WN"
        result = engine.evaluate_flight(sample_flight)
        assert not result.passed
        assert any(v.field == "airline" for v in result.violations)

    def test_economy_cabin_passes(self, engine, sample_flight):
        result = engine.evaluate_flight(sample_flight)
        assert result.passed

    def test_business_cabin_fails(self, engine, sample_flight):
        sample_flight.cabin_class = "business"
        result = engine.evaluate_flight(sample_flight)
        assert not result.passed
        assert any(v.field == "cabin_class" for v in result.violations)

    def test_premium_economy_passes(self, engine, sample_flight):
        sample_flight.cabin_class = "premium_economy"
        result = engine.evaluate_flight(sample_flight)
        assert result.passed


class TestHotelPolicy:
    def test_valid_hotel_passes(self, engine, sample_hotel):
        result = engine.evaluate_hotel(sample_hotel)
        assert result.passed

    def test_low_star_rating_fails(self, engine, sample_hotel):
        sample_hotel.star_rating = 2
        result = engine.evaluate_hotel(sample_hotel)
        assert not result.passed
        assert any(v.field == "star_rating" for v in result.violations)

    def test_non_preferred_chain_flagged(self, engine, sample_hotel):
        sample_hotel.chain = "Best Western"
        result = engine.evaluate_hotel(sample_hotel)
        assert not result.passed


class TestCostLimits:
    def test_flight_within_limit_passes(self, engine, sample_request, sample_flight):
        segment = TripSegment(
            segment_type="flight",
            merchant_url="http://localhost:8001",
            merchant_name="Test",
            details=sample_flight,
            cost=Money.from_float(800.00),
        )
        result = engine.evaluate_segment_cost(segment)
        assert result.passed

    def test_flight_over_limit_fails(self, engine, sample_request, sample_flight):
        segment = TripSegment(
            segment_type="flight",
            merchant_url="http://localhost:8001",
            merchant_name="Test",
            details=sample_flight,
            cost=Money.from_float(2000.00),
        )
        result = engine.evaluate_segment_cost(segment)
        assert not result.passed
        assert any(v.field == "cost" for v in result.violations)

    def test_hotel_per_night_over_limit_fails(self, engine, sample_hotel):
        segment = TripSegment(
            segment_type="hotel",
            merchant_url="http://localhost:8002",
            merchant_name="Test",
            details=sample_hotel,
            cost=Money.from_float(1200.00),  # 3 nights * $400/night > $250 limit
        )
        result = engine.evaluate_segment_cost(segment)
        assert not result.passed


class TestTripTotalPolicy:
    def _make_plan(self, request, segments):
        plan = TripPlan(request=request, segments=segments)
        plan.recalculate_total()
        return plan

    def test_trip_under_threshold_no_approval_needed(
        self, engine, sample_request, sample_flight, sample_hotel
    ):
        from datetime import datetime
        flight_seg = TripSegment(
            segment_type="flight",
            merchant_url="http://localhost:8001",
            merchant_name="Test",
            details=sample_flight,
            cost=Money.from_float(500.00),
        )
        hotel_seg = TripSegment(
            segment_type="hotel",
            merchant_url="http://localhost:8002",
            merchant_name="Test",
            details=sample_hotel,
            cost=Money.from_float(600.00),
        )
        plan = self._make_plan(sample_request, [flight_seg, hotel_seg])
        result = engine.evaluate_trip_total(plan)
        assert not result.requires_approval

    def test_trip_over_threshold_requires_approval(
        self, engine, sample_request, sample_flight, sample_hotel
    ):
        flight_seg = TripSegment(
            segment_type="flight",
            merchant_url="http://localhost:8001",
            merchant_name="Test",
            details=sample_flight,
            cost=Money.from_float(1400.00),
        )
        hotel_seg = TripSegment(
            segment_type="hotel",
            merchant_url="http://localhost:8002",
            merchant_name="Test",
            details=sample_hotel,
            cost=Money.from_float(1800.00),
        )
        plan = self._make_plan(sample_request, [flight_seg, hotel_seg])
        result = engine.evaluate_trip_total(plan)
        assert result.requires_approval
        assert result.approval_reason is not None


class TestAdvanceBooking:
    def test_advance_booking_sufficient_passes(self, engine):
        from datetime import date, timedelta
        request = TripRequest(
            traveler_name="Bob",
            traveler_email="bob@co.com",
            origin="SFO",
            destination="LAX",
            departure_date=date.today() + timedelta(days=14),
            purpose="meeting",
        )
        result = engine.evaluate_request(request)
        assert result.passed

    def test_advance_booking_insufficient_fails(self, engine):
        from datetime import date, timedelta
        request = TripRequest(
            traveler_name="Bob",
            traveler_email="bob@co.com",
            origin="SFO",
            destination="LAX",
            departure_date=date.today() + timedelta(days=3),
            purpose="meeting",
        )
        result = engine.evaluate_request(request)
        assert not result.passed
        assert any(v.field == "departure_date" for v in result.violations)
