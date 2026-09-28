from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


METRIC_LABELS = {
    "pe_ttm": "市盈率TTM",
    "pb": "市净率LF",
    "ps_ttm": "市销率TTM",
    "dyr": "股息率",
}

HIGHER_IS_CHEAPER = {"dyr"}


@dataclass(frozen=True)
class MetricSpec:
    key: str
    weighting: str = "aggregate"

    @property
    def label(self) -> str:
        return METRIC_LABELS.get(self.key, self.key)

    @property
    def higher_is_cheaper(self) -> bool:
        return self.key in HIGHER_IS_CHEAPER


@dataclass(frozen=True)
class Instrument:
    id: str
    name: str
    market: str
    code: str
    metrics: tuple[MetricSpec, ...]
    source: dict[str, Any]


@dataclass(frozen=True)
class Observation:
    day: date
    instrument_id: str
    instrument_name: str
    market: str
    code: str
    metric: str
    weighting: str
    value: float
    point: float | None
    source: str
    reported_percentile: float | None = None


@dataclass(frozen=True)
class StatSnapshot:
    current: float
    percentile: float
    q20: float
    median: float
    q80: float
    mean: float
    minimum: float
    maximum: float
    stddev: float
    zscore: float
    opportunity: float
    danger: float
    sample_count: int
    higher_is_cheaper: bool
