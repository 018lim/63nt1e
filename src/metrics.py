"""성과 지표 (CLAUDE.md 2.9). 수익률 지표는 현금흐름 영향을 뺀 시간가중수익률(TWR) 기준."""
import numpy as np
import pandas as pd

import config


def twr_index(monthly_returns: pd.Series) -> pd.Series:
    return (1.0 + monthly_returns).cumprod()


def cagr(monthly_returns: pd.Series) -> float:
    n = len(monthly_returns)
    return float(twr_index(monthly_returns).iloc[-1] ** (12.0 / n) - 1.0)


def volatility(monthly_returns: pd.Series) -> float:
    return float(monthly_returns.std(ddof=1) * np.sqrt(12))


def drawdown(monthly_returns: pd.Series) -> pd.Series:
    idx = twr_index(monthly_returns)
    peak = np.maximum.accumulate(np.concatenate([[1.0], idx.to_numpy()]))[1:]
    return idx / peak - 1.0


def max_drawdown(monthly_returns: pd.Series) -> float:
    return float(drawdown(monthly_returns).min())


def recovery_months(monthly_returns: pd.Series):
    """최대낙폭 저점에서 직전 고점을 회복하기까지 걸린 개월 수. 끝까지 회복 못 하면 None."""
    idx = twr_index(monthly_returns)
    dd = drawdown(monthly_returns)
    trough = dd.idxmin()
    peak_val = idx[:trough].max() if len(idx[:trough]) else 1.0
    after = idx[trough:]
    rec = after[after >= peak_val]
    if rec.empty:
        return None
    return int(idx.index.get_loc(rec.index[0]) - idx.index.get_loc(trough))


def irr_annual(seed: float, flows: pd.Series, terminal: float) -> float:
    """돈가중 수익률(IRR): 시드(t0 유출), 월말 순흐름(납입 유출/인출 유입), 마지막 평가액(유입). 연율."""
    cf = np.concatenate([[-seed], -flows.to_numpy(), [0.0]])
    cf[-1] += terminal
    lo, hi = -0.05, 0.05
    f = lambda r: sum(c / (1 + r) ** t for t, c in enumerate(cf))
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return float((1 + (lo + hi) / 2) ** 12 - 1)


def summarize(monthly_returns: pd.Series) -> dict:
    return {"cagr": cagr(monthly_returns), "vol": volatility(monthly_returns),
            "mdd": max_drawdown(monthly_returns), "recovery_months": recovery_months(monthly_returns)}
