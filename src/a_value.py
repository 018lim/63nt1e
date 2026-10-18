"""A값 시계열 (CLAUDE.md 2.4). 현재는 적용 A값(3년 평균)을 쓴다 (⚑ 단년 값 확보 시 data/raw 파일만 교체).

미래(공표 이후) 연도는 1995~마지막 공표 연도의 연평균 증가율(CAGR)로 연장한다.
"""
import pandas as pd

import config

FILE = config.RAW_DIR / "a_value_applied.csv"
CAGR_FROM = 1995


def load_published() -> pd.Series:
    df = pd.read_csv(FILE, comment="#")
    return df.set_index("year")["a_value_won"].astype(float)


def cagr(published: pd.Series | None = None) -> float:
    s = load_published() if published is None else published
    last = int(s.index.max())
    return (s[last] / s[CAGR_FROM]) ** (1 / (last - CAGR_FROM)) - 1


def a_value(year: int, published: pd.Series | None = None) -> float:
    """해당 연도 A값(원). 공표 이후 연도는 CAGR로 연장."""
    s = load_published() if published is None else published
    last = int(s.index.max())
    if year <= last:
        return float(s[year])
    return float(s[last] * (1 + cagr(s)) ** (year - last))
