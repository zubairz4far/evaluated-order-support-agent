from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

from toolguard.benchmark_runner import run_benchmark
from toolguard.final_holdout import (
    CANDIDATE_FREEZE_SHA,
    ROUTING_CORRECTION_FINAL_V1_SHA256,
    build_routing_correction_final_v1_benchmark,
)
from toolguard.providers import qwen_order_agent_provider


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the untouched routing-correction final holdout against the real Qwen adapter."
    )
    parser.add_argument(
        "--output",
        default="reports/routing_correction_final_qwen_v1.json",
        help="Path for machine-readable final evidence.",
    )
    parser.add_argument("--min-pass-rate", type=float, default=0.90)
    args = parser.parse_args()

    import accelerate
    import peft
    import torch
    import transformers

    benchmark = build_routing_correction_final_v1_benchmark()

    started = time.perf_counter()
    evidence = run_benchmark(
        benchmark,
        qwen_order_agent_provider(),
        min_pass_rate=args.min_pass_rate,
        require_zero_unexpected_tools=True,
    )
    elapsed = time.perf_counter() - started

    evidence["evaluation_contract"] = {
        "candidate_freeze_sha": CANDIDATE_FREEZE_SHA,
        "holdout_sha256": ROUTING_CORRECTION_FINAL_V1_SHA256,
        "holdout_policy": "untouched_after_candidate_freeze",
        "release_threshold": args.min_pass_rate,
        "require_zero_unexpected_tools": True,
    }
    evidence["model"] = {
        "base_model": "Qwen/Qwen3-1.7B",
        "adapter": "zubairz4far/qwen3-1.7b-tool-calling",
        "generation": {"do_sample": False, "max_new_tokens": 160},
    }
    evidence["runtime"] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "peft": peft.__version__,
        "accelerate": accelerate.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "elapsed_seconds": round(elapsed, 3),
        "github_sha": os.getenv("GITHUB_SHA"),
        "github_run_id": os.getenv("GITHUB_RUN_ID"),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "benchmark": evidence["benchmark"],
        "evaluation_contract": evidence["evaluation_contract"],
        "provider": evidence["provider"],
        "passed_cases": evidence["passed_cases"],
        "failed_cases": evidence["failed_cases"],
        "unexpected_tool_calls": evidence["unexpected_tool_calls"],
        "release_gate": evidence["release_gate"],
        "categories": evidence["categories"],
        "runtime": evidence["runtime"],
        "output": str(output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
