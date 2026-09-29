from __future__ import annotations
import re, requests

url="https://www.lixinger.com/equity/index/detail/sh/000922/922/fundamental/valuation/dyr?metrics-type=mcw"
r=requests.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0"})
print("HTTP",r.status_code,"LEN",len(r.text))
text=r.text
for needle in ["当前值","80%分位点","2016-","2026-09-18","__NEXT_DATA__","application/json","股息率"]:
    hits=[m.start() for m in re.finditer(re.escape(needle),text,re.I)]
    print("\n",needle,hits[:10])
    for pos in hits[:2]:
        print(text[max(0,pos-500):pos+2500].replace("\n"," ")[:3000])
