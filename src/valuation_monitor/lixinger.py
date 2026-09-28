from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Iterable

import requests

from .models import Instrument, MetricSpec, Observation


class LixingerError(RuntimeError):
    pass


class LixingerClient:
    BASE_URLS = {
        "cn": "https://open.lixinger.com/api/cn/index/fundamental",
        "hk": "https://open.lixinger.com/api/hk/index/fundamental",
        "us": "https://open.lixinger.com/api/us/index/fundamental",
    }

    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        self.token = token or os.getenv("LIXINGER_TOKEN", "")
        if not self.token:
            raise LixingerError("LIXINGER_TOKEN is not configured")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    def _endpoint(self, market: str) -> str:
        try:
            return self.BASE_URLS[market]
        except KeyError as exc:
            raise LixingerError(f"Unsupported market: {market}") from exc

    def _post(self, market: str, payload: dict) -> list[dict]:
        payload = dict(payload)
        payload["token"] = self.token
        response = self.session.post(self._endpoint(market), json=payload, timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 1:
            raise LixingerError(f"Lixinger API error: {body.get('message') or body}")
        data = body.get("data") or []
        if not isinstance(data, list):
            raise LixingerError("Lixinger API returned unexpected data shape")
        return data

    @staticmethod
    def _metric_keys(metrics: Iterable[MetricSpec]) -> list[str]:
        return [metric.source_key for metric in metrics]

    def fetch_range(self, instrument: Instrument, start: date, end: date) -> list[Observation]:
        metrics = list(instrument.metrics)
        payload = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "stockCodes": [instrument.code],
            "metricsList": ["cp", *self._metric_keys(metrics)],
        }
        rows = self._post(instrument.market, payload)
        return self._rows_to_observations(instrument, metrics, rows)

    def fetch_latest(self, instrument: Instrument, end: date | None = None, lookback_days: int = 10) -> list[Observation]:
        end = end or date.today()
        start = end - timedelta(days=lookback_days)
        observations = self.fetch_range(instrument, start, end)
        if not observations:
            return []
        latest_day = max(item.day for item in observations)
        return [item for item in observations if item.day == latest_day]

    def fetch_on_date(self, instrument: Instrument, target: date) -> list[Observation]:
        payload = {
            "date": target.isoformat(),
            "stockCodes": [instrument.code],
            "metricsList": ["cp", *self._metric_keys(instrument.metrics)],
        }
        rows = self._post(instrument.market, payload)
        return self._rows_to_observations(instrument, list(instrument.metrics), rows)

    @staticmethod
    def _parse_date(raw: str) -> date:
        return date.fromisoformat(raw[:10])

    def _rows_to_observations(
        self,
        instrument: Instrument,
        metrics: list[MetricSpec],
        rows: list[dict],
    ) -> list[Observation]:
        result: list[Observation] = []
        for row in rows:
            raw_date = row.get("date")
            if not raw_date:
                continue
            day = self._parse_date(raw_date)
            point = _as_float(row.get("cp"))
            for metric in metrics:
                value = _as_float(row.get(metric.source_key))
                if value is None:
                    continue
                result.append(
                    Observation(
                        day=day,
                        instrument_id=instrument.id,
                        instrument_name=instrument.name,
                        market=instrument.market,
                        code=instrument.code,
                        metric=metric.key,
                        weighting=metric.weighting,
                        value=value,
                        point=point,
                        source="lixinger",
                    )
                )
        return result


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
