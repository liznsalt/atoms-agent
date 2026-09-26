"""预览组装：把项目文件集组装为自包含 HTML（供 /preview/{id} 输出到 iframe）。

规则：
- 取 ``files["index.html"]`` 为入口（缺失则生成提示页）；
- ``<link rel="stylesheet" href="相对路径.css">`` → ``<style>`` 内联（仅当该文件存在）；
- ``<script src="相对路径.js"></script>`` → 内联 ``<script>``（仅当该文件存在）；
- ``https://`` 等外链保持原样（如 Tailwind CDN）；
- 确保含 ``<meta charset="utf-8">``。
"""

from __future__ import annotations

import re
from html import escape
from typing import Any

_LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_SCRIPT_SRC_RE = re.compile(r"<script\b([^>]*)>\s*</script>", re.IGNORECASE)
_ATTR_RE = re.compile(r"([\w:-]+)\s*=\s*(\"[^\"]*\"|'[^']*')", re.IGNORECASE)
_META_CHARSET_RE = re.compile(r"<meta\b[^>]*charset", re.IGNORECASE)
_HEAD_OPEN_RE = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
_LEADING_DOT_SLASH_RE = re.compile(r"^[./]+")

_EXTERNAL_PREFIXES = ("http://", "https://", "//", "data:")


def assemble_html(files: dict[str, str], *, design_mode: bool = False) -> str:
    """纯函数：文件集 → 自包含 HTML 字符串。

    design_mode=True 时额外注入元素选择器（hover 高亮 + 点选上报父页面）。
    无论何种模式都注入运行时错误捕获（Issue 自修复数据源）。
    """
    html = files.get("index.html")
    if not isinstance(html, str) or not html.strip():
        html = _placeholder_page(files)
    html = _inline_stylesheets(html, files)
    html = _inline_scripts(html, files)
    html = _ensure_charset(html)
    return _inject_bridge(html, design_mode)


def _inject_bridge(html: str, design_mode: bool) -> str:
    """把桥接脚本插到 <head> 最前：错误监听必须先于应用脚本注册，
    才能捕获同步运行错误（未定义函数等）。"""
    script = _bridge_script(design_mode)
    head = _HEAD_OPEN_RE.search(html)
    if head:
        return f"{html[: head.end()]}\n{script}{html[head.end() :]}"
    return f"{script}\n{html}"


def _bridge_script(design_mode: bool) -> str:
    """注入到预览尾部的桥接脚本：错误捕获（Issue 自修复）+ 可选元素选择器。

    - window.onerror / unhandledrejection → postMessage 给父页面（去重、限量）
    - design_mode：hover 描边高亮，click 拦截并上报元素描述（父页面回填需求）
    """
    picker = """
  var pickStyle = document.createElement('style');
  pickStyle.textContent = '[data-atoms-hover]{outline:2px solid #34d399 !important;outline-offset:2px !important;cursor:crosshair !important}';
  document.head.appendChild(pickStyle);
  var lastHover = null;
  document.addEventListener('mouseover', function (e) {
    if (lastHover) lastHover.removeAttribute('data-atoms-hover');
    lastHover = e.target;
    lastHover.setAttribute('data-atoms-hover', '');
  }, true);
  document.addEventListener('click', function (e) {
    e.preventDefault(); e.stopPropagation();
    var el = e.target;
    var desc = '<' + el.tagName.toLowerCase();
    if (el.id) desc += ' id="' + el.id + '"';
    if (el.className && typeof el.className === 'string' && el.className.trim()) {
      desc += ' class="' + el.className.trim().split(/\\s+/).slice(0, 3).join(' ') + '"';
    }
    desc += '>';
    parent.postMessage({ type: 'atoms-pick', description: desc,
      text: (el.textContent || '').trim().slice(0, 40) }, '*');
  }, true);
""" if design_mode else ""
    return (
        "<script>(function(){\n"
        "  var seen = {};\n"
        "  function report(message, source) {\n"
        "    message = String(message).slice(0, 300);\n"
        "    var key = message + '@' + source;\n"
        "    if (seen[key]) return;\n"
        "    seen[key] = 1;\n"
        "    if (Object.keys(seen).length > 5) return;\n"
        "    try { parent.postMessage({ type: 'atoms-issue', message: message, source: source }, '*'); } catch (e) {}\n"
        "  }\n"
        "  window.addEventListener('error', function (e) {\n"
        "    report(e.message, (e.filename || '') + ':' + (e.lineno || 0));\n"
        "  });\n"
        "  window.addEventListener('unhandledrejection', function (e) {\n"
        "    report('未处理的 Promise 异常: ' + (e.reason && e.reason.message ? e.reason.message : e.reason), 'promise');\n"
        "  });\n"
        + picker +
        "})();</script>"
    )


def _inline_stylesheets(html: str, files: dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        tag = match.group(0)
        attrs = _parse_attrs(tag)
        if attrs.get("rel", "").lower() != "stylesheet":
            return tag
        path = _resolve_relative(attrs.get("href", ""), files)
        if path is None:
            return tag
        return f"<style>\n{files[path]}\n</style>"

    return _LINK_TAG_RE.sub(_replace, html)


def _inline_scripts(html: str, files: dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        attrs = _parse_attrs(match.group(1))
        path = _resolve_relative(attrs.pop("src", ""), files)
        if path is None:
            return match.group(0)
        extra = "".join(f' {name}="{value}"' for name, value in attrs.items())
        return f"<script{extra}>\n{files[path]}\n</script>"

    return _SCRIPT_SRC_RE.sub(_replace, html)


def _parse_attrs(source: str) -> dict[str, str]:
    """解析标签（或属性串）中的 key="value" / key='value' 对。"""
    attrs: dict[str, str] = {}
    for match in _ATTR_RE.finditer(source):
        attrs[match.group(1).lower()] = match.group(2)[1:-1]
    return attrs


def _resolve_relative(url: str, files: dict[str, str]) -> str | None:
    """相对路径归一化后查 files；外链（http/https/data 等）返回 None 表示不内联。"""
    url = url.strip()
    if not url or url.startswith(_EXTERNAL_PREFIXES) or url.startswith("#"):
        return None
    candidates = [url]
    stripped = _LEADING_DOT_SLASH_RE.sub("", url)
    if stripped != url:
        candidates.append(stripped)
    for candidate in candidates:
        if candidate in files and isinstance(files[candidate], str):
            return candidate
    return None


def _ensure_charset(html: str) -> str:
    if _META_CHARSET_RE.search(html):
        return html
    meta = '<meta charset="utf-8">'
    head = _HEAD_OPEN_RE.search(html)
    if head:
        return f"{html[: head.end()]}\n{meta}{html[head.end() :]}"
    return f"{meta}\n{html}"


def _placeholder_page(files: dict[str, Any]) -> str:
    names = escape(", ".join(sorted(str(name) for name in files))) or "（无任何文件）"
    return (
        '<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n'
        "<title>预览未就绪</title>\n</head>\n"
        '<body style="font-family: system-ui, sans-serif; display: flex; '
        "min-height: 100vh; align-items: center; justify-content: center; "
        'background: #f5f5f5; color: #666; margin: 0;">\n'
        '<div style="text-align: center;">\n'
        "<h1 style=\"font-size: 22px;\">应用尚未生成</h1>\n"
        "<p>当前项目还没有 index.html，等待 Engineer Agent 生成后即可预览。</p>\n"
        f'<p style="color: #999; font-size: 14px;">现有文件：{names}</p>\n'
        "</div>\n</body>\n</html>"
    )
