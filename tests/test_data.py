"""CLAUDE.md 5절: 받은 원본 데이터로 계산한 연도별 TR vs 공개값 (허용오차 config.VALID_TOL)."""
import pandas as pd
import pytest

import config

CASES = [
    ("VUSTX", 1995, 0.302), ("FRESX", 1996, 0.3626), ("FRESX", 2008, -0.3815),
    ("VEIPX", 2008, -0.3090), ("VFITX", 2008, 0.1335), ("TLT", 2008, 0.3394),
    ("SCHD", 2020, 0.1503), ("IEI", 2022, -0.0951), ("VNQ", 2022, -0.2625),
]


def annual_tr(ticker: str, year: int) -> float:
    d = pd.read_csv(config.RAW_DIR / f"yf_{ticker}.csv", index_col=0, parse_dates=True)["Adj Close"]
    end = d[d.index.year == year].iloc[-1]
    prev = d[d.index.year == year - 1]
    start = prev.iloc[-1] if len(prev) else d[d.index.year == year].iloc[0]
    return end / start - 1


@pytest.mark.parametrize("ticker,year,published", CASES)
def test_annual_tr_matches_published(ticker, year, published):
    assert annual_tr(ticker, year) == pytest.approx(published, abs=config.VALID_TOL)
