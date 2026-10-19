from __future__ import annotations

import argparse
import csv
import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import load_config
from .history import load_history, merge_weekly, save_history, source_family
from .models import Instrument, MetricSpec, Observation
from .public_sources import PublicDataClient
from .report import build_html, snapshot_to_dict
from .stats import calculate_snapshot, subtract_years, weekly_last


def valuation_zone(percentile: float, higher_is_cheaper: bool) -> str:
    cheap_rank = 1.0 - percentile if higher_is_cheaper else percentile
    if cheap_rank <= 0.20:
        return "低估"
    if cheap_rank <= 0.50:
        return "偏低"
    if cheap_rank <= 0.80:
        return "偏高"
    return "高估"


def source_specs(instrument: Instrument) -> list[Instrument]:
    source = instrument.source
    sources = source.get("sources", []) if source.get("type") == "chain" else [source]
    result = []
    for entry in sources:
        # Never let separately derived third-party observations inherit an
        # official weighting identifier, even when they measure the same PE.
        weighting = (
            "funddb-native-unverified" if entry.get("type") == "guzhibiao"
            else "danjuan-native" if entry.get("type") == "danjuan" and instrument.code == "000300"
            else None
        )
        metrics = (tuple(MetricSpec(m.key, weighting) for m in instrument.metrics)
                   if weighting else instrument.metrics)
        result.append(replace(instrument, metrics=metrics, source=dict(entry)))
    return result


def candidate_history(path: Path, instruments: list[Instrument]) -> list[Observation]:
    """Previously verified third-party series, kept separate from official history."""
    if not path.exists():
        return []
    allowed = {(i.id, i.code, m.key) for i in instruments
               if any(s.source.get("type") == "guzhibiao" for s in source_specs(i))
               for m in i.metrics}
    result = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("instrument_id"), row.get("code"), row.get("metric")) not in allowed:
                continue
            if (row.get("source") != "guzhibiao-public-funddb-history"
                    or row.get("weighting") != "funddb-native-unverified"):
                continue
            try:
                day, value = date.fromisoformat(row["day"]), float(row["value"])
                if not (0 < value < 1000):
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            result.append(Observation(
                day=day, instrument_id=row["instrument_id"],
                instrument_name=row["instrument_name"], market="cn", code=row["code"],
                metric=row["metric"], weighting=row["weighting"], value=value,
                point=None, source=row["source"],
            ))
    return result


def series_rows(history: list[Observation], spot: Observation, cutoff: date) -> list[Observation]:
    family = source_family(spot.source)
    values = [
        row for row in history
        if row.instrument_id == spot.instrument_id and row.metric == spot.metric
        and row.weighting == spot.weighting and source_family(row.source) == family
        and cutoff <= row.day <= spot.day and 0 < row.value < 100000
    ]
    return sorted(values, key=lambda row: row.day)


def recent_mean(rows: list[Observation], current_day: date) -> tuple[float | None, int]:
    four = rows[-4:]
    if len(four) < 4 or (current_day - four[0].day).days > 35:
        return None, len(four)
    return sum(row.value for row in four) / 4, 4


