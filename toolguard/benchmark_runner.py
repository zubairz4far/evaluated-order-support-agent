from __future__ import annotations

from typing import Any
import uuid

from .benchmarks import (
    AGENT_RELIABILITY_V1_SHA256,
    BenchmarkDefinition,
    benchmark_sha256,
)
from .evaluators import evaluate_trace
from .models import AgentTrace, EvaluationResult
from .providers import ProviderAdapter
from .regression import summarize


def _category_summary(
    benchmark: BenchmarkDefinition,
    results: list[EvaluationResult],
) -> dict[str, dict[str, float | int]]:
    category_by_case = {
        case.case_id: case.metadata.get("category", "uncategorized")
        for case in benchmark.cases
    }
    grouped: dict[str, list[EvaluationResult]] = {}
    for result in results:
        category = category_by_case.get(result.trace_id, "uncategorized")
        grouped.setdefault(category, []).append(result)

    return {
        category: {
            "examples": len(items),
            "passed": sum(item.passed for item in items),
            "pass_rate": sum(item.passed for item in items) / len(items),
            "mean_score": sum(item.score for item in items) / len(items),
        }
        for category, items in sorted(grouped.items())
    }


def run_benchmark(
    benchmark: BenchmarkDefinition,
    provider: ProviderAdapter,
    *,
    min_pass_rate: float = 0.90,
    require_zero_unexpected_tools: bool = True,
) -> dict[str, Any]:
    """Execute a locked benchmark through a provider and return release evidence."""

    digest = benchmark_sha256(benchmark)
    if benchmark.name == "agent-reliability-v1" and digest != AGENT_RELIABILITY_V1_SHA256:
        raise ValueError(
            "agent-reliability-v1 benchmark digest changed: "
            f"expected {AGENT_RELIABILITY_V1_SHA256}, got {digest}"
        )

    results: list[EvaluationResult] = []
    failures: list[dict[str, Any]] = []
    unexpected_tool_calls = 0
    run_id = f"benchmark_{uuid.uuid4().hex[:12]}"

    for case in benchmark.cases:
        source = AgentTrace(
            trace_id=case.case_id,
            input_text=case.input_text,
            route="answer",
            expected=case.expected,
            metadata={**case.metadata, "benchmark_case_id": case.case_id},
        )
        candidate = provider.run(source, run_id)
        candidate = AgentTrace(
            trace_id=case.case_id,
            input_text=candidate.input_text,
            route=candidate.route,
            output_text=candidate.output_text,
            tool_calls=candidate.tool_calls,
            expected=candidate.expected,
            confirmation_requested=candidate.confirmation_requested,
            latency_ms=candidate.latency_ms,
            input_tokens=candidate.input_tokens,
            output_tokens=candidate.output_tokens,
            cost_usd=candidate.cost_usd,
            metadata={
                **candidate.metadata,
                "provider_trace_id": candidate.trace_id,
                "benchmark_run_id": run_id,
            },
        )
        result = evaluate_trace(candidate)
        results.append(result)
        if not result.passed:
            failures.append(
                {
                    "case_id": case.case_id,
                    "category": case.metadata.get("category", "uncategorized"),
                    "input_text": case.input_text,
                    "score": result.score,
                    "failures": result.failures,
                }
            )
        unexpected_tool_calls += sum(
            failure.startswith("unexpected_tool_call") for failure in result.failures
        )

    summary = summarize(results)
    categories = _category_summary(benchmark, results)
    release_failures: list[str] = []
    if summary["pass_rate"] < min_pass_rate:
        release_failures.append(
            f"pass_rate {summary['pass_rate']:.4f} < required {min_pass_rate:.4f}"
        )
    if require_zero_unexpected_tools and unexpected_tool_calls:
        release_failures.append(
            f"unexpected tool calls on non-tool cases: {unexpected_tool_calls}"
        )

    return {
        "benchmark": {
            "name": benchmark.name,
            "version": benchmark.version,
            "sha256": digest,
            "examples": benchmark.size,
        },
        "provider": provider.name,
        "run_id": run_id,
        "summary": summary,
        "categories": categories,
        "passed_cases": sum(item.passed for item in results),
        "failed_cases": len(failures),
        "unexpected_tool_calls": unexpected_tool_calls,
        "release_gate": {
            "decision": "PASS" if not release_failures else "BLOCK",
            "min_pass_rate": min_pass_rate,
            "require_zero_unexpected_tools": require_zero_unexpected_tools,
            "failures": release_failures,
        },
        "failures": failures,
    }
