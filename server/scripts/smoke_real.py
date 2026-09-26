# -*- coding: utf-8 -*-
"""真实生成冒烟：带 key 环境下 chat SSE 应产生 step/files/done 事件。"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"


def post_json(path: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    p = post_json("/api/projects", {"prompt": "真实生成冒烟项目"})
    pid = p["id"]
    print(f"created project id={pid}")

    data = json.dumps({"message": "做一个 hello world 单页：标题 + 一段问候语，绿色按钮点击后弹出提示"}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/projects/{pid}/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events = []
    with urllib.request.urlopen(req, timeout=30) as resp:
        buf = b""
        while True:
            chunk = resp.read(1024)
            if not chunk:
                break
            buf += chunk
        text = buf.decode("utf-8")
        for block in text.replace("\r\n", "\n").split("\n\n"):
            ev, payload = None, None
            for line in block.splitlines():
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:"):
                    payload = line[5:].strip()
            if ev:
                events.append((ev, payload))

    kinds = []
    for ev, payload in events:
        kinds.append(ev)
        print("EVENT:", ev, "|", (payload or "")[:260])

    kinds_set = set(kinds)
    assert "error" not in kinds_set, f"LLM 调用报错: {[p for e, p in events if e == 'error']}"
    assert "done" in kinds_set, f"缺少 done 事件, got {kinds_set}"
    assert "files" in kinds_set, f"缺少 files 事件, got {kinds_set}"
    assert any(e == "step" for e in kinds), "缺少 step 事件"

    last_files = [json.loads(p) for e, p in events if e == "files"][-1]
    names = list(last_files.get("files", {}).keys())
    print("FILES:", names)
    assert any("index.html" in n for n in names), f"未见 index.html: {names}"
    print("REAL SMOKE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
