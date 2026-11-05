import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from valuation_monitor.calendar_gate import latest_scheduled_day, planned_days, report_instant, has_new_closed_session, should_run, unpublished_gaps
TZ = ZoneInfo("Asia/Shanghai")

class ScheduleRecoveryTests(unittest.TestCase):
    def test_overnight_delay(self):
        now = datetime(2026, 10, 30, 1, 1, tzinfo=TZ)
        self.assertEqual(latest_scheduled_day(now), date(2026, 10, 29))
        self.assertEqual(planned_days(now, {"2026-10-28"}, "schedule"), [date(2026, 10, 29)])

    def test_closed_session_rule(self):
        self.assertTrue(has_new_closed_session(date(2026, 10, 30)))
        self.assertTrue(has_new_closed_session(date(2026, 10, 31)))
        self.assertFalse(has_new_closed_session(date(2026, 11, 1)))
        self.assertTrue(should_run("schedule", date(2026, 10, 30)))
        self.assertFalse(should_run("schedule", date(2026, 11, 1)))

    def test_recovery_and_dedup(self):
        now = datetime(2026, 11, 3, 19, tzinfo=TZ)
        self.assertEqual(planned_days(now, {"2026-10-29"}, "schedule"),
                         [date(2026, 10, 30), date(2026, 10, 31), date(2026, 11, 2), date(2026, 11, 3)])
        self.assertEqual(planned_days(now, {"2026-10-29", "2026-10-30", "2026-10-31", "2026-11-02", "2026-11-03"}, "schedule"), [])

    def test_manual_preview_uses_last_due_slot(self):
        now = datetime(2026, 10, 30, 11, tzinfo=TZ)
        self.assertEqual(planned_days(now, {"2026-10-29"}, "workflow_dispatch"), [date(2026, 10, 29)])
        self.assertEqual(planned_days(now, {"2026-10-29"}, "schedule"), [])

    def test_sunday_recovers_friday_and_us_close(self):
        now = datetime(2026, 11, 1, 19, tzinfo=TZ)
        self.assertEqual(planned_days(now, {"2026-10-29"}, "schedule"),
                         [date(2026, 10, 30), date(2026, 10, 31)])

    def test_saturday_morning_does_not_replay_future_slot(self):
        now = datetime(2026, 10, 31, 7, 17, tzinfo=TZ)
        self.assertEqual(planned_days(now, {"2026-10-29"}, "schedule"),
                         [date(2026, 10, 30)])

    def test_batch_limit_and_future_markers(self):
        now = datetime(2026, 11, 1, 19, tzinfo=TZ)
        self.assertEqual(planned_days(now, {"2026-10-29", "2099-01-01"}, "schedule", 1),
                         [date(2026, 10, 30)])
        with self.assertRaises(ValueError):
            planned_days(now, set(), "schedule", 0)

    def test_first_run_and_holiday(self):
        self.assertEqual(planned_days(datetime(2026, 10, 30, 19, tzinfo=TZ), set(), "schedule"),
                         [date(2026, 10, 30)])
        self.assertFalse(has_new_closed_session(date(2026, 1, 2)))
        self.assertTrue(has_new_closed_session(date(2026, 11, 28)))
        self.assertFalse(has_new_closed_session(date(2026, 11, 29)))

    def test_detects_middle_gap_without_replaying_newer_state(self):
        now = datetime(2026, 11, 4, 19, tzinfo=TZ)
        published = {"2026-11-02", "2026-11-04"}
        # Keep forward-only replay behavior; a missing older day requires repair.
        self.assertEqual(planned_days(now, published, "schedule"), [])
        self.assertEqual(unpublished_gaps(now, published), [date(2026, 11, 3)])

    def test_no_middle_gap_on_non_trading_day(self):
        now = datetime(2026, 11, 2, 19, tzinfo=TZ)
        published = {"2026-10-31", "2026-11-02"}
        self.assertEqual(unpublished_gaps(now, published), [])

    def test_cutoff(self):
        self.assertEqual(report_instant(date(2026, 10, 29)).isoformat(), "2026-10-29T18:30:00+08:00")

    def test_before_and_after_1830(self):
        self.assertEqual(latest_scheduled_day(datetime(2026, 10, 30, 18, 29, tzinfo=TZ)), date(2026, 10, 29))
        self.assertEqual(latest_scheduled_day(datetime(2026, 10, 30, 18, 30, tzinfo=TZ)), date(2026, 10, 30))
if __name__ == "__main__":
    unittest.main()
