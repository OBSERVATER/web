from __future__ import annotations
import json, re, requests

URLS=[
 ("hstech","https://baifenwei.com/index/hstech/"),
 ("hscgsi","https://getstockcheck.com/en/index/HSCGSI.HK/"),
]
for name,url in URLS:
    r=requests.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0"})
    print("\n###",name,r.status_code,len(r.text))
    text=r.text
    for pat in ["__NEXT_DATA__","series","history","historical","percentile","chart","dataset","application/json"]:
        print(pat, text.lower().find(pat.lower()))
    scripts=re.findall(r'<script[^>]*>(.*?)</script>',text,re.S|re.I)
    for i,s in enumerate(scripts):
        low=s.lower()
        if any(k in low for k in ["series","histor","percentile","dataset","chart"]):
            print("SCRIPT",i,"LEN",len(s))
            print(s[:5000].replace("\n"," ")[:5000])
