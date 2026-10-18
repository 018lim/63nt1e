import pytest

import config
from src import glide

# CLAUDE.md 2.2 검증표 (%)
TABLE = {
    30: [36.0, 18.0, 6.0, 18.0, 9.0, 3.0, 10.0, 63.0],
    61: [19.8, 20.25, 4.45, 20.25, 20.7, 4.55, 10.0, 49.05],
    90: [9.0, 18.0, 3.0, 18.0, 36.0, 6.0, 10.0, 36.0],
}


@pytest.mark.parametrize("age", sorted(TABLE))
def test_matches_spec_table(age):
    w = glide.target_weights(age) * 100
    expected = TABLE[age]
    assert list(w.round(6)) == pytest.approx(expected[:7], abs=0.005)  # 표는 소수 둘째 자리 반올림값
    assert glide.risky_share(w) == pytest.approx(expected[7], abs=0.005)


@pytest.mark.parametrize("age", range(30, 101))
def test_sum_is_one_and_nonnegative(age):
    w = glide.target_weights(age)
    assert w.sum() == pytest.approx(1.0, abs=1e-12)
    assert (w >= 0).all()
    assert w["cash"] == pytest.approx(config.CASH_W)


def test_risk_below_limit_all_ages():
    for age in range(30, 101):
        assert glide.risky_share(glide.target_weights(age)) <= config.RISK_LIMIT


def test_integer_age_from_calendar_year():
    assert glide.age_of(1995) == 30
    assert glide.age_of(2026) == 61
    assert glide.age_of(2055) == 90


def test_continues_after_90():
    x, y = glide.inner_weights(100)
    assert (x, y) == pytest.approx((0.25, 0.65))
