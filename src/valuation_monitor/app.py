from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import load_config
from .history import load_history, merge_weekly, save_history
from .lixinger import LixingerClient
from .mailer import send_html
from .models import Instrument, Observation
from .report import build_html, snapshot_to_dict, zone
from .stats import calculate_snapshot, subtract_years, weekly_last


def needs_backfill(history: list[Observation], instrument: Instrument, years: int, today: date) -> bool:
    cutoff = subtract_years(today, years)
    for metric in instrument.metrics:
        rows = [x for x in history if x.instrument_id == instrument.id and x.metric == metric.key]
        if not rows:
            return True
        earliest = min(x.day for x in rows)
        if earliest > cutoff and (today - earliest).days < 730:
            return True
    return False


def observations_for(history: list[Observation], instrument_id: str, metric: str, cutoff: date) -> list[Observation]:
    return [
        item for item in history
        if item.instrument_id == instrument_id and item.metric == metric and item.day >= cutoff
    ]


def run(config_path: str, history_path: str, latest_path: str, report_path: str, send_mail: bool) -> None:
    settings, instruments = load_config(config_path)
    years = int(settings.get("history_years", 10))
    timezone = str(settings.get("timezone", "Asia/Shanghai"))
    today = datetime.now(ZoneInfo(timezone)).date()
    cutoff = subtract_years(today, years)
    client = LixingerClient()
    history = load_history(history_path)

    incoming: list[Observation] = []
    latest_by_key: dict[tuple[str, str], Observation] = {}

    for instrument in instruments:
        if needs_backfill(history, instrument, years, today):
            backfill = client.fetch_range(instrument, cutoff, today)
            incoming.extend(weekly_last(backfill))

        latest = client.fetch_latest(instrument, end=today)
        incoming.extend(latest)
        for item in latest:
            latest_by_key[(item.instrument_id, item.metric)] = item

    history = merge_weekly(history, incoming)
    history = [item for item in history if item.day >= subtract_years(today, years + 1)]
    save_history(history_path, history)

    report_rows = []
    latest_json = {
        "generated_at": today.isoformat(),
        "history_years": years,
        "frequency": "weekly-last-trading-day",
        "items": [],
    }

    for instrument in instruments:
        for metric in instrument.metrics:
            current_obs = latest_by_key.get((instrument.id, metric.key))
            if current_obs is None:
                report_rows.append((instrument, metric.key, None, None))
                continue

            rows = observations_for(history, instrument.id, metric.key, cutoff)
            values = [item.value for item in rows]
            snapshot = calculate_snapshot(values, current_obs.value, metric.higher_is_cheaper)
            report_rows.append((instrument, metric.key, current_obs.point, snapshot))
            latest_json["items"].append({
                "instrument_id": instrument.id,
                "name": instrument.name,
                "market": instrument.market,
                "code": instrument.code,
                "metric": metric.key,
                "weighting": metric.weighting,
                "source": current_obs.source,
                "source_date": current_obs.day.isoformat(),
                "point": current_obs.point,
                "stats": snapshot_to_dict(snapshot),
                "zone": zone(snapshot),
            })

    html = build_html(today, report_rows)
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(html, encoding="utf-8")
    Path(latest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(latest_path).write_text(json.dumps(latest_json, ensure_ascii=False, indent=2), encoding="utf-8")

    if send_mail:
        opportunity_count = sum(1 for item in latest_json["items"] if item["zone"] == "机会区")
        subject = f"估值日报 {today.isoformat()} | 机会区 {opportunity_count} 项"
        send_html(subject, html)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cloud index valuation monitor")
    parser.add_argument("--config", default="watchlist.yaml")
    parser.add_argument("--history", default="data/history.csv")
    parser.add_argument("--latest", default="data/latest.json")
    parser.add_argument("--report", default="out/report.html")
    parser.add_argument("--send-mail", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.config, args.history, args.latest, args.report, args.send_mail)


if __name__ == "__main__":
    main()
