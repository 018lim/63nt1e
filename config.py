"""63NT1E 전체 파라미터. 코드에서 숫자를 직접 쓰지 말고 여기서 가져온다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
DASHBOARD_DIR = ROOT / "dashboard"

# --- 시나리오 ---
START = "1995-01"; RETIRE = "2026-01"; START_AGE = 30
BIRTH_YEAR = 1965           # 나이 = 달력 연도 - BIRTH_YEAR (정수)
SEED_DATE = "1994-12"       # 시드는 1994-12 말 종가로 투입
SEED_MULT = 16              # 시드 = 1995년 A값 x 16
CONTRIB_MULT = 1 / 3; WITHDRAW_MULT = 2 / 3
FX_FIXED = 1300             # KRW/USD, 결과 비율과 무관

# --- 전략 ---
GLIDE_STEP = 0.005          # 연 0.5%p
CASH_W = 0.10
RISK_LIMIT = 0.70           # 초과 시 로그만 기록
INCOME_TO_CASH = True       # False면 TR 재투자 모드 (인컴 검증 지연 시 대체)
GOLD_FEE_ADJ = False

# --- 검증 ---
VALID_TOL = 0.005           # 연도별 TR 검증 허용오차 (0.5%p)
VALID_TOL_INCOME = 0.003    # 연도별 배당 수익률 검증 허용오차 (0.3%p)

# --- 몬테카를로 ---
MC_PATHS = 10_000; MC_BLOCK = 12; MC_MAX_AGE = 100; MC_SEED = 631
LIFE_DEFAULT = 90
LIFE_MALE = 86.3; LIFE_FEMALE = 90.7   # 보험개발원 제10회 경험생명표 (2024)

# --- 자산 (leaf 7개, 순서 고정) ---
ASSETS = ["equity", "long_bond", "gold", "dividend", "mid_bond", "reit", "cash"]
CAPITAL_GAIN_ASSETS = ["equity", "long_bond", "gold"]   # 인출기 월간 매도 대상
INCOME_ASSETS = ["dividend", "mid_bond", "reit"]
RISKY_ASSETS = ["equity", "gold", "dividend", "reit"]

# 대리 자산 -> 실제 ETF 이어붙이기 (ETF 수익률 사용 시작월)
PROXY = {"equity": "VFINX", "long_bond": "VUSTX", "gold": "GOLD_SPOT",
         "dividend": "VEIPX", "mid_bond": "VFITX", "reit": "FRESX", "cash": "TB3MS"}
ETF = {"long_bond": ("TLT", "2002-08"), "gold": ("GLD", "2004-12"),
       "dividend": ("SCHD", "2011-11"), "mid_bond": ("IEI", "2007-02"),
       "reit": ("VNQ", "2004-10")}

# 벤치마크 구성 (TDF는 1996-11 FFFDX, 2003-11 VTTVX부터)
BENCH_TICKERS = ["VBMFX", "FFFDX", "VTTVX"]
TDF_SWITCH = {"FFFDX": "1996-11", "VTTVX": "2003-11"}
