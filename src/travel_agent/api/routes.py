from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

from travel_agent.escalation.models import ApprovalDecision
from travel_agent.travel.models import TripRequest, TripResult, TripStatus

router = APIRouter(prefix="/api", tags=["trips"])


# --- Request/Response models ---

class TripRequestPayload(BaseModel):
    traveler_name: str
    traveler_email: str
    origin: str
    destination: str
    departure_date: str  # ISO date
    return_date: str | None = None
    needs_hotel: bool = True
    needs_ground_transport: bool = True
    purpose: str
    seat_preference: str = "no_preference"


class TripStatusResponse(BaseModel):
    trip_id: str
    status: str
    itinerary: str | None = None
    total_cost_usd: float | None = None
    escalation_id: str | None = None
    error: str | None = None


class ApprovalPayload(BaseModel):
    approved: bool
    approver_email: str | None = None
    notes: str | None = None


# --- In-memory trip results store (replaced by DB in production) ---

_trip_results: dict[str, TripResult] = {}
_active_tasks: dict[str, asyncio.Task] = {}


def get_trip_results() -> dict[str, TripResult]:
    return _trip_results


def get_active_tasks() -> dict[str, asyncio.Task]:
    return _active_tasks


# --- Routes ---

@router.post("/trips", response_model=TripStatusResponse, status_code=202)
async def create_trip(
    payload: TripRequestPayload,
    background_tasks: BackgroundTasks,
    request: Request,
) -> TripStatusResponse:
    """Submit a new trip booking request. Returns immediately; booking happens async."""
    from travel_agent.travel.models import TravelerPreferences
    trip_request = TripRequest(
        traveler_name=payload.traveler_name,
        traveler_email=payload.traveler_email,
        origin=payload.origin.upper(),
        destination=payload.destination.upper(),
        departure_date=date.fromisoformat(payload.departure_date),
        return_date=date.fromisoformat(payload.return_date) if payload.return_date else None,
        needs_hotel=payload.needs_hotel,
        needs_ground_transport=payload.needs_ground_transport,
        purpose=payload.purpose,
        preferences=TravelerPreferences(seat_preference=payload.seat_preference),
    )

    # Kick off booking in the background
    orchestrator = request.app.state.orchestrator
    escalation_handler = request.app.state.escalation_handler

    async def run_booking():
        result = await orchestrator.handle_trip_request(trip_request)
        _trip_results[trip_request.id] = result

    task = asyncio.create_task(run_booking())
    _active_tasks[trip_request.id] = task

    # Store placeholder
    _trip_results[trip_request.id] = TripResult(
        trip_id=trip_request.id,
        status=TripStatus.PLANNING,
    )

    return TripStatusResponse(
        trip_id=trip_request.id,
        status=TripStatus.PLANNING.value,
    )


@router.get("/trips/{trip_id}", response_model=TripStatusResponse)
async def get_trip(trip_id: str) -> TripStatusResponse:
    result = _trip_results.get(trip_id)
    if not result:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Check if there's a pending escalation
    escalation_id = None
    if result.status == TripStatus.ESCALATED:
        escalation_id = result.escalation_id

    return TripStatusResponse(
        trip_id=result.trip_id,
        status=result.status.value,
        itinerary=result.itinerary,
        total_cost_usd=result.total_cost.amount if result.total_cost else None,
        escalation_id=escalation_id,
        error=result.error,
    )


@router.get("/trips/{trip_id}/itinerary")
async def get_itinerary(trip_id: str) -> dict:
    result = _trip_results.get(trip_id)
    if not result:
        raise HTTPException(status_code=404, detail="Trip not found")
    if not result.itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not yet available")
    return {"trip_id": trip_id, "itinerary": result.itinerary}


@router.get("/escalations")
async def list_escalations(request: Request) -> dict:
    handler = request.app.state.escalation_handler
    pending = handler.list_pending()
    return {
        "escalations": [
            {
                "id": e.id,
                "trip_id": e.trip_id,
                "reason": e.reason,
                "status": e.status.value,
                "created_at": e.created_at.isoformat(),
                "details": e.details,
            }
            for e in pending
        ]
    }


@router.get("/escalations/{escalation_id}")
async def get_escalation(escalation_id: str, request: Request) -> dict:
    handler = request.app.state.escalation_handler
    escalation = handler.get(escalation_id)
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return {
        "id": escalation.id,
        "trip_id": escalation.trip_id,
        "reason": escalation.reason,
        "status": escalation.status.value,
        "details": escalation.details,
        "created_at": escalation.created_at.isoformat(),
        "decided_at": escalation.decided_at.isoformat() if escalation.decided_at else None,
    }


@router.post("/escalations/{escalation_id}/decide")
async def decide_escalation(
    escalation_id: str,
    payload: ApprovalPayload,
    request: Request,
) -> dict:
    handler = request.app.state.escalation_handler
    decision = ApprovalDecision(
        approved=payload.approved,
        approver_email=payload.approver_email,
        notes=payload.notes,
    )
    escalation = await handler.process_decision(escalation_id, decision)
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")

    return {
        "escalation_id": escalation_id,
        "status": escalation.status.value,
        "trip_id": escalation.trip_id,
        "message": "Decision recorded. The booking will be updated accordingly.",
    }
