from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .models import Observation


FIELDS = [
    "day",
    "instrument_id",
    "instrument_name",
    "market",
    "code",
    "metric",
    "weighting",
    "value",
    "point",
    "source",
    "reported_percentile",
]


def load_history(path: str | Path) -> list[Observation]:
    path = Path(path)
    if not path.exists():
        return []
    result: list[Observation] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            result.append(
                Observation(
                    day=date.fromisoformat(row["day"]),
                    instrument_id=row["instrument_id"],
                    instrument_name=row["instrument_name"],
                    market=row["market"],
                    code=row["code"],
                    metric=row["metric"],
                    weighting=row.get("weighting") or "aggregate",
                    value=float(row["value"]),
                    point=float(row["point"]) if row.get("point") else None,
                    source=row.get("source") or "unknown",
                    reported_percentile=float(row["reported_percentile"]) if row.get("reported_percentile") else None,
                )
            )
    return result


def save_history(path: str | Path, observations: list[Observation]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(observations, key=lambda x: (x.instrument_id, x.metric, x.day))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for item in ordered:
            row = asdict(item)
            row["day"] = item.day.isoformat()
            row["point"] = "" if item.point is None else f"{item.point:.12g}"
            row["value"] = f"{item.value:.12g}"
            row["reported_percentile"] = (
                "" if item.reported_percentile is None else f"{item.reported_percentile:.12g}"
            )
            writer.writerow(row)


def merge_weekly(existing: list[Observation], incoming: list[Observation]) -> list[Observation]:
    by_key: dict[tuple[int, int, str, str], Observation] = {}
    for item in [*existing, *incoming]:
        iso = item.day.isocalendar()
        key = (iso.year, iso.week, item.instrument_id, item.metric)
        previous = by_key.get(key)
        if previous is None or item.day >= previous.day:
            by_key[key] = item
    return sorted(by_key.values(), key=lambda x: (x.instrument_id, x.metric, x.day))
