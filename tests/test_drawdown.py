import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from valuation_monitor.drawdown import calculate, merge_prices
from valuation_monitor.calendar_gate import market_opens, tomorrow_has_open_market, last_closed_session


def p(day, price, source="eastmoney:1.000300:unadjusted"):
    return {"day": day, "instrument_id": "csi300", "name": "沪深300",
            "close": price, "source": source}


class DrawdownTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"instruments": [{"id": "csi300", "name": "沪深300", "market": "cn"}]}
        self.now = datetime(2026, 10, 26, 18, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    def test_first_run_initializes_to_latest_without_backfilling_alerts(self):
        state, snap = calculate(self.cfg, [p("2026-10-23",100), p("2026-10-26",95)],
                                {}, set(), self.now)
        self.assertEqual(state["pending"], [])
        self.assertEqual(state["cycles"]["csi300"]["peak"], 95)
        self.assertAlmostEqual(snap["items"][0]["change_pct"], -5)

    def test_threshold_inclusive_and_reset(self):
        base = {"cycles": {"csi300": {"peak": 100, "last_close": 100,
                                    "last_day": "2026-10-23", "source": p("x", 1)["source"]}}}
        state, snap = calculate(self.cfg, [p("2026-10-23",100),p("2026-10-26",96)],base,set(),self.now)
        self.assertEqual(len(state["pending"]),1)
        self.assertAlmostEqual(state["pending"][0]["drop_pct"],4)
        self.assertEqual(state["cycles"]["csi300"]["peak"],96)
        state2, _ = calculate(self.cfg,[p("2026-10-23",100),p("2026-10-26",96)],
                              state,set(),self.now)
        self.assertEqual(len(state2["pending"]),1)

    def test_after_published_alert_cleared_without_duplicate(self):
        base = {"cycles":{"csi300":{"peak":100,"last_close":100,
                    "last_day":"2026-10-23","source":p("x",1)["source"]}}}
        state, _ = calculate(self.cfg,[p("2026-10-26",96)],base,set(),self.now)
        id_ = state["pending"][0]["id"]
        cleared, _ = calculate(self.cfg,[p("2026-10-26",96)],state,{id_},self.now)
        self.assertEqual(cleared["pending"],[])

    def test_peak_updates_and_non_trigger_rebound(self):
        base = {"cycles":{"csi300":{"peak":100,"last_close":100,
                    "last_day":"2026-10-23","source":p("x",1)["source"]}}}
        state,_ = calculate(self.cfg,[p("2026-10-26",102)],base,set(),self.now)
        self.assertEqual(state["cycles"]["csi300"]["peak"],102)

    def test_conflicting_prices_are_not_silently_merged(self):
        merged,warnings=merge_prices([p("2026-10-23",100)],[p("2026-10-23",99)])
        self.assertEqual(merged[0]["close"],100)
        self.assertEqual(len(warnings),1)

    def test_market_calendar_holidays(self):
        self.assertFalse(market_opens("cn", __import__("datetime").date(2026,10,1)))
        self.assertTrue(tomorrow_has_open_market(__import__("datetime").date(2026,10,25)))
        self.assertEqual(last_closed_session("us", self.now).__str__(), "2026-10-23")


if __name__ == "__main__":
    unittest.main()
