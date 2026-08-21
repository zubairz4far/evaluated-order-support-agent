import importlib.util
import unittest

from toolguard.models import AgentTrace, ExpectedBehavior, ToolCall
from toolguard.serialization import trace_to_dict


HAS_PLATFORM = (
    importlib.util.find_spec("fastapi") is not None
    and importlib.util.find_spec("httpx") is not None
)


def good_trace(trace_id: str) -> AgentTrace:
    return AgentTrace(
        trace_id=trace_id,
        input_text="Check inventory for SKU GLM-001",
        route="tool",
        tool_calls=[
            ToolCall(
                name="check_inventory",
                arguments={"sku": "GLM-001"},
                success=True,
                latency_ms=18.0,
            )
        ],
        expected=ExpectedBehavior(
            route="tool",
            tool_name="check_inventory",
            arguments={"sku": "GLM-001"},
        ),
        latency_ms=25.0,
        input_tokens=20,
        output_tokens=12,
        cost_usd=0.001,
    )


def bad_trace(trace_id: str) -> AgentTrace:
    return AgentTrace(
        trace_id=trace_id,
        input_text="Check inventory for SKU GLM-001",
        route="answer",
        output_text="It is probably in stock.",
        expected=ExpectedBehavior(
            route="tool",
            tool_name="check_inventory",
            arguments={"sku": "GLM-001"},
        ),
        latency_ms=10.0,
    )


@unittest.skipUnless(HAS_PLATFORM, "platform extra is not installed")
class ToolGuardPlatformApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from toolguard.platform import create_app

        self.client = TestClient(create_app())

    def capture(self, trace: AgentTrace):
        response = self.client.post("/api/traces", json={"trace": trace_to_dict(trace)})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_health_and_dashboard(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["version"], "0.3.0")

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("ToolGuard", dashboard.text)
        self.assertIn("Recent traces", dashboard.text)
        self.assertIn("average_latency_ms", dashboard.text)
        self.assertIn("tool_error_rate", dashboard.text)

    def test_default_benchmark_registry_exposes_locked_order_agent_suite(self):
        response = self.client.get("/api/benchmarks/order-agent-replay")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["size"], 12)
        self.assertEqual(len(payload["cases"]), 12)

    def test_custom_benchmark_can_be_registered(self):
        response = self.client.post(
            "/api/benchmarks",
            json={
                "name": "smoke-suite",
                "description": "one-case API benchmark",
                "version": "1",
                "cases": [
                    {
                        "case_id": "smoke-01",
                        "input_text": "Explain what you can do",
                        "expected": {"route": "answer"},
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["size"], 1)
        fetched = self.client.get("/api/benchmarks/smoke-suite")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["cases"][0]["case_id"], "smoke-01")

    def test_provider_registry_exposes_real_agent_replay_adapter(self):
        response = self.client.get("/api/providers")
        self.assertEqual(response.status_code, 200)
        providers = response.json()["items"]
        self.assertIn("replay-identity", providers)
        self.assertIn("order-agent-replay", providers)

    def test_capture_and_analytics(self):
        self.capture(good_trace("trace-good"))
        response = self.client.get("/api/analytics")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["traces"], 1)
        self.assertEqual(payload["total_tokens"], 32)
        self.assertAlmostEqual(payload["total_cost_usd"], 0.001)

    def test_identity_provider_replays_stored_trace_without_regression(self):
        self.capture(good_trace("trace-source"))
        response = self.client.post(
            "/api/replays",
            json={
                "source_trace_id": "trace-source",
                "provider": "replay-identity",
                "candidate_label": "same-behavior",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["passed"])
        self.assertTrue(payload["replay_id"].startswith("replay_"))
        self.assertNotEqual(payload["candidate_trace_id"], "trace-source")

    def test_release_policy_blocks_regressed_candidate(self):
        self.capture(good_trace("baseline"))
        self.capture(bad_trace("candidate"))
        response = self.client.post(
            "/api/releases/check",
            json={
                "baseline_trace_ids": ["baseline"],
                "candidate_trace_ids": ["candidate"],
                "policy": {
                    "name": "strict-api",
                    "min_pass_rate": 1.0,
                    "max_pass_rate_drop": 0.0,
                    "max_metric_drop": 0.0,
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertFalse(payload["passed"])
        self.assertTrue(payload["failures"])
        self.assertEqual(payload["policy"]["name"], "strict-api")


if __name__ == "__main__":
    unittest.main()
