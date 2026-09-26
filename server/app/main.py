from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import api_router, preview_router
from app.db.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Atoms Agent Demo", lifespan=lifespan)

# 校验错误（422）转友好中文文案：取第一条错误的字段 + 消息，避免前端拿到
# Pydantic 原始结构（detail 为数组）而显示兜底文案
_FIELD_LABELS = {"email": "邮箱", "password": "密码", "prompt": "需求", "message": "消息", "enabled": "开关"}
_MSG_ALIASES = {
    "Field required": "不能为空",
    "Missing": "不能为空",
    "Not a valid email address.": "格式不正确",
}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: RequestValidationError, exc: RequestValidationError):
    for err in exc.errors():
        raw = str(err.get("msg", ""))
        raw = raw.removeprefix("Value error, ")
        raw = _MSG_ALIASES.get(raw, raw)
        field = err.get("loc", [None])[-1]
        label = _FIELD_LABELS.get(field, "")
        # validator 消息可能已含字段名（如"密码至少 6 位"），避免拼成"密码密码…"
        text = raw if (label and raw.startswith(label)) else (f"{label}{raw}" if label else raw)
        if text:
            return JSONResponse({"detail": text}, status_code=422)
    return JSONResponse({"detail": "请求参数不合法"}, status_code=422)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(preview_router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# 生产模式：前端构建产物存在则同端口托管（挂在 API 路由之后，仅兜底未匹配路径）
# 前端构建产物位置：优先仓库相对路径（本地开发，总是最新构建），
# 回退部署包内嵌（server/client_dist，veFaaS 等仅打包 server/ 的部署形态）
_SERVER_ROOT = Path(__file__).resolve().parent.parent
_REPO_DIST = _SERVER_ROOT / ".." / "client" / "dist"
_EMBEDDED_DIST = _SERVER_ROOT / "client_dist"
STATIC_DIR = _REPO_DIST if _REPO_DIST.is_dir() else _EMBEDDED_DIST
try:
    STATIC_DIR = STATIC_DIR.resolve()
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    INDEX_HTML = STATIC_DIR / "index.html"

    # SPA history fallback：/project/3 等前端路由刷新时回退到 index.html；API/preview 404 仍返回 JSON
    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request, exc: StarletteHTTPException):
        from fastapi.responses import JSONResponse

        path = request.url.path
        if exc.status_code == 404 and INDEX_HTML.exists() and not (
            path.startswith("/api") or path.startswith("/preview")
        ):
            return FileResponse(str(INDEX_HTML))
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
except Exception:  # noqa: BLE001  开发模式无 dist（前端走 vite dev proxy）
    pass
