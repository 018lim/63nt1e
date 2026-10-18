"""백테스트 + 몬테카를로를 한 번에 돌려 README 6절·대시보드에 쓸 숫자를 만든다.

실행: python -m src.report
"""
import numpy as np
import pandas as pd

import config
from src import a_value as av
from src import backtest, benchmarks, metrics, montecarlo as mc, splice

ACC_END = pd.Timestamp("2025-12-31")      # 적립기 마지막 월말 (61세 적립금 시점)


def run_everything(paths=config.MC_PATHS, block=config.MC_BLOCK, income_to_cash=config.INCOME_TO_CASH):
    tr, inc, price, src, veipx_log = splice.build()
    res = backtest.run_backtest(tr, inc, price, income_to_cash=income_to_cash)
    b = benchmarks.benchmark_returns(tr)
    retire = pd.Timestamp(config.RETIRE) + pd.offsets.MonthEnd(0)
    flows = np.array([(-1 if d >= retire else 1) * backtest.monthly_flow(d.year, d >= retire, config.FX_FIXED)
                      for d in tr.index])
    vals, dep = benchmarks.simulate(b.to_numpy(), flows, res.seed)
    bench_values = pd.DataFrame(vals, index=tr.index, columns=b.columns)
    start = {c: float(bench_values[c].iloc[-1]) for c in b.columns}
    mcres = mc.run_montecarlo(tr, inc, price, res.final_holdings, start, tr.index[-1],
                              paths=paths, block=block, income_to_cash=income_to_cash)
    return dict(tr=tr, inc=inc, price=price, bt=res, bench_returns=b, bench_values=bench_values, mc=mcres)


def accumulation_table(out) -> pd.DataFrame:
    """적립기(1995-01 ~ 2025-12) 지표. 전략과 벤치마크."""
    m = out["bt"].monthly
    rets = {"63NT1E": m["ret_before_flow"]}
    rets.update({c: out["bench_returns"][c] for c in out["bench_returns"].columns})
    a26 = av.a_value(2026)
    rows = {}
    for name, r in rets.items():
        r = r[r.index <= ACC_END]
        s = metrics.summarize(r)
        v = (m["total"] if name == "63NT1E" else out["bench_values"][name])[ACC_END]
        s["balance_a_multiple"] = v * config.FX_FIXED / a26
        s["balance_krw"] = v * config.FX_FIXED
        rows[name] = s
    return pd.DataFrame(rows)


def income_coverage(out) -> dict:
    m = out["bt"].monthly
    y25 = m[m.index.year == 2025]
    annual_wd_2026 = 12 * av.a_value(2026) * config.WITHDRAW_MULT / config.FX_FIXED
    y26 = m[m.index.year == 2026]
    return {
        "retire_all": y25["income_all"].sum() / annual_wd_2026,
        "retire_bucket": y25["income_bucket"].sum() / annual_wd_2026,
        "2026_actual_all": y26["income_all"].sum() / y26["withdrawal"].sum(),
        "2026_actual_bucket": y26["income_bucket"].sum() / y26["withdrawal"].sum(),
    }


def mc_table(out, ages=(80, 86, 90, 95, 100)) -> pd.DataFrame:
    res = out["mc"]
    rows = []
    for n in res.depletion_year:
        for a in ages:
            q = mc.residual_quantiles(res, n, a)
            a_year = av.a_value(config.BIRTH_YEAR + a)
            rows.append({"name": n, "age": a, "depletion_prob": mc.depletion_prob(res, n, a),
                         "median_a_mult": q[0.5] * res.fx / a_year, "p10_a_mult": q[0.1] * res.fx / a_year})
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 200)
    out = run_everything()
    bt = out["bt"]
    print("== 적립기 지표 (1995-01 ~ 2025-12)")
    print(accumulation_table(out).round(4).to_string())
    print("\n== 인컴 커버리지", {k: round(v, 3) for k, v in income_coverage(out).items()})
    print("== 위험자산 70% 초과 로그:", len(bt.risk_log), "건 | 인출 fallback:", len(bt.fallback_months), "건")
    annual_wd = 12 * av.a_value(2026) * config.WITHDRAW_MULT / config.FX_FIXED
    cash_years = config.CASH_W * bt.monthly.loc["2025-12-31", "total"] / annual_wd
    print(f"== 은퇴 시점 현금 10% = 인출액 {cash_years:.2f}년치")
    print("\n== 몬테카를로 (고갈 확률 / 잔여자산 A값 배수 중앙값, 하위10%)")
    t = mc_table(out)
    print(t.pivot(index="name", columns="age", values="depletion_prob").round(4).to_string())
    print(t.pivot(index="name", columns="age", values="median_a_mult").round(1).to_string())
    print(t.pivot(index="name", columns="age", values="p10_a_mult").round(1).to_string())
    s6 = run_everything(block=6)["mc"]
    print("\n== 블록 6개월 민감도 (전략 고갈 확률):", {a: round(mc.depletion_prob(s6, "strategy", a), 4) for a in (80, 86, 90, 95, 100)})
    alt = run_everything(income_to_cash=False)
    print("== INCOME_TO_CASH=False 대체 모드: 2025-12 평가액 $%.0f (기본 $%.0f), 90세 고갈확률 %.4f" % (
        alt["bt"].monthly.loc["2025-12-31", "total"], bt.monthly.loc["2025-12-31", "total"],
        mc.depletion_prob(alt["mc"], "strategy", 90)))


if __name__ == "__main__":
    main()
