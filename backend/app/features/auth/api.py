from __future__ import annotations

from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.config import get_settings
from app.core.security import create_admin_session_token, require_admin_session
from app.features.auth.schemas import AdminLoginIn, AdminSessionOut

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=AdminSessionOut)
async def login(payload: AdminLoginIn, response: Response) -> AdminSessionOut:
    settings = get_settings()

    if not settings.admin_username or not settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_credentials_not_configured",
        )

    if not compare_digest(payload.username, settings.admin_username) or not compare_digest(
        payload.password,
        settings.admin_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )

    token = create_admin_session_token(settings.admin_username)
    response.set_cookie(
        key=settings.admin_session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.env == "production",
        samesite="lax",
        max_age=settings.admin_session_ttl_seconds,
        path="/",
    )
    return AdminSessionOut(authenticated=True, username=settings.admin_username)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    settings = get_settings()
    response.delete_cookie(
        key=settings.admin_session_cookie_name,
        httponly=True,
        secure=settings.env == "production",
        samesite="lax",
        path="/",
    )
    return response


@router.get("/auth/session", response_model=AdminSessionOut)
async def get_session(username: str = Depends(require_admin_session)) -> AdminSessionOut:
    return AdminSessionOut(authenticated=True, username=username)
