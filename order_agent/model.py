from __future__ import annotations

import re
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
