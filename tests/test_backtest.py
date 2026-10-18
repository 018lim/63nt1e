import numpy as np
import pandas as pd
import pytest

import config
from src import a_value as av
from src import backtest, benchmarks, glide, metrics, splice


@pytest.fixture(scope="module")
def data():
    tr, inc, price, src, _ = splice.build()
    return tr, inc, price


@pytest.fixture(scope="module")
def res(data):
    tr, inc, price = data
    return backtest.run_backtest(tr, inc, price)


def test_a_value_series():
    s = av.load_published()
    assert s[2026] == 3193511 and s[2025] == 3089062
    assert av.cagr() == pytest.approx(0.0432, abs=5e-5)
    assert av.a_value(2027) == pytest.approx(3193511 * (1 + av.cagr()))
    assert 16 * 3193511 == pytest.approx(51.1e6, rel=0.01)       # "2026년 기준 약 5,100만원"


def test_value_identity_each_month(res):
    """total_t = total_{t-1} x (1 + 수익률) + 순흐름 (현금흐름 보존)."""
    m = res.monthly
    prev = np.concatenate([[res.seed], m["total"].to_numpy()[:-1]])
    expected = prev * (1 + m["ret_before_flow"].to_numpy()) + m["flow"].to_numpy()
    assert np.allclose(m["total"].to_numpy(), expected, rtol=1e-9)


def test_seed_invested_1994_12_and_first_return_jan_1995(res, data):
    tr, inc, price = data
    w0 = glide.target_weights_for_year(1995)
    first = res.monthly.iloc[0]
    assert res.seed == pytest.approx(16 * 859858 / config.FX_FIXED)
    expected_ret = float((w0 * tr[config.ASSETS].iloc[0]).sum())      # 시드가 목표 비중이라 가중 수익률과 같다
    assert first["ret_before_flow"] == pytest.approx(expected_ret)


def test_flows_follow_phases(res):
    m = res.monthly
    contrib = m[~m["retired"]]
    assert contrib.index.min() == pd.Timestamp("1995-01-31") and contrib.index.max() == pd.Timestamp("2025-12-31")
    assert len(contrib) == 372 and (contrib["flow"] > 0).all()
    jan = m.loc["2026-01-31"]
    assert jan["flow"] == pytest.approx(-av.a_value(2026) * config.WITHDRAW_MULT / config.FX_FIXED)
    assert m["retired"].sum() == 9                                       # 2026-01 ~ 2026-09


def test_weights_valid_and_quarter_end_equals_target(res):
    w = res.weights
    assert np.allclose(w.sum(axis=1), 1.0) and (w >= -1e-12).all().all()
    for d in w.index:
        if d.month in (3, 6, 9):
            assert np.allclose(w.loc[d], glide.target_weights_for_year(d.year), atol=1e-9)
        if d.month == 12:       # 12월 말에는 다음 해 나이 기준 목표
            assert np.allclose(w.loc[d], glide.target_weights_for_year(d.year + 1), atol=1e-9)


def test_cash_target_between_quarters_not_below_zero_and_no_negative_holdings(res):
    assert (res.weights["cash"] >= 0).all()


def test_withdrawal_comes_from_cash_first(res):
    """2026-01: 인출 직후 현금이 줄어들고, 주식·장기채·금은 현금이 모자랄 때만 줄어든다 -> 인컴 자산은 월간에 안 팔림."""
    assert res.fallback_months == [] and res.depleted_month is None


def test_fx_invariance(data):
    tr, inc, price = data
    a = backtest.run_backtest(tr, inc, price, fx=1300)
    b = backtest.run_backtest(tr, inc, price, fx=1000)
    assert np.allclose(a.monthly["ret_before_flow"], b.monthly["ret_before_flow"], atol=1e-12)
    assert np.allclose(a.monthly["total"] * 1300, b.monthly["total"] * 1000, rtol=1e-9)
    assert metrics.cagr(a.monthly["ret_before_flow"]) == pytest.approx(metrics.cagr(b.monthly["ret_before_flow"]))
    assert metrics.max_drawdown(a.monthly["ret_before_flow"]) == pytest.approx(metrics.max_drawdown(b.monthly["ret_before_flow"]))


def test_no_lookahead_truncated_run_matches(data, res):
    """데이터를 2010-12로 잘라 돌려도 그 시점까지 결과가 같다 -> 미래 정보를 쓰지 않는다."""
    tr, inc, price = data
    cut = backtest.run_backtest(tr, inc, price, end="2010-12-31")
    full = res.monthly.loc[:"2010-12-31"]
    assert np.allclose(cut.monthly["total"], full["total"], rtol=1e-12)
    assert np.allclose(cut.weights, res.weights.loc[:"2010-12-31"], atol=1e-12)


def test_income_to_cash_modes_close(data, res):
    tr, inc, price = data
    alt = backtest.run_backtest(tr, inc, price, income_to_cash=False)
    assert alt.monthly["total"].iloc[-1] == pytest.approx(res.monthly["total"].iloc[-1], rel=0.02)


def test_benchmark_simulation_flows(data):
    tr, _, _ = data
    b = benchmarks.benchmark_returns(tr)
    assert list(b.columns) == ["60/40", "stock100", "cash100", "tdf"]
    vals, dep = benchmarks.simulate(np.zeros((3, 1)), np.array([10.0, 10.0, -50.0]), 100.0)
    assert vals[:, 0].tolist() == [110.0, 120.0, 70.0] and dep[0] == -1
    vals, dep = benchmarks.simulate(np.zeros((2, 1)), np.array([-60.0, -60.0]), 100.0)
    assert vals[:, 0].tolist() == [40.0, 0.0] and dep[0] == 1


def test_metrics_basic():
    r = pd.Series([0.1, -0.5, 0.2, 1.0, 0.0], index=pd.date_range("2000-01-31", periods=5, freq="ME"))
    assert metrics.max_drawdown(r) == pytest.approx(-0.5)
    assert metrics.recovery_months(r) == 2              # 저점 2000-02 -> 2000-04 회복 (1.1 x 0.5 x 1.2 x 2.0 > 1.1)
    assert metrics.cagr(pd.Series([0.01] * 12)) == pytest.approx(1.01 ** 12 - 1)
