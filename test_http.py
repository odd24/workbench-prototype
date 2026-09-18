import io
import http.client
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from server import APP_VERSION, Repository, WorkbenchHandler, WorkbenchHTTPServer
from workbench.http_api import WorkbenchHandler as ExtractedWorkbenchHandler
from workbench.http_api import WorkbenchHTTPServer as ExtractedWorkbenchHTTPServer


class QuietWorkbenchHandler(WorkbenchHandler):
    def log_message(self, _format, *_args):
        pass


class HTTPIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.temp.name))
        self.project = self.repo.create_project({"name": "HTTP 集成测试", "description": "临时数据"})
        QuietWorkbenchHandler.repository = self.repo
        self.server = WorkbenchHTTPServer(("127.0.0.1", 0), QuietWorkbenchHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, name="workbench-http-test", daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()
        self.assertFalse(self.thread.is_alive(), "HTTP 测试服务未正常停止")

    def request(self, method, path, payload=None, body=None, headers=None):
        request_headers = dict(headers or {})
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json; charset=utf-8"
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    def request_json(self, method, path, payload=None, body=None):
        status, headers, content = self.request(method, path, payload=payload, body=body)
        return status, headers, json.loads(content.decode("utf-8"))

    def request_with_content_length(self, value):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.putrequest("POST", "/api/projects")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", value)
            connection.endheaders()
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()

    def test_truncated_json_body_is_rejected_before_parsing(self):
        handler = object.__new__(WorkbenchHandler)
        handler.headers = {"Content-Length": "5"}
        handler.rfile = io.BytesIO(b"{}")
        handler.close_connection = False

        with self.assertRaisesRegex(ValueError, "请求内容不完整"):
            handler._body()

    def test_health_uses_temporary_repository_and_dynamic_port(self):
        status, headers, payload = self.request_json("GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertNotEqual(self.port, 0)
        self.assertEqual(headers.get_content_type(), "application/json")
        self.assertEqual(payload["data_dir"], str(self.repo.root))
        self.assertEqual(payload["app_version"], APP_VERSION)

    def test_server_keeps_compatible_extracted_http_exports(self):
        self.assertIs(WorkbenchHandler, ExtractedWorkbenchHandler)
        self.assertIs(WorkbenchHTTPServer, ExtractedWorkbenchHTTPServer)

    def test_static_file_is_served_with_no_cache_headers(self):
        status, headers, content = self.request("GET", "/index.html")

        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/html")
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertIn("本地工作台".encode("utf-8"), content)

    def test_json_create_and_read_round_trip(self):
        status, _, created = self.request_json("POST", "/api/records", {
            "type": "issue",
            "title": "HTTP 中文往返",
            "project_id": self.project["id"],
            "tags": ["集成测试"],
            "body": "# HTTP 中文往返\n\n正文 🧪",
        })
        self.assertEqual(status, 201)

        status, _, loaded = self.request_json("GET", f"/api/records/{quote(created['id'])}")
        self.assertEqual(status, 200)
        self.assertEqual(loaded["title"], "HTTP 中文往返")
        self.assertEqual(loaded["body"], "# HTTP 中文往返\n\n正文 🧪")
        self.assertTrue(any(path.name.startswith(created["id"]) for path in self.repo.projects_dir.rglob("*.md")))

    def test_incremental_refresh_endpoints_return_only_requested_payloads(self):
        first = self.repo.create_record({
            "type": "todo", "title": "增量一", "project_id": self.project["id"], "body": "正文一",
        })
        second = self.repo.create_record({
            "type": "issue", "title": "增量二", "project_id": self.project["id"], "body": "正文二",
        })
        attachment = self.repo.add_record_attachment_stream(first["id"], "条目附件.txt", io.BytesIO(b"asset"), 5)
        document = self.repo.create_document({"title": "增量文档", "category": "测试", "body": "文档正文"})

        ids = f"id={quote(second['id'])}&id={quote(first['id'])}"
        status, _, summaries = self.request_json("GET", f"/api/records?summary=1&{ids}")
        self.assertEqual(status, 200)
        self.assertEqual({item["id"] for item in summaries}, {first["id"], second["id"]})
        self.assertTrue(all("body" not in item and "body_preview" in item for item in summaries))
        self.assertTrue(all("attachments" not in item for item in summaries))

        status, _, asset_summaries = self.request_json(
            "GET", f"/api/records?summary=1&project={quote(self.project['id'])}&attachments=1"
        )
        self.assertEqual(status, 200)
        first_summary = next(item for item in asset_summaries if item["id"] == first["id"])
        self.assertEqual(first_summary["attachments"][0]["name"], attachment["name"])
        self.assertNotIn("body", first_summary)

        status, _, signatures = self.request_json("GET", "/api/document-signatures")
        self.assertEqual(status, 200)
        self.assertEqual(signatures, [{"id": document["id"], "file_mtime": document["file_mtime"]}])

    def test_zip_export_returns_binary_stream(self):
        self.repo.create_record({
            "type": "todo",
            "title": "导出字节流",
            "project_id": self.project["id"],
        })

        status, headers, content = self.request("GET", f"/api/export?project={quote(self.project['id'])}")

        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "application/zip")
        self.assertEqual(int(headers["Content-Length"]), len(content))
        self.assertIn("workbench-export.zip", headers["Content-Disposition"])
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
        self.assertTrue(any(name.endswith("README.md") for name in names))
        self.assertTrue(any("TODO-0001" in name for name in names))

    def test_stream_upload_and_inline_download_round_trip(self):
        content = (b"stream-boundary-" * 65536) + b"done"
        status, _, created = self.request_json(
            "POST",
            f"/api/projects/{quote(self.project['id'])}/assets/upload?name=stream.bin&category=HTTP",
            body=content,
        )
        self.assertEqual(status, 201)

        status, headers, downloaded = self.request(
            "GET", f"/api/project-assets/{quote(self.project['id'])}/{quote(created['id'])}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "application/octet-stream")
        self.assertEqual(int(headers["Content-Length"]), len(content))
        self.assertEqual(downloaded, content)

    def test_attachment_external_open_routes(self):
        with patch.object(self.repo, "open_project_asset_external", return_value={"ok": True, "application": "系统默认应用", "file": "资料.docx"}) as project_open:
            status, _, payload = self.request_json(
                "POST", f"/api/projects/{quote(self.project['id'])}/assets/ASSET-1/open-external"
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["application"], "系统默认应用")
        project_open.assert_called_once_with(self.project["id"], "ASSET-1")

        with patch.object(self.repo, "open_record_attachment_external", return_value={"ok": True, "application": "Typora", "file": "中文说明.md"}) as record_open:
            status, _, payload = self.request_json(
                "POST", "/api/records/ISSUE-0001/attachments/%E4%B8%AD%E6%96%87%E8%AF%B4%E6%98%8E.md/open-external"
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["application"], "Typora")
        record_open.assert_called_once_with("ISSUE-0001", "中文说明.md")

        status, _, missing = self.request_json(
            "POST", "/api/records/ISSUE-9999/attachments/missing.txt/open-external"
        )
        self.assertEqual(status, 404)
        self.assertIn("资源不存在", missing["error"])

    def test_conflict_is_reported_as_409(self):
        with patch.object(self.repo, "create_project", side_effect=FileExistsError("项目冲突")):
            status, _, conflict = self.request_json("POST", "/api/projects", {"name": "冲突"})

        self.assertEqual(status, 409)
        self.assertEqual(conflict, {"error": "项目冲突"})

    def test_bad_request_not_found_and_internal_error_statuses(self):
        status, _, bad_request = self.request_json("POST", "/api/projects", body=b"{")
        self.assertEqual(status, 400)
        self.assertIn("error", bad_request)

        status, _, wrong_shape = self.request_json("POST", "/api/projects", body=b"[]")
        self.assertEqual(status, 400)
        self.assertIn("JSON 对象", wrong_shape["error"])

        for length in ("invalid", "-1", "15000001"):
            with self.subTest(length=length):
                status, invalid_length = self.request_with_content_length(length)
                self.assertEqual(status, 400)
                self.assertIn("error", invalid_length)

        status, _, missing = self.request_json("GET", "/api/records/ISSUE-9999")
        self.assertEqual(status, 404)
        self.assertEqual(missing, {"error": "记录不存在"})

        with patch.object(self.repo, "list_projects", side_effect=RuntimeError("测试异常")):
            status, _, failure = self.request_json("GET", "/api/projects")
        self.assertEqual(status, 500)
        self.assertEqual(failure, {"error": "测试异常"})


if __name__ == "__main__":
    unittest.main()
