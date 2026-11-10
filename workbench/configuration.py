"""Knowledge-base configuration persistence and migration rules."""

from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path

from .markdown_io import dump_markdown, now_iso
from .persistence import atomic_write_json, atomic_write_text
from .security import validate_category_name


class ConfigurationRepository:
    """Own configuration persistence while collaborating with domain repositories."""

    def __init__(
        self,
        root: Path,
        config_dir: Path,
        unsorted_projects,
        list_documents,
        list_projects,
        list_records,
        update_document,
        update_project,
        update_record,
        concept_map_categories,
    ):
        self.root = root
        self.config_dir = config_dir
        self._unsorted_projects = unsorted_projects
        self.list_documents = list_documents
        self.list_projects = list_projects
        self.list_records = list_records
        self.update_document = update_document
        self.update_project = update_project
        self.update_record = update_record
        self.concept_map_categories = concept_map_categories
        self.before_category_change = lambda names: []
        self.after_category_rename = lambda changes, old, new: None
        self.category_catalogue = lambda before, after: nullcontext()

    def config(self) -> dict:
        return {
            "data_dir": str(self.root),
            "status_templates": json.loads((self.config_dir / "status-templates.json").read_text(encoding="utf-8")),
            "workflow_templates": json.loads((self.config_dir / "workflow-templates.json").read_text(encoding="utf-8")),
            "tags": self.list_tags(),
            "project_sort": self.project_sort(),
            "document_sort": self.document_sort(),
            "document_categories": self.document_categories(),
            "concept_map_categories": self.concept_map_categories(),
        }

    def project_sort(self) -> dict:
        path = self.config_dir / "project-sort.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {"mode": "custom", "order": []}
        return {"mode": value.get("mode", "custom"), "order": value.get("order", []) if isinstance(value.get("order", []), list) else []}

    def save_project_sort(self, payload: dict) -> dict:
        value = self.canonical_project_sort(payload, self._unsorted_projects())
        atomic_write_json(self.config_dir / "project-sort.json", value)
        return value

    @staticmethod
    def canonical_project_sort(payload: dict, projects) -> dict:
        """Normalize explicit ordering against the supplied project snapshot."""
        modes = {"custom", "updated", "name", "created", "record_count"}
        mode = str(payload.get("mode", "custom"))
        order = payload.get("order", [])
        if mode not in modes:
            raise ValueError("项目排序规则无效")
        if not isinstance(order, list) or any(not isinstance(item, str) for item in order):
            raise ValueError("项目顺序必须是项目编号列表")
        known = [project["id"] for project in sorted(projects, key=lambda item: item.get("created", ""))]
        known_set = set(known)
        cleaned = list(dict.fromkeys(item for item in order if item in known_set))
        cleaned.extend(project_id for project_id in known if project_id not in cleaned)
        return {"mode": mode, "order": cleaned}

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
        atomic_write_json(self.config_dir / "document-sort.json", value)
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
            name = validate_category_name(value, default="", label="分类名称")
            if not name:
                continue
            if name not in cleaned:
                cleaned.append(name)
        for document in self.list_documents():
            category = str(document.get("category") or "未分类").strip() or "未分类"
            if category not in cleaned:
                cleaned.append(category)
        previous = self.document_categories()
        with self.category_catalogue(previous, cleaned):
            self.before_category_change(set(previous) - set(cleaned))
            atomic_write_json(self.config_dir / "document-categories.json", cleaned)
        return cleaned
    def ensure_document_category(self, category: str) -> str:
        name = validate_category_name(category)
        categories = self.document_categories()
        if name not in categories:
            categories.append(name)
            self.save_document_categories(categories)
        return name

    def rename_document_category(self, old_name: str, new_name: str) -> dict:
        old_name = str(old_name).strip()
        new_name = validate_category_name(new_name, default="", label="分类名称")
        categories = self.document_categories()
        if old_name not in categories:
            raise FileNotFoundError(old_name)
        if not new_name:
            raise ValueError("分类名称不能为空")
        if new_name != old_name and new_name in categories:
            raise ValueError("分类名称已存在")
        if new_name == old_name:
            return {"categories": categories, "document_sort": self.document_sort(), "updated_documents": 0}
        authorization_changes = self.before_category_change([old_name])
        changed = 0
        for document in self.list_documents():
            if str(document.get("category") or "未分类") != old_name:
                continue
            self.update_document(document["id"], {"category": new_name, "expected_revision": document["revision"]})
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
        self.after_category_rename(authorization_changes, old_name, new_name)
        return {"categories": saved_categories, "document_sort": saved_sort, "updated_documents": changed}

    def delete_document_category(self, name: str) -> dict:
        name = str(name).strip()
        categories = self.document_categories()
        if name not in categories:
            raise FileNotFoundError(name)
        if name == "未分类":
            raise ValueError("“未分类”是系统默认分类，不能删除")
        self.before_category_change([name])
        changed = 0
        for document in self.list_documents():
            if str(document.get("category") or "未分类") != name:
                continue
            self.update_document(document["id"], {"category": "未分类", "expected_revision": document["revision"]})
            changed += 1
        remaining = [category for category in categories if category != name]
        if "未分类" not in remaining:
            remaining.append("未分类")
        saved_categories = self.save_document_categories(remaining)
        sorting = self.document_sort()
        category_order = [category for category in sorting.get("category_order", []) if category != name]
        if "未分类" not in category_order:
            category_order.append("未分类")
        file_modes = {category: mode for category, mode in sorting.get("file_modes", {}).items() if category != name}
        file_orders = {category: order for category, order in sorting.get("file_orders", {}).items() if category != name}
        saved_sort = self.save_document_sort({**sorting, "category_order": category_order, "file_modes": file_modes, "file_orders": file_orders})
        return {"categories": saved_categories, "document_sort": saved_sort, "updated_documents": changed}

    def _validate_statuses(self, templates: dict):
        from .workflow_changes import validate_statuses
        validate_statuses(templates)

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
        atomic_write_json(self.config_dir / "labels.json", cleaned)
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
