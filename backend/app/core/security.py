from __future__ import annotations

import base64
import hashlib
import hmac
import time
from secrets import compare_digest

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings


def _require_backend_proxy_secret_value(x_backend_proxy_secret: str | None) -> None:
    settings = get_settings()

    if settings.env != "production" and not settings.backend_proxy_secret:
        return

    if not settings.backend_proxy_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="backend_proxy_secret_not_configured",
        )

    if x_backend_proxy_secret is None or not compare_digest(
        x_backend_proxy_secret,
        settings.backend_proxy_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_backend_proxy_secret",
        )


def _require_discord_service_token_value(x_discord_service_token: str | None) -> None:
    settings = get_settings()

    if settings.env != "production" and not settings.discord_service_token:
        return

    if not settings.discord_service_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="discord_service_token_not_configured",
        )

    if x_discord_service_token is None or not compare_digest(
        x_discord_service_token,
        settings.discord_service_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_discord_service_token",
        )


def _get_admin_session_secret() -> str:
    settings = get_settings()

    if settings.admin_session_secret:
        return settings.admin_session_secret

    if settings.env != "production":
        return "dev-admin-session-secret"

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="admin_session_secret_not_configured",
    )


def _build_admin_session_signature(payload: str) -> str:
    secret = _get_admin_session_secret().encode("utf-8")
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_admin_session_token(username: str, now: int | None = None) -> str:
    settings = get_settings()
    issued_at = int(time.time() if now is None else now)
    expires_at = issued_at + settings.admin_session_ttl_seconds
    payload = f"{username}:{expires_at}"
    signature = _build_admin_session_signature(payload)
    raw = f"{payload}:{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def validate_admin_session_token(token: str) -> str | None:
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, expires_at_raw, signature = decoded.split(":", 2)
        expires_at = int(expires_at_raw)
    except Exception:
        return None

    if expires_at < int(time.time()):
        return None

    payload = f"{username}:{expires_at}"
    expected_signature = _build_admin_session_signature(payload)
    if not compare_digest(signature, expected_signature):
        return None

    return username


def _require_admin_session_value(admin_session_cookie: str | None) -> str:
    settings = get_settings()

    if not settings.admin_username or not settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_credentials_not_configured",
        )

    if not admin_session_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_admin_session",
        )

    username = validate_admin_session_token(admin_session_cookie)
    if username is None or username != settings.admin_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_admin_session",
        )

    return username


async def require_backend_proxy_secret(
    x_backend_proxy_secret: str | None = Header(default=None, alias="X-Backend-Proxy-Secret"),
) -> None:
    _require_backend_proxy_secret_value(x_backend_proxy_secret)


async def require_admin_session(
    request: Request,
) -> str:
    settings = get_settings()
    return _require_admin_session_value(request.cookies.get(settings.admin_session_cookie_name))


async def require_admin_frontend_access(
    request: Request,
    x_backend_proxy_secret: str | None = Header(default=None, alias="X-Backend-Proxy-Secret"),
) -> str:
    _require_backend_proxy_secret_value(x_backend_proxy_secret)
    settings = get_settings()
    return _require_admin_session_value(request.cookies.get(settings.admin_session_cookie_name))


async def require_discord_service_token(
    x_discord_service_token: str | None = Header(default=None, alias="X-Discord-Service-Token"),
) -> None:
    _require_discord_service_token_value(x_discord_service_token)


async def require_admin_or_discord_service(
    request: Request,
    x_backend_proxy_secret: str | None = Header(default=None, alias="X-Backend-Proxy-Secret"),
    x_discord_service_token: str | None = Header(default=None, alias="X-Discord-Service-Token"),
) -> str:
    settings = get_settings()

    if x_discord_service_token:
        _require_discord_service_token_value(x_discord_service_token)
        return "discord"

    if settings.env != "production" and not settings.admin_username and not settings.backend_proxy_secret:
        return "local"

    _require_backend_proxy_secret_value(x_backend_proxy_secret)
    return _require_admin_session_value(request.cookies.get(settings.admin_session_cookie_name))
