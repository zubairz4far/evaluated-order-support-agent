# Evaluated Order Support Agent + ToolGuard

A production-shaped project for safe LLM tool execution and **agent reliability engineering**. The guarded agent validates proposed calls before execution; ToolGuard evaluates traces, replays failures, blocks regressions, exposes operational diagnostics, and runs locked behavioral benchmarks through provider adapters.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/zubairz4far/evaluated-order-support-agent)

## Status

**ToolGuard v1.0 — locked agent-reliability benchmark + Qwen provider integration + safe public demo path.**

v1.0 adds:

- a **100-case locked reliability benchmark** compatible with the published Qwen tool schema;
- SHA-256 benchmark integrity verification;
- cached/lazy `qwen-transformers` provider integration;
- deterministic `qwen-contract-replay` CI provider using the same two tool names;
- one-click benchmark execution from the dashboard;
- benchmark execution API + CLI;
- category-level metrics, failure details and `PASS` / `BLOCK` release decisions;
- safe public demo mode that exposes only the deterministic benchmark while `/api/*` remains fail-closed;
- Render Blueprint support in addition to Docker, Compose and Kubernetes;
- live-container CI that validates authentication and the 100-case benchmark API.

## The locked 100-case benchmark

`agent-reliability-v1` is deliberately aligned to the real model adapter rather than a fictional larger tool catalog.

| Category | Cases | Expected behavior |
|---|---:|---|
| Valid order requests | 25 | exact `get_order` call + order ID |
| Valid inventory requests | 25 | exact `check_inventory` call + SKU |
| Missing required arguments | 20 | clarify without a tool call |
| Conceptual / no-tool requests | 15 | answer without a tool call |
| Prompt-injection / invented-tool requests | 15 | reject without a tool call |
| **Total** | **100** | locked behavior contract |

Frozen benchmark SHA-256:

```text
d005de66762008999db1a37469231fc5ae0554dad16f0336827265db35dafaa9
```

The runtime refuses to treat a changed `agent-reliability-v1` definition as the locked suite if its digest no longer matches this value.

## Evidence: deterministic contract vs real Qwen

Two evidence types are intentionally kept separate.

### 1. Deterministic Qwen-contract release gate

`qwen-contract-replay` mirrors the published adapter's `get_order` / `check_inventory` contract and is used for reproducible CI, container and API acceptance. It is **not presented as model accuracy**.

Run it with:

```bash
python -m toolguard.cli benchmark \
  --name agent-reliability-v1 \
  --provider qwen-contract-replay
```

The release gate requires the configured pass-rate threshold and, by default, zero unexpected tool calls on non-tool cases.

### 2. Real published Qwen adapter

`qwen-transformers` wraps:

- base: `Qwen/Qwen3-1.7B`
- adapter: `zubairz4far/qwen3-1.7b-tool-calling`

The provider is registered at platform startup **without loading the model**. On first use it loads once, caches the model, and serializes provider execution rather than reloading 1.7B parameters for every case.

Run the 100-case suite on suitable GPU hardware:

```bash
pip install -e '.[platform,model]'
export TOOLGUARD_API_KEY='local-secret'
uvicorn toolguard.platform:app --host 0.0.0.0 --port 8000

python -m toolguard.cli benchmark \
  --name agent-reliability-v1 \
  --provider qwen-transformers
```

No 100-case real-Qwen score is claimed until that GPU benchmark is actually executed and frozen.

The earlier guarded-agent benchmark **was** measured on a Kaggle T4 with the published adapter: **12/12 cases passed (100%)** in 31.19 seconds. See [`docs/BENCHMARK.md`](docs/BENCHMARK.md) and [`reports/real_model_benchmark_report.json`](reports/real_model_benchmark_report.json). That result applies only to its 12-case suite.

## One-click evaluation API

Protected execution endpoint:

```text
POST /api/benchmarks/{name}/run
```

Example:

```bash
curl -X POST http://localhost:8000/api/benchmarks/agent-reliability-v1/run \
  -H 'X-API-Key: local-secret' \
  -H 'Content-Type: application/json' \
  -d '{"provider":"qwen-contract-replay"}'
```

The result contains:

- benchmark name/version/SHA;
- provider;
- overall pass rate and evaluator metrics;
- category-level pass rates;
- failed-case details;
- unexpected-tool count;
- release-gate decision and reasons.

## Public portfolio demo mode

The checked-in `render.yaml` launches a deliberately constrained demo:

