from __future__ import annotations

import requests

CASES = [
    ("value100-pe-sz", "https://danjuanapp.com/djapi/index_eva/pe_history/SZ980081?day=all", "index_eva_pe_growths", "pe"),
    ("value100-pe-cni", "https://danjuanapp.com/djapi/index_eva/pe_history/CNI980081?day=all", "index_eva_pe_growths", "pe"),
    ("pharma50-pb-csi", "https://danjuanapp.com/djapi/index_eva/pb_history/CSI931140?day=all", "index_eva_pb_growths", "pb"),
    ("pharma50-pb-sh", "https://danjuanapp.com/djapi/index_eva/pb_history/SH931140?day=all", "index_eva_pb_growths", "pb"),
    ("hscgsi-pb", "https://danjuanapp.com/djapi/index_eva/pb_history/HSCGSI?day=all", "index_eva_pb_growths", "pb"),
    ("hstech-pb", "https://danjuanapp.com/djapi/index_eva/pb_history/HSTECH?day=all", "index_eva_pb_growths", "pb"),
    ("sp500-pe-sp500", "https://danjuanapp.com/djapi/index_eva/pe_history/SP500?day=all", "index_eva_pe_growths", "pe"),
    ("sp500-pe-spx", "https://danjuanapp.com/djapi/index_eva/pe_history/SPX?day=all", "index_eva_pe_growths", "pe"),
]

headers={
    "User-Agent":"Mozilla/5.0 (compatible; ValuationMonitor/1.0)",
    "Referer":"https://danjuanfunds.com/djmodule/value-center",
}

for name,url,key,field in CASES:
    try:
        r=requests.get(url,headers=headers,timeout=20)
        print("\nCASE",name,"HTTP",r.status_code,"LEN",len(r.content))
        j=r.json()
        data=(j.get("data") or {}).get(key) or []
        print("COUNT",len(data))
        if data:
            print("FIRST",data[0])
            print("LAST",data[-1])
    except Exception as exc:
        print("ERROR",name,repr(exc))
