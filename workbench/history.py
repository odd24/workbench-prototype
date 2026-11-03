"""Shared Markdown snapshots for records and knowledge documents."""

from datetime import datetime
from pathlib import Path
import re
import uuid

from .markdown_io import load_markdown
from .persistence import atomic_write_bytes


def save_snapshot(history_dir: Path, item_id: str, source: Path):
    directory = history_dir / item_id
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8]
    atomic_write_bytes(directory / f"{stamp}.md", source.read_bytes())
    for old in sorted(directory.glob("*.md"), reverse=True)[30:]:
        old.unlink()


def history_path(history_dir: Path, item_id: str, version: str) -> Path:
    if not re.fullmatch(r"(?:ISSUE|TODO|INFO|IDEA|DOC)-\d+", item_id):
        raise ValueError("条目标识无效")
    if not re.fullmatch(r"\d{8}-\d{6}-\d{6}(?:-[a-f0-9]{8})?", str(version)):
        raise ValueError("历史版本标识无效")
    return history_dir / item_id / f"{version}.md"


def read_snapshot(history_dir: Path, item_id: str, version: str) -> dict:
    meta, body = load_markdown(history_path(history_dir, item_id, version))
    if meta.get("id") != item_id or not meta.get("type"):
        raise ValueError("历史版本损坏或不属于此条目")
    return {**meta, "body": body, "version": version}


def list_snapshots(history_dir: Path, item_id: str) -> list[dict]:
    history_path(history_dir, item_id, "20000101-000000-000000")
    items = []
    for path in sorted((history_dir / item_id).glob("*.md"), reverse=True):
        try:
            item = read_snapshot(history_dir, item_id, path.stem)
            items.append({"version": path.stem, "updated": item.get("updated"),
                          "title": item.get("title"), "status": item.get("status"),
                          "preview": item["body"][:180]})
        except (ValueError, OSError):
            continue
    return items
