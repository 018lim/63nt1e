"""CLAUDE.md 5절: 받은 원본 데이터로 계산한 연도별 TR vs 공개값 (허용오차 config.VALID_TOL)."""
import pandas as pd
import pytest

import config

# VUSTX 1995 = 30.2%: 수정주가·배당 재투자 직접 계산·서드파티(30.21%)가 일치. 운용사 공식값은 미확인(확인되면 교체).
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


# TDF 대조 (CLAUDE.md 2.7): VTTVX 2021~2025 연도별 수익률, 출처 Yahoo Finance 성과 표(dividend.com 값과 일치).
# FFFDX와 VTTVX 2020년 이전은 운용사 공식값 미확인 -> 확인되면 추가.
@pytest.mark.parametrize("year,published", [(2021, 0.0980), (2022, -0.1555), (2023, 0.1455), (2024, 0.0944), (2025, 0.1460)])
def test_vttvx_matches_public_calendar_returns(year, published):
    assert annual_tr("VTTVX", year) == pytest.approx(published, abs=config.VALID_TOL)