def run(config_path: str, history_path: str, latest_path: str, report_path: str,
        as_of_date: str | None = None) -> None:
    settings, instruments = load_config(config_path)
    years = int(settings.get("history_years", 10))
    minimum_weeks = int(settings.get("minimum_history_weeks", 450))
    timezone = str(settings.get("timezone", "Asia/Shanghai"))
    today = date.fromisoformat(as_of_date) if as_of_date else datetime.now(ZoneInfo(timezone)).date()
    cutoff = subtract_years(today, years)
    client = PublicDataClient()
    history = load_history(history_path)
    history.extend(candidate_history(Path(history_path).parent / "candidates/guzhibiao_funddb_history.csv", instruments))
    incoming: list[Observation] = []
    observations: dict[tuple[str, str], list[tuple[int, Observation]]] = {}
    errors: list[str] = []
    warnings: list[str] = []

    for instrument in instruments:
        for priority, src in enumerate(source_specs(instrument)):
            try:
                historic = client.fetch_range(src, cutoff, today)
                incoming.extend(weekly_last(historic))
            except Exception as exc:
                warnings.append(f"{instrument.name} / {src.source.get('type')} history: {exc}")
            try:
                latest = [row for row in client.fetch_latest(src, end=today) if row.day <= today]
                incoming.extend(latest)
                for row in latest:
                    observations.setdefault((instrument.id, row.metric), []).append((priority, row))
            except Exception as exc:
                warnings.append(f"{instrument.name} / {src.source.get('type')} latest: {exc}")

    history = merge_weekly(history, incoming)
    history = [row for row in history if row.day >= subtract_years(today, years + 1)]
    save_history(history_path, history)
    report_rows = []
    latest_json = {
        "generated_at": today.isoformat(), "history_years": years,
        "frequency": "weekly-last-trading-day", "minimum_history_weeks": minimum_weeks,
        "errors": errors, "source_warnings": warnings + list(client.history_source_warnings),
        "items": [],
    }

    for instrument in instruments:
        for metric in instrument.metrics:
            candidates = observations.get((instrument.id, metric.key), [])
            candidates.sort(key=lambda pair: (pair[0], -pair[1].day.toordinal()))
            if not candidates:
                errors.append(f"{instrument.name} / {metric.key}: all current data sources unavailable")
                report_rows.append((instrument, metric.key, None, None))
                latest_json["items"].append({
                    "instrument_id": instrument.id, "name": instrument.name,
                    "code": instrument.code, "metric": metric.key,
                    "current": None, "zone": "数据不可用",
                })
                continue
            # Prefer the official primary, unless a separate, fresh, full-history
            # series can calculate its own comparable valuation statistics.
            primary = candidates[0][1]
            qualified = []
            for priority, spot in candidates:
                if (today - spot.day).days > 10:
                    continue
                rows = series_rows(history, spot, cutoff)
                if len(rows) < minimum_weeks:
                    continue
                # 450 tightly packed samples must not be labelled ten-year history.
                min_span = max(1, years - 2) * 365
                if (rows[-1].day - rows[0].day).days < min_span:
                    continue
                qualified.append((priority, spot, rows))
            selected = min(qualified, key=lambda pair: pair[0]) if qualified else None
            spot = selected[1] if selected else primary
            rows = selected[2] if selected else series_rows(history, spot, cutoff)
            snapshot = calculate_snapshot([row.value for row in rows], spot.value,
                                          metric.higher_is_cheaper) if selected else None
            fresh = (today - spot.day).days <= 10
            pct = (snapshot.percentile if snapshot else spot.reported_percentile if fresh else None)
            status = (valuation_zone(pct, metric.higher_is_cheaper) if pct is not None
                      else "历史不足" if fresh else "数据过期")
            average, recent_count = recent_mean(rows, spot.day) if fresh else (None, 0)
            # Keep a reliable alternate spot for visibility, never use it in calculations.
            other = primary if (primary.source != spot.source or primary.weighting != spot.weighting) else None
            payload = {
                "instrument_id": instrument.id, "name": instrument.name,
                "market": instrument.market, "code": instrument.code, "metric": metric.key,
                "weighting": spot.weighting, "source": spot.source,
                "series_family": source_family(spot.source),
                "source_date": spot.day.isoformat(), "point": spot.point if spot.point is not None else primary.point,
                "current": spot.value, "reported_percentile": spot.reported_percentile if fresh else None,
                "rating_percentile": pct, "percentile_origin": "10Y本地" if snapshot else "源站" if pct is not None else None,
                "history_samples": len(rows),
                "history_complete": snapshot is not None,
                "recent_4w_mean": average, "recent_samples": recent_count,
                "recent_4w_diff_pct": (spot.value / average - 1) * 100 if average else None,
                "median_diff_pct": (spot.value / snapshot.median - 1) * 100 if snapshot else None,
                "zone": status,
            }
            if other is not None:
                payload["reference_current"] = other.value
                payload["reference_source"] = other.source
                payload["reference_date"] = other.day.isoformat()
            if snapshot:
                payload["stats"] = snapshot_to_dict(snapshot)
            latest_json["items"].append(payload)
            report_rows.append((instrument, metric.key, spot, snapshot))

    html = build_html(today, report_rows, minimum_weeks, errors)
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


if __name__ == "__main__":
    a = parse_args()
    run(a.config, a.history, a.latest, a.report, a.as_of_date)
