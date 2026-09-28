from datetime import date
import unittest

from valuation_monitor.models import Instrument, MetricSpec, Observation
from valuation_monitor.report import build_html
from valuation_monitor.stats import calculate_snapshot


class ReportTests(unittest.TestCase):
    def test_report_contains_values(self):
        instrument = Instrument(
            "hscgsi",
            "恒生消费",
            "hk",
            "HSCGSI",
            (MetricSpec("pb"),),
            {"type": "test"},
        )
        current = Observation(
            date(2026, 9, 28),
            "hscgsi",
            "恒生消费",
            "hk",
            "HSCGSI",
            "pb",
            "aggregate",
            2.29,
            2193.18,
            "test-public",
        )
        snapshot = calculate_snapshot([1.72, 2.16, 2.29, 2.58, 3.05, 4.27], 2.29, False)
        report = build_html(date(2026, 9, 28), [(instrument, "pb", current, snapshot)])
        self.assertIn("恒生消费", report)
        self.assertIn("2.29", report)
        self.assertIn("市净率LF", report)
        self.assertIn("test-public", report)


if __name__ == "__main__":
    unittest.main()
