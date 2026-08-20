import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ToolGuardCliTests(unittest.TestCase):
    def test_evaluate_example_fixture(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "toolguard.cli",
                "evaluate",
                str(ROOT / "examples" / "toolguard_traces.jsonl"),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["examples"], 3)
        self.assertEqual(payload["passed"], 3)
        self.assertEqual(payload["pass_rate"], 1.0)

    def test_compare_exits_nonzero_on_regression(self):
        good = {
            "trace_id": "base",
            "input_text": "Check inventory for SKU-9",
            "route": "tool",
            "tool_calls": [
                {
                    "name": "check_inventory",
                    "arguments": {"sku": "SKU-9"},
                    "success": True,
                }
            ],
            "expected": {
                "route": "tool",
                "tool_name": "check_inventory",
                "arguments": {"sku": "SKU-9"},
            },
        }
        bad = dict(good)
        bad["trace_id"] = "candidate"
        bad["route"] = "answer"
        bad["tool_calls"] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.jsonl"
            candidate = Path(tmpdir) / "candidate.jsonl"
            baseline.write_text(json.dumps(good) + "\n", encoding="utf-8")
            candidate.write_text(json.dumps(bad) + "\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "toolguard.cli",
                    "compare",
                    str(baseline),
                    str(candidate),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["passed"])
        self.assertTrue(payload["failures"])


if __name__ == "__main__":
    unittest.main()
