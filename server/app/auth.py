"""认证：pbkdf2 密码哈希 + HMAC 签名 Cookie 会话（stdlib 实现，零新依赖）。

- 密码：pbkdf2_hmac(sha256, 120000 轮)，格式 "salt_hex$hash_hex"
- 会话：token = base64url(payload).base64url(hmac_sha256(sig_key, payload))，
  payload = {"uid": int, "exp": epoch 秒}；Cookie HttpOnly + SameSite=Lax
- SECRET 从 env AUTH_SECRET 读取，缺省用机器本地随机文件固化（重启不失效）
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

from fastapi import Cookie, HTTPException

from app.db import store

SESSION_COOKIE = "atoms_session"
_SESSION_TTL = 7 * 24 * 3600  # 7 天
_PBKDF2_ROUNDS = 120_000


# ---- 密码哈希 ----


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), _PBKDF2_ROUNDS
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


# ---- 会话 token ----


def _secret() -> bytes:
    env = os.getenv("AUTH_SECRET")
    if env:
        return env.encode()
    # 无 env 时用本地随机文件固化（开发/演示；生产建议注入 AUTH_SECRET）
    path = Path(".auth_secret")
    if path.exists():
        return bytes.fromhex(path.read_text().strip())
    value = secrets.token_hex(32)
    path.write_text(value)
    return bytes.fromhex(value)


_SECRET = _secret()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_session_token(user_id: int) -> str:
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + _SESSION_TTL})
    body = _b64(payload.encode())
    sig = _b64(hmac.new(_SECRET, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def _parse_token(token: str) -> Optional[int]:
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = _b64(hmac.new(_SECRET, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    uid, exp = payload.get("uid"), payload.get("exp")
    if not isinstance(uid, int) or not isinstance(exp, int) or exp < time.time():
        return None
    return uid


# ---- FastAPI 依赖 ----


def current_user(atoms_session: Optional[str] = Cookie(default=None)) -> dict:
    """受保护 API 的登录依赖：无/失效会话 → 401。"""
    if not atoms_session:
        raise HTTPException(status_code=401, detail="未登录")
    uid = _parse_token(atoms_session)
    if uid is None:
        raise HTTPException(status_code=401, detail="会话已失效，请重新登录")
    user = store.get_user(uid)
    if user is None:
        raise HTTPException(status_code=401, detail="账号不存在")
    return user


def optional_user(atoms_session: Optional[str] = Cookie(default=None)) -> Optional[dict]:
    """preview/share 等访客可用路由的宽松依赖：未登录返回 None。"""
    if not atoms_session:
        return None
    uid = _parse_token(atoms_session)
    if uid is None:
        return None
    return store.get_user(uid)
