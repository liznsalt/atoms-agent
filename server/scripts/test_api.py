"""API 层验证脚本：TestClient 跑 REST/SSE 全断言 + uvicorn 真实启动冒烟。

运行方式（cwd 必须是 server 目录）：
    set PYTHONDONTWRITEBYTECODE=1 && .venv/Scripts/python.exe scripts/test_api.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

DB_FILE = SERVER_DIR / ".tmp_test_api.db"

# 必须在 import app.* 之前设置（app.config 在 import 时固化环境变量）
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.as_posix()}"
os.environ.pop("LLM_API_KEY", None)  # 错误路径需要"未配置 key"

from fastapi.testclient import TestClient  # noqa: E402

import app.api.routes as routes  # noqa: E402
from app.main import app  # noqa: E402


def parse_sse(text: str) -> list[tuple[str, str]]:
    """解析 SSE 文本为 [(event, data)] 列表（忽略 ping 注释等行）。"""
    parsed: list[tuple[str, str]] = []
    event = ""
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event, data_lines
        if event or data_lines:
            parsed.append((event or "message", "\n".join(data_lines)))
        event, data_lines = "", []

    for line in text.splitlines():
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
        elif not line.strip():
            flush()
    flush()
    return parsed


def test_crud(client: TestClient) -> None:
    resp = client.post("/api/projects", json={"prompt": "做一个   待办事项应用，支持增删改查"})
    assert resp.status_code == 201, f"创建应 201: {resp.status_code} {resp.text}"
    created = resp.json()
    pid = created["id"]
    assert isinstance(pid, int)
    assert created["title"] == "做一个 待办事项应用，支持增删改查", created["title"]

    # 超 30 字符截断
    resp = client.post("/api/projects", json={"prompt": "需" * 40})
    assert resp.status_code == 201
    assert resp.json()["title"] == "需" * 30

    # prompt 必填非空
    assert client.post("/api/projects", json={"prompt": "   "}).status_code == 422
    assert client.post("/api/projects", json={}).status_code == 422

    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert any(p["id"] == pid for p in resp.json())

    resp = client.get(f"/api/projects/{pid}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["project"]["id"] == pid
    assert detail["messages"] == []
    assert detail["files"] == {}

    assert client.get("/api/projects/999999").status_code == 404

    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert client.delete(f"/api/projects/{pid}").status_code == 404
    print("PASS REST CRUD（201/压缩空白/30 字截断/422 空校验/列表/详情/204/404）")


def test_chat_error(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"prompt": "错误路径"}).json()["id"]

    resp = client.post(f"/api/projects/{pid}/chat", json={"message": "生成一个页面"})
    assert resp.status_code == 200, resp.text
    events = parse_sse(resp.text)
    error_data = next((d for e, d in events if e == "error"), None)
    assert error_data is not None, f"应含 error 事件: {events}"
    message = json.loads(error_data)["message"]
    assert "未配置" in message, message

    # 无脏数据：files 仍为空；messages 含 user 消息与 ⚠️ agent 消息
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["files"] == {}, detail["files"]
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "agent"], roles
    assert detail["messages"][1]["content"].startswith("⚠️ 生成失败：")
    assert "未配置" in detail["messages"][1]["content"]

    # message 必填非空；项目不存在 404
    assert client.post(f"/api/projects/{pid}/chat", json={"message": "  "}).status_code == 422
    assert client.post("/api/projects/999999/chat", json={"message": "x"}).status_code == 404
    print("PASS chat 错误路径（error 事件、files 无脏数据、user+⚠️agent 消息落库）")


def test_chat_success_and_preview(client: TestClient) -> int:
    pid = client.post("/api/projects", json={"prompt": "成功路径"}).json()["id"]

    def fake_run_generation(prompt, current_files, on_step, on_files, model=None):
        on_step("tool", "engineer", "保存 index.html")
        on_files({"index.html": "<h1>ok</h1>"})
        return {"summary": "替身总结：已保存 index.html", "files": {"index.html": "<h1>ok</h1>"}}

    original = routes.run_generation
    routes.run_generation = fake_run_generation
    try:
        resp = client.post(f"/api/projects/{pid}/chat", json={"message": "生成页面"})
    finally:
        routes.run_generation = original

    assert resp.status_code == 200, resp.text
    events = parse_sse(resp.text)
    assert [e for e, _ in events] == ["step", "files", "done"], events

    assert json.loads(events[0][1]) == {
        "kind": "tool",
        "agent": "engineer",
        "content": "保存 index.html",
    }
    assert json.loads(events[1][1]) == {"files": {"index.html": "<h1>ok</h1>"}}
    assert json.loads(events[2][1]) == {"summary": "替身总结：已保存 index.html"}

    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["files"] == {"index.html": "<h1>ok</h1>"}, "set_files 应落库"
    agent_messages = [m for m in detail["messages"] if m["role"] == "agent"]
    assert agent_messages[0]["content"] == "替身总结：已保存 index.html"
    steps = agent_messages[0]["steps"]
    assert steps and steps[0]["kind"] == "tool" and steps[0]["agent"] == "engineer"
    assert steps[0].get("ts"), "step 应带 iso 时间戳"

    # preview：有文件项目返回组装 HTML；不存在项目 404
    resp = client.get(f"/preview/{pid}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<h1>ok</h1>" in resp.text
    assert client.get("/preview/999999").status_code == 404
    print("PASS chat 成功路径（step/files/done 事件序、落库、agent steps）+ preview")
    return pid


def smoke_uvicorn(expected_project_id: int) -> None:
    """uvicorn 真实启动 + HTTP 请求 /api/health 与 /api/projects，验证后杀掉。"""
    port = 8765
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(SERVER_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        health = None
        deadline = time.time() + 30
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.communicate(timeout=5)[0]
                raise AssertionError(f"uvicorn 提前退出:\n{out!r}")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/health", timeout=2
                ) as r:
                    health = json.loads(r.read())
                break
            except Exception:
                time.sleep(0.3)
        assert health == {"ok": True}, f"health 响应异常: {health}"

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/projects", timeout=5
        ) as r:
            projects = json.loads(r.read())
        assert any(
            p["id"] == expected_project_id for p in projects
        ), f"跨进程应读到持久化数据: {projects}"
        print("PASS uvicorn 冒烟（/api/health ok、/api/projects 跨进程持久化）")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    if DB_FILE.exists():
        DB_FILE.unlink()

    tests = [test_crud, test_chat_error, test_chat_success_and_preview]
    failed = 0
    success_pid: int | None = None
    try:
        with TestClient(app) as client:  # with 触发 lifespan → init_db()
            for test in tests:
                try:
                    result = test(client)
                except AssertionError as exc:
                    failed += 1
                    print(f"FAIL {test.__name__}: {exc}")
                    if test is test_chat_success_and_preview:
                        success_pid = None
                else:
                    if result is not None:
                        success_pid = result

        if not failed and success_pid is not None:
            try:
                smoke_uvicorn(success_pid)
            except AssertionError as exc:
                failed += 1
                print(f"FAIL smoke_uvicorn: {exc}")
    finally:
        from app.db.db import engine

        engine.dispose()  # 释放连接池文件锁，Windows 下才能删除
        # Windows 下句柄释放可能有延迟（uvicorn 子进程/daemon 线程），重试删除
        for _ in range(10):
            if not DB_FILE.exists():
                break
            try:
                DB_FILE.unlink()  # 清理临时 db
                break
            except PermissionError:
                time.sleep(0.3)
        else:
            print(f"WARN: 临时 db 被占用，删除失败: {DB_FILE}")

    if failed:
        print(f"\n{failed} FAILED")
        sys.exit(1)
    print("\nALL PASS")


if __name__ == "__main__":
    main()
