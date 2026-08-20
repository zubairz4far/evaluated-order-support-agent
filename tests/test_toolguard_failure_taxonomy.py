import unittest

from toolguard.failure_taxonomy import classify_failure, summarize_failures
from toolguard.models import EvaluationResult


class FailureTaxonomyTests(unittest.TestCase):
    def test_known_failure_prefix_is_classified(self):
        self.assertEqual(
            classify_failure("arguments: predicted arguments differ from expected"),
            "arguments",
        )

    def test_unknown_failure_is_other(self):
        self.assertEqual(classify_failure("something unexpected"), "other")

    def test_summary_counts_failure_categories(self):
        results = [
            EvaluationResult(
                trace_id="a",
                passed=False,
                score=0.5,
                metrics={},
                failures=["route: expected tool, got answer", "arguments: mismatch"],
            ),
            EvaluationResult(
                trace_id="b",
                passed=False,
                score=0.5,
                metrics={},
                failures=["arguments: mismatch"],
            ),
        ]
        self.assertEqual(
            summarize_failures(results),
            {"arguments": 2, "route": 1},
        )


if __name__ == "__main__":
    unittest.main()
