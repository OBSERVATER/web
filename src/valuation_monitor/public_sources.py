from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta
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
    CSI_WEIGHT = (
        "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/"
        "autofile/closeweight/{code}closeweight.xls"
    )
    CNI_WEIGHT = "https://www.cnindex.com.cn/sample-detail/download-history"
    EASTMONEY_DC = "https://datacenter-web.eastmoney.com/api/data/v1/get"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ValuationMonitor/1.0)",
            "Accept": "*/*",
        })
        self._danjuan_cache: list[dict[str, Any]] | None = None
        self._cni_cache: list[dict[str, Any]] | None = None
        self.history_source_warnings: list[str] = []

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
        if source_type == "reconstructed":
            rows = self._fetch_reconstructed(instrument, end=end)
            return self._attach_index_points(instrument, rows)
        if source_type == "danjuan":
            rows = self._fetch_danjuan(instrument)
            return self._attach_index_points(instrument, rows)
        if source_type == "cni":
            rows = self._fetch_cni(instrument)
            return self._attach_index_points(instrument, rows)
        if source_type == "csindex_indicator":
            rows = self._fetch_csindex_indicator(instrument)
            return self._attach_index_points(instrument, rows)
        if source_type == "public_page":
            rows = self._fetch_public_page(instrument)
            return self._attach_index_points(instrument, rows)
        raise PublicSourceError(f"Unsupported source type: {source_type!r} for {instrument.name}")

    def fetch_range(self, instrument: Instrument, start: date, end: date) -> list[Observation]:
        source_type = str(instrument.source.get("type", "")).strip()

        if source_type == "chain":
            # Historical chains are complementary, not just fallbacks.  The first
            # configured source is authoritative for a week; later sources only
            # fill weeks the earlier sources do not provide.  This keeps source
            # methodologies from silently overwriting one another while still
            # extending sparse public history.
            chosen: dict[tuple[int, int, str], Observation] = {}
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
                    candidate_rows = self.fetch_range(chained, start, end)
                except Exception as exc:
                    self.history_source_warnings.append(f"{instrument.name}: {candidate.get('type')}: {exc}")
                    continue

                # Keep the last trading observation from this candidate for each
                # ISO week/metric, then only use it when a higher-priority source
                # has not already supplied that week.
                weekly: dict[tuple[int, int, str], Observation] = {}
                for item in candidate_rows:
                    iso = item.day.isocalendar()
                    key = (iso.year, iso.week, item.metric)
                    previous = weekly.get(key)
                    if previous is None or item.day > previous.day:
                        weekly[key] = item
                for key, item in weekly.items():
                    chosen.setdefault(key, item)

            return sorted(chosen.values(), key=lambda x: (x.metric, x.day))

        rows: list[Observation] = []
        if source_type == "danjuan":
            rows = self._fetch_danjuan_history(instrument, start, end)
        elif source_type == "csindex_indicator":
            rows = [
                item for item in self._fetch_csindex_indicator(instrument, all_rows=True)
                if start <= item.day <= end
            ]
        elif source_type == "public_page" and instrument.source.get("history_type") == "stockcheck_embedded":
            rows = self._fetch_stockcheck_embedded_history(instrument, start, end)
        elif source_type == "public_page" and instrument.source.get("history_type") == "baifenwei_percentile":
            rows = self._fetch_baifenwei_percentile_history(instrument, start, end)
        elif source_type == "public_html_table":
            rows = self._fetch_public_html_table_history(instrument, start, end)

        return self._attach_index_points(instrument, rows)

    def _get_json(self, url: str, **kwargs) -> Any:
        response = self.session.get(url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response.json()

    def _get_bytes_retry(self, url: str, *, params: dict | None = None, attempts: int = 3) -> bytes:
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                response = self.session.get(url, params=params, timeout=max(self.timeout, 60))
                response.raise_for_status()
                return response.content
            except Exception as exc:
                last_exc = exc
        raise PublicSourceError(f"Public file source failed: {url}: {last_exc}")

    def _eastmoney_index_points(self, secid: str, start: date, end: date) -> dict[date, float]:
        params = {
            "secid": secid,
            "klt": "101",
            "fqt": "1",
            "lmt": "10000",
            "beg": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "iscca": "1",
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
            "ut": "f057cbcbce2a86e2866ab8877db1d059",
            "forcect": "1",
        }
        payload = self._get_json(
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            params=params,
            headers={"Referer": "https://quote.eastmoney.com/"},
        )
        klines = (payload.get("data") or {}).get("klines") or []
        result: dict[date, float] = {}
        for line in klines:
            parts = str(line).split(",")
            if len(parts) < 3:
                continue
            try:
                day = date.fromisoformat(parts[0])
                close = float(parts[2])
            except (TypeError, ValueError):
                continue
            result[day] = close
        return result

    def _attach_index_points(
        self,
        instrument: Instrument,
        rows: list[Observation],
    ) -> list[Observation]:
        secid = str(instrument.source.get("point_secid", "")).strip()
        if not secid or not rows:
            return rows
        start = min(item.day for item in rows) - timedelta(days=10)
        end = max(item.day for item in rows) + timedelta(days=2)
        try:
            points = self._eastmoney_index_points(secid, start, end)
        except Exception:
            return rows
        if not points:
            return rows

        point_days = sorted(points)
        result: list[Observation] = []
        for item in rows:
            point = points.get(item.day)
            if point is None:
                prior = [d for d in point_days if d <= item.day]
                if prior and (item.day - prior[-1]).days <= 7:
                    point = points[prior[-1]]
            result.append(
                Observation(
                    day=item.day,
                    instrument_id=item.instrument_id,
                    instrument_name=item.instrument_name,
                    market=item.market,
                    code=item.code,
                    metric=item.metric,
                    weighting=item.weighting,
                    value=item.value,
                    point=point if point is not None else item.point,
                    source=item.source,
                    reported_percentile=item.reported_percentile,
                )
            )
        return result

    def _eastmoney_market_snapshot(self, target: date) -> tuple[date, pd.DataFrame]:
        for offset in range(0, 8):
            day = target - timedelta(days=offset)
            params = {
                "sortColumns": "SECURITY_CODE",
                "sortTypes": "1",
                "pageSize": "6000",
                "pageNumber": "1",
                "reportName": "RPT_VALUEANALYSIS_DET",
                "columns": "ALL",
                "quoteColumns": "",
                "source": "WEB",
                "client": "WEB",
                "filter": f"(TRADE_DATE='{day.isoformat()}')",
            }
            try:
                payload = self._get_json(
                    self.EASTMONEY_DC,
                    params=params,
                    headers={"Referer": "https://data.eastmoney.com/"},
                )
            except Exception:
                continue
            rows = (payload.get("result") or {}).get("data") or []
            if not rows:
                continue
            frame = pd.DataFrame(rows)
            if frame.empty or "SECURITY_CODE" not in frame.columns:
                continue
            frame["SECURITY_CODE"] = frame["SECURITY_CODE"].astype(str).str.zfill(6)
            for column in ("PE_TTM", "PB_MRQ", "PS_TTM", "TOTAL_MARKET_CAP"):
                if column in frame.columns:
                    frame[column] = pd.to_numeric(frame[column], errors="coerce")
            return day, frame
        raise PublicSourceError(f"No Eastmoney valuation snapshot on or before {target}")

    def _reconstructed_members(self, instrument: Instrument, target: date) -> pd.DataFrame:
        provider = str(instrument.source.get("index_provider", "")).lower()
        if provider == "cni":
            content = self._get_bytes_retry(self.CNI_WEIGHT, params={"indexcode": instrument.code})
            frame = pd.read_excel(io.BytesIO(content))
            if len(frame.columns) < 6:
                raise PublicSourceError("Unexpected CNI weight file")
            frame = frame.iloc[:, :6].copy()
            frame.columns = ["day", "code", "name", "industry", "market_cap", "weight"]
            frame["day"] = pd.to_datetime(frame["day"], errors="coerce")
            frame["code"] = frame["code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
            frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce")
            eligible = frame[frame["day"] <= pd.Timestamp(target)]
            if eligible.empty:
                eligible = frame
            latest_day = eligible["day"].max()
            return eligible[eligible["day"] == latest_day].copy()

        if provider == "csi":
            content = self._get_bytes_retry(self.CSI_WEIGHT.format(code=instrument.code))
            frame = pd.read_excel(io.BytesIO(content))
            if len(frame.columns) < 10:
                raise PublicSourceError("Unexpected CSI weight file")
            frame = frame.iloc[:, :10].copy()
            frame.columns = [
                "day", "index_code", "index_name", "index_name_en", "code",
                "name", "name_en", "exchange", "exchange_en", "weight",
            ]
            frame["day"] = pd.to_datetime(
                frame["day"].astype(str).str.replace(r"\.0$", "", regex=True),
                format="%Y%m%d",
                errors="coerce",
            )
            frame["code"] = frame["code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
            frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce")
            eligible = frame[frame["day"] <= pd.Timestamp(target)]
            if eligible.empty:
                eligible = frame
            latest_day = eligible["day"].max()
            return eligible[eligible["day"] == latest_day].copy()

        raise PublicSourceError(f"Unsupported reconstructed index provider: {provider}")

    def _fetch_reconstructed(self, instrument: Instrument, end: date | None = None) -> list[Observation]:
        target = end or date.today()
        day, market = self._eastmoney_market_snapshot(target)
        members = self._reconstructed_members(instrument, day)
        if members.empty:
            raise PublicSourceError(f"No constituent weights for {instrument.name}")

        metric_fields = {
            "pe_ttm": "PE_TTM",
            "pb": "PB_MRQ",
            "ps_ttm": "PS_TTM",
        }
        aggregation = str(instrument.source.get("aggregation", "index_weight_harmonic"))
        result: list[Observation] = []

        for metric in instrument.metrics:
            field = metric_fields.get(metric.key)
            if field is None or field not in market.columns:
                continue
            merged = members[["code", "weight"]].merge(
                market[["SECURITY_CODE", field, "TOTAL_MARKET_CAP"]],
                left_on="code",
                right_on="SECURITY_CODE",
                how="left",
            )
            merged = merged.rename(columns={field: "value"})
            merged["value"] = pd.to_numeric(merged["value"], errors="coerce")
            merged["weight"] = pd.to_numeric(merged["weight"], errors="coerce")
            merged["TOTAL_MARKET_CAP"] = pd.to_numeric(merged["TOTAL_MARKET_CAP"], errors="coerce")
            valid = merged[
                merged["value"].notna()
                & (merged["value"] > 0)
            ].copy()
            if valid.empty:
                continue

            if aggregation == "index_weight_harmonic":
                valid["w"] = valid["weight"] / 100.0
                valid = valid[valid["w"].notna() & (valid["w"] > 0)]
                weight_sum = valid["w"].sum()
                denominator = (valid["w"] / valid["value"]).sum()
                value = weight_sum / denominator if denominator else None
            elif aggregation == "market_cap_harmonic":
                valid = valid[
                    valid["TOTAL_MARKET_CAP"].notna()
                    & (valid["TOTAL_MARKET_CAP"] > 0)
                ]
                market_cap_sum = valid["TOTAL_MARKET_CAP"].sum()
                denominator = (valid["TOTAL_MARKET_CAP"] / valid["value"]).sum()
                value = market_cap_sum / denominator if denominator else None
            else:
                raise PublicSourceError(f"Unsupported aggregation: {aggregation}")

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
                    weighting=aggregation,
                    value=float(value),
                    point=None,
                    source=f"reconstructed:{instrument.source.get('index_provider')}+eastmoney:{aggregation}",
                )
            )
        return result

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
        explicit_code = str(instrument.source.get("index_code", "")).strip()
        if explicit_code:
            try:
                item = self._get_json(
                    f"https://danjuanfunds.com/djapi/index_eva/detail/{explicit_code}",
                    headers={"Referer": "https://danjuanfunds.com/djmodule/value-center"},
                ).get("data") or {}
                if not item:
                    item = self._match_danjuan(instrument)
            except Exception:
                item = self._match_danjuan(instrument)
        else:
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

    def _fetch_danjuan_history(
        self,
        instrument: Instrument,
        start: date,
        end: date,
    ) -> list[Observation]:
        symbol = str(instrument.source.get("index_code", "")).strip()
        if not symbol:
            try:
                item = self._match_danjuan(instrument)
                symbol = str(item.get("index_code", "")).strip()
            except Exception:
                return []
        if not symbol:
            return []

        metric_map = {
            "pe_ttm": ("pe_history", "index_eva_pe_growths", "pe"),
            "pb": ("pb_history", "index_eva_pb_growths", "pb"),
        }
        result: list[Observation] = []
        headers = {"Referer": "https://danjuanfunds.com/djmodule/value-center"}

        for metric in instrument.metrics:
            mapping = metric_map.get(metric.key)
            if mapping is None:
                continue
            endpoint, list_key, value_key = mapping
            payload = self._get_json(
                f"https://danjuanfunds.com/djapi/index_eva/{endpoint}/{symbol}?day=all",
                headers=headers,
            )
            rows = (payload.get("data") or {}).get(list_key) or []
            for row in rows:
                ts = row.get("ts")
                value = _as_float(row.get(value_key))
                if ts is None or value is None:
                    continue
                day = datetime.fromtimestamp(float(ts) / 1000).date()
                if not (start <= day <= end):
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
                        point=None,
                        source="danjuan-public-history",
                    )
                )
        return sorted(result, key=lambda x: (x.metric, x.day))

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
        frame["day"] = pd.to_datetime(
            frame["day"].astype(str).str.replace(r"\\.0$", "", regex=True),
            format="%Y%m%d",
            errors="coerce",
        ).dt.date
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

    def _fetch_public_html_table_history(
        self, instrument: Instrument, start: date, end: date,
    ) -> list[Observation]:
        """Optional token-free public HTML dated table; never interpolate."""
        url = str(instrument.source.get("url", "")).strip()
        metric_key = instrument.metrics[0].key if len(instrument.metrics) == 1 else ""
        label = {
            "dyr": ("股息率", "Dividend Yield"),
            "pb": ("市净率", "Price to Book"),
            "pe_ttm": ("市盈率", "P/E"),
            "ps_ttm": ("市销率", "P/S"),
        }.get(metric_key)
        if not url or label is None:
            return []
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        result: list[Observation] = []
        for table in soup.select("table"):
            heads = [cell.get_text(" ", strip=True) for cell in table.select("thead th")]
            if not heads:
                head_row = table.find("tr")
                heads = [x.get_text(" ", strip=True) for x in head_row.find_all(["td", "th"])] if head_row else []
            date_col = next((i for i, h in enumerate(heads) if h in ("日期", "Date")), None)
            value_col = next((i for i, h in enumerate(heads) if any(h.startswith(s) for s in label)), None)
            if date_col is None or value_col is None or date_col == value_col:
                continue
            for tr in table.find_all("tr"):
                cells = [x.get_text(" ", strip=True) for x in tr.find_all(["td", "th"])]
                if max(date_col, value_col) >= len(cells):
                    continue
                try:
                    day = date.fromisoformat(cells[date_col][:10])
                except ValueError:
                    continue
                if not (start <= day <= end):
                    continue
                val = _as_float(cells[value_col])
                if val is None or val <= 0:
                    continue
                result.append(Observation(
                    day=day, instrument_id=instrument.id, instrument_name=instrument.name,
                    market=instrument.market, code=instrument.code, metric=metric_key,
                    weighting=str(instrument.source.get("weighting", "unverified")),
                    value=val, point=None, source=f"public-html-table:{url}",
                ))
        return sorted(result, key=lambda x: x.day)

    def _fetch_baifenwei_percentile_history(
        self,
        instrument: Instrument,
        start: date,
        end: date,
    ) -> list[Observation]:
        url = str(instrument.source.get("url", "")).strip()
        if not url:
            return []
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        match = re.search(r"var\s+d\s*=\s*(\[.*?\]);\s*var\s+ctx", response.text, re.S)
        if not match:
            return []

        import json
        try:
            rows = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        percentile_fields = {
            "pe_ttm": "pe_pct",
            "pb": "pb_pct",
            "ps_ttm": "ps_pct",
        }
        result: list[Observation] = []
        for metric in instrument.metrics:
            field = percentile_fields.get(metric.key)
            if not field:
                continue
            for row in rows:
                try:
                    day = date.fromisoformat(str(row.get("date")))
                    pct = float(row.get(field))
                except (TypeError, ValueError):
                    continue
                if not (start <= day <= end):
                    continue
                point = _as_float(row.get("point"))
                result.append(
                    Observation(
                        day=day,
                        instrument_id=instrument.id,
                        instrument_name=instrument.name,
                        market=instrument.market,
                        code=instrument.code,
                        metric=metric.key,
                        weighting=metric.weighting,
                        value=0.0,
                        point=point,
                        source="baifenwei-percentile-history",
                        reported_percentile=pct / 100.0,
                    )
                )
        return result

    def _fetch_stockcheck_embedded_history(
        self,
        instrument: Instrument,
        start: date,
        end: date,
    ) -> list[Observation]:
        url = str(instrument.source.get("url", "")).strip()
        if not url:
            return []
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        match = re.search(r"window\.__SSG_CHART__\s*=\s*(\{.*?\});", response.text, re.S)
        if not match:
            return []

        import json
        payload = json.loads(match.group(1))
        window = payload.get("10Y") or {}
        dates = window.get("dates") or []
        metric_map = {"pe_ttm": "pe", "pb": "pb"}
        result: list[Observation] = []

        for metric in instrument.metrics:
            field = metric_map.get(metric.key)
            if not field:
                continue
            values = window.get(field) or []
            for raw_day, raw_value in zip(dates, values):
                try:
                    day = date.fromisoformat(str(raw_day))
                    value = float(raw_value)
                except (TypeError, ValueError):
                    continue
                if not (start <= day <= end):
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
                        point=None,
                        source="stockcheck-public-history",
                    )
                )
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
            percentile_patterns = instrument.source.get("percentile_patterns") or {}
            percentile_pattern = percentile_patterns.get(metric.key)
            reported_percentile = None
            if percentile_pattern:
                raw_percentile = _search_number(str(percentile_pattern), text)
                if raw_percentile is not None:
                    reported_percentile = raw_percentile / 100.0
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
                reported_percentile=reported_percentile,
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
