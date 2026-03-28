from __future__ import annotations

from datetime import date

from travel_agent.policy.models import CompanyPolicy
from travel_agent.travel.models import (
    FlightDetails,
    GroundTransportDetails,
    HotelDetails,
    PolicyResult,
    PolicyViolation,
    TripPlan,
    TripRequest,
    TripSegment,
)


class PolicyEngine:
    def __init__(self, policy: CompanyPolicy):
        self.policy = policy

    def evaluate_request(self, request: TripRequest) -> PolicyResult:
        violations: list[PolicyViolation] = []

        # Advance booking check
        days_until_departure = (request.departure_date - date.today()).days
        if days_until_departure < self.policy.flights.advance_booking_days:
            violations.append(
                PolicyViolation(
                    field="departure_date",
                    message=(
                        f"Departure is {days_until_departure} days away; "
                        f"policy requires {self.policy.flights.advance_booking_days}+ days advance booking"
                    ),
                    value=days_until_departure,
                    limit=self.policy.flights.advance_booking_days,
                )
            )

        return PolicyResult(passed=len(violations) == 0, violations=violations)

    def evaluate_flight(self, flight: FlightDetails) -> PolicyResult:
        violations: list[PolicyViolation] = []
        fp = self.policy.flights

        if fp.preferred_airlines and flight.airline not in fp.preferred_airlines:
            violations.append(
                PolicyViolation(
                    field="airline",
                    message=f"Airline {flight.airline!r} is not in preferred list {fp.preferred_airlines}",
                    value=flight.airline,
                )
            )

        if flight.cabin_class.lower() not in fp.allowed_cabin_classes:
            violations.append(
                PolicyViolation(
                    field="cabin_class",
                    message=f"Cabin class {flight.cabin_class!r} is not allowed (allowed: {fp.allowed_cabin_classes})",
                    value=flight.cabin_class,
                )
            )

        if fp.require_refundable and not flight.is_refundable:
            violations.append(
                PolicyViolation(
                    field="is_refundable",
                    message="Policy requires refundable tickets",
                    value=str(flight.is_refundable),
                )
            )

        return PolicyResult(passed=len(violations) == 0, violations=violations)

    def evaluate_hotel(self, hotel: HotelDetails) -> PolicyResult:
        violations: list[PolicyViolation] = []
        hp = self.policy.hotels

        if hp.preferred_chains and hotel.chain and hotel.chain not in hp.preferred_chains:
            violations.append(
                PolicyViolation(
                    field="chain",
                    message=f"Hotel chain {hotel.chain!r} is not in preferred list",
                    value=hotel.chain,
                )
            )

        if hotel.star_rating < hp.min_star_rating:
            violations.append(
                PolicyViolation(
                    field="star_rating",
                    message=f"Hotel star rating {hotel.star_rating} is below minimum {hp.min_star_rating}",
                    value=hotel.star_rating,
                    limit=hp.min_star_rating,
                )
            )

        if hotel.star_rating > hp.max_star_rating:
            violations.append(
                PolicyViolation(
                    field="star_rating",
                    message=f"Hotel star rating {hotel.star_rating} exceeds maximum {hp.max_star_rating}",
                    value=hotel.star_rating,
                    limit=hp.max_star_rating,
                )
            )

        return PolicyResult(passed=len(violations) == 0, violations=violations)

    def evaluate_ground_transport(self, transport: GroundTransportDetails) -> PolicyResult:
        violations: list[PolicyViolation] = []
        gp = self.policy.ground_transport

        if gp.preferred_providers and transport.provider not in gp.preferred_providers:
            violations.append(
                PolicyViolation(
                    field="provider",
                    message=f"Provider {transport.provider!r} is not in preferred list",
                    value=transport.provider,
                )
            )

        return PolicyResult(passed=len(violations) == 0, violations=violations)

    def evaluate_segment_cost(self, segment: TripSegment) -> PolicyResult:
        violations: list[PolicyViolation] = []
        cost = segment.cost.amount

        if segment.segment_type == "flight":
            limit = self.policy.flights.max_price_usd
            if cost > limit:
                violations.append(
                    PolicyViolation(
                        field="cost",
                        message=f"Flight cost ${cost:.2f} exceeds limit ${limit:.2f}",
                        value=cost,
                        limit=limit,
                    )
                )
        elif segment.segment_type == "hotel":
            assert isinstance(segment.details, HotelDetails)
            nights = segment.details.nights or 1
            per_night = cost / nights
            limit = self.policy.hotels.max_price_per_night_usd
            if per_night > limit:
                violations.append(
                    PolicyViolation(
                        field="cost_per_night",
                        message=f"Hotel cost ${per_night:.2f}/night exceeds limit ${limit:.2f}/night",
                        value=per_night,
                        limit=limit,
                    )
                )
        elif segment.segment_type == "ground_transport":
            limit = self.policy.ground_transport.max_price_usd
            if cost > limit:
                violations.append(
                    PolicyViolation(
                        field="cost",
                        message=f"Ground transport cost ${cost:.2f} exceeds limit ${limit:.2f}",
                        value=cost,
                        limit=limit,
                    )
                )

        return PolicyResult(passed=len(violations) == 0, violations=violations)

    def evaluate_trip_total(self, trip: TripPlan) -> PolicyResult:
        violations: list[PolicyViolation] = []
        tp = self.policy.trip
        total = trip.total_cost.amount

        if total > tp.max_total_usd:
            violations.append(
                PolicyViolation(
                    field="total_cost",
                    message=f"Trip total ${total:.2f} exceeds maximum ${tp.max_total_usd:.2f}",
                    value=total,
                    limit=tp.max_total_usd,
                )
            )

        requires_approval = False
        approval_reason = None
        if total > tp.approval_threshold_usd:
            requires_approval = True
            approval_reason = f"Trip total ${total:.2f} exceeds approval threshold ${tp.approval_threshold_usd:.2f}"

        # Check business class on any flight segment
        for segment in trip.segments:
            if segment.segment_type == "flight" and isinstance(segment.details, FlightDetails):
                if segment.details.cabin_class.lower() == "business":
                    requires_approval = True
                    approval_reason = "Business class requires VP approval"

        return PolicyResult(
            passed=len(violations) == 0,
            violations=violations,
            requires_approval=requires_approval,
            approval_reason=approval_reason,
        )

    def evaluate_full_trip(self, trip: TripPlan) -> PolicyResult:
        all_violations: list[PolicyViolation] = []
        requires_approval = False
        approval_reason = None

        for segment in trip.segments:
            # Evaluate cost limits
            cost_result = self.evaluate_segment_cost(segment)
            all_violations.extend(cost_result.violations)

            # Evaluate segment-specific details
            if segment.segment_type == "flight" and isinstance(segment.details, FlightDetails):
                detail_result = self.evaluate_flight(segment.details)
                all_violations.extend(detail_result.violations)
            elif segment.segment_type == "hotel" and isinstance(segment.details, HotelDetails):
                detail_result = self.evaluate_hotel(segment.details)
                all_violations.extend(detail_result.violations)
            elif segment.segment_type == "ground_transport" and isinstance(
                segment.details, GroundTransportDetails
            ):
                detail_result = self.evaluate_ground_transport(segment.details)
                all_violations.extend(detail_result.violations)

        # Evaluate total
        total_result = self.evaluate_trip_total(trip)
        all_violations.extend(total_result.violations)
        if total_result.requires_approval:
            requires_approval = True
            approval_reason = total_result.approval_reason

        return PolicyResult(
            passed=len(all_violations) == 0,
            violations=all_violations,
            requires_approval=requires_approval,
            approval_reason=approval_reason,
        )

    def requires_human_approval(self, trip: TripPlan) -> bool:
        result = self.evaluate_full_trip(trip)
        return result.requires_approval or not result.passed
