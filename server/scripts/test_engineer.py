"""验证 agents/engineer.py：fake 模型注入 run_generation 全流程跑通。

说明：FakeMessagesListChatModel 未实现 bind_tools（BaseChatModel 默认抛
NotImplementedError，langchain create_agent 会调用 bind_tools），故子类化
覆盖 bind_tools 后注入——deepagents 本身接受 BaseChatModel 实例。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app.agents.engineer import build_engineer, run_generation  # noqa: E402


class SaveFileArgs(BaseModel):
    """save_file 工具参数（tool_calls.args 经 pydantic 构造）。"""

    filename: str
    content: str


def tool_call(filename: str, content: str, call_id: str) -> dict[str, Any]:
    return {
        "name": "save_file",
        "args": SaveFileArgs(filename=filename, content=content).model_dump(),
        "id": call_id,
        "type": "tool_call",
    }


class FakeToolCallingModel(FakeMessagesListChatModel):
    """补齐 bind_tools 的 fake 模型（按序返回 responses）。"""

    def bind_tools(self, tools: Any, *, tool_choice: Any = None, **kwargs: Any) -> "FakeToolCallingModel":
        return self


def test_build_engineer_constructs() -> None:
    fake = FakeToolCallingModel(responses=[AIMessage(content="ok")])
    agent = build_engineer(fake)
    assert agent is not None
    assert hasattr(agent, "stream")
    print("PASS build_engineer 构造成功")


def test_run_generation_from_scratch() -> None:
    fake = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    tool_call("index.html", "<h1>Todo App</h1>", "call_1"),
                    tool_call("app.js", "console.log('ready');", "call_2"),
                ],
            ),
            AIMessage(content="已生成待办应用首页与脚本。"),
        ]
    )
    steps: list[tuple[str, str, str]] = []
    files_events: list[dict[str, str]] = []

    result = run_generation(
        prompt="生成一个待办事项应用",
        current_files={},
        on_step=lambda kind, agent, content: steps.append((kind, agent, content)),
        on_files=lambda files: files_events.append(files),
        model=fake,
    )

    kinds = [k for k, _, _ in steps]
    assert "tool" in kinds, f"应有 tool 事件: {steps}"
    assert "message" in kinds, f"应有 message 事件: {steps}"
    assert any(
        kind == "tool" and "保存文件 index.html" in content for kind, _, content in steps
    ), f"应包含保存 index.html 步骤: {steps}"
    assert all(agent == "engineer" for _, agent, _ in steps), "agent 名应为 engineer"

    assert files_events, "on_files 应至少收到一次"
    assert files_events[-1] == {
        "index.html": "<h1>Todo App</h1>",
        "app.js": "console.log('ready');",
    }, f"最终文件集不符: {files_events[-1]}"

    assert result["files"]["index.html"] == "<h1>Todo App</h1>"
    assert result["files"]["app.js"] == "console.log('ready');"
    assert result["summary"] == "已生成待办应用首页与脚本。", f"summary 不符: {result['summary']!r}"
    print("PASS run_generation 从零生成（tool/message 事件、on_files、summary、files）")


def test_run_generation_incremental() -> None:
    current = {
        "index.html": "<h1>旧标题</h1>",
        "style.css": "h1 { color: black; }",
    }
    fake = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[tool_call("style.css", "h1 { color: green; }", "call_1")],
            ),
            AIMessage(content="已把主题色改为绿色，仅改动 style.css。"),
        ]
    )
    files_events: list[dict[str, str]] = []
    result = run_generation(
        prompt="主题色改绿色",
        current_files=current,
        on_step=lambda *_: None,
        on_files=lambda files: files_events.append(files),
        model=fake,
    )

    assert result["files"]["index.html"] == "<h1>旧标题</h1>", "未提及的文件必须保持不变"
    assert result["files"]["style.css"] == "h1 { color: green; }", "提及的文件应被更新"
    assert files_events, "on_files 应有回调"
    assert files_events[0]["index.html"] == "<h1>旧标题</h1>", "pending 应初始化自 current_files"
    assert result["summary"] == "已把主题色改为绿色，仅改动 style.css。"
    print("PASS run_generation 增量迭代（旧文件保留、新文件更新）")


def test_summary_fallback_synthesized() -> None:
    fake = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[tool_call("index.html", "<p>hello</p>", "call_1")],
            ),
            AIMessage(content=""),  # 最终无文本 → 走合成总结
        ]
    )
    result = run_generation(
        prompt="生成页面",
        current_files={},
        on_step=lambda *_: None,
        on_files=lambda *_: None,
        model=fake,
    )
    assert result["summary"], "summary 兜底不应为空"
    assert "index.html" in result["summary"], f"合成总结应列出文件: {result['summary']!r}"
    print("PASS run_generation summary 合成兜底")


def main() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    if failed:
        print(f"\n{failed} FAILED")
        sys.exit(1)
    print(f"\nALL PASS ({len(tests)} tests)")


if __name__ == "__main__":
    main()
