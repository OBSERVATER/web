from __future__ import annotations
import requests

url="https://push2his.eastmoney.com/api/qt/stock/kline/get"
secids=["0.980081","2.000922","124.HSCGSI","125.HSCGSI","305.HSCGSI","124.HSTECH","125.HSTECH","305.HSTECH","2.931140","100.SPX"]
for secid in secids:
    params={
      "secid":secid,"klt":"101","fqt":"1","lmt":"20","beg":"20260901","end":"20260930","iscca":"1",
      "fields1":"f1,f2,f3,f4,f5,f6,f7,f8",
      "fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
      "ut":"f057cbcbce2a86e2866ab8877db1d059","forcect":"1",
    }
    try:
      r=requests.get(url,params=params,timeout=20,headers={"User-Agent":"Mozilla/5.0","Referer":"https://quote.eastmoney.com/"})
      j=r.json()
      d=j.get("data")
      print(secid,"HTTP",r.status_code,"DATA",bool(d),"name",(d or {}).get("name"),"code",(d or {}).get("code"),"n",len((d or {}).get("klines") or []))
      if d and d.get("klines"):
        print(" last",d["klines"][-1])
    except Exception as exc:
      print(secid,"ERR",repr(exc))

print("\nHK SPOT")
spot="https://15.push2.eastmoney.com/api/qt/clist/get"
params={"pn":"1","pz":"300","po":"1","np":"1","fltt":"2","invt":"2","fid":"f3","fs":"m:124,m:125,m:305","fields":"f12,f13,f14"}
try:
 r=requests.get(spot,params=params,timeout=30,headers={"User-Agent":"Mozilla/5.0"})
 j=r.json()
 for x in (j.get("data") or {}).get("diff") or []:
  if x.get("f12") in ("HSCGSI","HSTECH"):
   print(x)
except Exception as exc:
 print("spot err",repr(exc))
