"""Crash-safe file replacement helpers for persisted workbench data."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def _replace_with_retry(source: Path, destination: Path, attempts: int = 8):
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt + 1 == attempts:
                raise
            time.sleep(0.005 * (attempt + 1))


def atomic_write_bytes(destination: Path, content: bytes) -> Path:
    """Write bytes beside the destination and atomically replace it after fsync."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        _replace_with_retry(temporary, destination)
        return destination
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_text(destination: Path, content: str, encoding: str = "utf-8") -> Path:
    return atomic_write_bytes(destination, content.encode(encoding))


def atomic_write_json(destination: Path, payload: Any) -> Path:
    return atomic_write_text(destination, json.dumps(payload, ensure_ascii=False, indent=2))
