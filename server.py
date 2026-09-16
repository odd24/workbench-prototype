"""Zero-dependency local server and Markdown repository for 本地工作台."""

from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from workbench import external_editor as external_editor_module
from workbench.assets import AttachmentRepository
from workbench.concept_maps import CONCEPT_MAP_HEIGHT, CONCEPT_MAP_WIDTH, ConceptMapRepository
from workbench.configuration import ConfigurationRepository
from workbench.documents import DocumentRepository
from workbench.external_editor import EXTERNAL_EDITOR_FILE
from workbench.markdown_io import (
    dump_markdown,
    load_markdown,
    load_markdown_text,
    normalize_info_fields,
    now_iso,
    parse_scalar,
    slugify,
    yaml_scalar,
)
from workbench.paths import (
    DEFAULT_DATA_DIR,
    EXPORT_LOCATION_FILE,
    LOCATION_FILE,
    common_export_locations,
    configured_data_dir,
    configured_export_dir,
    directory_browser_payload,
    export_location_payload,
    export_to_saved_location,
    relocate_repository,
    save_data_location,
    save_export_location,
)


APP_DIR = Path(__file__).resolve().parent
APP_VERSION = "2026.09.16.2"
TYPE_DIRS = {"issue": "issues", "todo": "todos", "idea": "ideas", "info": "infos"}
TYPE_PREFIXES = {"issue": "ISSUE", "todo": "TODO", "idea": "IDEA", "info": "INFO"}


def detected_external_editors() -> list[dict]:
    return external_editor_module.detected_external_editors()


def external_editor_payload(config_file: Path = EXTERNAL_EDITOR_FILE) -> dict:
    return external_editor_module.external_editor_payload(config_file, detected_external_editors)


def save_external_editor(editor_id: str, custom_path: str = "", config_file: Path = EXTERNAL_EDITOR_FILE) -> dict:
    return external_editor_module.save_external_editor(editor_id, custom_path, config_file, detected_external_editors)


def open_markdown_external(path: Path, config_file: Path = EXTERNAL_EDITOR_FILE) -> str:
    return external_editor_module.open_markdown_external(path, config_file, detected_external_editors)


