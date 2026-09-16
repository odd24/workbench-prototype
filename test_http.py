import io
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

    def test_health_uses_temporary_repository_and_dynamic_port(self):
        status, headers, payload = self.request_json("GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertNotEqual(self.port, 0)
        self.assertEqual(headers.get_content_type(), "application/json")
        self.assertEqual(payload["data_dir"], str(self.repo.root))
        self.assertEqual(payload["app_version"], APP_VERSION)

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

    def test_bad_request_not_found_and_internal_error_statuses(self):
        status, _, bad_request = self.request_json("POST", "/api/projects", body=b"{")
        self.assertEqual(status, 400)
        self.assertIn("error", bad_request)

        status, _, missing = self.request_json("GET", "/api/records/ISSUE-9999")
        self.assertEqual(status, 404)
        self.assertEqual(missing, {"error": "记录不存在"})

        with patch.object(self.repo, "list_projects", side_effect=RuntimeError("测试异常")):
            status, _, failure = self.request_json("GET", "/api/projects")
        self.assertEqual(status, 500)
        self.assertEqual(failure, {"error": "测试异常"})


if __name__ == "__main__":
    unittest.main()
