# AI Travel Agent — Claude Instructions

## Project Overview

An AI agent that autonomously books business travel (flights, hotels, ground transport) using:
- **UCP (Universal Commerce Protocol)** — merchant discovery, catalog browsing, checkout sessions
- **AP2 (Agent Payments Protocol)** — cryptographic payment mandates (Intent, Cart, Payment)
- **Claude API (Anthropic)** — custom tool-calling loop for booking orchestration

## Tech Stack

- **Python 3.12**, FastAPI, Uvicorn
- **Anthropic SDK** — direct API usage, no LangChain or agent frameworks
- **Pydantic v2** — all data models
- **SQLAlchemy async** + aiosqlite (dev) / PostgreSQL (prod)
- **httpx (async)** — all HTTP calls
- **pytest + pytest-asyncio** — `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed)
- **ruff** — linter/formatter, line-length 100, target py312
- **uv** — package manager

## Running the App

```bash
source .venv/bin/activate

# Start mock merchants (3 separate terminals)
uvicorn mock_merchants.flight_merchant:app --port 8001
uvicorn mock_merchants.hotel_merchant:app --port 8002
uvicorn mock_merchants.transport_merchant:app --port 8003

# Start main server
uvicorn travel_agent.main:app --reload

# Run tests
pytest
pytest tests/unit/ -v
pytest tests/integration/ -v
```

## Architecture Rules — Never Break These

### Custom Tool-Calling Loop
- The agent loop lives in `src/travel_agent/agent/orchestrator.py` — `TravelAgentOrchestrator._run_agent_loop()`
- It calls Claude → executes tool calls → feeds results back → repeats (max 20 iterations)
- **No LangChain, no agent frameworks** — keep this direct and simple
- Tools are defined in `agent/tools.py` as Anthropic tool-use schemas

### UCP Checkout State Machine
Always preserve this sequence — do not skip states:
```
create_checkout → (update with traveler info) → ready_for_complete → complete
```
- `incomplete` → session created, items added
- `ready_for_complete` → traveler info added, waiting for payment
- `completed` → payment processed, `order_id` returned

### AP2 Mandate Separation
Three mandate types — never conflate them:
| Mandate | When Created | Human Required? |
|---------|-------------|-----------------|
| **Intent Mandate** | At policy-check time, before searching | No — autonomous |
| **Cart Mandate** | When trip exceeds approval threshold | Yes — human approves |
| **Payment Mandate** | At checkout completion time | No — derived from approved intent/cart |

- Intent Mandate: pre-authorizes autonomous spending up to a max amount within categories
- Cart Mandate: exact cart contents, requires escalation to human approver
- Payment Mandate: VDC-signed JWT, created only at `complete_checkout` time

## Module Responsibilities

```
src/travel_agent/
├── agent/          Claude orchestrator, tool definitions, prompts, trip context
├── policy/         YAML rule evaluation — pass/fail/escalate
├── ucp/            UCP HTTP client, /.well-known/ucp discovery, checkout lifecycle
├── ap2/            Mandate construction, VDC signing (local EC key), payment orchestration
├── travel/         Trip/Segment/Itinerary models, multi-merchant search, merchant registry
├── escalation/     Human-in-the-loop approval handler + models
├── api/            REST API routes (FastAPI routers)
├── web/            Jinja2 web UI (trip form, status, approvals dashboard)
├── db/             SQLAlchemy ORM models, engine, repository DAL
└── cli.py          Click CLI (book, status, approvals, decide)

mock_merchants/     3 UCP-compliant mock FastAPI servers + inventory.json
config/             company_policy.yaml (edit to change rules), settings.yaml
tests/unit/         Policy engine, AP2 mandates, VDC signing
tests/integration/  Mock merchant UCP checkout lifecycle (in-process via ASGITransport)
```

## Coding Conventions

- `from __future__ import annotations` at the top of every file
- Type hints on all function signatures
- Pydantic v2 `.model_dump()` not `.dict()`
- Async throughout — no synchronous DB calls, no sync HTTP
- Prefer editing existing files; do not create new modules unless truly necessary
- Do not add docstrings, comments, or type hints to code you didn't change
- Do not add error handling for scenarios that can't happen
- Three similar lines of code is better than a premature abstraction

## Testing Conventions

- `asyncio_mode = "auto"` in `pyproject.toml` — no `@pytest.mark.asyncio` decorator needed
- Integration tests use `httpx.AsyncClient(transport=ASGITransport(app=...))` — no real network calls
- Mock merchants are imported in-process as fixtures — no external servers needed for tests
- Use `respx` for mocking external HTTP calls in unit tests
- Never mock the database in tests — use in-memory SQLite

## Company Policy

Edit `config/company_policy.yaml` to change rules:
- `flights.max_price_usd`: 1500
- `hotels.max_price_per_night_usd`: 250
- `trip.approval_threshold_usd`: 3000 — trips over this require human approval
- Business class always requires VP approval (escalation)

## Agent Tools (exposed to Claude)

`check_policy`, `search_flights`, `search_hotels`, `search_ground_transport`,
`select_and_book_segment`, `escalate_to_human`, `get_order_status`, `build_itinerary`

## Key Files to Know

| File | Purpose |
|------|---------|
| `src/travel_agent/agent/orchestrator.py` | Main agent loop — start here |
| `src/travel_agent/agent/tools.py` | Claude tool schemas |
| `src/travel_agent/agent/prompts.py` | System prompt |
| `src/travel_agent/ucp/checkout.py` | UCP checkout lifecycle |
| `src/travel_agent/ap2/mandates.py` | Intent/Cart/Payment mandate creation |
| `src/travel_agent/ap2/signing.py` | VDC signing (local EC key pair) |
| `src/travel_agent/policy/engine.py` | Policy rule evaluation |
| `config/company_policy.yaml` | Edit to change travel policy rules |
| `mock_merchants/inventory.json` | Sample flights/hotels/transport inventory |
