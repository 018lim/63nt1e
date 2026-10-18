import numpy as np
import pandas as pd
import pytest

import config
from src import a_value as av
from src import backtest, benchmarks, montecarlo as mc, splice


@pytest.fixture(scope="module")
def setup():
    tr, inc, price, _, _ = splice.build()
    r = backtest.run_backtest(tr, inc, price)
    b = benchmarks.benchmark_returns(tr)
    start = {c: 1_000_000.0 for c in b.columns}
    return tr, inc, price, r, start


def test_bootstrap_indices_blocks():
    rng = np.random.default_rng(1)
    idx = mc.block_bootstrap_indices(381, 471, 50, 12, rng)
    assert idx.shape == (50, 471) and idx.min() >= 0 and idx.max() <= 380
    first_block = idx[:, :12]
    assert (np.diff(first_block, axis=1) == 1).all()           # 12개월 연속 블록
    assert (np.diff(idx[:, 12:24], axis=1) == 1).all()


def test_reproducible_same_seed(setup):
    tr, inc, price, r, start = setup
    a = mc.run_montecarlo(tr, inc, price, r.final_holdings, start, tr.index[-1], paths=300)
    b = mc.run_montecarlo(tr, inc, price, r.final_holdings, start, tr.index[-1], paths=300)
    assert np.array_equal(a.depletion_year["strategy"], b.depletion_year["strategy"])
    assert np.allclose(a.year_end_value["strategy"], b.year_end_value["strategy"])
    c = mc.run_montecarlo(tr, inc, price, r.final_holdings, start, tr.index[-1], paths=300, seed=7)
    assert not np.allclose(a.year_end_value["strategy"], c.year_end_value["strategy"])


def test_shapes_and_period(setup):
    tr, inc, price, r, start = setup
    res = mc.run_montecarlo(tr, inc, price, r.final_holdings, start, tr.index[-1], paths=200)
    assert res.years[0] == 2026 and res.years[-1] == 1965 + config.MC_MAX_AGE
    assert res.year_end_value["strategy"].shape == (200, 40)
    # 2026년 첫 해는 10~12월 3개월만 인출
    assert res.withdrawal[0] == pytest.approx(3 * av.a_value(2026) * config.WITHDRAW_MULT / config.FX_FIXED)
    assert res.withdrawal[1] == pytest.approx(12 * av.a_value(2027) * config.WITHDRAW_MULT / config.FX_FIXED)


def test_depletion_logic_consistent(setup):
    tr, inc, price, r, start = setup
    res = mc.run_montecarlo(tr, inc, price, r.final_holdings, start, tr.index[-1], paths=500)
    for n in res.depletion_year:
        dy, v = res.depletion_year[n], res.year_end_value[n]
        for p in np.where(dy > 0)[0][:50]:
            assert (v[p, res.years >= dy[p]] == 0).all()              # 고갈 후에는 0
        assert (v[dy == 0] > 0).all()                                  # 미고갈 경로는 매년 잔고 > 0
        probs = [mc.depletion_prob(res, n, a) for a in range(80, 101)]
        assert probs == sorted(probs)                                  # 고갈 확률은 나이에 따라 늘기만 한다


def test_cash_only_benchmark_depletes_and_wealth_nonneg(setup):
    tr, inc, price, r, start = setup
    res = mc.run_montecarlo(tr, inc, price, r.final_holdings, start, tr.index[-1], paths=200)
    assert mc.depletion_prob(res, "cash100", 100) > 0.9      # 고금리 구간만 뽑힌 일부 경로는 버틸 수 있다
    assert all((v >= 0).all() for v in res.year_end_value.values())


def test_block_length_changes_result_but_runs(setup):
    tr, inc, price, r, start = setup
    a = mc.run_montecarlo(tr, inc, price, r.final_holdings, start, tr.index[-1], paths=300, block=6)
    assert a.block == 6 and 0 <= mc.depletion_prob(a, "strategy", 100) <= 1
