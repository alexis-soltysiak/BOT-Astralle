from __future__ import annotations

from pydantic import BaseModel


class AdminLoginIn(BaseModel):
    username: str
    password: str


class AdminSessionOut(BaseModel):
    authenticated: bool
    username: str
