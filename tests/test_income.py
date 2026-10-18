"""인컴 검증 (CLAUDE.md 5절): 공개 연간 배당과 대조.

공개값 출처: dividendvision.com (SCHD, VNQ 연도별 주당 분배금 합계, 분할 반영).
 - 주당 합계는 yfinance 합계와 0.1% 이내여야 한다.
 - 연도별 인컴 수익률 = 월별 (분배금 / 전월 말 Close)의 합. 공개 합계 / 그해 전월 말 Close 평균과
   VALID_TOL_INCOME(0.3%p) 이내여야 한다. (분배 시점 가중 방식 차이만 남는다.)
한계: 공개값을 구한 구간은 ETF 시기뿐이다. 뮤추얼펀드 구간 인컴은 VEIPX 연차보고서 대조(test_splice)만 있다.
"""
import pandas as pd
import pytest

import config
from src import splice

PUBLIC = {
    ("SCHD", 2020): 0.67614, ("SCHD", 2021): 0.74974, ("SCHD", 2022): 0.85384, ("SCHD", 2023): 0.8864,
    ("VNQ", 2021): 2.9656, ("VNQ", 2022): 3.2261, ("VNQ", 2023): 3.4928, ("VNQ", 2024): 3.4335,
}


@pytest.fixture(scope="module")
def monthly():
    return {t: splice.monthly_from_yf(t) for t in ("SCHD", "VNQ")}


@pytest.mark.parametrize("ticker,year", sorted(PUBLIC))
def test_dividend_per_share_matches_public(monthly, ticker, year):
    f = monthly[ticker]
    assert f[f.index.year == year]["div"].sum() == pytest.approx(PUBLIC[(ticker, year)], rel=0.001)


@pytest.mark.parametrize("ticker,year", sorted(PUBLIC))
def test_annual_income_yield_matches_public(monthly, ticker, year):
    f = monthly[ticker]
    ours = f[f.index.year == year]["income"].sum()
    ref = PUBLIC[(ticker, year)] / f["close"].shift(1)[f.index.year == year].mean()
    assert ours == pytest.approx(ref, abs=config.VALID_TOL_INCOME)
