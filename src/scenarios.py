"""가상 시나리오: 은퇴 시점(2026-01 인출 시작 직전)에 주가가 한 번에 폭락하면? (CLAUDE.md 2.11)

2025-12 말 잔고에 충격을 주고, 2026-01부터 100세까지 몬테카를로로 인출을 이어 간다.
 - 충격 대상: 주식형 자산 = 주식지수 + 배당성장 (금·리츠·채권·현금은 그대로)
 - 벤치마크: 60/40은 주식 60%만큼, 주식 100%는 전부, 현금 100%는 영향 없음. TDF는 내부 주식 비중을 알 수 없어 제외.
 - 충격 크기별로 같은 난수 시드(같은 월 번호)를 써서 '충격이 없을 때'와 짝을 지어 비교한다.
 - 충격 이후 수익률은 1995~2026년 과거 월 수익률을 12개월 블록으로 다시 뽑으므로, 폭락 뒤 장기 하락이 이어지는 경우는 담지 못한다.
실행: python -m src.scenarios (결과 요약 출력)
"""
import numpy as np
import pandas as pd

import config
from src import a_value as av
from src import backtest, montecarlo as mc, report
from src import rebalance as rb

SHOCKS = (0.0, 0.10, 0.20, 0.30, 0.40, 0.50)
NAMES = ["strategy", "60/40", "stock100", "cash100"]          # TDF 제외
STOCK_ASSETS = ["equity", "dividend"]
STOCK_WEIGHT = {"60/40": 0.6, "stock100": 1.0, "cash100": 0.0}      # 전략은 실제 보유 비중으로 계산
SCENARIO_START = "2025-12-31"


def apply_shock(holdings: np.ndarray, x: float) -> np.ndarray:
    """주식형 자산(주식지수·배당성장) 평가액을 x만큼 줄인다."""
    h = np.asarray(holdings, float).copy()
    for a in STOCK_ASSETS:
        h[config.ASSETS.index(a)] *= (1.0 - x)
    return h


def run_scenarios(out=None, paths=config.MC_PATHS, shocks=SHOCKS) -> dict:
    out = out or report.run_everything(paths=paths)
    tr, inc, price = out["tr"], out["inc"], out["price"]
    pre = backtest.run_backtest(tr, inc, price, end=SCENARIO_START)           # 2025-12 말 보유액 (나이 61세 목표 비중으로 리밸런싱된 상태)
    h0 = pre.final_holdings
    base_bench = {n: float(out["bench_values"][n if n != "60/40" else "60/40"].loc[SCENARIO_START])
                  for n in ("60/40", "stock100", "cash100")}
    base_bench["tdf"] = float(out["bench_values"]["tdf"].loc[SCENARIO_START])
    total0 = float(h0.sum())
    a26 = av.a_value(2026)

    result = {"shocks": list(shocks), "ages": list(range(61, config.MC_MAX_AGE + 1)), "start": SCENARIO_START, "series": {}}
    for n in NAMES:
        result["series"][n] = {"immediate_loss": [], "start_a_multiple": [], "dep_cum": [], "resid": []}
    cash_years = {}
    for x in shocks:
        h = apply_shock(h0, x)
        bench = {n: base_bench[n] * (1.0 - STOCK_WEIGHT[n] * x) for n in ("60/40", "stock100", "cash100")}
        bench["tdf"] = base_bench["tdf"]
        res = mc.run_montecarlo(tr, inc, price, h, bench, pd.Timestamp(SCENARIO_START), paths=paths)
        ages = result["ages"]
        for n in NAMES:
            start_value = float(h.sum()) if n == "strategy" else bench[n]
            base_value = total0 if n == "strategy" else base_bench[n]
            s = result["series"][n]
            s["immediate_loss"].append(1.0 - start_value / base_value)
            s["start_a_multiple"].append(start_value * config.FX_FIXED / a26)
            s["dep_cum"].append([mc.depletion_prob(res, n, a) for a in ages])
            rows = {}
            for a in ages:
                q = mc.residual_quantiles(res, n, a, qs=(0.10, 0.25, 0.50, 0.75, 0.90))
                a_year = av.a_value(config.BIRTH_YEAR + a)
                rows[a] = [q[k] * config.FX_FIXED / a_year for k in (0.10, 0.25, 0.50, 0.75, 0.90)]
            s["resid"].append(rows)
        cash_years[x] = float(h[rb.CASH] / (12 * a26 * config.WITHDRAW_MULT / config.FX_FIXED))
        result.setdefault("fallback_paths", {})[x] = res.fallback_paths
    result["strategy_cash_years"] = cash_years
    result["strategy_stock_weight"] = float(h0[[config.ASSETS.index(a) for a in STOCK_ASSETS]].sum() / total0)
    return result


def main():
    r = run_scenarios()
    print("전략의 주식형(주식지수+배당성장) 비중: %.1f%%" % (100 * r["strategy_stock_weight"]))
    ages = r["ages"]
    for n in NAMES:
        s = r["series"][n]
        print(f"\n[{n}]  충격 / 즉시 손실 / 90세 고갈 확률 / 100세 고갈 확률 / 90세 잔여 중앙값(A)")
        for i, x in enumerate(r["shocks"]):
            print(f"  -{x * 100:.0f}%  {s['immediate_loss'][i] * 100:5.1f}%  {s['dep_cum'][i][ages.index(90)] * 100:6.2f}%  "
                  f"{s['dep_cum'][i][ages.index(100)] * 100:6.2f}%  {s['resid'][i][90][2]:8.1f}")


if __name__ == "__main__":
    main()
