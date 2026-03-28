from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from travel_agent.policy.loader import load_policy
from travel_agent.policy.engine import PolicyEngine
from travel_agent.travel.models import (
    FlightDetails,
    HotelDetails,
    GroundTransportDetails,
    Money,
    TripPlan,
    TripRequest,
    TripSegment,
)


SAMPLE_POLICY_PATH = Path(__file__).parent.parent / "config" / "company_policy.yaml"


@pytest.fixture
def policy():
    return load_policy(SAMPLE_POLICY_PATH)


@pytest.fixture
def policy_engine(policy):
    return PolicyEngine(policy)


@pytest.fixture
def sample_request():
    return TripRequest(
        traveler_name="Alice Smith",
        traveler_email="alice@company.com",
        origin="SFO",
        destination="JFK",
        departure_date=date(2026, 6, 15),
        return_date=date(2026, 6, 18),
        purpose="client meeting",
    )


@pytest.fixture
def sample_flight():
    from datetime import datetime
    return FlightDetails(
        airline="UA",
        flight_number="UA 415",
        origin="SFO",
        destination="JFK",
        departure_datetime=datetime(2026, 6, 15, 8, 0),
        arrival_datetime=datetime(2026, 6, 15, 16, 30),
        cabin_class="economy",
        duration_minutes=330,
        is_refundable=False,
    )


@pytest.fixture
def sample_hotel():
    return HotelDetails(
        name="Marriott Marquis",
        chain="Marriott",
        address="1535 Broadway, New York, NY",
        city="New York",
        star_rating=4,
        check_in_date=date(2026, 6, 15),
        check_out_date=date(2026, 6, 18),
        room_type="standard",
    )
