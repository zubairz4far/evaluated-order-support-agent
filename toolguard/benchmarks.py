from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .models import ExpectedBehavior


@dataclass(frozen=True)
class BenchmarkCaseSpec:
    case_id: str
    input_text: str
    expected: ExpectedBehavior
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkDefinition:
    name: str
    description: str
    cases: tuple[BenchmarkCaseSpec, ...]
    version: str = "1"

    @property
    def size(self) -> int:
        return len(self.cases)


class BenchmarkRegistry:
    def __init__(self) -> None:
        self._items: dict[str, BenchmarkDefinition] = {}

    def register(self, benchmark: BenchmarkDefinition, *, replace: bool = False) -> None:
        if benchmark.name in self._items and not replace:
            raise ValueError(f"benchmark already registered: {benchmark.name}")
        if not benchmark.cases:
            raise ValueError("benchmark must contain at least one case")
        case_ids = [case.case_id for case in benchmark.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("benchmark case_id values must be unique")
        self._items[benchmark.name] = benchmark

    def get(self, name: str) -> BenchmarkDefinition | None:
        return self._items.get(name)

    def list(self) -> list[BenchmarkDefinition]:
        return [self._items[name] for name in sorted(self._items)]


def build_order_agent_benchmark() -> BenchmarkDefinition:
    from .order_agent_benchmark import REPLAY_CASES

    cases = tuple(
        BenchmarkCaseSpec(
            case_id=f"order-agent-{index:02d}",
            input_text=case.prompt,
            expected=case.expected,
            metadata={"confirmed": str(case.confirmed).lower()},
        )
        for index, case in enumerate(REPLAY_CASES, 1)
    )
    return BenchmarkDefinition(
        name="order-agent-replay",
        description="Locked 12-case guarded order-support benchmark.",
        cases=cases,
        version="1",
    )


def default_benchmark_registry() -> BenchmarkRegistry:
    registry = BenchmarkRegistry()
    registry.register(build_order_agent_benchmark())
    return registry
