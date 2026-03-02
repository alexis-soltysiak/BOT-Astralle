from __future__ import annotations

from secrets import compare_digest

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_backend_proxy_secret(
    x_backend_proxy_secret: str | None = Header(default=None, alias="X-Backend-Proxy-Secret"),
) -> None:
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
