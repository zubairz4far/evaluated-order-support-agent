import importlib.util
import unittest

from toolguard.models import AgentTrace, ExpectedBehavior, ToolCall
from toolguard.serialization import trace_to_dict


HAS_PLATFORM = (
    importlib.util.find_spec("fastapi") is not None
    and importlib.util.find_spec("httpx") is not None
)


API_KEY = "test-toolguard-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}


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

        self.client = TestClient(create_app(api_key=API_KEY))

    def capture(self, trace: AgentTrace):
        response = self.client.post(
            "/api/traces",
            json={"trace": trace_to_dict(trace)},
            headers=AUTH_HEADERS,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_health_and_dashboard(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["version"], "1.0.0")
        self.assertTrue(health.json()["api_auth_configured"])
        self.assertFalse(health.json()["demo_mode"])

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("ToolGuard v1.0", dashboard.text)
        self.assertIn("Run 100-case benchmark", dashboard.text)
        self.assertIn("Recent traces", dashboard.text)
        self.assertIn("X-API-Key", dashboard.text)

    def test_public_demo_exposes_only_safe_contract_benchmark(self):
        from fastapi.testclient import TestClient
        from toolguard.platform import create_app

        client = TestClient(create_app(demo_mode=True))
        health = client.get("/health")
        self.assertTrue(health.json()["demo_mode"])
        self.assertFalse(health.json()["api_auth_configured"])

        demo = client.get("/demo/benchmark")
        self.assertEqual(demo.status_code, 200, demo.text)
        payload = demo.json()
        self.assertEqual(payload["provider"], "qwen-contract-replay")
        self.assertEqual(payload["passed_cases"], 100)
        self.assertEqual(payload["release_gate"]["decision"], "PASS")

        protected = client.get("/api/providers")
        self.assertEqual(protected.status_code, 503)

    def test_demo_endpoint_is_disabled_in_authenticated_mode(self):
        response = self.client.get("/demo/benchmark")
        self.assertEqual(response.status_code, 404)

    def test_api_rejects_missing_and_wrong_key(self):
        missing = self.client.get("/api/providers")
        self.assertEqual(missing.status_code, 401)

        wrong = self.client.get(
            "/api/providers",
            headers={"X-API-Key": "wrong-key"},
        )
        self.assertEqual(wrong.status_code, 401)

    def test_api_fails_closed_without_server_key(self):
        from fastapi.testclient import TestClient
        from toolguard.platform import create_app

        client = TestClient(create_app())
        self.assertEqual(client.get("/health").status_code, 200)
        response = client.get("/api/providers")
        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["detail"])

    def test_default_benchmark_registry_exposes_locked_suites(self):
        legacy = self.client.get(
            "/api/benchmarks/order-agent-replay",
            headers=AUTH_HEADERS,
        )
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.json()["size"], 12)

        v1 = self.client.get(
            "/api/benchmarks/agent-reliability-v1",
            headers=AUTH_HEADERS,
        )
        self.assertEqual(v1.status_code, 200)
        payload = v1.json()
        self.assertEqual(payload["size"], 100)
        self.assertEqual(len(payload["cases"]), 100)
        self.assertEqual(
            payload["sha256"],
            "d005de66762008999db1a37469231fc5ae0554dad16f0336827265db35dafaa9",
        )

    def test_locked_100_case_benchmark_runs_through_api(self):
        response = self.client.post(
            "/api/benchmarks/agent-reliability-v1/run",
            headers=AUTH_HEADERS,
            json={"provider": "qwen-contract-replay"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["passed_cases"], 100)
        self.assertEqual(payload["failed_cases"], 0)
        self.assertEqual(payload["unexpected_tool_calls"], 0)
        self.assertEqual(payload["release_gate"]["decision"], "PASS")
        self.assertEqual(payload["categories"]["prompt_injection"]["passed"], 15)

    def test_custom_benchmark_can_be_registered(self):
        response = self.client.post(
            "/api/benchmarks",
            headers=AUTH_HEADERS,
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
        fetched = self.client.get(
            "/api/benchmarks/smoke-suite",
            headers=AUTH_HEADERS,
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["cases"][0]["case_id"], "smoke-01")

    def test_provider_registry_exposes_replay_and_qwen_adapters(self):
        response = self.client.get("/api/providers", headers=AUTH_HEADERS)
        self.assertEqual(response.status_code, 200)
        providers = response.json()["items"]
        self.assertIn("replay-identity", providers)
        self.assertIn("order-agent-replay", providers)
        self.assertIn("qwen-contract-replay", providers)
        self.assertIn("qwen-transformers", providers)

    def test_capture_and_analytics(self):
        self.capture(good_trace("trace-good"))
        response = self.client.get("/api/analytics", headers=AUTH_HEADERS)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["traces"], 1)
        self.assertEqual(payload["total_tokens"], 32)
        self.assertAlmostEqual(payload["total_cost_usd"], 0.001)

    def test_identity_provider_replays_stored_trace_without_regression(self):
        self.capture(good_trace("trace-source"))
        response = self.client.post(
            "/api/replays",
            headers=AUTH_HEADERS,
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
            headers=AUTH_HEADERS,
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
