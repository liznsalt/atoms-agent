"""REST + SSE 路由：项目 CRUD、对话式流式生成（SSE）、预览页输出。

契约见 .trae/specs/implement-atoms-demo/spec.md「二、前后端交互契约」。
"""

from __future__ import annotations

import json
import os
import threading
import time
import zipfile
import io
from collections.abc import Iterator
from datetime import datetime, timezone
from queue import Queue
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, field_validator
from sse_starlette.sse import EventSourceResponse

from app.agents.engineer import GenerationStopped, run_generation
from app.auth import (
    SESSION_COOKIE,
    create_session_token,
    current_user,
    hash_password,
    verify_password,
)
from app.db import store
from app.preview.assemble import assemble_html

api_router = APIRouter(prefix="/api")
preview_router = APIRouter()  # /preview/{id} 按 spec 不带 /api 前缀


# ---------- 认证（Task 13）----------


class RegisterRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or len(value) > 120:
            raise ValueError("邮箱格式不正确")
        return value

    @field_validator("password")
    @classmethod
    def _valid_password(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError("密码至少 6 位")
        return value


def _session_response(user: dict, response: Response) -> dict:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user["id"]),
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )
    return {"id": user["id"], "email": user["email"]}


@api_router.post("/auth/register")
def register(body: RegisterRequest, response: Response) -> dict:
    user = store.create_user(body.email, hash_password(body.password))
    if user is None:
        raise HTTPException(status_code=409, detail="该邮箱已注册")
    return _session_response(user, response)


@api_router.post("/auth/login")
def login(body: RegisterRequest, response: Response) -> dict:
    """登录只校验凭据（复用 RegisterRequest 的格式校验）。"""
    record = store.get_user_by_email(body.email)
    if record is None or not verify_password(body.password, record["password_hash"]):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    return _session_response({"id": record["id"], "email": record["email"]}, response)


@api_router.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@api_router.get("/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return {"id": user["id"], "email": user["email"]}


# ---------- 项目（全部登录鉴权 + owner 隔离）----------


class ProjectCreateRequest(BaseModel):
    """POST /api/projects 请求体。"""

    prompt: str

    @field_validator("prompt")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt 不能为空")
        return value


class ChatRequest(BaseModel):
    """POST /api/projects/{id}/chat 请求体。"""

    message: str

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message 不能为空")
        return value


class ShareRequest(BaseModel):
    """POST /api/projects/{id}/share 请求体。"""

    enabled: bool


def _owned_project(project_id: int, user: dict) -> dict:
    """取当前用户可见的项目（自己的或无主演示项目），否则 404。"""
    project = store.get_project(project_id, owner_id=user["id"])
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@api_router.post("/projects", status_code=201)
def create_project(
    body: ProjectCreateRequest, user: dict = Depends(current_user)
) -> dict:
    """创建项目：title 取 prompt 压缩空白后前 30 字符。"""
    title = " ".join(body.prompt.split())[:30]
    project = store.create_project(title, owner_id=user["id"])
    return {"id": project["id"], "title": project["title"]}


@api_router.get("/projects")
def list_projects(user: dict = Depends(current_user)) -> list[dict]:
    return store.list_projects(user["id"])


@api_router.get("/projects/{project_id}")
def get_project(project_id: int, user: dict = Depends(current_user)) -> dict:
    _owned_project(project_id, user)
    return {
        "project": store.get_project(project_id),
        "messages": store.get_messages(project_id),
        "files": store.get_files(project_id),
        "versions": store.list_versions(project_id),
    }


@api_router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, user: dict = Depends(current_user)) -> None:
    if store.get_project(project_id, owner_id=user["id"]) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not store.delete_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")


# ---------- 项目事件总线：活跃生成直播 + 空闲连接 hub（sync 实时通知） ----------

_runs: dict[int, dict[str, Any]] = {}
_run_lock = threading.Lock()
# 空闲订阅：页面挂着等该项目变更（多设备实时同步的数据通道）
_hubs: dict[int, set[Queue]] = {}
# 每条 SSE 流的结束哨兵（广播 done/stopped/error 后送各订阅队列）
_STREAM_END = object()

# 全局生成并发池：serverless 实例资源有限，超过上限的生成排队等待（事件广播排队位次）
_MAX_GEN = int(os.getenv("MAX_CONCURRENT_GENERATIONS", "3"))
_gen_slots = threading.BoundedSemaphore(_MAX_GEN)
_waiting = 0
_waiting_lock = threading.Lock()


