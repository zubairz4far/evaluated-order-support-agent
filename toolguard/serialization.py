from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import AgentTrace, ExpectedBehavior, ToolCall


def trace_to_dict(trace: AgentTrace) -> dict[str, Any]:
    return asdict(trace)


def trace_from_dict(row: dict[str, Any]) -> AgentTrace:
    expected = row.get("expected")
    return AgentTrace(
        trace_id=row["trace_id"],
        input_text=row["input_text"],
        route=row["route"],
        output_text=row.get("output_text", ""),
        tool_calls=[ToolCall(**call) for call in row.get("tool_calls", [])],
        expected=ExpectedBehavior(**expected) if expected else None,
        confirmation_requested=row.get("confirmation_requested", False),
        latency_ms=row.get("latency_ms"),
        input_tokens=row.get("input_tokens"),
        output_tokens=row.get("output_tokens"),
        cost_usd=row.get("cost_usd"),
        metadata=row.get("metadata", {}),
    )
