app:
  name: "AI Travel Agent"
  version: "0.1.0"
  debug: true

database:
  url: "sqlite+aiosqlite:///./travel_agent.db"

server:
  host: "0.0.0.0"
  port: 8000

agent:
  model: "claude-sonnet-4-20250514"
  max_iterations: 20
  temperature: 0.0

merchants:
  flight:
    url: "http://localhost:8001"
    name: "SkyWay Airlines"
  hotel:
    url: "http://localhost:8002"
    name: "StayWell Hotels"
  ground_transport:
    url: "http://localhost:8003"
    name: "RideRight Transport"

webhooks:
  base_url: "http://localhost:8000/webhooks"
