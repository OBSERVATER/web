from __future__ import annotations
import re, requests

url="https://baifenwei.com/index/hstech/"
text=requests.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0"}).text
print("LEN",len(text))
for needle in ["近 10 年百分位","3.1%","1.51","10 年百分位与指数点位走势","PS 百分位","chartData","series","datasets","labels"]:
    hits=[m.start() for m in re.finditer(re.escape(needle),text,re.I)]
    print("\nNEEDLE",needle,"COUNT",len(hits),"HITS",hits[:20])
    for pos in hits[:5]:
        print(text[max(0,pos-1200):pos+5000].replace("\n"," ")[:6200])
