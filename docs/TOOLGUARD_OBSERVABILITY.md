# ToolGuard v0.2 Observability

ToolGuard v0.2 extends trace-level reliability evaluation into an operational observability layer for tool-using agents.

## Data flow

```mermaid
flowchart LR
    A[Agent / model run] --> T[AgentTrace]
    T --> P[ObservabilityPipeline]
    P --> S[TraceStore]
    P --> O[TelemetrySink]
    S --> PG[(PostgreSQL JSONB)]
    O --> OT[OpenTelemetry provider]
    PG --> AN[Latency / token / cost analytics]
    PG --> R[Replay by trace ID]
    R --> C[Candidate runner]
    C --> E[ToolGuard evaluator]
    E --> G[Regression policy]
```

## Trace storage

`InMemoryTraceStore` is used for deterministic tests and local experiments.

`PostgresTraceStore` stores the complete trace as JSONB while projecting common operational fields into indexed columns:

- trace ID
- replay ID
- capture timestamp
- latency
- input tokens
- output tokens
- cost

The PostgreSQL dependency is loaded only when the backend is used.

```python
from toolguard.store import PostgresTraceStore

store = PostgresTraceStore("postgresql://user:pass@localhost/toolguard")
store.init_schema()
```

Install production observability dependencies with:

```bash
pip install -e '.[observability]'
```

## OpenTelemetry

`OpenTelemetrySink` emits a parent `toolguard.agent_trace` span and child `toolguard.tool_call` spans. ToolGuard uses the application's configured global OpenTelemetry provider instead of owning exporter configuration.

Captured attributes include:

- `toolguard.trace_id`
- route
- replay ID
- latency
- input/output tokens
- cost
- tool names
- tool success/error/latency

This allows the same ToolGuard instrumentation to export through OTLP, console, or another OpenTelemetry-compatible backend.

## Analytics

Operational metrics can be computed directly from traces:

```bash
python -m toolguard.cli analytics examples/toolguard_traces.jsonl
```

The summary includes:

- trace count
- average latency
- p95 latency
- input/output/total tokens
- total and average cost
- tool call count
- tool error rate

ToolGuard never invents pricing. `cost_usd` is aggregated only when the model/provider adapter supplied it.

## Replay and candidate comparison

A stored trace with expected behavior can be replayed against any candidate runner implementing:

```python
candidate_trace = runner(source_trace, replay_id)
```

`ObservabilityPipeline.replay(...)`:

1. loads the original trace by ID;
2. generates a unique replay ID;
3. runs the candidate;
4. attaches source/candidate/replay metadata;
5. persists and emits the candidate trace;
6. evaluates baseline and candidate under the same ToolGuard metrics;
7. applies the configured regression budget.

This makes production failures or interesting traces reusable as regression tests instead of one-off incidents.

## Scope boundary

v0.2 is a Python reliability/observability library. It deliberately does not include an HTTP service or dashboard. Those are v0.3 concerns so the persistence, telemetry, analytics, and replay contracts remain stable before adding a UI/API layer.
