from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


DecisionKind = Literal["tool_call", "answer", "clarify", "reject"]


@dataclass(frozen=True)
class Decision:
    kind: DecisionKind
    message: str = ""
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    status: str
    message: str
    data: dict[str, Any] | None = None
    trace_id: str = ""
