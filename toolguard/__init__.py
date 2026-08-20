"""ToolGuard: lightweight reliability evaluation primitives for tool-using agents."""

from .models import AgentTrace, EvaluationResult, ExpectedBehavior, ToolCall
from .evaluators import evaluate_trace
from .regression import compare_runs

__all__ = [
    "AgentTrace",
    "EvaluationResult",
    "ExpectedBehavior",
    "ToolCall",
    "evaluate_trace",
    "compare_runs",
]
