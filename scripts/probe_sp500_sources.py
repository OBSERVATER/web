"""Network test: original providers and alternative uncredentialed S&P 500 daily series."""
from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import date
from pathlib import Path

OUT = Path("out/sp500-sources")
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = ("old_eastmoney", "old_danjuan", "akshare_sina", "akshare_eastmoney_global", "yahoo_chart")


def summarize(values, source):
    import pandas as pd
    frame = pd.DataFrame(values, columns=["day", "close"])
    if frame.empty:
        raise ValueError("no daily closes")
    frame["day"] = pd.to_datetime(frame.day, errors="coerce")
    frame["close"] = pd.to_numeric(frame.close, errors="coerce")
    frame = frame.dropna().sort_values("day")
    frame = frame[(frame.close > 0) & (frame.day.dt.date <= date(2026, 10, 26))]
    if frame.empty:
        raise ValueError("no valid dates/prices")
    dupe_conflicts = int((frame.groupby("day")["close"].nunique() > 1).sum())
    frame = frame.drop_duplicates("day", keep="last")
    frame["day"] = frame.day.dt.strftime("%Y-%m-%d")
    frame.to_csv(OUT / f"{source}.csv", index=False)
    return {"rows":len(frame), "earliest":str(frame.iloc[0].day),
            "latest":str(frame.iloc[-1].day), "latest_close":float(frame.iloc[-1].close),
            "head":frame.head(3).to_dict("records"),"tail":frame.tail(3).to_dict("records"),
            "duplicate_conflicts":dupe_conflicts}


def one(source):
    if source == "old_eastmoney":
        sys.path.insert(0,"src")
        from valuation_monitor.public_sources import PublicDataClient
        client=PublicDataClient()
        dayprice=client._eastmoney_index_points("100.SPX",date(2000,1,1),date(2026,10,26))
        return summarize(dayprice.items(),source)
    if source == "old_danjuan":
        import requests
        url="https://danjuanfunds.com/djapi/index_eva/detail/SP500"
        r=requests.get(url,timeout=18,headers={"Referer":"https://danjuanfunds.com/djmodule/value-center",
                                              "User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        payload=r.json()
        item=payload.get("data") or {}
        if not item:
            raise ValueError(f"Empty data: {str(payload)[:240]}")
        return {"status_code":r.status_code,
                "fields":sorted(item.keys())[:50],
                "code":item.get("index_code"),
                "value":item.get("current"),"pe":item.get("pe"),
                "ts":item.get("ts") or item.get("updated_at")}
    if source == "akshare_sina":
        import akshare as ak
        df=ak.index_us_stock_sina(symbol=".INX")
        return summarize(zip(df["date"],df["close"]),source)
    if source == "akshare_eastmoney_global":
        import akshare as ak
        df=ak.index_global_hist_em(symbol="标普500")
        print(f"COLUMNS {list(df.columns)}",flush=True)
        pricefield=("最新价" if "最新价" in df.columns else "收盘价")
        return summarize(zip(df["日期"],df[pricefield]),source)
    if source == "yahoo_chart":
        import requests
        url="https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC"
        r=requests.get(url,timeout=18,headers={"User-Agent":"Mozilla/5.0"},
           params={"period1":"946684800","period2":"1793145600","interval":"1d"})
        r.raise_for_status()
        response=r.json()
        item=response["chart"]["result"][0]
        stamps=item.get("timestamp") or []
        close=item["indicators"]["quote"][0]["close"]
        from datetime import datetime, timezone
        pairs=[(datetime.fromtimestamp(t,timezone.utc).date(),value)
               for t,value in zip(stamps,close) if value is not None and math.isfinite(value)]
        return summarize(pairs,source)
    raise ValueError(source)


def main():
    if len(sys.argv)>1:
        result=one(sys.argv[1])
        print("TEST_RESULT_JSON="+json.dumps(result,ensure_ascii=False,default=str),flush=True)
        return
    results={}
    for source in SOURCES:
        try:
            r=subprocess.run([sys.executable,__file__,source],capture_output=True,text=True,timeout=70)
            if r.returncode:
                results[source]={"status":"error","detail":(r.stderr+"\n"+r.stdout)[-900:]}
            else:
                tagged=[line for line in r.stdout.splitlines() if line.startswith("TEST_RESULT_JSON=")]
                if not tagged:
                    raise ValueError(f"No output result: {r.stdout[-400:]}")
                results[source]={"status":"ok",**json.loads(tagged[-1].split("=",1)[1])}
        except subprocess.TimeoutExpired:
            results[source]={"status":"timeout","detail":"70 seconds"}
        except Exception as e:
            results[source]={"status":"error","detail":str(e)}
        (OUT/"summary.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
        record=results[source]
        print("PROBE",source,record.get("status"),"rows",record.get("rows"),
              "range",record.get("earliest"),record.get("latest"),
              "close",record.get("latest_close"),"err",record.get("detail","")[:200],flush=True)
    print("SUMMARY="+json.dumps(results,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
