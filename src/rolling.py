"""은퇴 시점별 인출기 롤링 분석 (기존 규칙 변경 없음, 적립기는 다시 돌리지 않는다).

- 모든 전략이 같은 시작 자산(적립기 결과 255.6A)으로 은퇴하고, 시작 월을 매월 한 칸씩 밀어 가며 10·15·20년 인출한다.
- 63nt1e: 시작 시 61세 목표 비중으로 투입 후 기존 규칙(글라이드 매년 0.5%p, 분기 말 전체 리밸런싱, 인출은 현금 먼저 -> 시세차익 자산 -> 최후 수단 인컴 자산).
  나이는 시작 달력 연도가 61세이고, 이후 달력 연도마다 +1 (12월 말에 다음 해 목표로 갱신하는 기존 규칙과 동일).
- 인출액: 월 A2026 x (1+0.0432)^(경과 연수) x 2/3 (연 단위로 증가). 모든 시작 시점에 같은 금액 경로를 쓴다.
- 수익 재투자(INCOME_TO_CASH=False): 자산을 TR로 굴린다.
- 시작 월은 데이터 첫 월부터 인출 기간을 끝까지 채울 수 있는 마지막 월까지.
실행: python -m src.rolling [--chart]   (결과를 화면에 출력만 한다. 파일·README는 건드리지 않음)
"""
import json
import sys

import numpy as np
import pandas as pd

import config
from src import a_value as av
from src import benchmarks, glide
from src import rebalance as rb

WD_GROWTH = 0.0432
HORIZONS = (10, 15, 20)
NAMES = ["63nt1e", "60/40", "stock100", "cash100", "tdf"]
LABELS = {"63nt1e": "63nt1e", "60/40": "60/40", "stock100": "주식 100%", "cash100": "현금 100%", "tdf": "TDF"}
START_AGE = 61


