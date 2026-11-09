"""Shared write serialization, byte revisions and service directory ownership."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from functools import wraps
from pathlib import Path


class RevisionConflict(FileExistsError):
    """The resource changed since it was read by the caller."""


def file_revision(path: Path) -> str:
    return content_revision(path.read_bytes())


def content_revision(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_versioned_markdown(path, loader):
    # Retain the injectable parser, but never pair old content with a new hash.
    for _attempt in range(3):
        before = path.read_bytes()
        meta, body = loader(path)
        if path.read_bytes() == before:
            return meta, body, content_revision(before)
    raise RevisionConflict("文件在读取过程中持续变化，请稍后重试")


def check_revision(path: Path, payload: dict):
    expected = payload.get("expected_revision")
    if expected is not None and expected != file_revision(path):
        raise RevisionConflict("内容已发生变化，请查看最新版本并处理冲突")


def coordinated(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.write_lock:
            uploads = getattr(self, "document_uploads", None)
            if uploads:
                uploads.guard()
            guard = getattr(self, "write_guard", None)
            if guard:
                guard()
            return method(self, *args, **kwargs)
    return call


@dataclass
class PreparedMarkdownWrite:
    """Domain-produced bytes that can be journaled before application."""

    path: Path
    item_id: str
    text: str
    before: bytes | None
    history_version: str | None = None

    @classmethod
    def for_update(cls, path, item_id, text, revision):
        before = path.read_bytes()
        if content_revision(before) != revision:
            raise RevisionConflict("文件在准备过程中发生变化，请重新预览")
        return cls(path, item_id, text, before)

    @property
    def after(self):
        return self.text.encode("utf-8")

    def apply(self, history_dir, writer, checkpoint=None):
        from .history import save_snapshot_bytes
        current = self.path.read_bytes() if self.path.exists() else None
        if current != self.before:
            raise RevisionConflict("文件在准备写入后发生变化，请重新预览")
        if self.before is not None:
            save_snapshot_bytes(history_dir, self.item_id, self.before, self.history_version)
        if checkpoint:
            checkpoint("history")
        writer(self.path, self.text)
        if self.path.read_bytes() != self.after:
            raise RevisionConflict("文件在提交过程中发生变化，请检查恢复日志")
        if checkpoint:
            checkpoint("target")


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

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
