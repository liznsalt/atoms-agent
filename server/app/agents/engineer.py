"""Engineer Agent：基于 deepagents 的 Web 应用生成智能体。

deepagents 0.7.19 真实 API（经源码确认）：
- ``create_deep_agent(model, tools, *, system_prompt, ...)`` 返回 LangGraph
  ``CompiledStateGraph``；model 接受 ``BaseChatModel`` 实例（原样透传）。
- 默认 StateBackend，文件经 agent 状态的 ``files`` key 管理；本项目不用内置
  文件工具落盘，而是注册自定义 ``save_file`` 工具直接写入内存 pending 字典。
- stream(stream_mode=["updates", "messages"])：
  * "messages" 产出 ``(message, metadata)``，AI 文本 chunk / ToolMessage；
  * "updates" 产出 ``{node: {"messages": [AIMessage(含完整 tool_calls), ...]}}``。
- 0.7.19 已无内置 todo 工具（源码 grep 确认），todo 事件留注释位退化处理。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from deepagents import create_deep_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph

from app.agents.llm import get_chat_model
from app.config import MAX_CONTEXT_CHARS

AGENT_NAME = "engineer"


class GenerationStopped(Exception):
    """用户主动停止：由上层置取消标志，流循环/回调检测后抛出以中断生成。"""

# 事件契约（对应 SSE step 事件的 kind 取值）：
#   "todo"    —— 计划/todo 更新（当前版本 deepagents 无内置 todo 工具，预留）
#   "tool"    —— 工具调用（如"保存文件 index.html"）
#   "message" —— AIMessage 文本增量（非空 chunk）
OnStep = Callable[[str, str, str], None]
OnFiles = Callable[[dict[str, str]], None]

ENGINEER_SYSTEM_PROMPT = """你是 Atoms 平台的 Engineer Agent，一名资深前端工程师，负责生成和迭代可直接在浏览器运行的 Web 应用。

## 输出规则
1. 生成自包含的纯前端 Web 应用：HTML/CSS/JS 分文件组织，如 index.html、style.css、app.js。
2. 样式可直接用 Tailwind CDN：<script src="https://cdn.tailwindcss.com"></script>，禁止使用构建工具、npm 或本地依赖。
3. 每个文件都必须调用 save_file 工具保存（不要使用任何其他文件写入工具），且必须是文件完整内容（禁止省略或占位符）；入口文件必须是 index.html。
4. 应用必须纯浏览器可用：状态数据放 localStorage，所有逻辑在前端完成，不要调用任何后端接口。

## 增量修改原则
- 当用户输入附带"当前文件集"时，只对需要改动的文件调用 save_file；未提及的文件会自动保留，无需重复保存。
- follow-up 修改（如"主题色改成绿色"）只改相关文件，不要重写无关文件。

