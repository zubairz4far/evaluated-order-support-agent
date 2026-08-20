# ToolGuard Core v0

ToolGuard is a provider-agnostic reliability layer for tool-using agents. It turns agent behavior into typed traces, evaluates those traces deterministically, and compares candidate runs against a baseline before release.

## Why this exists

A tool-using agent can fail even when its final text looks reasonable. Common failure modes include:

- choosing the wrong route (`tool`, `answer`, `clarify`, or `reject`)
- selecting the wrong tool
- inventing or corrupting tool arguments
- calling a tool on a non-tool request
- skipping a required confirmation gate
- executing a tool that reports failure
- regressing after a prompt/model/policy change

ToolGuard scores these behaviors separately so a model improvement cannot hide a regression in another dimension.

## Trace contract

```python
from toolguard import AgentTrace, ExpectedBehavior, ToolCall

trace = AgentTrace(
    trace_id="inventory-001",
    input_text="Check inventory for SKU-9",
    route="tool",
    tool_calls=[
        ToolCall(
            name="check_inventory",
            arguments={"sku": "SKU-9"},
            success=True,
            latency_ms=41.2,
        )
    ],
    expected=ExpectedBehavior(
        route="tool",
        tool_name="check_inventory",
        arguments={"sku": "SKU-9"},
    ),
    latency_ms=312.4,
    input_tokens=91,
    output_tokens=26,
    cost_usd=0.0004,
)
```

## Deterministic evaluation

```python
from toolguard import evaluate_trace

result = evaluate_trace(trace)
print(result.passed)
print(result.metrics)
print(result.failures)
```

Metrics currently include:

- route accuracy
- tool-selection accuracy
- exact argument accuracy
- key/value argument accuracy
- no-tool accuracy
- confirmation accuracy
- execution success
- per-trace reliability score

Latency, token usage, cost, and tool-call count are retained as diagnostics.

## Regression gate

A release candidate can be compared against an accepted baseline:

```python
from toolguard import compare_runs

comparison = compare_runs(
    baseline_results,
    candidate_results,
    max_pass_rate_drop=0.0,
    max_metric_drop=0.0,
)

if not comparison["passed"]:
    raise SystemExit(comparison["failures"])
```

The CLI returns a non-zero exit code when a candidate violates the configured regression budget, making it suitable for GitHub Actions.

```bash
python -m toolguard.cli evaluate traces.jsonl
python -m toolguard.cli compare baseline.jsonl candidate.jsonl
```

## v0 scope

This first version deliberately avoids model-provider dependencies. It is the core evaluation contract that future adapters can feed from Qwen, OpenAI, Anthropic, LangGraph, or custom agents.

Next layers:

1. adapter for the existing guarded order-support agent
2. persisted trace store
3. OpenTelemetry spans
4. failure taxonomy and replay IDs
5. benchmark registry
6. dashboard/API
7. GitHub release gate with stored baseline artifacts
