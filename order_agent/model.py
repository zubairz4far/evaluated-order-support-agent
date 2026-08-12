from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from typing import Protocol

from .types import Decision


class ModelAdapter(Protocol):
    def decide(self, message: str) -> Decision: ...


class ReplayModel:
    """Deterministic offline stand-in for the fine-tuned model."""

    def decide(self, message: str) -> Decision:
        text = message.strip()
        lower = text.lower()
        if any(term in lower for term in ("ignore rules", "invent a tool", "system prompt")):
            return Decision("reject", "I cannot override the tool policy or invent tools.")
        order_id = self._capture(r"\b(\d{5})\b", text)
        tracking = self._capture(r"\b(PX-\d+)\b", text.upper())
        sku = self._capture(r"\b(GLM-\d+)\b", text.upper())
        if "cancel" in lower:
            return (Decision("tool_call", tool="cancel_order", arguments={"order_id": order_id})
                    if order_id else Decision("clarify", "Please provide the order ID to cancel."))
        if "refund" in lower:
            amount = self._capture(r"(?:pkr\s*)?(\d{3,6})", lower)
            if not order_id or not amount:
                return Decision("clarify", "Please provide the order ID and refund amount.")
            return Decision("tool_call", tool="create_refund", arguments={"order_id": order_id, "amount": int(amount)})
        if "track" in lower:
            return (Decision("tool_call", tool="track_shipment", arguments={"tracking_id": tracking})
                    if tracking else Decision("clarify", "Please provide the tracking ID."))
        if "inventory" in lower or "stock" in lower:
            return (Decision("tool_call", tool="get_inventory", arguments={"sku": sku})
                    if sku else Decision("clarify", "Please provide the SKU."))
        if "order" in lower:
            return (Decision("tool_call", tool="get_order", arguments={"order_id": order_id})
                    if order_id else Decision("clarify", "Please provide the order ID."))
        return Decision("answer", "I can help with orders, tracking, inventory, cancellations, and refunds.")

    @staticmethod
    def _capture(pattern: str, text: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(1) if match else None


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Get an order by its order ID.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": "Check current inventory for a product SKU.",
            "parameters": {
                "type": "object",
                "properties": {"sku": {"type": "string"}},
                "required": ["sku"],
            },
        },
    },
]


@dataclass
class TransformersAdapter:
    """Lazy adapter for the published Qwen3 PEFT model.

    Heavy ML dependencies are imported only when this adapter is instantiated,
    keeping the deterministic demo and test suite lightweight.
    """

    adapter_id: str = "zubairz4far/qwen3-1.7b-tool-calling"
    base_model_id: str = "Qwen/Qwen3-1.7B"
    max_new_tokens: int = 160

    def __post_init__(self) -> None:
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install model dependencies with: pip install -e '.[model]'") from exc
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_id, trust_remote_code=True)
        base = AutoModelForCausalLM.from_pretrained(
            self.base_model_id, torch_dtype="auto", device_map="auto", trust_remote_code=True
        )
        self.model = PeftModel.from_pretrained(base, self.adapter_id)
        self.model.eval()

    def decide(self, message: str) -> Decision:
        prompt = self.tokenizer.apply_chat_template(
            [{"role": "user", "content": message}],
            tools=TOOL_SCHEMAS,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with self._torch.inference_mode():
            generated = self.model.generate(
                **inputs, max_new_tokens=self.max_new_tokens, do_sample=False
            )
        completion = self.tokenizer.decode(
            generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )
        self.last_completion = completion
        return self.parse_completion(completion)

    @staticmethod
    def parse_completion(text: str) -> Decision:
        candidate = TransformersAdapter._first_json_object(text)
        if candidate is None:
            clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            lower = clean.lower()
            if any(word in lower for word in ("provide", "need", "which", "what is", "please share")):
                return Decision("clarify", clean)
            if any(word in lower for word in ("cannot", "can't", "won't", "not available")):
                return Decision("reject", clean)
            return Decision("answer", clean)
        try:
            payload: dict[str, Any] = json.loads(candidate)
        except json.JSONDecodeError:
            return Decision("reject", "Model output was not valid structured JSON.")
        if "name" in payload and "arguments" in payload:
            return Decision("tool_call", tool=payload.get("name"), arguments=payload.get("arguments", {}))
        kind = payload.get("kind")
        if kind not in {"tool_call", "answer", "clarify", "reject"}:
            return Decision("reject", "Model returned an unsupported decision kind.")
        if kind == "tool_call":
            args = payload.get("arguments", {})
            if not isinstance(payload.get("tool"), str) or not isinstance(args, dict):
                return Decision("reject", "Model returned a malformed tool call.")
            return Decision(kind, tool=payload["tool"], arguments=args)
        return Decision(kind, message=str(payload.get("message", "")))

    @staticmethod
    def _first_json_object(text: str) -> str | None:
        start = text.find("{")
        if start < 0:
            return None
        depth, quoted, escaped = 0, False, False
        for index in range(start, len(text)):
            char = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        return None
