from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .benchmarks import BenchmarkRegistry, default_benchmark_registry
from .observability import ObservabilityPipeline
from .policies import ReleasePolicy, check_release
from .providers import ProviderRegistry, default_provider_registry
from .serialization import trace_from_dict, trace_to_dict
from .store import InMemoryTraceStore, TraceStore


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ToolGuard</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
    body { margin: 0; background: #0b0d10; color: #f3f4f6; }
    main { max-width: 1120px; margin: 0 auto; padding: 40px 24px 64px; }
    h1 { font-size: 32px; margin: 0; letter-spacing: -0.03em; }
    .muted { color: #9ca3af; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 28px 0; }
    .card { border: 1px solid #252a31; border-radius: 14px; background: #11151a; padding: 16px; }
    .metric { font-size: 26px; font-weight: 700; margin-top: 8px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { text-align: left; padding: 11px 8px; border-bottom: 1px solid #252a31; }
    th { color: #9ca3af; font-weight: 500; }
    code { color: #c7d2fe; }
    .section { margin-top: 28px; }
  </style>
</head>
<body>
<main>
  <h1>ToolGuard</h1>
  <p class="muted">Agent reliability, observability, replay and release gates.</p>
  <div class="grid" id="metrics"></div>
  <div class="section card">
    <h2>Recent traces</h2>
    <table><thead><tr><th>Trace</th><th>Route</th><th>Latency</th><th>Cost</th></tr></thead><tbody id="traces"></tbody></table>
  </div>
  <div class="section card">
    <h2>Benchmarks</h2>
    <table><thead><tr><th>Name</th><th>Version</th><th>Cases</th></tr></thead><tbody id="benchmarks"></tbody></table>
  </div>
</main>
<script>
const fmt = v => v === null || v === undefined ? '—' : v;
async function load() {
  const [analytics, traces, benchmarks] = await Promise.all([
    fetch('/api/analytics').then(r => r.json()),
    fetch('/api/traces?limit=20').then(r => r.json()),
    fetch('/api/benchmarks').then(r => r.json())
  ]);
  const metrics = [
    ['Traces', analytics.traces],
    ['Avg latency ms', analytics.avg_latency_ms],
    ['P95 latency ms', analytics.p95_latency_ms],
    ['Tokens', analytics.total_tokens],
    ['Cost USD', analytics.total_cost_usd],
    ['Tool errors', analytics.tool_errors]
  ];
  document.getElementById('metrics').innerHTML = metrics.map(([k,v]) => `<div class="card"><div class="muted">${k}</div><div class="metric">${fmt(v)}</div></div>`).join('');
  document.getElementById('traces').innerHTML = traces.items.map(t => `<tr><td><code>${t.trace_id}</code></td><td>${t.route}</td><td>${fmt(t.latency_ms)}</td><td>${fmt(t.cost_usd)}</td></tr>`).join('');
  document.getElementById('benchmarks').innerHTML = benchmarks.items.map(b => `<tr><td>${b.name}</td><td>${b.version}</td><td>${b.size}</td></tr>`).join('');
}
load().catch(err => { document.body.insertAdjacentHTML('beforeend', `<pre>${err}</pre>`); });
</script>
</body>
</html>"""


def create_app(
    *,
    store: TraceStore | None = None,
    providers: ProviderRegistry | None = None,
    benchmarks: BenchmarkRegistry | None = None,
    release_policy: ReleasePolicy | None = None,
):
    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.responses import HTMLResponse
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError(
            "ToolGuard platform requires: pip install -e '.[platform]'"
        ) from exc

    trace_store = store or InMemoryTraceStore()
    pipeline = ObservabilityPipeline(trace_store)
    provider_registry = providers or default_provider_registry()
    benchmark_registry = benchmarks or default_benchmark_registry()
    default_policy = release_policy or ReleasePolicy()

    class TraceRequest(BaseModel):
        trace: dict[str, Any]
        replay_id: str | None = None

    class ReplayRequest(BaseModel):
        source_trace_id: str
        provider: str
        candidate_label: str | None = None
        max_pass_rate_drop: float = Field(default=0.0, ge=0.0, le=1.0)
        max_metric_drop: float = Field(default=0.0, ge=0.0, le=1.0)

    class PolicyRequest(BaseModel):
        name: str = "api-policy"
        min_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
        max_pass_rate_drop: float = Field(default=0.0, ge=0.0, le=1.0)
        max_metric_drop: float = Field(default=0.0, ge=0.0, le=1.0)

    class ReleaseCheckRequest(BaseModel):
        baseline_trace_ids: list[str]
        candidate_trace_ids: list[str]
        policy: PolicyRequest | None = None

    app = FastAPI(
        title="ToolGuard API",
        version="0.3.0",
        description="Agent reliability, observability, replay and release-gate service.",
    )
    app.state.store = trace_store
    app.state.pipeline = pipeline
    app.state.providers = provider_registry
    app.state.benchmarks = benchmark_registry
    app.state.release_policy = default_policy

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "toolguard", "version": "0.3.0"}

    @app.get("/", response_class=HTMLResponse)
    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> str:
        return DASHBOARD_HTML

    @app.get("/api/traces")
    def list_traces(limit: int = Query(default=100, ge=1, le=5000)) -> dict[str, Any]:
        items = [trace_to_dict(trace) for trace in trace_store.list(limit=limit)]
        return {"items": items, "count": len(items)}

    @app.get("/api/traces/{trace_id}")
    def get_trace(trace_id: str) -> dict[str, Any]:
        trace = trace_store.get(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="trace not found")
        return trace_to_dict(trace)

    @app.post("/api/traces", status_code=201)
    def capture_trace(request: TraceRequest) -> dict[str, str]:
        try:
            trace = trace_from_dict(request.trace)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"invalid trace: {exc}") from exc
        pipeline.capture(trace, replay_id=request.replay_id)
        return {"trace_id": trace.trace_id}

    @app.get("/api/analytics")
    def analytics(limit: int = Query(default=1000, ge=1, le=10000)) -> dict[str, Any]:
        return pipeline.analytics(limit=limit)

    @app.get("/api/providers")
    def list_providers() -> dict[str, Any]:
        return {"items": provider_registry.list()}

    @app.get("/api/benchmarks")
    def list_benchmarks() -> dict[str, Any]:
        items = [
            {
                "name": item.name,
                "description": item.description,
                "version": item.version,
                "size": item.size,
            }
            for item in benchmark_registry.list()
        ]
        return {"items": items, "count": len(items)}

    @app.get("/api/benchmarks/{name}")
    def get_benchmark(name: str) -> dict[str, Any]:
        benchmark = benchmark_registry.get(name)
        if benchmark is None:
            raise HTTPException(status_code=404, detail="benchmark not found")
        return {
            "name": benchmark.name,
            "description": benchmark.description,
            "version": benchmark.version,
            "size": benchmark.size,
            "cases": [
                {
                    "case_id": case.case_id,
                    "input_text": case.input_text,
                    "expected": asdict(case.expected),
                    "metadata": case.metadata,
                }
                for case in benchmark.cases
            ],
        }

    @app.post("/api/replays")
    def replay(request: ReplayRequest) -> dict[str, Any]:
        provider = provider_registry.get(request.provider)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider not found")
        try:
            outcome = pipeline.replay(
                request.source_trace_id,
                request.candidate_label or provider.name,
                provider.run,
                max_pass_rate_drop=request.max_pass_rate_drop,
                max_metric_drop=request.max_metric_drop,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return asdict(outcome)

    @app.post("/api/releases/check")
    def release_check(request: ReleaseCheckRequest) -> dict[str, Any]:
        def resolve(trace_ids: list[str]):
            traces = []
            missing = []
            for trace_id in trace_ids:
                trace = trace_store.get(trace_id)
                if trace is None:
                    missing.append(trace_id)
                else:
                    traces.append(trace)
            if missing:
                raise HTTPException(
                    status_code=404,
                    detail={"message": "traces not found", "trace_ids": missing},
                )
            return traces

        baseline = resolve(request.baseline_trace_ids)
        candidate = resolve(request.candidate_trace_ids)
        policy = (
            ReleasePolicy(**request.policy.model_dump())
            if request.policy is not None
            else default_policy
        )
        try:
            return check_release(baseline, candidate, policy)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


def app_from_environment():
    import os

    from .store import PostgresTraceStore

    dsn = os.getenv("TOOLGUARD_DATABASE_URL")
    if dsn:
        store = PostgresTraceStore(dsn)
        store.init_schema()
    else:
        store = InMemoryTraceStore()
    return create_app(store=store)


app = app_from_environment()
