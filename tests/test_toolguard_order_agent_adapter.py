import unittest

from order_agent.agent import OrderSupportAgent
from order_agent.model import ReplayModel
from toolguard import ExpectedBehavior, evaluate_trace
from toolguard.order_agent_adapter import audit_event_to_trace
from toolguard.order_agent_benchmark import REPLAY_CASES, run_cases


class OrderAgentAuditContractTests(unittest.TestCase):
    def test_audit_event_contains_trace_context(self):
        agent = OrderSupportAgent(ReplayModel())
        result = agent.handle("Check order 12345")
        event = agent.audit_log[-1]

        self.assertEqual(event["trace_id"], result.trace_id)
        self.assertEqual(event["input_text"], "Check order 12345")
        self.assertEqual(event["output_text"], result.message)
        self.assertFalse(event["confirmed"])
        self.assertIn("latency_ms", event)


class OrderAgentToolGuardAdapterTests(unittest.TestCase):
    def test_confirmation_required_maps_to_tool_route(self):
        agent = OrderSupportAgent(ReplayModel())
        agent.handle("Cancel order 67890")
        expected = ExpectedBehavior(
            route="tool",
            tool_name="cancel_order",
            arguments={"order_id": "67890"},
            require_confirmation=True,
        )
        trace = audit_event_to_trace(agent.audit_log[-1], expected)
        result = evaluate_trace(trace)

        self.assertEqual(trace.route, "tool")
        self.assertTrue(trace.confirmation_requested)
        self.assertTrue(result.passed)

    def test_clarification_has_no_tool_call(self):
        agent = OrderSupportAgent(ReplayModel())
        agent.handle("Check inventory")
        trace = audit_event_to_trace(
            agent.audit_log[-1], ExpectedBehavior(route="clarify")
        )
        result = evaluate_trace(trace)

        self.assertEqual(trace.route, "clarify")
        self.assertEqual(trace.tool_calls, [])
        self.assertTrue(result.passed)

    def test_full_replay_agent_benchmark_passes_through_toolguard(self):
        results = run_cases(ReplayModel(), REPLAY_CASES)
        self.assertEqual(len(results), 12)
        self.assertEqual(sum(item.passed for item in results), 12)
        self.assertTrue(all(item.score == 1.0 for item in results))


if __name__ == "__main__":
    unittest.main()
