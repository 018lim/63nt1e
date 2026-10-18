"""원본 데이터 내려받기 -> data/raw/ (받은 그대로 저장, 이후 수정하지 않는다).

실행: python -m src.fetch
"""
import io

import pandas as pd
import requests
import yfinance as yf

import config

YF_TICKERS = ["VFINX", "VUSTX", "TLT", "GLD", "VEIPX", "SCHD", "VFITX", "IEI", "FRESX", "VNQ",
              "FFFDX", "VTTVX"]
FETCH_START = "1994-11-01"   # 시드 투입(1994-12 말) 가격까지 확보


def fetch_yf(ticker: str) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(start=FETCH_START, auto_adjust=False, actions=True)
    df.index = df.index.tz_localize(None).normalize()
    df.index.name = "Date"
    return df


def fetch_fred(series: str) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


def main():
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    for t in YF_TICKERS:
        df = fetch_yf(t)
        path = config.RAW_DIR / f"yf_{t}.csv"
        df.to_csv(path)
        extra = [c for c in ("Dividends", "Capital Gains") if c in df.columns]
        print(f"{t:6s} rows={len(df):6d} {df.index.min().date()} ~ {df.index.max().date()} cols={list(df.columns)} extra={extra}")
    tb = fetch_fred("TB3MS")
    tb.to_csv(config.RAW_DIR / "fred_TB3MS.csv", index=False)
    print("TB3MS", len(tb), tb.iloc[0].tolist(), tb.iloc[-1].tolist())


if __name__ == "__main__":
    main()
