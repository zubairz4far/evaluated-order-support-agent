from __future__ import annotations

import time
import uuid
import re
from typing import Any

from .model import ModelAdapter
from .tools import DemoOrderStore, ToolValidationError, build_registry
from .types import AgentResult, Decision


class OrderSupportAgent:
    def __init__(self, model: ModelAdapter, store: DemoOrderStore | None = None) -> None:
        self.model = model
        self.store = store or DemoOrderStore()
        self.registry = build_registry(self.store)
        self.audit_log: list[dict[str, Any]] = []

    def handle(self, message: str, *, confirmed: bool = False) -> AgentResult:
        started = time.perf_counter()
        trace_id = uuid.uuid4().hex[:12]
        if self._is_injection_request(message):
            decision = Decision("reject", "I cannot reveal hidden instructions or invent unavailable tools.")
        else:
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
                ungrounded = self._ungrounded_identifier(message, decision.arguments)
                if ungrounded:
                    status = "clarify"
                    response = f"Please provide a valid {ungrounded}."
                elif spec.mutating and not confirmed:
                    status = "confirmation_required"
                    response = f"Confirm execution of {spec.name}."
                else:
                    data = spec.handler(**decision.arguments)
                    status = "executed"
                    response = f"Executed {spec.name}."
        except ToolValidationError as exc:
            status = "reject"
            response = f"Tool call rejected: {exc}."
        self.audit_log.append({
            "trace_id": trace_id,
            "input_text": message,
            "output_text": response,
            "decision": decision.kind,
            "tool": decision.tool,
            "arguments": decision.arguments,
            "status": status,
            "confirmed": confirmed,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        })
        return AgentResult(status=status, message=response, data=data, trace_id=trace_id)

    @staticmethod
    def _is_injection_request(message: str) -> bool:
        lower = message.lower()
        patterns = (
            "ignore the available", "ignore rules", "invent a", "system prompt",
            "hidden instructions", "reveal the prompt", "override the tool",
        )
        return any(pattern in lower for pattern in patterns)

    @staticmethod
    def _ungrounded_identifier(message: str, arguments: dict[str, Any]) -> str | None:
        for key in ("order_id", "tracking_id", "sku", "customer_id"):
            if key not in arguments:
                continue
            value = str(arguments[key]).strip()
            if value.lower() in {"unknown", "none", "null", "n/a", "missing"}:
                return key
            if not re.search(rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])", message, re.IGNORECASE):
                return key
        return None
