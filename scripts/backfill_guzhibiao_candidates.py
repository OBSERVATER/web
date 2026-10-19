"""Persist independently labelled PUBLIC raw valuation histories as candidate datasets.

No credentials, no data/history.csv changes, no overwriting production spot values.
Only the publicly displayed first-party history route of guzhibiao.com is used.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import date
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

INDICATORS = {
    "dyr": ("dividend", "percent", 400),
    "pe_ttm": ("pe", "ratio", 400),
    "pb": ("pb", "ratio", 400),
    "ps_ttm": ("ps", "ratio", 400),
}


def active_specs() -> list[tuple]:
    config = yaml.safe_load(Path("watchlist.yaml").read_text(encoding="utf-8"))
    specs = []
    for item in config.get("instruments", []):
        src = item.get("source", {})
        sources = src.get("sources", []) if src.get("type") == "chain" else [src]
        if not any(candidate.get("type") == "guzhibiao" for candidate in sources):
            continue
        for metric in (item.get("metrics") or {}):
            if metric in INDICATORS:
                indicator, unit, minimum = INDICATORS[metric]
                specs.append((item["id"], item["name"], str(item["code"]),
                              metric, indicator, unit, minimum))
    return specs


FIELDS = ["day", "instrument_id", "instrument_name", "code", "metric", "value",
          "source", "weighting", "coverage_note"]
BASE = "https://guzhibiao.com/api/index"
OUT = Path("data/candidates/guzhibiao_funddb_history.csv")
SUMMARY = Path("data/candidates/guzhibiao_funddb_summary.json")


def collect(session: requests.Session, spec: tuple) -> tuple[list[dict], dict]:
    instrument_id, name, expected_code, metric, indicator, unit, min_weeks = spec
    url = f"{BASE}/{quote(name, safe='')}/history"
    response = session.get(url, params={"indicator": indicator}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != expected_code or payload.get("indicator") != indicator:
        raise ValueError(f"Unexpected index/metric identity for {name}: {payload.get('code')}/{payload.get('indicator')}")
    days = payload.get("dates")
    values = payload.get("values")
    if not isinstance(days, list) or not isinstance(values, list) or len(days) != len(values):
        raise ValueError(f"Invalid dated raw history for {name}")
    today = date.today()
    weekly: dict[tuple[int, int], tuple[date, float]] = {}
    valid_daily = 0
    for day_raw, value_raw in zip(days, values):
        try:
            day = date.fromisoformat(str(day_raw))
            value = float(value_raw)
        except (ValueError, TypeError):
            continue
        if day > today or day.year < 1990 or not math.isfinite(value) or value <= 0:
            continue
        if not 0 < value < (100 if unit == "percent" else 1000):
            continue
        valid_daily += 1
        iso = day.isocalendar()
        key = iso.year, iso.week
        previous = weekly.get(key)
        if previous is None or day > previous[0]:
            weekly[key] = (day, value)
    if len(weekly) < min_weeks:
        raise ValueError(f"Insufficient {name} public history: {len(weekly)} < {min_weeks}")
    rows = [
        dict(day=day.isoformat(), instrument_id=instrument_id, instrument_name=name,
             code=expected_code, metric=metric, value=format(value, ".10g"),
             source="guzhibiao-public-funddb-history", weighting="funddb-native-unverified",
             coverage_note="separate-candidate-do-not-merge-with-official-weighted-history")
        for day, value in sorted(weekly.values())
    ]
    report = dict(instrument_id=instrument_id, code=expected_code, metric=metric,
                  source_url=f"{url}?indicator={indicator}", raw_daily=valid_daily,
                  weekly_samples=len(rows), first=rows[0], last=rows[-1],
                  sampling="ISO-week last published trading day",
                  production_merge_allowed=False)
    return rows, report


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent":"ValuationMonitor/1.0 (public-history-research)",
                            "Accept":"application/json"})
    all_rows = []
    reports = []
    for spec in active_specs():
        try:
            rows, report = collect(session, spec)
        except Exception as exc:
            print(f"Not available for {spec[1]}: {exc}", flush=True)
            continue
        all_rows.extend(rows)
        reports.append(report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    if not all_rows:
        raise RuntimeError("No valid active third-party history was collected")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    SUMMARY.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Persisted {len(all_rows)} verified dated weekly CANDIDATES, no production changes.", flush=True)


if __name__ == "__main__":
    main()
