"""Record persistence, caching, history, conversion, and search."""

from __future__ import annotations

import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

from .markdown_io import dump_markdown, load_markdown_text, normalize_info_fields, now_iso, slugify
from .persistence import atomic_write_text
from .security import validate_portable_filename


TYPE_DIRS = {"issue": "issues", "todo": "todos", "idea": "ideas", "info": "infos"}
TYPE_PREFIXES = {"issue": "ISSUE", "todo": "TODO", "idea": "IDEA", "info": "INFO"}


class RecordRepository:
    """Own record source files and their filesystem-signature cache."""

    def __init__(
        self,
        global_ideas_dir: Path,
        projects_dir: Path,
        history_dir: Path,
        record_id_lock: threading.Lock,
        load_markdown,
        project,
        list_projects,
        open_markdown_external,
        move_to_trash,
    ):
        self.global_ideas_dir = global_ideas_dir
        self.projects_dir = projects_dir
        self.history_dir = history_dir
        self._record_id_lock = record_id_lock
        self.load_markdown = load_markdown
        self.project = project
        self.list_projects = list_projects
        self.open_markdown_external = open_markdown_external
        self._move_to_trash = move_to_trash
        self._record_cache_lock = threading.RLock()
        self._record_cache: dict[Path, tuple[int, int, dict]] = {}
        self._record_paths_by_id: dict[str, Path] = {}

    def import_markdown(self, payload: dict) -> dict:
        content = str(payload.get("content", ""))
        source_name = validate_portable_filename(payload.get("name", "导入记录.md"), label="导入文件名", suffixes={".md"})
        meta, body = load_markdown_text(content)
        record_type = payload.get("type") or meta.get("type") or "idea"
        title = payload.get("title") or meta.get("title")
        if not title:
            heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            title = heading.group(1).strip() if heading else Path(source_name).stem
        project_id = payload.get("project_id") if payload.get("project_id") is not None else meta.get("project_id")
        return self.create_record({"type": record_type, "title": title, "project_id": project_id, "status": meta.get("status"), "priority": meta.get("priority", "普通"), "tags": meta.get("tags", []), "due": meta.get("due"), "info_fields": meta.get("info_fields", []), "body": body})

    def _record_paths(self):
        yield from self.global_ideas_dir.glob("*.md")
        for directory in self.projects_dir.iterdir():
            if directory.is_dir():
                for subdir in TYPE_DIRS.values():
                    yield from (directory / subdir).glob("*.md")

    def _load_record(self, path: Path) -> dict | None:
        try:
            stat = path.stat()
        except FileNotFoundError:
            with self._record_cache_lock:
                cached = self._record_cache.pop(path, None)
                if cached:
                    self._record_paths_by_id.pop(str(cached[2].get("id", "")), None)
            return None
        signature = (stat.st_mtime_ns, stat.st_size)
        with self._record_cache_lock:
            cached = self._record_cache.get(path)
            if cached and cached[:2] == signature:
                return {**cached[2]}
            previous_id = str(cached[2].get("id", "")) if cached else ""
            try:
                meta, body = self.load_markdown(path)
            except FileNotFoundError:
                self._record_cache.pop(path, None)
                if previous_id:
                    self._record_paths_by_id.pop(previous_id, None)
                return None
            record = {**meta, "body": body, "file_path": str(path), "file_mtime": stat.st_mtime_ns}
            self._record_cache[path] = (stat.st_mtime_ns, stat.st_size, record)
            record_id = str(record.get("id", ""))
            if previous_id and previous_id != record_id:
                self._record_paths_by_id.pop(previous_id, None)
            if record_id:
                self._record_paths_by_id[record_id] = path
            return {**record}

    def _forget_record(self, path: Path):
        with self._record_cache_lock:
            cached = self._record_cache.pop(path, None)
            if cached:
                self._record_paths_by_id.pop(str(cached[2].get("id", "")), None)

    def list_records(self, project_id=None, record_type=None) -> list[dict]:
        records = []
        paths = list(self._record_paths())
        for path in paths:
            record = self._load_record(path)
            if not record or record.get("type") not in TYPE_DIRS:
                continue
            if project_id is not None and record.get("project_id") != project_id:
                continue
            if record_type and record.get("type") != record_type:
                continue
            records.append(record)
        current_paths = set(paths)
        with self._record_cache_lock:
            for stale in self._record_cache.keys() - current_paths:
                cached = self._record_cache.pop(stale)
                self._record_paths_by_id.pop(str(cached[2].get("id", "")), None)
        return sorted(records, key=lambda item: item.get("updated", ""), reverse=True)

    def list_record_summaries(self, project_id=None, record_type=None, record_ids=None, include_attachments: bool = False) -> list[dict]:
        """Return list-view data without transferring full Markdown bodies."""
        selected_ids = set(record_ids or [])
        summaries = []
        for record in self.list_records(project_id, record_type):
            if selected_ids and record.get("id") not in selected_ids:
                continue
            summary = {
                key: value for key, value in record.items()
                if key not in {"body", "attachments", "file_path"}
            }
            summary["body_preview"] = str(record.get("body", ""))[:600]
            if include_attachments:
                summary["attachments"] = list(record.get("attachments") or [])
            summaries.append(summary)
        return summaries

    def record_signatures(self) -> list[dict]:
        """Return the small payload used by the browser's change poll."""
        return [{"id": item.get("id"), "type": item.get("type"), "file_mtime": item.get("file_mtime")} for item in self.list_records()]

    def get_record(self, record_id: str) -> tuple[dict, Path] | tuple[None, None]:
        with self._record_cache_lock:
            known_path = self._record_paths_by_id.get(record_id)
        if known_path:
            record = self._load_record(known_path)
            if record and record.get("id") == record_id:
                return record, known_path
        for path in self._record_paths():
            record = self._load_record(path)
            if record and record.get("id") == record_id:
                return record, path
        return None, None

    def _next_id(self, record_type: str) -> str:
        prefix = TYPE_PREFIXES[record_type]
        used = []
        for record in self.list_records(record_type=record_type):
            match = re.fullmatch(rf"{prefix}-(\d+)", str(record.get("id", "")))
            if match:
                used.append(int(match.group(1)))
        return f"{prefix}-{max(used, default=0) + 1:04d}"

    def create_record(self, payload: dict) -> dict:
        record_type = payload.get("type")
        if record_type not in TYPE_DIRS:
            raise ValueError("记录类型无效")
        title = str(payload.get("title", "")).strip()
        if not title:
            raise ValueError("标题不能为空")
        project_id = payload.get("project_id") or None
        if record_type != "idea" and not project_id:
            raise ValueError("问题、待办和信息必须选择项目")
        if project_id and not self.project(project_id):
            raise ValueError("项目不存在")
        with self._record_id_lock:
            record_id, stamp = self._next_id(record_type), now_iso()
            if project_id:
                directory = self.projects_dir / project_id / TYPE_DIRS[record_type]
            else:
                directory = self.global_ideas_dir
            directory.mkdir(parents=True, exist_ok=True)
            meta = {
                "id": record_id, "type": record_type, "title": title, "project_id": project_id,
                "links": payload.get("links", []), "attachments": payload.get("attachments", []), "created": stamp, "updated": stamp,
            }
            if record_type == "info":
                meta["info_fields"] = normalize_info_fields(payload.get("info_fields", []))
                meta["info_color"] = payload.get("info_color") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(payload.get("info_color", ""))) else "#35a99a"
                meta["tags"] = payload.get("tags", [])
            else:
                meta.update({
                    "status": payload.get("status") or {"issue": "待处理", "todo": "待办", "idea": "收件箱"}[record_type],
                    "priority": payload.get("priority", "普通"), "tags": payload.get("tags", []),
                    "due": payload.get("due"), "completed": bool(payload.get("completed", False)),
                })
            body = str(payload.get("body", "")).strip() or f"# {title}\n\n"
            filename = f"{record_id}-{slugify(title)}.md"
            path = directory / filename
            atomic_write_text(path, dump_markdown(meta, body))
        return self._load_record(path)

    def update_record(self, record_id: str, payload: dict) -> dict:
        record, path = self.get_record(record_id)
        if not record:
            raise FileNotFoundError(record_id)
        editable = {"title", "status", "priority", "tags", "due", "completed", "links", "attachments", "info_fields", "info_color", "body"}
        if record.get("type") == "info":
            editable -= {"status", "priority", "due", "completed"}
        else:
            editable -= {"info_fields", "info_color"}
        if "info_fields" in payload:
            payload = {**payload, "info_fields": normalize_info_fields(payload["info_fields"])}
        if "info_color" in payload:
            payload = {**payload, "info_color": payload["info_color"] if re.fullmatch(r"#[0-9a-fA-F]{6}", str(payload["info_color"])) else record.get("info_color", "#35a99a")}
        updated = {**record, **{key: value for key, value in payload.items() if key in editable}, "updated": now_iso()}
        body = updated.pop("body")
        updated.pop("file_path", None)
        updated.pop("file_mtime", None)
        self._save_history(record_id, path)
        atomic_write_text(path, dump_markdown(updated, body))
        self._forget_record(path)
        return self._load_record(path)

    def convert_record(self, record_id: str, target_type: str) -> dict:
        if target_type not in {"issue", "todo"}:
            raise ValueError("只能在问题和待办之间转换")
        record, source = self.get_record(record_id)
        if not record or not source:
            raise FileNotFoundError(record_id)
        if record.get("type") not in {"issue", "todo"}:
            raise ValueError("只能在问题和待办之间转换")
        if record.get("type") == target_type:
            return record

        project_id = record.get("project_id")
        if not project_id or not self.project(project_id):
            raise ValueError("问题和待办必须归属于有效项目")
        destination_dir = self.projects_dir / project_id / TYPE_DIRS[target_type]
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source.name
        if destination.exists():
            raise ValueError("目标类型目录中已存在同名记录")

        body = record.get("body", "")
        metadata = {
            key: value for key, value in record.items()
            if key not in {"body", "file_path", "file_mtime"}
        }
        metadata["type"] = target_type
        metadata["updated"] = now_iso()
        self._save_history(record_id, source)
        self._forget_record(source)
        shutil.move(str(source), str(destination))
        try:
            atomic_write_text(destination, dump_markdown(metadata, body))
        except Exception:
            shutil.move(str(destination), str(source))
            raise
        return self._load_record(destination)

    def open_record_external(self, record_id: str) -> dict:
        record, path = self.get_record(record_id)
        if not record or not path:
            raise FileNotFoundError(record_id)
        editor = self.open_markdown_external(path)
        return {"ok": True, "editor": editor, "record_id": record_id, "file": path.name}

    def _save_history(self, record_id: str, source: Path):
        directory = self.history_dir / record_id
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(source, directory / f"{stamp}.md")
        versions = sorted(directory.glob("*.md"), reverse=True)
        for old_version in versions[30:]:
            old_version.unlink()

    def list_history(self, record_id: str) -> list[dict]:
        directory = self.history_dir / record_id
        if not directory.exists():
            return []
        versions = []
        for path in sorted(directory.glob("*.md"), reverse=True):
            meta, body = self.load_markdown(path)
            versions.append({"version": path.stem, "updated": meta.get("updated"), "title": meta.get("title"), "status": meta.get("status"), "preview": body[:180]})
        return versions

    def restore_history(self, record_id: str, version: str) -> dict:
        if not re.fullmatch(r"\d{8}-\d{6}-\d{6}", version):
            raise ValueError("历史版本标识无效")
        source = self.history_dir / record_id / f"{version}.md"
        current, current_path = self.get_record(record_id)
        if not current or not source.exists():
            raise FileNotFoundError(record_id)
        restored_meta, restored_body = self.load_markdown(source)
        payload = {key: value for key, value in restored_meta.items() if key not in {"id", "type", "project_id", "created", "updated"}}
        payload["body"] = restored_body
        return self.update_record(record_id, payload)

    def delete_record(self, record_id: str) -> dict:
        record, path = self.get_record(record_id)
        if not record:
            raise FileNotFoundError(record_id)
        self._forget_record(path)
        return self._move_to_trash(path, record_id, "record", record.get("title", record_id))

    def search(self, query: str) -> list[dict]:
        needle = query.casefold().strip()
        if not needle:
            return self.list_records()[:20]
        results = []
        projects = {item["id"]: item["name"] for item in self.list_projects()}
        for record in self.list_records():
            haystack = " ".join([str(record.get(key, "")) for key in ("title", "body", "tags", "status", "priority", "info_fields")]).casefold()
            if needle in haystack:
                record["project_name"] = projects.get(record.get("project_id"), "未归属")
                results.append(record)
        return results[:50]
