"""백테스트: 1994-12 말 시드 투입 -> 1995-01 ~ 최신 완성 월 (CLAUDE.md 2.3, 2.4).

매월 순서: ① 그달 수익률 반영 ② 인컴 현금 입금 ③ 월간 처리(납입/인출) ④ 분기 말이면 전체 리밸런싱.
금액 단위는 달러 (A값 원화 / fx).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

import config
from src import a_value as av
from src import glide
from src import rebalance as rb

QUARTER_MONTHS = (3, 6, 9, 12)


@dataclass
class BacktestResult:
    monthly: pd.DataFrame        # 월별 요약 (평가액, 흐름, 인컴, 수익률 등)
    weights: pd.DataFrame        # 월말(리밸런싱 후) 자산 비중
    risk_log: pd.DataFrame       # 분기 리밸런싱 직전 위험자산 비중이 한도를 넘은 기록
    fallback_months: list        # 인출 시 인컴 자산까지 팔아야 했던 달
    depleted_month: object       # 고갈된 달 (없으면 None)
    seed: float
    final_holdings: np.ndarray   # 마지막 월말 보유액 (7,)


def monthly_flow(year: int, retired: bool, fx: float, published=None) -> float:
    a = av.a_value(year, published) / fx
    return a * (config.WITHDRAW_MULT if retired else config.CONTRIB_MULT)


def run_backtest(tr, inc, price, fx=config.FX_FIXED, income_to_cash=config.INCOME_TO_CASH,
                 end=None, published=None) -> BacktestResult:
    """tr/inc/price: splice 출력(월말 인덱스). end: 마지막 월 (포함, 기본은 데이터 끝)."""
    idx = tr.index if end is None else tr.index[tr.index <= pd.Timestamp(end)]
    retire = pd.Timestamp(config.RETIRE) + pd.offsets.MonthEnd(0)

    seed = config.SEED_MULT * av.a_value(int(config.START[:4]), published) / fx
    target0 = glide.target_weights_for_year(int(config.START[:4])).to_numpy()
    H = (seed * target0)[None, :]

    price_np, inc_np = price[config.ASSETS].to_numpy(), inc[config.ASSETS].to_numpy()
    rows, wrows, risk_rows, fallback, depleted_month = [], [], [], [], None
    prev_total = H.sum()
    dead = False
    for i, d in enumerate(idx):
        year, month = d.year, d.month
        target = glide.target_weights_for_year(year).to_numpy()
        retired = d >= retire

        H, income = rb.apply_returns(H, price_np[i][None, :], inc_np[i][None, :], income_to_cash)
        total_after_return = H.sum()
        flow = monthly_flow(year, retired, fx, published)
        if dead:
            flow_applied = 0.0
        elif not retired:
            H = rb.monthly_contribute(H, flow, target)
            flow_applied = flow
        else:
            H, depleted, fb = rb.monthly_withdraw(H, flow)
            flow_applied = -flow
            if fb[0]:
                fallback.append(d)
            if depleted[0]:
                dead, depleted_month = True, d
                flow_applied = -total_after_return
        if month in QUARTER_MONTHS and H.sum() > 0:
            t_next = glide.target_weights_for_year(year + 1).to_numpy() if month == 12 else target
            H, before, over = rb.quarterly_rebalance(H, t_next)
            if over[0]:
                risk_rows.append({"date": d, "risky_share_before": float(before[0])})
        total = float(H.sum())
        rows.append({
            "date": d, "age": glide.age_of(year), "retired": retired,
            "ret_before_flow": (total_after_return / prev_total - 1.0) if prev_total > 0 else 0.0,
            "flow": flow_applied, "total": total,
            "income_all": float(income.sum()), "income_bucket": float(income[0, rb.INC].sum()),
            "withdrawal": flow if retired and not dead_before(depleted_month, d) else 0.0,
        })
        wrows.append(dict(date=d, **dict(zip(config.ASSETS, (H[0] / total if total > 0 else H[0])))))
        prev_total = total

    monthly = pd.DataFrame(rows).set_index("date")
    weights = pd.DataFrame(wrows).set_index("date")
    risk_log = pd.DataFrame(risk_rows, columns=["date", "risky_share_before"])
    return BacktestResult(monthly, weights, risk_log, fallback, depleted_month, seed, H[0].copy())


def dead_before(depleted_month, d) -> bool:
    return depleted_month is not None and d > depleted_month
