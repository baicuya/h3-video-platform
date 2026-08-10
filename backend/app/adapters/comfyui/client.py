from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urlencode

import aiohttp

from app.core.config import get_settings


class ComfyUIClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.comfyui_base_url.rstrip("/")
        self.ws_url = settings.comfyui_ws_url
        self.client_id = uuid.uuid4().hex

    async def health_check(self) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/system_stats", timeout=30) as response:
                response.raise_for_status()
                return await response.json()

    async def upload_input(self, path: Path) -> str:
        form = aiohttp.FormData()
        with path.open("rb") as handle:
            form.add_field(
                "image",
                handle,
                filename=path.name,
                content_type="application/octet-stream",
            )
            form.add_field("type", "input")
            form.add_field("overwrite", "false")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/upload/image", data=form, timeout=300
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
        subfolder = result.get("subfolder", "")
        return f"{subfolder}/{result['name']}" if subfolder else result["name"]

    async def upload_image(self, path: Path) -> str:
        return await self.upload_input(path)

    async def submit_workflow(self, workflow: dict[str, Any]) -> str:
        payload = {"prompt": workflow, "client_id": self.client_id}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/prompt", json=payload, timeout=60
            ) as response:
                response.raise_for_status()
                result = await response.json()
        if result.get("node_errors"):
            raise RuntimeError(f"ComfyUI workflow validation failed: {result['node_errors']}")
        return str(result["prompt_id"])

    async def get_queue(self) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/queue", timeout=30) as response:
                response.raise_for_status()
                return await response.json()

    async def clear_pending(self) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/queue", json={"clear": True}, timeout=30
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def get_history(self, prompt_id: str) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/history/{prompt_id}", timeout=30
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def interrupt(self) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/interrupt", timeout=30) as response:
                response.raise_for_status()

    async def view_file(self, *, filename: str, subfolder: str, file_type: str) -> bytes:
        query = urlencode(
            {"filename": filename, "subfolder": subfolder, "type": file_type}
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/view?{query}", timeout=300) as response:
                response.raise_for_status()
                return await response.read()

    async def watch_execution(
        self, prompt_id: str, timeout_seconds: float = 7_200
    ) -> AsyncIterator[dict[str, Any]]:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        ws_target = f"{self.ws_url}?clientId={self.client_id}"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_target, heartbeat=30) as websocket:
                while asyncio.get_running_loop().time() < deadline:
                    try:
                        message = await websocket.receive(timeout=10)
                    except TimeoutError:
                        history = await self.get_history(prompt_id)
                        item = history.get(prompt_id)
                        if item and item.get("status", {}).get("completed"):
                            yield {"type": "history", "data": item}
                            return
                        continue
                    if message.type == aiohttp.WSMsgType.TEXT:
                        event = json.loads(message.data)
                        data = event.get("data", {})
                        if data.get("prompt_id") != prompt_id:
                            continue
                        yield event
                        if event.get("type") == "executing" and data.get("node") is None:
                            return
                    elif message.type in {
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.ERROR,
                    }:
                        break
        raise TimeoutError(f"ComfyUI prompt {prompt_id} did not finish")
