"""reports/results.json 의 숫자로 README 6절 결과표와 설명을 채운다 (손으로 옮기지 않기 위함).

실행: python -m src.readme_fill   (먼저 python -m src.report)
"""
import json
import re

import config
from src import a_value as av

README = config.ROOT / "README.md"
NAMES = ["63nt1e", "tdf", "60/40", "stock100", "cash100"]


def pct(x, d=2):
    return f"{x * 100:.{d}f}%"


def build_section(r: dict) -> str:
    acc = r["accumulation"]
    mc = {(m["name"], m["age"]): m for m in r["mc"]}
    mc_names = {"63nt1e": "strategy", "tdf": "tdf", "60/40": "60/40", "stock100": "stock100", "cash100": "cash100"}
    cov = r["coverage"]

    def row(label, f):
        return "| " + label + " | " + " | ".join(f(n) for n in NAMES) + " |"

    lines = [
        "| 지표 | 63nt1e | TDF | 60/40 | 주식 100% | 현금 100% |",
        "|---|---|---|---|---|---|",
        row("연평균 수익률 (시간가중)", lambda n: pct(acc[n]["cagr"])),
        row("변동성 (연)", lambda n: pct(acc[n]["vol"])),
        row("수익 ÷ 변동성", lambda n: f"{acc[n]['return_per_vol']:.2f}"),
        row("샤프 비율 (현금 대비)", lambda n: "–" if n == "cash100" else f"{acc[n]['sharpe']:.2f}"),
        row("최대낙폭", lambda n: pct(acc[n]["mdd"])),
        row("61세 적립금 (A값 배수)", lambda n: f"{acc[n]['balance_a_multiple']:.1f}"),
        "| 은퇴 시점 인컴 커버리지 (보유 자산 전체의 이자·배당 ÷ 인출액) | " + " | ".join(
            [pct(cov["retire_all"], 1), "–", pct(cov["bench_retire"]["60/40"], 1), pct(cov["bench_retire"]["stock100"], 1), pct(cov["bench_retire"]["cash100"], 1)]) + " |",
        "| └ 인컴 버킷 3개 자산(배당성장·중기채·리츠)만 | " + pct(cov["retire_bucket"], 1) + " | – | – | – | – |",
        row("90세까지 고갈 확률", lambda n: pct(mc[(mc_names[n], 90)]["depletion_prob"])),
        row("100세까지 고갈 확률", lambda n: pct(mc[(mc_names[n], 100)]["depletion_prob"])),
        row("90세 잔여자산 중앙값 (A값 배수)", lambda n: f"{mc[(mc_names[n], 90)]['median_a_mult']:.1f}"),
        row("90세 잔여자산 하위 10% (A값 배수)", lambda n: f"{mc[(mc_names[n], 90)]['p10_a_mult']:.1f}"),
    ]
    b6 = r["block6"]["strategy"]
    base = {a: mc[("strategy", a)]["depletion_prob"] for a in (90, 100)}
    alt = r["income_to_cash_false"]
    a_base, a_alt = acc["63nt1e"], alt["accumulation_63nt1e"]
    strict = r["strict_no_income_sale"]["strategy"]
    notes = f"""
적립기 지표는 1995-01~2025-12, 몬테카를로는 2026-09 말 잔고에서 시작해 100세까지 10,000개 경로(12개월 블록, 시드 {config.MC_SEED})입니다. 잔여자산은 해당 연도 A값의 배수로 표시했습니다. TDF는 Fidelity Freedom 2020(1996-11~2003-10)을 Vanguard Target Retirement 2025(2003-11~)로 이은 값입니다(5절). 벤치마크는 배당 재투자(총수익) 방식이며, 인컴 커버리지는 보유 자산이 낸 이자·배당을 따로 합산한 참고값입니다(TDF는 분배금에 자본이득이 섞여 있어 계산하지 않았습니다).

**있는 그대로 읽으면**
- 63nt1e는 변동성({pct(acc['63nt1e']['vol'])})과 최대낙폭({pct(acc['63nt1e']['mdd'])})이 현금 100%를 제외한 비교 대상 중 가장 작고 수익 ÷ 변동성이 가장 높습니다. 대신 연평균 수익률과 61세 적립금은 60/40과 주식 100%보다 낮습니다.
- 90세까지 고갈 확률은 60/40보다 높고({pct(base[90])} vs {pct(mc[('60/40', 90)]['depletion_prob'])}), 100세에서는 격차가 더 벌어집니다({pct(base[100])} vs {pct(mc[('60/40', 100)]['depletion_prob'])}). 90세 잔여자산 중앙값도 60/40의 절반 이하입니다({mc[('strategy', 90)]['median_a_mult']:.1f}A vs {mc[('60/40', 90)]['median_a_mult']:.1f}A). 위험자산을 36%까지 줄이는 글라이드패스의 대가입니다.
- 주식 100%의 고갈 확률이 가장 낮은 것은 1995~2026년이 미국 주식에 유리한 구간이고 부트스트랩이 그 구간에서 뽑기 때문입니다.
- TDF는 같은 기간 63nt1e와 비슷한 수익률이지만 낙폭이 크고 고갈 확률이 높게 나왔습니다.

**민감도**
- 몬테카를로 블록 길이: 6개월 블록이면 90세 고갈 확률 {pct(b6['90'])}, 100세 {pct(b6['100'])}로, 12개월 블록({pct(base[90])}, {pct(base[100])})과 차이가 있습니다. 절대값은 작지만 블록 길이에 민감합니다.
- 인컴 처리 방식: 인컴을 현금으로 쌓는 기본 방식과 재투자 방식(`INCOME_TO_CASH=False`)의 결과가 거의 같습니다. 연평균 수익률 {pct(a_base['cagr'])} vs {pct(a_alt['cagr'])}, 61세 적립금 {a_base['balance_a_multiple']:.1f}A vs {a_alt['balance_a_multiple']:.1f}A, 90세 고갈 확률 {pct(base[90])} vs {pct(alt['depletion_90']['strategy'])}. 인컴 분류 방식에 결론이 민감하지 않습니다.
- 인출 규칙 해석: 현금과 시세차익 자산으로 인출액을 못 낼 때 마지막 수단으로 인컴 자산을 파는 경로가 몬테카를로에서 {r['mc_fallback_paths']['base']:,}개(전체의 {r['mc_fallback_paths']['base'] / config.MC_PATHS * 100:.1f}%) 있었습니다. 이를 고갈로 보는 엄격한 해석에서는 90세 고갈 확률이 {pct(strict['90'])}, 100세가 {pct(strict['100'])}입니다.
"""
    return "\n".join(lines) + "\n" + notes


