import unittest
from scripts.build_issue_comment import percent


class PercentFormatTests(unittest.TestCase):
    def test_tiny_negative_move_does_not_display_negative_zero(self):
        self.assertEqual(percent(-0.004006, signed=True), "-0.004%")

    def test_usual_moves_remain_two_decimals(self):
        self.assertEqual(percent(-1.234, signed=True), "-1.23%")
        self.assertEqual(percent(4.25), "4.25%")


if __name__ == "__main__":
    unittest.main()
