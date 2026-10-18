"""대시보드용 사전 계산 데이터 -> dashboard/data.json, dashboard/data.js (CLAUDE.md 2.10).

data.js 는 같은 내용을 `window.DATA = {...}` 로 감싼 것이다. index.html 을 더블클릭(file://)으로 열면
브라우저가 data.json 을 직접 읽지 못하므로, <script src="data.js"> 로 불러올 수 있게 둘 다 만든다.
실행: python -m src.export
"""
import json

import numpy as np
import pandas as pd

import config
from src import a_value as av
from src import glide, metrics, report
from src import montecarlo as mc

IDS = ["strategy", "60/40", "stock100", "cash100", "tdf"]
LABELS = {"strategy": "63NT1E", "60/40": "60/40", "stock100": "주식 100%", "cash100": "현금 100%", "tdf": "TDF"}
BENCH_COL = {"strategy": None, "60/40": "60/40", "stock100": "stock100", "cash100": "cash100", "tdf": "tdf"}
AGES = list(range(61, config.MC_MAX_AGE + 1))     # 2026(61세) ~ 100세
QS = (0.10, 0.25, 0.50, 0.75, 0.90)


def r(x, d=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


def clean(x):
    """NaN/inf 는 JSON 표준이 아니므로 None(null)으로 바꾼다."""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (float, np.floating)) and not np.isfinite(x):
        return None
    return x


def build(out=None) -> dict:
    out = out or report.run_everything()
    bt, res = out["bt"], out["mc"]
    m = bt.monthly
    a26 = av.a_value(2026)
    krw_eok = lambda usd: np.asarray(usd, float) * config.FX_FIXED / 1e8
    dates = [d.strftime("%Y-%m") for d in m.index]

    # --- 적립기 곡선 (억 원, 고정 환율)
    series = {"strategy": krw_eok(m["total"])}
    for i in IDS[1:]:
        series[i] = krw_eok(out["bench_values"][BENCH_COL[i]])
    # --- 낙폭 (적립기 TWR 기준)
    acc_idx = m.index[m.index <= report.ACC_END]
    rets = {"strategy": m["ret_before_flow"]}
    rets.update({i: out["bench_returns"][BENCH_COL[i]] for i in IDS[1:]})
    dd = {i: (metrics.drawdown(rets[i].loc[acc_idx]) * 100).round(3).tolist() for i in IDS}
    acc = report.accumulation_table(out)
    acc_t = {LABELS_ID: acc[name].to_dict() for LABELS_ID, name in zip(IDS, ["63NT1E", "60/40", "stock100", "cash100", "tdf"])}

    # --- 글라이드패스 비중 (나이 30~100)
    ages_w = list(range(config.START_AGE, config.MC_MAX_AGE + 1))
    weights = [[r(v, 5) for v in glide.target_weights(a).tolist()] for a in ages_w]

    # --- 몬테카를로
    mcd = {}
    for i in IDS:
        dy = res.depletion_year[i]
        cum = [r(mc.depletion_prob(res, i, a), 5) for a in AGES]
        hist = [int(((dy == config.BIRTH_YEAR + a)).sum()) for a in AGES]
        resid = {}
        for a in AGES:
            col = config.BIRTH_YEAR + a - res.years[0]
            a_year = av.a_value(config.BIRTH_YEAR + a)
            v = res.year_end_value[i][:, col] * config.FX_FIXED / a_year
            resid[a] = [r(np.quantile(v, q), 2) for q in QS]
        mcd[i] = {"dep_cum": cum, "dep_hist": hist, "resid": resid}

    # --- 인컴 커버리지 (MC, 해당 연도 말까지 고갈되지 않은 경로 기준)
    cov_ages, cov = [], {"all_p10": [], "all_p50": [], "bucket_p10": [], "bucket_p50": [], "alive": []}
    for yi, y in enumerate(res.years):
        if yi == 0:
            continue                                   # 2026년은 10~12월 3개월뿐이라 제외 (백테스트 실제값을 따로 표시)
        alive = res.year_end_value["strategy"][:, yi] > 0
        wd = res.withdrawal[yi]
        a = int(y) - config.BIRTH_YEAR
        cov_ages.append(a)
        for k, arr in (("all", res.income_all), ("bucket", res.income_bucket)):
            x = arr[alive, yi] / wd
            cov[f"{k}_p10"].append(r(np.quantile(x, 0.10)))
            cov[f"{k}_p50"].append(r(np.quantile(x, 0.50)))
        cov["alive"].append(r(alive.mean(), 4))
    c = report.income_coverage(out)

    data = {
        "meta": {
            "fx": config.FX_FIXED, "a2026": a26, "birth_year": config.BIRTH_YEAR, "start_age": config.START_AGE,
            "retire_age": config.START_AGE + 31, "life_male": config.LIFE_MALE, "life_female": config.LIFE_FEMALE,
            "life_default": config.LIFE_DEFAULT, "max_age": config.MC_MAX_AGE,
            "mc_paths": res.paths, "mc_block": res.block, "mc_seed": config.MC_SEED,
            "data_end": dates[-1], "mc_start": "2026-10", "income_to_cash": config.INCOME_TO_CASH,
            "labels": LABELS, "ids": IDS, "assets": config.ASSETS,
            "asset_labels": {"equity": "주식지수", "long_bond": "장기채", "gold": "금", "dividend": "배당성장",
                             "mid_bond": "중기채", "reit": "리츠", "cash": "현금"},
        },
        "backtest": {"dates": dates, "retire_index": dates.index("2026-01"),
                     "series": {i: np.round(series[i], 3).tolist() for i in IDS}},
        "drawdown": {"dates": [d.strftime("%Y-%m") for d in acc_idx], "series": dd},
        "metrics": acc_t,
        "weights": {"ages": ages_w, "assets": config.ASSETS, "values": weights},
        "mc": {"ages": AGES, "series": mcd, "quantiles": list(QS)},
        "coverage": {"ages": cov_ages, **cov,
                     "actual_2026": {"age": 61, "all": r(c["2026_actual_all"]), "bucket": r(c["2026_actual_bucket"])},
                     "retire": {"all": r(c["retire_all"]), "bucket": r(c["retire_bucket"])}},
        "kpi": {"retire_balance_a": r(acc_t["strategy"]["balance_a_multiple"], 1),
                "retire_balance_krw": r(acc_t["strategy"]["balance_krw"], 0),
                "cash_years": r(config.CASH_W * m.loc["2025-12-31", "total"] /
                                (12 * a26 * config.WITHDRAW_MULT / config.FX_FIXED), 2)},
    }
    return clean(data)


def main():
    config.DASHBOARD_DIR.mkdir(exist_ok=True)
    data = build()
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    (config.DASHBOARD_DIR / "data.json").write_text(text, encoding="utf-8")
    (config.DASHBOARD_DIR / "data.js").write_text("window.DATA = " + text + ";\n", encoding="utf-8")
    print(f"data.json {len(text) / 1024:.0f} KB 저장")


if __name__ == "__main__":
    main()
