"""Research-only, source-labelled comparison against user-supplied Wind-like screenshots.

This code never overwrites live valuation values or makes a production source
selection based on the desired screenshot outputs.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from valuation_monitor.stats import calculate_snapshot

REFERENCE = {
  "csi300": {"metric":"pe_ttm","current":12.82,"percentile":52.05,"opportunity":11.72,
             "danger":14.14,"median":12.72,"mean":12.89,"minimum":10.23,"maximum":17.45,"zscore":-0.05},
  "csi_dividend": {"metric":"dyr","current":4.69,"percentile":52.25,"opportunity":5.69,
             "danger":4.06,"median":4.66,"mean":4.78,"minimum":2.99,"maximum":6.99,"zscore":-0.09},
  "sp500": {"metric":"pe_ttm","current":24.44,"percentile":49.71,"opportunity":21.95,
             "danger":28.51,"median":24.55,"mean":25.42,"minimum":16.15,"maximum":41.99,"zscore":-0.22}
}
HISTORY_SOURCES={"csi300":"guzhibiao-public-funddb-history",
                 "csi_dividend":"guzhibiao-public-funddb-history",
                 "sp500":"danjuan-public-history"}
OUTPUT=Path("out/valuation-source-audit")


def guzhibiao_probe():
    """Check the currently used public provider; do not mix its values with other families."""
    from urllib.parse import quote
    import requests
    url=f"https://guzhibiao.com/api/index/{quote('中证红利',safe='')}/history"
    response=requests.get(url,params={"indicator":"dividend"},timeout=25)
    response.raise_for_status()
    data=response.json()
    if not isinstance(data,dict) or str(data.get("code"))!="000922" or data.get("indicator")!="dividend":
        raise ValueError("Source identity / indicator mismatch")
    raw=list(zip(data.get("dates") or [],data.get("values") or []))
    values=[]
    for d,v in raw:
        try:
            day=date.fromisoformat(str(d))
            value=float(v)
            if date(2000,1,1)<=day<=date(2026,10,26) and 0<value<100:
                values.append((day,value))
        except (ValueError,TypeError):
            continue
    values.sort()
    with (OUTPUT/"guzhibiao_dividend.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f)
        writer.writerow(["day","value"])
        writer.writerows((d.isoformat(),v) for d,v in values)
    print("SOURCE_RESULT="+json.dumps({"rows":len(values),
          "first":values[0][0].isoformat() if values else None,
          "last":values[-1][0].isoformat() if values else None,
          "current":values[-1][1] if values else None,
          "provider":"guzhibiao-public-funddb-history"},
          ensure_ascii=False),flush=True)


def values_for_source(path,id,source):
    values=[]
    with path.open(encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            if row["instrument_id"]!=id:continue
            if row["source"]!=source and not (source=="danjuan-public-history" and row["source"]=="danjuan-public"):
                continue
            try:
                if date.fromisoformat(row["day"])<date(2016,10,26):continue
                x=float(row["value"])
                if x>0: values.append(x)
            except (ValueError,KeyError):
                continue
    return values


def compare_stats(reference,stats):
    return {key:{"actual":round(float(stats[key]),5),"benchmark":target,"difference":round(float(stats[key])-target,5)}
            for key,target in reference.items() if key in stats and isinstance(target,(float,int))}


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if len(sys.argv)>1 and sys.argv[1]=="--guzhibiao":
        guzhibiao_probe()
        return
    snapshot=json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    items={x["instrument_id"]:x for x in snapshot["items"]}
    rows=[]
    for id,ref in REFERENCE.items():
        item=items[id]
        values=values_for_source(Path("data/history.csv"),id,HISTORY_SOURCES[id])
        snap=calculate_snapshot(values,ref["current"],id=="csi_dividend")
        baseline={"current":item["current"],"percentile":item["rating_percentile"]*100,
                  **(item.get("stats") or {})}
        baseline["percentile"]=item["rating_percentile"]*100
        alt={"current":ref["current"],"percentile":snap.percentile*100,
             "opportunity":snap.opportunity,"danger":snap.danger,
             "median":snap.median,"mean":snap.mean,"minimum":snap.minimum,
             "maximum":snap.maximum,"zscore":snap.zscore}
        rows.append({"index":id,"sample_count":len(values),
                     "baseline":compare_stats(ref,baseline),
                     "same_history_screenshot_current_only":compare_stats(ref,alt)})
    candidate={}
    try:
        cmd=subprocess.run([sys.executable,__file__,"--guzhibiao"],
                           capture_output=True,text=True,timeout=45)
        if cmd.returncode!=0: raise RuntimeError((cmd.stderr+cmd.stdout)[-1200:])
        entry=[x[len("SOURCE_RESULT="):] for x in cmd.stdout.splitlines()
               if x.startswith("SOURCE_RESULT=")][-1]
        candidate=json.loads(entry)
    except Exception as exc:
        candidate={"status":"unavailable","error":str(exc)[:1200]}
    report={"benchmark_date":"User screenshots provided 2026-10-26, close references around 2026-10-23",
            "reference_is_observation_not_source_of_truth":True,
            "results":rows,"guzhibiao_live_candidate":candidate}
    (OUTPUT/"audit.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    for item in rows:
        key=item["index"]
        print("AUDIT",key,"samples",item["sample_count"],
              "baseline_pct_difference",item["baseline"]["percentile"]["difference"],
              "screenshot_current_pct_difference",
              item["same_history_screenshot_current_only"]["percentile"]["difference"],flush=True)
    print("GUZHIBIAO_LIVE",candidate,flush=True)


if __name__=="__main__":main()
