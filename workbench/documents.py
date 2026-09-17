"""Knowledge document persistence, references, and import/export."""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

from .markdown_io import dump_markdown, load_markdown, load_markdown_text, now_iso, slugify


class DocumentRepository:
    """Own knowledge documents while using injected cross-domain lookups."""

    def __init__(
        self,
        documents_dir: Path,
        ensure_document_category,
        list_records,
        list_projects,
        open_markdown_external,
        move_to_trash,
    ):
        self.documents_dir = documents_dir
        self.ensure_document_category = ensure_document_category
        self.list_records = list_records
        self.list_projects = list_projects
        self.open_markdown_external = open_markdown_external
        self._move_to_trash = move_to_trash

    def list_documents(self) -> list[dict]:
        documents = []
        for path in self.documents_dir.glob("*.md"):
            meta, body = load_markdown(path)
            if meta.get("type") != "document":
                continue
            meta.pop("document_type", None)
            documents.append({**meta, "body": body, "file_path": str(path), "file_mtime": path.stat().st_mtime_ns})
        return sorted(documents, key=lambda item: item.get("updated", ""), reverse=True)

    def document_signatures(self) -> list[dict]:
        """Return the small payload used by the browser's document change poll."""
        signatures = []
        for path in self.documents_dir.glob("*.md"):
            front_matter = []
            with path.open("r", encoding="utf-8") as source:
                if source.readline().rstrip("\r\n") != "---":
                    continue
                front_matter.append("---\n")
                for line in source:
                    front_matter.append(line)
                    if line.rstrip("\r\n") == "---":
                        break
            meta, _ = load_markdown_text("".join(front_matter))
            if meta.get("type") != "document" or not meta.get("id"):
                continue
            signatures.append({"id": meta["id"], "file_mtime": path.stat().st_mtime_ns, "updated": meta.get("updated", "")})
        signatures.sort(key=lambda item: item["updated"], reverse=True)
        return [{"id": item["id"], "file_mtime": item["file_mtime"]} for item in signatures]

    def get_document(self, document_id: str) -> tuple[dict, Path] | tuple[None, None]:
        for document in self.list_documents():
            if document.get("id") == document_id:
                return document, Path(document["file_path"])
        return None, None

    def list_reference_targets(self) -> list[dict]:
        """Return lightweight targets that visual editors can reference."""
        targets = [
            {
                "id": document.get("id"), "type": "document",
                "title": document.get("title", ""),
                "category": document.get("category", "未分类"),
                "attachments": [],
            }
            for document in self.list_documents()
        ]
        for record in self.list_records():
            if record.get("type") not in {"issue", "todo"}:
                continue
            attachments = []
            for item in record.get("attachments", []):
                if isinstance(item, str):
                    try:
                        item = json.loads(item)
                    except (TypeError, json.JSONDecodeError):
                        continue
                if isinstance(item, dict) and str(item.get("name", "")).strip():
                    attachments.append({
                        "name": str(item["name"]),
                        "size": int(item.get("size", 0) or 0),
                        "mime": str(item.get("mime", "application/octet-stream")),
                    })
            targets.append({
                "id": record.get("id"), "type": record.get("type"),
                "title": record.get("title", ""),
                "project_id": record.get("project_id"),
                "attachments": attachments,
            })
        return targets

    def list_document_backlinks(self, document_id: str) -> list[dict]:
        """Return issue and todo records that reference a knowledge document."""
        document, _ = self.get_document(document_id)
        if not document:
            raise FileNotFoundError(document_id)
        normalized_id = str(document_id).upper()
        project_names = {str(item.get("id")): str(item.get("name", item.get("id", ""))) for item in self.list_projects()}
        backlinks = []
        for record in self.list_records():
            if record.get("type") not in {"issue", "todo"}:
                continue
            tokens = re.findall(r"\[\[([A-Za-z]+-\d+(?:#[^\]]+)?)\]\]", str(record.get("body", "")))
            links = record.get("links", [])
            if isinstance(links, str):
                links = [links]
            if isinstance(links, list):
                tokens.extend(str(item) for item in links)
            referenced_ids = {token.split("#", 1)[0].upper() for token in tokens}
            if normalized_id not in referenced_ids:
                continue
            project_id = str(record.get("project_id", ""))
            backlinks.append({
                "id": record.get("id"),
                "type": record.get("type"),
                "title": record.get("title", ""),
                "project_id": project_id,
                "project_name": project_names.get(project_id, project_id or "未归属项目"),
                "updated": record.get("updated", ""),
            })
        return sorted(backlinks, key=lambda item: item.get("updated", ""), reverse=True)

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
        editor = self.open_markdown_external(path)
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
