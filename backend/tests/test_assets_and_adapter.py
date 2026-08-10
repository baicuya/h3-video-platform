from __future__ import annotations

import pytest

from app.adapters.comfyui.client import ComfyUIClient

from .helpers import create_user, login


@pytest.mark.asyncio
async def test_file_type_validation(client):
    await create_user(username="uploader")
    assert (await login(client, "uploader")).status_code == 200
    response = await client.post(
        "/api/v1/assets/images",
        files={"file": ("payload.exe", b"not-an-image", "image/png")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_asset_content_preview_is_private_and_supports_ranges(client):
    await create_user(username="owner")
    await create_user(username="other")
    assert (await login(client, "owner")).status_code == 200
    payload = b"preview-image-bytes"
    upload = await client.post(
        "/api/v1/assets/images",
        files={"file": ("preview.png", payload, "image/png")},
    )
    assert upload.status_code == 201
    asset_id = upload.json()["id"]

    preview = await client.get(f"/api/v1/assets/{asset_id}/content")
    assert preview.status_code == 200
    assert preview.content == payload
    assert preview.headers["content-type"] == "image/png"
    assert preview.headers["content-disposition"].startswith("inline;")
    assert preview.headers["cache-control"] == "private, max-age=3600"

    partial = await client.get(
        f"/api/v1/assets/{asset_id}/content",
        headers={"Range": "bytes=0-6"},
    )
    assert partial.status_code == 206
    assert partial.content == payload[:7]

    assert (await login(client, "other")).status_code == 200
    assert (await client.get(f"/api/v1/assets/{asset_id}/content")).status_code == 404


@pytest.mark.asyncio
async def test_comfyui_adapter_mock(monkeypatch):
    async def fake_health(self):
        return {"system": {"comfyui_version": "test"}}

    async def fake_submit(self, workflow):
        assert workflow == {"1": {"class_type": "Test"}}
        return "prompt-test"

    monkeypatch.setattr(ComfyUIClient, "health_check", fake_health)
    monkeypatch.setattr(ComfyUIClient, "submit_workflow", fake_submit)
    client = ComfyUIClient()
    assert (await client.health_check())["system"]["comfyui_version"] == "test"
    assert await client.submit_workflow({"1": {"class_type": "Test"}}) == "prompt-test"
