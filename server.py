"""Zero-dependency local server and Markdown repository for 本地工作台."""

from __future__ import annotations

import argparse
import ast
import base64
import io
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse


APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = APP_DIR / "workbench-data"
LOCATION_FILE = APP_DIR / ".workbench-location.json"
EXPORT_LOCATION_FILE = APP_DIR / ".workbench-export.json"
EXTERNAL_EDITOR_FILE = APP_DIR / ".workbench-editor.json"
APP_VERSION = "2026.08.31.3"
TYPE_DIRS = {"issue": "issues", "todo": "todos", "idea": "ideas", "info": "infos"}
TYPE_PREFIXES = {"issue": "ISSUE", "todo": "TODO", "idea": "IDEA", "info": "INFO"}


def _environment_path(variable: str, *parts: str) -> str | None:
    root = os.environ.get(variable)
    return str(Path(root, *parts)) if root else None


def detected_external_editors() -> list[dict]:
    definitions = [
        ("typora", "Typora", [os.environ.get("TYPORA_PATH"), shutil.which("Typora.exe"), shutil.which("Typora"), _environment_path("LOCALAPPDATA", "Programs", "Typora", "Typora.exe"), _environment_path("LOCALAPPDATA", "Typora", "Typora.exe"), _environment_path("PROGRAMFILES", "Typora", "Typora.exe"), _environment_path("PROGRAMFILES(X86)", "Typora", "Typora.exe")]),
        ("vscode", "Visual Studio Code", [shutil.which("Code.exe"), _environment_path("LOCALAPPDATA", "Programs", "Microsoft VS Code", "Code.exe"), _environment_path("PROGRAMFILES", "Microsoft VS Code", "Code.exe"), shutil.which("code")]),
        ("obsidian", "Obsidian", [shutil.which("Obsidian.exe"), shutil.which("obsidian"), _environment_path("LOCALAPPDATA", "Obsidian", "Obsidian.exe"), _environment_path("LOCALAPPDATA", "Programs", "Obsidian", "Obsidian.exe")]),
        ("notepadpp", "Notepad++", [shutil.which("notepad++.exe"), _environment_path("PROGRAMFILES", "Notepad++", "notepad++.exe"), _environment_path("PROGRAMFILES(X86)", "Notepad++", "notepad++.exe")]),
        ("sublime", "Sublime Text", [shutil.which("sublime_text.exe"), shutil.which("subl"), _environment_path("PROGRAMFILES", "Sublime Text", "sublime_text.exe")]),
        ("marktext", "MarkText", [shutil.which("MarkText.exe"), shutil.which("marktext"), _environment_path("LOCALAPPDATA", "Programs", "MarkText", "MarkText.exe")]),
        ("zettlr", "Zettlr", [shutil.which("Zettlr.exe"), shutil.which("zettlr"), _environment_path("LOCALAPPDATA", "Programs", "Zettlr", "Zettlr.exe")]),
    ]
    editors = []
    for editor_id, name, candidates in definitions:
        executable = next((Path(candidate).resolve() for candidate in candidates if candidate and Path(candidate).is_file()), None)
        if executable:
            editors.append({"id": editor_id, "name": name, "path": str(executable), "kind": "detected"})
    editors.append({"id": "system", "name": "系统默认 Markdown 编辑器", "path": "", "kind": "system"})
    return editors


def external_editor_payload(config_file: Path = EXTERNAL_EDITOR_FILE) -> dict:
    try:
        selected = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        selected = {}
    editors = detected_external_editors()
    custom_path = str(selected.get("path", "")).strip()
    if selected.get("id") == "custom" and custom_path and Path(custom_path).is_file():
        editors.insert(0, {"id": "custom", "name": selected.get("name") or Path(custom_path).stem, "path": str(Path(custom_path).resolve()), "kind": "custom"})
    available_ids = {editor["id"] for editor in editors}
    selected_id = selected.get("id") if selected.get("id") in available_ids else ("typora" if "typora" in available_ids else "system")
    selected_editor = next(editor for editor in editors if editor["id"] == selected_id)
    return {"selected": selected_id, "selected_name": selected_editor["name"], "editors": editors}


def save_external_editor(editor_id: str, custom_path: str = "", config_file: Path = EXTERNAL_EDITOR_FILE) -> dict:
    editor_id = str(editor_id or "").strip()
    if editor_id == "custom":
        executable = Path(str(custom_path or "").strip()).expanduser()
        if not executable.is_file():
            raise ValueError("自定义编辑器程序不存在，请填写可执行程序的完整路径")
        config = {"id": "custom", "name": executable.stem, "path": str(executable.resolve())}
    else:
        editor = next((item for item in detected_external_editors() if item["id"] == editor_id), None)
        if not editor:
            raise ValueError("所选编辑器当前不可用")
        config = {"id": editor["id"], "name": editor["name"], "path": editor["path"]}
    config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return external_editor_payload(config_file)