def _broadcast(ctx: dict[str, Any], event: str, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False)
    for queue in list(ctx["queues"]):
        queue.put({"event": event, "data": data})


def _finish_run(ctx: dict[str, Any], event: str, payload: dict[str, Any]) -> None:
    """结束广播：结束事件送达所有订阅者后，各流送哨兵收尾。"""
    _broadcast(ctx, event, payload)
    for queue in list(ctx["queues"]):
        queue.put(_STREAM_END)


def _notify_project(project_id: int, reason: str, running: bool) -> None:
    """通知项目的空闲订阅连接（另一台设备的页面）：有变更，拉最新数据。"""
    data = json.dumps({"reason": reason, "running": running}, ensure_ascii=False)
    with _run_lock:
        queues = list(_hubs.get(project_id, ()))
    for queue in queues:
        queue.put({"event": "sync", "data": data})


@api_router.post("/projects/{project_id}/stop")
def stop_generation(project_id: int, user: dict = Depends(current_user)) -> dict:
    if store.get_project(project_id, owner_id=user["id"]) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    with _run_lock:
        ctx = _runs.get(project_id)
        if ctx is not None:
            ctx["cancel"].set()
    return {"stopping": ctx is not None}


def _consume(queue: Queue) -> Iterator[dict[str, str]]:
    """SSE 生成器：消费一条订阅队列直到哨兵。"""
    while True:
        item = queue.get()
        if item is _STREAM_END:
            break
        yield item


def _subscribe_run(ctx: dict[str, Any]) -> tuple[list[dict[str, str]], Queue]:
    """快照当前活跃生成（排队位次 + 已发生步骤 + 最新文件）并注册订阅，原子完成。"""
    snapshot: list[dict[str, str]] = []
    if ctx.get("queued"):
        snapshot.append(
            {
                "event": "queue",
                "data": json.dumps(
                    {"position": ctx["queued"], "max": _MAX_GEN}, ensure_ascii=False
                ),
            }
        )
    snapshot.extend(
        {
            "event": "step",
            "data": json.dumps(
                {"kind": s["kind"], "agent": s["agent"], "content": s["content"]},
                ensure_ascii=False,
            ),
        }
        for s in ctx["steps"]
    )
    pending_text = "".join(ctx["message_buf"])
    if pending_text:
        snapshot.append(
            {
                "event": "step",
                "data": json.dumps(
                    {"kind": "message", "agent": "engineer", "content": pending_text},
                    ensure_ascii=False,
                ),
            }
        )
    if ctx["latest_files"] != ctx["base_files"]:
        snapshot.append(
            {
                "event": "files",
                "data": json.dumps({"files": ctx["latest_files"]}, ensure_ascii=False),
            }
        )
    queue: Queue = Queue()
    ctx["queues"].add(queue)
    return snapshot, queue


@api_router.get("/projects/{project_id}/events")
def project_events(project_id: int, user: dict = Depends(current_user)) -> EventSourceResponse:
    """项目事件长连接：有活跃生成 → 重放+直播；空闲 → 挂住等待 sync 通知（多设备实时同步）。"""
    if store.get_project(project_id, owner_id=user["id"]) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return EventSourceResponse(_events_stream(project_id))


def _events_stream(project_id: int) -> Iterator[dict[str, str]]:
    """一条长连接的完整生命周期：

    1. 有活跃生成 → 重放快照 + 直播直到本轮结束（done/stopped/error）
    2. 回到空闲 → 挂入项目 hub 等待 sync 事件（新消息/新生成/回滚/分享），
       sse-starlette 周期 ping 保活；另一设备发起生成时本连接收到 sync，
       客户端断开重连即进入直播。连接由客户端离开页面时断开（GeneratorExit 清理）。
    """
    while True:
        with _run_lock:
            ctx = _runs.get(project_id)
            if ctx is not None:
                snapshot, queue = _subscribe_run(ctx)
        if ctx is None:
            break
        yield from snapshot
        yield from _consume(queue)  # 直到本轮结束哨兵
        # 本轮结束：回到循环头，若队列已自动开启下一轮则继续直播，否则转空闲 hub

    idle_queue: Queue = Queue()
    with _run_lock:
        _hubs.setdefault(project_id, set()).add(idle_queue)
    try:
        while True:
            item = idle_queue.get()  # 挂住等待；sse-starlette 的 ping 帧维持连接
            if item is _STREAM_END:
                break
            yield item  # sync 事件
    finally:
        with _run_lock:
            queues = _hubs.get(project_id)
            if queues is not None:
                queues.discard(idle_queue)
                if not queues:
                    _hubs.pop(project_id, None)


