from __future__ import annotations

from travel_agent.travel.models import SearchResult, TripPlan, TripRequest


class TripContext:
    """
    Maintains in-memory state for an active trip booking session.
    Shared between the orchestrator and tool handlers.
    """

    def __init__(self, request: TripRequest, plan: TripPlan):
        self.request = request
        self.plan = plan
        self.flight_results: list[SearchResult] = []
        self.hotel_results: list[SearchResult] = []
        self.transport_results: list[SearchResult] = []
        self.messages: list[dict] = []  # Claude conversation history

    def add_message(self, role: str, content) -> None:
        self.messages.append({"role": role, "content": content})

    def get_messages(self) -> list[dict]:
        return list(self.messages)
