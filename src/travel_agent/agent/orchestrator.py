from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Any

import anthropic

from travel_agent.agent.memory import TripContext
from travel_agent.agent.prompts import SYSTEM_PROMPT
from travel_agent.agent.tools import TOOL_DEFINITIONS
from travel_agent.ap2.mandates import MandateManager
from travel_agent.ap2.payment import PaymentOrchestrator
from travel_agent.ap2.signing import VDCSigner
from travel_agent.escalation.handler import EscalationHandler
from travel_agent.policy.engine import PolicyEngine
from travel_agent.travel.merchants import MerchantRegistry
from travel_agent.travel.models import (
    Money,
    SegmentStatus,
    TripPlan,
    TripRequest,
    TripResult,
    TripSegment,
    TripStatus,
)
from travel_agent.travel.search import TravelSearchService
from travel_agent.ucp.checkout import CheckoutManager, CheckoutEscalationRequired
from travel_agent.ucp.models import CheckoutCreateRequest, LineItem


class TravelAgentOrchestrator:
    """
    Claude-powered travel booking agent.

    Runs a tool-calling loop: call Claude → execute tool calls → feed results back → repeat
    until the trip is fully booked, escalated, or failed.
    """

    MAX_ITERATIONS = 20

    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        model: str,
        policy_engine: PolicyEngine,
        search_service: TravelSearchService,
        checkout_manager: CheckoutManager,
        payment_orchestrator: PaymentOrchestrator,
        mandate_manager: MandateManager,
        escalation_handler: EscalationHandler,
        webhook_base_url: str = "",
    ):
        self._claude = anthropic_client
        self._model = model
        self._policy = policy_engine
        self._search = search_service
        self._checkout = checkout_manager
        self._payment = payment_orchestrator
        self._mandates = mandate_manager
        self._escalation = escalation_handler
        self._webhook_base_url = webhook_base_url

        # In-flight trip contexts keyed by trip_id
        self._contexts: dict[str, TripContext] = {}

    async def handle_trip_request(self, request: TripRequest) -> TripResult:
        """Main entry point. Returns a TripResult once booking is resolved."""
        plan = TripPlan(request=request)
        ctx = TripContext(request=request, plan=plan)
        self._contexts[plan.id] = ctx

        # Build the initial user message
        user_msg = self._format_trip_request(request)
        ctx.add_message("user", user_msg)

        try:
            result = await self._run_agent_loop(ctx)
        except Exception as exc:
            result = TripResult(
                trip_id=plan.id,
                status=TripStatus.FAILED,
                error=str(exc),
            )
        finally:
            self._contexts.pop(plan.id, None)

        return result

    async def _run_agent_loop(self, ctx: TripContext) -> TripResult:
        for iteration in range(self.MAX_ITERATIONS):
            response = await self._claude.messages.create(
                model=self._model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=ctx.get_messages(),
            )

            # Append assistant response to history
            ctx.add_message("assistant", response.content)

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Agent decided it's done — extract final text
                text = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
                ctx.plan.status = TripStatus.BOOKED if ctx.plan.segments else TripStatus.FAILED
                ctx.plan.itinerary = text
                return self._build_result(ctx)

            if response.stop_reason != "tool_use":
                break

            # Execute all tool calls
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = await self._execute_tool(ctx, block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            ctx.add_message("user", tool_results)

            # Check if plan is in a terminal state
            if ctx.plan.status in (TripStatus.BOOKED, TripStatus.ESCALATED, TripStatus.FAILED):
                # Let agent generate a final response with the known state
                final = await self._claude.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    tools=TOOL_DEFINITIONS,
                    messages=ctx.get_messages(),
                )
                text = next(
                    (b.text for b in final.content if hasattr(b, "text")), ""
                )
                ctx.plan.itinerary = ctx.plan.itinerary or text
                return self._build_result(ctx)

        # Exceeded max iterations
        ctx.plan.status = TripStatus.FAILED
        return TripResult(
            trip_id=ctx.plan.id,
            status=TripStatus.FAILED,
            error="Agent exceeded maximum iterations without completing the booking",
        )

    async def _execute_tool(self, ctx: TripContext, tool_name: str, tool_input: dict) -> dict:
        try:
            if tool_name == "check_policy":
                return await self._tool_check_policy(ctx, tool_input)
            elif tool_name == "search_flights":
                return await self._tool_search_flights(ctx, tool_input)
            elif tool_name == "search_hotels":
                return await self._tool_search_hotels(ctx, tool_input)
            elif tool_name == "search_ground_transport":
                return await self._tool_search_ground_transport(ctx, tool_input)
            elif tool_name == "select_and_book_segment":
                return await self._tool_select_and_book_segment(ctx, tool_input)
            elif tool_name == "escalate_to_human":
                return await self._tool_escalate(ctx, tool_input)
            elif tool_name == "get_order_status":
                return await self._tool_get_order_status(ctx, tool_input)
            elif tool_name == "build_itinerary":
                return await self._tool_build_itinerary(ctx, tool_input)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as exc:
            return {"error": str(exc)}

    # --- Tool implementations ---

    async def _tool_check_policy(self, ctx: TripContext, inp: dict) -> dict:
        check_type = inp.get("check_type", "request")
        if check_type == "request":
            result = self._policy.evaluate_request(ctx.request)
        else:
            ctx.plan.recalculate_total()
            result = self._policy.evaluate_full_trip(ctx.plan)

        # Create intent mandate if auto-approved
        if result.passed and not result.requires_approval and not ctx.plan.intent_mandate_id:
            ctx.plan.recalculate_total()
            intent = self._mandates.create_intent_mandate(
                request=ctx.request,
                max_amount_cents=int(self._policy.policy.trip.max_total_usd * 100),
            )
            ctx.plan.intent_mandate_id = intent.id
            ctx.plan.status = TripStatus.SEARCHING

        return {
            "passed": result.passed,
            "requires_approval": result.requires_approval,
            "approval_reason": result.approval_reason,
            "violations": [v.model_dump() for v in result.violations],
            "intent_mandate_created": ctx.plan.intent_mandate_id is not None,
        }

    async def _tool_search_flights(self, ctx: TripContext, inp: dict) -> dict:
        dep_date = date.fromisoformat(inp["departure_date"])
        results = await self._search.search_flights(
            origin=inp["origin"],
            destination=inp["destination"],
            departure_date=dep_date,
            cabin_class=inp.get("cabin_class", "economy"),
            adults=inp.get("adults", 1),
        )
        ctx.flight_results = results
        return {
            "count": len(results),
            "flights": [
                {
                    "index": i,
                    "merchant_url": r.merchant_url,
                    "merchant_name": r.merchant_name,
                    "description": (
                        f"{r.details.airline} {r.details.flight_number} | "
                        f"{r.details.origin}→{r.details.destination} | "
                        f"Dep {r.details.departure_datetime.strftime('%H:%M')} "
                        f"Arr {r.details.arrival_datetime.strftime('%H:%M')} | "
                        f"${r.cost.amount:.2f} | {r.details.cabin_class}"
                    ),
                    "price_usd": r.cost.amount,
                    "details": r.details.model_dump(mode="json"),
                }
                for i, r in enumerate(results)
            ],
        }

    async def _tool_search_hotels(self, ctx: TripContext, inp: dict) -> dict:
        check_in = date.fromisoformat(inp["check_in"])
        check_out = date.fromisoformat(inp["check_out"])
        results = await self._search.search_hotels(
            city=inp["city"],
            check_in=check_in,
            check_out=check_out,
            room_type=inp.get("room_type", "standard"),
        )
        ctx.hotel_results = results
        return {
            "count": len(results),
            "hotels": [
                {
                    "index": i,
                    "merchant_url": r.merchant_url,
                    "merchant_name": r.merchant_name,
                    "description": (
                        f"{r.details.name} ({r.details.chain or 'Independent'}) | "
                        f"{'★' * r.details.star_rating} | "
                        f"{r.details.city} | ${r.cost.amount:.2f} total"
                    ),
                    "price_usd": r.cost.amount,
                    "details": r.details.model_dump(mode="json"),
                }
                for i, r in enumerate(results)
            ],
        }

    async def _tool_search_ground_transport(self, ctx: TripContext, inp: dict) -> dict:
        pickup_date = date.fromisoformat(inp["pickup_date"])
        results = await self._search.search_ground_transport(
            pickup_location=inp["pickup_location"],
            dropoff_location=inp["dropoff_location"],
            pickup_date=pickup_date,
            days=inp.get("days", 1),
            transport_type=inp.get("transport_type"),
        )
        ctx.transport_results = results
        return {
            "count": len(results),
            "options": [
                {
                    "index": i,
                    "merchant_url": r.merchant_url,
                    "merchant_name": r.merchant_name,
                    "description": (
                        f"{r.details.provider} | {r.details.vehicle_type or r.details.type} | "
                        f"${r.cost.amount:.2f}"
                    ),
                    "price_usd": r.cost.amount,
                    "details": r.details.model_dump(mode="json"),
                }
                for i, r in enumerate(results)
            ],
        }

    async def _tool_select_and_book_segment(self, ctx: TripContext, inp: dict) -> dict:
        trip_id = inp["trip_id"]
        segment_type = inp["segment_type"]
        merchant_url = inp["merchant_url"]
        merchant_name = inp["merchant_name"]
        price_cents = inp["price_cents"]
        details_dict = json.loads(inp.get("details_json", "{}"))

        # Build line item
        line_item = LineItem(
            id=inp["item_id"],
            name=inp["item_name"],
            description=inp.get("item_description", ""),
            quantity=1,
            unit_price_cents=price_cents,
        )

        # Create UCP checkout session
        try:
            session = await self._checkout.create_and_populate(
                merchant_url=merchant_url,
                items=[line_item],
                buyer_name=ctx.request.traveler_name,
                buyer_email=ctx.request.traveler_email,
            )
        except CheckoutEscalationRequired as e:
            return {
                "status": "requires_escalation",
                "message": str(e),
                "continue_url": e.session.escalation_reason.continue_url if e.session.escalation_reason else None,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

        # Parse details into correct type
        details = _parse_segment_details(segment_type, details_dict)
        if details is None:
            return {"status": "error", "message": "Failed to parse segment details"}

        segment = TripSegment(
            segment_type=segment_type,
            merchant_url=merchant_url,
            merchant_name=merchant_name,
            checkout_session_id=session.id,
            details=details,
            cost=Money(amount_cents=price_cents, currency="USD"),
            status=SegmentStatus.CHECKOUT_CREATED,
        )
        ctx.plan.segments.append(segment)
        ctx.plan.recalculate_total()

        # If session is ready_for_complete and we have an intent mandate, pay now
        if session.status.value == "ready_for_complete" and ctx.plan.intent_mandate_id:
            # Re-create intent mandate object for verification
            from travel_agent.ap2.models import IntentMandate
            from datetime import timezone
            intent = self._mandates.create_intent_mandate(
                request=ctx.request,
                max_amount_cents=int(self._policy.policy.trip.max_total_usd * 100),
            )
            intent.id = ctx.plan.intent_mandate_id

            try:
                mandate, receipt = await self._payment.pay_with_intent_mandate(session, intent)
                payment_data = self._payment.build_payment_data(mandate)
                completed = await self._checkout.complete(merchant_url, session.id, payment_data)
                segment.status = SegmentStatus.BOOKED
                segment.order_id = completed.order_id
                return {
                    "status": "booked",
                    "order_id": completed.order_id,
                    "confirmation": receipt.merchant_confirmation_id,
                    "amount_usd": receipt.amount_cents / 100,
                }
            except Exception as e:
                segment.status = SegmentStatus.FAILED
                return {"status": "error", "message": str(e)}

        return {
            "status": "checkout_created",
            "session_id": session.id,
            "session_status": session.status.value,
            "total_usd": session.totals.total if session.totals else price_cents / 100,
        }

    async def _tool_escalate(self, ctx: TripContext, inp: dict) -> dict:
        trip_id = inp["trip_id"]
        reason = inp["reason"]
        details = json.loads(inp.get("details", "{}"))

        escalation_id = await self._escalation.request_approval(
            trip_id=trip_id,
            reason=reason,
            details={
                **details,
                "trip_total_usd": ctx.plan.total_cost.amount,
                "segments_count": len(ctx.plan.segments),
            },
        )
        ctx.plan.status = TripStatus.ESCALATED

        return {
            "escalated": True,
            "escalation_id": escalation_id,
            "message": f"Trip has been escalated for approval. Escalation ID: {escalation_id}",
            "next_steps": "The approver will be notified. Check status via GET /escalations/{escalation_id}",
        }

    async def _tool_get_order_status(self, ctx: TripContext, inp: dict) -> dict:
        order_id = inp["order_id"]
        # Find segment with this order_id
        for segment in ctx.plan.segments:
            if segment.order_id == order_id:
                return {"order_id": order_id, "status": segment.status.value}
        return {"order_id": order_id, "status": "not_found"}

    async def _tool_build_itinerary(self, ctx: TripContext, inp: dict) -> dict:
        segments = ctx.plan.segments
        if not segments:
            return {"itinerary": "No segments booked.", "total_usd": 0}

        lines = [
            f"TRAVEL ITINERARY — {ctx.request.traveler_name}",
            f"Purpose: {ctx.request.purpose}",
            f"Trip ID: {ctx.plan.id}",
            "=" * 50,
        ]

        for seg in segments:
            lines.append(f"\n[{seg.segment_type.upper().replace('_', ' ')}]")
            lines.append(f"  Merchant: {seg.merchant_name}")
            lines.append(f"  Status:   {seg.status.value}")
            if seg.order_id:
                lines.append(f"  Order ID: {seg.order_id}")
            lines.append(f"  Cost:     ${seg.cost.amount:.2f}")

            from travel_agent.travel.models import FlightDetails, HotelDetails, GroundTransportDetails
            d = seg.details
            if isinstance(d, FlightDetails):
                lines.append(f"  Flight:   {d.airline} {d.flight_number}")
                lines.append(f"  Route:    {d.origin} → {d.destination}")
                lines.append(f"  Departs:  {d.departure_datetime.strftime('%Y-%m-%d %H:%M')}")
                lines.append(f"  Arrives:  {d.arrival_datetime.strftime('%Y-%m-%d %H:%M')}")
                lines.append(f"  Class:    {d.cabin_class.title()}")
            elif isinstance(d, HotelDetails):
                lines.append(f"  Hotel:    {d.name}")
                lines.append(f"  Address:  {d.address}")
                lines.append(f"  Check-in: {d.check_in_date}")
                lines.append(f"  Check-out:{d.check_out_date}")
                lines.append(f"  Room:     {d.room_type.title()}")
            elif isinstance(d, GroundTransportDetails):
                lines.append(f"  Provider: {d.provider}")
                lines.append(f"  Type:     {d.type}")
                lines.append(f"  Pick-up:  {d.pickup_location}")
                lines.append(f"  Drop-off: {d.dropoff_location}")

        lines.append("\n" + "=" * 50)
        lines.append(f"TOTAL: ${ctx.plan.total_cost.amount:.2f}")

        itinerary = "\n".join(lines)
        ctx.plan.itinerary = itinerary
        ctx.plan.status = TripStatus.BOOKED

        return {
            "itinerary": itinerary,
            "total_usd": ctx.plan.total_cost.amount,
            "segments_booked": len([s for s in segments if s.status == SegmentStatus.BOOKED]),
        }

    def _build_result(self, ctx: TripContext) -> TripResult:
        return TripResult(
            trip_id=ctx.plan.id,
            status=ctx.plan.status,
            itinerary=ctx.plan.itinerary,
            segments=ctx.plan.segments,
            total_cost=ctx.plan.total_cost,
            policy_result=ctx.plan.policy_result,
        )

    def _format_trip_request(self, req: TripRequest) -> str:
        lines = [
            f"Please book a business trip for {req.traveler_name} ({req.traveler_email}).",
            f"Purpose: {req.purpose}",
            f"Route: {req.origin} → {req.destination}",
            f"Departure: {req.departure_date}",
        ]
        if req.return_date:
            lines.append(f"Return: {req.return_date}")
        if req.needs_hotel:
            lines.append("Hotel: Yes (same destination city)")
        if req.needs_ground_transport:
            lines.append("Ground transport: Yes")
        if req.preferences:
            lines.append(f"Preferences: seat={req.preferences.seat_preference}")
        lines.append(f"\nTrip ID: {req.id} — use this for all tool calls.")
        return "\n".join(lines)


def _parse_segment_details(segment_type: str, d: dict):
    from travel_agent.travel.models import FlightDetails, HotelDetails, GroundTransportDetails
    try:
        if segment_type == "flight":
            return FlightDetails(**d)
        elif segment_type == "hotel":
            return HotelDetails(**d)
        elif segment_type == "ground_transport":
            return GroundTransportDetails(**d)
    except Exception:
        return None
