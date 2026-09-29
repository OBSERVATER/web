from __future__ import annotations

import io
import math
from datetime import date

import pandas as pd
import requests

AS_OF="2026-09-28"
DC="https://datacenter-web.eastmoney.com/api/data/v1/get"

def get_market_valuations(day: str) -> pd.DataFrame:
    params={
        "sortColumns":"SECURITY_CODE",
        "sortTypes":"1",
        "pageSize":"6000",
        "pageNumber":"1",
        "reportName":"RPT_VALUEANALYSIS_DET",
        "columns":"ALL",
        "quoteColumns":"",
        "source":"WEB",
        "client":"WEB",
        "filter":f"(TRADE_DATE='{day}')",
    }
    r=requests.get(DC,params=params,timeout=60,headers={"User-Agent":"Mozilla/5.0","Referer":"https://data.eastmoney.com/"})
    r.raise_for_status()
    j=r.json()
    rows=((j.get("result") or {}).get("data") or [])
    df=pd.DataFrame(rows)
    print("market rows",len(df),"fields",list(df.columns)[:20])
    if df.empty:
        return df
    df["SECURITY_CODE"]=df["SECURITY_CODE"].astype(str).str.zfill(6)
    for col in ["PE_TTM","PB_MRQ","PS_TTM","TOTAL_MARKET_CAP"]:
        if col in df:
            df[col]=pd.to_numeric(df[col],errors="coerce")
    return df

def get_cni_weights(code: str) -> pd.DataFrame:
    url="https://www.cnindex.com.cn/sample-detail/download-history"
    r=requests.get(url,params={"indexcode":code},timeout=60,headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    df=pd.read_excel(io.BytesIO(r.content))
    df.columns=["日期","代码","简称","行业","总市值","权重"]
    df["代码"]=df["代码"].astype(str).str.replace(".0","",regex=False).str.zfill(6)
    df["权重"]=pd.to_numeric(df["权重"],errors="coerce")
    df["日期"]=pd.to_datetime(df["日期"],errors="coerce")
    target=pd.Timestamp(AS_OF)
    available=df[df["日期"]<=target]
    if available.empty:
        available=df
    d=available["日期"].max()
    out=available[available["日期"]==d].copy()
    print("CNI weight date",d,"n",len(out),"sum",out["权重"].sum())
    return out

def get_csi_weights(code: str) -> pd.DataFrame:
    url=f"https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/closeweight/{code}closeweight.xls"
    r=requests.get(url,timeout=60,headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    df=pd.read_excel(io.BytesIO(r.content))
    df.columns=["日期","指数代码","指数名称","指数英文名称","代码","简称","英文简称","交易所","交易所英文","权重"]
    df["代码"]=df["代码"].astype(str).str.replace(".0","",regex=False).str.zfill(6)
    df["权重"]=pd.to_numeric(df["权重"],errors="coerce")
    df["日期"]=pd.to_datetime(df["日期"].astype(str).str.replace(r"\.0$","",regex=True),format="%Y%m%d",errors="coerce")
    d=df["日期"].max()
    out=df[df["日期"]==d].copy()
    print("CSI weight date",d,"n",len(out),"sum",out["权重"].sum())
    return out

def weighted_harmonic(weights: pd.DataFrame, market: pd.DataFrame, field: str):
    cols=["SECURITY_CODE",field,"TOTAL_MARKET_CAP"]
    m=weights[["代码","权重"]].merge(market[cols],left_on="代码",right_on="SECURITY_CODE",how="left")
    m=m.rename(columns={field:"x"})
    m["w"]=m["权重"]/100.0
    valid=m["x"].notna() & (m["x"]!=0) & m["w"].notna()
    mv=m[valid].copy()
    denominator=(mv["w"]/mv["x"]).sum()
    result=1.0/denominator if denominator!=0 else float("nan")
    renorm=mv["w"].sum()
    renorm_result=renorm/denominator if denominator!=0 else float("nan")
    arithmetic=(mv["w"]*mv["x"]).sum()/renorm
    pos=mv[mv["x"]>0].copy()
    pos_w=pos["w"].sum()
    pos_h=pos_w/(pos["w"]/pos["x"]).sum() if len(pos) else float("nan")
    pos_a=(pos["w"]*pos["x"]).sum()/pos_w if len(pos) else float("nan")
    eq_h=len(pos)/(1.0/pos["x"]).sum() if len(pos) else float("nan")
    eq_a=pos["x"].mean() if len(pos) else float("nan")
    cap=mv["TOTAL_MARKET_CAP"].where(mv["TOTAL_MARKET_CAP"]>0)
    cap_valid=mv[cap.notna()].copy()
    cap_w=cap_valid["TOTAL_MARKET_CAP"]/cap_valid["TOTAL_MARKET_CAP"].sum()
    cap_h=1.0/(cap_w/cap_valid["x"]).sum()
    cap_a=(cap_w*cap_valid["x"]).sum()
    print(field,"matched",len(mv),"/",len(m),"weight matched",renorm,"positive",len(pos))
    print("index-weight harmonic",result,"renormalized",renorm_result)
    print("index-weight positive harmonic",pos_h,"arithmetic",pos_a)
    print("equal positive harmonic",eq_h,"arithmetic",eq_a)
    print("total-mcap harmonic",cap_h,"arithmetic",cap_a)
    missing=m[~valid][["代码","权重","x"]]
    if not missing.empty:
        print("missing/nonzero sample",missing.head(20).to_dict("records"))
    return result,renorm_result

def main():
    market=get_market_valuations(AS_OF)
    if market.empty:
        raise SystemExit("no market valuation rows")

    print("\n=== VALUE100 980081 ===")
    try:
        value_w=get_cni_weights("980081")
        weighted_harmonic(value_w,market,"PE_TTM")
    except Exception as exc:
        print("VALUE100 ERROR",repr(exc))

    print("\n=== PHARMA50 931140 ===")
    try:
        pharma_w=get_csi_weights("931140")
        weighted_harmonic(pharma_w,market,"PB_MRQ")
    except Exception as exc:
        print("PHARMA50 ERROR",repr(exc))

if __name__=="__main__":
    main()
