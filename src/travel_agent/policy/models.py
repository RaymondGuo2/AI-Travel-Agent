from __future__ import annotations

from pydantic import BaseModel


class FlightPolicy(BaseModel):
    max_price_usd: float = 1500.0
    preferred_airlines: list[str] = []
    allowed_cabin_classes: list[str] = ["economy", "premium_economy"]
    advance_booking_days: int = 7
    require_refundable: bool = False


class HotelPolicy(BaseModel):
    max_price_per_night_usd: float = 250.0
    min_star_rating: int = 3
    max_star_rating: int = 5
    preferred_chains: list[str] = []


class GroundTransportPolicy(BaseModel):
    max_price_usd: float = 150.0
    preferred_providers: list[str] = []


class EscalationRule(BaseModel):
    condition: str
    action: str


class TripPolicy(BaseModel):
    max_total_usd: float = 5000.0
    per_diem_usd: float = 75.0
    approval_threshold_usd: float = 3000.0


class EscalationConfig(BaseModel):
    rules: list[EscalationRule] = []


class CompanyPolicy(BaseModel):
    version: int = 1
    flights: FlightPolicy = FlightPolicy()
    hotels: HotelPolicy = HotelPolicy()
    ground_transport: GroundTransportPolicy = GroundTransportPolicy()
    trip: TripPolicy = TripPolicy()
    escalation: EscalationConfig = EscalationConfig()
