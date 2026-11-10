"""Controlled Markdown snapshots and original-byte concept map JSON history."""

from datetime import datetime
from pathlib import Path
import re
import uuid

from .markdown_io import load_markdown
from .persistence import atomic_write_bytes


def save_snapshot(history_dir: Path, item_id: str, source: Path):
    save_snapshot_bytes(history_dir, item_id, source.read_bytes())


def save_snapshot_bytes(history_dir: Path, item_id: str, content: bytes, version=None):
    directory = history_dir / item_id
    directory.mkdir(parents=True, exist_ok=True)
    stamp = version or datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8]
    target = history_path(history_dir, item_id, stamp)
    if target.exists() and target.read_bytes() != content:
        raise ValueError("历史快照内容冲突")
    if not target.exists():
        atomic_write_bytes(target, content)
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


def concept_map_history_path(history_dir, item_id, version):
    if not re.fullmatch(r"CMAP-\d+", str(item_id)):
        raise ValueError("概念图标识无效")
    if not re.fullmatch(r"\d{8}-\d{6}-\d{6}(?:-[a-f0-9]{8})?", str(version)):
        raise ValueError("历史版本标识无效")
    return history_dir / item_id / f"{version}.json"


def save_concept_map_snapshot(history_dir, item_id, content, version):
    target = concept_map_history_path(history_dir, item_id, version)
    if target.exists():
        if target.read_bytes() != content:
            raise ValueError("概念图历史快照内容冲突")
    else:
        atomic_write_bytes(target, content)


def read_concept_map_snapshot(history_dir, item_id, version):
    import json
    from .write_coordinator import content_revision
    raw = concept_map_history_path(history_dir, item_id, version).read_bytes()
    item = json.loads(raw.decode('utf-8'))
    if not isinstance(item, dict) or item.get('id') != item_id:
        raise ValueError("历史版本损坏或不属于此概念图")
    if type(item.get('version', 1)) is not int or item.get('version', 1) not in (1, 2):
        raise ValueError("概念图历史版本尚不支持，保留原文件")
    return {**item, 'revision':content_revision(raw)}, raw


def list_concept_map_snapshots(history_dir, item_id):
    concept_map_history_path(history_dir, item_id, '20000101-000000-000000')
    items = []
    for path in sorted((history_dir / item_id).glob('*.json'), reverse=True):
        try:
            item, _ = read_concept_map_snapshot(history_dir, item_id, path.stem)
            items.append({'version':path.stem, 'title':item.get('title', ''), 'updated':item.get('updated'), 'revision':item['revision'], 'available':True})
        except (ValueError, OSError):
            items.append({'version':path.stem, 'available':False, 'warning':'历史格式未知或损坏，保留文件，不能恢复'})
    return items
