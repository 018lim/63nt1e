"""대시보드를 어디서나 열 수 있게 묶는다 -> site/ (Actions·빌드 없이 정적 호스팅 가능).

만드는 것:
  site/index.html            대시보드 (data.js, 로고를 같은 폴더에서 읽음) -> 폴더째 Netlify·Vercel·Cloudflare Pages 등에 올리면 된다
  site/data.js, site/63nt1e_logo.svg
  site/63nt1e-dashboard.html 파일 하나로 끝나는 버전 (데이터·로고를 안에 넣음) -> 이메일 첨부나 더블클릭으로 바로 열림
실행: python -m src.build_site   (python -m src.export 다음에)
"""
import base64
import shutil

import config

SITE = config.ROOT / "site"
LOGO_REL = "../assets/63nt1e_logo.svg"


def build() -> dict:
    SITE.mkdir(exist_ok=True)
    html = (config.DASHBOARD_DIR / "index.html").read_text(encoding="utf-8")
    data_js = (config.DASHBOARD_DIR / "data.js").read_text(encoding="utf-8")
    logo = (config.ROOT / "assets" / "63nt1e_logo.svg").read_bytes()
    assert LOGO_REL in html and '<script src="data.js"></script>' in html, "대시보드 HTML 구조가 바뀌었습니다"

    # 1) 폴더째 올리는 버전: 로고 경로만 같은 폴더로
    (SITE / "index.html").write_text(html.replace(LOGO_REL, "63nt1e_logo.svg"), encoding="utf-8")
    (SITE / "data.js").write_text(data_js, encoding="utf-8")
    shutil.copyfile(config.ROOT / "assets" / "63nt1e_logo.svg", SITE / "63nt1e_logo.svg")

    # 2) 파일 하나짜리 버전: 데이터와 로고를 HTML 안에 넣는다
    uri = "data:image/svg+xml;base64," + base64.b64encode(logo).decode("ascii")
    single = html.replace(LOGO_REL, uri).replace('<script src="data.js"></script>', "<script>\n" + data_js + "</script>")
    (SITE / "63nt1e-dashboard.html").write_text(single, encoding="utf-8")
    return {"index": SITE / "index.html", "single": SITE / "63nt1e-dashboard.html", "single_kb": len(single.encode("utf-8")) / 1024}


def main():
    r = build()
    print(f"site/ 생성: index.html (폴더째 호스팅), 63nt1e-dashboard.html ({r['single_kb']:.0f} KB, 파일 하나)")


if __name__ == "__main__":
    main()
