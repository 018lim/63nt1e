"""CLAUDE.md 5절: 받은 원본 데이터로 계산한 연도별 TR vs 공개값 (허용오차 config.VALID_TOL)."""
import pandas as pd
import pytest

import config

CASES = [
    ("VUSTX", 1995, 0.3105), ("FRESX", 1996, 0.3626), ("FRESX", 2008, -0.3815),
    ("VEIPX", 2008, -0.3090), ("VFITX", 2008, 0.1335), ("TLT", 2008, 0.3394),
    ("SCHD", 2020, 0.1503), ("IEI", 2022, -0.0951), ("VNQ", 2022, -0.2625),
]
# 계산값 30.2%는 서드파티(alphacubator.com)의 30.21%와 일치, 명세의 31.05%와는 0.83%p 차이.
# 공개값 쪽 오류 가능성 -> 사용자 확인 전까지 규칙을 바꾸지 않고 xfail로 기록한다.
KNOWN_MISMATCH = {("VUSTX", 1995): "명세 공개값 31.05% vs 원본 계산 30.2% (운용사 공식값 확인 필요)"}


def annual_tr(ticker: str, year: int) -> float:
    d = pd.read_csv(config.RAW_DIR / f"yf_{ticker}.csv", index_col=0, parse_dates=True)["Adj Close"]
    end = d[d.index.year == year].iloc[-1]
    prev = d[d.index.year == year - 1]
    start = prev.iloc[-1] if len(prev) else d[d.index.year == year].iloc[0]
    return end / start - 1


@pytest.mark.parametrize("ticker,year,published", CASES)
def test_annual_tr_matches_published(ticker, year, published):
    if (ticker, year) in KNOWN_MISMATCH:
        pytest.xfail(KNOWN_MISMATCH[(ticker, year)])
    assert annual_tr(ticker, year) == pytest.approx(published, abs=config.VALID_TOL)
