from __future__ import annotations
import re, requests

urls=[
("lixinger_dyr","https://www.lixinger.com/equity/index/detail/sh/000922/922/fundamental/valuation/dyr?metrics-type=mcw"),
("baifenwei_hstech","https://baifenwei.com/index/hstech/"),
]
for name,url in urls:
    r=requests.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0"})
    text=r.text
    print("\n###",name,"HTTP",r.status_code,"LEN",len(text))
    for needle in ["__NEXT_DATA__","2016-","2026-09-28","4.27","4.26","series","datasets","股息率","ps_pct"]:
        hits=[m.start() for m in re.finditer(re.escape(needle),text,re.I)]
        print("NEEDLE",needle,"COUNT",len(hits),"HITS",hits[:10])
        for pos in hits[:2]:
            print(text[max(0,pos-800):pos+3500].replace("\n"," ")[:4300])
