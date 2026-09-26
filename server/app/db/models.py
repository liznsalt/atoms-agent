from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.snowflake import snowflake_id


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    # 统一存 naive UTC（SQLite 读回也是 naive），保证序列化结果前后一致
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """账号：邮箱唯一，密码 pbkdf2 哈希（stdlib，零新依赖）。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class Project(Base):
    __tablename__ = "projects"

    # 雪花 ID（53 位，JS Number 精度安全）：应用层生成，跨实例可配 MACHINE_ID 错开；
    # SQLite INTEGER 亲和性对存量小 id 天然兼容，无需数据迁移
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    title: Mapped[str] = mapped_column(String, nullable=False)
    # 归属用户（严格隔离：仅 owner 可见；历史无主项目由启动迁移划归最早用户）
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), index=True, nullable=True
    )
    # 一键分享：share_id 稳定复用（关闭再开启链接不变），is_shared 控制链接是否生效
    share_id: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class Version(Base):
    """版本快照：每次生成成功 / 回滚后自动落一份全量文件集。"""

    __tablename__ = "versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id"), index=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    files: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)  # "user" | "agent"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class FileState(Base):
    __tablename__ = "file_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id"), unique=True, nullable=False
    )
    files: Mapped[dict] = mapped_column(JSON, nullable=False)
