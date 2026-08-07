"""Small standard-library client used by the Phase 4 ComfyUI smoke tests."""

from __future__ import annotations

import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ComfyUIError(RuntimeError):
    """Raised when ComfyUI rejects or fails a validation workflow."""


class ComfyUITestClient:
    def __init__(self, base_url: str, timeout_seconds: float = 1_800) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _json_request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers: dict[str, str] = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ComfyUIError(f"ComfyUI HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise ComfyUIError(f"ComfyUI unavailable: {exc.reason}") from exc

    def health_check(self) -> dict[str, Any]:
        return self._json_request("/system_stats")

    def upload_image(self, image_path: Path) -> str:
        boundary = f"----h3-{uuid.uuid4().hex}"
        mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        image_bytes = image_path.read_bytes()
        chunks = [
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="image"; '
                f'filename="{image_path.name}"\r\n'
            ).encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            image_bytes,
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="type"\r\n\r\ninput\r\n',
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="overwrite"\r\n\r\nfalse\r\n',
            f"--{boundary}--\r\n".encode(),
        ]
        request = Request(
            f"{self.base_url}/upload/image",
            data=b"".join(chunks),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                result = json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ComfyUIError(f"Image upload failed ({exc.code}): {detail}") from exc
        subfolder = result.get("subfolder", "")
        name = result["name"]
        return f"{subfolder}/{name}" if subfolder else name

    def submit_workflow(self, workflow: dict[str, Any]) -> str:
        result = self._json_request("/prompt", method="POST", payload={"prompt": workflow})
        node_errors = result.get("node_errors") or {}
        if node_errors:
            raise ComfyUIError(f"Workflow validation failed: {node_errors}")
        try:
            return str(result["prompt_id"])
        except KeyError as exc:
            raise ComfyUIError(f"Missing prompt_id in response: {result}") from exc

    def wait_for_completion(self, prompt_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            history = self._json_request(f"/history/{prompt_id}")
            item = history.get(prompt_id)
            if not item:
                time.sleep(2)
                continue
            status = item.get("status", {})
            if status.get("completed"):
                if status.get("status_str") != "success":
                    raise ComfyUIError(
                        f"Prompt {prompt_id} completed with status {status}: "
                        f"{status.get('messages', [])}"
                    )
                return item
            time.sleep(2)
        raise ComfyUIError(
            f"Prompt {prompt_id} did not finish within {self.timeout_seconds:.0f}s"
        )


def load_workflow(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        workflow = json.load(handle)
    if not isinstance(workflow, dict):
        raise ComfyUIError(f"Workflow must be a JSON object: {path}")
    return workflow


def output_files(history_item: dict[str, Any]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for node_output in history_item.get("outputs", {}).values():
        for key in ("images", "audio"):
            value = node_output.get(key, [])
            if isinstance(value, list):
                files.extend(item for item in value if isinstance(item, dict))
    return files
