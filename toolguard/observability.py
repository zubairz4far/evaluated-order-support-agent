from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable
import uuid

from .analytics import aggregate_traces
from .evaluators import evaluate_trace
from .models import AgentTrace
from .regression import compare_runs
from .store import TraceStore
from .telemetry import NoopTelemetrySink, TelemetrySink


@dataclass(frozen=True)
class ReplayOutcome:
    replay_id: str
    source_trace_id: str
    candidate_trace_id: str
    candidate_label: str
    passed: bool
    comparison: dict[str, Any]


class ObservabilityPipeline:
    def __init__(
        self,
        store: TraceStore,
        telemetry: TelemetrySink | None = None,
    ) -> None:
        self.store = store
        self.telemetry = telemetry or NoopTelemetrySink()

    def capture(self, trace: AgentTrace, *, replay_id: str | None = None) -> str:
        self.store.save(trace, replay_id=replay_id)
        self.telemetry.emit(trace, replay_id=replay_id)
        return trace.trace_id

    def analytics(self, limit: int = 1000) -> dict[str, float | int | None]:
        return aggregate_traces(self.store.list(limit=limit))

    def replay(
        self,
        source_trace_id: str,
        candidate_label: str,
        runner: Callable[[AgentTrace, str], AgentTrace],
        *,
        max_pass_rate_drop: float = 0.0,
        max_metric_drop: float = 0.0,
    ) -> ReplayOutcome:
        source = self.store.get(source_trace_id)
        if source is None:
            raise KeyError(f"unknown source trace: {source_trace_id}")
        if source.expected is None:
            raise ValueError("replay requires a source trace with expected behavior")

        replay_id = f"replay_{uuid.uuid4().hex[:12]}"
        candidate = runner(source, replay_id)
        metadata = {
            **candidate.metadata,
            "replay_id": replay_id,
            "source_trace_id": source.trace_id,
            "candidate_label": candidate_label,
        }
        candidate = replace(
            candidate,
            expected=candidate.expected or source.expected,
            metadata=metadata,
        )
        self.capture(candidate, replay_id=replay_id)

        baseline_result = evaluate_trace(source)
        candidate_result = evaluate_trace(candidate)
        comparison = compare_runs(
            [baseline_result],
            [candidate_result],
            max_pass_rate_drop=max_pass_rate_drop,
            max_metric_drop=max_metric_drop,
        )
        return ReplayOutcome(
            replay_id=replay_id,
            source_trace_id=source.trace_id,
            candidate_trace_id=candidate.trace_id,
            candidate_label=candidate_label,
            passed=bool(comparison["passed"]),
            comparison=comparison,
        )
