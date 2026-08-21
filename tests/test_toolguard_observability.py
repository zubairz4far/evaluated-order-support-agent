from __future__ import annotations

import unittest

from toolguard.analytics import aggregate_traces
from toolguard.models import AgentTrace, ExpectedBehavior, ToolCall
from toolguard.observability import ObservabilityPipeline
from toolguard.serialization import trace_from_dict, trace_to_dict
from toolguard.store import InMemoryTraceStore, PostgresTraceStore


class RecordingTelemetry:
    def __init__(self) -> None:
        self.events = []

    def emit(self, trace, *, replay_id=None) -> None:
        self.events.append((trace.trace_id, replay_id))


def good_trace(trace_id="trace-good"):
    return AgentTrace(
        trace_id=trace_id,
        input_text="Check order 12345",
        route="tool",
        output_text="Executed get_order.",
        tool_calls=[
            ToolCall(
                name="get_order",
                arguments={"order_id": "12345"},
                success=True,
                latency_ms=20.0,
            )
        ],
        expected=ExpectedBehavior(
            route="tool",
            tool_name="get_order",
            arguments={"order_id": "12345"},
        ),
        latency_ms=50.0,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.002,
    )


class SerializationTests(unittest.TestCase):
    def test_trace_round_trip(self):
        original = good_trace()
        restored = trace_from_dict(trace_to_dict(original))
        self.assertEqual(restored, original)


class StoreAndAnalyticsTests(unittest.TestCase):
    def test_in_memory_store_round_trip_and_order(self):
        store = InMemoryTraceStore()
        store.save(good_trace("one"))
        store.save(good_trace("two"))
        self.assertEqual(store.get("one").trace_id, "one")
        self.assertEqual([row.trace_id for row in store.list()], ["two", "one"])

    def test_aggregate_latency_tokens_cost_and_tool_errors(self):
        first = good_trace("one")
        second = AgentTrace(
            trace_id="two",
            input_text="Check order 67890",
            route="tool",
            tool_calls=[
                ToolCall(
                    name="get_order",
                    arguments={"order_id": "67890"},
                    success=False,
                    latency_ms=80.0,
                    error="timeout",
                )
            ],
            expected=ExpectedBehavior(
                route="tool",
                tool_name="get_order",
                arguments={"order_id": "67890"},
            ),
            latency_ms=150.0,
            input_tokens=20,
            output_tokens=10,
            cost_usd=0.004,
        )
        summary = aggregate_traces([first, second])
        self.assertEqual(summary["traces"], 2)
        self.assertEqual(summary["average_latency_ms"], 100.0)
        self.assertEqual(summary["p95_latency_ms"], 150.0)
        self.assertEqual(summary["total_tokens"], 45)
        self.assertAlmostEqual(summary["total_cost_usd"], 0.006)
        self.assertEqual(summary["tool_calls"], 2)
        self.assertEqual(summary["tool_error_rate"], 0.5)

    def test_postgres_schema_contains_replay_and_usage_columns(self):
        schema = PostgresTraceStore.SCHEMA_SQL
        self.assertIn("replay_id", schema)
        self.assertIn("payload JSONB", schema)
        self.assertIn("cost_usd", schema)


class ObservabilityPipelineTests(unittest.TestCase):
    def test_capture_persists_and_emits_telemetry(self):
        store = InMemoryTraceStore()
        telemetry = RecordingTelemetry()
        pipeline = ObservabilityPipeline(store, telemetry)
        trace = good_trace()
        pipeline.capture(trace)
        self.assertEqual(store.get(trace.trace_id), trace)
        self.assertEqual(telemetry.events, [(trace.trace_id, None)])

    def test_replay_passes_for_equivalent_candidate(self):
        store = InMemoryTraceStore()
        telemetry = RecordingTelemetry()
        pipeline = ObservabilityPipeline(store, telemetry)
        source = good_trace()
        pipeline.capture(source)

        def runner(original, replay_id):
            return good_trace("candidate-good")

        outcome = pipeline.replay(source.trace_id, "candidate-v2", runner)
        self.assertTrue(outcome.passed)
        self.assertTrue(outcome.replay_id.startswith("replay_"))
        candidate = store.get("candidate-good")
        self.assertEqual(candidate.metadata["source_trace_id"], source.trace_id)
        self.assertEqual(candidate.metadata["candidate_label"], "candidate-v2")
        self.assertEqual(candidate.metadata["replay_id"], outcome.replay_id)
        self.assertEqual(telemetry.events[-1], ("candidate-good", outcome.replay_id))

    def test_replay_blocks_argument_regression(self):
        store = InMemoryTraceStore()
        pipeline = ObservabilityPipeline(store)
        source = good_trace()
        pipeline.capture(source)

        def runner(original, replay_id):
            return AgentTrace(
                trace_id="candidate-bad",
                input_text=original.input_text,
                route="tool",
                tool_calls=[
                    ToolCall(
                        name="get_order",
                        arguments={"order_id": "99999"},
                        success=True,
                    )
                ],
                expected=original.expected,
            )

        outcome = pipeline.replay(source.trace_id, "candidate-regression", runner)
        self.assertFalse(outcome.passed)
        self.assertTrue(outcome.comparison["failures"])


if __name__ == "__main__":
    unittest.main()
