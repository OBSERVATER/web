import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from valuation_monitor.drawdown import calculate
from scripts.build_issue_comment import instrument_section

class TriggerDisplayTests(unittest.TestCase):
    def test_threshold_shown_before_reset(self):
        source = "akshare-csi:000300"
        state = {"cycles": {"csi300": {
            "peak": 100.0, "last_close": 100.0,
            "last_day": "2026-10-23", "source": source
        }}, "pending": []}
        hist = [{"day": "2026-10-26", "instrument_id": "csi300",
                 "close": 96.0, "source": source}]
        config = {"instruments": [{"id": "csi300", "name": "沪深300", "market": "cn"}]}
        when = datetime(2026, 10, 26, 18, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        updated, snap = calculate(config, hist, state, set(), when)
        self.assertEqual(updated["cycles"]["csi300"]["peak"], 96.0)
        self.assertAlmostEqual(snap["items"][0]["triggered_drop_pct"], 4.0)
        rendered = "\n".join(instrument_section(
            {"name": "沪深300", "metric": "pe_ttm", "current": 12.81},
            snap["items"][0]))
        self.assertIn("本轮累计跌幅：4.00%", rendered)
        self.assertIn("已触发", rendered)

if __name__ == "__main__":
    unittest.main()
