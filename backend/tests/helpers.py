from __future__ import annotations

from app.core.security import hash_password
from app.models.user import User

from .conftest import TestSession


async def create_user(
    *,
    username: str,
    password: str = "password-123",
    role: str = "user",
    must_change_password: bool = False,
    is_active: bool = True,
) -> User:
    async with TestSession() as db:
        user = User(
            username=username,
            display_name=username.title(),
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
            must_change_password=must_change_password,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def login(client, username: str, password: str = "password-123"):
    return await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
