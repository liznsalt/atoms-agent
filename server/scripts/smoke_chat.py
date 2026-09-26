# -*- coding: utf-8 -*-
"""冒烟：创建项目 → chat SSE → 应收到 error(未配置 key) 或 step/done 事件"""
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
    p = post_json("/api/projects", {"prompt": "curl 冒烟验证项目"})
    pid = p["id"]
    print(f"created project id={pid} title={p['title']!r}")

    data = json.dumps({"message": "做一个 hello world 页面"}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/projects/{pid}/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events = []
    with urllib.request.urlopen(req, timeout=30) as resp:
        print("content-type:", resp.headers.get("content-type"))
        buf = b""
        while True:
            chunk = resp.read(1024)
            if not chunk:
                break
            buf += chunk
        text = buf.decode("utf-8")
        # 解析 SSE：event: x\ndata: y
        for block in text.split("\n\n"):
            ev, payload = None, None
            for line in block.splitlines():
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:"):
                    payload = line[5:].strip()
            if ev:
                events.append((ev, payload))
    for ev, payload in events:
        print("EVENT:", ev, "|", (payload or "")[:200])
    kinds = {ev for ev, _ in events}
    assert "error" in kinds, f"expected error event (no LLM key), got {kinds}"
    assert "done" not in kinds, "unexpected done"
    print("SMOKE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
