from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    success: Optional[bool] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class ExpectedBehavior:
    route: str
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    require_confirmation: bool = False

    def __post_init__(self) -> None:
        valid = {"tool", "answer", "clarify", "reject"}
        if self.route not in valid:
            raise ValueError(f"route must be one of {sorted(valid)}")
        if self.route == "tool" and not self.tool_name:
            raise ValueError("tool_name is required when route='tool'")


@dataclass(frozen=True)
class AgentTrace:
    trace_id: str
    input_text: str
    route: str
    output_text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    expected: Optional[ExpectedBehavior] = None
    confirmation_requested: bool = False
    latency_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        valid = {"tool", "answer", "clarify", "reject"}
        if self.route not in valid:
            raise ValueError(f"route must be one of {sorted(valid)}")
        if self.route == "tool" and not self.tool_calls:
            raise ValueError("tool route requires at least one tool call")


@dataclass(frozen=True)
class EvaluationResult:
    trace_id: str
    passed: bool
    score: float
    metrics: Dict[str, float]
    failures: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
