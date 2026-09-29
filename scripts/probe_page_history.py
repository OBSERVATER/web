from __future__ import annotations
import requests

url="https://baifenwei.com/index/hstech/"
text=requests.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0"}).text
print("LEN",len(text))
for start in [70000,72000,73500,74500]:
    print("\n### BLOCK",start)
    print(text[start:start+6000].replace("\n"," "))
