from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analytics import aggregate_traces
from .evaluators import evaluate_trace
from .regression import compare_runs
from .serialization import trace_from_dict


def _load_traces(path):
    traces = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                traces.append(trace_from_dict(json.loads(line)))
    if not traces:
        raise SystemExit(f"no traces found in {path}")
    return traces


def _load_results(path):
    return [evaluate_trace(trace) for trace in _load_traces(path)]


def main():
    parser = argparse.ArgumentParser(description="ToolGuard reliability evaluator")
    sub = parser.add_subparsers(dest="command", required=True)

    evaluate = sub.add_parser("evaluate", help="evaluate a JSONL trace set")
    evaluate.add_argument("traces")

    analytics = sub.add_parser("analytics", help="summarize latency/token/cost telemetry")
    analytics.add_argument("traces")

    compare = sub.add_parser("compare", help="compare candidate traces to baseline")
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    compare.add_argument("--max-pass-rate-drop", type=float, default=0.0)
    compare.add_argument("--max-metric-drop", type=float, default=0.0)

    args = parser.parse_args()

    if args.command == "analytics":
        print(json.dumps(aggregate_traces(_load_traces(args.traces)), indent=2))
        return

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
