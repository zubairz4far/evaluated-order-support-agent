from dataclasses import asdict
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel, Field
except ImportError as exc:
    raise RuntimeError(
        "ToolGuard platform requires: pip install -e '.[platform]'"
    ) from exc

from .benchmark_runner import run_benchmark
from .benchmarks import (
    BenchmarkCaseSpec,
    BenchmarkDefinition,
    BenchmarkRegistry,
    benchmark_sha256,
    default_benchmark_registry,
)
from .models import ExpectedBehavior
from .observability import ObservabilityPipeline
from .policies import ReleasePolicy, check_release
from .providers import ProviderRegistry, default_provider_registry
from .security import ApiKeyMiddleware
from .serialization import trace_from_dict, trace_to_dict
from .store import InMemoryTraceStore, TraceStore


class TraceRequest(BaseModel):
    trace: dict[str, Any]
    replay_id: str | None = None


class ReplayRequest(BaseModel):
    source_trace_id: str
    provider: str
    candidate_label: str | None = None
    max_pass_rate_drop: float = Field(default=0.0, ge=0.0, le=1.0)
    max_metric_drop: float = Field(default=0.0, ge=0.0, le=1.0)


class BenchmarkRunRequest(BaseModel):
    provider: str = "qwen-contract-replay"
    min_pass_rate: float = Field(default=0.90, ge=0.0, le=1.0)
    require_zero_unexpected_tools: bool = True


class PolicyRequest(BaseModel):
    name: str = "api-policy"
    min_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    max_pass_rate_drop: float = Field(default=0.0, ge=0.0, le=1.0)
    max_metric_drop: float = Field(default=0.0, ge=0.0, le=1.0)


class ReleaseCheckRequest(BaseModel):
    baseline_trace_ids: list[str]
    candidate_trace_ids: list[str]
    policy: PolicyRequest | None = None


class ExpectedRequest(BaseModel):
    route: str
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    require_confirmation: bool = False


class BenchmarkCaseRequest(BaseModel):
    case_id: str
    input_text: str
    expected: ExpectedRequest
    metadata: dict[str, str] = Field(default_factory=dict)


