from __future__ import annotations
import requests
url="https://push2his.eastmoney.com/api/qt/stock/kline/get"
secids=["1.000922","0.399922","2.399922","2.000922"]
for secid in secids:
 params={"secid":secid,"klt":"101","fqt":"1","lmt":"10000","beg":"20260901","end":"20260930","iscca":"1","fields1":"f1,f2,f3,f4,f5,f6,f7,f8","fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64","ut":"f057cbcbce2a86e2866ab8877db1d059","forcect":"1"}
 try:
  j=requests.get(url,params=params,timeout=20,headers={"User-Agent":"Mozilla/5.0","Referer":"https://quote.eastmoney.com/"}).json()
  d=j.get("data")
  print(secid,bool(d),(d or {}).get("name"),(d or {}).get("code"),len((d or {}).get("klines") or []), ((d or {}).get("klines") or [None])[-1])
 except Exception as e: print(secid,repr(e))
