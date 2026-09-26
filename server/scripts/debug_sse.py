# -*- coding: utf-8 -*-
"""SSE raw 流调试：逐 chunk 打印服务端原始输出，定位事件丢失。"""
import json
import sys
import time
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
    p = post_json("/api/projects", {"prompt": "SSE raw 调试项目"})
    pid = p["id"]
    print(f"project id={pid}", flush=True)

    data = json.dumps({"message": "做一个显示当前时间的页面"}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/projects/{pid}/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=30) as resp:
        print("headers:", dict(resp.headers), flush=True)
        while True:
            chunk = resp.read(512)
            if not chunk:
                break
            elapsed = time.time() - t0
            print(f"[{elapsed:7.2f}s] {chunk.decode('utf-8', 'replace')!r}", flush=True)
    print("STREAM END", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
