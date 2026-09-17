"""Compatibility repository facade that composes the domain repositories."""

from __future__ import annotations

import io
import json
import shutil
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .assets import AttachmentRepository
from .concept_maps import ConceptMapRepository
from .configuration import ConfigurationRepository
from .documents import DocumentRepository
from .external_editor import open_markdown_external
from .markdown_io import load_markdown, now_iso, slugify
from .projects import ProjectRepository
from .persistence import atomic_write_json
from .records import RecordRepository
from .security import archive_name_for, validate_zip_bytes


class Repository:
    def __init__(
        self,
        data_dir: Path,
        load_markdown_callback=load_markdown,
        open_markdown_external_callback=open_markdown_external,
    ):
        self.root = data_dir.resolve()
        self._record_id_lock = threading.Lock()
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
        self._record_repository = RecordRepository(
            self.global_ideas_dir,
            self.projects_dir,
            self.history_dir,
            self._record_id_lock,
            lambda path: load_markdown_callback(path),
            self.project,
            self.list_projects,
            lambda path: open_markdown_external_callback(path),
            self._move_to_trash,
        )
        self._record_cache_lock = self._record_repository._record_cache_lock
        self._record_cache = self._record_repository._record_cache
        self._record_paths_by_id = self._record_repository._record_paths_by_id
        self._project_repository = ProjectRepository(
            self.projects_dir,
            lambda path: load_markdown_callback(path),
            self.project_sort,
            self.save_project_sort,
            self.list_records,
            self._move_to_trash,
        )
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
            lambda path: open_markdown_external_callback(path),
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
        atomic_write_json(settings, {"version": 1, "data_dir": str(self.root)})
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
            atomic_write_json(templates, data)
        workflows = self.config_dir / "workflow-templates.json"
        if not workflows.exists():
            default_statuses = json.loads(templates.read_text(encoding="utf-8"))
            atomic_write_json(workflows, [{"id": "standard", "name": "标准工作流", "statuses": default_statuses}])
        labels = self.config_dir / "labels.json"
        if not labels.exists():
            atomic_write_json(labels, [])
        project_sort = self.config_dir / "project-sort.json"
        if not project_sort.exists():
            atomic_write_json(project_sort, {"mode": "custom", "order": []})
        document_sort = self.config_dir / "document-sort.json"
        if not document_sort.exists():
            atomic_write_json(document_sort, {"category_mode": "manual", "category_order": [], "file_mode": "updated", "file_modes": {}, "file_orders": {}})
        document_categories = self.config_dir / "document-categories.json"
        if not document_categories.exists():
            atomic_write_json(document_categories, [])
        concept_map_categories = self.config_dir / "concept-map-categories.json"
        if not concept_map_categories.exists():
            atomic_write_json(concept_map_categories, [])
        trash_index = self.trash_dir / "index.json"
        if not trash_index.exists():
            atomic_write_json(trash_index, {})

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
        return self._project_repository._unsorted_projects()

    def list_projects(self) -> list[dict]:
        return self._project_repository.list_projects()

    def project(self, project_id: str) -> dict | None:
        return self._project_repository.project(project_id)

    def create_project(self, payload: dict) -> dict:
        return self._project_repository.create_project(payload)

    def update_project(self, project_id: str, payload: dict) -> dict:
        return self._project_repository.update_project(project_id, payload)

    def _trash_index(self) -> dict:
        return json.loads((self.trash_dir / "index.json").read_text(encoding="utf-8"))

    def _write_trash_index(self, index: dict):
        atomic_write_json(self.trash_dir / "index.json", index)

    def _move_to_trash(self, source: Path, item_id: str, kind: str, title: str) -> dict:
        source = source.resolve()
        if source == self.root or not source.is_relative_to(self.root) or source.is_relative_to(self.trash_dir) or not source.exists():
            raise ValueError("待删除路径无效")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        token = f"{kind}-{stamp}-{slugify(item_id)}"
        destination = self.trash_dir / token
        shutil.move(str(source), str(destination))
        index = self._trash_index()
        index[token] = {"token": token, "id": item_id, "kind": kind, "title": title, "deleted_at": now_iso(), "original_path": str(source), "trash_path": str(destination)}
        self._write_trash_index(index)
        return index[token]

    def delete_project(self, project_id: str) -> dict:
        return self._project_repository.delete_project(project_id)

    def list_trash(self) -> list[dict]:
        index = self._trash_index()
        valid = []
        for item in index.values():
            try:
                if not isinstance(item, dict):
                    continue
                path = Path(item["trash_path"]).resolve()
                if path.parent == self.trash_dir and path.exists():
                    valid.append(item)
            except (KeyError, OSError, TypeError):
                continue
        return sorted(valid, key=lambda item: str(item.get("deleted_at", "")), reverse=True)

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
        if source.parent != self.trash_dir or not source.exists():
            raise FileNotFoundError(token)
        destination = Path(item["original_path"]).resolve()
        if not destination.is_relative_to(self.root) or destination.is_relative_to(self.trash_dir):
            raise ValueError("回收站恢复路径无效")
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
        if target.parent != self.trash_dir:
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

    def document_signatures(self) -> list[dict]:
        return self._document_repository.document_signatures()

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
        excluded_files = {(self.config_dir / "settings.json").resolve()}
        if project_id:
            project = self.project(project_id)
            if not project:
                raise FileNotFoundError(project_id)
            source = self.projects_dir / project_id
            excluded_files = set()
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in source.rglob("*"):
                if not path.is_file() or path.is_symlink():
                    continue
                resolved = path.resolve()
                if resolved.is_relative_to(self.trash_dir) or resolved in excluded_files or path.name.startswith(".workbench-"):
                    continue
                archive_name = archive_name_for(source, path)
                if archive_name:
                    archive.write(path, archive_name)
        return validate_zip_bytes(memory.getvalue())

    def import_markdown(self, payload: dict) -> dict:
        return self._record_repository.import_markdown(payload)

    def _record_paths(self):
        return self._record_repository._record_paths()

    def _load_record(self, path: Path) -> dict | None:
        return self._record_repository._load_record(path)

    def _forget_record(self, path: Path):
        return self._record_repository._forget_record(path)

    def list_records(self, project_id=None, record_type=None) -> list[dict]:
        return self._record_repository.list_records(project_id, record_type)

    def list_record_summaries(self, project_id=None, record_type=None, record_ids=None) -> list[dict]:
        return self._record_repository.list_record_summaries(project_id, record_type, record_ids)

    def record_signatures(self) -> list[dict]:
        return self._record_repository.record_signatures()

    def get_record(self, record_id: str) -> tuple[dict, Path] | tuple[None, None]:
        return self._record_repository.get_record(record_id)

    def _next_id(self, record_type: str) -> str:
        return self._record_repository._next_id(record_type)

    def create_record(self, payload: dict) -> dict:
        return self._record_repository.create_record(payload)

    def update_record(self, record_id: str, payload: dict) -> dict:
        return self._record_repository.update_record(record_id, payload)

    def convert_record(self, record_id: str, target_type: str) -> dict:
        return self._record_repository.convert_record(record_id, target_type)

    def open_record_external(self, record_id: str) -> dict:
        return self._record_repository.open_record_external(record_id)

    def _save_history(self, record_id: str, source: Path):
        return self._record_repository._save_history(record_id, source)

    def list_history(self, record_id: str) -> list[dict]:
        return self._record_repository.list_history(record_id)

    def restore_history(self, record_id: str, version: str) -> dict:
        return self._record_repository.restore_history(record_id, version)

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
        return self._record_repository.delete_record(record_id)

    def search(self, query: str) -> list[dict]:
        return self._record_repository.search(query)

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
