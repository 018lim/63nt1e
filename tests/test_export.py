"""대시보드 데이터가 report 결과와 일치하는지 (python -m src.report, python -m src.export 실행 후)."""
import json

import pytest

import config


@pytest.fixture(scope="module")
def data():
    return json.loads((config.DASHBOARD_DIR / "data.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def results():
    return json.loads((config.REPORTS_DIR / "results.json").read_text(encoding="utf-8"))


def test_json_is_valid_standard_json():
    text = (config.DASHBOARD_DIR / "data.json").read_text(encoding="utf-8")
    json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))   # NaN/Infinity 금지
    js = (config.DASHBOARD_DIR / "data.js").read_text(encoding="utf-8")
    assert js.startswith("window.DATA = ") and js.rstrip().endswith(";")


def test_matches_report(data, results):
    mc = {(m["name"], m["age"]): m for m in results["mc"]}
    ages = data["mc"]["ages"]
    for name in data["meta"]["ids"]:
        for a in (80, 90, 100):
            assert data["mc"]["series"][name]["dep_cum"][ages.index(a)] == pytest.approx(mc[(name, a)]["depletion_prob"], abs=1e-4)
    assert data["metrics"]["strategy"]["balance_a_multiple"] == pytest.approx(results["accumulation"]["63nt1e"]["balance_a_multiple"])
    assert data["coverage"]["retire"]["bucket"] == pytest.approx(results["coverage"]["retire_bucket"], abs=1e-3)
    assert data["kpi"]["cash_years"] == pytest.approx(results["cash_years"], abs=0.01)


def test_histogram_consistent_with_cumulative(data):
    paths = data["meta"]["mc_paths"]
    for name, s in data["mc"]["series"].items():
        assert sum(s["dep_hist"]) / paths == pytest.approx(s["dep_cum"][-1], abs=1e-4)
        cum = 0
        for h, c in zip(s["dep_hist"], s["dep_cum"]):
            cum += h
            assert cum / paths == pytest.approx(c, abs=1e-4)


def test_shapes(data):
    assert len(data["backtest"]["dates"]) == 381 and data["backtest"]["dates"][-1] == "2026-09"
    assert data["weights"]["ages"][0] == 30 and data["weights"]["ages"][-1] == 100
    assert all(abs(sum(r) - 1) < 1e-3 for r in data["weights"]["values"])
    assert data["meta"]["life_male"] == 86.3 and data["meta"]["life_female"] == 90.7
    for a in range(80, 101):
        assert len(data["mc"]["series"]["strategy"]["resid"][str(a)]) == 5


def test_benchmark_coverage_and_meta(data, results):
    cov = data["coverage"]
    assert set(cov["bench"]) == {"60/40", "stock100", "cash100"}          # TDF는 분배금에 자본이득이 섞여 제외
    assert all(len(v["p50"]) == len(cov["ages"]) for v in cov["bench"].values())
    assert cov["bench_retire"]["60/40"] == pytest.approx(results["coverage"]["bench_retire"]["60/40"], abs=1e-3)
    assert 0 < data["meta"]["mc_fallback_paths"] < data["meta"]["mc_paths"]
    assert data["meta"]["mc_fallback_paths"] == results["mc_fallback_paths"]["base"]


def test_scenario_block(data, results):
    sc = data["scenario"]
    assert sc["shocks"] == [0.0, 0.1, 0.2, 0.3, 0.4, 0.5] and sc["names"] == ["strategy", "60/40", "stock100", "cash100"]
    k90 = sc["ages"].index(90)
    for n in sc["names"]:
        assert len(sc["series"][n]["dep_cum"]) == 6 and len(sc["series"][n]["dep_cum"][0]) == len(sc["ages"])
        assert len(sc["series"][n]["resid"][0]["90"]) == 5
    # results.json 과 같은 값
    assert sc["series"]["strategy"]["dep_cum"][5][k90] == pytest.approx(results["shock"]["series"]["strategy"]["dep_cum"][5][k90], abs=1e-4)
    assert sc["strategy_cash_years"]["0.0"] == pytest.approx(sc["strategy_cash_years"]["0.5"])