def open_markdown_external(path: Path, config_file: Path = EXTERNAL_EDITOR_FILE) -> str:
    payload = external_editor_payload(config_file)
    editor = next(item for item in payload["editors"] if item["id"] == payload["selected"])
    if editor["kind"] != "system":
        subprocess.Popen([editor["path"], str(path)], cwd=str(path.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return editor["name"]
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return editor["name"]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def slugify(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "-", value.strip())
    value = re.sub(r"\s+", "-", value).strip(".- ")
    return value[:80] or "untitled"


def yaml_scalar(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(str(value), ensure_ascii=False)


def dump_markdown(meta: dict, body: str) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {yaml_scalar(item)}" for item in value)
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.extend(["---", "", body.strip(), ""])
    return "\n".join(lines)


def parse_scalar(value: str):
    value = value.strip()
    if value == "null":
        return None
    if value in {"true", "false"}:
        return value == "true"
    try:
        parsed = json.loads(value)
        # 兼容旧版本把字典先转成 Python 字符串、再包成 JSON 字符串的格式。
        if isinstance(parsed, str) and parsed.startswith("{") and parsed.endswith("}"):
            try:
                legacy = ast.literal_eval(parsed)
                if isinstance(legacy, dict):
                    return legacy
            except (ValueError, SyntaxError):
                pass
        return parsed
    except (json.JSONDecodeError, TypeError):
        return value


def normalize_info_fields(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    fields = []
    for item in value[:100]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()[:120]
        content = str(item.get("value", "")).strip()
        note = str(item.get("note", "")).strip()
        if name or content:
            field = {"name": name or "未命名字段", "value": content}
            if note:
                field["note"] = note
            fields.append(field)
    return fields


def load_markdown(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    return load_markdown_text(text)


def load_markdown_text(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    try:
        raw_meta, body = text[4:].split("\n---\n", 1)
    except ValueError:
        return {}, text
    meta, current_list = {}, None
    for line in raw_meta.splitlines():
        if line.startswith("  - ") and current_list:
            meta[current_list].append(parse_scalar(line[4:]))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value:
            meta[key], current_list = parse_scalar(value), None
        else:
            meta[key], current_list = [], key
    return meta, body.strip()


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
        self.trash_dir = self.root / ".trash"
        self.history_dir = self.root / "history"
        self.config_dir = self.root / "config"
        for directory in (self.projects_dir, self.global_ideas_dir, self.global_assets_dir, self.documents_dir, self.trash_dir, self.history_dir, self.config_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self._ensure_config()
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
        trash_index = self.trash_dir / "index.json"
        if not trash_index.exists():
            trash_index.write_text("{}", encoding="utf-8")

    def config(self) -> dict:
        return {
            "data_dir": str(self.root),
            "status_templates": json.loads((self.config_dir / "status-templates.json").read_text(encoding="utf-8")),
            "workflow_templates": json.loads((self.config_dir / "workflow-templates.json").read_text(encoding="utf-8")),
            "tags": self.list_tags(),
            "project_sort": self.project_sort(),
            "document_sort": self.document_sort(),
            "document_categories": self.document_categories(),
        }

    def project_sort(self) -> dict:
        path = self.config_dir / "project-sort.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {"mode": "custom", "order": []}
        return {"mode": value.get("mode", "custom"), "order": value.get("order", []) if isinstance(value.get("order", []), list) else []}

    def save_project_sort(self, payload: dict) -> dict:
        modes = {"custom", "updated", "name", "created", "record_count"}
        mode = str(payload.get("mode", "custom"))
        order = payload.get("order", [])
        if mode not in modes:
            raise ValueError("项目排序规则无效")
        if not isinstance(order, list) or any(not isinstance(item, str) for item in order):
            raise ValueError("项目顺序必须是项目编号列表")
        known = [project["id"] for project in sorted(self._unsorted_projects(), key=lambda item: item.get("created", ""))]
        known_set = set(known)
        cleaned = list(dict.fromkeys(item for item in order if item in known_set))
        cleaned.extend(project_id for project_id in known if project_id not in cleaned)
        value = {"mode": mode, "order": cleaned}
        (self.config_dir / "project-sort.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return value

    def document_sort(self) -> dict:
        path = self.config_dir / "document-sort.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        category_mode = value.get("category_mode", "manual")
        file_mode = value.get("file_mode", value.get("mode", "updated"))
        if category_mode not in {"manual", "name", "count", "updated"}:
            category_mode = "manual"
        if file_mode not in {"manual", "updated", "title", "created"}:
            file_mode = "updated"
        file_orders = value.get("file_orders", {})
        if not isinstance(file_orders, dict):
            file_orders = {}
        file_modes = value.get("file_modes", {})
        if not isinstance(file_modes, dict):
            file_modes = {}
        result = {
            "category_mode": category_mode,
            "category_order": value.get("category_order", []) if isinstance(value.get("category_order", []), list) else [],
            "file_mode": file_mode,
            "file_modes": {str(key): mode for key, mode in file_modes.items() if mode in {"manual", "updated", "title", "created"}},
            "file_orders": {str(key): order for key, order in file_orders.items() if isinstance(order, list)},
        }
        legacy_order = value.get("order", []) if isinstance(value.get("order", []), list) else []
        if legacy_order:
            result["legacy_order"] = legacy_order
        return result

    def save_document_sort(self, payload: dict) -> dict:
        current = self.document_sort()
        category_mode = str(payload.get("category_mode", current["category_mode"]))
        file_mode = str(payload.get("file_mode", current["file_mode"]))
        if category_mode not in {"manual", "name", "count", "updated"}:
            raise ValueError("分类排序规则无效")
        if file_mode not in {"manual", "updated", "title", "created"}:
            raise ValueError("文档排序规则无效")
        documents = self.list_documents()
        categories = self.document_categories()
        category_order = payload.get("category_order", current["category_order"])
        if not isinstance(category_order, list) or any(not isinstance(item, str) for item in category_order):
            raise ValueError("分类顺序必须是分类名称列表")
        cleaned_categories = list(dict.fromkeys(item for item in category_order if item in categories))
        cleaned_categories.extend(category for category in categories if category not in cleaned_categories)
        incoming_orders = payload.get("file_orders", current["file_orders"])
        if not isinstance(incoming_orders, dict):
            raise ValueError("文档顺序格式无效")
        incoming_modes = payload.get("file_modes", current.get("file_modes", {}))
        if not isinstance(incoming_modes, dict) or any(mode not in {"manual", "updated", "title", "created"} for mode in incoming_modes.values()):
            raise ValueError("分类内文档排序规则无效")
        legacy_order = current.get("legacy_order", [])
        cleaned_orders = {}
        for category in categories:
            known = [document["id"] for document in documents if str(document.get("category") or "未分类") == category]
            order = incoming_orders.get(category, legacy_order)
            if not isinstance(order, list) or any(not isinstance(item, str) for item in order):
                raise ValueError("文档顺序必须是文档编号列表")
            cleaned = list(dict.fromkeys(item for item in order if item in known))
            cleaned.extend(document_id for document_id in known if document_id not in cleaned)
            cleaned_orders[category] = cleaned
        cleaned_modes = {category: incoming_modes.get(category, file_mode) for category in categories}
        value = {"category_mode": category_mode, "category_order": cleaned_categories, "file_mode": file_mode, "file_modes": cleaned_modes, "file_orders": cleaned_orders}
        (self.config_dir / "document-sort.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return value

    def document_categories(self) -> list[str]:
        path = self.config_dir / "document-categories.json"
        try:
            configured = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            configured = []
        if not isinstance(configured, list):
            configured = []
        categories = list(dict.fromkeys(str(item).strip() for item in configured if str(item).strip()))
        for document in self.list_documents():
            category = str(document.get("category") or "未分类").strip() or "未分类"
            if category not in categories:
                categories.append(category)
        return categories

    def save_document_categories(self, categories: list) -> list[str]:
        if not isinstance(categories, list):
            raise ValueError("文档分类格式无效")
        cleaned = []
        for value in categories:
            name = str(value).strip()
            if not name:
                continue
            if len(name) > 80:
                raise ValueError("分类名称不能超过 80 个字符")
            if name not in cleaned:
                cleaned.append(name)
        for document in self.list_documents():
            category = str(document.get("category") or "未分类").strip() or "未分类"
            if category not in cleaned:
                cleaned.append(category)
        (self.config_dir / "document-categories.json").write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
        return cleaned

    def ensure_document_category(self, category: str) -> str:
        name = str(category or "未分类").strip() or "未分类"
        categories = self.document_categories()
        if name not in categories:
            categories.append(name)
            self.save_document_categories(categories)
        return name

    def rename_document_category(self, old_name: str, new_name: str) -> dict:
        old_name = str(old_name).strip()
        new_name = str(new_name).strip()
        categories = self.document_categories()
        if old_name not in categories:
            raise FileNotFoundError(old_name)
        if not new_name:
            raise ValueError("分类名称不能为空")
        if len(new_name) > 80:
            raise ValueError("分类名称不能超过 80 个字符")
        if new_name != old_name and new_name in categories:
            raise ValueError("分类名称已存在")
        if new_name == old_name:
            return {"categories": categories, "document_sort": self.document_sort(), "updated_documents": 0}
        changed = 0
        for document in self.list_documents():
            if str(document.get("category") or "未分类") != old_name:
                continue
            path = Path(document["file_path"])
            meta = {key: value for key, value in document.items() if key not in {"body", "file_path", "file_mtime"}}
            meta["category"] = new_name
            meta["updated"] = now_iso()
            path.write_text(dump_markdown(meta, document.get("body", "")), encoding="utf-8")
            changed += 1
        renamed_categories = [new_name if category == old_name else category for category in categories]
        saved_categories = self.save_document_categories(renamed_categories)
        sorting = self.document_sort()
        category_order = [new_name if category == old_name else category for category in sorting.get("category_order", [])]
        file_modes = dict(sorting.get("file_modes", {}))
        if old_name in file_modes:
            file_modes[new_name] = file_modes.pop(old_name)
        file_orders = dict(sorting.get("file_orders", {}))
        if old_name in file_orders:
            file_orders[new_name] = file_orders.pop(old_name)
        saved_sort = self.save_document_sort({**sorting, "category_order": category_order, "file_modes": file_modes, "file_orders": file_orders})
        return {"categories": saved_categories, "document_sort": saved_sort, "updated_documents": changed}

    def save_workflow_templates(self, workflows: list[dict]) -> list[dict]:
        if not isinstance(workflows, list) or not workflows:
            raise ValueError("至少需要一套工作流模板")
        ids = set()
        for workflow in workflows:
            if not workflow.get("id") or not workflow.get("name") or workflow["id"] in ids:
                raise ValueError("工作流标识和名称不能为空且标识不能重复")
            ids.add(workflow["id"])
            statuses = workflow.get("statuses", {})
            self._validate_statuses(statuses)

        # 状态名称可以编辑，但记录中保存的是状态名称。用稳定的状态 ID
        # 识别重命名并同步记录，避免改名后记录落入不可见的旧状态。
        try:
            previous = json.loads((self.config_dir / "workflow-templates.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = []
        previous_by_id = {item.get("id"): item for item in previous if isinstance(item, dict)}
        renames: dict[str, dict[str, dict[str, str]]] = {}
        removed_statuses: dict[tuple[str, str, str], str] = {}
        for workflow in workflows:
            old_workflow = previous_by_id.get(workflow["id"])
            if not old_workflow:
                continue
            for record_type in ("issue", "todo", "idea"):
                new_by_id = {item.get("id"): item for item in workflow["statuses"].get(record_type, [])}
                for old_status in old_workflow.get("statuses", {}).get(record_type, []):
                    new_status = new_by_id.get(old_status.get("id"))
                    old_name, new_name = old_status.get("name"), new_status.get("name") if new_status else None
                    if old_name and new_name and old_name != new_name:
                        renames.setdefault(workflow["id"], {}).setdefault(record_type, {})[old_name] = new_name

                    if old_name and not new_status:
                        removed_statuses[(workflow["id"], record_type, old_name)] = old_status.get("id", "")

        previous_ids = {item.get("id") for item in previous if isinstance(item, dict)}
        default_workflow = "standard" if "standard" in previous_ids else (previous[0].get("id") if previous else workflows[0]["id"])
        all_projects = self.list_projects()
        project_workflows = {project["id"]: project.get("workflow_template") or default_workflow for project in all_projects}
        if removed_statuses:
            usage: dict[tuple[str, str, str], list[dict]] = {}
            for record in self.list_records():
                workflow_id = project_workflows.get(record.get("project_id"), default_workflow)
                key = (workflow_id, record.get("type"), record.get("status"))
                if key in removed_statuses:
                    usage.setdefault(key, []).append(record)
            if usage:
                details = []
                for (_, _, status_name), used_records in usage.items():
                    preview = "、".join(f"{item['id']} {item.get('title', '')}" for item in used_records[:5])
                    suffix = f" 等 {len(used_records)} 条" if len(used_records) > 5 else ""
                    details.append(f"状态「{status_name}」正在被使用：{preview}{suffix}")
                raise ValueError("；".join(details) + "。请先把这些记录移动到其他状态")

        (self.config_dir / "workflow-templates.json").write_text(json.dumps(workflows, ensure_ascii=False, indent=2), encoding="utf-8")
        if renames:
            for record in self.list_records():
                workflow_id = project_workflows.get(record.get("project_id"), default_workflow)
                renamed = renames.get(workflow_id, {}).get(record.get("type"), {}).get(record.get("status"))
                if renamed:
                    self.update_record(record["id"], {"status": renamed})
            # 项目中还保存了按状态排序的辅助配置，状态改名时一并更新，
            # 防止产生不可见的旧键或丢失用户已有的排序规则。
            for project in all_projects:
                workflow_renames = renames.get(project_workflows[project["id"]], {})
                changes = {}
                for record_type in ("issue", "todo", "idea"):
                    mapping = workflow_renames.get(record_type, {})
                    if not mapping:
                        continue
                    order_key = f"{record_type}_status_order"
                    sorts_key = f"{record_type}_status_record_sorts"
                    if isinstance(project.get(order_key), list):
                        changes[order_key] = [mapping.get(name, name) for name in project[order_key]]
                    if isinstance(project.get(sorts_key), dict):
                        changes[sorts_key] = {mapping.get(name, name): mode for name, mode in project[sorts_key].items()}
                if changes:
                    self.update_project(project["id"], changes)
        return workflows

    def _validate_statuses(self, templates: dict):
        required = {"issue", "todo", "idea"}
        if not isinstance(templates, dict) or not required.issubset(templates):
            raise ValueError("状态模板必须包含问题、待办和想法")
        for record_type in required:
            if not isinstance(templates[record_type], list) or not templates[record_type]:
                raise ValueError("每种记录至少需要一个状态")
            for status in templates[record_type]:
                if not status.get("id") or not status.get("name"):
                    raise ValueError("状态必须包含标识和名称")

    def list_tags(self) -> list[dict]:
        configured = json.loads((self.config_dir / "labels.json").read_text(encoding="utf-8"))
        known = {item["name"]: item for item in configured if isinstance(item, dict) and item.get("name")}
        colors = ["#4d78e8", "#7856c8", "#2ba477", "#e08b38", "#df4b4b", "#60748a"]
        for record in self.list_records():
            for tag in record.get("tags") or []:
                if tag not in known:
                    known[tag] = {"name": tag, "color": colors[len(known) % len(colors)]}
        for document in self.list_documents():
            for tag in document.get("tags") or []:
                if tag not in known:
                    known[tag] = {"name": tag, "color": colors[len(known) % len(colors)]}
        return sorted(known.values(), key=lambda item: item["name"].casefold())

    def save_tags(self, payload) -> list[dict]:
        renames, removed = {}, []
        if isinstance(payload, dict):
            tags = payload.get("tags", [])
            renames = payload.get("renames", {})
            removed = payload.get("removed", [])
        else:
            tags = payload
        if not isinstance(tags, list):
            raise ValueError("标签数据必须是列表")
        if removed:
            usage = {}
            removed_names = {str(name) for name in removed}
            for record in self.list_records():
                for tag in record.get("tags") or []:
                    if tag in removed_names:
                        usage.setdefault(tag, []).append(record)
            for document in self.list_documents():
                for tag in document.get("tags") or []:
                    if tag in removed_names:
                        usage.setdefault(tag, []).append(document)
            if usage:
                details = []
                for tag, used_records in usage.items():
                    preview = "、".join(f"{item['id']} {item.get('title', '')}" for item in used_records[:5])
                    suffix = f" 等 {len(used_records)} 条" if len(used_records) > 5 else ""
                    details.append(f"标签「{tag}」正在被使用：{preview}{suffix}")
                raise ValueError("；".join(details) + "。请先从这些记录或文档中移除标签")
        cleaned, names = [], set()
        for item in tags:
            name = str(item.get("name", "")).strip()
            if not name or name in names:
                continue
            names.add(name)
            cleaned.append({"name": name, "color": item.get("color", "#60748a")})
        (self.config_dir / "labels.json").write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
        if renames or removed:
            for record in self.list_records():
                old_tags = record.get("tags") or []
                new_tags = []
                for tag in old_tags:
                    if tag in removed:
                        continue
                    renamed = renames.get(tag, tag)
                    if renamed and renamed not in new_tags:
                        new_tags.append(renamed)
                if new_tags != old_tags:
                    self.update_record(record["id"], {"tags": new_tags})
            for document in self.list_documents():
                old_tags = document.get("tags") or []
                new_tags = []
                for tag in old_tags:
                    if tag in removed:
                        continue
                    renamed = renames.get(tag, tag)
                    if renamed and renamed not in new_tags:
                        new_tags.append(renamed)
                if new_tags != old_tags:
                    self.update_document(document["id"], {"tags": new_tags})
        return cleaned

    def save_status_templates(self, templates: dict) -> dict:
        self._validate_statuses(templates)
        path = self.config_dir / "status-templates.json"
        path.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8")
        return templates

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
        documents = []
        for path in self.documents_dir.glob("*.md"):
            meta, body = load_markdown(path)
            if meta.get("type") != "document":
                continue
            meta.pop("document_type", None)
            documents.append({**meta, "body": body, "file_path": str(path), "file_mtime": path.stat().st_mtime_ns})
        return sorted(documents, key=lambda item: item.get("updated", ""), reverse=True)

    def get_document(self, document_id: str) -> tuple[dict, Path] | tuple[None, None]:
        for document in self.list_documents():
            if document.get("id") == document_id:
                return document, Path(document["file_path"])
        return None, None

    def create_document(self, payload: dict) -> dict:
        title = str(payload.get("title", "")).strip()
        if not title:
            raise ValueError("文档标题不能为空")
        used = []
        for document in self.list_documents():
            match = re.fullmatch(r"DOC-(\d+)", str(document.get("id", "")))
            if match:
                used.append(int(match.group(1)))
        document_id = f"DOC-{max(used, default=0) + 1:04d}"
        stamp = now_iso()
        tags = list(dict.fromkeys(str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip())) if isinstance(payload.get("tags", []), list) else []
        category = self.ensure_document_category(str(payload.get("category", "未分类")))
        meta = {"id": document_id, "type": "document", "title": title, "category": category, "tags": tags, "created": stamp, "updated": stamp}
        body = str(payload.get("body", "")).strip() or f"# {title}\n\n"
        path = self.documents_dir / f"{document_id}-{slugify(title)}.md"
        path.write_text(dump_markdown(meta, body), encoding="utf-8")
        return {**meta, "body": body, "file_path": str(path), "file_mtime": path.stat().st_mtime_ns}

    def update_document(self, document_id: str, payload: dict) -> dict:
        document, path = self.get_document(document_id)
        if not document or not path:
            raise FileNotFoundError(document_id)
        title = str(payload.get("title", document.get("title", ""))).strip()
        if not title:
            raise ValueError("文档标题不能为空")
        meta = {key: value for key, value in document.items() if key not in {"body", "file_path", "file_mtime"}}
        tags_payload = payload.get("tags", document.get("tags", []))
        tags = list(dict.fromkeys(str(tag).strip() for tag in tags_payload if str(tag).strip())) if isinstance(tags_payload, list) else document.get("tags", [])
        meta.pop("document_type", None)
        category = self.ensure_document_category(str(payload.get("category", document.get("category", "未分类"))))
        meta.update({"title": title, "category": category, "tags": tags, "updated": now_iso()})
        body = str(payload.get("body", document.get("body", "")))
        path.write_text(dump_markdown(meta, body), encoding="utf-8")
        return {**meta, "body": body, "file_path": str(path), "file_mtime": path.stat().st_mtime_ns}

    def open_document_external(self, document_id: str) -> dict:
        document, path = self.get_document(document_id)
        if not document or not path:
            raise FileNotFoundError(document_id)
        editor = open_markdown_external(path)
        return {"ok": True, "editor": editor, "document_id": document_id, "file": path.name}

    def delete_document(self, document_id: str) -> dict:
        document, path = self.get_document(document_id)
        if not document or not path:
            raise FileNotFoundError(document_id)
        return self._move_to_trash(path, document_id, "document", document.get("title", document_id))

    def import_document(self, payload: dict) -> dict:
        content = str(payload.get("content", ""))
        if not content.strip():
            raise ValueError("导入的文档内容为空")
        meta, body = load_markdown_text(content)
        title = str(payload.get("title") or meta.get("title") or "").strip()
        if not title:
            heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            title = heading.group(1).strip() if heading else Path(str(payload.get("name", "导入文档.md"))).stem
        return self.create_document({
            "title": title,
            "category": payload.get("category") or meta.get("category") or "导入文档",
            "tags": payload.get("tags") or meta.get("tags") or [],
            "body": body,
        })

    def export_document(self, document_id: str) -> tuple[bytes, str]:
        document, path = self.get_document(document_id)
        if not document or not path:
            raise FileNotFoundError(document_id)
        meta = {key: value for key, value in document.items() if key not in {"body", "file_path", "file_mtime", "document_type"}}
        return dump_markdown(meta, document.get("body", "")).encode("utf-8"), f"{document_id}.md"

    def export_documents_zip(self, document_ids: list[str] | None = None) -> bytes:
        selected = set(document_ids or [])
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.documents_dir.glob("*.md")):
                meta, body = load_markdown(path)
                if meta.get("type") != "document" or (selected and str(meta.get("id", "")) not in selected):
                    continue
                meta.pop("document_type", None)
                archive.writestr(path.name, dump_markdown(meta, body))
        return memory.getvalue()

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
        record, record_path = self.get_record(record_id)
        if not record:
            raise FileNotFoundError(record_id)
        filename = Path(filename).name
        if not filename or filename in {".", ".."}:
            raise ValueError("附件文件名无效")
        try:
            content = base64.b64decode(encoded_content, validate=True)
        except ValueError as exc:
            raise ValueError("附件内容无效") from exc
        candidate = self._record_attachment_target(record, filename)
        candidate.write_bytes(content)
        return self._register_record_attachment(record, record_path, candidate, len(content))

    def _record_attachment_target(self, record: dict, filename: str) -> Path:
        image = (mimetypes.guess_type(filename)[0] or "").startswith("image/")
        if record.get("project_id"):
            asset_root = self.projects_dir / record["project_id"] / "assets" / ("images" if image else "files")
        else:
            asset_root = self.global_assets_dir / ("images" if image else "files")
        asset_root.mkdir(parents=True, exist_ok=True)
        stem, suffix, candidate, counter = Path(filename).stem, Path(filename).suffix, asset_root / filename, 2
        while candidate.exists():
            candidate = asset_root / f"{stem}-{counter}{suffix}"
            counter += 1
        return candidate

    def _register_record_attachment(self, record: dict, record_path: Path, candidate: Path, size: int) -> dict:
        relative = Path(os.path.relpath(candidate, record_path.parent)).as_posix()
        attachments = list(record.get("attachments") or [])
        attachment = {"name": candidate.name, "path": relative, "size": size, "mime": mimetypes.guess_type(candidate.name)[0] or "application/octet-stream", "category": ""}
        attachments.append(json.dumps(attachment, ensure_ascii=False, separators=(",", ":")))
        image = attachment["mime"].startswith("image/")
        label = f"![{candidate.name}]({relative})" if image else f"[{candidate.name}]({relative})"
        body = record["body"].rstrip() + f"\n\n{label}\n"
        self.update_record(record["id"], {"attachments": attachments, "body": body})
        return attachment

    def add_record_attachment_stream(self, record_id: str, filename: str, stream, length: int) -> dict:
        record, record_path = self.get_record(record_id)
        if not record:
            raise FileNotFoundError(record_id)
        filename = Path(filename).name
        if not filename or filename in {".", ".."}:
            raise ValueError("附件文件名无效")
        candidate = self._record_attachment_target(record, filename)
        remaining, written = length, 0
        try:
            with candidate.open("wb") as output:
                while remaining:
                    chunk = stream.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("附件上传不完整")
                    output.write(chunk); written += len(chunk); remaining -= len(chunk)
            return self._register_record_attachment(record, record_path, candidate, written)
        except Exception:
            candidate.unlink(missing_ok=True)
            raise

    def attachment_path(self, record_id: str, filename: str) -> Path | None:
        record, record_path = self.get_record(record_id)
        if not record:
            return None
        for raw in record.get("attachments") or []:
            try:
                attachment = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                continue
            if attachment.get("name") == filename:
                candidate = (record_path.parent / attachment["path"]).resolve()
                if candidate.is_relative_to(self.root) and candidate.is_file():
                    return candidate
        return None

    def _project_asset_index(self, project_id: str) -> Path:
        if not self.project(project_id):
            raise FileNotFoundError(project_id)
        path = self.projects_dir / project_id / "assets" / "index.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def project_assets(self, project_id: str) -> list[dict]:
        index = self._project_asset_index(project_id)
        try:
            items = json.loads(index.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            items = []
        if not isinstance(items, list):
            items = []
        valid = []
        project_root = self.projects_dir / project_id
        for item in items:
            if not isinstance(item, dict) or not item.get("id") or not item.get("path"):
                continue
            candidate = (project_root / item["path"]).resolve()
            if candidate.is_relative_to(project_root) and candidate.is_file():
                valid.append({**item, "size": candidate.stat().st_size})
        return sorted(valid, key=lambda item: item.get("created", ""), reverse=True)

    def project_asset_categories(self, project_id: str) -> list[dict]:
        self._project_asset_index(project_id)
        path = self.projects_dir / project_id / "assets" / "categories.json"
        try:
            configured = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            configured = []
        categories, known = [], set()
        for item in configured if isinstance(configured, list) else []:
            if not isinstance(item, dict):
                continue
            name = self._asset_category(item.get("name", ""), allow_empty=True)
            if name and name not in known:
                categories.append({"name": name, "tag": str(item.get("tag", "")).strip()})
                known.add(name)
        for asset in self.project_assets(project_id):
            name = self._asset_category(asset.get("category", ""), allow_empty=True)
            if name and name not in known:
                categories.append({"name": name, "tag": ""})
                known.add(name)
        return categories

    def save_project_asset_categories(self, project_id: str, categories: list[dict]) -> list[dict]:
        if not isinstance(categories, list):
            raise ValueError("附件分类格式无效")
        previous_names = {item["name"] for item in self.project_asset_categories(project_id)}
        cleaned, known = [], set()
        for item in categories:
            if not isinstance(item, dict):
                raise ValueError("附件分类格式无效")
            name = self._asset_category(item.get("name", ""), allow_empty=True)
            if not name or name in known:
                continue
            cleaned.append({"name": name, "tag": str(item.get("tag", "")).strip()[:80]})
            known.add(name)
        assets = self.project_assets(project_id)
        changed = False
        for asset in assets:
            if asset.get("category") and asset["category"] not in known:
                asset["category"] = ""
                changed = True
        if changed:
            self._save_project_assets(project_id, assets)
        removed = previous_names - known
        if removed:
            for record in self.list_records(project_id=project_id):
                for raw in list(record.get("attachments") or []):
                    try:
                        attachment = json.loads(raw) if isinstance(raw, str) else raw
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if attachment.get("category") in removed:
                        self.update_record_attachment_category(record["id"], attachment.get("name", ""), "")
        path = self.projects_dir / project_id / "assets" / "categories.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return cleaned

    def ensure_project_asset_category(self, project_id: str, category: str) -> str:
        name = self._asset_category(category, allow_empty=True)
        if not name:
            return ""
        categories = self.project_asset_categories(project_id)
        if name not in {item["name"] for item in categories}:
            categories.append({"name": name, "tag": ""})
            self.save_project_asset_categories(project_id, categories)
        return name

    def _save_project_assets(self, project_id: str, items: list[dict]):
        index = self._project_asset_index(project_id)
        temporary = index.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(index)

    @staticmethod
    def _asset_category(value: str, allow_empty: bool = False) -> str:
        category = re.sub(r"[\\/:*?\"<>|]+", "-", str(value or "").strip())[:40].strip(". ")
        return category if category or allow_empty else "未分类"

    def _new_project_asset_target(self, project_id: str, filename: str) -> tuple[Path, str]:
        if not self.project(project_id):
            raise FileNotFoundError(project_id)
        filename = Path(filename).name
        if not filename or filename in {".", ".."}:
            raise ValueError("附件文件名无效")
        asset_root = self.projects_dir / project_id / "assets" / "library"
        asset_root.mkdir(parents=True, exist_ok=True)
        stem, suffix, candidate, counter = Path(filename).stem, Path(filename).suffix, asset_root / filename, 2
        while candidate.exists():
            candidate = asset_root / f"{stem}-{counter}{suffix}"
            counter += 1
        return candidate, filename

    def _register_project_asset(self, project_id: str, candidate: Path, size: int, category: str) -> dict:
        known_ids = {item.get("id") for item in self.project_assets(project_id)}
        asset_id, counter = f"ASSET-{int(time.time() * 1000)}", 2
        while asset_id in known_ids:
            asset_id = f"ASSET-{int(time.time() * 1000)}-{counter}"
            counter += 1
        item = {
            "id": asset_id, "name": candidate.name,
            "path": candidate.relative_to(self.projects_dir / project_id).as_posix(),
            "size": size, "mime": mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
            "category": self.ensure_project_asset_category(project_id, category), "created": now_iso(),
        }
        items = self.project_assets(project_id)
        items.append(item)
        self._save_project_assets(project_id, items)
        return item

    def add_project_asset(self, project_id: str, filename: str, encoded_content: str, category: str = "未分类") -> dict:
        project = self.project(project_id)
        if not project:
            raise FileNotFoundError(project_id)
        filename = Path(filename).name
        if not filename or filename in {".", ".."}:
            raise ValueError("附件文件名无效")
        try:
            content = base64.b64decode(encoded_content, validate=True)
        except ValueError as exc:
            raise ValueError("附件内容无效") from exc
        candidate, _ = self._new_project_asset_target(project_id, filename)
        candidate.write_bytes(content)
        return self._register_project_asset(project_id, candidate, len(content), category)

    def add_project_asset_stream(self, project_id: str, filename: str, stream, length: int, category: str = "") -> dict:
        if length < 0:
            raise ValueError("附件大小无效")
        candidate, _ = self._new_project_asset_target(project_id, filename)
        remaining, written = length, 0
        try:
            with candidate.open("wb") as output:
                while remaining:
                    chunk = stream.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("附件上传不完整")
                    output.write(chunk)
                    written += len(chunk)
                    remaining -= len(chunk)
            return self._register_project_asset(project_id, candidate, written, category)
        except Exception:
            candidate.unlink(missing_ok=True)
            raise

    def update_project_asset(self, project_id: str, asset_id: str, payload: dict) -> dict:
        items = self.project_assets(project_id)
        item = next((entry for entry in items if entry.get("id") == asset_id), None)
        if not item:
            raise FileNotFoundError(asset_id)
        if "category" in payload:
            item["category"] = self.ensure_project_asset_category(project_id, payload["category"])
        self._save_project_assets(project_id, items)
        return item

    def delete_project_asset(self, project_id: str, asset_id: str) -> dict:
        items = self.project_assets(project_id)
        item = next((entry for entry in items if entry.get("id") == asset_id), None)
        if not item:
            raise FileNotFoundError(asset_id)
        path = self.project_asset_path(project_id, asset_id)
        if path:
            path.unlink()
        self._save_project_assets(project_id, [entry for entry in items if entry.get("id") != asset_id])
        return {"deleted": True, "id": asset_id, "name": item.get("name", asset_id)}

    def project_asset_path(self, project_id: str, asset_id: str) -> Path | None:
        try:
            item = next((entry for entry in self.project_assets(project_id) if entry.get("id") == asset_id), None)
        except FileNotFoundError:
            return None
        if not item:
            return None
        project_root = self.projects_dir / project_id
        candidate = (project_root / item["path"]).resolve()
        return candidate if candidate.is_relative_to(project_root) and candidate.is_file() else None

    def update_record_attachment_category(self, record_id: str, filename: str, category: str) -> dict:
        record, _ = self.get_record(record_id)
        if not record:
            raise FileNotFoundError(record_id)
        updated_attachments, matched = [], None
        normalized = self.ensure_project_asset_category(record["project_id"], category) if record.get("project_id") else self._asset_category(category, allow_empty=True)
        for raw in record.get("attachments") or []:
            try:
                item = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                updated_attachments.append(raw)
                continue
            if item.get("name") == filename:
                item["category"] = normalized
                matched = item
            updated_attachments.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
        if not matched:
            raise FileNotFoundError(filename)
        self.update_record(record_id, {"attachments": updated_attachments})
        return matched

    def delete_record_attachment(self, record_id: str, filename: str) -> dict:
        record, record_path = self.get_record(record_id)
        if not record:
            raise FileNotFoundError(record_id)
        kept, removed = [], None
        for raw in record.get("attachments") or []:
            try:
                item = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                kept.append(raw)
                continue
            if item.get("name") == filename and removed is None:
                removed = item
            else:
                kept.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
        if not removed:
            raise FileNotFoundError(filename)
        candidate = (record_path.parent / removed.get("path", "")).resolve()
        if candidate.is_relative_to(self.root) and candidate.is_file():
            candidate.unlink()
        relative = removed.get("path", "")
        body = record.get("body", "")
        for label in (f"![{filename}]({relative})", f"[{filename}]({relative})"):
            body = body.replace(label, "")
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        self.update_record(record_id, {"attachments": kept, "body": body})
        return {"deleted": True, "record_id": record_id, "name": filename}

    def batch_update_assets(self, project_id: str, selections: list[dict], category: str) -> dict:
        if not isinstance(selections, list) or not selections:
            raise ValueError("请选择附件")
        normalized = self.ensure_project_asset_category(project_id, category)
        updated = 0
        for selection in selections:
            if selection.get("source") == "project":
                self.update_project_asset(project_id, str(selection.get("id", "")), {"category": normalized})
                updated += 1
            elif selection.get("source") == "record":
                self.update_record_attachment_category(str(selection.get("record_id", "")), str(selection.get("name", "")), normalized)
                updated += 1
        return {"updated": updated, "category": normalized}

    def batch_delete_assets(self, project_id: str, selections: list[dict]) -> dict:
        if not isinstance(selections, list) or not selections:
            raise ValueError("请选择附件")
        deleted = 0
        for selection in selections:
            if selection.get("source") == "project":
                self.delete_project_asset(project_id, str(selection.get("id", "")))
                deleted += 1
            elif selection.get("source") == "record":
                self.delete_record_attachment(str(selection.get("record_id", "")), str(selection.get("name", "")))
                deleted += 1
        return {"deleted": deleted}

    def orphan_assets(self) -> list[dict]:
        referenced = set()
        for record in self.list_records():
            record_path = Path(record["file_path"])
            for raw in record.get("attachments") or []:
                try:
                    attachment = json.loads(raw) if isinstance(raw, str) else raw
                    referenced.add((record_path.parent / attachment["path"]).resolve())
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
        for project in self.list_projects():
            index = self.projects_dir / project["id"] / "assets" / "index.json"
            categories = self.projects_dir / project["id"] / "assets" / "categories.json"
            referenced.add(index.resolve())
            referenced.add(categories.resolve())
            for item in self.project_assets(project["id"]):
                referenced.add((self.projects_dir / project["id"] / item["path"]).resolve())
        roots = [self.global_assets_dir, *self.projects_dir.glob("*/assets")]
        orphaned = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file() and path.resolve() not in referenced:
                    orphaned.append({"path": str(path), "name": path.name, "size": path.stat().st_size})
        return orphaned

    def cleanup_orphan_assets(self) -> dict:
        orphaned = self.orphan_assets()
        for item in orphaned:
            path = Path(item["path"]).resolve()
            if path.is_relative_to(self.root) and path.is_file():
                path.unlink()
        return {"removed": len(orphaned), "bytes": sum(item["size"] for item in orphaned)}

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


def save_data_location(data_dir: Path, location_file: Path = LOCATION_FILE):
    location_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = location_file.with_suffix(location_file.suffix + ".tmp")
    temporary.write_text(json.dumps({"data_dir": str(data_dir.resolve())}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(location_file)


def relocate_repository(current: Repository, raw_path: str, migrate: bool, location_file: Path = LOCATION_FILE) -> Repository:
    value = os.path.expandvars(str(raw_path).strip())
    if not value:
        raise ValueError("数据目录不能为空")
    target = Path(value).expanduser()
    if not target.is_absolute():
        raise ValueError("请输入完整的绝对路径，例如 E:\\WorkBenchData")
    target = target.resolve()
    if target == current.root:
        save_data_location(target, location_file)
        return current
    if migrate and (target.is_relative_to(current.root) or current.root.is_relative_to(target)):
        raise ValueError("新旧数据目录不能互相嵌套，请选择独立目录")
    if migrate:
        if target.exists() and any(target.iterdir()):
            raise ValueError("复制数据时目标目录必须为空；如需打开已有工作台，请选择“直接使用已有目录”")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(current.root, target, dirs_exist_ok=True)
    else:
        target.mkdir(parents=True, exist_ok=True)
    repository = Repository(target)
    save_data_location(repository.root, location_file)
    return repository


def configured_data_dir(command_line_value: Path | None) -> Path:
    if command_line_value is not None:
        return command_line_value
    environment_value = os.environ.get("WORKBENCH_DATA_DIR")
    if environment_value:
        return Path(environment_value)
    try:
        saved = json.loads(LOCATION_FILE.read_text(encoding="utf-8"))
        if saved.get("data_dir"):
            return Path(saved["data_dir"])
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return DEFAULT_DATA_DIR


def common_export_locations() -> list[dict]:
    home = Path.home()
    choices = [
        ("downloads", "下载", home / "Downloads"),
        ("desktop", "桌面", home / "Desktop"),
        ("documents", "文档", home / "Documents"),
    ]
    return [{"id": key, "label": label, "path": str(path.resolve())} for key, label, path in choices]


def configured_export_dir(location_file: Path = EXPORT_LOCATION_FILE) -> Path | None:
    try:
        saved = json.loads(location_file.read_text(encoding="utf-8"))
        path = Path(saved.get("export_dir", ""))
        return path.resolve() if path.is_absolute() else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def export_location_payload(location_file: Path = EXPORT_LOCATION_FILE) -> dict:
    directory = configured_export_dir(location_file)
    return {
        "path": str(directory) if directory else "",
        "name": directory.name if directory else "",
        "common": common_export_locations(),
    }


def save_export_location(raw_path: str, location_file: Path = EXPORT_LOCATION_FILE) -> dict:
    value = os.path.expandvars(str(raw_path).strip())
    if not value:
        raise ValueError("请选择或填写导出目录")
    target = Path(value).expanduser()
    if not target.is_absolute():
        raise ValueError("请输入完整的绝对路径，例如 C:\\Users\\用户名\\Downloads")
    target.mkdir(parents=True, exist_ok=True)
    target = target.resolve()
    # 创建并立即删除探测文件，在保存设置前确认目录确实可写。
    with tempfile.NamedTemporaryFile(prefix=".workbench-write-test-", dir=target, delete=True):
        pass
    location_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = location_file.with_suffix(location_file.suffix + ".tmp")
    temporary.write_text(json.dumps({"export_dir": str(target)}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(location_file)
    return export_location_payload(location_file)


def directory_browser_payload(raw_path: str = "") -> dict:
    value = os.path.expandvars(str(raw_path).strip())
    target = Path(value).expanduser() if value else (configured_export_dir() or Path.home())
    if not target.is_absolute():
        raise ValueError("请输入完整目录路径")
    target = target.resolve()
    if not target.is_dir():
        raise ValueError("该目录不存在，请选择已有目录")
    directories = []
    try:
        children = sorted((item for item in target.iterdir() if item.is_dir() and not item.name.startswith(".")), key=lambda item: item.name.casefold())
        for child in children:
            try:
                directories.append({"name": child.name, "path": str(child.resolve())})
            except OSError:
                continue
    except PermissionError as exc:
        raise ValueError("没有权限浏览该目录，请返回上一级") from exc
    roots = []
    if sys.platform == "win32":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            if drive.exists():
                roots.append({"name": f"本地磁盘 ({letter}:)", "path": str(drive)})
    else:
        roots.append({"name": "根目录", "path": "/"})
    parent = target.parent
    return {
        "path": str(target),
        "name": target.name or str(target),
        "parent": str(parent) if parent != target else "",
        "directories": directories,
        "roots": roots,
    }


def export_to_saved_location(repository: Repository, project_id: str | None, filename: str, location_file: Path = EXPORT_LOCATION_FILE) -> dict:
    directory = configured_export_dir(location_file)
    if not directory:
        raise ValueError("请先选择导出位置")
    if not directory.is_dir():
        raise ValueError("已保存的导出目录不存在，请重新选择位置")
    clean_name = Path(str(filename)).name
    if clean_name != filename or not clean_name.lower().endswith(".zip"):
        raise ValueError("导出文件名无效")
    content = repository.export_zip(project_id)
    destination = directory / clean_name
    with tempfile.NamedTemporaryFile(prefix=f".{clean_name}.", suffix=".tmp", dir=directory, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.replace(destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return {"ok": True, "path": str(destination), "directory": str(directory), "filename": clean_name, "size": len(content)}


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
            if path == "/api/documents":
                return self._json(self.repository.list_documents())
            if path.startswith("/api/documents/"):
                document, _ = self.repository.get_document(path.rsplit("/", 1)[-1])
                return self._json(document) if document else self._json({"error": "文档不存在"}, HTTPStatus.NOT_FOUND)
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
                if len(parts) == 4 and parts[-1] == "open-external":
                    return self._json(self.repository.open_record_external(parts[-2]))
                if len(parts) == 5 and parts[-2:] == ["attachments", "upload"]:
                    length = int(self.headers.get("Content-Length", "0"))
                    filename = (query.get("name") or [""])[0]
                    return self._json(self.repository.add_record_attachment_stream(parts[2], filename, self.rfile, length), HTTPStatus.CREATED)
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
            if path.startswith("/api/documents/"):
                return self._json(self.repository.update_document(path.rsplit("/", 1)[-1], self._body()))
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
            if path.startswith("/api/documents/"):
                return self._json(self.repository.delete_document(path.rsplit("/", 1)[-1]))
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
