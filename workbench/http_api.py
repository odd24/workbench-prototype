"""HTTP server, response helpers, and API routing for the local workbench."""

from __future__ import annotations

import json
import mimetypes
import socket
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .external_editor import external_editor_payload, save_external_editor
from .paths import (
    directory_browser_payload,
    export_location_payload,
    export_to_saved_location,
    relocate_repository,
    save_export_location,
)


APP_DIR = Path(__file__).resolve().parent.parent
APP_VERSION = "2026.09.17.2"
MAX_JSON_BODY_BYTES = 15_000_000


class WorkbenchHTTPServer(ThreadingHTTPServer):
    """Use an exclusive port so repeated launches cannot mix server versions."""

    allow_reuse_address = False

    def server_bind(self):
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class WorkbenchHandler(SimpleHTTPRequestHandler):
    repository: object
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

    def _content_length(self, maximum: int | None = None) -> int:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError) as exc:
            raise ValueError("请求长度无效") from exc
        if length < 0:
            raise ValueError("请求长度无效")
        if maximum is not None and length > maximum:
            self.close_connection = True
            raise ValueError("请求内容过大")
        return length

    def _body(self):
        length = self._content_length(MAX_JSON_BODY_BYTES)
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError("请求内容不完整")
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        if not isinstance(payload, dict):
            raise ValueError("请求内容必须是 JSON 对象")
        return payload

    def _route(self):
        parsed = urlparse(self.path)
        return unquote(parsed.path), parse_qs(parsed.query)

    def _inline_file(self, file_path: Path):
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{quote(file_path.name)}")
        self.end_headers()
        self.wfile.write(content)

    def _get_document_resource(self, path: str) -> bool:
        if path.startswith("/api/documents/") and path.endswith("/export"):
            document_id = path.strip("/").split("/")[-2]
            content, filename = self.repository.export_document(document_id)
            self._bytes(content, "text/markdown; charset=utf-8", filename)
        elif path.startswith("/api/documents/") and path.endswith("/backlinks"):
            document_id = path.strip("/").split("/")[-2]
            self._json(self.repository.list_document_backlinks(document_id))
        elif path == "/api/documents":
            self._json(self.repository.list_documents())
        elif path == "/api/document-signatures":
            self._json(self.repository.document_signatures())
        elif path == "/api/reference-targets":
            self._json(self.repository.list_reference_targets())
        elif path.startswith("/api/documents/"):
            document, _ = self.repository.get_document(path.rsplit("/", 1)[-1])
            self._json(document) if document else self._json({"error": "文档不存在"}, HTTPStatus.NOT_FOUND)
        else:
            return False
        return True

    def _get_concept_map_resource(self, path: str) -> bool:
        if path == "/api/concept-maps":
            self._json(self.repository.list_concept_maps())
        elif path == "/api/concept-map-categories":
            self._json(self.repository.concept_map_categories())
        elif path.startswith("/api/concept-maps/"):
            concept_map, _ = self.repository.get_concept_map(path.rsplit("/", 1)[-1])
            self._json(concept_map) if concept_map else self._json({"error": "概念图不存在"}, HTTPStatus.NOT_FOUND)
        else:
            return False
        return True

    def _get_project_asset_resource(self, path: str) -> bool:
        if path == "/api/projects":
            self._json(self.repository.list_projects())
        elif path.startswith("/api/projects/") and path.endswith("/assets"):
            self._json(self.repository.project_assets(path.strip("/").split("/")[2]))
        elif path.startswith("/api/projects/") and path.endswith("/asset-categories"):
            self._json(self.repository.project_asset_categories(path.strip("/").split("/")[2]))
        elif path.startswith("/api/project-assets/"):
            parts = path.strip("/").split("/")
            if len(parts) != 4:
                self._json({"error": "项目附件路径无效"}, HTTPStatus.BAD_REQUEST)
            else:
                file_path = self.repository.project_asset_path(parts[2], parts[3])
                self._inline_file(file_path) if file_path else self._json({"error": "项目附件不存在"}, HTTPStatus.NOT_FOUND)
        else:
            return False
        return True

    def _get_record_resource(self, path: str, query: dict) -> bool:
        if path == "/api/records":
            summary = (query.get("summary") or [""])[0] == "1"
            loader = self.repository.list_record_summaries if summary else self.repository.list_records
            record_ids = query.get("id") if summary else None
            records = loader((query.get("project") or [None])[0], (query.get("type") or [None])[0], record_ids) if record_ids else loader((query.get("project") or [None])[0], (query.get("type") or [None])[0])
            self._json([record for record in records if record.get("type") != "idea"])
        elif path == "/api/record-signatures":
            self._json([record for record in self.repository.record_signatures() if record.get("type") != "idea"])
        elif path.startswith("/api/records/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[-1] == "history":
                self._json(self.repository.list_history(parts[-2]))
            else:
                record, _ = self.repository.get_record(parts[-1])
                self._json(record) if record else self._json({"error": "记录不存在"}, HTTPStatus.NOT_FOUND)
        elif path.startswith("/api/attachments/"):
            parts = path.strip("/").split("/", 3)
            if len(parts) != 4:
                self._json({"error": "附件路径无效"}, HTTPStatus.BAD_REQUEST)
            else:
                file_path = self.repository.attachment_path(parts[2], parts[3])
                self._inline_file(file_path) if file_path else self._json({"error": "附件不存在"}, HTTPStatus.NOT_FOUND)
        elif path == "/api/search":
            self._json([record for record in self.repository.search((query.get("q") or [""])[0]) if record.get("type") != "idea"])
        else:
            return False
        return True

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
            if self._get_document_resource(path) or self._get_concept_map_resource(path):
                return
            if path == "/api/export":
                project_id = (query.get("project") or [None])[0]
                return self._bytes(self.repository.export_zip(project_id), "application/zip", "workbench-export.zip")
            if path == "/api/orphan-assets":
                return self._json(self.repository.orphan_assets())
            if self._get_project_asset_resource(path) or self._get_record_resource(path, query):
                return
            return self._json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except FileExistsError as exc:
            return self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
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
                length = self._content_length()
                filename = (query.get("name") or [""])[0]
                category = (query.get("category") or [""])[0]
                return self._json(self.repository.add_project_asset_stream(project_id, filename, self.rfile, length, category), HTTPStatus.CREATED)
            if path.startswith("/api/projects/") and path.endswith("/open-external"):
                parts = path.strip("/").split("/")
                if len(parts) == 6 and parts[3] == "assets":
                    return self._json(self.repository.open_project_asset_external(parts[2], parts[4]))
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
                    length = self._content_length()
                    filename = (query.get("name") or [""])[0]
                    append_to_body = (query.get("append") or ["1"])[0] != "0"
                    return self._json(self.repository.add_record_attachment_stream(parts[2], filename, self.rfile, length, append_to_body), HTTPStatus.CREATED)
                if len(parts) == 6 and parts[3] == "attachments" and parts[-1] == "open-external":
                    return self._json(self.repository.open_record_attachment_external(parts[2], parts[4]))
                if len(parts) == 4 and parts[-1] == "attachments":
                    payload = self._body()
                    return self._json(self.repository.add_attachment(parts[-2], payload.get("name", ""), payload.get("content", "")), HTTPStatus.CREATED)
                if len(parts) == 4 and parts[-1] == "restore":
                    return self._json(self.repository.restore_history(parts[-2], self._body().get("version", "")))
            return self._json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except FileNotFoundError as exc:
            return self._json({"error": f"资源不存在：{exc}"}, HTTPStatus.NOT_FOUND)
        except FileExistsError as exc:
            return self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
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
                    type(self).repository = repository
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
        except FileExistsError as exc:
            return self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            return self._json({"error": f"无法使用该目录：{exc}"}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            return self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

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
        except FileExistsError as exc:
            return self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            return self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

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
        except FileExistsError as exc:
            return self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            return self._json({"error": f"附件删除失败：{exc}"}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            return self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
