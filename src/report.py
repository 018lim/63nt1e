"""백테스트 + 몬테카를로를 한 번에 돌려 README 6절·대시보드에 쓸 숫자를 만든다.

실행: python -m src.report
"""
import numpy as np
import pandas as pd

import config
from src import a_value as av
from src import backtest, benchmarks, metrics, montecarlo as mc, scenarios, splice

ACC_END = pd.Timestamp("2025-12-31")      # 적립기 마지막 월말 (61세 적립금 시점)


def run_everything(paths=config.MC_PATHS, block=config.MC_BLOCK, income_to_cash=config.INCOME_TO_CASH,
                   income_fallback=True):
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
                              paths=paths, block=block, income_to_cash=income_to_cash, income_fallback=income_fallback)
    return dict(tr=tr, inc=inc, price=price, bt=res, bench_returns=b, bench_values=bench_values, mc=mcres)


def accumulation_table(out) -> pd.DataFrame:
    """적립기(1995-01 ~ 2025-12) 지표. 전략과 벤치마크."""
    m = out["bt"].monthly
    rets = {"63nt1e": m["ret_before_flow"]}
    rets.update({c: out["bench_returns"][c] for c in out["bench_returns"].columns})
    a26 = av.a_value(2026)
    rows = {}
    for name, r in rets.items():
        r = r[r.index <= ACC_END]
        s = metrics.summarize(r, out["tr"]["cash"])
        v = (m["total"] if name == "63nt1e" else out["bench_values"][name])[ACC_END]
        s["balance_a_multiple"] = v * config.FX_FIXED / a26
        s["balance_krw"] = v * config.FX_FIXED
        rows[name] = s
    return pd.DataFrame(rows)


def income_coverage(out) -> dict:
    m = out["bt"].monthly
    y25 = m[m.index.year == 2025]
    annual_wd_2026 = 12 * av.a_value(2026) * config.WITHDRAW_MULT / config.FX_FIXED
    y26 = m[m.index.year == 2026]
    bench = {}
    rates = benchmarks.benchmark_income_rates(out["inc"])
    for c in ("60/40", "stock100", "cash100"):
        v_prev = out["bench_values"][c].shift(1)
        inc25 = (v_prev * rates[c])[v_prev.index.year == 2025].sum()
        bench[c] = float(inc25 / annual_wd_2026)
    return {
        "bench_retire": bench,
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


def compute_results(base=None) -> dict:
    """README·대시보드에 쓸 숫자 모음 (reports/results.json)."""
    out = base or run_everything()
    bt, res = out["bt"], out["mc"]
    acc = accumulation_table(out)
    cov = income_coverage(out)
    annual_wd = 12 * av.a_value(2026) * config.WITHDRAW_MULT / config.FX_FIXED
    ages = (80, 86, 90, 95, 100)
    mct = mc_table(out, ages)
    s6 = run_everything(block=6)
    alt = run_everything(income_to_cash=False)
    alt_acc = accumulation_table(alt)
    strict = run_everything(income_fallback=False)
    return {
        "accumulation": acc.to_dict(),
        "coverage": {k: (float(v) if not isinstance(v, dict) else {kk: float(vv) for kk, vv in v.items()}) for k, v in cov.items()},
        "cash_years": float(config.CASH_W * bt.monthly.loc["2025-12-31", "total"] / annual_wd),
        "risk_log_count": len(bt.risk_log), "backtest_fallback_months": len(bt.fallback_months),
        "mc_fallback_paths": {"base": res.fallback_paths, "block6": s6["mc"].fallback_paths},
        "mc": mct.to_dict(orient="records"),
        "shock": scenarios.run_scenarios(out),
        "strict_no_income_sale": {n: {a: mc.depletion_prob(strict["mc"], n, a) for a in ages} for n in ("strategy",)},
        "block6": {n: {a: mc.depletion_prob(s6["mc"], n, a) for a in ages} for n in s6["mc"].depletion_year},
        "income_to_cash_false": {
            "accumulation_63nt1e": alt_acc["63nt1e"].to_dict(),
            "depletion_90": {n: mc.depletion_prob(alt["mc"], n, 90) for n in alt["mc"].depletion_year},
            "median_a_mult_90_strategy": next(r["median_a_mult"] for r in mc_table(alt, (90,)).to_dict("records") if r["name"] == "strategy"),
        },
    }


def main():
    import json
    pd.set_option("display.width", 200)
    r = compute_results()
    config.REPORTS_DIR.mkdir(exist_ok=True)
    (config.REPORTS_DIR / "results.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    acc = pd.DataFrame(r["accumulation"])
    print("== 적립기 지표 (1995-01 ~ 2025-12)"); print(acc.round(4).to_string())
    print("\n== 인컴 커버리지", {k: round(v, 3) for k, v in r["coverage"].items()})
    print(f"== 은퇴 시점 현금 10% = 인출액 {r['cash_years']:.2f}년치")
    print("== 위험자산 70% 초과:", r["risk_log_count"], "건 | 백테스트 인컴자산 매도(fallback):", r["backtest_fallback_months"],
          "개월 | MC fallback 경로 수:", r["mc_fallback_paths"])
    t = pd.DataFrame(r["mc"])
    print("\n== 몬테카를로 고갈 확률"); print(t.pivot(index="name", columns="age", values="depletion_prob").round(4).to_string())
    print("== 잔여자산 중앙값 (A값 배수)"); print(t.pivot(index="name", columns="age", values="median_a_mult").round(1).to_string())
    print("== 잔여자산 하위 10% (A값 배수)"); print(t.pivot(index="name", columns="age", values="p10_a_mult").round(1).to_string())
    print("\n== 블록 6개월 민감도 (고갈 확률)"); print(pd.DataFrame(r["block6"]).T.round(4).to_string())
    print("\n== 명세 문자 그대로(인컴 자산 매도 없음, 시세차익+현금으로 못 내면 고갈) 전략 고갈 확률:",
          {a: round(v, 4) for a, v in r["strict_no_income_sale"]["strategy"].items()})
    a = r["income_to_cash_false"]["accumulation_63nt1e"]; b = acc["63nt1e"]
    print("\n== INCOME_TO_CASH 기본(True) vs False, 63nt1e 적립기")
    for k in ("cagr", "vol", "mdd", "return_per_vol", "sharpe", "balance_a_multiple"):
        print(f"  {k:20s} {b[k]:.4f}  {a[k]:.4f}  (차이 {a[k]-b[k]:+.4f})")
    print("  90세 고갈 확률(전략):", round(r["income_to_cash_false"]["depletion_90"]["strategy"], 4),
          "| 90세 잔여자산 중앙값(A배수):", round(r["income_to_cash_false"]["median_a_mult_90_strategy"], 1))


if __name__ == "__main__":
    main()
