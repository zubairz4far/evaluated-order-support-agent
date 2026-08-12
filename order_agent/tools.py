from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class ToolValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    required: dict[str, type]
    optional: dict[str, type]
    mutating: bool
    handler: Callable[..., dict[str, Any]]

    def validate(self, arguments: dict[str, Any]) -> None:
        allowed = set(self.required) | set(self.optional)
        unknown = set(arguments) - allowed
        missing = set(self.required) - set(arguments)
        if unknown:
            raise ToolValidationError(f"unknown arguments: {sorted(unknown)}")
        if missing:
            raise ToolValidationError(f"missing arguments: {sorted(missing)}")
        for key, value in arguments.items():
            expected = self.required.get(key, self.optional.get(key))
            if expected and not isinstance(value, expected):
                raise ToolValidationError(f"{key} must be {expected.__name__}")
            if isinstance(value, str) and (not value.strip() or len(value) > 100):
                raise ToolValidationError(f"invalid {key}")


class DemoOrderStore:
    def __init__(self) -> None:
        self.orders = {
            "12345": {"status": "shipped", "tracking": "PX-1001", "total": 4200},
            "67890": {"status": "processing", "tracking": None, "total": 2750},
        }
        self.inventory = {"GLM-001": 18, "GLM-002": 0}

    def get_order(self, order_id: str) -> dict[str, Any]:
        order = self.orders.get(order_id)
        return {"found": bool(order), "order_id": order_id, "order": order}

    def track_shipment(self, tracking_id: str) -> dict[str, Any]:
        return {"tracking_id": tracking_id, "status": "in_transit", "eta_days": 2}

    def get_inventory(self, sku: str) -> dict[str, Any]:
        return {"sku": sku, "available": self.inventory.get(sku, 0)}

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        if order_id not in self.orders:
            return {"ok": False, "reason": "not_found"}
        if self.orders[order_id]["status"] == "shipped":
            return {"ok": False, "reason": "already_shipped"}
        self.orders[order_id]["status"] = "cancelled"
        return {"ok": True, "order_id": order_id}

    def create_refund(self, order_id: str, amount: int) -> dict[str, Any]:
        return {"ok": True, "order_id": order_id, "amount": amount, "mode": "simulation"}


def build_registry(store: DemoOrderStore) -> dict[str, ToolSpec]:
    return {
        "get_order": ToolSpec("get_order", {"order_id": str}, {}, False, store.get_order),
        "track_shipment": ToolSpec("track_shipment", {"tracking_id": str}, {}, False, store.track_shipment),
        "get_inventory": ToolSpec("get_inventory", {"sku": str}, {}, False, store.get_inventory),
        "cancel_order": ToolSpec("cancel_order", {"order_id": str}, {}, True, store.cancel_order),
        "create_refund": ToolSpec("create_refund", {"order_id": str, "amount": int}, {}, True, store.create_refund),
    }
