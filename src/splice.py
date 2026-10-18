"""대리 자산 -> ETF 이어붙이기, TR / 인컴 / 가격 성분 월별 시계열 생성 (CLAUDE.md 2.5, 2.6).

실행: python -m src.splice   ->  data/processed/ 에 저장
월 수익률 = 전월 말 -> 당월 말 (월 마지막 영업일 종가). 날짜는 월말 타임스탬프.
  TR      : 수정주가(Adj Close) 수익률
  income  : 그달 소득 분배금 합계 / 전월 말 Close  (자본이득 분배 제외)
  price   : TR - income   (자본이득 분배는 자산에 남는다 = 재투자와 동일)
"""
import numpy as np
import pandas as pd

import config

DEC = 12


# ---------- 읽기 ----------
def read_yf(ticker: str) -> pd.DataFrame:
    return pd.read_csv(config.RAW_DIR / f"yf_{ticker}.csv", index_col=0, parse_dates=True)


def last_complete_month(index: pd.DatetimeIndex) -> pd.Period:
    """데이터 마지막 날이 속한 달은 아직 진행 중이므로 제외."""
    return index.max().to_period("M") - 1


def veipx_dividends_ex_capital_gains(div: pd.Series) -> tuple[pd.Series, pd.DataFrame]:
    """VEIPX 12월 분배금에서 자본이득 분배를 뺀다 (연차보고서 기준, CLAUDE.md 7절).

    12월 소득분 = 그 회계연도(10월~9월) 소득 분배(nii) - 같은 회계연도의 3·6·9월 분배 합계.
    자본이득 = 12월 분배 - 12월 소득분. 반환: (조정된 일별 분배금, 분리 로그)
    """
    fy = pd.read_csv(config.RAW_DIR / "veipx_distributions_by_fy.csv", comment="#", parse_dates=["fy_end"])
    div = div[div > 0].copy()
    adjusted = div.copy()
    rows = []
    for _, r in fy.iterrows():
        y = r.fy_end.year
        win = div[(div.index >= f"{y - 1}-10-01") & (div.index <= f"{y}-09-30")]
        dec = win[win.index.month == DEC]
        other = win[win.index.month != DEC]
        if len(dec) != 1:
            raise ValueError(f"VEIPX FY{y}: 12월 분배가 {len(dec)}건 (1건이어야 함)")
        dec_income = r.nii_dist - other.sum()
        adjusted[dec.index[0]] = dec_income
        rows.append({"fy": y, "dec_date": dec.index[0].date(), "dec_dist": dec.iloc[0],
                     "dec_income": dec_income, "cg_implied": dec.iloc[0] - dec_income, "cg_report": r.cg_dist})
    return adjusted, pd.DataFrame(rows)


# ---------- 티커별 월별 TR / 인컴 ----------
def monthly_from_yf(ticker: str, dividends: pd.Series | None = None) -> pd.DataFrame:
    df = read_yf(ticker)
    div = df["Dividends"] if dividends is None else dividends
    last = last_complete_month(df.index)
    g = df.groupby(df.index.to_period("M"))
    out = pd.DataFrame({"close": g["Close"].last(), "adj": g["Adj Close"].last()})
    out["div"] = div.groupby(div.index.to_period("M")).sum().reindex(out.index).fillna(0.0)
    out = out[out.index <= last]
    out["tr"] = out["adj"].pct_change()
    out["income"] = out["div"] / out["close"].shift(1)
    return out


def monthly_gold_spot() -> pd.DataFrame:
    g = pd.read_csv(config.RAW_DIR / "gold_spot_month_end.csv", comment="#", parse_dates=["date"])
    s = g.set_index(g["date"].dt.to_period("M"))["pm_fix_usd"]
    out = pd.DataFrame({"close": s})
    out["tr"] = s.pct_change()
    if config.GOLD_FEE_ADJ:
        out["tr"] -= 0.0040 / 12          # GLD 보수 연 0.40% 반영 옵션
    out["income"] = 0.0
    return out


