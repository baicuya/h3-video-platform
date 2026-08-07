from __future__ import annotations

import uuid
from datetime import UTC, datetime


def uuid_string() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)
