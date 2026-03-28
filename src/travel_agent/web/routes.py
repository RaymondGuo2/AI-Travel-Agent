from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    template = templates.env.get_template("index.html")
    rendered = template.render(request=request)
    return HTMLResponse(rendered)


@router.get("/trips/{trip_id}", response_class=HTMLResponse)
async def trip_status_page(trip_id: str, request: Request):
    from travel_agent.api.routes import _trip_results
    result = _trip_results.get(trip_id)
    if not result:
        return HTMLResponse("<h1>Trip not found</h1>", status_code=404)

    escalation_id = None
    handler = request.app.state.escalation_handler
    for esc in handler.get_by_trip(trip_id):
        escalation_id = esc.id
        break

    template = templates.env.get_template("trip_status.html")
    rendered = template.render(
        request=request,
        trip_id=trip_id,
        status=result.status.value,
        itinerary=result.itinerary,
        total_cost_usd=result.total_cost.amount if result.total_cost else None,
        error=result.error,
        escalation_id=escalation_id,
    )
    return HTMLResponse(rendered)


@router.get("/approvals", response_class=HTMLResponse)
async def approvals_page(request: Request):
    handler = request.app.state.escalation_handler
    pending = handler.list_pending()
    template = templates.env.get_template("approvals.html")
    rendered = template.render(
        request=request,
        escalations=[
            {
                "id": e.id,
                "trip_id": e.trip_id,
                "reason": e.reason,
                "status": e.status.value,
                "details": e.details,
                "created_at": e.created_at.isoformat(),
            }
            for e in pending
        ],
    )
    return HTMLResponse(rendered)


@router.get("/approvals/{escalation_id}", response_class=HTMLResponse)
async def approval_detail_page(escalation_id: str, request: Request):
    handler = request.app.state.escalation_handler
    escalation = handler.get(escalation_id)
    if not escalation:
        return HTMLResponse("<h1>Escalation not found</h1>", status_code=404)

    template = templates.env.get_template("approval_detail.html")
    rendered = template.render(
        request=request,
        escalation_id=escalation_id,
        trip_id=escalation.trip_id,
        status=escalation.status.value,
        reason=escalation.reason,
        details=escalation.details,
        decided_at=escalation.decided_at.isoformat() if escalation.decided_at else None,
    )
    return HTMLResponse(rendered)