def withdrawal_path(months: int, fx: float, growth: float = WD_GROWTH) -> np.ndarray:
    """월별 인출액(달러, 양수). 시작 후 12개월마다 (1+growth)배."""
    wd0 = av.a_value(2026) * config.WITHDRAW_MULT / fx
    return wd0 * (1.0 + growth) ** (np.arange(months) // 12)


def _target_table(max_years: int) -> np.ndarray:
    """행: 나이 61 .. 61+max_years+1, 열: 7개 자산 목표 비중."""
    return np.array([glide.target_weights(START_AGE + k).to_numpy() for k in range(max_years + 2)])


def run_strategy(tr, inc, price, start_value: float, years: int, fx=config.FX_FIXED, growth=WD_GROWTH) -> dict:
    """63nt1e 롤링. 반환: starts(시작 월 인덱스), end_value, depleted(고갈 여부)."""
    N, T = len(tr), 12 * years
    starts = np.arange(0, N - T + 1)
    P = len(starts)
    price_np, inc_np = price[config.ASSETS].to_numpy(), inc[config.ASSETS].to_numpy()
    cal_month, cal_year = tr.index.month.to_numpy(), tr.index.year.to_numpy()
    tgt = _target_table(years)
    H = np.tile(start_value * tgt[0], (P, 1))
    y0 = cal_year[starts]
    wd = withdrawal_path(T, fx, growth)
    dead = np.zeros(P, bool)
    for t in range(T):
        idx = starts + t
        H, _ = rb.apply_returns(H, price_np[idx], inc_np[idx], income_to_cash=False)
        H, depleted, _ = rb.monthly_withdraw(H, wd[t])
        dead |= depleted
        q = np.isin(cal_month[idx], (3, 6, 9, 12))
        if q.any():
            age_idx = (cal_year[idx] - y0) + (cal_month[idx] == 12)        # 12월 말에는 다음 해 나이 기준
            H = np.where(q[:, None], H.sum(axis=1)[:, None] * tgt[age_idx], H)
    return {"starts": starts, "end_value": H.sum(axis=1), "depleted": dead}


def run_benchmarks(tr, start_value: float, years: int, fx=config.FX_FIXED, growth=WD_GROWTH) -> dict:
    bench = benchmarks.benchmark_returns(tr)
    N, T = len(tr), 12 * years
    starts = np.arange(0, N - T + 1)
    out = {}
    wd = withdrawal_path(T, fx, growth)
    for name in ("60/40", "stock100", "cash100", "tdf"):
        r = bench[name].to_numpy()
        R = np.stack([r[starts + t] for t in range(T)])                       # (T, P)
        vals, dep_at = benchmarks.simulate(R, -wd, start_value)
        out[name] = {"starts": starts, "end_value": vals[-1], "depleted": dep_at >= 0}
    return out


def run_rolling(tr, inc, price, start_a_multiple: float, horizons=HORIZONS, fx=config.FX_FIXED, growth=WD_GROWTH) -> dict:
    start_value = start_a_multiple * av.a_value(2026) / fx
    res = {"start_value": start_value, "months": [d.strftime("%Y-%m") for d in tr.index], "by_horizon": {}}
    for y in horizons:
        d = {"63nt1e": run_strategy(tr, inc, price, start_value, y, fx, growth)}
        d.update(run_benchmarks(tr, start_value, y, fx, growth))
        res["by_horizon"][y] = d
    return res


def ratio(r: dict, start_value: float) -> np.ndarray:
    return r["end_value"] / start_value * 100.0


def summary_table(res: dict, y: int) -> pd.DataFrame:
    rows = []
    for n in NAMES:
        x = ratio(res["by_horizon"][y][n], res["start_value"])
        rows.append({"전략": LABELS[n], "시작 월 수": len(x), "최악": x.min(), "하위 10%": np.quantile(x, 0.10), "중앙값": np.median(x),
                     "최선": x.max(), "바닥난 시작 월 수": int((x <= 0).sum())})
    return pd.DataFrame(rows).set_index("전략")


def worst_starts(res: dict, y: int, k: int = 3) -> dict:
    out = {}
    for n in NAMES:
        r = res["by_horizon"][y][n]
        x = ratio(r, res["start_value"])
        order = np.argsort(x, kind="stable")[:k]
        out[n] = [(res["months"][r["starts"][i]], float(x[i])) for i in order]
    return out


def chart_table(res: dict, y: int = 15) -> pd.DataFrame:
    """시작 월(행) x 전략(열): y년 뒤 잔액 비율(시작 대비 %)."""
    cols = {LABELS[n]: ratio(res["by_horizon"][y][n], res["start_value"]) for n in NAMES}
    starts = res["by_horizon"][y]["63nt1e"]["starts"]
    return pd.DataFrame(cols, index=[res["months"][i] for i in starts])


def load_start_a_multiple() -> float:
    """적립기 결과(이미 계산된 reports/results.json)에서 61세 적립금(A값 배수)을 읽는다. 적립기는 다시 돌리지 않는다."""
    r = json.loads((config.REPORTS_DIR / "results.json").read_text(encoding="utf-8"))
    return float(r["accumulation"]["63nt1e"]["balance_a_multiple"])


def main(argv=None):
    from src import splice
    argv = sys.argv[1:] if argv is None else argv
    pd.set_option("display.width", 220); pd.set_option("display.float_format", lambda v: f"{v:,.1f}")
    tr, inc, price, _, _ = splice.build()
    a_mult = load_start_a_multiple()
    res = run_rolling(tr, inc, price, a_mult)
    print(f"데이터: {res['months'][0]} ~ {res['months'][-1]} ({len(res['months'])}개월)")
    print(f"시작 자산 {a_mult:.1f}A = ${res['start_value']:,.0f} (모든 전략 동일), 인출 시작액 월 ${withdrawal_path(1, config.FX_FIXED)[0]:,.0f}, 연 {WD_GROWTH * 100:.2f}% 증가, INCOME_TO_CASH=False\n")
    for y in HORIZONS:
        t = summary_table(res, y)
        print(f"== 인출 {y}년: 종료 시 잔액 비율 (시작 자산 대비 %, 명목)")
        print(t.to_string(formatters={"시작 월 수": "{:d}".format, "바닥난 시작 월 수": "{:d}".format}))
        print()
    for y in HORIZONS:
        print(f"== 인출 {y}년: 최악의 시작 월 3개 (종료 시 잔액 비율 %)")
        for n, lst in worst_starts(res, y).items():
            print(f"  {LABELS[n]:8s} " + " | ".join(f"{m} {v:,.1f}%" for m, v in lst))
        print()
    ch = chart_table(res, 15)
    if "--chart" in argv:
        print("== 차트 데이터: 시작 월 x 15년 뒤 잔액 비율(%)"); print(ch.to_string())
    else:
        print("== 차트 데이터(15년 뒤 잔액 비율 %): 6개월 간격 표본 (전체는 --chart)")
        print(ch.iloc[::6].to_string())
    return res


if __name__ == "__main__":
    main()
