# AI Travel Agent

An AI assistant that autonomously books business travel (flights, hotels, ground transport) within company policy — no back-and-forth approvals for routine trips.

Built on **Google's Universal Commerce Protocol (UCP)** for merchant discovery and checkout, and **Agent Payments Protocol (AP2)** for cryptographic payment authorization.

## How it works

```
Trip Request → Policy Check → Merchant Discovery (UCP /.well-known/ucp)
     → Catalog Search → Claude Selects Options
     → UCP Checkout Sessions → AP2 Payment Mandates
     → Autonomous Booking OR Escalation to Human Approver
     → Itinerary
```

**Within policy** → Intent Mandate created upfront. Agent books end-to-end autonomously.
**Over approval threshold** → Cart Mandate presented to human approver. Booking resumes on approval.

## Quick Start

```bash
# 1. Install
uv venv && uv pip install -e ".[dev]"
source .venv/bin/activate
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# 2. Start mock merchants (in separate terminals)
uvicorn mock_merchants.flight_merchant:app --port 8001
uvicorn mock_merchants.hotel_merchant:app --port 8002
uvicorn mock_merchants.transport_merchant:app --port 8003

# 3. Start the main server
uvicorn travel_agent.main:app --reload

# 4. Open the web UI
open http://localhost:8000
```

## CLI Usage

```bash
# Book a trip interactively
travel-agent book

# Book with flags
travel-agent book \
  --name "Alice Smith" \
  --email alice@company.com \
  --origin SFO \
  --destination JFK \
  --departure 2026-09-15 \
  --return-date 2026-09-18 \
  --purpose "client meeting"

# Check trip status
travel-agent status <trip-id>

# List pending approvals
travel-agent approvals

# Approve/reject an escalation
travel-agent decide <escalation-id> --approve
travel-agent decide <escalation-id> --reject
```

## REST API

```
POST /api/trips                          Submit a trip request (async)
GET  /api/trips/{id}                     Check trip status and itinerary
GET  /api/trips/{id}/itinerary           Get formatted itinerary
GET  /api/escalations                    List pending approvals
GET  /api/escalations/{id}               Get escalation details
POST /api/escalations/{id}/decide        Approve or reject

POST /webhooks/ucp/orders                UCP order status webhooks (for merchants)
```

## Company Policy

Edit `config/company_policy.yaml` to configure your rules:

```yaml
flights:
  max_price_usd: 1500
  preferred_airlines: ["UA", "DL", "AA"]
  allowed_cabin_classes: ["economy", "premium_economy"]
  advance_booking_days: 7
hotels:
  max_price_per_night_usd: 250
  min_star_rating: 3
  preferred_chains: ["Marriott", "Hilton", "IHG"]
trip:
  approval_threshold_usd: 3000   # Trips over this require human approval
```

## Architecture

```
src/travel_agent/
├── agent/          Claude orchestrator (tool-calling loop)
├── policy/         Company policy engine (YAML rules → pass/fail/escalate)
├── ucp/            UCP client, discovery (/.well-known/ucp), checkout lifecycle
├── ap2/            AP2 mandate creation, VDC signing, payment orchestration
├── travel/         Trip models, search service, merchant registry
├── escalation/     Human-in-the-loop approval handler
├── api/            REST API routes
├── web/            Jinja2 web UI (trip form, status, approvals)
└── cli.py          Click CLI

mock_merchants/
├── flight_merchant.py    UCP-compliant mock airline (port 8001)
├── hotel_merchant.py     UCP-compliant mock hotel chain (port 8002)
├── transport_merchant.py UCP-compliant mock ground transport (port 8003)
└── inventory.json        Sample travel inventory
```

## UCP + AP2 Integration Details

**UCP** handles the commerce layer:
- `GET /.well-known/ucp` — merchant capability discovery
- `POST /checkout-sessions` — create checkout
- `PUT /checkout-sessions/{id}` — add traveler details
- `POST /checkout-sessions/{id}/complete` — finalize with AP2 payment data
- Webhooks — real-time order status updates

**AP2** handles payment authorization:
- **Intent Mandate** — pre-authorizes autonomous spending within conditions (max amount, expiry, categories). Created at policy-check time, no human needed.
- **Cart Mandate** — exact cart contents signed by merchant, requires human approval. Used for over-threshold trips.
- **Payment Mandate** — final payment authorization, VDC-signed JWT. Created at checkout completion time.

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/ -v

# Integration tests (no external services needed — uses in-process mock merchants)
pytest tests/integration/ -v
```

## Protocols

- [Universal Commerce Protocol (UCP)](https://ucp.dev) — Apache 2.0, co-developed by Google and Shopify
- [Agent Payments Protocol (AP2)](https://ap2-protocol.org/specification/) — Apache 2.0, led by Google