class Repository:
    def __init__(self, data_dir: Path):
        self.root = data_dir.resolve()
        self._record_id_lock = threading.Lock()
        # Markdown remains the source of truth.  Cache parsed records by the
        # filesystem signature so normal reads only stat files; externally
        # edited files are picked up automatically on the next access.
        self._record_cache_lock = threading.RLock()
        self._record_cache: dict[Path, tuple[int, int, dict]] = {}
        self._record_paths_by_id: dict[str, Path] = {}
        self.projects_dir = self.root / "projects"
        self.global_ideas_dir = self.root / "ideas"
        self.global_assets_dir = self.root / "assets"
        self.documents_dir = self.root / "documents"
        self.concept_maps_dir = self.root / "concept-maps"
        self.trash_dir = self.root / ".trash"
        self.history_dir = self.root / "history"
        self.config_dir = self.root / "config"
        for directory in (self.projects_dir, self.global_ideas_dir, self.global_assets_dir, self.documents_dir, self.concept_maps_dir, self.trash_dir, self.history_dir, self.config_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self._ensure_config()
        self._configuration_repository = ConfigurationRepository(
            self.root,
            self.config_dir,
            self._unsorted_projects,
            self.list_documents,
            self.list_projects,
            self.list_records,
            self.update_document,
            self.update_project,
            self.update_record,
            self.concept_map_categories,
        )
        self._document_repository = DocumentRepository(
            self.documents_dir,
            self.ensure_document_category,
            self.list_records,
            self.list_projects,
            lambda path: open_markdown_external(path),
            self._move_to_trash,
        )
        self._concept_map_repository = ConceptMapRepository(self.concept_maps_dir, self.config_dir, self._record_id_lock, self._move_to_trash)
        self._attachment_repository = AttachmentRepository(
            self.root,
            self.projects_dir,
            self.global_assets_dir,
            self.get_record,
            self.update_record,
            self.project,
            self.list_records,
            self.list_projects,
        )
        self.cleanup_trash()

    def _ensure_config(self):
        settings = self.config_dir / "settings.json"
        settings.write_text(json.dumps({"version": 1, "data_dir": str(self.root)}, ensure_ascii=False, indent=2), encoding="utf-8")
        templates = self.config_dir / "status-templates.json"
        if not templates.exists():
            data = {
                "issue": [
                    {"id": "backlog", "name": "待处理", "color": "#87919e"},
                    {"id": "analysis", "name": "分析中", "color": "#4d78e8"},
                    {"id": "in_progress", "name": "处理中", "color": "#e08b38"},
                    {"id": "resolved", "name": "已解决", "color": "#2ba477", "completed": True},
                ],
                "todo": [
                    {"id": "todo", "name": "待办", "color": "#87919e"},
                    {"id": "doing", "name": "进行中", "color": "#4d78e8"},
                    {"id": "done", "name": "已完成", "color": "#2ba477", "completed": True},
                ],
                "idea": [
                    {"id": "inbox", "name": "收件箱", "color": "#87919e"},
                    {"id": "review", "name": "待评估", "color": "#7856c8"},
                    {"id": "adopted", "name": "已采纳", "color": "#2ba477", "completed": True},
                ],
            }
            templates.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        workflows = self.config_dir / "workflow-templates.json"
        if not workflows.exists():
            default_statuses = json.loads(templates.read_text(encoding="utf-8"))
            workflows.write_text(json.dumps([{"id": "standard", "name": "标准工作流", "statuses": default_statuses}], ensure_ascii=False, indent=2), encoding="utf-8")
        labels = self.config_dir / "labels.json"
        if not labels.exists():
            labels.write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
        project_sort = self.config_dir / "project-sort.json"
        if not project_sort.exists():
            project_sort.write_text(json.dumps({"mode": "custom", "order": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        document_sort = self.config_dir / "document-sort.json"
        if not document_sort.exists():
            document_sort.write_text(json.dumps({"category_mode": "manual", "category_order": [], "file_mode": "updated", "file_modes": {}, "file_orders": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
        document_categories = self.config_dir / "document-categories.json"
        if not document_categories.exists():
            document_categories.write_text("[]", encoding="utf-8")
        concept_map_categories = self.config_dir / "concept-map-categories.json"
        if not concept_map_categories.exists():
            concept_map_categories.write_text("[]", encoding="utf-8")
        trash_index = self.trash_dir / "index.json"
        if not trash_index.exists():
            trash_index.write_text("{}", encoding="utf-8")

    def config(self) -> dict:
        return self._configuration_repository.config()

    def project_sort(self) -> dict:
        return self._configuration_repository.project_sort()

    def save_project_sort(self, payload: dict) -> dict:
        return self._configuration_repository.save_project_sort(payload)

    def document_sort(self) -> dict:
        return self._configuration_repository.document_sort()

    def save_document_sort(self, payload: dict) -> dict:
        return self._configuration_repository.save_document_sort(payload)

    def document_categories(self) -> list[str]:
        return self._configuration_repository.document_categories()

    def save_document_categories(self, categories: list) -> list[str]:
        return self._configuration_repository.save_document_categories(categories)

    def ensure_document_category(self, category: str) -> str:
        return self._configuration_repository.ensure_document_category(category)

    def rename_document_category(self, old_name: str, new_name: str) -> dict:
        return self._configuration_repository.rename_document_category(old_name, new_name)

    def delete_document_category(self, name: str) -> dict:
        return self._configuration_repository.delete_document_category(name)

    def save_workflow_templates(self, payload) -> list[dict]:
        return self._configuration_repository.save_workflow_templates(payload)

    def _validate_statuses(self, templates: dict):
        return self._configuration_repository._validate_statuses(templates)

    def list_tags(self) -> list[dict]:
        return self._configuration_repository.list_tags()

    def save_tags(self, payload) -> list[dict]:
        return self._configuration_repository.save_tags(payload)

    def save_status_templates(self, templates: dict) -> dict:
        return self._configuration_repository.save_status_templates(templates)

    def _unsorted_projects(self) -> list[dict]:
        projects = []
        for readme in self.projects_dir.glob("*/README.md"):
            meta, body = load_markdown(readme)
            if meta.get("type") != "project":
                continue
            meta["description"] = body.removeprefix(f"# {meta.get('name', '')}").strip()
            meta["path"] = str(readme.parent)
            projects.append(meta)
        return projects

    def list_projects(self) -> list[dict]:
        projects = self._unsorted_projects()
        sorting = self.project_sort()
        mode = sorting["mode"]
        if mode == "name":
            return sorted(projects, key=lambda item: item.get("name", "").casefold())
        if mode == "created":
            return sorted(projects, key=lambda item: item.get("created", ""), reverse=True)
        if mode == "record_count":
            counts: dict[str, int] = {}
            for record in self.list_records():
                project_id = record.get("project_id")
                if project_id:
                    counts[project_id] = counts.get(project_id, 0) + 1
            return sorted(projects, key=lambda item: (counts.get(item.get("id"), 0), item.get("name", "")), reverse=True)
        if mode == "updated":
            return sorted(projects, key=lambda item: item.get("updated", ""), reverse=True)
        positions = {project_id: index for index, project_id in enumerate(sorting["order"])}
        return sorted(projects, key=lambda item: (positions.get(item.get("id"), 999999), item.get("created", "")))

    def project(self, project_id: str) -> dict | None:
        return next((item for item in self.list_projects() if item.get("id") == project_id), None)

    def create_project(self, payload: dict) -> dict:
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValueError("项目名称不能为空")
        base = slugify(name)
        project_id, index = base, 2
        while self.project(project_id):
            project_id, index = f"{base}-{index}", index + 1
        folder = self.projects_dir / project_id
        for child in (*TYPE_DIRS.values(), "assets/images", "assets/files"):
            (folder / child).mkdir(parents=True, exist_ok=True)
        stamp = now_iso()
        meta = {"id": project_id, "type": "project", "name": name, "status": payload.get("status", "active"), "color": payload.get("color", "#4d78e8"), "workflow_template": payload.get("workflow_template", "standard"), "created": stamp, "updated": stamp}
        body = f"# {name}\n\n{payload.get('description', '').strip()}"
        (folder / "README.md").write_text(dump_markdown(meta, body), encoding="utf-8")
        sorting = self.project_sort()
        if sorting["mode"] == "custom":
            sorting["order"] = [project["id"] for project in self.list_projects()]
            self.save_project_sort(sorting)
        return {**meta, "description": payload.get("description", ""), "path": str(folder)}

    def update_project(self, project_id: str, payload: dict) -> dict:
        project = self.project(project_id)
        if not project:
            raise FileNotFoundError(project_id)
        readme = self.projects_dir / project_id / "README.md"
        meta, body = load_markdown(readme)
        for key in ("name", "status", "color", "workflow_template", "issue_status_order", "todo_status_order", "idea_status_order", "mixed_status_order", "issue_record_sort", "todo_record_sort", "idea_record_sort", "info_record_sort", "mixed_record_sort", "issue_record_order", "todo_record_order", "idea_record_order", "info_record_order", "mixed_record_order", "issue_status_record_sorts", "todo_status_record_sorts", "idea_status_record_sorts", "mixed_status_record_sorts"):
            if key in payload:
                if key == "name" and not str(payload[key]).strip():
                    raise ValueError("项目名称不能为空")
                if key.endswith("_order") and (not isinstance(payload[key], list) or any(not isinstance(item, str) for item in payload[key])):
                    raise ValueError("顺序必须是字符串列表")
                if key.endswith("_record_sort") and payload[key] not in {"manual", "updated", "priority", "due", "title", "created"}:
                    raise ValueError("不支持的记录排序规则")
                if key.endswith("_status_record_sorts") and (not isinstance(payload[key], dict) or any(not isinstance(status, str) or mode not in {"manual", "updated", "priority", "due", "title", "created"} for status, mode in payload[key].items())):
                    raise ValueError("不支持的状态记录排序设置")
                meta[key] = payload[key]
        meta["updated"] = now_iso()
        description = payload.get("description", project.get("description", ""))
        body = f"# {meta['name']}\n\n{str(description).strip()}"
        readme.write_text(dump_markdown(meta, body), encoding="utf-8")
        return {**meta, "description": description, "path": str(readme.parent)}

    def _trash_index(self) -> dict:
        return json.loads((self.trash_dir / "index.json").read_text(encoding="utf-8"))

    def _write_trash_index(self, index: dict):
        (self.trash_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    def _move_to_trash(self, source: Path, item_id: str, kind: str, title: str) -> dict:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        token = f"{kind}-{stamp}-{slugify(item_id)}"
        destination = self.trash_dir / token
        shutil.move(str(source), str(destination))
        index = self._trash_index()
        index[token] = {"token": token, "id": item_id, "kind": kind, "title": title, "deleted_at": now_iso(), "original_path": str(source), "trash_path": str(destination)}
        self._write_trash_index(index)
        return index[token]

    def delete_project(self, project_id: str) -> dict:
        project = self.project(project_id)
        if not project:
            raise FileNotFoundError(project_id)
        return self._move_to_trash(self.projects_dir / project_id, project_id, "project", project["name"])

    def list_trash(self) -> list[dict]:
        index = self._trash_index()
        valid = [item for item in index.values() if Path(item["trash_path"]).exists()]
        return sorted(valid, key=lambda item: item["deleted_at"], reverse=True)

    def cleanup_trash(self, retention_days: int = 30):
        cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86400
        for item in list(self.list_trash()):
            try:
                deleted = datetime.fromisoformat(item["deleted_at"]).timestamp()
            except (ValueError, TypeError):
                continue
            if deleted < cutoff:
                self.purge_trash(item["token"])

    def restore_trash(self, token: str) -> dict:
        index = self._trash_index()
        item = index.get(token)
        if not item:
            raise FileNotFoundError(token)
        source = Path(item["trash_path"]).resolve()
        if not source.is_relative_to(self.trash_dir) or not source.exists():
            raise FileNotFoundError(token)
        destination = Path(item["original_path"])
        if destination.exists():
            destination = destination.with_name(f"{destination.stem}-restored-{datetime.now().strftime('%H%M%S')}{destination.suffix}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        del index[token]
        self._write_trash_index(index)
        return {**item, "restored_path": str(destination)}

    def purge_trash(self, token: str) -> dict:
        index = self._trash_index()
        item = index.get(token)
        if not item:
            raise FileNotFoundError(token)
        target = Path(item["trash_path"]).resolve()
        if not target.is_relative_to(self.trash_dir):
            raise ValueError("回收站路径无效")
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        del index[token]
        self._write_trash_index(index)
        return {"token": token, "purged": True}

    @staticmethod
    def _trash_tokens(payload: dict) -> list[str]:
        tokens = payload.get("tokens", [])
        if not isinstance(tokens, list):
            raise ValueError("回收站项目列表无效")
        cleaned = list(dict.fromkeys(str(token) for token in tokens if str(token).strip()))
        if not cleaned:
            raise ValueError("请选择回收站内容")
        return cleaned

    def batch_restore_trash(self, payload: dict) -> dict:
        tokens = self._trash_tokens(payload)
        index = self._trash_index()
        missing = [token for token in tokens if token not in index]
        if missing:
            raise FileNotFoundError(missing[0])
        restored = [self.restore_trash(token) for token in tokens]
        return {"restored": restored, "count": len(restored)}

    def batch_purge_trash(self, payload: dict) -> dict:
        tokens = self._trash_tokens(payload)
        index = self._trash_index()
        missing = [token for token in tokens if token not in index]
        if missing:
            raise FileNotFoundError(missing[0])
        purged = [self.purge_trash(token) for token in tokens]
        return {"purged": purged, "count": len(purged)}

    def list_documents(self) -> list[dict]:
        return self._document_repository.list_documents()

    @staticmethod
    def _concept_map_number(value, default=0.0) -> float:
        return ConceptMapRepository.concept_map_number(value, default)

    def _normalize_concept_map(self, payload: dict, current: dict | None = None) -> dict:
        return self._concept_map_repository.normalize(payload, current)

    def list_concept_maps(self) -> list[dict]:
        return self._concept_map_repository.list()

    def concept_map_categories(self) -> list[str]:
        return self._concept_map_repository.categories()

    def save_concept_map_categories(self, categories: list) -> list[str]:
        return self._concept_map_repository.save_categories(categories)

    def ensure_concept_map_category(self, category: str) -> str:
        return self._concept_map_repository.ensure_category(category)

    def rename_concept_map_category(self, old_name: str, new_name: str) -> dict:
        return self._concept_map_repository.rename_category(old_name, new_name)

    def delete_concept_map_category(self, name: str) -> dict:
        return self._concept_map_repository.delete_category(name)

    def get_concept_map(self, map_id: str) -> tuple[dict, Path] | tuple[None, None]:
        return self._concept_map_repository.get(map_id)

    def _write_concept_map(self, path: Path, item: dict) -> dict:
        return self._concept_map_repository.write(path, item)

    def create_concept_map(self, payload: dict) -> dict:
        return self._concept_map_repository.create(payload)

    def update_concept_map(self, map_id: str, payload: dict) -> dict:
        return self._concept_map_repository.update(map_id, payload)

    def delete_concept_map(self, map_id: str) -> dict:
        return self._concept_map_repository.delete(map_id)

    def get_document(self, document_id: str) -> tuple[dict, Path] | tuple[None, None]:
        return self._document_repository.get_document(document_id)

    def list_reference_targets(self) -> list[dict]:
        return self._document_repository.list_reference_targets()

    def list_document_backlinks(self, document_id: str) -> list[dict]:
        return self._document_repository.list_document_backlinks(document_id)

    def create_document(self, payload: dict) -> dict:
        return self._document_repository.create_document(payload)

    def update_document(self, document_id: str, payload: dict) -> dict:
        return self._document_repository.update_document(document_id, payload)

    def open_document_external(self, document_id: str) -> dict:
        return self._document_repository.open_document_external(document_id)

    def delete_document(self, document_id: str) -> dict:
        return self._document_repository.delete_document(document_id)

    def import_document(self, payload: dict) -> dict:
        return self._document_repository.import_document(payload)

    def export_document(self, document_id: str) -> tuple[bytes, str]:
        return self._document_repository.export_document(document_id)

    def export_documents_zip(self, document_ids: list[str] | None = None) -> bytes:
        return self._document_repository.export_documents_zip(document_ids)

    def export_zip(self, project_id: str | None = None) -> bytes:
        source = self.root
        if project_id:
            project = self.project(project_id)
            if not project:
                raise FileNotFoundError(project_id)
            source = self.projects_dir / project_id
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in source.rglob("*"):
                if path.is_file() and not path.is_relative_to(self.trash_dir):
                    archive.write(path, path.relative_to(source))
        return memory.getvalue()

    def import_markdown(self, payload: dict) -> dict:
        content = str(payload.get("content", ""))
        meta, body = load_markdown_text(content)
        record_type = payload.get("type") or meta.get("type") or "idea"
        title = payload.get("title") or meta.get("title")
        if not title:
            heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            title = heading.group(1).strip() if heading else Path(payload.get("name", "导入记录.md")).stem
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
                meta, body = load_markdown(path)
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

    def list_record_summaries(self, project_id=None, record_type=None) -> list[dict]:
        """Return list-view data without transferring full Markdown bodies."""
        summaries = []
        for record in self.list_records(project_id, record_type):
            summary = {
                key: value for key, value in record.items()
                if key not in {"body", "attachments", "file_path"}
            }
            summary["body_preview"] = str(record.get("body", ""))[:600]
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
            path.write_text(dump_markdown(meta, body), encoding="utf-8")
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
        path.write_text(dump_markdown(updated, body), encoding="utf-8")
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
            destination.write_text(dump_markdown(metadata, body), encoding="utf-8")
        except Exception:
            shutil.move(str(destination), str(source))
            raise
        return self._load_record(destination)

    def open_record_external(self, record_id: str) -> dict:
        record, path = self.get_record(record_id)
        if not record or not path:
            raise FileNotFoundError(record_id)
        editor = open_markdown_external(path)
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
            meta, body = load_markdown(path)
            versions.append({"version": path.stem, "updated": meta.get("updated"), "title": meta.get("title"), "status": meta.get("status"), "preview": body[:180]})
        return versions

    def restore_history(self, record_id: str, version: str) -> dict:
        if not re.fullmatch(r"\d{8}-\d{6}-\d{6}", version):
            raise ValueError("历史版本标识无效")
        source = self.history_dir / record_id / f"{version}.md"
        current, current_path = self.get_record(record_id)
        if not current or not source.exists():
            raise FileNotFoundError(record_id)
        restored_meta, restored_body = load_markdown(source)
        payload = {key: value for key, value in restored_meta.items() if key not in {"id", "type", "project_id", "created", "updated"}}
        payload["body"] = restored_body
        return self.update_record(record_id, payload)

    def add_attachment(self, record_id: str, filename: str, encoded_content: str) -> dict:
        return self._attachment_repository.add_attachment(record_id, filename, encoded_content)

    def _record_attachment_target(self, record: dict, filename: str) -> Path:
        return self._attachment_repository._record_attachment_target(record, filename)

    def _register_record_attachment(self, record: dict, record_path: Path, candidate: Path, size: int, append_to_body: bool = True) -> dict:
        return self._attachment_repository._register_record_attachment(record, record_path, candidate, size, append_to_body)

    def add_record_attachment_stream(self, record_id: str, filename: str, stream, length: int, append_to_body: bool = True) -> dict:
        return self._attachment_repository.add_record_attachment_stream(record_id, filename, stream, length, append_to_body)

    def attachment_path(self, record_id: str, filename: str) -> Path | None:
        return self._attachment_repository.attachment_path(record_id, filename)

    def _project_asset_index(self, project_id: str) -> Path:
        return self._attachment_repository._project_asset_index(project_id)

    def project_assets(self, project_id: str) -> list[dict]:
        return self._attachment_repository.project_assets(project_id)

    def project_asset_categories(self, project_id: str) -> list[dict]:
        return self._attachment_repository.project_asset_categories(project_id)

    def save_project_asset_categories(self, project_id: str, categories: list[dict]) -> list[dict]:
        return self._attachment_repository.save_project_asset_categories(project_id, categories)

    def ensure_project_asset_category(self, project_id: str, category: str) -> str:
        return self._attachment_repository.ensure_project_asset_category(project_id, category)

    def _save_project_assets(self, project_id: str, items: list[dict]):
        return self._attachment_repository._save_project_assets(project_id, items)

    @staticmethod
    def _asset_category(value: str, allow_empty: bool = False) -> str:
        return AttachmentRepository._asset_category(value, allow_empty)

    def _new_project_asset_target(self, project_id: str, filename: str) -> tuple[Path, str]:
        return self._attachment_repository._new_project_asset_target(project_id, filename)

    def _register_project_asset(self, project_id: str, candidate: Path, size: int, category: str) -> dict:
        return self._attachment_repository._register_project_asset(project_id, candidate, size, category)

    def add_project_asset(self, project_id: str, filename: str, encoded_content: str, category: str = "未分类") -> dict:
        return self._attachment_repository.add_project_asset(project_id, filename, encoded_content, category)

    def add_project_asset_stream(self, project_id: str, filename: str, stream, length: int, category: str = "") -> dict:
        return self._attachment_repository.add_project_asset_stream(project_id, filename, stream, length, category)

    def update_project_asset(self, project_id: str, asset_id: str, payload: dict) -> dict:
        return self._attachment_repository.update_project_asset(project_id, asset_id, payload)

    def delete_project_asset(self, project_id: str, asset_id: str) -> dict:
        return self._attachment_repository.delete_project_asset(project_id, asset_id)

    def project_asset_path(self, project_id: str, asset_id: str) -> Path | None:
        return self._attachment_repository.project_asset_path(project_id, asset_id)

    def update_record_attachment_category(self, record_id: str, filename: str, category: str) -> dict:
        return self._attachment_repository.update_record_attachment_category(record_id, filename, category)

    def delete_record_attachment(self, record_id: str, filename: str) -> dict:
        return self._attachment_repository.delete_record_attachment(record_id, filename)

    def batch_update_assets(self, project_id: str, selections: list[dict], category: str) -> dict:
        return self._attachment_repository.batch_update_assets(project_id, selections, category)

    def batch_delete_assets(self, project_id: str, selections: list[dict]) -> dict:
        return self._attachment_repository.batch_delete_assets(project_id, selections)

    def orphan_assets(self) -> list[dict]:
        return self._attachment_repository.orphan_assets()

    def cleanup_orphan_assets(self) -> dict:
        return self._attachment_repository.cleanup_orphan_assets()

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

    def seed_demo(self):
        if self.list_projects():
            return
        website = self.create_project({"name": "网站重构", "description": "重构官网核心流程，提升访问速度和内容维护效率。", "color": "#4d78e8"})
        delivery = self.create_project({"name": "客户交付平台", "description": "整理客户交付流程与资料。", "color": "#8b65dd"})
        samples = [
            {"type": "issue", "title": "登录页面偶尔请求失败", "project_id": website["id"], "status": "待处理", "priority": "紧急", "tags": ["登录", "前端"], "due": "2026-08-28", "body": "# 登录页面偶尔请求失败\n\n## 问题描述\n\n用户提交登录表单后，偶尔出现接口请求超时。\n\n## 原因分析\n\n待补充。"},
            {"type": "issue", "title": "Markdown 表格导入后格式错乱", "project_id": website["id"], "status": "分析中", "priority": "高", "tags": ["Markdown", "导入"], "body": "# Markdown 表格导入后格式错乱\n\n包含复杂表格时解析结果不符合预期。"},
            {"type": "issue", "title": "全局搜索结果缺少高亮", "project_id": website["id"], "status": "处理中", "priority": "高", "tags": ["搜索", "体验"], "body": "# 全局搜索结果缺少高亮\n\n搜索结果需要突出显示命中的关键词。"},
            {"type": "todo", "title": "完成搜索接口检查", "project_id": website["id"], "status": "进行中", "priority": "高", "due": "2026-08-27", "body": "# 完成搜索接口检查\n\n确认标题、正文与标签都能被检索。"},
            {"type": "todo", "title": "更新项目说明文档", "project_id": delivery["id"], "status": "待办", "priority": "普通", "body": "# 更新项目说明文档"},
            {"type": "idea", "title": "给搜索结果增加快捷预览", "status": "待评估", "priority": "普通", "tags": ["搜索"], "body": "# 给搜索结果增加快捷预览\n\n在搜索结果右侧展示 Markdown 内容片段。"},
        ]
        for sample in samples:
            self.create_record(sample)


class WorkbenchHTTPServer(ThreadingHTTPServer):
    """Use an exclusive port so repeated launches cannot mix server versions."""

    allow_reuse_address = False

    def server_bind(self):
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class WorkbenchHandler(SimpleHTTPRequestHandler):
    repository: Repository
    repository_switch_lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def log_message(self, fmt, *args):
        sys.stdout.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

    def end_headers(self):
        # The app is local and changes frequently. Prevent an old app.js from
        # making newly added navigation items look unresponsive.
        if not urlparse(self.path).path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def _json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, body: bytes, content_type: str, filename: str | None = None):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header("Content-Disposition", f"attachment; filename={filename}")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 15_000_000:
            raise ValueError("请求内容过大")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _route(self):
        parsed = urlparse(self.path)
        return unquote(parsed.path), parse_qs(parsed.query)

    def do_GET(self):
        path, query = self._route()
        if not path.startswith("/api/"):
            return super().do_GET()
        try:
            if path == "/api/health":
                return self._json({"ok": True, "data_dir": str(self.repository.root), "app_version": APP_VERSION})
            if path == "/api/config":
                return self._json(self.repository.config())
            if path == "/api/export-location":
                return self._json(export_location_payload())
            if path == "/api/external-editors":
                return self._json(external_editor_payload())
            if path == "/api/directories":
                return self._json(directory_browser_payload((query.get("path") or [""])[0]))
            if path == "/api/tags":
                return self._json(self.repository.list_tags())
            if path == "/api/trash":
                return self._json(self.repository.list_trash())
            if path.startswith("/api/documents/") and path.endswith("/export"):
                document_id = path.strip("/").split("/")[-2]
                content, filename = self.repository.export_document(document_id)
                return self._bytes(content, "text/markdown; charset=utf-8", filename)
            if path.startswith("/api/documents/") and path.endswith("/backlinks"):
                document_id = path.strip("/").split("/")[-2]
                return self._json(self.repository.list_document_backlinks(document_id))
            if path == "/api/documents":
                return self._json(self.repository.list_documents())
            if path == "/api/reference-targets":
                return self._json(self.repository.list_reference_targets())
            if path.startswith("/api/documents/"):
                document, _ = self.repository.get_document(path.rsplit("/", 1)[-1])
                return self._json(document) if document else self._json({"error": "文档不存在"}, HTTPStatus.NOT_FOUND)
            if path == "/api/concept-maps":
                return self._json(self.repository.list_concept_maps())
            if path == "/api/concept-map-categories":
                return self._json(self.repository.concept_map_categories())
            if path.startswith("/api/concept-maps/"):
                concept_map, _ = self.repository.get_concept_map(path.rsplit("/", 1)[-1])
                return self._json(concept_map) if concept_map else self._json({"error": "概念图不存在"}, HTTPStatus.NOT_FOUND)
            if path == "/api/export":
                project_id = (query.get("project") or [None])[0]
                return self._bytes(self.repository.export_zip(project_id), "application/zip", "workbench-export.zip")
            if path == "/api/orphan-assets":
                return self._json(self.repository.orphan_assets())
            if path == "/api/projects":
                return self._json(self.repository.list_projects())
            if path.startswith("/api/projects/") and path.endswith("/assets"):
                project_id = path.strip("/").split("/")[2]
                return self._json(self.repository.project_assets(project_id))
            if path.startswith("/api/projects/") and path.endswith("/asset-categories"):
                project_id = path.strip("/").split("/")[2]
                return self._json(self.repository.project_asset_categories(project_id))
            if path.startswith("/api/project-assets/"):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    return self._json({"error": "项目附件路径无效"}, HTTPStatus.BAD_REQUEST)
                file_path = self.repository.project_asset_path(parts[2], parts[3])
                if not file_path:
                    return self._json({"error": "项目附件不存在"}, HTTPStatus.NOT_FOUND)
                content = file_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{quote(file_path.name)}")
                self.end_headers()
                return self.wfile.write(content)
            if path == "/api/records":
                loader = self.repository.list_record_summaries if (query.get("summary") or [""])[0] == "1" else self.repository.list_records
                records = loader((query.get("project") or [None])[0], (query.get("type") or [None])[0])
                return self._json([record for record in records if record.get("type") != "idea"])
            if path == "/api/record-signatures":
                return self._json([record for record in self.repository.record_signatures() if record.get("type") != "idea"])
            if path.startswith("/api/records/"):
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[-1] == "history":
                    return self._json(self.repository.list_history(parts[-2]))
                record, _ = self.repository.get_record(parts[-1])
                return self._json(record) if record else self._json({"error": "记录不存在"}, HTTPStatus.NOT_FOUND)
            if path.startswith("/api/attachments/"):
                parts = path.strip("/").split("/", 3)
                if len(parts) != 4:
                    return self._json({"error": "附件路径无效"}, HTTPStatus.BAD_REQUEST)
                file_path = self.repository.attachment_path(parts[2], parts[3])
                if not file_path:
                    return self._json({"error": "附件不存在"}, HTTPStatus.NOT_FOUND)
                content = file_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{quote(file_path.name)}")
                self.end_headers()
                return self.wfile.write(content)
            if path == "/api/search":
                return self._json([record for record in self.repository.search((query.get("q") or [""])[0]) if record.get("type") != "idea"])
            return self._json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            return self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        path, query = self._route()
        try:
            if path == "/api/projects":
                return self._json(self.repository.create_project(self._body()), HTTPStatus.CREATED)
            if path == "/api/documents/export":
                payload = self._body()
                document_ids = payload.get("document_ids", [])
                if not isinstance(document_ids, list) or not document_ids:
                    raise ValueError("请选择需要导出的文档")
                known = {item["id"] for item in self.repository.list_documents()}
                cleaned = list(dict.fromkeys(str(item) for item in document_ids if str(item) in known))
                if not cleaned:
                    raise ValueError("所选文档不存在")
                return self._bytes(self.repository.export_documents_zip(cleaned), "application/zip", "knowledge-documents.zip")
            if path == "/api/documents/import":
                return self._json(self.repository.import_document(self._body()), HTTPStatus.CREATED)
            if path == "/api/documents":
                return self._json(self.repository.create_document(self._body()), HTTPStatus.CREATED)
            if path == "/api/concept-maps":
                return self._json(self.repository.create_concept_map(self._body()), HTTPStatus.CREATED)
            if path.startswith("/api/documents/") and path.endswith("/open-external"):
                document_id = path.strip("/").split("/")[-2]
                return self._json(self.repository.open_document_external(document_id))
            if path.startswith("/api/projects/") and path.endswith("/assets/upload"):
                project_id = path.strip("/").split("/")[2]
                length = int(self.headers.get("Content-Length", "0"))
                filename = (query.get("name") or [""])[0]
                category = (query.get("category") or [""])[0]
                return self._json(self.repository.add_project_asset_stream(project_id, filename, self.rfile, length, category), HTTPStatus.CREATED)
            if path.startswith("/api/projects/") and path.endswith("/assets"):
                project_id = path.strip("/").split("/")[2]
                payload = self._body()
                return self._json(self.repository.add_project_asset(project_id, payload.get("name", ""), payload.get("content", ""), payload.get("category", "未分类")), HTTPStatus.CREATED)
            if path == "/api/records":
                payload = self._body()
                if payload.get("type") == "idea":
                    raise ValueError("想法记录类型已停用，请使用知识库")
                return self._json(self.repository.create_record(payload), HTTPStatus.CREATED)
            if path == "/api/import":
                return self._json(self.repository.import_markdown(self._body()), HTTPStatus.CREATED)
            if path == "/api/export-file":
                payload = self._body()
                return self._json(export_to_saved_location(self.repository, payload.get("project_id"), str(payload.get("filename", ""))))
            if path == "/api/trash/batch/restore":
                return self._json(self.repository.batch_restore_trash(self._body()))
            if path.startswith("/api/trash/") and path.endswith("/restore"):
                token = path.strip("/").split("/")[-2]
                return self._json(self.repository.restore_trash(token))
            if path.startswith("/api/records/"):
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[-1] == "convert":
                    return self._json(self.repository.convert_record(parts[-2], str(self._body().get("type", ""))))
                if len(parts) == 4 and parts[-1] == "open-external":
                    return self._json(self.repository.open_record_external(parts[-2]))
                if len(parts) == 5 and parts[-2:] == ["attachments", "upload"]:
                    length = int(self.headers.get("Content-Length", "0"))
                    filename = (query.get("name") or [""])[0]
                    append_to_body = (query.get("append") or ["1"])[0] != "0"
                    return self._json(self.repository.add_record_attachment_stream(parts[2], filename, self.rfile, length, append_to_body), HTTPStatus.CREATED)
                if len(parts) == 4 and parts[-1] == "attachments":
                    payload = self._body()
                    return self._json(self.repository.add_attachment(parts[-2], payload.get("name", ""), payload.get("content", "")), HTTPStatus.CREATED)
                if len(parts) == 4 and parts[-1] == "restore":
                    return self._json(self.repository.restore_history(parts[-2], self._body().get("version", "")))
            return self._json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            return self._json({"error": f"无法写入该目录：{exc}"}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            return self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_PUT(self):
        path, _ = self._route()
        try:
            if path == "/api/data-directory":
                payload = self._body()
                with self.repository_switch_lock:
                    repository = relocate_repository(
                        self.repository,
                        str(payload.get("path", "")),
                        payload.get("mode", "migrate") == "migrate",
                    )
                    WorkbenchHandler.repository = repository
                return self._json(repository.config())
            if path == "/api/export-location":
                return self._json(save_export_location(str(self._body().get("path", ""))))
            if path == "/api/external-editor":
                payload = self._body()
                return self._json(save_external_editor(str(payload.get("id", "")), str(payload.get("path", ""))))
            if path.startswith("/api/projects/") and path.endswith("/asset-categories"):
                project_id = path.strip("/").split("/")[2]
                return self._json(self.repository.save_project_asset_categories(project_id, self._body().get("categories", [])))
            if path == "/api/project-sort":
                return self._json(self.repository.save_project_sort(self._body()))
            if path == "/api/document-sort":
                return self._json(self.repository.save_document_sort(self._body()))
            if path == "/api/document-categories":
                return self._json(self.repository.save_document_categories(self._body().get("categories", [])))
            if path == "/api/concept-map-categories":
                return self._json(self.repository.save_concept_map_categories(self._body().get("categories", [])))
            if path == "/api/status-templates":
                return self._json(self.repository.save_status_templates(self._body()))
            if path == "/api/workflow-templates":
                return self._json(self.repository.save_workflow_templates(self._body()))
            if path == "/api/tags":
                return self._json(self.repository.save_tags(self._body()))
            return self._json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            return self._json({"error": f"无法使用该目录：{exc}"}, HTTPStatus.BAD_REQUEST)

    def do_PATCH(self):
        path, _ = self._route()
        try:
            if path == "/api/assets/batch":
                payload = self._body()
                return self._json(self.repository.batch_update_assets(str(payload.get("project_id", "")), payload.get("selections", []), str(payload.get("category", ""))))
            if path == "/api/document-categories/rename":
                payload = self._body()
                return self._json(self.repository.rename_document_category(payload.get("old_name", ""), payload.get("new_name", "")))
            if path == "/api/concept-map-categories/rename":
                payload = self._body()
                return self._json(self.repository.rename_concept_map_category(payload.get("old_name", ""), payload.get("new_name", "")))
            if path.startswith("/api/documents/"):
                return self._json(self.repository.update_document(path.rsplit("/", 1)[-1], self._body()))
            if path.startswith("/api/concept-maps/"):
                return self._json(self.repository.update_concept_map(path.rsplit("/", 1)[-1], self._body()))
            if path.startswith("/api/projects/") and "/assets/" in path:
                parts = path.strip("/").split("/")
                if len(parts) != 5:
                    raise ValueError("项目附件路径无效")
                return self._json(self.repository.update_project_asset(parts[2], parts[4], self._body()))
            if path.startswith("/api/records/"):
                return self._json(self.repository.update_record(path.rsplit("/", 1)[-1], self._body()))
            if path.startswith("/api/projects/"):
                return self._json(self.repository.update_project(path.rsplit("/", 1)[-1], self._body()))
            return self._json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except FileNotFoundError:
            return self._json({"error": "记录不存在"}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self):
        path, _ = self._route()
        try:
            if path == "/api/assets/batch":
                payload = self._body()
                return self._json(self.repository.batch_delete_assets(str(payload.get("project_id", "")), payload.get("selections", [])))
            if path.startswith("/api/document-categories/"):
                return self._json(self.repository.delete_document_category(path.rsplit("/", 1)[-1]))
            if path.startswith("/api/concept-map-categories/"):
                return self._json(self.repository.delete_concept_map_category(path.rsplit("/", 1)[-1]))
            if path.startswith("/api/documents/"):
                return self._json(self.repository.delete_document(path.rsplit("/", 1)[-1]))
            if path.startswith("/api/concept-maps/"):
                return self._json(self.repository.delete_concept_map(path.rsplit("/", 1)[-1]))
            if path == "/api/trash/batch":
                return self._json(self.repository.batch_purge_trash(self._body()))
            if path.startswith("/api/records/"):
                return self._json(self.repository.delete_record(path.rsplit("/", 1)[-1]))
            if path.startswith("/api/projects/"):
                return self._json(self.repository.delete_project(path.rsplit("/", 1)[-1]))
            if path.startswith("/api/trash/"):
                return self._json(self.repository.purge_trash(path.rsplit("/", 1)[-1]))
            if path == "/api/orphan-assets":
                return self._json(self.repository.cleanup_orphan_assets())
            return self._json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except FileNotFoundError:
            return self._json({"error": "记录不存在"}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            return self._json({"error": f"附件删除失败：{exc}"}, HTTPStatus.BAD_REQUEST)


def windows_listener_pids(port: int) -> set[int]:
    """Return Windows PIDs listening on the selected local port."""
    if sys.platform != "win32":
        return set()
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True,
        encoding="utf-8", errors="ignore", check=False,
    )
    pids = set()
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) < 5 or columns[0].upper() != "TCP" or columns[-2].upper() != "LISTENING":
            continue
        local_address = columns[1].rsplit(":", 1)
        if len(local_address) == 2 and local_address[-1] == str(port) and columns[-1].isdigit():
            pids.add(int(columns[-1]))
    return pids


def replace_existing_workbench(host: str, port: int, data_dir: Path) -> bool:
    """Stop stale copies only after confirming the port serves this data directory."""
    pids = windows_listener_pids(port)
    if not pids:
        return False
    try:
        from urllib.request import urlopen
        with urlopen(f"http://{host}:{port}/api/health", timeout=2) as response:
            health = json.loads(response.read().decode("utf-8"))
    except Exception:
        return False
    if Path(health.get("data_dir", "")).resolve() != data_dir.resolve():
        return False
    if len(pids) == 1 and health.get("app_version") == APP_VERSION:
        return True
    print(f"检测到 {len(pids)} 个旧工作台服务，正在安全重启……")
    for pid in pids:
        if pid != os.getpid():
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
    for _ in range(30):
        if not windows_listener_pids(port):
            break
        time.sleep(0.1)
    return False


def main():
    parser = argparse.ArgumentParser(description="本地工作台服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--seed-demo", action="store_true", help="数据为空时创建演示项目和记录")
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    parser.add_argument("--replace", action="store_true", help="启动时替换同一数据目录的旧工作台服务")
    args = parser.parse_args()
    repository = Repository(configured_data_dir(args.data_dir))
    if args.seed_demo:
        repository.seed_demo()
    if args.replace and replace_existing_workbench(args.host, args.port, repository.root):
        print(f"本地工作台已在运行：http://{args.host}:{args.port}")
        if args.open:
            webbrowser.open(f"http://{args.host}:{args.port}/?session={int(time.time())}")
        return
    WorkbenchHandler.repository = repository
    server = WorkbenchHTTPServer((args.host, args.port), WorkbenchHandler)
    print(f"本地工作台已启动：http://{args.host}:{args.port}")
    print(f"Markdown 数据目录：{repository.root}")
    if args.open:
        session_url = f"http://{args.host}:{args.port}/?session={int(time.time())}"
        threading.Timer(0.35, lambda: webbrowser.open(session_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")


if __name__ == "__main__":
    main()
