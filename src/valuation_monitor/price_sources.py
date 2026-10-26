"""Anonymous public index daily-close adapters; do not combine different index identities."""
from __future__ import annotations

import math
from datetime import date, timedelta, datetime, timezone
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd
import requests
import pandas_market_calendars as mcal

PRICES = {
    "value100": ("cn", date(2012, 12, 31), "980081", "cni"),
    "csi_dividend": ("cn", date(2004, 12, 31), "000922", "csi"),
    "csi300": ("cn", date(2004, 12, 31), "000300", "csi"),
    "sp500": ("us", date(2000, 1, 3), "^GSPC", "yahoo"),
    "nasdaq100": ("us", date(2000, 1, 3), "^NDX", "yahoo"),
}


def normalized_dates(frame: pd.DataFrame, date_col: str, close_col: str,
                     market: str, begin: date, end: date) -> dict[date, float]:
    if frame is None or frame.empty:
        return {}
    if date_col not in frame or close_col not in frame:
        raise ValueError(f"Unexpected historical columns: {list(frame.columns)}")
    df = frame[[date_col, close_col]].copy()
    df.columns = ["day", "close"]
    df["day"] = pd.to_datetime(df["day"], errors="coerce").dt.date
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna()
    df = df[df["day"].between(begin, end) & (df["close"] > 0)]
    if df.empty:
        return {}
    # Check known exchange calendar for every date; never treat a weekend
    # or holiday synthetic base observation as a tradable daily closing price.
    calendar = mcal.get_calendar("SSE" if market == "cn" else "NYSE")
    sessions = calendar.valid_days(start_date=begin, end_date=end)
    allowed = set(pd.to_datetime(sessions).date)
    result = {}
    for _, row in df.iterrows():
        day, value = row["day"], float(row["close"])
        if not math.isfinite(value) or day not in allowed:
            continue
        old = result.get(day)
        if old is not None and abs(old - value) > max(0.01, old * 0.0001):
            raise ValueError(f"Contradictory closing values for {day}")
        result[day] = value
    return result


def _windows(begin: date, end: date):
    start = begin
    while start <= end:
        finish = min(date(start.year + 2, 12, 31), end)
        yield start, finish
        start = finish + timedelta(days=1)


def _akshare_daily(kind: str, symbol: str, begin: date, end: date) -> pd.DataFrame:
    parts = []
    for start, finish in _windows(begin, end):
        if kind == "cni":
            item = ak.index_hist_cni(symbol=symbol, start_date=start.strftime("%Y%m%d"),
                                     end_date=finish.strftime("%Y%m%d"))
            if item is not None and not item.empty:
                if "收盘价" not in item and "收盘" in item:
                    item = item.rename(columns={"收盘": "收盘价"})
                parts.append(item[["日期", "收盘价"]].rename(columns={"收盘价": "close"}))
        else:
            item = ak.stock_zh_index_hist_csindex(
                symbol=symbol, start_date=start.strftime("%Y%m%d"),
                end_date=finish.strftime("%Y%m%d"))
            if item is not None and not item.empty:
                parts.append(item[["日期", "收盘"]].rename(columns={"收盘": "close"}))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["日期", "close"])


def _yahoo_daily(symbol: str, begin: date, end: date) -> pd.DataFrame:
    if symbol not in ("^GSPC", "^NDX"):
        raise ValueError(f"Unexpected Yahoo index symbol: {symbol}")
    from urllib.parse import quote
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}"
    params = {"interval": "1d", "period1": str(int(datetime(begin.year,begin.month,begin.day,tzinfo=timezone.utc).timestamp())),
              "period2": str(int(datetime.combine(end+timedelta(days=1),datetime.min.time(),timezone.utc).timestamp()))}
    reply = requests.get(url, params=params, timeout=30, headers={"User-Agent":"Mozilla/5.0"})
    reply.raise_for_status()
    entry = reply.json()["chart"]["result"][0]
    stamps = entry["timestamp"]
    closes = entry["indicators"]["quote"][0]["close"]
    days = [datetime.fromtimestamp(stamp, timezone.utc).date() for stamp in stamps]
    return pd.DataFrame({"日期": days, "close": closes})


def fetch_daily(instrument_id: str, begin: date, end: date) -> list[dict]:
    market, origin, symbol, kind = PRICES[instrument_id]
    begin = max(origin, begin)
    if begin > end:
        return []
    if kind in ("cni","csi"):
        frame = _akshare_daily(kind, symbol, begin, end)
    else:
        frame = _yahoo_daily(symbol, begin, end)
    values = normalized_dates(frame, "日期", "close", market, begin, end)
    if not values:
        raise ValueError(f"No valid daily close for {instrument_id} ({begin} to {end})")
    # One stable canonical series per index, with a fixed provider identity.
    source = f"akshare-{kind}:{symbol}" if kind != "yahoo" else f"yahoo:{symbol}:price"
    return [{"day": day.isoformat(), "instrument_id": instrument_id,
             "close": price, "source": source} for day, price in sorted(values.items())]
