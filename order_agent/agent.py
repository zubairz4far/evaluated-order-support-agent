from __future__ import annotations

import time
import uuid
from typing import Any

from .model import ModelAdapter
from .tools import DemoOrderStore, ToolValidationError, build_registry
from .types import AgentResult


class OrderSupportAgent:
    def __init__(self, model: ModelAdapter, store: DemoOrderStore | None = None) -> None:
        self.model = model
        self.store = store or DemoOrderStore()
        self.registry = build_registry(self.store)
        self.audit_log: list[dict[str, Any]] = []

    def handle(self, message: str, *, confirmed: bool = False) -> AgentResult:
        started = time.perf_counter()
        trace_id = uuid.uuid4().hex[:12]
        decision = self.model.decide(message)
        status = decision.kind
        data = None
        response = decision.message
        try:
            if decision.kind == "tool_call":
                spec = self.registry.get(decision.tool or "")
                if spec is None:
                    raise ToolValidationError("tool is not allow-listed")
                spec.validate(decision.arguments)
                if spec.mutating and not confirmed:
                    status = "confirmation_required"
                    response = f"Confirm execution of {spec.name}."
                else:
                    data = spec.handler(**decision.arguments)
                    status = "executed"
                    response = f"Executed {spec.name}."
        except ToolValidationError as exc:
            status = "rejected"
            response = f"Tool call rejected: {exc}."
        self.audit_log.append({
            "trace_id": trace_id,
            "decision": decision.kind,
            "tool": decision.tool,
            "arguments": decision.arguments,
            "status": status,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        })
        return AgentResult(status=status, message=response, data=data, trace_id=trace_id)
