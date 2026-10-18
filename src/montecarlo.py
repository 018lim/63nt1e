"""몬테카를로 (인출기): 12개월 블록 부트스트랩, 고갈 나이 기록 (CLAUDE.md 2.8).

시작: 백테스트 마지막 월말(2026-09)의 잔고·비중 -> 다음 달부터 MC_MAX_AGE(100세)가 되는 해 12월까지.
(가격 성분, 인컴 성분) 7개 자산 벡터와 벤치마크 TR을 '같은 월 번호'로 함께 뽑는다.
나이 = 달력 연도 - 1965. N세 잔여자산 = N세가 되는 해 12월 말 평가액, 고갈 = 그 해(포함)까지 한 번이라도 인출 불능.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

import config
from src import a_value as av
from src import benchmarks, glide
from src import rebalance as rb


@dataclass
class MCResult:
    years: np.ndarray                 # 연말 기록 연도 (2026 ~ 2065)
    depletion_year: dict              # 이름 -> (P,) 고갈 연도 (미고갈 0)
    year_end_value: dict              # 이름 -> (P, 연수) 연말 평가액(달러)
    income_all: np.ndarray            # (P, 연수) 연간 인컴(전략, 달러)
    income_bucket: np.ndarray         # (P, 연수) 인컴 버킷 3개 자산 인컴
    withdrawal: np.ndarray            # (연수,) 연간 인출액(달러)
    a_value: np.ndarray               # (연수,) 해당 연도 A값(원)
    fx: float
    block: int
    paths: int
    fallback_paths: int = 0           # 인컴 자산까지 팔아야 했던(규칙 예외) 경로 수


def block_bootstrap_indices(n_obs: int, n_months: int, paths: int, block: int, rng) -> np.ndarray:
    """(paths, n_months) 월 번호. 블록 시작을 [0, n_obs-block]에서 균등 추출(순환 없음)."""
    n_blocks = -(-n_months // block)
    starts = rng.integers(0, n_obs - block + 1, size=(paths, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(paths, -1)
    return idx[:, :n_months]


def run_montecarlo(tr, inc, price, start_holdings, bench_start_values, last_date,
                   paths=config.MC_PATHS, block=config.MC_BLOCK, seed=config.MC_SEED,
                   fx=config.FX_FIXED, income_to_cash=config.INCOME_TO_CASH,
                   income_fallback=True) -> MCResult:
    first = pd.Timestamp(last_date) + pd.offsets.MonthEnd(1)
    end_year = config.BIRTH_YEAR + config.MC_MAX_AGE
    months = pd.date_range(first, f"{end_year}-12-31", freq="ME")
    T = len(months)
    years = np.arange(first.year, end_year + 1)

    rng = np.random.default_rng(seed)
    idx = block_bootstrap_indices(len(tr), T, paths, block, rng)
    price_np, inc_np = price[config.ASSETS].to_numpy(), inc[config.ASSETS].to_numpy()
    bench = benchmarks.benchmark_returns(tr)
    bench_np = bench.to_numpy()

    H = np.tile(np.asarray(start_holdings, float), (paths, 1))
    names = ["strategy"] + list(bench.columns)
    V = {n: (np.full(paths, bench_start_values[n]) if n != "strategy" else None) for n in names}
    dep_year = {n: np.zeros(paths, int) for n in names}
    ye_value = {n: np.zeros((paths, len(years))) for n in names}
    fallback_any = np.zeros(paths, bool)
    inc_all = np.zeros((paths, len(years))); inc_bucket = np.zeros_like(inc_all)
    wd_year = np.zeros(len(years)); a_year = np.array([av.a_value(int(y)) for y in years])

    for t, d in enumerate(months):
        y, m = d.year, d.month
        yi = y - years[0]
        amount = av.a_value(y) * config.WITHDRAW_MULT / fx
        wd_year[yi] += amount
        target = glide.target_weights_for_year(y).to_numpy()

        # --- 전략
        H, income = rb.apply_returns(H, price_np[idx[:, t]], inc_np[idx[:, t]], income_to_cash)
        inc_all[:, yi] += income.sum(axis=1); inc_bucket[:, yi] += income[:, rb.INC].sum(axis=1)
        H, depleted, fb = rb.monthly_withdraw(H, amount, income_fallback)
        fallback_any |= fb
        new = depleted & (dep_year["strategy"] == 0)
        dep_year["strategy"][new] = y
        if m in (3, 6, 9, 12):
            t_next = glide.target_weights_for_year(y + 1).to_numpy() if m == 12 else target
            H, _, _ = rb.quarterly_rebalance(H, t_next)
        if m == 12:
            ye_value["strategy"][:, yi] = H.sum(axis=1)

        # --- 벤치마크 (같은 월 번호)
        for j, n in enumerate(bench.columns):
            v = V[n] * (1.0 + bench_np[idx[:, t], j]) - amount
            dead = v <= 0
            new = dead & (dep_year[n] == 0)
            dep_year[n][new] = y
            V[n] = np.where(dead, 0.0, v)
            if m == 12:
                ye_value[n][:, yi] = V[n]

    return MCResult(years, dep_year, ye_value, inc_all, inc_bucket, wd_year, a_year, fx, block, paths, int(fallback_any.sum()))


def depletion_prob(res: MCResult, name: str, age: int) -> float:
    """age세가 되는 해(포함)까지 고갈된 경로 비율."""
    dy = res.depletion_year[name]
    return float(((dy > 0) & (dy <= config.BIRTH_YEAR + age)).mean())


def residual_quantiles(res: MCResult, name: str, age: int, qs=(0.1, 0.5, 0.9)) -> dict:
    col = config.BIRTH_YEAR + age - res.years[0]
    v = res.year_end_value[name][:, col]
    return {q: float(np.quantile(v, q)) for q in qs}
