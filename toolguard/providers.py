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


def default_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(replay_identity_provider())
    return registry
