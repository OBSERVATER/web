from __future__ import annotations
import re, requests, urllib.parse

base="https://baifenwei.com/index/hstech/"
r=requests.get(base,timeout=30,headers={"User-Agent":"Mozilla/5.0"})
text=r.text
print("HTML",r.status_code,len(text))
srcs=re.findall(r'<script[^>]+src=["\']([^"\']+)["\']',text,re.I)
print("SCRIPTS",srcs)
for src in srcs:
    url=urllib.parse.urljoin(base,src)
    try:
        t=requests.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0"}).text
    except Exception as exc:
        print("ERR",url,repr(exc)); continue
    hits=[]
    for needle in ["fetch(","/api/","10Y","percentile","chart","series","valuation","history","dataset"]:
        if needle.lower() in t.lower(): hits.append(needle)
    print("\nJS",url,"LEN",len(t),"HITS",hits)
    for needle in ["/api/","fetch(","valuation","history"]:
        pos=t.lower().find(needle.lower())
        if pos>=0:
            print(t[max(0,pos-500):pos+2500].replace("\n"," ")[:3000])
