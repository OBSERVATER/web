from __future__ import annotations

import bisect
import math
import statistics
from datetime import date

from .models import Observation, StatSnapshot


def subtract_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, month=2, day=28)


def weekly_last(observations: list[Observation]) -> list[Observation]:
    selected: dict[tuple[int, int, str, str], Observation] = {}
    for item in observations:
        iso = item.day.isocalendar()
        key = (iso.year, iso.week, item.instrument_id, item.metric)
        previous = selected.get(key)
        if previous is None or item.day > previous.day:
            selected[key] = item
    return sorted(selected.values(), key=lambda x: (x.instrument_id, x.metric, x.day))


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if not 0 <= q <= 1:
        raise ValueError("q must be in [0, 1]")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def percentile_rank(values: list[float], current: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("values must not be empty")
    if len(ordered) == 1:
        return 1.0
    left = bisect.bisect_left(ordered, current)
    right = bisect.bisect_right(ordered, current)
    rank_index = (left + right - 1) / 2
    return min(1.0, max(0.0, rank_index / (len(ordered) - 1)))


def calculate_snapshot(values: list[float], current: float, higher_is_cheaper: bool) -> StatSnapshot:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v)) and float(v) > 0]
    if not clean:
        raise ValueError("No valid values")

    mean = statistics.fmean(clean)
    stddev = statistics.pstdev(clean) if len(clean) > 1 else 0.0
    q20 = percentile(clean, 0.20)
    median = percentile(clean, 0.50)
    q80 = percentile(clean, 0.80)
    zscore = 0.0 if stddev == 0 else (current - mean) / stddev

    return StatSnapshot(
        current=current,
        percentile=percentile_rank(clean, current),
        q20=q20,
        median=median,
        q80=q80,
        mean=mean,
        minimum=min(clean),
        maximum=max(clean),
        stddev=stddev,
        zscore=zscore,
        opportunity=q80 if higher_is_cheaper else q20,
        danger=q20 if higher_is_cheaper else q80,
        sample_count=len(clean),
        higher_is_cheaper=higher_is_cheaper,
    )
