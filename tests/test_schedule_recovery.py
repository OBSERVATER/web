import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from valuation_monitor.calendar_gate import latest_scheduled_day, planned_days, report_instant, tomorrow_has_open_market
TZ = ZoneInfo("Asia/Shanghai")

class ScheduleRecoveryTests(unittest.TestCase):
    def test_overnight_delay(self):
        now = datetime(2026, 10, 30, 1, 1, tzinfo=TZ)
        self.assertEqual(latest_scheduled_day(now), date(2026, 10, 29))
        self.assertEqual(planned_days(now, {"2026-10-28"}, "schedule"), [date(2026, 10, 29)])

    def test_original_market_rule(self):
        self.assertFalse(tomorrow_has_open_market(date(2026, 10, 30)))
        self.assertTrue(tomorrow_has_open_market(date(2026, 11, 1)))

    def test_recovery_and_dedup(self):
        now = datetime(2026, 11, 3, 19, tzinfo=TZ)
        self.assertEqual(planned_days(now, {"2026-10-29"}, "schedule"),
                         [date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)])
        self.assertEqual(planned_days(now, {"2026-10-29", "2026-11-01", "2026-11-02", "2026-11-03"}, "schedule"), [])

    def test_manual_preview_uses_last_due_slot(self):
        now = datetime(2026, 10, 30, 11, tzinfo=TZ)
        self.assertEqual(planned_days(now, {"2026-10-29"}, "workflow_dispatch"), [date(2026, 10, 29)])
        self.assertEqual(planned_days(now, {"2026-10-29"}, "schedule"), [])

    def test_cutoff(self):
        self.assertEqual(report_instant(date(2026, 10, 29)).isoformat(), "2026-10-29T18:30:00+08:00")

    def test_before_and_after_1830(self):
        self.assertEqual(latest_scheduled_day(datetime(2026, 10, 30, 18, 29, tzinfo=TZ)), date(2026, 10, 29))
        self.assertEqual(latest_scheduled_day(datetime(2026, 10, 30, 18, 30, tzinfo=TZ)), date(2026, 10, 30))
if __name__ == "__main__":
    unittest.main()
