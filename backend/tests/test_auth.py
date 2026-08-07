from __future__ import annotations

import pytest

from .helpers import create_user, login


@pytest.mark.asyncio
async def test_login_me_logout_and_generic_error(client):
    await create_user(username="alice")
    wrong = await login(client, "alice", "wrong-password")
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "账号或密码错误"
    missing = await login(client, "nobody", "wrong-password")
    assert missing.status_code == 401
    assert missing.json()["detail"] == "账号或密码错误"

    response = await login(client, "alice")
    assert response.status_code == 200
    assert response.cookies.get("h3_session")
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"
    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204


@pytest.mark.asyncio
async def test_login_rate_limit(client):
    await create_user(username="limited")
    for _ in range(5):
        response = await login(client, "limited", "wrong-password")
        assert response.status_code == 401
    response = await login(client, "limited", "wrong-password")
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_first_login_forces_password_change(client):
    await create_user(
        username="first-login",
        password="initial-123",
        must_change_password=True,
    )
    assert (await login(client, "first-login", "initial-123")).status_code == 200
    blocked = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "t2v", "prompt": "test"},
    )
    assert blocked.status_code == 403
    changed = await client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "initial-123",
            "new_password": "changed-123",
            "confirm_password": "changed-123",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
    assert (await login(client, "first-login", "changed-123")).status_code == 200
