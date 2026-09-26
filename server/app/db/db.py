from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL

_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    # FastAPI 多线程访问同一 SQLite 连接需要关闭同线程校验
    _connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

if DATABASE_URL.startswith("sqlite"):
    # WAL：读写并发下读不阻塞写（多用户同时浏览/生成时预览与聊天互不卡）
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _sqlite_wal(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def init_db() -> None:
    from . import models  # noqa: F401  确保模型已注册到 Base.metadata

    models.Base.metadata.create_all(engine)
    _add_missing_project_columns()
    _adopt_orphan_projects()


def _adopt_orphan_projects() -> None:
    """历史无主项目划归最早注册的用户（严格隔离后 NULL 项目无人可见，归属后数据不丢）。"""
    from sqlalchemy import func, select, update

    from .models import Project, User

    with engine.begin() as conn:
        orphan_count = conn.execute(
            select(func.count()).select_from(Project).where(Project.owner_id.is_(None))
        ).scalar()
        if not orphan_count:
            return
        first_user_id = conn.execute(select(func.min(User.id))).scalar()
        if first_user_id is None:
            return  # 无任何用户则暂不处理（保持现状，出现用户后下次启动再归）
        conn.execute(
            update(Project).where(Project.owner_id.is_(None)).values(owner_id=first_user_id)
        )


def _add_missing_project_columns() -> None:
    """SQLite 轻量迁移：create_all 不会给已有表补新列，启动时为 projects 补 owner/分享字段。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if not inspector.has_table("projects"):
        return
    columns = {col["name"] for col in inspector.get_columns("projects")}
    with engine.begin() as conn:
        if "owner_id" not in columns:
            conn.execute(text("ALTER TABLE projects ADD COLUMN owner_id INTEGER"))
            conn.execute(text("CREATE INDEX ix_projects_owner_id ON projects (owner_id)"))
        if "share_id" not in columns:
            conn.execute(text("ALTER TABLE projects ADD COLUMN share_id VARCHAR"))
            conn.execute(text("CREATE UNIQUE INDEX ix_projects_share_id ON projects (share_id)"))
        if "is_shared" not in columns:
            conn.execute(text(
                "ALTER TABLE projects ADD COLUMN is_shared BOOLEAN NOT NULL DEFAULT 0"
            ))
