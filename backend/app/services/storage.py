from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import UploadFile


class StorageProvider(ABC):
    @abstractmethod
    async def save_upload(
        self,
        upload: UploadFile,
        *,
        kind: str,
        extension: str,
        max_bytes: int,
    ) -> tuple[str, int]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_url(self, storage_path: str) -> str:
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    async def save_upload(
        self,
        upload: UploadFile,
        *,
        kind: str,
        extension: str,
        max_bytes: int,
    ) -> tuple[str, int]:
        relative = Path("uploads") / kind / f"{uuid.uuid4().hex}{extension}"
        destination = (self.root / relative).resolve()
        if self.root not in destination.parents:
            raise ValueError("非法存储路径")
        destination.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        try:
            with destination.open("xb") as handle:
                while chunk := await upload.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("文件超过大小限制")
                    handle.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return str(relative), total

    async def delete(self, storage_path: str) -> None:
        target = (self.root / storage_path).resolve()
        if self.root not in target.parents:
            raise ValueError("非法存储路径")
        target.unlink(missing_ok=True)

    async def get_url(self, storage_path: str) -> str:
        return f"/media/{storage_path}"

    def absolute_path(self, storage_path: str) -> Path:
        target = (self.root / storage_path).resolve()
        if self.root not in target.parents:
            raise ValueError("非法存储路径")
        return target
