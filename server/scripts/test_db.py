"""数据库层临时验证脚本：两个不同 SQLite 连接串各跑一遍完整断言，证明仅改连接串即可切库。

运行方式（cwd 必须是 server 目录，保证相对路径行为可预期）：
    .venv/Scripts/python.exe scripts/test_db.py
"""

import importlib
import os
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

DB_FILES = [".tmp_test_db_a.db", ".tmp_test_db_b.db"]


def run_scenario(db_url: str) -> None:
    # 模拟"仅改连接串"的两次独立启动：设置 DATABASE_URL 后重载模块
    os.environ["DATABASE_URL"] = db_url

    import app.config as config

    importlib.reload(config)
    assert config.DATABASE_URL == db_url, f"DATABASE_URL not applied: {config.DATABASE_URL}"

    import app.db.db as db

    importlib.reload(db)

    import app.db.store as store

    importlib.reload(store)

    db.init_db()

    # --- 项目创建 ---
    p1 = store.create_project("测试")
    assert isinstance(p1["id"], int)
    assert p1["title"] == "测试"
    assert isinstance(p1["created_at"], str) and "T" in p1["created_at"]

    p2 = store.create_project("second")
    assert p2["id"] != p1["id"]

    # --- 消息 ---
    steps = [
        {"kind": "todo", "agent": "engineer", "content": "写 index.html", "ts": "2026-01-01T00:00:00"}
    ]
    m1 = store.add_message(p1["id"], "user", "做一个倒计时页面")
    m2 = store.add_message(p1["id"], "agent", "已完成", steps=steps)
    assert m1["project_id"] == p1["id"]
    assert m1["steps"] is None
    assert m2["steps"] == steps

    msgs = store.get_messages(p1["id"])
    assert len(msgs) == 2
    assert [m["id"] for m in msgs] == [m1["id"], m2["id"]]  # id 升序
    assert msgs[0]["role"] == "user" and msgs[1]["role"] == "agent"
    assert msgs[1]["content"] == "已完成"

    # --- 文件 upsert / 整体替换 ---
    files_v1 = {"index.html": "<html>v1</html>"}
    store.set_files(p1["id"], files_v1)
    assert store.get_files(p1["id"]) == files_v1

    files_v2 = {"index.html": "<html>v2</html>", "app.js": "console.log(1)"}
    store.set_files(p1["id"], files_v2)
    assert store.get_files(p1["id"]) == files_v2  # 整体替换，不是合并

    assert store.get_files(p2["id"]) == {}  # 无记录返回 {}

    # --- 查询 / 不存在 ---
    got = store.get_project(p1["id"])
    assert got == p1, f"create 与再读取序列化不一致: {got} != {p1}"
    assert store.get_project(999999) is None
    assert store.get_files(999999) == {}
    assert store.get_messages(999999) == []

    # --- 列表按 created_at 倒序 ---
    projects = store.list_projects()
    assert [p["id"] for p in projects] == [p2["id"], p1["id"]]

    # --- 删除（连带清掉消息与文件，不留脏数据）---
    assert store.delete_project(p1["id"]) is True
    assert store.delete_project(p1["id"]) is False
    assert store.get_project(p1["id"]) is None
    assert store.get_messages(p1["id"]) == []
    assert store.get_files(p1["id"]) == {}
    assert [p["id"] for p in store.list_projects()] == [p2["id"]]

    # 释放连接池，Windows 下才能删除 db 文件
    db.engine.dispose()


def main() -> None:
    for name in DB_FILES:
        path = SERVER_DIR / name
        if path.exists():
            path.unlink()
    try:
        for i, name in enumerate(DB_FILES, 1):
            url = f"sqlite:///./{name}"
            run_scenario(url)
            print(f"scenario {i} ({url}) PASS")
    finally:
        for name in DB_FILES:
            path = SERVER_DIR / name
            if path.exists():
                path.unlink()
    print("ALL PASS")


if __name__ == "__main__":
    main()
