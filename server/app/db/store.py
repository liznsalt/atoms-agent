"""查询层：每个函数内部独立开 session，dict 序列化统一在此完成。"""

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import delete, select

from .db import SessionLocal
from .models import FileState, Message, Project, User, Version


def _iso(value: datetime) -> str:
    return value.isoformat()


def _project_dict(project: Project) -> dict:
    return {
        "id": project.id,
        "title": project.title,
        "owner_id": project.owner_id,
        "share_id": project.share_id,
        "is_shared": project.is_shared,
        "created_at": _iso(project.created_at),
    }


def _user_dict(user: User) -> dict:
    return {"id": user.id, "email": user.email, "created_at": _iso(user.created_at)}


def _version_dict(version: Version) -> dict:
    return {
        "id": version.id,
        "project_id": version.project_id,
        "label": version.label,
        "created_at": _iso(version.created_at),
    }


def _message_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "project_id": message.project_id,
        "role": message.role,
        "content": message.content,
        "steps": message.steps,
        "created_at": _iso(message.created_at),
    }


def create_project(title: str, owner_id: int | None = None) -> dict:
    with SessionLocal() as session:
        project = Project(title=title, owner_id=owner_id)
        session.add(project)
        session.commit()
        return _project_dict(project)


def list_projects(owner_id: int) -> list[dict]:
    """多用户隔离：仅返回该用户拥有的项目。"""
    with SessionLocal() as session:
        projects = session.scalars(
            select(Project)
            .where(Project.owner_id == owner_id)
            .order_by(Project.created_at.desc(), Project.id.desc())
        ).all()
        return [_project_dict(p) for p in projects]


def get_project(project_id: int, owner_id: int | None = None) -> Optional[dict]:
    """详情查询；传 owner_id 时严格校验归属（仅 owner 可见），否则 None。"""
    with SessionLocal() as session:
        project = session.get(Project, project_id)
        if project is None:
            return None
        if owner_id is not None and project.owner_id != owner_id:
            return None
        return _project_dict(project)


def delete_project(project_id: int) -> bool:
    with SessionLocal() as session:
        project = session.get(Project, project_id)
        if project is None:
            return False
        session.execute(delete(FileState).where(FileState.project_id == project_id))
        session.execute(delete(Message).where(Message.project_id == project_id))
        session.execute(delete(Version).where(Version.project_id == project_id))
        session.delete(project)
        session.commit()
        return True


def add_message(
    project_id: int,
    role: str,
    content: str,
    steps: Optional[list[dict[str, Any]]] = None,
) -> dict:
    with SessionLocal() as session:
        message = Message(project_id=project_id, role=role, content=content, steps=steps)
        session.add(message)
        session.commit()
        return _message_dict(message)


def get_messages(project_id: int) -> list[dict]:
    with SessionLocal() as session:
        messages = session.scalars(
            select(Message).where(Message.project_id == project_id).order_by(Message.id.asc())
        ).all()
        return [_message_dict(m) for m in messages]


def get_files(project_id: int) -> dict:
    with SessionLocal() as session:
        state = session.scalars(
            select(FileState).where(FileState.project_id == project_id)
        ).first()
        return {} if state is None else state.files


def set_files(project_id: int, files: dict[str, str]) -> None:
    with SessionLocal() as session:
        state = session.scalars(
            select(FileState).where(FileState.project_id == project_id)
        ).first()
        if state is None:
            session.add(FileState(project_id=project_id, files=files))
        else:
            state.files = files
        session.commit()


# ---------- 版本快照（Task 9）----------


def create_version(project_id: int, label: str, files: dict[str, str]) -> dict:
    with SessionLocal() as session:
        version = Version(project_id=project_id, label=label, files=files)
        session.add(version)
        session.commit()
        return _version_dict(version)


def list_versions(project_id: int) -> list[dict]:
    """版本列表（倒序，最新在前）；不回传 files 大字段。"""
    with SessionLocal() as session:
        rows = session.scalars(
            select(Version).where(Version.project_id == project_id).order_by(Version.id.desc())
        ).all()
        return [_version_dict(v) for v in rows]


def get_version_files(project_id: int, version_id: int) -> Optional[dict]:
    with SessionLocal() as session:
        version = session.get(Version, version_id)
        if version is None or version.project_id != project_id:
            return None
        return version.files


# ---------- 账号（Task 13）----------


def create_user(email: str, password_hash: str) -> Optional[dict]:
    """注册；邮箱已存在返回 None。"""
    with SessionLocal() as session:
        exists = session.scalars(select(User).where(User.email == email)).first()
        if exists is not None:
            return None
        user = User(email=email, password_hash=password_hash)
        session.add(user)
        session.commit()
        return _user_dict(user)


def get_user_by_email(email: str) -> Optional[dict]:
    with SessionLocal() as session:
        user = session.scalars(select(User).where(User.email == email)).first()
        if user is None:
            return None
        return {"id": user.id, "email": user.email, "password_hash": user.password_hash}


def get_user(user_id: int) -> Optional[dict]:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        return None if user is None else _user_dict(user)


# ---------- 一键分享（Task 11）----------


def set_shared(project_id: int, enabled: bool) -> Optional[dict]:
    """开关分享；开启时惰性生成 share_id（同一项目关闭再开启链接不变）。"""
    with SessionLocal() as session:
        project = session.get(Project, project_id)
        if project is None:
            return None
        if enabled:
            if not project.share_id:
                project.share_id = uuid4().hex
            project.is_shared = True
        else:
            project.is_shared = False
        session.commit()
        return _project_dict(project)


def get_shared(share_id: str) -> Optional[dict]:
    """访客侧查询：仅 is_shared 开启时返回项目元信息（不含消息历史）。"""
    with SessionLocal() as session:
        project = session.scalars(
            select(Project).where(Project.share_id == share_id, Project.is_shared.is_(True))
        ).first()
        if project is None:
            return None
        return {
            "project_id": project.id,
            "title": project.title,
            "created_at": _iso(project.created_at),
        }
