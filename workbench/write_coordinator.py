"""Shared write serialization, byte revisions and service directory ownership."""

from __future__ import annotations

import hashlib
import os
from functools import wraps
from pathlib import Path


class RevisionConflict(FileExistsError):
    """The resource changed since it was read by the caller."""


def file_revision(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_revision(path: Path, payload: dict):
    expected = payload.get("expected_revision")
    if expected is not None and expected != file_revision(path):
        raise RevisionConflict("内容已发生变化，请查看最新版本并处理冲突")


def coordinated(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.write_lock:
            guard = getattr(self, "write_guard", None)
            if guard:
                guard()
            return method(self, *args, **kwargs)
    return call


class DataDirectoryLock:
    """OS-owned advisory lock; only the HTTP service holds it, not read tools."""

    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / ".workbench-service.lock"
        self.stream = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                if not self.stream.read(1):
                    self.stream.write(b"0")
                    self.stream.flush()
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise FileExistsError("该数据目录已有工作台服务，请使用已有服务或先停止它") from exc

    def close(self):
        if self.stream.closed:
            return
        if os.name == "nt":
            import msvcrt
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        self.stream.close()
