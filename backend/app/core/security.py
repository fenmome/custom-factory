"""JWT 认证与密码散列。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# 使用 pbkdf2_sha256：纯 Python 实现、无外部后端依赖，
# 且不受 bcrypt 的 72 字节长度上限限制（bcrypt>=4 会对超长密码直接报错）。
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],
    default="pbkdf2_sha256",
    deprecated=["bcrypt"],
    pbkdf2_sha256__rounds=290_000,
)

MAX_PASSWORD_BYTES = 1024


def hash_password(plain: str) -> str:
    if len(plain.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("密码过长")
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(*, user_id: str, workspace_id: str, expires_hours: int | None = None) -> str:
    """签发包含用户与工作空间身份的 JWT。"""
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours or settings.ACCESS_TOKEN_EXPIRE_HOURS)
    payload: dict[str, Any] = {
        "sub": user_id,
        "ws": workspace_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "typ": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """解码并校验 JWT，失败时返回空字典（由调用方决定抛出何种异常）。"""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return {}


def create_runner_token(*, executor_id: str, workspace_id: str) -> str:
    """为 Codex Runner 签发长期 token（绑定 executor 身份）。"""
    payload: dict[str, Any] = {
        "exec": executor_id,
        "ws": workspace_id,
        "typ": "runner",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_runner_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return {}
    if payload.get("typ") != "runner":
        return {}
    return payload


def constant_time_equals(left: str, right: str) -> bool:
    """常量时间字符串比较，用于静态 Runner Token。"""
    import hmac

    return hmac.compare_digest(left, right)
