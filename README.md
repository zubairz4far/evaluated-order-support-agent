# Evaluated Order Support Agent + ToolGuard

A production-shaped portfolio project for safe LLM tool execution and **agent reliability engineering**. The guarded order-support agent validates proposed calls, applies policy checks, executes only allow-listed tools, records an audit trace, and is evaluated against locked behavioral benchmarks. ToolGuard evaluates those traces, replays failures, blocks regressions, exposes observability, and enforces release policies through a secured platform API.

## Status

**ToolGuard v0.4 — secured and container-validated platform hardening.**

v0.4 keeps the evaluated v0.3 platform and adds:

- fail-closed API-key protection for every `/api/*` route;
- explicit `401` behavior for missing/wrong credentials and `503` when server auth is not configured;
- non-root Python 3.12 container runtime;
- Docker Compose with PostgreSQL-backed trace persistence;
- Kubernetes deployment with Secret-backed configuration, probes, resources, and non-root security context;
- CI container build plus live health/authentication smoke testing.

Full v0.4 boundary and limitations: [docs/PLATFORM_V04.md](docs/PLATFORM_V04.md).

## What this demonstrates

- Typed tool schemas and strict argument validation
- Separation between model decisions and real-world execution
- Confirmation gates for destructive actions
- Prompt-injection and unknown-tool rejection
- Deterministic audit logs with latency and outcome
- Reproducible behavioral evaluation
- Provider-agnostic agent trace evaluation
- Candidate-vs-baseline regression gates for CI
- PostgreSQL-backed trace persistence
- OpenTelemetry-compatible agent/tool spans
- Latency, token, cost, and tool-error analytics
- Stored-trace replay with candidate comparison
- FastAPI service + OpenAPI contract
- Versioned benchmark registry
- Configurable release policies
- Lightweight operational dashboard
- Model/provider adapter interface
- API-key security boundary
- Docker / Compose / Kubernetes deployment artifacts
- Live container/auth smoke verification in CI

The default agent demo uses a deterministic `ReplayModel`, so it runs without a GPU or paid API key. `TransformersAdapter` loads the published Qwen3 QLoRA adapter for real inference on suitable hardware.

## Evaluated guarded-agent result

Measured on a Kaggle T4 with the published adapter: **12/12 guarded-agent cases passed (100%)** in 31.19 seconds.

See [docs/BENCHMARK.md](docs/BENCHMARK.md) and [reports/real_model_benchmark_report.json](reports/real_model_benchmark_report.json).

This 12-case result validates the guarded-agent benchmark only; it is not presented as broad model accuracy.

## ToolGuard CLI

ToolGuard evaluates behavior at the trace level instead of judging only the final answer. It scores routing, tool selection, argument correctness, no-tool behavior, confirmation gates, and execution while retaining operational diagnostics.

```bash
python -m toolguard.cli evaluate examples/toolguard_traces.jsonl
python -m toolguard.cli analytics examples/toolguard_traces.jsonl
python -m toolguard.cli compare \
  examples/toolguard_baseline.jsonl \
  examples/toolguard_candidate_regression.jsonl
```

The compare command exits non-zero when a candidate exceeds the configured regression budget, allowing it to act as a release gate in CI.

## Run ToolGuard v0.4 locally

Install the platform extra:

```bash
pip install -e '.[platform]'
export TOOLGUARD_API_KEY='local-secret'
uvicorn toolguard.platform:app --host 0.0.0.0 --port 8000
```

Public endpoints:

- `GET /health`
- `GET /`
- `GET /dashboard`

Protected endpoints require `X-API-Key`:

- `GET /api/traces`
- `POST /api/traces`
- `GET /api/analytics`
- `GET /api/providers`
- `GET /api/benchmarks`
- `POST /api/benchmarks`
- `POST /api/replays`
- `POST /api/releases/check`

Example:

```bash
curl -H 'X-API-Key: local-secret' http://localhost:8000/api/providers
```

If `TOOLGUARD_API_KEY` is absent, protected routes fail closed with HTTP `503` rather than becoming public.

## Docker Compose

Compose adds PostgreSQL-backed trace persistence and refuses to resolve the ToolGuard service without an API key.

```bash
export TOOLGUARD_API_KEY='replace-with-a-secret'
docker compose up --build
```

Then open:

- `http://localhost:8000/dashboard`
- `http://localhost:8000/docs`
- `http://localhost:8000/health`

## Kubernetes

The checked-in manifest is intentionally conservative: one ToolGuard replica, `Recreate` strategy, non-root runtime, health probes, resource bounds, and Secret-backed API key/database configuration.

```bash
kubectl create secret generic toolguard-secrets \
  --from-literal=api-key='replace-with-a-secret' \
  --from-literal=database-url='postgresql://USER:PASSWORD@HOST:5432/DB'

kubectl apply -f k8s/deployment.yaml
```

The manifest uses an example/local image name; it is **not** a claim that a public container registry image has been published.

## Existing agent demo

Run the deterministic Gradio demo:

```bash
pip install -e '.[demo]'
python app.py
```

Run with the real model on GPU-capable hardware:

```bash
pip install -e '.[model,demo]'
MODEL_MODE=transformers python app.py
```

Run the same locked benchmark against the real adapter:

```bash
python -m order_agent.eval --model transformers
```

The UI always displays its active mode. Mutations remain simulated in both modes.

## Safety model

The real-model path exposes the trained `get_order` and `check_inventory` tools. Calls execute only after schema validation and identifier grounding against the user's request. The replay path also demonstrates confirmation-gated simulated mutations. Unknown tools, malformed arguments, invented identifiers, and instruction-injection attempts are blocked before execution.

ToolGuard v0.4 separately protects its platform API with a shared API key. That is a basic service boundary, not enterprise identity; production deployments should normally add TLS, workload identity/OIDC, RBAC, secret rotation, and network policy.

## Architecture

```mermaid
flowchart TD
    U[User request] --> M[Model adapter]
    M --> V[Schema validation]
    V --> P[Policy gate]
    P --> T[Allow-listed tool]
    T --> A[Audit event]
    P --> C[Confirmation request]
    V --> R[Safe rejection]
    A --> G[ToolGuard trace]
    G --> E[Deterministic evaluators]
    E --> Q[Regression gate]
    G --> O[Observability pipeline]
    O --> DB[(PostgreSQL / In-memory)]
    O --> OT[OpenTelemetry]
    DB --> API[FastAPI platform]
    API --> AUTH[X-API-Key boundary]
    AUTH --> BR[Benchmark registry]
    AUTH --> RP[Replay providers]
    AUTH --> REL[Release policies]
    AUTH --> UI[Dashboard]
```

## CI acceptance

The ToolGuard Gate validates the behavior rather than only linting source files:

- ToolGuard platform tests;
- deterministic trace fixture evaluation;
- observability analytics;
- guarded order-agent replay benchmark;
- intentional regression blocking;
- Docker Compose configuration;
- Docker image build;
- live container `/health`;
- unauthenticated protected API returns `401`;
- authenticated protected API succeeds.

## Remaining production gaps

v0.4 deliberately does **not** claim a finished multi-tenant or horizontally scalable reliability service. Remaining work includes:

1. replace startup PostgreSQL schema creation with versioned migrations;
2. persist benchmark definitions and release-policy history;
3. move expensive real-model replays onto workers/queues;
4. add distributed idempotency/concurrency controls before horizontal scaling;
5. run sustained load/soak tests;
6. replace the shared key with production identity/RBAC where needed.

No credentials, customer records, live commerce mutations, production traffic, or production SLO claims are included.