class BenchmarkRequest(BaseModel):
    name: str
    description: str = ""
    version: str = "1"
    cases: list[BenchmarkCaseRequest]
    replace: bool = False


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
    .controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
    select, button { background: #171b21; color: #f3f4f6; border: 1px solid #343b45; border-radius: 8px; padding: 9px 12px; }
    button { cursor: pointer; font-weight: 700; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #090b0e; padding: 14px; border-radius: 10px; }
    .hidden { display: none; }
  </style>
</head>
<body>
<main>
  <h1>ToolGuard v1.0</h1>
  <p class="muted">Agent reliability, replay, locked evaluation and release gates.</p>
  <p class="muted" id="mode-note"></p>

  <div class="section card">
    <h2>Run locked agent reliability benchmark</h2>
    <p class="muted">100 cases: tool routing, exact arguments, missing-argument clarification, no-tool behavior and prompt-injection rejection.</p>
    <div class="controls">
      <select id="provider"></select>
      <button id="run-benchmark">Run 100-case benchmark</button>
    </div>
    <pre id="benchmark-result">No benchmark run yet.</pre>
  </div>

  <div id="private-data">
    <div class="grid" id="metrics"></div>
    <div class="section card">
      <h2>Recent traces</h2>
      <table><thead><tr><th>Trace</th><th>Route</th><th>Latency</th><th>Cost</th></tr></thead><tbody id="traces"></tbody></table>
    </div>
    <div class="section card">
      <h2>Benchmarks</h2>
      <table><thead><tr><th>Name</th><th>Version</th><th>Cases</th><th>SHA-256</th></tr></thead><tbody id="benchmarks"></tbody></table>
    </div>
  </div>
</main>
<script>
const fmt = v => v === null || v === undefined ? '—' : v;
let apiKey = null;
let demoMode = false;
const authHeaders = () => apiKey ? {'X-API-Key': apiKey} : {};
const api = async (path, options={}) => {
  const response = await fetch(path, {...options, headers: {...authHeaders(), ...(options.headers || {})}});
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return response.json();
};
async function load() {
  const health = await fetch('/health').then(r => r.json());
  demoMode = Boolean(health.demo_mode);
  const select = document.getElementById('provider');
  if (demoMode) {
    document.getElementById('mode-note').textContent = 'Public demo mode: only the deterministic locked benchmark is exposed. Protected /api routes remain fail-closed.';
    document.getElementById('private-data').classList.add('hidden');
    select.innerHTML = '<option value="qwen-contract-replay" selected>qwen-contract-replay</option>';
    return;
  }

  document.getElementById('mode-note').textContent = 'Authenticated mode: API data and provider execution require X-API-Key.';
  apiKey = sessionStorage.getItem('toolguard_api_key');
  if (!apiKey) {
    apiKey = window.prompt('ToolGuard API key');
    if (apiKey) sessionStorage.setItem('toolguard_api_key', apiKey);
  }
  const [analytics, traces, benchmarks, providers] = await Promise.all([
    api('/api/analytics'),
    api('/api/traces?limit=20'),
    api('/api/benchmarks'),
    api('/api/providers')
  ]);
  const metrics = [
    ['Traces', analytics.traces],
    ['Avg latency ms', analytics.average_latency_ms],
    ['P95 latency ms', analytics.p95_latency_ms],
    ['Tokens', analytics.total_tokens],
    ['Cost USD', analytics.total_cost_usd],
    ['Tool error rate', analytics.tool_error_rate]
  ];
  document.getElementById('metrics').innerHTML = metrics.map(([k,v]) => `<div class="card"><div class="muted">${k}</div><div class="metric">${fmt(v)}</div></div>`).join('');
  document.getElementById('traces').innerHTML = traces.items.map(t => `<tr><td><code>${t.trace_id}</code></td><td>${t.route}</td><td>${fmt(t.latency_ms)}</td><td>${fmt(t.cost_usd)}</td></tr>`).join('');
  document.getElementById('benchmarks').innerHTML = benchmarks.items.map(b => `<tr><td>${b.name}</td><td>${b.version}</td><td>${b.size}</td><td><code>${b.sha256.slice(0,12)}…</code></td></tr>`).join('');
  select.innerHTML = providers.items.map(p => `<option value="${p}" ${p === 'qwen-contract-replay' ? 'selected' : ''}>${p}</option>`).join('');
}
document.getElementById('run-benchmark').addEventListener('click', async () => {
  const output = document.getElementById('benchmark-result');
  output.textContent = 'Running…';
  try {
    const payload = demoMode
      ? await fetch('/demo/benchmark').then(async r => { if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`); return r.json(); })
      : await api('/api/benchmarks/agent-reliability-v1/run', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({provider: document.getElementById('provider').value})
        });
    output.textContent = JSON.stringify({
      provider: payload.provider,
      benchmark: payload.benchmark,
      passed_cases: payload.passed_cases,
      failed_cases: payload.failed_cases,
      unexpected_tool_calls: payload.unexpected_tool_calls,
      release_gate: payload.release_gate,
      categories: payload.categories
    }, null, 2);
  } catch (err) {
    output.textContent = String(err);
  }
});
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
    api_key: str | None = None,
    demo_mode: bool = False,
):
    trace_store = store or InMemoryTraceStore()
    pipeline = ObservabilityPipeline(trace_store)
    provider_registry = providers or default_provider_registry()
    benchmark_registry = benchmarks or default_benchmark_registry()
    default_policy = release_policy or ReleasePolicy()

    app = FastAPI(
        title="ToolGuard API",
        version="1.0.0",
        description="Agent reliability, observability, locked evaluation, replay and release-gate service.",
    )
    app.add_middleware(ApiKeyMiddleware, api_key=api_key)
    app.state.store = trace_store
    app.state.pipeline = pipeline
    app.state.providers = provider_registry
    app.state.benchmarks = benchmark_registry
    app.state.release_policy = default_policy
    app.state.api_key_configured = bool(api_key)
    app.state.demo_mode = demo_mode

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "service": "toolguard",
            "version": "1.0.0",
            "api_auth_configured": bool(api_key),
            "demo_mode": demo_mode,
        }

    @app.get("/", response_class=HTMLResponse)
    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> str:
        return DASHBOARD_HTML

    @app.get("/demo/benchmark")
    def public_demo_benchmark() -> dict[str, Any]:
        if not demo_mode:
            raise HTTPException(status_code=404, detail="demo mode is disabled")
        benchmark = benchmark_registry.get("agent-reliability-v1")
        provider = provider_registry.get("qwen-contract-replay")
        if benchmark is None or provider is None:
            raise HTTPException(status_code=503, detail="demo benchmark is unavailable")
        return run_benchmark(
            benchmark,
            provider,
            min_pass_rate=1.0,
            require_zero_unexpected_tools=True,
        )

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
                "sha256": benchmark_sha256(item),
            }
            for item in benchmark_registry.list()
        ]
        return {"items": items, "count": len(items)}

    @app.post("/api/benchmarks", status_code=201)
    def register_benchmark(request: BenchmarkRequest) -> dict[str, Any]:
        try:
            benchmark = BenchmarkDefinition(
                name=request.name,
                description=request.description,
                version=request.version,
                cases=tuple(
                    BenchmarkCaseSpec(
                        case_id=case.case_id,
                        input_text=case.input_text,
                        expected=ExpectedBehavior(**case.expected.model_dump()),
                        metadata=case.metadata,
                    )
                    for case in request.cases
                ),
            )
            benchmark_registry.register(benchmark, replace=request.replace)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "name": benchmark.name,
            "version": benchmark.version,
            "size": benchmark.size,
            "sha256": benchmark_sha256(benchmark),
        }

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
            "sha256": benchmark_sha256(benchmark),
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

    @app.post("/api/benchmarks/{name}/run")
    def execute_benchmark(name: str, request: BenchmarkRunRequest) -> dict[str, Any]:
        benchmark = benchmark_registry.get(name)
        if benchmark is None:
            raise HTTPException(status_code=404, detail="benchmark not found")
        provider = provider_registry.get(request.provider)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider not found")
        try:
            return run_benchmark(
                benchmark,
                provider,
                min_pass_rate=request.min_pass_rate,
                require_zero_unexpected_tools=request.require_zero_unexpected_tools,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

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
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
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

    policy = ReleasePolicy(
        name=os.getenv("TOOLGUARD_POLICY_NAME", "strict"),
        min_pass_rate=float(os.getenv("TOOLGUARD_MIN_PASS_RATE", "1.0")),
        max_pass_rate_drop=float(os.getenv("TOOLGUARD_MAX_PASS_RATE_DROP", "0.0")),
        max_metric_drop=float(os.getenv("TOOLGUARD_MAX_METRIC_DROP", "0.0")),
    )
    demo_mode = os.getenv("TOOLGUARD_DEMO_MODE", "false").lower() in {"1", "true", "yes"}
    return create_app(
        store=store,
        release_policy=policy,
        api_key=os.getenv("TOOLGUARD_API_KEY"),
        demo_mode=demo_mode,
    )


app = app_from_environment()