## 汇报
- 全部文件保存完成后，用简短中文总结本次生成/修改了哪些文件、做了什么，供用户在聊天面板查看。"""


def build_engineer(
    model: Any | None = None,
    *,
    on_files: OnFiles | None = None,
    pending: dict[str, str] | None = None,
) -> CompiledStateGraph:
    """创建 Engineer Agent。

    Args:
        model: 模型实例（可注入测试替身）；None 时走 get_chat_model()。
        on_files: save_file 落盘回调（收到完整文件集快照）；默认 no-op。
        pending: save_file 的目标字典（闭包捕获）；默认新建空字典。

    Returns:
        deepagents CompiledStateGraph，已注册自定义 save_file 工具。
    """
    if model is None:
        model = get_chat_model()
    files: dict[str, str] = pending if pending is not None else {}
    notify: OnFiles = on_files if on_files is not None else (lambda _files: None)

    @tool
    def save_file(filename: str, content: str) -> str:
        """保存一个项目文件（已存在则整体覆盖），并即时推送最新文件集。

        Args:
            filename: 文件相对路径，如 index.html、style.css、app.js。
            content: 文件的完整内容。
        """
        files[filename] = content
        notify(dict(files))
        return f"已保存 {filename}（{len(content)} 字符）"

    return create_deep_agent(
        model=model,
        tools=[save_file],
        system_prompt=ENGINEER_SYSTEM_PROMPT,
    )


def run_generation(
    prompt: str,
    current_files: dict[str, str],
    on_step: OnStep,
    on_files: OnFiles,
    model: Any | None = None,
    should_cancel: Callable[[], bool] | None = None,
    history: str | None = None,
) -> dict[str, Any]:
    """执行一次生成/增量迭代任务。

    Args:
        prompt: 用户需求（首次生成或 follow-up）。
        current_files: 当前文件集（follow-up 时作为上下文拼入输入，增量修改）。
        on_step: 过程回调 on_step(kind, agent, content)，kind ∈ {"todo", "tool", "message"}。
        on_files: 文件集回调 on_step(files)，save_file 每次落盘后触发，可多次。
        model: 可选模型注入（测试替身）；None 时走 get_chat_model()。
        should_cancel: 协作式取消检查（Stop 提速关键）：流循环每收到一个 chunk
            就检查，取消延迟从"下一个回调"降到"下一个 chunk"（通常亚秒级）。
        history: 轻量对话上下文（此前轮次的需求与结论摘要，已截断）；None 表示无历史。

    Returns:
        {"summary": 最终 AIMessage 文本或合成总结, "files": 本次任务结束后的完整文件集}

    Raises:
        GenerationStopped: should_cancel 为真时尽早抛出，上层保留进度收尾。
        其他上游异常直接抛出（pending 仅为局部态，调用方不提交即无脏数据）。
    """
    pending = dict(current_files)
    agent = build_engineer(model, on_files=on_files, pending=pending)
    user_input = _compose_user_input(prompt, current_files, history)

    summary = ""
    for mode, chunk in agent.stream(
        {"messages": [HumanMessage(content=user_input)]},
        stream_mode=["updates", "messages"],
    ):
        if should_cancel is not None and should_cancel():
            raise GenerationStopped
        if mode == "messages":
            message, _metadata = chunk
            # AIMessageChunk 是 AIMessage 子类；流式文本 chunk 逐段转发
            if isinstance(message, AIMessage):
                text = _extract_text(message.content)
                if text:
                    on_step("message", AGENT_NAME, text)
        elif mode == "updates":
            # 完整消息（含 tool_calls）只经 updates 模式到达，取最后一条
            # 无工具调用的 AIMessage 文本作为 summary 候选
            summary = _handle_update(chunk, on_step) or summary

    if not summary:
        summary = _synthesize_summary(pending)
    return {"summary": summary, "files": pending}


def _handle_update(update: Any, on_step: OnStep) -> str:
    """解析 updates 模式的一个 chunk：发 tool/todo 步骤事件，返回 summary 候选文本。"""
    if not isinstance(update, dict):
        return ""
    candidate = ""
    for node_update in update.values():
        if not isinstance(node_update, dict):
            continue
        for message in node_update.get("messages") or []:
            if not isinstance(message, AIMessage):
                continue
            if message.tool_calls:
                for call in message.tool_calls:
                    kind, content = _describe_tool_call(call)
                    on_step(kind, AGENT_NAME, content)
            else:
                text = _extract_text(message.content)
                if text:
                    candidate = text
    return candidate


def _describe_tool_call(call: dict[str, Any]) -> tuple[str, str]:
    """把一个 tool_call 映射为 (kind, 展示文案)。

    todo 注释位：deepagents 0.7.19 已移除内置 todo 写入工具（源码确认无
    TodoWrite/write_todos），故当前只会产出 tool/message 两类事件；若未来
    版本恢复 todo 工具，下方按名称匹配即可自动映射为 kind="todo"。
    """
    name = str(call.get("name", ""))
    args = call.get("args") or {}
    if "todo" in name.lower():
        todos = args.get("todos", args)
        return "todo", f"更新计划：{todos}"
    if name == "save_file":
        return "tool", f"保存文件 {args.get('filename', '')}"
    return "tool", f"调用工具 {name}"


def _compose_user_input(
    prompt: str,
    current_files: dict[str, str],
    history: str | None = None,
) -> str:
    """组装单轮输入：轻量历史 + 需求 + 当前文件集（超限自动压缩）。

    上下文工程（压缩）策略：
    - 历史只注入摘要化的少量轮次（首条原始需求 + 最近两轮），单条截断，KB 级；
    - 文件集总量超过 MAX_CONTEXT_CHARS 时压缩：入口 index.html 全量保留，
      其余文件只保留头部并标注省略（截断文件本轮无需重写、保持原样）。
    """
    parts: list[str] = []
    if history:
        parts.append("## 此前对话（摘要，仅供理解上下文，本轮需求见文末）")
        parts.append(history)
        parts.append("")
    if not current_files:
        parts.append(f"{prompt}\n\n当前项目还没有任何文件，请从零开始生成完整应用。")
        return "\n".join(parts)
    parts.append(prompt)
    parts.append("")
    parts.append("当前文件集如下（遵循增量修改原则，只改需要改的文件，未提及的文件自动保留）：")
    parts.extend(_render_files(current_files))
    return "\n".join(parts)


# 压缩时非入口文件保留的头部字符数（足以看清结构与命名约定）
_FILE_PREVIEW_CHARS = 1500


def _render_files(current_files: dict[str, str]) -> list[str]:
    """渲染文件集；总量超限（MAX_CONTEXT_CHARS）时压缩非入口文件。"""
    total = sum(len(content) for content in current_files.values())
    lines: list[str] = []
    if total <= MAX_CONTEXT_CHARS:
        for name in sorted(current_files):
            lines.append(f"----- {name} -----")
            lines.append(current_files[name])
            lines.append(f"----- {name} 结束 -----")
        return lines
    # 上下文压缩：入口文件全量 + 其余文件头部预览，控制单轮输入规模
    lines.append(
        f"（注：文件集总量 {total} 字符超过上限 {MAX_CONTEXT_CHARS}，已压缩——"
        "仅 index.html 全量展示，其余文件保留开头部分。被截断的文件保持原样即可、"
        "不要重写；若确需修改被截断的文件，请输出基于现有结构的完整新内容。）"
    )
    for name in sorted(current_files):
        content = current_files[name]
        lines.append(f"----- {name} -----")
        if name == "index.html" or len(content) <= _FILE_PREVIEW_CHARS:
            lines.append(content)
        else:
            omitted = len(content) - _FILE_PREVIEW_CHARS
            lines.append(content[:_FILE_PREVIEW_CHARS])
            lines.append(f"……（中间省略 {omitted} 字符，此文件未变更时无需重写）")
        lines.append(f"----- {name} 结束 -----")
    return lines


def _extract_text(content: Any) -> str:
    """提取消息文本：兼容 str 与 content blocks 列表两种形态。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return ""


def _synthesize_summary(files: dict[str, str]) -> str:
    """模型未输出总结文本时的合成兜底。"""
    if files:
        return f"本次共保存 {len(files)} 个文件：{', '.join(sorted(files))}"
    return "本次未保存任何文件。"
