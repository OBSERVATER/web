"""Focused Nasdaq-100 live source verification; no repository state mutation."""
import json
import math
import traceback
from datetime import date
from pathlib import Path

from valuation_monitor.models import Instrument, MetricSpec
from valuation_monitor.public_sources import PublicDataClient
from valuation_monitor.price_sources import fetch_daily
from valuation_monitor.stats import calculate_snapshot, weekly_last

target = date(2026,10,26)
cutoff = date(2016,10,26)
Path("out").mkdir(exist_ok=True)
result={"index":"nasdaq100","code":"NDX","screenshot":{
    "point":28957.53,"pe":28.68,"percentile":36.47,
    "median":31.02,"opportunity":26.57,"danger":35.86,
    "mean":31.12,"minimum":20.10,"maximum":42.94,"zscore":-0.51
}}
inst=Instrument(id="nasdaq100",name="纳斯达克100",market="us",code="NDX",
    metrics=(MetricSpec("pe_ttm"),),source={"type":"danjuan",
        "name":"纳斯达克100","index_code":"NDX"})
try:
    rows=fetch_daily("nasdaq100",date(2016,10,26),target)
    result["price"]={"count":len(rows),"first":rows[0],
      "latest":rows[-1],"previous":rows[-2],"close_diff":rows[-1]["close"]-28957.53,
      "recent_change_pct":(rows[-1]["close"]/rows[-2]["close"]-1)*100}
    by_days=[r for r in rows if r["day"]>="2025-10-23"]
    if len(by_days)>5:
        high=max(r["close"] for r in by_days)
        result["price"]["year_high_close"]=high
        result["price"]["year_peak_to_current_pct"]=(high-rows[-1]["close"])/high*100
except Exception as e:
    result["price_error"]=f"{type(e).__name__}: {e}"
try:
    client=PublicDataClient(timeout=25)
    latest=client.fetch_latest(inst,end=target)
    hist=client.fetch_range(inst,cutoff,target)
    hist=weekly_last(hist)
    result["valuation"]={"latest_count":len(latest),"history_count":len(hist),
       "first_date":str(hist[0].day) if hist else None,
       "last_date":str(hist[-1].day) if hist else None}
    if latest:
        current=latest[-1]
        values=[v.value for v in hist if v.day<=current.day and v.day>=cutoff]
        result["valuation"].update({"current":current.value,"asof":str(current.day),
             "source":current.source,"history_asof":str(hist[-1].day) if hist else None})
        if values:
            snap=calculate_snapshot(values,current.value,False)
            vals={"current":snap.current,"percentile":snap.percentile*100,
                  "median":snap.median,"opportunity":snap.opportunity,
                  "danger":snap.danger,"mean":snap.mean,"minimum":snap.minimum,
                  "maximum":snap.maximum,"zscore":snap.zscore}
            result["valuation"]["stats"]=vals
            result["valuation"]["comparison"]={k:{"actual":v,
                "screenshot":result["screenshot"]["pe" if k=="current" else k],
                "delta":v-result["screenshot"]["pe" if k=="current" else k]}
                for k,v in vals.items()}
except Exception as e:
    result["valuation_error"]=f"{type(e).__name__}: {e}"
Path("out/nasdaq100_fast_probe.json").write_text(json.dumps(result,
    indent=2,ensure_ascii=False),encoding="utf-8")
print("NDX_FAST_PROBE="+json.dumps(result,ensure_ascii=False),flush=True)
