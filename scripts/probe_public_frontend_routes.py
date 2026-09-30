"""Inspect publicly served frontend JS for documented/public route names only.

No crawling behind login, no query guessing, no mutating requests. This script
prints candidate route strings for human verification before any integration.
"""
from __future__ import annotations
from urllib.parse import urljoin, urlparse
import re
import requests
from bs4 import BeautifulSoup

BASE = "https://guzhibiao.com/"
session = requests.Session()
session.headers.update({"User-Agent": "ValuationMonitor/1.0 (+source audit)"})
page = session.get(BASE, timeout=20)
print("landing HTTP", page.status_code, "bytes", len(page.content), flush=True)
page.raise_for_status()
soup = BeautifulSoup(page.text, "html.parser")
scripts = []
for tag in soup.find_all("script", src=True):
    url = urljoin(BASE, tag["src"])
    if urlparse(url).netloc in {"guzhibiao.com", "www.guzhibiao.com"}:
        scripts.append(url)
print("first-party script URLs", scripts[:24], flush=True)
patterns = (r"/api/[A-Za-z0-9_/$\\{\\}?.=&-]+", r"/v1/[A-Za-z0-9_/$\\{\\}?.=&-]+")
for url in scripts[:16]:
    try:
        r = session.get(url, timeout=20)
        print("bundle", url.rsplit("/",1)[-1][:75], "HTTP", r.status_code, "bytes", len(r.content), flush=True)
        if not r.ok or len(r.content) > 5_000_000:
            continue
        routes = set()
        for pattern in patterns:
            routes.update(re.findall(pattern, r.text))
        routes = sorted(s for s in routes if any(k in s.lower() for k in
                        ("index", "histor", "valuation", "ratio", "fund", "sync")))
        print("relevant route strings:", routes[:70], flush=True)
        for key in ("/api/index/", "/api/sync/health"):
            for m in list(re.finditer(re.escape(key), r.text))[:3]:
                print("route context:", r.text[max(0, m.start()-210):m.start()+310], flush=True)
    except requests.RequestException as exc:
        print("bundle unavailable:", str(exc)[:130], flush=True)
