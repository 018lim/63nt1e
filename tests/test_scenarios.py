import numpy as np
import pytest

import config
from src import report, scenarios


@pytest.fixture(scope="module")
def small():
    out = report.run_everything(paths=400)
    return scenarios.run_scenarios(out, paths=400, shocks=(0.0, 0.2, 0.5))


def test_apply_shock_only_hits_stock_assets():
    h = np.array([10.0, 20, 30, 40, 50, 60, 70])
    s = scenarios.apply_shock(h, 0.5)
    i = {a: config.ASSETS.index(a) for a in config.ASSETS}
    assert s[i["equity"]] == 5 and s[i["dividend"]] == 20
    for a in ("long_bond", "gold", "mid_bond", "reit", "cash"):
        assert s[i[a]] == h[i[a]]
    assert h[i["equity"]] == 10                       # 입력은 바꾸지 않는다


def test_immediate_loss_matches_weights(small):
    w = small["strategy_stock_weight"]
    got = small["series"]["strategy"]["immediate_loss"]
    assert got == pytest.approx([0.0, 0.2 * w, 0.5 * w])
    assert small["series"]["60/40"]["immediate_loss"] == pytest.approx([0.0, 0.12, 0.30])
    assert small["series"]["stock100"]["immediate_loss"] == pytest.approx([0.0, 0.2, 0.5])
    assert small["series"]["cash100"]["immediate_loss"] == pytest.approx([0.0, 0.0, 0.0])


def test_bigger_crash_never_better(small):
    """같은 난수를 쓰므로 충격이 클수록 고갈 확률은 줄지 않고, 잔여자산 중앙값은 늘지 않는다."""
    ages = small["ages"]
    for n in ("strategy", "60/40", "stock100"):
        for k in (ages.index(90), ages.index(100)):
            p = [row[k] for row in small["series"][n]["dep_cum"]]
            assert p == sorted(p)
        med = [rows[90][2] for rows in small["series"][n]["resid"]]
        assert med == sorted(med, reverse=True)


def test_cash_benchmark_unaffected_and_cash_buffer(small):
    c = small["series"]["cash100"]["dep_cum"]
    assert c[0] == c[1] == c[2]
    cy = small["strategy_cash_years"]
    assert cy[0.0] == pytest.approx(cy[0.5])          # 현금 완충은 충격의 영향을 받지 않는다
    assert 3.0 < cy[0.0] < 3.4
