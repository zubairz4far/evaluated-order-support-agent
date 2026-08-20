import unittest

from toolguard import AgentTrace, ExpectedBehavior, ToolCall, evaluate_trace
from toolguard.regression import compare_runs


class ToolGuardEvaluationTests(unittest.TestCase):
    def test_valid_tool_call_passes(self):
        trace = AgentTrace(
            trace_id="ok-1",
            input_text="Check inventory for SKU-9",
            route="tool",
            tool_calls=[ToolCall("check_inventory", {"sku": "SKU-9"}, success=True)],
            expected=ExpectedBehavior(
                route="tool",
                tool_name="check_inventory",
                arguments={"sku": "SKU-9"},
            ),
        )
        result = evaluate_trace(trace)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.metrics["argument_kv_accuracy"], 1.0)

    def test_wrong_argument_is_diagnosed(self):
        trace = AgentTrace(
            trace_id="bad-arg",
            input_text="Check inventory for SKU-9",
            route="tool",
            tool_calls=[ToolCall("check_inventory", {"sku": "SKU-8"}, success=True)],
            expected=ExpectedBehavior(
                route="tool",
                tool_name="check_inventory",
                arguments={"sku": "SKU-9"},
            ),
        )
        result = evaluate_trace(trace)
        self.assertFalse(result.passed)
        self.assertEqual(result.metrics["tool_selection_accuracy"], 1.0)
        self.assertEqual(result.metrics["argument_exact_accuracy"], 0.0)
        self.assertTrue(any("arguments" in failure for failure in result.failures))

    def test_non_tool_route_penalizes_hallucinated_tool(self):
        trace = AgentTrace(
            trace_id="hallucination",
            input_text="What is inventory management?",
            route="answer",
            tool_calls=[ToolCall("check_inventory", {"sku": "invented"})],
            expected=ExpectedBehavior(route="answer"),
        )
        result = evaluate_trace(trace)
        self.assertFalse(result.passed)
        self.assertEqual(result.metrics["no_tool_accuracy"], 0.0)

    def test_confirmation_gate_is_scored(self):
        trace = AgentTrace(
            trace_id="confirm",
            input_text="Cancel order A-1",
            route="tool",
            tool_calls=[ToolCall("cancel_order", {"order_id": "A-1"}, success=True)],
            expected=ExpectedBehavior(
                route="tool",
                tool_name="cancel_order",
                arguments={"order_id": "A-1"},
                require_confirmation=True,
            ),
            confirmation_requested=False,
        )
        result = evaluate_trace(trace)
        self.assertFalse(result.passed)
        self.assertEqual(result.metrics["confirmation_accuracy"], 0.0)


class ToolGuardRegressionTests(unittest.TestCase):
    def _result(self, trace_id, passed, score, route_metric):
        from toolguard.models import EvaluationResult

        return EvaluationResult(
            trace_id=trace_id,
            passed=passed,
            score=score,
            metrics={"route_accuracy": route_metric},
        )

    def test_regression_gate_blocks_quality_drop(self):
        baseline = [
            self._result("b1", True, 1.0, 1.0),
            self._result("b2", True, 1.0, 1.0),
        ]
        candidate = [
            self._result("c1", True, 1.0, 1.0),
            self._result("c2", False, 0.0, 0.0),
        ]
        comparison = compare_runs(baseline, candidate)
        self.assertFalse(comparison["passed"])
        self.assertLess(comparison["deltas"]["pass_rate"], 0.0)

    def test_regression_budget_can_allow_small_drop(self):
        baseline = [
            self._result("b1", True, 1.0, 1.0),
            self._result("b2", True, 1.0, 1.0),
        ]
        candidate = [
            self._result("c1", True, 1.0, 1.0),
            self._result("c2", False, 0.8, 0.8),
        ]
        comparison = compare_runs(
            baseline,
            candidate,
            max_pass_rate_drop=0.5,
            max_metric_drop=0.2,
        )
        self.assertTrue(comparison["passed"])


if __name__ == "__main__":
    unittest.main()
