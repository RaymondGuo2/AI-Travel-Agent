from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Money(BaseModel):
    amount_cents: int
    currency: str = "USD"

    @property
    def amount(self) -> float:
        return self.amount_cents / 100

    @classmethod
    def from_float(cls, amount: float, currency: str = "USD") -> "Money":
        return cls(amount_cents=round(amount * 100), currency=currency)

    def __add__(self, other: "Money") -> "Money":
        assert self.currency == other.currency, "Cannot add different currencies"
        return Money(amount_cents=self.amount_cents + other.amount_cents, currency=self.currency)


class TravelerPreferences(BaseModel):
    seat_preference: Literal["window", "aisle", "middle", "no_preference"] = "no_preference"
    meal_preference: str | None = None
    loyalty_numbers: dict[str, str] = Field(default_factory=dict)  # airline/hotel -> number
    notes: str | None = None


class TripRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    traveler_name: str
    traveler_email: str
    origin: str  # IATA code or city
    destination: str
    departure_date: date
    return_date: date | None = None
    multi_city: list[CityStop] | None = None
    needs_hotel: bool = True
    needs_ground_transport: bool = True
    preferences: TravelerPreferences | None = None
    purpose: str  # e.g. "client meeting", "conference"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CityStop(BaseModel):
    city: str
    arrival_date: date
    departure_date: date


class FlightDetails(BaseModel):
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_datetime: datetime
    arrival_datetime: datetime
    cabin_class: str
    duration_minutes: int
    is_refundable: bool = False
    baggage_included: bool = True


class HotelDetails(BaseModel):
    name: str
    chain: str | None = None
    address: str
    city: str
    star_rating: int
    check_in_date: date
    check_out_date: date
    room_type: str
    is_refundable: bool = False

    @property
    def nights(self) -> int:
        return (self.check_out_date - self.check_in_date).days


class GroundTransportDetails(BaseModel):
    provider: str
    type: Literal["car_rental", "ride_service", "shuttle", "taxi"]
    pickup_location: str
    dropoff_location: str
    pickup_datetime: datetime
    vehicle_type: str | None = None
    is_refundable: bool = False


class SegmentStatus(str, Enum):
    SEARCHING = "searching"
    SELECTED = "selected"
    CHECKOUT_CREATED = "checkout_created"
    PAYMENT_PENDING = "payment_pending"
    BOOKED = "booked"
    CANCELED = "canceled"
    FAILED = "failed"


class TripSegment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    segment_type: Literal["flight", "hotel", "ground_transport"]
    merchant_url: str
    merchant_name: str
    checkout_session_id: str | None = None
    order_id: str | None = None
    details: FlightDetails | HotelDetails | GroundTransportDetails
    cost: Money
    status: SegmentStatus = SegmentStatus.SEARCHING


class TripStatus(str, Enum):
    PLANNING = "planning"
    SEARCHING = "searching"
    POLICY_CHECK = "policy_check"
    BOOKING = "booking"
    BOOKED = "booked"
    ESCALATED = "escalated"
    FAILED = "failed"
    CANCELED = "canceled"


class PolicyViolation(BaseModel):
    field: str
    message: str
    value: str | float | None = None
    limit: str | float | None = None


class PolicyResult(BaseModel):
    passed: bool
    violations: list[PolicyViolation] = Field(default_factory=list)
    requires_approval: bool = False
    approval_reason: str | None = None


class TripPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request: TripRequest
    segments: list[TripSegment] = Field(default_factory=list)
    total_cost: Money = Field(default_factory=lambda: Money(amount_cents=0))
    policy_result: PolicyResult | None = None
    intent_mandate_id: str | None = None
    status: TripStatus = TripStatus.PLANNING
    itinerary: str | None = None  # Human-readable summary
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def recalculate_total(self) -> None:
        if not self.segments:
            self.total_cost = Money(amount_cents=0)
            return
        total = sum(s.cost.amount_cents for s in self.segments)
        self.total_cost = Money(amount_cents=total, currency=self.segments[0].cost.currency)


class SearchResult(BaseModel):
    merchant_url: str
    merchant_name: str
    segment_type: Literal["flight", "hotel", "ground_transport"]
    details: FlightDetails | HotelDetails | GroundTransportDetails
    cost: Money
    score: float = 0.0  # Higher = better match for policy + preferences


class TripResult(BaseModel):
    trip_id: str
    status: TripStatus
    itinerary: str | None = None
    segments: list[TripSegment] = Field(default_factory=list)
    total_cost: Money | None = None
    policy_result: PolicyResult | None = None
    escalation_id: str | None = None
    error: str | None = None