def _recent_history(project_id: int) -> str | None:
    """轻量对话上下文：首条原始需求 + 最近两轮（user/agent 各截断）。

    上下文压缩的一环：以 KB 级摘要代替全量历史注入，配合文件集超限裁剪，
    控制单轮输入规模；本轮消息在调用前已落库为末位，这里取[:-1]排除。
    """
    messages = store.get_messages(project_id)
    prior = messages[:-1] if messages else []
    if not prior:
        return None

    def _fmt(m: dict) -> str:
        limit = 200 if m["role"] == "user" else 400
        text = " ".join(str(m["content"]).split())  # 压平换行与连续空白
        clipped = text[:limit] + ("…" if len(text) > limit else "")
        return f"{'用户' if m['role'] == 'user' else '工程师'}：{clipped}"

    lines: list[str] = []
    first_user = next((m for m in prior if m["role"] == "user"), None)
    recent = prior[-4:]  # 最近两轮（user + agent 各一条）
    if first_user is not None and first_user not in recent:
        text = " ".join(str(first_user["content"]).split())[:300]
        lines.append(f"最初需求：{text}")
    lines.extend(_fmt(m) for m in recent)
    return "\n".join(lines) if lines else None


@api_router.post("/projects/{project_id}/chat")
def chat(
    project_id: int, body: ChatRequest, user: dict = Depends(current_user)
) -> EventSourceResponse:
    """对话式生成：SSE 推送 queue/step/files/done/stopped/error 事件（spec 契约）。"""
    if store.get_project(project_id, owner_id=user["id"]) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    store.add_message(project_id, "user", body.message)
    # 通知该项目的空闲长连接（另一设备）：有新消息且生成开始，拉取并进入直播
    _notify_project(project_id, "chat_start", running=True)
    current_files = store.get_files(project_id)

    # 活跃生成上下文：取消标志 + 过程累积 + 订阅队列（chat 自身是首个订阅者；
    # 任意设备经 GET /events 订阅，同一轮生成多处直播）
    queue: Queue = Queue()
    ctx: dict[str, Any] = {
        "cancel": threading.Event(),
        "steps": [],
        "message_buf": [],
        "latest_files": dict(current_files),
        "base_files": current_files,
        "queues": {queue},
        "queued": 0,
    }
    with _run_lock:
        _runs[project_id] = ctx

    steps: list[dict[str, Any]] = ctx["steps"]
    message_buf: list[str] = ctx["message_buf"]
    latest_files: dict[str, str] = ctx["latest_files"]
    cancel: threading.Event = ctx["cancel"]

    def _check_cancel() -> None:
        if cancel.is_set():
            raise GenerationStopped

    def _append_step(kind: str, agent: str, content: str) -> None:
        steps.append(
            {
                "kind": kind,
                "agent": agent,
                "content": content,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )

    def on_step(kind: str, agent: str, content: str) -> None:
        _check_cancel()  # message chunk 频率高，取消延迟≈一个 token
        if kind == "message":
            # 逐 token 流式下发（打字机效果），但落库缓冲合并为一条
            message_buf.append(content)
        else:
            _append_step(kind, agent, content)
        _broadcast(ctx, "step", {"kind": kind, "agent": agent, "content": content})

    def flush_message_step() -> None:
        if message_buf:
            _append_step("message", "engineer", "".join(message_buf))
            message_buf.clear()

    def on_files(files: dict[str, str]) -> None:
        _check_cancel()
        latest_files.update(files)
        _broadcast(ctx, "files", {"files": files})

    def _acquire_slot() -> None:
        """并发池：有空槽立即开跑；否则排队等待（位次广播给订阅者），排队中可被 Stop 取消。"""
        global _waiting
        if _gen_slots.acquire(blocking=False):
            ctx["_slot_held"] = True
            return
        with _waiting_lock:
            _waiting += 1
            position = _waiting
        ctx["queued"] = position
        _broadcast(ctx, "queue", {"position": position, "max": _MAX_GEN})
        deadline = time.monotonic() + 900  # 15 分钟兜底，防永久滞留
        try:
            while not _gen_slots.acquire(timeout=5):
                _check_cancel()  # 排队期间用户点 Stop：立即退出而非等到获得槽位
                if time.monotonic() > deadline:
                    raise TimeoutError("生成排队超时（并发池繁忙），请稍后重试")
        finally:
            with _waiting_lock:
                _waiting -= 1
        ctx["queued"] = 0
        _broadcast(ctx, "queue", {"position": 0, "max": _MAX_GEN})
        ctx["_slot_held"] = True

    def run() -> None:
        try:
            _acquire_slot()
            result = run_generation(
                body.message,
                current_files,
                on_step,
                on_files,
                should_cancel=cancel.is_set,
                history=_recent_history(project_id),
            )
            flush_message_step()  # 合并的 message 落库
            # 原子提交：仅成功才落库；失败路径 pending 不进库，无脏数据
            store.set_files(project_id, result["files"])
            store.add_message(project_id, "agent", result["summary"], steps=steps)
            # 版本快照：每次生成成功自动存（label 取总结前 60 字符）
            label = result["summary"].strip()[:60] or body.message.strip()[:60]
            store.create_version(project_id, label, result["files"])
            _finish_run(ctx, "done", {"summary": result["summary"]})
        except GenerationStopped:
            # Stop 保留进度：已写入的文件落库 + 版本快照 + 系统消息
            flush_message_step()
            store.set_files(project_id, latest_files)
            store.add_message(project_id, "agent", "⏹ 已停止：已保存的文件已保留", steps=steps)
            if latest_files != current_files:
                store.create_version(project_id, "⏹ 已停止（进度保留）", latest_files)
            _finish_run(ctx, "stopped", {"message": "已停止，已完成的修改已保留"})
        except Exception as exc:
            store.add_message(project_id, "agent", f"⚠️ 生成失败：{exc}")
            _finish_run(ctx, "error", {"message": str(exc)})
        finally:
            if ctx.get("_slot_held"):
                _gen_slots.release()
            with _run_lock:
                if _runs.get(project_id) is ctx:
                    del _runs[project_id]
            # 本轮结束：通知空闲长连接拉取最终态
            _notify_project(project_id, "gen_end", running=False)

    threading.Thread(target=run, daemon=True).start()
    return EventSourceResponse(_consume(queue))


@preview_router.get("/preview/{project_id}")
def preview(project_id: int, design: int = 0) -> HTMLResponse:
    """项目文件集组装为自包含 HTML（供 iframe sandbox 加载）。

    ?design=1 开启 Design Mode：注入元素选择器（点选回填需求输入框）。
    """
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return HTMLResponse(assemble_html(store.get_files(project_id), design_mode=bool(design)))


# ---------- P1：版本快照与回滚 ----------


@api_router.post("/projects/{project_id}/versions/{version_id}/rollback")
def rollback_version(
    project_id: int, version_id: int, user: dict = Depends(current_user)
) -> dict:
    """回滚 = 恢复旧版本文件集，并作为新版本落快照（回滚本身可再撤销）。"""
    _owned_project(project_id, user)
    files = store.get_version_files(project_id, version_id)
    if files is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    store.set_files(project_id, files)
    version = store.create_version(project_id, f"回滚至 v{version_id}", files)
    message = store.add_message(project_id, "agent", f"⏪ 已回滚至版本 v{version_id}")
    _notify_project(project_id, "rollback", running=False)
    return {
        "files": files,
        "versions": store.list_versions(project_id),
        "version": version,
        "message": message,
    }


# ---------- P1：一键分享（Task 11）----------


@api_router.post("/projects/{project_id}/share")
def toggle_share(
    project_id: int, body: ShareRequest, user: dict = Depends(current_user)
) -> dict:
    """开启/关闭公开分享；关闭后原链接即刻失效（访客侧 404）。"""
    _owned_project(project_id, user)
    share = store.set_shared(project_id, body.enabled)
    _notify_project(project_id, "share", running=False)
    return {"share_id": share["share_id"], "is_shared": share["is_shared"]}


@api_router.get("/share/{share_id}")
def get_share(share_id: str) -> dict:
    """访客侧：仅返回项目元信息，不含消息历史（只读预览数据源）。"""
    data = store.get_shared(share_id)
    if data is None:
        raise HTTPException(status_code=404, detail="分享链接无效或已关闭")
    return data


# ---------- P1：代码导出（Task 12）----------


def _safe_zip_name(name: str) -> str:
    """防路径穿越：zip 条目名去掉盘符与 ../ 段。"""
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    return "/".join(parts) or "file.txt"


@api_router.get("/projects/{project_id}/export")
def export_project(project_id: int, user: dict = Depends(current_user)) -> StreamingResponse:
    """当前文件集内存打包 ZIP 下载。"""
    _owned_project(project_id, user)
    files = store.get_files(project_id)
    if not files:
        raise HTTPException(status_code=404, detail="暂无可导出的文件")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(_safe_zip_name(name), content)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="atoms-project-{project_id}.zip"'
        },
    )