def build_rolling(r: dict) -> str:
    from src import rolling
    b = r["rolling15"]
    st, names = b["stats"], rolling.NAMES
    img = config.REPORTS_DIR / "rolling_15y.png"
    rolling.plot_block(b, img)
    L = rolling.LABELS
    a_mult = b["start_value"] * config.FX_FIXED / av.a_value(2026)
    lines = [
        "### 은퇴 시점별 15년 인출 결과 (롤링 분석)",
        "",
        f"{b['months'][0]}부터 {b['months'][-1]}까지 매월 은퇴했다고 가정하고(시작 월 {b['n_starts']}개, 15년을 채울 수 있는 마지막 시작 월까지), 모든 전략이 같은 시작 자산 {a_mult:.1f}A에서 15년 동안 인출했을 때 남은 돈입니다. "
        f"인출액은 월 A값(2026년)의 2/3로 시작해 매년 {rolling.WD_GROWTH * 100:.2f}%씩 늘어납니다. 63nt1e는 61세 비중으로 시작해 기존 규칙(글라이드, 분기 리밸런싱, 인출 순서)을 그대로 쓰고, 수익은 재투자(`INCOME_TO_CASH=False`)합니다.",
        "",
        "![은퇴 시점별 15년 뒤 잔액 비율](reports/rolling_15y.png)",
        "",
        "가로축은 은퇴(인출 시작) 시점, 세로축은 15년 뒤 계좌에 남은 돈이 시작 자산의 몇 %인지입니다. 100%선 위면 15년 동안 생활비를 쓰고도 시작 자산 이상이 남은 것입니다(명목 기준).",
        "",
        "| 전략 | 최악 | 하위 10% | 중앙값 | 최선 | 바닥난 시작 월 수 | 최악이었던 은퇴 시점 |",
        "|---|---|---|---|---|---|---|",
    ]
    for n in names:
        s = st[n]
        lines.append(f"| {L[n]} | {s['worst']:.1f}% | {s['p10']:.1f}% | {s['median']:.1f}% | {s['best']:.1f}% | {s['depleted_starts']} | {s['worst_month']} |")
    def cmp(key, label):
        hi = [L[n] for n in names if n != "63nt1e" and st[n][key] > st["63nt1e"][key]]
        return f"{label}: " + ("63nt1e가 비교 대상 중 가장 높습니다" if not hi else "63nt1e보다 높은 전략은 " + ", ".join(hi))
    lines += [
        "",
        "- " + cmp("worst", "최악") + f"({st['63nt1e']['worst']:.1f}%, {st['63nt1e']['worst_month']} 은퇴). " + cmp("p10", "하위 10%") + ". " + cmp("median", "중앙값") + ". " + cmp("best", "최선") + ".",
        f"- 최악이었던 은퇴 시점은 전략마다 다릅니다: 63nt1e {st['63nt1e']['worst_month']}, 60/40 {st['60/40']['worst_month']}, 주식 100% {st['stock100']['worst_month']}, TDF {st['tdf']['worst_month']}.",
        f"- 한계: 인접한 시작 월은 거의 같은 구간을 겹쳐 쓰고 데이터가 31년뿐이라, {b['n_starts']}개 시작 월은 독립된 {b['n_starts']}개 사례가 아닙니다. 잔액 비율은 물가·A값 보정이 없는 명목 값입니다.",
    ]
    return "\n".join(lines) + "\n"


def main():
    r = json.loads((config.REPORTS_DIR / "results.json").read_text(encoding="utf-8"))
    text = README.read_text(encoding="utf-8")
    start = text.index("## 6. 결과")
    end = text.index("## 7. 상담에서는")
    section = "## 6. 결과\n\n<!-- 아래는 python -m src.report 와 python -m src.readme_fill 이 results.json 에서 생성한 값입니다 -->\n\n" + build_section(r) + "\n" + build_rolling(r) + "\n---\n\n"
    text = text[:start] + section + text[end:]
    README.write_text(text, encoding="utf-8")
    print("README 6절 갱신 완료")


if __name__ == "__main__":
    main()