def monthly_cash() -> pd.DataFrame:
    t = pd.read_csv(config.RAW_DIR / "fred_TB3MS.csv")
    t["date"] = pd.to_datetime(t.iloc[:, 0])
    s = t.set_index(t["date"].dt.to_period("M"))["TB3MS"] / 100 / 12
    return pd.DataFrame({"tr": s, "income": s})      # 현금은 가격 변동 없이 이자만


# ---------- 이어붙이기 ----------
def splice_asset(asset: str, frames: dict[str, pd.DataFrame], months: pd.PeriodIndex):
    """반환: (tr, income, source) 시리즈. ETF 시작월부터 ETF, 그 전은 대리 자산."""
    proxy = config.PROXY[asset]
    etf = config.ETF.get(asset)
    start = pd.Period(etf[1], "M") if etf else None
    tr, inc, src = [], [], []
    for m in months:
        name = etf[0] if (etf and m >= start) else proxy
        f = frames[name]
        tr.append(f.at[m, "tr"]); inc.append(f.at[m, "income"]); src.append(name)
    return (pd.Series(tr, months), pd.Series(inc, months), pd.Series(src, months))


def build():
    div_adj, veipx_log = veipx_dividends_ex_capital_gains(read_yf("VEIPX")["Dividends"])
    frames = {t: monthly_from_yf(t) for t in
              ["VFINX", "VUSTX", "TLT", "GLD", "FRESX", "VNQ", "VFITX", "IEI", "SCHD", "VBMFX", "FFFDX", "VTTVX"]}
    frames["VEIPX"] = monthly_from_yf("VEIPX", div_adj)
    spot = monthly_gold_spot()
    frames["GOLD_SPOT"] = spot
    frames["TB3MS"] = monthly_cash()
    # GLD 분배금은 없음(0). 금 현물/GLD 모두 인컴 0.
    frames["GLD"]["income"] = 0.0

    last = min(f.index.max() for k, f in frames.items() if k not in ("GOLD_SPOT",))
    months = pd.period_range(config.START, last, freq="M")

    tr, inc, src = {}, {}, {}
    for a in config.ASSETS:
        tr[a], inc[a], src[a] = splice_asset(a, frames, months)
    tr, inc, src = pd.DataFrame(tr), pd.DataFrame(inc), pd.DataFrame(src)
    price = tr - inc

    # 벤치마크 구성요소 (TR만 필요)
    bench = pd.DataFrame(index=months)
    bench["vbmfx"] = frames["VBMFX"].loc[months, "tr"]
    tdf = pd.Series(np.nan, months)
    for m in months:
        if m >= pd.Period(config.TDF_SWITCH["VTTVX"], "M"):
            tdf[m] = frames["VTTVX"].at[m, "tr"]
        elif m >= pd.Period(config.TDF_SWITCH["FFFDX"], "M"):
            tdf[m] = frames["FFFDX"].at[m, "tr"]
        else:   # 1995-01 ~ 1996-10: 60/40으로 채움
            tdf[m] = 0.6 * tr.at[m, "equity"] + 0.4 * bench.at[m, "vbmfx"]
    bench["tdf"] = tdf
    tr_all = pd.concat([tr, bench], axis=1)

    for df in (tr_all, inc, price, src):
        df.index = months.to_timestamp(how="end").normalize()
        df.index.name = "date"
    return tr_all, inc, price, src, veipx_log


def main():
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    tr, inc, price, src, veipx_log = build()
    tr.to_csv(config.PROCESSED_DIR / "returns_tr.csv")
    inc.to_csv(config.PROCESSED_DIR / "returns_income.csv")
    price.to_csv(config.PROCESSED_DIR / "returns_price.csv")
    src.to_csv(config.PROCESSED_DIR / "source_map.csv")
    veipx_log.to_csv(config.PROCESSED_DIR / "veipx_cg_separation.csv", index=False)
    print(f"{tr.index.min().date()} ~ {tr.index.max().date()}  {len(tr)}개월  NaN={int(tr.isna().sum().sum())}")
    print(src.apply(lambda s: s.iloc[0] + " -> " + s.iloc[-1]).to_string())


if __name__ == "__main__":
    main()
