"""Validate Nasdaq-100 valuation against the supplied 10Y weekly screenshot.

Audit data is explicitly descriptive; it never alters production PE or drawdown.
"""
from __future__ import annotations
import csv
import json
from datetime import date
from pathlib import Path

from valuation_monitor.stats import calculate_snapshot

REFERENCE = {"current": 28.68, "percentile": 36.47, "opportunity": 26.57,
             "danger": 35.86, "median": 31.02, "mean": 31.12,
             "minimum": 20.10, "maximum": 42.94, "zscore": -0.51}


def read_records(path, instrument, value_col):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        records=[]
        for row in csv.DictReader(handle):
            if row.get("instrument_id") != instrument:
                continue
            try:
                records.append((date.fromisoformat(row["day"]),float(row[value_col]),row))
            except (KeyError,TypeError,ValueError):
                continue
    return sorted(records)


def main():
    latest=json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    price=json.loads(Path("out/price_snapshot.json").read_text(encoding="utf-8"))
    ndx=next((row for row in latest["items"] if row["instrument_id"]=="nasdaq100"),None)
    ndx_price=next((row for row in price["items"] if row["instrument_id"]=="nasdaq100"),None)
    hist=read_records("data/history.csv","nasdaq100","value")
    hist=[r for r in hist if r[0]>=date(2016,10,26)
          and r[2]["source"].startswith("danjuan-public")]
    closes=read_records("data/daily_prices.csv","nasdaq100","close")
    report={"instrument":"nasdaq100","reference":REFERENCE,
            "valuation_source":ndx["source"] if ndx else None,
            "valuation_asof":ndx["source_date"] if ndx else None,
            "valuation_n":len(hist),"price_n":len(closes),
            "price_first":str(closes[0][0]) if closes else None,
            "price_latest":str(closes[-1][0]) if closes else None,
            "last_close":closes[-1][1] if closes else None,
            "current_change_pct":ndx_price["change_pct"] if ndx_price else None}
    if ndx and ndx.get("stats"):
        snap=ndx["stats"]
        current={"current":ndx.get("current"),
                 "percentile":float(ndx["rating_percentile"])*100,
                 **{key:snap.get(key) for key in
                    ("opportunity","danger","median","mean","minimum","maximum","zscore")}}
        report["comparison"]={key:{"measured":actual,"screenshot":target,
                                   "delta":round(actual-target,5) if isinstance(actual,(float,int)) else None}
            for key,target in REFERENCE.items() for actual in [current.get(key)]}
    if closes:
        by_day=[(d,v) for d,v,_ in closes]
        lastday=by_day[-1][0]
        end=by_day[-1][1]
        for label,days in (("1m",31),("3m",93),("1y",366),("10y",3653)):
            period=[(d,v) for d,v in by_day if (lastday-d).days<=days]
            if period:
                max_close=max(v for d,v in period)
                min_close=min(v for d,v in period)
                max_dd=0.
                running_peak=period[0][1]
                for d,v in period:
                    running_peak=max(running_peak,v)
                    max_dd=max(max_dd,(running_peak-v)/running_peak*100)
                report[label]={"start":str(period[0][0]),"end":str(lastday),
                               "first_close":period[0][1],"last_close":end,
                               "change_pct":(end/period[0][1]-1)*100,
                               "period_high":max_close,"period_low":min_close,
                               "highest_to_current_pct":(max_close-end)/max_close*100,
                               "max_drawdown_pct":max_dd,
                               "sessions":len(period)}
    output=Path("out/nasdaq100_analysis.json")
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("NAS100_ANALYSIS="+json.dumps(report,ensure_ascii=False),flush=True)
    if not ndx or not ndx.get("current") or len(hist)<450:
        raise SystemExit("Nasdaq-100 10-year PE history is insufficient")
    if not closes or abs(closes[-1][1]-28957.53)/28957.53>0.02:
        raise SystemExit("Nasdaq-100 daily-price identity/sanity check failed")


if __name__=="__main__":
    main()
