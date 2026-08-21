# ToolGuard v0.3 Platform

ToolGuard v0.3 exposes the reliability and observability layers as a standalone FastAPI service.

## Run locally

```bash
pip install -e '.[platform]'
uvicorn toolguard.platform:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/dashboard` for the built-in dashboard and `http://localhost:8000/docs` for OpenAPI documentation.

The default backend is an in-memory trace store. No external service is required for a local demo.

## PostgreSQL

Install both platform and observability dependencies and set a database URL:

```bash
pip install -e '.[platform,observability]'
export TOOLGUARD_DATABASE_URL='postgresql://user:password@localhost:5432/toolguard'
uvicorn toolguard.platform:app --host 0.0.0.0 --port 8000
```

The current v0.3 backend creates the trace table/indexes on startup. Production hardening should replace this with explicit migrations.

## Release policy configuration

The default release policy is strict. It can be configured through environment variables:

```bash
export TOOLGUARD_POLICY_NAME='production'
export TOOLGUARD_MIN_PASS_RATE='0.98'
export TOOLGUARD_MAX_PASS_RATE_DROP='0.01'
export TOOLGUARD_MAX_METRIC_DROP='0.02'
```

These values become the default policy for `/api/releases/check`. A request can also supply an explicit policy.

## API surface

- `GET /health` — service health/version
- `GET /dashboard` — lightweight operational dashboard
- `GET /api/traces` — recent trace records
- `GET /api/traces/{trace_id}` — one trace
- `POST /api/traces` — capture a trace
- `GET /api/analytics` — latency/token/cost/tool-error aggregates
- `GET /api/providers` — available replay providers
- `GET /api/benchmarks` — benchmark registry summary
- `GET /api/benchmarks/{name}` — benchmark definition and expected behavior
- `POST /api/benchmarks` — register/replace a benchmark definition
- `POST /api/replays` — replay a stored trace through a provider and apply regression metrics
- `POST /api/releases/check` — compare stored baseline/candidate traces under a release policy

## Provider adapters

The platform provider contract is intentionally small:

```python
class ProviderAdapter(Protocol):
    name: str
    def run(self, source: AgentTrace, replay_id: str) -> AgentTrace: ...
```

The default registry includes:

- `replay-identity` — deterministic platform/replay validation
- `order-agent-replay` — executes the existing guarded order-support agent with `ReplayModel`

`qwen_order_agent_provider()` creates a lazy provider around the existing `TransformersAdapter`. It is not registered by default because instantiating the real model requires GPU-capable model dependencies.

## Benchmark registry

The default registry exposes the locked `order-agent-replay` suite with 12 independent expected behaviors. Custom benchmark definitions can be added through Python or `POST /api/benchmarks`.

Expected behavior remains independent from candidate model output; benchmark ground truth is never inferred from the model's own decision.

## Dashboard

The built-in dashboard deliberately has no frontend framework or CDN dependency. It reads the same public service endpoints used by API clients and displays:

- trace count
- average and p95 latency
- total token usage
- total modeled cost
- tool error count
- recent trace routes
- registered benchmarks

This keeps the portfolio demo reproducible while the core value remains in evaluation/replay infrastructure rather than frontend complexity.
