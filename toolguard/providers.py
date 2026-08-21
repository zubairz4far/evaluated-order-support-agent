from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Protocol
import uuid

from .models import AgentTrace


class ProviderAdapter(Protocol):
    name: str

    def run(self, source: AgentTrace, replay_id: str) -> AgentTrace: ...


@dataclass
class CallableProvider:
    name: str
    runner: Callable[[AgentTrace, str], AgentTrace]

    def run(self, source: AgentTrace, replay_id: str) -> AgentTrace:
        return self.runner(source, replay_id)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ProviderAdapter] = {}

    def register(self, provider: ProviderAdapter, *, replace: bool = False) -> None:
        if provider.name in self._providers and not replace:
            raise ValueError(f"provider already registered: {provider.name}")
        self._providers[provider.name] = provider

    def get(self, name: str) -> ProviderAdapter | None:
        return self._providers.get(name)

    def list(self) -> list[str]:
        return sorted(self._providers)


def replay_identity_provider() -> CallableProvider:
    def runner(source: AgentTrace, replay_id: str) -> AgentTrace:
        return replace(
            source,
            trace_id=f"trace_{uuid.uuid4().hex[:12]}",
            metadata={
                **source.metadata,
                "provider": "replay-identity",
                "replay_id": replay_id,
            },
        )

    return CallableProvider(name="replay-identity", runner=runner)


def order_agent_provider(name: str, model_factory: Callable[[], object]) -> CallableProvider:
    """Adapt an OrderSupportAgent model to the generic ToolGuard provider API.

    Passing `TransformersAdapter` as the factory exposes the published Qwen
    model without importing or loading heavy ML dependencies at platform start.
    """

    def runner(source: AgentTrace, replay_id: str) -> AgentTrace:
        if source.expected is None:
            raise ValueError("order-agent replay requires expected behavior")

        from order_agent.agent import OrderSupportAgent
        from .order_agent_adapter import audit_event_to_trace

        confirmed = bool(source.metadata.get("confirmed", False))
        agent = OrderSupportAgent(model_factory())
        agent.handle(source.input_text, confirmed=confirmed)
        trace = audit_event_to_trace(agent.audit_log[-1], source.expected)
        return replace(
            trace,
            metadata={
                **trace.metadata,
                "provider": name,
                "replay_id": replay_id,
            },
        )

    return CallableProvider(name=name, runner=runner)


def replay_order_agent_provider() -> CallableProvider:
    from order_agent.model import ReplayModel

    return order_agent_provider("order-agent-replay", ReplayModel)


def qwen_order_agent_provider() -> CallableProvider:
    from order_agent.model import TransformersAdapter

    return order_agent_provider("qwen-transformers", TransformersAdapter)


def default_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(replay_identity_provider())
    registry.register(replay_order_agent_provider())
    return registry