```text
TOOLGUARD_DEMO_MODE=true
```

In demo mode:

- `/` and `/dashboard` are public;
- `GET /demo/benchmark` runs only `agent-reliability-v1` through `qwen-contract-replay`;
- the UI does not ask visitors for an API key;
- `/api/*` remains fail-closed because no server API key is configured;
- no real Qwen weights are downloaded;
- no live commerce mutation is exposed;
- no persistent trace database is claimed.

This is analogous to an executable portfolio fixture, not a claim that the free demo host is the full GPU production topology.

## Authenticated platform

For the full API boundary:

```bash
pip install -e '.[platform]'
export TOOLGUARD_API_KEY='local-secret'
uvicorn toolguard.platform:app --host 0.0.0.0 --port 8000
```

Public endpoints:

- `GET /health`
- `GET /`
- `GET /dashboard`
- `GET /demo/benchmark` only when demo mode is enabled

Protected `/api/*` endpoints include:

- traces + analytics;
- provider registry;
- benchmark registry;
- benchmark execution;
- stored-trace replay;
- candidate-vs-baseline release checks.

Missing/wrong credentials return `401` when a server key is configured. If the server key is absent, protected routes return `503` rather than becoming public.

## Docker / Compose

The image runs as an unprivileged user and supports platform-assigned `$PORT` values.

```bash
export TOOLGUARD_API_KEY='replace-with-a-secret'
docker compose up --build
```

Compose adds PostgreSQL-backed **trace** persistence. Benchmark definitions and some release configuration remain process-local in v1.0.

## Kubernetes

The checked-in manifest remains intentionally conservative: one ToolGuard replica, `Recreate` strategy, non-root runtime, probes, resources, and Secret-backed API/database configuration.

```bash
kubectl create secret generic toolguard-secrets \
  --from-literal=api-key='replace-with-a-secret' \
  --from-literal=database-url='postgresql://USER:PASSWORD@HOST:5432/DB'

kubectl apply -f k8s/deployment.yaml
```

The manifest uses an example/local image name; it is **not** a claim that a registry image has been published.

## Architecture

```mermaid
flowchart TD
    U[User request] --> M[Model/provider adapter]
    M --> V[Schema + grounding validation]
    V --> P[Policy gate]
    P --> T[Allow-listed tool]
    T --> A[Audit trace]
    V --> R[Clarify / reject]
    A --> G[ToolGuard trace]
    G --> E[Deterministic evaluators]
    E --> REL[PASS / BLOCK release gate]
    G --> O[Latency / token / cost diagnostics]
    O --> DB[(PostgreSQL / in-memory)]
    DB --> API[Secured FastAPI platform]
    API --> B[Locked benchmark registry]
    B --> C[Qwen contract replay]
    B --> Q[Lazy cached Qwen3 adapter]
    API --> UI[Dashboard]
    DEMO[Public demo mode] --> C
```

## What this demonstrates

- LLM tool-schema design and guarded execution
- Qwen3 QLoRA integration
- provider abstraction and model lifecycle handling
- exact routing / tool / argument evaluation
- prompt-injection and unexpected-tool checks
- locked benchmark integrity
- replay and regression gates
- explicit candidate release policy
- PostgreSQL trace persistence
- OpenTelemetry-compatible observability
- FastAPI + OpenAPI
- API-key security boundary
- Docker / Compose / Kubernetes / Render deployment artifacts
- live container validation in GitHub Actions

## CI acceptance

The ToolGuard Gate now validates:

1. platform/unit tests;
2. deterministic trace evaluation and analytics;
3. original guarded-agent replay benchmark;
4. **locked 100-case Qwen-contract benchmark + SHA**;
5. intentional candidate regression blocking;
6. Docker Compose configuration;
7. non-root container build;
8. live `/health` and version check;
9. unauthorized protected API -> `401`;
10. Qwen provider registration;
11. live-container execution of the 100-case benchmark API.

## Remaining production gaps

v1.0 still does **not** claim a multi-tenant or horizontally scalable hosted SaaS. Remaining gaps include:

- queue/worker execution for expensive real-model benchmark runs;
- versioned database migrations instead of startup schema creation;
- persistence of benchmark definitions and release-policy history;
- distributed concurrency/idempotency before horizontal scaling;
- sustained load/soak testing;
- OIDC/workload identity and RBAC for enterprise deployments;
- a frozen 100-case real-Qwen GPU result.

No credentials, customer records, live commerce mutations, production traffic or production SLO claims are included.
