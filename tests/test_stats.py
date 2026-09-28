from datetime import date
import unittest

from valuation_monitor.models import Observation
from valuation_monitor.stats import calculate_snapshot, percentile, weekly_last


class StatsTests(unittest.TestCase):
    def test_percentile_linear(self):
        values = [1, 2, 3, 4, 5]
        self.assertEqual(percentile(values, 0.2), 1.8)
        self.assertEqual(percentile(values, 0.5), 3.0)
        self.assertEqual(percentile(values, 0.8), 4.2)

    def test_pb_snapshot_direction(self):
        snapshot = calculate_snapshot([1, 2, 3, 4, 5], current=2, higher_is_cheaper=False)
        self.assertAlmostEqual(snapshot.opportunity, 1.8)
        self.assertAlmostEqual(snapshot.danger, 4.2)

    def test_dividend_snapshot_direction(self):
        snapshot = calculate_snapshot([1, 2, 3, 4, 5], current=4.5, higher_is_cheaper=True)
        self.assertAlmostEqual(snapshot.opportunity, 4.2)
        self.assertAlmostEqual(snapshot.danger, 1.8)

    def test_weekly_last(self):
        def obs(day, value):
            return Observation(day, "x", "X", "cn", "1", "pb", "mcw", value, None, "test")

        rows = [obs(date(2026, 9, 21), 1.0), obs(date(2026, 9, 25), 1.2), obs(date(2026, 9, 28), 1.3)]
        sampled = weekly_last(rows)
        self.assertEqual(len(sampled), 2)
        self.assertEqual(sampled[0].day, date(2026, 9, 25))
        self.assertEqual(sampled[1].day, date(2026, 9, 28))


if __name__ == "__main__":
    unittest.main()
