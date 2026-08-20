from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable

from .models import EvaluationResult


KNOWN_CATEGORIES = {
    "route",
    "tool",
    "arguments",
    "execution",
    "unexpected_tool_call",
    "confirmation",
}


def classify_failure(message: str) -> str:
    prefix = message.split(":", 1)[0].strip()
    return prefix if prefix in KNOWN_CATEGORIES else "other"


def summarize_failures(results: Iterable[EvaluationResult]) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for result in results:
        for failure in result.failures:
            counts[classify_failure(failure)] += 1
    return dict(sorted(counts.items()))
