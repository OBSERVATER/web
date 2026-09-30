from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import load_config
from .history import load_history, merge_weekly, save_history
from .models import Observation
from .public_sources import PublicDataClient
from .report import build_html, snapshot_to_dict, zone
from .stats import calculate_snapshot, subtract_years, weekly_last


def observations_for(history: list[Observation], instrument_id: str, metric: str, cutoff):
    return [
        item for item in history
        if item.instrument_id == instrument_id and item.metric == metric and item.day >= cutoff
    ]


def run(config_path: str, history_path: str, latest_path: str, report_path: str, as_of_date: str | None = None) -> None:
    settings, instruments = load_config(config_path)
    years = int(settings.get("history_years", 10))
    minimum_history_weeks = int(settings.get("minimum_history_weeks", 450))
    timezone = str(settings.get("timezone", "Asia/Shanghai"))
    today = date.fromisoformat(as_of_date) if as_of_date else datetime.now(ZoneInfo(timezone)).date()
    cutoff = subtract_years(today, years)
    client = PublicDataClient()
    history = load_history(history_path)

    incoming: list[Observation] = []
    latest_by_key: dict[tuple[str, str], Observation] = {}
    errors: list[str] = []

    for instrument in instruments:
        try:
            backfill = client.fetch_range(instrument, cutoff, today)
            incoming.extend(weekly_last(backfill))
        except Exception as exc:
            errors.append(f"{instrument.name} history: {exc}")

        try:
            latest = client.fetch_latest(instrument, end=today)
            incoming.extend(latest)
            for item in latest:
                latest_by_key[(item.instrument_id, item.metric)] = item
        except Exception as exc:
            errors.append(f"{instrument.name} latest: {exc}")

    history = merge_weekly(history, incoming)
    history = [item for item in history if item.day >= subtract_years(today, years + 1)]
    save_history(history_path, history)

    report_rows = []
    latest_json = {
        "generated_at": today.isoformat(),
        "history_years": years,
        "frequency": "weekly-last-trading-day",
        "minimum_history_weeks": minimum_history_weeks,
        "errors": errors,
        "source_warnings": list(client.history_source_warnings),
        "items": [],
    }

    for instrument in instruments:
        for metric in instrument.metrics:
            current_obs = latest_by_key.get((instrument.id, metric.key))
            if current_obs is None:
                report_rows.append((instrument, metric.key, None, None))
                continue

            rows = observations_for(history, instrument.id, metric.key, cutoff)
            # Different providers can report the same metric using different
            # weighting/aggregation methods. Keep all dated observations for
            # traceability, but never pool incompatible histories into 10Y stats.
            valid_rows = [
                item for item in rows
                if item.value is not None and float(item.value) > 0
            ]
            methods = sorted({item.weighting for item in valid_rows})
            values = [item.value for item in valid_rows]
            percentile_samples = sum(item.reported_percentile is not None for item in rows)
            snapshot = None
            history_consistent = not methods or methods == [current_obs.weighting]
            if history_consistent and len(values) >= minimum_history_weeks:
                snapshot = calculate_snapshot(values, current_obs.value, metric.higher_is_cheaper)

            report_rows.append((instrument, metric.key, current_obs, snapshot))
            payload = {
                "instrument_id": instrument.id,
                "name": instrument.name,
                "market": instrument.market,
                "code": instrument.code,
                "metric": metric.key,
                "weighting": metric.weighting,
                "source": current_obs.source,
                "source_date": current_obs.day.isoformat(),
                "point": current_obs.point,
                "current": current_obs.value,
                "reported_percentile": current_obs.reported_percentile,
                "history_samples": len(values),
                "percentile_history_samples": percentile_samples,
                "history_complete": history_consistent and len(values) >= minimum_history_weeks,
                "history_methods": methods,
                "history_method_consistent": history_consistent,
            }
            if snapshot is not None:
                payload["stats"] = snapshot_to_dict(snapshot)
                payload["zone"] = zone(snapshot)
            latest_json["items"].append(payload)

    html = build_html(today, report_rows, minimum_history_weeks, errors)
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(html, encoding="utf-8")
    Path(latest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(latest_path).write_text(json.dumps(latest_json, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cloud index valuation monitor")
    parser.add_argument("--config", default="watchlist.yaml")
    parser.add_argument("--history", default="data/history.csv")
    parser.add_argument("--latest", default="data/latest.json")
    parser.add_argument("--report", default="out/report.html")
    parser.add_argument("--as-of-date", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.config, args.history, args.latest, args.report, args.as_of_date)


if __name__ == "__main__":
    main()
