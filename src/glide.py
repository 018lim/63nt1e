"""글라이드패스: 연도 -> 7개 leaf 목표 비중 (CLAUDE.md 2.2)."""
import pandas as pd

import config


def age_of(year: int) -> int:
    """달력 연도 기준 정수 나이."""
    return year - config.BIRTH_YEAR


def inner_weights(age: int) -> tuple[float, float]:
    """버킷 내부 비율 (x, y). x='6' 자리(주식형), y='3' 자리(채권). 90세 이후에도 같은 공식."""
    t = age - config.START_AGE
    x = 0.6 - config.GLIDE_STEP * t
    y = 0.3 + config.GLIDE_STEP * t
    return x, y


def target_weights(age: int) -> pd.Series:
    """나이 -> leaf 목표 비중. 합계 1."""
    x, y = inner_weights(age)
    g, i = x, y                      # 대분류: 자본이득 G, 인컴 I
    alt = 0.1                        # 버킷 내부 '1' 자리(대체자산)
    w = {
        "equity": g * x, "long_bond": g * y, "gold": g * alt,
        "dividend": i * x, "mid_bond": i * y, "reit": i * alt,
        "cash": config.CASH_W,
    }
    return pd.Series(w)[config.ASSETS]


def target_weights_for_year(year: int) -> pd.Series:
    """해당 연도 동안 쓰는 목표 비중. 연도 안에서는 바뀌지 않는다."""
    return target_weights(age_of(year))


def risky_share(weights: pd.Series) -> float:
    return float(weights[config.RISKY_ASSETS].sum())
