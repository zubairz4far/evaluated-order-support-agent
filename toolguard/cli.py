from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import AgentTrace, ExpectedBehavior, ToolCall
from .evaluators import evaluate_trace
from .regression import compare_runs


def _load_trace(row):
    expected = row.get("expected")
    return AgentTrace(
        trace_id=row["trace_id"],
        input_text=row["input_text"],
        route=row["route"],
        output_text=row.get("output_text", ""),
        tool_calls=[ToolCall(**call) for call in row.get("tool_calls", [])],
        expected=ExpectedBehavior(**expected) if expected else None,
        confirmation_requested=row.get("confirmation_requested", False),
        latency_ms=row.get("latency_ms"),
        input_tokens=row.get("input_tokens"),
        output_tokens=row.get("output_tokens"),
        cost_usd=row.get("cost_usd"),
        metadata=row.get("metadata", {}),
    )


def _load_results(path):
    traces = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                traces.append(evaluate_trace(_load_trace(json.loads(line))))
    if not traces:
        raise SystemExit(f"no traces found in {path}")
    return traces


def main():
    parser = argparse.ArgumentParser(description="ToolGuard reliability evaluator")
    sub = parser.add_subparsers(dest="command", required=True)

    evaluate = sub.add_parser("evaluate", help="evaluate a JSONL trace set")
    evaluate.add_argument("traces")

    compare = sub.add_parser("compare", help="compare candidate traces to baseline")
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    compare.add_argument("--max-pass-rate-drop", type=float, default=0.0)
    compare.add_argument("--max-metric-drop", type=float, default=0.0)

    args = parser.parse_args()

    if args.command == "evaluate":
        results = _load_results(args.traces)
        payload = {
            "examples": len(results),
            "passed": sum(item.passed for item in results),
            "pass_rate": sum(item.passed for item in results) / len(results),
            "mean_score": sum(item.score for item in results) / len(results),
            "failures": [
                {"trace_id": item.trace_id, "failures": item.failures}
                for item in results
                if not item.passed
            ],
        }
        print(json.dumps(payload, indent=2))
        return

    baseline = _load_results(args.baseline)
    candidate = _load_results(args.candidate)
    payload = compare_runs(
        baseline,
        candidate,
        max_pass_rate_drop=args.max_pass_rate_drop,
        max_metric_drop=args.max_metric_drop,
    )
    print(json.dumps(payload, indent=2))
    raise SystemExit(0 if payload["passed"] else 1)


if __name__ == "__main__":
    main()
