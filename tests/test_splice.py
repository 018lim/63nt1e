"""이어붙이기·TR/인컴 분해 검증 (CLAUDE.md 5절)."""
import numpy as np
import pandas as pd
import pytest

import config
from src import splice


@pytest.fixture(scope="module")
def built():
    return splice.build()   # tr(+벤치마크), income, price, source_map, veipx_log


def test_index_and_no_nan(built):
    tr, inc, price, src, _ = built
    idx = pd.date_range("1995-01-31", "2026-09-30", freq="ME")
    assert tr.index.equals(idx) and inc.index.equals(idx) and price.index.equals(idx)
    assert not tr.isna().any().any() and not inc.isna().any().any()
    assert list(tr.columns[:7]) == config.ASSETS


def test_source_switch_months(built):
    src = built[3]
    for asset, (etf, start) in config.ETF.items():
        s = src[asset]
        first_etf = s[s == etf].index.min()
        assert first_etf.strftime("%Y-%m") == start, asset
        assert (s[s.index < first_etf] == config.PROXY[asset]).all()
        assert (s[s.index >= first_etf] == etf).all()


def test_price_plus_income_equals_tr(built):
    tr, inc, price, _, _ = built
    assert (price + inc - tr[config.ASSETS]).abs().max().max() < 1e-12


def test_cash_is_tb3ms_over_1200(built):
    tr, inc, price, _, _ = built
    t = pd.read_csv(config.RAW_DIR / "fred_TB3MS.csv")
    s = t.set_index(pd.to_datetime(t["observation_date"]).dt.to_period("M"))["TB3MS"] / 1200
    got = tr["cash"].copy(); got.index = got.index.to_period("M")
    assert np.allclose(got.values, s.reindex(got.index).values)
    assert (price["cash"] == 0).all()


def test_gold_has_no_income(built):
    assert (built[1]["gold"] == 0).all()


def test_first_return_uses_1994_12_seed_price(built):
    tr = built[0]
    adj = splice.read_yf("VFINX")["Adj Close"]
    expected = adj[:"1995-01-31"].iloc[-1] / adj[:"1994-12-31"].iloc[-1] - 1
    assert tr["equity"].iloc[0] == pytest.approx(expected)


def test_price_component_matches_unadjusted_close_return(built):
    """독립 점검: (Close_t + D_t)/Close_{t-1} - 1 와 수정주가 TR이 월 단위로 거의 같다.
    (분배금 재투자 시점이 월중이냐 월말이냐 차이만 남는다.)"""
    src = built[3]
    for asset in config.ASSETS:
        if asset in ("cash", "gold"):
            continue
        for ticker in src[asset].unique():
            if ticker == "GOLD_SPOT":
                continue
            months = src[asset][src[asset] == ticker].index.to_period("M")
            if ticker == "VEIPX":
                div, _ = splice.veipx_dividends_ex_capital_gains(splice.read_yf("VEIPX")["Dividends"])
                f = splice.monthly_from_yf("VEIPX", div)
                f["div"] = splice.monthly_from_yf("VEIPX")["div"]      # 자본이득 포함 전체 분배로 비교
            else:
                f = splice.monthly_from_yf(ticker)
            close_tr = f["close"].pct_change() + f["div"] / f["close"].shift(1)
            diff = (f["tr"] - close_tr).reindex(months).abs()
            assert diff.max() < 0.0025, (asset, ticker, diff.idxmax(), diff.max())


def test_veipx_capital_gain_separation_matches_report(built):
    log = built[4]
    assert len(log) == 17                          # FY1995 ~ FY2011
    assert (log["cg_implied"] - log["cg_report"]).abs().max() < 0.005
    assert (log["dec_income"] > 0).all()


def test_tdf_stitching(built):
    tr = built[0]
    m = pd.Timestamp("1996-10-31")
    assert tr.at[m, "tdf"] == pytest.approx(0.6 * tr.at[m, "equity"] + 0.4 * tr.at[m, "mid_bond"])
    ff = splice.monthly_from_yf("FFFDX")["tr"]; vt = splice.monthly_from_yf("VTTVX")["tr"]
    assert tr.at[pd.Timestamp("1996-11-30"), "tdf"] == pytest.approx(ff[pd.Period("1996-11")])
    assert tr.at[pd.Timestamp("2003-10-31"), "tdf"] == pytest.approx(ff[pd.Period("2003-10")])
    assert tr.at[pd.Timestamp("2003-11-30"), "tdf"] == pytest.approx(vt[pd.Period("2003-11")])


def test_monthly_returns_sane(built):
    tr = built[0]
    assert tr.max().max() < 0.5 and tr.min().min() > -0.5
