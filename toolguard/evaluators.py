from __future__ import annotations

from typing import Any, Dict, List

from .models import AgentTrace, EvaluationResult


def _arg_accuracy(expected: Dict[str, Any], predicted: Dict[str, Any]) -> float:
    if not expected:
        return 1.0 if not predicted else 0.0
    matched = sum(1 for key, value in expected.items() if predicted.get(key) == value)
    return matched / len(expected)


def evaluate_trace(trace: AgentTrace) -> EvaluationResult:
    """Evaluate one agent trace against its expected behavior.

    The scorer is intentionally deterministic. It gives separate signals for
    routing, tool selection, arguments, confirmation behavior, and execution.
    """
    if trace.expected is None:
        raise ValueError("trace.expected is required for deterministic evaluation")

    expected = trace.expected
    failures: List[str] = []
    metrics: Dict[str, float] = {}

    route_ok = trace.route == expected.route
    metrics["route_accuracy"] = float(route_ok)
    if not route_ok:
        failures.append(f"route: expected {expected.route}, got {trace.route}")

    tool_name_ok = True
    arg_score = 1.0
    execution_ok = 1.0

    if expected.route == "tool":
        first_call = trace.tool_calls[0] if trace.tool_calls else None
        tool_name_ok = bool(first_call and first_call.name == expected.tool_name)
        metrics["tool_selection_accuracy"] = float(tool_name_ok)
        if not tool_name_ok:
            got = first_call.name if first_call else None
            failures.append(f"tool: expected {expected.tool_name}, got {got}")

        predicted_args = first_call.arguments if first_call else {}
        arg_score = _arg_accuracy(expected.arguments, predicted_args)
        metrics["argument_kv_accuracy"] = arg_score
        metrics["argument_exact_accuracy"] = float(predicted_args == expected.arguments)
        if predicted_args != expected.arguments:
            failures.append("arguments: predicted arguments differ from expected")

        if first_call and first_call.success is False:
            execution_ok = 0.0
            failures.append("execution: tool call reported failure")
        metrics["execution_success"] = execution_ok
    else:
        no_tool_ok = len(trace.tool_calls) == 0
        metrics["no_tool_accuracy"] = float(no_tool_ok)
        if not no_tool_ok:
            failures.append("unexpected_tool_call: non-tool route emitted a tool call")

    confirmation_ok = trace.confirmation_requested == expected.require_confirmation
    metrics["confirmation_accuracy"] = float(confirmation_ok)
    if not confirmation_ok:
        failures.append(
            "confirmation: expected "
            f"{expected.require_confirmation}, got {trace.confirmation_requested}"
        )

    core_values = [metrics["route_accuracy"], metrics["confirmation_accuracy"]]
    if expected.route == "tool":
        core_values.extend(
            [
                metrics["tool_selection_accuracy"],
                metrics["argument_exact_accuracy"],
                metrics["execution_success"],
            ]
        )
    else:
        core_values.append(metrics["no_tool_accuracy"])

    score = sum(core_values) / len(core_values)
    passed = all(value == 1.0 for value in core_values)

    diagnostics = {
        "latency_ms": trace.latency_ms,
        "input_tokens": trace.input_tokens,
        "output_tokens": trace.output_tokens,
        "cost_usd": trace.cost_usd,
        "tool_calls": len(trace.tool_calls),
    }

    return EvaluationResult(
        trace_id=trace.trace_id,
        passed=passed,
        score=score,
        metrics=metrics,
        failures=failures,
        diagnostics=diagnostics,
    )
