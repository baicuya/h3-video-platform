from __future__ import annotations

import pytest

from .helpers import create_user, login


@pytest.mark.asyncio
async def test_admin_creates_disables_and_resets_user(client):
    await create_user(username="admin", role="admin")
    assert (await login(client, "admin")).status_code == 200
    created = await client.post(
        "/api/v1/admin/users",
        json={
            "username": "video.user",
            "display_name": "Video User",
            "initial_password": "initial-123",
            "confirm_password": "initial-123",
            "role": "user",
            "is_active": True,
            "remark": "internal",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["initial_password"] == "initial-123"
    user_id = body["user"]["id"]
    assert body["user"]["must_change_password"] is True

    reset = await client.post(
        f"/api/v1/admin/users/{user_id}/reset-password",
        json={"new_password": "reset-pass-123", "confirm_password": "reset-pass-123"},
    )
    assert reset.status_code == 200
    disabled = await client.post(f"/api/v1/admin/users/{user_id}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    client.cookies.clear()
    denied = await login(client, "video.user", "reset-pass-123")
    assert denied.status_code == 401


@pytest.mark.asyncio
async def test_normal_user_cannot_access_admin_and_no_register_route(client):
    await create_user(username="normal")
    assert (await login(client, "normal")).status_code == 200
    denied = await client.get("/api/v1/admin/users")
    assert denied.status_code == 403
    register = await client.post(
        "/api/v1/auth/register",
        json={"username": "self-register", "password": "password-123"},
    )
    assert register.status_code == 404
