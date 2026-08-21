from __future__ import annotations

from typing import Protocol

from .models import AgentTrace


class TelemetrySink(Protocol):
    def emit(self, trace: AgentTrace, *, replay_id: str | None = None) -> None: ...


class NoopTelemetrySink:
    def emit(self, trace: AgentTrace, *, replay_id: str | None = None) -> None:
        return None


class OpenTelemetrySink:
    """Emit ToolGuard traces through an already configured OpenTelemetry provider.

    ToolGuard does not own exporter configuration. Applications can configure
    OTLP, console, or another exporter using the normal OpenTelemetry SDK.
    """

    def __init__(self, instrumentation_name: str = "toolguard") -> None:
        try:
            from opentelemetry import trace as otel_trace
        except ImportError as exc:
            raise RuntimeError(
                "OpenTelemetrySink requires the observability extra: "
                "pip install -e '.[observability]'"
            ) from exc
        self._tracer = otel_trace.get_tracer(instrumentation_name)

    def emit(self, trace: AgentTrace, *, replay_id: str | None = None) -> None:
        with self._tracer.start_as_current_span("toolguard.agent_trace") as span:
            span.set_attribute("toolguard.trace_id", trace.trace_id)
            span.set_attribute("toolguard.route", trace.route)
            span.set_attribute("toolguard.tool_call_count", len(trace.tool_calls))
            if replay_id:
                span.set_attribute("toolguard.replay_id", replay_id)
            if trace.latency_ms is not None:
                span.set_attribute("toolguard.latency_ms", float(trace.latency_ms))
            if trace.input_tokens is not None:
                span.set_attribute("toolguard.input_tokens", int(trace.input_tokens))
            if trace.output_tokens is not None:
                span.set_attribute("toolguard.output_tokens", int(trace.output_tokens))
            if trace.cost_usd is not None:
                span.set_attribute("toolguard.cost_usd", float(trace.cost_usd))
            if trace.tool_calls:
                span.set_attribute(
                    "toolguard.tool_names",
                    ",".join(call.name for call in trace.tool_calls),
                )

            for index, call in enumerate(trace.tool_calls):
                with self._tracer.start_as_current_span("toolguard.tool_call") as tool_span:
                    tool_span.set_attribute("toolguard.tool_index", index)
                    tool_span.set_attribute("toolguard.tool_name", call.name)
                    if call.success is not None:
                        tool_span.set_attribute("toolguard.tool_success", bool(call.success))
                    if call.latency_ms is not None:
                        tool_span.set_attribute("toolguard.tool_latency_ms", float(call.latency_ms))
                    if call.error:
                        tool_span.set_attribute("toolguard.tool_error", call.error)
