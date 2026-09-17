"""Record and project attachment persistence."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
from pathlib import Path

from workbench.markdown_io import now_iso
from workbench.persistence import atomic_write_json
from workbench.security import validate_category_name, validate_portable_filename


class AttachmentRepository:
    def __init__(
        self,
        root: Path,
        projects_dir: Path,
        global_assets_dir: Path,
        get_record,
        update_record,
        project,
        list_records,
        list_projects,
        open_file_external,
    ):
        self.root = root
        self.projects_dir = projects_dir
        self.global_assets_dir = global_assets_dir
        self._get_record = get_record
        self._update_record = update_record
        self._project = project
        self._list_records = list_records
        self._list_projects = list_projects
        self.open_file_external = open_file_external

    def get_record(self, record_id: str):
        return self._get_record(record_id)

    def update_record(self, record_id: str, payload: dict):
        return self._update_record(record_id, payload)

    def project(self, project_id: str):
        return self._project(project_id)

    def list_records(self, project_id: str | None = None, record_type: str | None = None):
        return self._list_records(project_id=project_id, record_type=record_type)

    def list_projects(self):
        return self._list_projects()

    def add_attachment(self, record_id: str, filename: str, encoded_content: str) -> dict:
        record, record_path = self.get_record(record_id)
        if not record:
            raise FileNotFoundError(record_id)
        filename = validate_portable_filename(filename, label="附件文件名")
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

    def _record_attachment_roots(self, record: dict) -> tuple[Path, Path]:
        base = self.projects_dir / record["project_id"] / "assets" if record.get("project_id") else self.global_assets_dir
        return (base / "images").resolve(), (base / "files").resolve()

    def _register_record_attachment(self, record: dict, record_path: Path, candidate: Path, size: int, append_to_body: bool = True) -> dict:
        relative = Path(os.path.relpath(candidate, record_path.parent)).as_posix()
        attachments = list(record.get("attachments") or [])
        attachment = {"name": candidate.name, "path": relative, "size": size, "mime": mimetypes.guess_type(candidate.name)[0] or "application/octet-stream", "category": ""}
        attachments.append(json.dumps(attachment, ensure_ascii=False, separators=(",", ":")))
        changes = {"attachments": attachments}
        if append_to_body:
            image = attachment["mime"].startswith("image/")
            label = f"![{candidate.name}]({relative})" if image else f"[{candidate.name}]({relative})"
            changes["body"] = record["body"].rstrip() + f"\n\n{label}\n"
        self.update_record(record["id"], changes)
        return attachment

    def add_record_attachment_stream(self, record_id: str, filename: str, stream, length: int, append_to_body: bool = True) -> dict:
        record, record_path = self.get_record(record_id)
        if not record:
            raise FileNotFoundError(record_id)
        if length < 0:
            raise ValueError("附件大小无效")
        filename = validate_portable_filename(filename, label="附件文件名")
        candidate = self._record_attachment_target(record, filename)
        remaining, written = length, 0
        try:
            with candidate.open("wb") as output:
                while remaining:
                    chunk = stream.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("附件上传不完整")
                    output.write(chunk); written += len(chunk); remaining -= len(chunk)
            return self._register_record_attachment(record, record_path, candidate, written, append_to_body)
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
                if not isinstance(attachment, dict) or not attachment.get("path"):
                    continue
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                continue
            if attachment.get("name") == filename:
                try:
                    candidate = (record_path.parent / attachment["path"]).resolve()
                except (OSError, TypeError, ValueError):
                    continue
                if any(candidate.is_relative_to(root) for root in self._record_attachment_roots(record)) and candidate.is_file():
                    return candidate
        return None

    def open_record_attachment_external(self, record_id: str, filename: str) -> dict:
        path = self.attachment_path(record_id, filename)
        if not path:
            raise FileNotFoundError(filename)
        application = self.open_file_external(path)
        return {"ok": True, "application": application, "record_id": record_id, "file": path.name}

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
        library_root = (project_root / "assets" / "library").resolve()
        for item in items:
            if not isinstance(item, dict) or not item.get("id") or not item.get("path"):
                continue
            try:
                candidate = (project_root / item["path"]).resolve()
            except (OSError, TypeError, ValueError):
                continue
            if candidate.is_relative_to(library_root) and candidate.is_file():
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
            try:
                name = self._asset_category(item.get("name", ""), allow_empty=True)
            except ValueError:
                continue
            if name and name not in known:
                categories.append({"name": name, "tag": str(item.get("tag", "")).strip()})
                known.add(name)
        for asset in self.project_assets(project_id):
            try:
                name = self._asset_category(asset.get("category", ""), allow_empty=True)
            except ValueError:
                continue
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
        atomic_write_json(path, cleaned)
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
        atomic_write_json(index, items)

    @staticmethod
    def _asset_category(value: str, allow_empty: bool = False) -> str:
        raw = validate_category_name(value, default="" if allow_empty else "未分类", label="附件分类", max_length=80)
        category = re.sub(r"[\\/:*?\"<>|]+", "-", raw)[:40].strip(". ")
        return category if category or allow_empty else "未分类"

    def _new_project_asset_target(self, project_id: str, filename: str) -> tuple[Path, str]:
        if not self.project(project_id):
            raise FileNotFoundError(project_id)
        filename = validate_portable_filename(filename, label="附件文件名")
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
        filename = validate_portable_filename(filename, label="附件文件名")
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
        library_root = (project_root / "assets" / "library").resolve()
        try:
            candidate = (project_root / item["path"]).resolve()
        except (KeyError, OSError, TypeError, ValueError):
            return None
        return candidate if candidate.is_relative_to(library_root) and candidate.is_file() else None

    def open_project_asset_external(self, project_id: str, asset_id: str) -> dict:
        path = self.project_asset_path(project_id, asset_id)
        if not path:
            raise FileNotFoundError(asset_id)
        application = self.open_file_external(path)
        return {"ok": True, "application": application, "project_id": project_id, "asset_id": asset_id, "file": path.name}

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
        try:
            candidate = (record_path.parent / removed.get("path", "")).resolve()
        except (OSError, TypeError, ValueError):
            candidate = None
        if candidate and any(candidate.is_relative_to(root) for root in self._record_attachment_roots(record)) and candidate.is_file():
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
            roots = self._record_attachment_roots(record)
            for raw in record.get("attachments") or []:
                try:
                    attachment = json.loads(raw) if isinstance(raw, str) else raw
                    candidate = (record_path.parent / attachment["path"]).resolve()
                    if any(candidate.is_relative_to(root) for root in roots):
                        referenced.add(candidate)
                except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
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
            resolved_root = root.resolve()
            for path in root.rglob("*"):
                try:
                    candidate = path.resolve()
                except (OSError, RuntimeError):
                    continue
                if path.is_symlink() or not candidate.is_relative_to(resolved_root):
                    continue
                if path.is_file() and candidate not in referenced:
                    orphaned.append({"path": str(path), "name": path.name, "size": path.stat().st_size})
        return orphaned

    def cleanup_orphan_assets(self) -> dict:
        orphaned = self.orphan_assets()
        for item in orphaned:
            path = Path(item["path"]).resolve()
            if path.is_relative_to(self.root.resolve()) and path.is_file():
                path.unlink()
        return {"removed": len(orphaned), "bytes": sum(item["size"] for item in orphaned)}
