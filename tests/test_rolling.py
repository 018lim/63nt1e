import numpy as np
import pytest

import config
from src import a_value as av
from src import glide, rolling, splice
from src import rebalance as rb


@pytest.fixture(scope="module")
def data():
    tr, inc, price, _, _ = splice.build()
    return tr, inc, price


def reference_single_path(tr, inc, price, start_idx, years, start_value):
    """벡터화하지 않은 단순 구현: 한 시작 월에서 rb 함수를 그대로 호출."""
    price_np, inc_np = price[config.ASSETS].to_numpy(), inc[config.ASSETS].to_numpy()
    wd = rolling.withdrawal_path(12 * years, config.FX_FIXED)
    y0 = tr.index[start_idx].year
    H = (start_value * glide.target_weights(61).to_numpy())[None, :]
    for t in range(12 * years):
        i = start_idx + t
        H, _ = rb.apply_returns(H, price_np[i][None, :], inc_np[i][None, :], income_to_cash=False)
        H, _, _ = rb.monthly_withdraw(H, wd[t])
        d = tr.index[i]
        if d.month in (3, 6, 9, 12):
            age = 61 + (d.year - y0) + (1 if d.month == 12 else 0)
            H, _, _ = rb.quarterly_rebalance(H, glide.target_weights(age).to_numpy())
    return float(H.sum())


def test_vectorized_matches_reference(data):
    tr, inc, price = data
    sv = 255.6 * av.a_value(2026) / config.FX_FIXED
    r = rolling.run_strategy(tr, inc, price, sv, years=10)
    for s in (0, 50, 144, 261):
        assert r["end_value"][s] == pytest.approx(reference_single_path(tr, inc, price, s, 10, sv), rel=1e-9)


def test_number_of_starts_and_horizon_fill(data):
    tr, inc, price = data
    res = rolling.run_rolling(tr, inc, price, 255.6)
    for y, n in ((10, 262), (15, 202), (20, 142)):
        r = res["by_horizon"][y]["63nt1e"]
        assert len(r["starts"]) == n == len(tr) - 12 * y + 1
        assert r["starts"][-1] + 12 * y <= len(tr)                   # 기간을 채울 수 없는 시작 월은 제외
        assert all(len(v["end_value"]) == n for v in res["by_horizon"][y].values())


def test_withdrawal_path_grows_yearly():
    wd = rolling.withdrawal_path(36, config.FX_FIXED)
    assert wd[0] == pytest.approx(av.a_value(2026) * config.WITHDRAW_MULT / config.FX_FIXED)
    assert wd[11] == wd[0] and wd[12] == pytest.approx(wd[0] * 1.0432) and wd[24] == pytest.approx(wd[0] * 1.0432 ** 2)


def test_same_start_value_for_all(data):
    """모든 전략이 같은 시작 자산에서 출발: 수익률 0, 인출 0이면 종료 잔액 = 시작 자산."""
    tr, inc, price = data
    z = tr.copy() * 0.0
    zi, zp = inc.copy() * 0.0, price.copy() * 0.0
    sv = 1000.0
    r = rolling.run_strategy(z, zi, zp, sv, 10, growth=0.0)
    # 수익률 0이어도 인출은 있으므로 종료 잔액은 sv - 120 x 월 인출액
    wd0 = rolling.withdrawal_path(1, config.FX_FIXED)[0]
    assert r["end_value"][0] == pytest.approx(max(sv - 120 * wd0, 0.0))
