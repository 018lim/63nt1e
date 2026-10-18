"""벤치마크 (CLAUDE.md 2.7): 전략과 같은 시드·납입·인출. TR 기준(배당 재투자), 매월 비중 복귀.

비중이 고정이고 매월 복귀하므로 포트폴리오 수익률은 구성 수익률의 가중합이다.
인출은 보유 비중대로 매도한 뒤 비중으로 복귀하는 것과 같다 (가치 기준 동일).
"""
import numpy as np
import pandas as pd

import config


def benchmark_returns(tr: pd.DataFrame) -> pd.DataFrame:
    """월별 TR 표(splice 출력)에서 벤치마크 월 수익률 4개."""
    return pd.DataFrame({
        "60/40": 0.6 * tr["equity"] + 0.4 * tr["vbmfx"],
        "stock100": tr["equity"],
        "cash100": tr["cash"],
        "tdf": tr["tdf"],
    })


def simulate(returns: np.ndarray, flows: np.ndarray, seed: float):
    """returns: (T, P) 월 수익률, flows: (T,) 월말 순현금흐름(+납입, -인출), seed: 시작 금액.
    반환: values (T, P) 월말 평가액(현금흐름 반영 후), depleted_at (P,) 고갈된 월 인덱스(없으면 -1)."""
    T, P = returns.shape
    v = np.full(P, float(seed))
    out = np.zeros((T, P))
    depleted_at = np.full(P, -1)
    for t in range(T):
        v = v * (1.0 + returns[t]) + flows[t]
        dead = v <= 0
        newly = dead & (depleted_at < 0)
        depleted_at[newly] = t
        v = np.where(dead, 0.0, v)
        out[t] = v
    return out, depleted_at
