from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .models import Instrument, Observation


class PublicSourceError(RuntimeError):
    pass


class PublicDataClient:
    DANJUAN_URL = "https://danjuanfunds.com/djapi/index_eva/dj"
    CNI_URL = "https://www.cnindex.com.cn/index/indexList"
    CSI_INDICATOR = (
        "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/"
        "autofile/indicator/{code}indicator.xls"
    )

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ValuationMonitor/1.0)",
            "Accept": "*/*",
        })
        self._danjuan_cache: list[dict[str, Any]] | None = None
        self._cni_cache: list[dict[str, Any]] | None = None

    def fetch_latest(self, instrument: Instrument, end: date | None = None) -> list[Observation]:
        source_type = str(instrument.source.get("type", "")).strip()
        if source_type == "chain":
            errors = []
            for candidate in instrument.source.get("sources", []):
                chained = Instrument(
                    id=instrument.id,
                    name=instrument.name,
                    market=instrument.market,
                    code=instrument.code,
                    metrics=instrument.metrics,
                    source=dict(candidate),
                )
                try:
                    rows = self.fetch_latest(chained, end=end)
                    if rows:
                        return rows
                except Exception as exc:
                    errors.append(f"{candidate.get('type')}: {exc}")
            raise PublicSourceError(
                f"All public sources failed for {instrument.name}: " + " | ".join(errors)
            )
        if source_type == "danjuan":
            return self._fetch_danjuan(instrument)
        if source_type == "cni":
            return self._fetch_cni(instrument)
        if source_type == "csindex_indicator":
            return self._fetch_csindex_indicator(instrument)
        if source_type == "public_page":
            return self._fetch_public_page(instrument)
        raise PublicSourceError(f"Unsupported source type: {source_type!r} for {instrument.name}")

    def fetch_range(self, instrument: Instrument, start: date, end: date) -> list[Observation]:
        source_type = str(instrument.source.get("type", "")).strip()
        if source_type == "csindex_indicator":
            return [
                item for item in self._fetch_csindex_indicator(instrument, all_rows=True)
                if start <= item.day <= end
            ]
        return []

    def _get_json(self, url: str, **kwargs) -> Any:
        response = self.session.get(url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response.json()

    def _danjuan_items(self) -> list[dict[str, Any]]:
        if self._danjuan_cache is not None:
            return self._danjuan_cache
        headers = {"Referer": "https://danjuanfunds.com/rn/value-center"}
        payload = self._get_json(self.DANJUAN_URL, headers=headers)
        items = payload.get("data", {}).get("items", [])
        if not isinstance(items, list):
            raise PublicSourceError("Danjuan returned unexpected payload")
        self._danjuan_cache = items
        return items

    @staticmethod
    def _normalise_code(value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", value.upper())

    def _match_danjuan(self, instrument: Instrument) -> dict[str, Any]:
        expected_code = self._normalise_code(str(instrument.source.get("index_code", instrument.code)))
        expected_name = str(instrument.source.get("name", instrument.name)).strip()

        by_name = []
        for item in self._danjuan_items():
            code = self._normalise_code(str(item.get("index_code", "")))
            name = str(item.get("name", ""))
            if expected_code and code == expected_code:
                return item
            if expected_name and expected_name in name:
                by_name.append(item)

        if len(by_name) == 1:
            return by_name[0]
        raise PublicSourceError(f"Danjuan index not found or ambiguous: {instrument.name}/{instrument.code}")

    def _fetch_danjuan(self, instrument: Instrument) -> list[Observation]:
        item = self._match_danjuan(instrument)
        ts = item.get("ts") or item.get("updated_at") or item.get("created_at")
        day = datetime.fromtimestamp(float(ts) / 1000).date() if ts else date.today()
        point = _as_float(item.get("current"))
        field_map = {
            "pe_ttm": ("pe", "pe_percentile"),
            "pb": ("pb", "pb_percentile"),
            "dyr": ("yeild", None),
        }

        result: list[Observation] = []
        for metric in instrument.metrics:
            mapping = field_map.get(metric.key)
            if mapping is None:
                continue
            field, percentile_field = mapping
            value = _as_float(item.get(field))
            if value is None:
                continue
            if metric.key == "dyr":
                value *= 100.0
            reported = _as_float(item.get(percentile_field)) if percentile_field else None
            result.append(Observation(
                day=day,
                instrument_id=instrument.id,
                instrument_name=instrument.name,
                market=instrument.market,
                code=instrument.code,
                metric=metric.key,
                weighting=metric.weighting,
                value=value,
                point=point,
                source="danjuan-public",
                reported_percentile=reported,
            ))
        return result

    def _cni_rows(self) -> list[dict[str, Any]]:
        if self._cni_cache is not None:
            return self._cni_cache
        payload = self._get_json(
            self.CNI_URL,
            params={"channelCode": "-1", "rows": "2000", "pageNum": "1"},
        )
        rows = payload.get("data", {}).get("rows", [])
        if not isinstance(rows, list):
            raise PublicSourceError("CNI returned unexpected payload")
        self._cni_cache = rows
        return rows

    def _fetch_cni(self, instrument: Instrument) -> list[Observation]:
        row = next(
            (x for x in self._cni_rows() if str(x.get("indexcode", "")).zfill(6) == instrument.code.zfill(6)),
            None,
        )
        if row is None:
            raise PublicSourceError(f"CNI index not found: {instrument.code}")

        point = _as_float(row.get("closeingPoint"))
        day = date.today()
        result: list[Observation] = []
        for metric in instrument.metrics:
            if metric.key != "pe_ttm":
                continue
            value = _as_float(row.get("peDynamic"))
            if value is None:
                continue
            result.append(Observation(
                day=day,
                instrument_id=instrument.id,
                instrument_name=instrument.name,
                market=instrument.market,
                code=instrument.code,
                metric=metric.key,
                weighting=metric.weighting,
                value=value,
                point=point,
                source="cnindex-official-public",
            ))
        return result

    def _fetch_csindex_indicator(self, instrument: Instrument, all_rows: bool = False) -> list[Observation]:
        url = self.CSI_INDICATOR.format(code=instrument.code)
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        frame = pd.read_excel(io.BytesIO(response.content))
        if frame.empty:
            return []

        columns = list(frame.columns)
        if len(columns) < 10:
            raise PublicSourceError(f"Unexpected CSI indicator columns: {columns}")

        frame = frame.rename(columns={
            columns[0]: "day",
            columns[1]: "code",
            columns[2]: "name_full",
            columns[3]: "name_short",
            columns[4]: "name_en_full",
            columns[5]: "name_en_short",
            columns[6]: "pe1",
            columns[7]: "pe2",
            columns[8]: "dyr1",
            columns[9]: "dyr2",
        })
        frame["day"] = pd.to_datetime(frame["day"], errors="coerce").dt.date
        frame = frame.dropna(subset=["day"]).sort_values("day")
        if not all_rows:
            frame = frame.tail(1)

        metric_fields = {
            "pe_ttm": str(instrument.source.get("pe_field", "pe2")),
            "dyr": str(instrument.source.get("dyr_field", "dyr2")),
        }
        result: list[Observation] = []
        for _, row in frame.iterrows():
            for metric in instrument.metrics:
                field = metric_fields.get(metric.key)
                if field is None:
                    continue
                value = _as_float(row.get(field))
                if value is None:
                    continue
                result.append(Observation(
                    day=row["day"],
                    instrument_id=instrument.id,
                    instrument_name=instrument.name,
                    market=instrument.market,
                    code=instrument.code,
                    metric=metric.key,
                    weighting=metric.weighting,
                    value=value,
                    point=None,
                    source="csindex-official-public",
                ))
        return result

    def _fetch_public_page(self, instrument: Instrument) -> list[Observation]:
        url = str(instrument.source.get("url", "")).strip()
        if not url:
            raise PublicSourceError(f"Missing public page URL for {instrument.name}")
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
        day = date.today()
        point = None
        point_pattern = instrument.source.get("point_pattern")
        if point_pattern:
            point = _search_number(str(point_pattern), text)

        result: list[Observation] = []
        patterns = instrument.source.get("patterns") or {}
        for metric in instrument.metrics:
            pattern = patterns.get(metric.key)
            if not pattern:
                continue
            value = _search_number(str(pattern), text)
            if value is None:
                continue
            result.append(Observation(
                day=day,
                instrument_id=instrument.id,
                instrument_name=instrument.name,
                market=instrument.market,
                code=instrument.code,
                metric=metric.key,
                weighting=metric.weighting,
                value=value,
                point=point,
                source=f"public-page:{url}",
            ))
        return result


def _search_number(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.I | re.S)
    if not match:
        return None
    return _as_float(match.group(1))


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
