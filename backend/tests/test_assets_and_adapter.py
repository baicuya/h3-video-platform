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
