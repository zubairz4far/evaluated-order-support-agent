from __future__ import annotations

from typing import Any, Mapping

from .models import AgentTrace, ExpectedBehavior, ToolCall


_STATUS_TO_ROUTE = {
    "executed": "tool",
    "confirmation_required": "tool",
    "clarify": "clarify",
    "reject": "reject",
    "answer": "answer",
}


def audit_event_to_trace(
    event: Mapping[str, Any],
    expected: ExpectedBehavior,
) -> AgentTrace:
    """Convert one OrderSupportAgent audit event into a ToolGuard trace.

    Expected behavior is supplied independently by the benchmark. The adapter
    never infers ground truth from the model's own decision.
    """
    status = str(event.get("status", ""))
    try:
        route = _STATUS_TO_ROUTE[status]
    except KeyError as exc:
        raise ValueError(f"unsupported order-agent status: {status!r}") from exc

    tool_calls = []
    if event.get("decision") == "tool_call" and event.get("tool"):
        success = True if status == "executed" else None
        if status == "reject":
            success = False
        tool_calls.append(
            ToolCall(
                name=str(event["tool"]),
                arguments=dict(event.get("arguments") or {}),
                success=success,
            )
        )

    return AgentTrace(
        trace_id=str(event["trace_id"]),
        input_text=str(event.get("input_text", "")),
        output_text=str(event.get("output_text", "")),
        route=route,
        tool_calls=tool_calls,
        expected=expected,
        confirmation_requested=status == "confirmation_required",
        latency_ms=float(event["latency_ms"]) if event.get("latency_ms") is not None else None,
        metadata={
            "source": "evaluated-order-support-agent",
            "agent_status": status,
            "confirmed": bool(event.get("confirmed", False)),
            "model_decision": event.get("decision"),
        },
    )
