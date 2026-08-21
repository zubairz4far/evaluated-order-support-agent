from __future__ import annotations

import math
from typing import Iterable

from .models import AgentTrace


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def aggregate_traces(traces: Iterable[AgentTrace]) -> dict[str, float | int | None]:
    rows = list(traces)
    latencies = [float(t.latency_ms) for t in rows if t.latency_ms is not None]
    costs = [float(t.cost_usd) for t in rows if t.cost_usd is not None]
    input_tokens = [int(t.input_tokens) for t in rows if t.input_tokens is not None]
    output_tokens = [int(t.output_tokens) for t in rows if t.output_tokens is not None]

    tool_calls = [call for trace in rows for call in trace.tool_calls]
    observed_tool_calls = [call for call in tool_calls if call.success is not None]
    failed_tool_calls = [call for call in observed_tool_calls if call.success is False]

    total_cost = sum(costs)
    return {
        "traces": len(rows),
        "average_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "total_input_tokens": sum(input_tokens),
        "total_output_tokens": sum(output_tokens),
        "total_tokens": sum(input_tokens) + sum(output_tokens),
        "total_cost_usd": total_cost,
        "average_cost_per_trace_usd": (total_cost / len(rows)) if rows else None,
        "tool_calls": len(tool_calls),
        "observed_tool_calls": len(observed_tool_calls),
        "tool_error_rate": (
            len(failed_tool_calls) / len(observed_tool_calls)
            if observed_tool_calls
            else None
        ),
    }
