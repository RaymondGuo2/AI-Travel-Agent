from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


@click.group()
def cli():
    """AI Travel Agent — book business travel autonomously."""


@cli.command()
@click.option("--name", prompt="Traveler name", help="Full name of the traveler")
@click.option("--email", prompt="Traveler email", help="Email address")
@click.option("--origin", prompt="Origin (IATA code)", help="e.g. SFO")
@click.option("--destination", prompt="Destination (IATA code)", help="e.g. JFK")
@click.option("--departure", prompt="Departure date (YYYY-MM-DD)", help="ISO date")
@click.option("--return-date", default=None, help="Return date (optional)")
@click.option("--purpose", prompt="Purpose of travel", help="e.g. client meeting")
@click.option("--no-hotel", is_flag=True, help="Skip hotel booking")
@click.option("--no-transport", is_flag=True, help="Skip ground transport booking")
def book(name, email, origin, destination, departure, return_date, purpose, no_hotel, no_transport):
    """Book a business trip end-to-end."""

    async def _run():
        from travel_agent.main import create_app
        import httpx

        req_data = {
            "traveler_name": name,
            "traveler_email": email,
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_date": departure,
            "return_date": return_date,
            "purpose": purpose,
            "needs_hotel": not no_hotel,
            "needs_ground_transport": not no_transport,
        }

        console.print(Panel(
            f"[bold]Booking trip[/bold]\n"
            f"{origin.upper()} → {destination.upper()} on {departure}\n"
            f"Traveler: {name} | Purpose: {purpose}",
            title="AI Travel Agent",
            border_style="blue",
        ))

        # Use the running server if available, otherwise run inline
        server_url = os.environ.get("TRAVEL_AGENT_URL", "http://localhost:8000")
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                # Submit trip
                r = await client.post(f"{server_url}/api/trips", json=req_data)
                r.raise_for_status()
                trip = r.json()
                trip_id = trip["trip_id"]

                console.print(f"[dim]Trip ID: {trip_id}[/dim]")

                # Poll for completion
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Agent is booking your travel...", total=None)
                    for _ in range(100):
                        await asyncio.sleep(3)
                        r = await client.get(f"{server_url}/api/trips/{trip_id}")
                        status_data = r.json()
                        status = status_data["status"]

                        if status in ("booked", "escalated", "failed"):
                            progress.update(task, description=f"Status: {status}")
                            break

                _print_result(status_data)

        except httpx.ConnectError:
            console.print("[red]Could not connect to travel agent server.[/red]")
            console.print("Start the server with: [bold]uvicorn travel_agent.main:app --reload[/bold]")
            raise SystemExit(1)

    asyncio.run(_run())


@cli.command()
@click.argument("trip_id")
def status(trip_id):
    """Check the status of a trip by ID."""

    async def _run():
        import httpx
        server_url = os.environ.get("TRAVEL_AGENT_URL", "http://localhost:8000")
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{server_url}/api/trips/{trip_id}")
            if r.status_code == 404:
                console.print("[red]Trip not found.[/red]")
                return
            _print_result(r.json())

    asyncio.run(_run())


@cli.command()
def approvals():
    """List pending approval requests."""

    async def _run():
        import httpx
        server_url = os.environ.get("TRAVEL_AGENT_URL", "http://localhost:8000")
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{server_url}/api/escalations")
            data = r.json()

        table = Table(title="Pending Approvals")
        table.add_column("Escalation ID", style="cyan")
        table.add_column("Trip ID")
        table.add_column("Reason")
        table.add_column("Total ($)", justify="right")
        table.add_column("Status")

        for e in data.get("escalations", []):
            table.add_row(
                e["id"][:8] + "...",
                e["trip_id"][:8] + "...",
                e["reason"][:60],
                f"{e['details'].get('trip_total_usd', 0):.2f}",
                e["status"],
            )

        console.print(table)

    asyncio.run(_run())


@cli.command()
@click.argument("escalation_id")
@click.option("--approve/--reject", default=True, prompt="Approve this trip?")
@click.option("--email", default=None, help="Your email (for audit trail)")
def decide(escalation_id, approve, email):
    """Approve or reject a pending escalation."""

    async def _run():
        import httpx
        server_url = os.environ.get("TRAVEL_AGENT_URL", "http://localhost:8000")
        payload = {"approved": approve, "approver_email": email}
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{server_url}/api/escalations/{escalation_id}/decide",
                json=payload,
            )
            if r.ok:
                result = r.json()
                action = "approved" if approve else "rejected"
                console.print(f"[green]✓ Trip {action}.[/green] Trip ID: {result['trip_id']}")
            else:
                console.print(f"[red]Error: {r.text}[/red]")

    asyncio.run(_run())


def _print_result(data: dict):
    status = data.get("status", "unknown")
    color = {"booked": "green", "escalated": "yellow", "failed": "red"}.get(status, "blue")

    console.print(f"\n[{color} bold]Status: {status.upper()}[/{color} bold]")

    if data.get("total_cost_usd"):
        console.print(f"Total: [bold]${data['total_cost_usd']:.2f}[/bold]")

    if data.get("itinerary"):
        console.print(Panel(data["itinerary"], title="Itinerary", border_style=color))

    if data.get("escalation_id"):
        console.print(f"[yellow]Escalation ID: {data['escalation_id']}[/yellow]")
        console.print(f"Run: [bold]travel-agent decide {data['escalation_id']}[/bold] to approve/reject")

    if data.get("error"):
        console.print(f"[red]Error: {data['error']}[/red]")


if __name__ == "__main__":
    cli()
