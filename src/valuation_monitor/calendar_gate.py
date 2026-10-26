"""Exchange-calendar rules for Shanghai 18:30 report and confirmed closes."""
from __future__ import annotations

import argparse
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal

CALENDARS = {"cn": "SSE", "us": "NYSE"}
SHANGHAI = ZoneInfo("Asia/Shanghai")


def calendar_for(market: str):
    return mcal.get_calendar(CALENDARS[market])


def market_opens(market: str, day: date) -> bool:
    schedule = calendar_for(market).schedule(start_date=day, end_date=day)
    return not schedule.empty


def tomorrow_has_open_market(local_day: date) -> bool:
    tomorrow = local_day + timedelta(days=1)
    return any(market_opens(m, tomorrow) for m in ("cn", "us"))


def last_closed_session(market: str, now: datetime) -> date | None:
    """Latest session with close time <= now, checked in UTC rather than by date alone."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    today_cn = now.astimezone(SHANGHAI).date()
    schedule = calendar_for(market).schedule(
        start_date=today_cn - timedelta(days=25), end_date=today_cn)
    completed = schedule[schedule["market_close"] <= now]
    return completed.index[-1].date() if len(completed) else None


def should_run(event_name: str, local_day: date) -> bool:
    return event_name == "workflow_dispatch" or tomorrow_has_open_market(local_day)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", default=os.getenv("GITHUB_EVENT_NAME", "schedule"))
    parser.add_argument("--output", default=os.getenv("GITHUB_OUTPUT"))
    args = parser.parse_args()
    today = datetime.now(SHANGHAI).date()
    run = should_run(args.event, today)
    print(f"Beijing date={today}; tomorrow open={tomorrow_has_open_market(today)}; run={run}")
    if args.output:
        with open(args.output, "a", encoding="utf-8") as handle:
            handle.write(f"run={'true' if run else 'false'}\n")
