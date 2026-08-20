from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Iterable, List

from .models import EvaluationResult


def summarize(results: Iterable[EvaluationResult]) -> Dict[str, float]:
    items = list(results)
    if not items:
        raise ValueError("at least one evaluation result is required")

    metric_names = sorted({name for item in items for name in item.metrics})
    summary: Dict[str, float] = {
        "examples": float(len(items)),
        "pass_rate": sum(item.passed for item in items) / len(items),
        "mean_score": sum(item.score for item in items) / len(items),
    }

    for name in metric_names:
        values = [item.metrics[name] for item in items if name in item.metrics]
        if values:
            summary[name] = sum(values) / len(values)

    return summary


def compare_runs(
    baseline: Iterable[EvaluationResult],
    candidate: Iterable[EvaluationResult],
    *,
    max_pass_rate_drop: float = 0.0,
    max_metric_drop: float = 0.0,
) -> Dict[str, object]:
    """Compare a candidate evaluation run with a baseline.

    A release passes only if pass rate and every shared metric stay within the
    configured regression budget. Positive deltas are improvements.
    """
    base = summarize(baseline)
    cand = summarize(candidate)

    shared_metrics = sorted(
        key
        for key in set(base) & set(cand)
        if key not in {"examples"}
    )
    deltas = {name: cand[name] - base[name] for name in shared_metrics}

    failures: List[str] = []
    if deltas.get("pass_rate", 0.0) < -max_pass_rate_drop:
        failures.append(
            f"pass_rate regressed by {abs(deltas['pass_rate']):.4f} "
            f"(budget {max_pass_rate_drop:.4f})"
        )

    for name, delta in deltas.items():
        if name in {"pass_rate", "mean_score"}:
            continue
        if delta < -max_metric_drop:
            failures.append(
                f"{name} regressed by {abs(delta):.4f} "
                f"(budget {max_metric_drop:.4f})"
            )

    return {
        "passed": not failures,
        "baseline": base,
        "candidate": cand,
        "deltas": deltas,
        "failures": failures,
    }
