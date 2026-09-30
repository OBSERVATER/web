"""Non-mutating GitHub-runner survey of public historical valuation candidates.

No registration, private endpoint, browser bypass, credentials, or writes to
data/history.csv. Print whether a source provides *dated raw valuations*.
"""
from __future__ import annotations

import io
import json

import pandas as pd
import requests
from bs4 import BeautifulSoup

TIMEOUT = 20
S = requests.Session()
S.headers.update({"User-Agent": "ValuationMonitor/1.0 (+public data audit)", "Accept": "*/*"})

CANDIDATES = [
    ("funddb public landing", "https://funddb.cn/site/index", "html"),
    ("guzhibiao documented public coverage", "https://guzhibiao.com/api/sync/coverage", "json"),
    ("Siblis no-key index catalog", "https://siblisresearch.supabase.co/functions/v1/free-data-api/v1/indices", "json"),
    ("honglicha CSI spot verification", "https://www.honglicha.com/", "html"),
    ("CSI official recent DY1/DY2 XLS", "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000922indicator.xls", "xls"),
    ("CSI alternate historical OSS host", "https://csi-web-dev.oss-cn-shanghai-finance-1-pub.aliyuncs.com/static/html/csindex/public/uploads/file/autofile/indicator/000922indicator.xls", "xls"),
]

def audit(name: str, url: str, kind: str) -> None:
    print(f"\\nSOURCE {name}: {url}", flush=True)
    try:
        r = S.get(url, timeout=TIMEOUT)
        print("HTTP", r.status_code, "bytes", len(r.content), "type", r.headers.get("Content-Type", ""), flush=True)
        r.raise_for_status()
        if kind == "json":
            data = r.json()
            print("root keys", sorted(data) if isinstance(data, dict) else type(data).__name__)
            if "Siblis" in name:
                items = data.get("indices", [])
                print("index coverage:", len(items), "samples:", [x.get("ticker") for x in items[:30]])
                for keyword in ("HSTECH", "931140", "000922", "980081", "CSI", "HANG"):
                    matching = [x for x in items if keyword.lower() in json.dumps(x).lower()]
                    print("match", keyword, matching[:3])
            else:
                print("response excerpt:", json.dumps(data, ensure_ascii=False)[:450])
        elif kind == "xls":
            frame = pd.read_excel(io.BytesIO(r.content))
            d = pd.to_datetime(frame.iloc[:, 0].astype(str).str.replace(r"\\.0$", "", regex=True),
                               format="%Y%m%d", errors="coerce").dropna()
            print("dated indicator rows", len(d), "min", str(d.min()), "max", str(d.max()), flush=True)
            if len(frame.columns) >= 10:
                print("last D/P2 values", frame.iloc[-3:, [0, 9]].to_dict("records"))
        else:
            soup = BeautifulSoup(r.text, "html.parser")
            plain = soup.get_text(" ", strip=True)
            print("title:", soup.title.get_text(" ", strip=True) if soup.title else "—")
            print("explicitly dated rows", len(soup.select("table tr")), "candidate index mentions",
                  {s: plain.count(s) for s in ("中证红利", "价值100", "医药50", "恒生科技")})
    except Exception as e:
        print("UNAVAILABLE", type(e).__name__, str(e)[:220], flush=True)

if __name__ == "__main__":
    for args in CANDIDATES:
        audit(*args)
