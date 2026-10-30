"""Exchange-calendar rules and recoverable 18:30 Beijing schedule."""
from __future__ import annotations
import argparse
import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas_market_calendars as mcal

CALENDARS = {"cn": "SSE", "us": "NYSE"}
SHANGHAI = ZoneInfo("Asia/Shanghai")
REPORT_TIME = time(18, 30)
MAX_RECOVERY_DAYS = 45
MAX_DAYS_PER_RUN = 5

def calendar_for(market: str):
    return mcal.get_calendar(CALENDARS[market])

def market_opens(market: str, day: date) -> bool:
    return not calendar_for(market).schedule(start_date=day, end_date=day).empty

def tomorrow_has_open_market(local_day: date) -> bool:
    """The configured business rule: check NEXT day's session."""
    tomorrow = local_day + timedelta(days=1)
    return any(market_opens(m, tomorrow) for m in ("cn", "us"))

def last_closed_session(market: str, now: datetime) -> date | None:
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    today_cn = now.astimezone(SHANGHAI).date()
    schedule = calendar_for(market).schedule(
        start_date=today_cn - timedelta(days=25), end_date=today_cn)
    completed = schedule[schedule["market_close"] <= now]
    return completed.index[-1].date() if len(completed) else None

def should_run(event_name: str, scheduled_day: date) -> bool:
    return event_name == "workflow_dispatch" or tomorrow_has_open_market(scheduled_day)

def latest_scheduled_day(now: datetime) -> date:
    """Latest already-due 18:30 slot, not the GitHub event's unknown target timestamp."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    local = now.astimezone(SHANGHAI)
    return local.date() if local.time() >= REPORT_TIME else local.date() - timedelta(days=1)

def planned_days(now: datetime, published_reports: set[str], event_name: str,
                 max_days: int = MAX_DAYS_PER_RUN) -> list[date]:
    if max_days < 1:
        raise ValueError("max_days must be positive")
    latest = latest_scheduled_day(now)
    valid = []
    for value in published_reports:
        try:
            valid.append(date.fromisoformat(value))
        except ValueError:
            pass
    # First deployment must not create reports for an unbounded historical period.
    first = (max(valid) + timedelta(days=1)) if valid else latest
    first = max(first, latest - timedelta(days=MAX_RECOVERY_DAYS))
    pending = []
    day = first
    while day <= latest and len(pending) < max_days:
        if day.isoformat() not in published_reports and tomorrow_has_open_market(day):
            pending.append(day)
        day += timedelta(days=1)
    if not pending and event_name == "workflow_dispatch":
        # Manual verification may rerun an already reported day; publication is idempotent.
        return [latest]
    return pending

def report_instant(scheduled_day: date) -> datetime:
    return datetime.combine(scheduled_day, REPORT_TIME, tzinfo=SHANGHAI)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", default=os.getenv("GITHUB_EVENT_NAME", "schedule"))
    parser.add_argument("--published", default="out/published-issue.json")
    parser.add_argument("--dates-file", default="out/planned-days.txt")
    parser.add_argument("--output", default=os.getenv("GITHUB_OUTPUT"))
    args = parser.parse_args()
    published_path = Path(args.published)
    if not published_path.exists():
        raise FileNotFoundError(f"Publication scan missing: {published_path}")
    published = set(json.loads(published_path.read_text(encoding="utf-8")).get(
        "published_reports", []))
    now = datetime.now(SHANGHAI)
    days = planned_days(now, published, args.event)
    target = Path(args.dates_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(f"{d.isoformat()}\n" for d in days), encoding="utf-8")
    print(f"Beijing now={now.isoformat()}; last due slot={latest_scheduled_day(now)};"
          f" published={len(published)}; planned={','.join(map(str, days)) or '-'}")
    if args.output:
        with open(args.output, "a", encoding="utf-8") as handle:
            handle.write(f"run={'true' if days else 'false'}\n")

if __name__ == "__main__":
    main()
