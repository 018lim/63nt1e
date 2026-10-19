import re

import config
from src import build_site


def test_site_files_are_self_contained():
    r = build_site.build()
    idx = r["index"].read_text(encoding="utf-8")
    single = r["single"].read_text(encoding="utf-8")
    assert "../assets" not in idx and 'src="63nt1e_logo.svg"' in idx and '<script src="data.js"></script>' in idx
    assert (build_site.SITE / "data.js").exists() and (build_site.SITE / "63nt1e_logo.svg").exists()
    # 파일 하나짜리 버전은 바깥 파일을 읽지 않는다 (외부 src 없음, 데이터 내장)
    assert '<script src=' not in single and "window.DATA = " in single and 'src="data:image/svg+xml;base64,' in single
    assert not re.search(r'src="(?!data:)[^"]+\.(js|svg|png)"', single)
