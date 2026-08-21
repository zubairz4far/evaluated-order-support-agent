from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .evaluators import evaluate_trace
from .models import AgentTrace
from .regression import compare_runs, summarize


@dataclass(frozen=True)
class ReleasePolicy:
    name: str = "strict"
    min_pass_rate: float = 1.0
    max_pass_rate_drop: float = 0.0
    max_metric_drop: float = 0.0

    def __post_init__(self) -> None:
        for field_name in ("min_pass_rate", "max_pass_rate_drop", "max_metric_drop"):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1")


def check_release(
    baseline: Iterable[AgentTrace],
    candidate: Iterable[AgentTrace],
    policy: ReleasePolicy | None = None,
) -> dict:
    policy = policy or ReleasePolicy()
    baseline_results = [evaluate_trace(trace) for trace in baseline]
    candidate_results = [evaluate_trace(trace) for trace in candidate]
    if not baseline_results or not candidate_results:
        raise ValueError("release checks require non-empty baseline and candidate traces")

    comparison = compare_runs(
        baseline_results,
        candidate_results,
        max_pass_rate_drop=policy.max_pass_rate_drop,
        max_metric_drop=policy.max_metric_drop,
    )
    candidate_summary = summarize(candidate_results)
    failures = list(comparison["failures"])
    if candidate_summary["pass_rate"] < policy.min_pass_rate:
        failures.append(
            f"candidate pass_rate {candidate_summary['pass_rate']:.4f} is below "
            f"minimum {policy.min_pass_rate:.4f}"
        )

    return {
        **comparison,
        "passed": not failures,
        "policy": {
            "name": policy.name,
            "min_pass_rate": policy.min_pass_rate,
            "max_pass_rate_drop": policy.max_pass_rate_drop,
            "max_metric_drop": policy.max_metric_drop,
        },
        "failures": failures,
    }
