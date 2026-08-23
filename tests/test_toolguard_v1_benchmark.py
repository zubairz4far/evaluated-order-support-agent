import re
import unittest

from order_agent.types import Decision
from toolguard.benchmark_runner import run_benchmark
from toolguard.benchmarks import (
    AGENT_RELIABILITY_V1_SHA256,
    benchmark_sha256,
    build_agent_reliability_v1_benchmark,
    default_benchmark_registry,
)
from toolguard.providers import default_provider_registry, order_agent_provider


class RoutingAdversaryModel:
    """Test double that is correct only when an explicit identifier is grounded.

    Any ambiguous request that reaches this model becomes an invented tool call,
    forcing the pre-model routing policy to prove that it intercepted clarify
    and capability cases itself.
    """

    def decide(self, message):
        order = re.search(r"\b(\d{5})\b", message)
        sku = re.search(r"\b(GLM-\d+)\b", message, re.IGNORECASE)
        if order:
            return Decision("tool_call", tool="get_order", arguments={"order_id": order.group(1)})
        if sku:
            return Decision("tool_call", tool="check_inventory", arguments={"sku": sku.group(1).upper()})
        return Decision("tool_call", tool="check_inventory", arguments={"sku": "GLM-999"})


class ToolGuardV1BenchmarkTests(unittest.TestCase):
    def test_locked_benchmark_shape_and_digest(self):
        benchmark = build_agent_reliability_v1_benchmark()
        self.assertEqual(benchmark.size, 100)
        self.assertEqual(benchmark_sha256(benchmark), AGENT_RELIABILITY_V1_SHA256)

        categories = {}
        for case in benchmark.cases:
            category = case.metadata["category"]
            categories[category] = categories.get(category, 0) + 1
        self.assertEqual(
            categories,
            {
                "clarify_missing_argument": 20,
                "no_tool_answer": 15,
                "prompt_injection": 15,
                "tool_check_inventory": 25,
                "tool_get_order": 25,
            },
        )

    def test_qwen_contract_replay_passes_release_gate(self):
        benchmark = build_agent_reliability_v1_benchmark()
        provider = default_provider_registry().get("qwen-contract-replay")
        self.assertIsNotNone(provider)
        payload = run_benchmark(benchmark, provider)
        self.assertEqual(payload["passed_cases"], 100)
        self.assertEqual(payload["failed_cases"], 0)
        self.assertEqual(payload["unexpected_tool_calls"], 0)
        self.assertEqual(payload["release_gate"]["decision"], "PASS")
        self.assertEqual(payload["summary"]["pass_rate"], 1.0)
        self.assertEqual(payload["categories"]["prompt_injection"]["pass_rate"], 1.0)

    def test_routing_correction_development_suite_is_separate_and_balanced(self):
        benchmark = default_benchmark_registry().get("routing-correction-dev-v1")
        self.assertIsNotNone(benchmark)
        self.assertEqual(benchmark.size, 70)
        categories = {}
        for case in benchmark.cases:
            category = case.metadata["category"]
            categories[category] = categories.get(category, 0) + 1
        self.assertEqual(
            categories,
            {
                "clarify_missing_order_id": 15,
                "clarify_missing_sku": 15,
                "no_tool_capability": 15,
                "tool_get_order": 10,
                "tool_check_inventory": 10,
                "prompt_injection": 5,
            },
        )
        locked_prompts = {case.input_text for case in build_agent_reliability_v1_benchmark().cases}
        self.assertFalse(locked_prompts & {case.input_text for case in benchmark.cases})

    def test_routing_correction_policy_passes_development_suite_against_adversary(self):
        benchmark = default_benchmark_registry().get("routing-correction-dev-v1")
        provider = order_agent_provider("routing-adversary", RoutingAdversaryModel)
        self.assertIsNotNone(benchmark)
        payload = run_benchmark(benchmark, provider, min_pass_rate=1.0)
        self.assertEqual(payload["passed_cases"], 70, payload["failures"])
        self.assertEqual(payload["failed_cases"], 0)
        self.assertEqual(payload["unexpected_tool_calls"], 0)
        self.assertEqual(payload["release_gate"]["decision"], "PASS")

    def test_real_qwen_provider_is_registered_without_loading_model(self):
        providers = default_provider_registry()
        self.assertIn("qwen-transformers", providers.list())


if __name__ == "__main__":
    unittest.main()
