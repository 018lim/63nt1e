"""매월·분기 규칙 (CLAUDE.md 2.3). 백테스트(경로 1개)와 몬테카를로(경로 N개)가 같은 함수를 쓴다.

보유액 H는 (경로 수, 7) 배열, 열 순서는 config.ASSETS. 마지막 열(cash)이 현금.
"""
import numpy as np

import config

CASH = config.ASSETS.index("cash")
NONCASH = [i for i, a in enumerate(config.ASSETS) if a != "cash"]
CG = [config.ASSETS.index(a) for a in config.CAPITAL_GAIN_ASSETS]
INC = [config.ASSETS.index(a) for a in config.INCOME_ASSETS]
RISKY = [config.ASSETS.index(a) for a in config.RISKY_ASSETS]


def apply_returns(H, price_ret, income_ret, income_to_cash=config.INCOME_TO_CASH):
    """① 그달 수익률 반영 ② 인컴 현금 입금.

    income_to_cash=True : 자산은 가격 성분으로만 변하고, 인컴(전월 말 보유액 x 인컴 수익률)은 현금으로 들어간다.
                          현금 자산 자체의 이자는 현금에 그대로 붙는다(가격 성분 0, 인컴 = 금리/12).
    income_to_cash=False: 자산을 TR(= 가격 + 인컴)로 굴린다(배당 재투자). 인컴은 지표 계산용으로만 반환.
    반환: (새 H, 자산별 인컴 금액 (경로, 7))
    """
    income = H * income_ret
    if income_to_cash:
        H_new = H * (1.0 + price_ret)
        H_new[:, CASH] += income.sum(axis=1)   # 현금 이자 포함 전체 인컴
    else:
        H_new = H * (1.0 + price_ret + income_ret)
    return H_new, income


def monthly_contribute(H, amount, target):
    """적립기 월간 처리: 납입금을 현금에 넣고, 현금 10%를 채운 뒤 남는 돈으로 부족한 자산만 매수. 팔지 않는다."""
    H = H.copy()
    H[:, CASH] += amount
    total = H.sum(axis=1)
    excess = np.maximum(H[:, CASH] - config.CASH_W * total, 0.0)

    deficit = np.maximum(target[NONCASH] * total[:, None] - H[:, NONCASH], 0.0)
    deficit_sum = deficit.sum(axis=1)
    w_noncash = target[NONCASH] / target[NONCASH].sum()

    buy = np.zeros_like(deficit)
    covered = excess <= deficit_sum
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(deficit_sum[:, None] > 0, deficit / deficit_sum[:, None], 0.0)
    buy[covered] = excess[covered, None] * share[covered]
    extra = excess[~covered] - deficit_sum[~covered]
    buy[~covered] = deficit[~covered] + extra[:, None] * w_noncash

    H[:, NONCASH] += buy
    H[:, CASH] -= buy.sum(axis=1)
    return H


def monthly_withdraw(H, amount):
    """인출기 월간 처리: 현금에서 먼저 차감 -> 모자라면 시세차익 자산(주식지수·장기채·금)을 보유 비중대로 매도.
    그래도 모자라면 마지막 수단으로 인컴 자산을 보유 비중대로 매도(규칙 예외, fallback 플래그로 반환).
    전체 평가액이 인출액보다 작으면 고갈: 전부 0으로 만들고 depleted=True.
    반환: (새 H, depleted (경로,), fallback_used (경로,))
    """
    H = H.copy()
    n = H.shape[0]
    depleted = H.sum(axis=1) < amount
    paid_cash = np.minimum(H[:, CASH], amount)
    H[:, CASH] -= paid_cash
    short = amount - paid_cash                     # 현금으로 못 낸 금액

    cg_tot = H[:, CG].sum(axis=1)
    sell_cg = np.minimum(short, cg_tot)
    with np.errstate(divide="ignore", invalid="ignore"):
        frac = np.where(cg_tot > 0, sell_cg / cg_tot, 0.0)
    H[:, CG] *= (1.0 - frac)[:, None]
    short = short - sell_cg

    fallback = (short > 1e-9) & ~depleted
    inc_tot = H[:, INC].sum(axis=1)
    sell_inc = np.minimum(short, inc_tot)
    with np.errstate(divide="ignore", invalid="ignore"):
        frac = np.where(inc_tot > 0, sell_inc / inc_tot, 0.0)
    H[:, INC] *= (1.0 - frac)[:, None]

    H[depleted] = 0.0
    return H, depleted, fallback


def risky_share(H):
    total = H.sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(total > 0, H[:, RISKY].sum(axis=1) / total, 0.0)


def quarterly_rebalance(H, target):
    """분기 말: 밴드 없이 7개 자산 전부를 목표 비중으로. 합계가 보존되므로 매도액 = 매수액.
    반환: (새 H, 리밸런싱 직전 위험자산 비중, 70% 초과 여부)"""
    before = risky_share(H)
    total = H.sum(axis=1)
    H_new = total[:, None] * target[None, :]
    return H_new, before, before > config.RISK_LIMIT
