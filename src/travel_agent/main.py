from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
import yaml
from fastapi import FastAPI

from travel_agent.agent.orchestrator import TravelAgentOrchestrator
from travel_agent.ap2.mandates import MandateManager
from travel_agent.ap2.payment import PaymentOrchestrator
from travel_agent.ap2.signing import VDCSigner
from travel_agent.escalation.handler import EscalationHandler
from travel_agent.policy.engine import PolicyEngine
from travel_agent.policy.loader import load_default_policy
from travel_agent.travel.merchants import MerchantInfo, MerchantRegistry
from travel_agent.travel.search import TravelSearchService
from travel_agent.ucp.client import UCPClient
from travel_agent.ucp.checkout import CheckoutManager
from travel_agent.ucp.discovery import MerchantDiscovery


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load settings
    settings_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
    with open(settings_path) as f:
        settings = yaml.safe_load(f)

    # Build dependency graph
    policy = load_default_policy()
    policy_engine = PolicyEngine(policy)

    ucp_client = UCPClient()
    discovery = MerchantDiscovery(ucp_client)

    # Register known merchants from settings
    registry = MerchantRegistry()
    merchants_cfg = settings.get("merchants", {})
    for category, info in merchants_cfg.items():
        registry.register(MerchantInfo(
            url=info["url"],
            name=info["name"],
            category=category + "s" if not category.endswith("s") else category,
            merchant_id=info["url"].split("//")[-1],
        ))

    search_service = TravelSearchService(ucp_client, discovery, registry)

    checkout_manager = CheckoutManager(
        ucp_client,
        discovery,
        webhook_base_url=settings.get("webhooks", {}).get("base_url", ""),
    )

    signer = VDCSigner()
    mandate_manager = MandateManager()
    payment_orchestrator = PaymentOrchestrator(signer, mandate_manager)
    escalation_handler = EscalationHandler()

    anthropic_client = anthropic.AsyncAnthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", "")
    )
    model = settings.get("agent", {}).get("model", "claude-sonnet-4-20250514")

    orchestrator = TravelAgentOrchestrator(
        anthropic_client=anthropic_client,
        model=model,
        policy_engine=policy_engine,
        search_service=search_service,
        checkout_manager=checkout_manager,
        payment_orchestrator=payment_orchestrator,
        mandate_manager=mandate_manager,
        escalation_handler=escalation_handler,
        webhook_base_url=settings.get("webhooks", {}).get("base_url", ""),
    )

    # Store on app state for route access
    app.state.orchestrator = orchestrator
    app.state.escalation_handler = escalation_handler
    app.state.ucp_client = ucp_client

    yield

    await ucp_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Travel Agent",
        description="Autonomous business travel booking via UCP and AP2 protocols",
        version="0.1.0",
        lifespan=lifespan,
    )

    from travel_agent.api.routes import router as api_router
    from travel_agent.webhooks.routes import router as webhook_router
    from travel_agent.web.routes import router as web_router

    app.include_router(api_router)
    app.include_router(webhook_router)
    app.include_router(web_router)

    return app


app = create_app()


def run():
    import uvicorn
    uvicorn.run("travel_agent.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
