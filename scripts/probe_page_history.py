from __future__ import annotations
import re, requests

url="https://baifenwei.com/index/hstech/"
text=requests.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0"}).text
print("LEN",len(text))
for needle in ['"10Y"', "'10Y'", "10Y:", "chartData", "series:", "dates:", "ps:", "percentile"]:
    hits=[m.start() for m in re.finditer(re.escape(needle),text,re.I)]
    print("\nNEEDLE",needle,"HITS",hits[:20])
    for pos in hits[:3]:
        print(text[max(0,pos-500):pos+1800].replace("\n"," ")[:2300])
