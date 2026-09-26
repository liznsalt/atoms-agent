"""验证 preview/assemble.py：内联成功、CDN 保留、无相对引用残留。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.preview.assemble import assemble_html  # noqa: E402

FILES = {
    "index.html": (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        '<link rel="stylesheet" href="style.css">\n'
        '<link href="./style.css" rel="stylesheet">\n'
        '<script src="https://cdn.tailwindcss.com"></script>\n'
        "</head>\n"
        "<body>\n"
        "<h1>你好，Atoms</h1>\n"
        '<script src="app.js"></script>\n'
        '<script src="missing.js"></script>\n'
        "</body>\n"
        "</html>\n"
    ),
    "style.css": "body { background: #eef2ff; }\nh1 { color: #4338ca; }\n",
    "app.js": "console.log('app loaded');\ndocument.querySelector('h1').textContent += '!';\n",
    "notes.txt": "与 HTML 无关的文件，不应被内联",
}

OUT = assemble_html(FILES)


def test_css_inlined() -> None:
    assert "<style>" in OUT, "应有 <style> 内联"
    assert "body { background: #eef2ff; }" in OUT, "style.css 内容应内联"
    assert 'href="style.css"' not in OUT, "相对 CSS 引用应被替换"
    assert 'rel="stylesheet"' not in OUT, "link 标签应被整体替换"


def test_js_inlined() -> None:
    assert "console.log('app loaded');" in OUT, "app.js 内容应内联"
    assert 'src="app.js"' not in OUT, "相对 JS 引用应被替换"


def test_cdn_preserved() -> None:
    assert '<script src="https://cdn.tailwindcss.com"></script>' in OUT, "Tailwind CDN 外链必须保留"


def test_missing_preserved() -> None:
    assert '<script src="missing.js"></script>' in OUT, "files 中不存在的引用应保持原样"


def test_no_relative_refs_left() -> None:
    leftovers = re.findall(r'(?:href|src)=["\'](?:\./|\x2F)?(?:style\.css|app\.js)["\']', OUT)
    assert leftovers == [], f"相对引用残留: {leftovers}"


def test_charset_present() -> None:
    assert re.search(r"<meta\b[^>]*charset\s*=\s*[\"']?utf-8", OUT, re.IGNORECASE), "必须含 utf-8 charset"


def test_placeholder_when_no_index() -> None:
    page = assemble_html({"style.css": "body{}"})
    assert "应用尚未生成" in page
    assert "现有文件：style.css" in page
    assert 'charset="utf-8"' in page


def test_content_not_corrupted() -> None:
    assert "你好，Atoms" in OUT, "正文内容不应被破坏"


def main() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    if failed:
        print(f"\n{failed} FAILED")
        sys.exit(1)
    print(f"\nALL PASS ({len(tests)} tests)")


if __name__ == "__main__":
    main()
