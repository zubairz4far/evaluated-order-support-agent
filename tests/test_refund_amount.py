import unittest

from order_agent.model import ReplayModel


class RefundAmountParsingTests(unittest.TestCase):
    def test_pkr_amount_is_not_confused_with_order_id(self):
        decision = ReplayModel().decide("Refund order 12345 PKR 500")
        self.assertEqual(decision.kind, "tool_call")
        self.assertEqual(decision.tool, "create_refund")
        self.assertEqual(
            decision.arguments,
            {"order_id": "12345", "amount": 500},
        )

    def test_amount_without_currency_skips_order_id(self):
        decision = ReplayModel().decide("Refund order 12345 amount 750")
        self.assertEqual(
            decision.arguments,
            {"order_id": "12345", "amount": 750},
        )


if __name__ == "__main__":
    unittest.main()
