"""Probe only the first-party public historical chart route used by guzhibiao.com.

No login, token, private API, write, or synthetic data. Do not use its results
in production until method/date/series checks and independent spot checks pass.
"""
from __future__ import annotations
from urllib.parse import quote
import json
import requests

BASE = "https://guzhibiao.com/api/index"
TARGETS = [
    ("中证红利", "dividend"),
    ("中证红利", "dyr"),
    ("价值100", "pe"),
    ("医药50", "pb"),
    ("恒生科技", "ps"),
]
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ValuationMonitor-source-audit)", "Accept": "application/json"})
for name, key in TARGETS:
    url = f"{BASE}/{quote(name, safe='')}/history"
    print("\\nCANDIDATE", name, key, flush=True)
    try:
        r = s.get(url, params={"indicator": key}, timeout=25)
        print("HTTP", r.status_code, "bytes", len(r.content), "url", r.url, flush=True)
        r.raise_for_status()
        data = r.json()
        print("root keys", list(data) if isinstance(data, dict) else type(data).__name__, flush=True)
        print("JSON head", json.dumps(data, ensure_ascii=False)[:1100], flush=True)
        for candidate in ("history", "series", "data", "rows", "values"):
            rows = data.get(candidate) if isinstance(data, dict) else None
            if isinstance(rows, list):
                print("list", candidate, "count", len(rows), "first", rows[:1], "last", rows[-1:], flush=True)
            elif isinstance(rows, dict):
                print("object", candidate, "keys", list(rows)[:20], flush=True)
    except Exception as exc:
        print("UNAVAILABLE", type(exc).__name__, str(exc)[:180], flush=True)
