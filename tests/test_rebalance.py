import numpy as np
import pytest

import config
from src import glide, rebalance as rb

T = glide.target_weights(30).to_numpy()


def H(*v):
    return np.array([v], dtype=float)


def test_returns_income_to_cash():
    h = H(100, 100, 0, 0, 0, 0, 100)
    price = np.array([[0.1, -0.1, 0, 0, 0, 0, 0]])
    inc = np.array([[0.01, 0.02, 0, 0, 0, 0, 0.005]])
    new, income = rb.apply_returns(h, price, inc, income_to_cash=True)
    assert new[0, 0] == pytest.approx(110) and new[0, 1] == pytest.approx(90)
    assert income.sum() == pytest.approx(1 + 2 + 0.5)
    assert new[0, 6] == pytest.approx(100 + 3.5)       # 현금 이자 포함 입금


def test_returns_tr_mode_reinvests():
    h = H(100, 0, 0, 0, 0, 0, 0)
    new, _ = rb.apply_returns(h, np.array([[0.09, 0, 0, 0, 0, 0, 0]]),
                              np.array([[0.01, 0, 0, 0, 0, 0, 0]]), income_to_cash=False)
    assert new[0, 0] == pytest.approx(110)


def test_contribute_conserves_and_never_sells():
    h = H(30, 20, 6, 10, 9, 3, 12)
    new = rb.monthly_contribute(h, 10.0, T)
    assert new.sum() == pytest.approx(h.sum() + 10.0)
    assert (new[0, :6] >= h[0, :6] - 1e-12).all()      # 기존 보유분은 팔지 않는다
    assert new[0, 6] == pytest.approx(config.CASH_W * new.sum(), abs=1e-9)


def test_contribute_fills_deficits_proportionally():
    # 총 100, 목표 대비 equity 부족 6, long_bond 부족 3, 나머지는 목표 이상, 현금 10 -> 납입 9
    h = H(30, 15, 6, 18, 9, 3, 19)
    new = rb.monthly_contribute(h, 0.0, T)
    # 현금 초과 = 19-10 = 9 -> equity +6, long_bond +3
    assert new[0, 0] == pytest.approx(36) and new[0, 1] == pytest.approx(18)
    assert new[0, 6] == pytest.approx(10)


def test_contribute_surplus_split_by_target():
    h = H(36, 18, 6, 18, 9, 3, 10)                     # 이미 목표 비중
    new = rb.monthly_contribute(h, 10.0, T)
    assert (new[0] / new.sum() == pytest.approx(T))


def test_contribute_cash_below_target_buys_nothing():
    h = H(40, 20, 6, 20, 9, 3, 2)
    new = rb.monthly_contribute(h, 1.0, T)
    assert new[0, :6] == pytest.approx(h[0, :6]) and new[0, 6] == pytest.approx(3)


def test_withdraw_from_cash_first():
    h = H(36, 18, 6, 18, 9, 3, 10)
    new, dep, fb = rb.monthly_withdraw(h, 4.0)
    assert new[0, 6] == pytest.approx(6) and new[0, :6] == pytest.approx(h[0, :6])
    assert not dep[0] and not fb[0]


def test_withdraw_sells_capital_gain_assets_pro_rata():
    h = H(36, 18, 6, 18, 9, 3, 2)
    new, dep, fb = rb.monthly_withdraw(h, 8.0)         # 현금 2 + 시세차익 6 매도
    assert new[0, 6] == 0
    assert (h[0, :3] - new[0, :3]).sum() == pytest.approx(6)
    assert (h[0, :3] - new[0, :3]) == pytest.approx(np.array([36, 18, 6]) / 60 * 6)
    assert new[0, 3:6] == pytest.approx(h[0, 3:6])     # 인컴 자산은 안 판다
    assert not fb[0]


def test_withdraw_fallback_then_depletion():
    h = H(1, 1, 1, 5, 5, 5, 0)
    new, dep, fb = rb.monthly_withdraw(h, 6.0)
    assert fb[0] and not dep[0] and new.sum() == pytest.approx(h.sum() - 6)
    new, dep, fb = rb.monthly_withdraw(h, 100.0)
    assert dep[0] and new.sum() == 0


def test_quarterly_full_rebalance_and_risk_flag():
    h = H(70, 5, 5, 10, 5, 2, 3)
    new, before, over = rb.quarterly_rebalance(h, T)
    assert new.sum() == pytest.approx(h.sum())
    assert new[0] == pytest.approx(T * h.sum())
    assert over[0] and before[0] == pytest.approx(0.87)
