from __future__ import annotations

"""
Anthropic tool-use definitions and implementations for the travel agent.

Each TOOL_DEFINITIONS entry is passed to the Claude API.
Each function in TOOL_HANDLERS maps the tool name to its async implementation.
"""

import json
from datetime import date, datetime
from typing import Any

TOOL_DEFINITIONS = [
    {
        "name": "check_policy",
        "description": (
            "Validate a proposed booking or trip plan against company travel policy. "
            "Returns whether the trip is approved, requires escalation, or is rejected."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string", "description": "The trip plan ID to evaluate"},
                "check_type": {
                    "type": "string",
                    "enum": ["request", "full_trip"],
                    "description": "'request' for initial request validation, 'full_trip' after segments are selected",
                },
            },
            "required": ["trip_id", "check_type"],
        },
    },
    {
        "name": "search_flights",
        "description": "Search for available flights via UCP-compliant airline merchants.",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Origin airport IATA code (e.g. SFO)"},
                "destination": {"type": "string", "description": "Destination airport IATA code (e.g. JFK)"},
                "departure_date": {"type": "string", "description": "ISO date string (YYYY-MM-DD)"},
                "cabin_class": {
                    "type": "string",
                    "enum": ["economy", "premium_economy", "business"],
                    "description": "Cabin class. Default: economy",
                },
                "adults": {"type": "integer", "description": "Number of adult passengers. Default: 1"},
            },
            "required": ["origin", "destination", "departure_date"],
        },
    },
    {
        "name": "search_hotels",
        "description": "Search for available hotels via UCP-compliant hotel merchants.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name (e.g. New York)"},
                "check_in": {"type": "string", "description": "ISO date string (YYYY-MM-DD)"},
                "check_out": {"type": "string", "description": "ISO date string (YYYY-MM-DD)"},
                "room_type": {
                    "type": "string",
                    "enum": ["standard", "deluxe", "suite"],
                    "description": "Room type. Default: standard",
                },
            },
            "required": ["city", "check_in", "check_out"],
        },
    },
    {
        "name": "search_ground_transport",
        "description": "Search for ground transport (car rental, shuttle) via UCP-compliant merchants.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pickup_location": {"type": "string"},
                "dropoff_location": {"type": "string"},
                "pickup_date": {"type": "string", "description": "ISO date string (YYYY-MM-DD)"},
                "days": {"type": "integer", "description": "Number of rental days. Default: 1"},
                "transport_type": {
                    "type": "string",
                    "enum": ["car_rental", "shuttle", "ride_service"],
                    "description": "Type of transport (optional filter)",
                },
            },
            "required": ["pickup_location", "dropoff_location", "pickup_date"],
        },
    },
    {
        "name": "select_and_book_segment",
        "description": (
            "Select a search result and create/complete a UCP checkout session for it. "
            "Use the index from search results to pick the best option."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string"},
                "segment_type": {
                    "type": "string",
                    "enum": ["flight", "hotel", "ground_transport"],
                },
                "merchant_url": {"type": "string", "description": "Merchant base URL"},
                "merchant_name": {"type": "string"},
                "item_id": {"type": "string", "description": "Catalog item ID from search results"},
                "item_name": {"type": "string"},
                "item_description": {"type": "string"},
                "price_cents": {"type": "integer"},
                "details_json": {"type": "string", "description": "JSON string of segment details"},
            },
            "required": [
                "trip_id", "segment_type", "merchant_url", "merchant_name",
                "item_id", "item_name", "price_cents", "details_json",
            ],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Escalate the trip booking to a human approver. Use when: "
            "(1) trip total exceeds the approval threshold, "
            "(2) a checkout session returns requires_escalation, or "
            "(3) policy violations that block autonomous booking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string"},
                "reason": {"type": "string", "description": "Why escalation is needed"},
                "details": {
                    "type": "string",
                    "description": "JSON string with escalation context (policy violations, cost breakdown, etc.)",
                },
            },
            "required": ["trip_id", "reason"],
        },
    },
    {
        "name": "get_order_status",
        "description": "Check the status of a booked order by order ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "build_itinerary",
        "description": "Assemble all booked segments into a human-readable itinerary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string"},
            },
            "required": ["trip_id"],
        },
    },
]
