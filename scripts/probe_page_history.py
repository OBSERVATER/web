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
    assigns=re.findall(r'window\.([A-Z0-9_]+)\s*=\s*(\{.*?\});',text,re.S)
    print("WINDOW ASSIGNS",[(k,len(v)) for k,v in assigns])
    for key,raw in assigns:
        try:
            obj=json.loads(raw)
        except Exception as exc:
            print(key,"json error",repr(exc))
            continue
        print("VAR",key,"topkeys",list(obj)[:20])
        if "10Y" in obj:
            ten=obj["10Y"]
            print("10Y keys",list(ten)[:20])
            for k,v in ten.items():
                if isinstance(v,list):
                    print(" ",k,"len",len(v),"first",v[:2],"last",v[-2:])
                elif isinstance(v,dict):
                    print(" ",k,v)
