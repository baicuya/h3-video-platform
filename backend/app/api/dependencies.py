from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Cookie(alias=get_settings().cookie_name)] = None,
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或登录已失效",
    )
    if not token:
        raise credentials_error
    try:
        payload = decode_access_token(token)
        user_id = str(payload["sub"])
        session_version = int(payload["sv"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise credentials_error from None
    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.session_version != session_version:
        raise credentials_error
    return user


async def require_password_changed(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="首次登录必须先修改密码",
        )
    return user


async def require_admin(
    user: Annotated[User, Depends(require_password_changed)],
) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
