"""One-time read-only probe of daily index closes. No accounts, no tokens, no repo writes."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import akshare as ak
import pandas as pd
import requests

OUT = Path("out/index-history-probe")
OUT.mkdir(parents=True, exist_ok=True)
TODAY = date(2026, 10, 26)
RESULTS = {}
SPECS = [
    ("value100", "价值100", "980081", 2012, "cni"),
    ("csi_dividend", "中证红利", "000922", 2004, "csindex"),
    ("csi300", "沪深300", "000300", 2004, "csindex"),
    ("sp500", "标普500", "SP500", 2010, "fred"),
]


def call_part(kind, code, start, end):
    s, e = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    if kind == "cni":
        return ak.index_hist_cni(symbol=code, start_date=s, end_date=e)
    if kind == "csindex":
        return ak.stock_zh_index_hist_csindex(symbol=code, start_date=s, end_date=e)
    raise ValueError(kind)


def cni_new_api(code, start, end):
    # Backup for the March 2026 endpoint change; only used when AKShare fails.
    url = "https://hq.cnindex.com.cn/market/market/getIndexDailyData"
    headers = {"Origin": "https://www.cnindex.com.cn",
               "Referer": "https://www.cnindex.com.cn/",
               "User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, params={
        "indexCode": code, "startDate": start.isoformat(),
        "endDate": end.isoformat()}, timeout=25)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data")
    if isinstance(rows, dict):
        rows = rows.get("data")
    if not isinstance(rows, list):
        raise ValueError(f"Unrecognized response structure {str(payload)[:240]}")
    if not rows:
        return pd.DataFrame(columns=["日期","收盘价"])
    if isinstance(rows[0], dict):
        return pd.DataFrame(rows)
    if len(rows[0]) >= 6:
        return pd.DataFrame({"日期":[r[0] for r in rows],"收盘价":[r[5] for r in rows]})
    raise ValueError(f"Unknown row format {str(rows[0])[:240]}")


def years(start_year, end_date, size=3):
    for y in range(start_year, end_date.year + 1, size):
        beg = date(y, 1, 1)
        end = min(date(y + size - 1, 12, 31), end_date)
        yield beg, end


def normalize(df, date_col, close_col):
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "close"])
    if date_col not in df or close_col not in df:
        raise ValueError(f"Missing columns; got {list(df.columns)}")
    x = df[[date_col, close_col]].copy()
    x.columns = ["date", "close"]
    x["date"] = pd.to_datetime(x["date"], errors="coerce")
    x["close"] = pd.to_numeric(x["close"], errors="coerce")
    x = x.dropna()
    x = x[(x["close"] > 0) & (x["date"].dt.date <= TODAY)]
    return x


def load_fred():
    # The public graph CSV needs no FRED API key; the official SP500 series
    # ordinarily provides about the most recent ten years only.
    uri = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500"
    r = requests.get(uri, timeout=40, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    from io import StringIO
    frame = pd.read_csv(StringIO(r.text))
    date_col = frame.columns[0]
    close_col = "SP500" if "SP500" in frame else frame.columns[-1]
    return normalize(frame, date_col, close_col)


def probe(spec):
    ident, name, code, start_year, kind = spec
    errors = []
    fragments = []
    attempts = []
    if kind == "fred":
        try:
            frame = load_fred()
            fragments.append(frame)
            attempts.append({"source":"FRED", "status":"ok", "rows":len(frame)})
        except Exception as exc:
            errors.append(f"FRED: {type(exc).__name__}: {str(exc)[:250]}")
    else:
        for start, end in years(start_year, TODAY):
            if kind == "cni":
                chain = [("AKShare.index_hist_cni",lambda: call_part(kind,code,start,end)),
                         ("CNI.new_api", lambda: cni_new_api(code,start,end))]
            else:
                chain = [("AKShare.stock_zh_index_hist_csindex",lambda: call_part(kind,code,start,end))]
            for label,fn in chain:
                try:
                    result = fn()
                    cols = list(result.columns)
                    if kind == "cni" and "收盘价" not in cols and "收盘" in cols:
                        result = result.rename(columns={"收盘":"收盘价"})
                    frame = normalize(result, "日期", "收盘价" if kind == "cni" else "收盘")
                    attempts.append({"source":label, "start":str(start), "end":str(end),
                                     "status":"ok", "rows":len(frame)})
                    if not frame.empty:
                        fragments.append(frame)
                        break
                except Exception as exc:
                    errors.append(f"{label} {start}..{end}: {type(exc).__name__}: {str(exc)[:250]}")
                    attempts.append({"source":label,"start":str(start),"end":str(end),"status":"error"})
            time.sleep(0.3)
    if fragments:
        merged = pd.concat(fragments, ignore_index=True)
        conflicts = int((merged.groupby("date")["close"].nunique() > 1).sum())
        merged = merged.drop_duplicates(subset=["date"], keep="first").sort_values("date")
        merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
        merged.to_csv(OUT / f"{ident}.csv",index=False,encoding="utf-8")
        first, last = merged.iloc[0], merged.iloc[-1]
        diffs = pd.to_datetime(merged["date"]).diff().dt.days
        result = {"name":name,"index":code,"status":"ok","rows":len(merged),
                  "earliest":first["date"],"earliest_close":float(first["close"]),
                  "latest":last["date"],"latest_close":float(last["close"]),
                  "duplicate_date_conflicts":conflicts,
                  "max_calendar_gap_days":int(diffs.max()) if len(merged)>1 else None,
                  "attempts":attempts,"errors":errors}
    else:
        result = {"name":name,"index":code,"status":"failed",
                  "rows":0,"attempts":attempts,"errors":errors}
    RESULTS[ident] = result
    (OUT / "summary.json").write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2),
                                       encoding="utf-8")
    print(f"RESULT {ident}: status={result['status']} rows={result['rows']} "
          f"dates={result.get('earliest')}..{result.get('latest')} "
          f"close={result.get('latest_close')}", flush=True)
    if errors:
        print(f"  warnings ({len(errors)}): {errors[:3]}",flush=True)


for spec in SPECS:
    probe(spec)
print(json.dumps({k:{field:v.get(field) for field in
      ("status","rows","earliest","latest","latest_close","duplicate_date_conflicts")}
      for k,v in RESULTS.items()}, ensure_ascii=False,indent=2),flush=True)
