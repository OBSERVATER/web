from datetime import date, timedelta
import unittest

from valuation_monitor.app import (
    candidate_history, recent_mean, series_rows, source_specs, valuation_zone,
)
from valuation_monitor.history import merge_weekly
from valuation_monitor.models import Instrument, MetricSpec, Observation


def row(day, val, source="csindex-official-public", weighting="aggregate"):
    return Observation(date.fromisoformat(day), "x", "X", "cn", "000300",
                       "pe_ttm", weighting, val, None, source)


class ValuationPolicyTests(unittest.TestCase):
    def test_four_band_boundaries_and_dividend_reverse(self):
        for p, expected in [(0.1, "低估"), (0.2, "低估"),
                            (0.4, "偏低"), (0.7, "偏高"), (0.9, "高估")]:
            self.assertEqual(valuation_zone(p, False), expected)
        self.assertEqual(valuation_zone(0.9, True), "低估")
        self.assertEqual(valuation_zone(0.1, True), "高估")

    def test_historical_source_isolation(self):
        official = row("2026-10-16", 17.0)
        funddb = row("2026-10-16", 19.0, "guzhibiao-public-funddb-history",
                     "funddb-native-unverified")
        rows = merge_weekly([official], [funddb])
        self.assertEqual(len(rows), 2)
        self.assertEqual(series_rows(rows, official, date(2025, 1, 1)), [official])
        self.assertEqual(series_rows(rows, funddb, date(2025, 1, 1)), [funddb])

    def test_four_week_mean_requires_four_recent_samples(self):
        base = date(2026, 10, 2)
        rows = [row((base + timedelta(days=i*7)).isoformat(), 10.0 + i)
                for i in range(4)]
        self.assertEqual(recent_mean(rows, rows[-1].day), (11.5, 4))
        self.assertEqual(recent_mean(rows[:3], rows[2].day)[0], None)
        old = rows.copy()
        old[0] = row("2025-10-02", 10)
        self.assertIsNone(recent_mean(old, rows[-1].day)[0])

    def test_candidate_source_has_independent_weighting(self):
        ins = Instrument("x", "X", "cn", "000300", (MetricSpec("pe_ttm"),), {
            "type": "chain", "sources": [
                {"type": "csindex_indicator"},
                {"type": "guzhibiao"},
            ],
        })
        specs = source_specs(ins)
        self.assertEqual(specs[0].metrics[0].weighting, "aggregate")
        self.assertEqual(specs[1].metrics[0].weighting, "funddb-native-unverified")


if __name__ == "__main__":
    unittest.main()
