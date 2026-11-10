import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from server import Repository, WorkbenchHandler, WorkbenchHTTPServer
from workbench.agent_security import AgentSecurity, read_json
from workbench.agent_service import AgentService
from workbench.paths import relocate_repository


class AgentAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = Repository(self.base / "data")
        self.project = self.repo.create_project({"name": "允许访问"})
        self.hidden = self.repo.create_project({"name": "禁止访问"})
        self.issue = self.repo.create_record({"type": "issue", "title": "中文问题", "project_id": self.project["id"], "body": "命令\necho 'hello'\n知识"})
        self.secret = self.repo.create_record({"type": "issue", "title": "隐藏问题", "project_id": self.hidden["id"], "body": "private"})
        self.document = self.repo.create_document({"title": "知识", "category": "允许", "body": "正文\n第二段"})
        self.hidden_doc = self.repo.create_document({"title": "隐藏知识", "category": "隐藏", "body": "private"})
        self.security = AgentSecurity(self.repo.root, self.base / "credentials")
        info = self.security.add_client("测试客户端", ["read", "propose", "commit"], [self.project["id"]], ["允许"], "http://127.0.0.1:4174")
        self.client_id = info["client_id"]
        self.config = read_json(Path(info["config_file"]))
        self.repo.agent_service = AgentService(self.repo, self.security)
        class Handler(WorkbenchHandler):
            def log_message(self, *_args):
                pass
        Handler.repository = self.repo
        self.handler = Handler
        self.server = WorkbenchHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self.temp.cleanup()

    def request(self, path, method="GET", payload=None, headers=None, auth=True):
        values = {"Authorization": "Bearer " + self.config["token"], "X-Workbench-Workspace": self.config["workspace_id"]} if auth else {}
        values.update(headers or {})
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        if data:
            values["Content-Type"] = "application/json"
        request = Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=values, method=method)
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            return response.status, json.loads(body) if response.headers.get_content_type() == "application/json" else body

    def test_capabilities_and_scoped_search_catalog_and_segment_reads(self):
        status, result = self.request("/api/agent/v1/capabilities")
        self.assertEqual(status, 200)
        self.assertEqual(result["workspace_id"], self.security.workspace_id)
        status, result = self.request("/api/agent/v1/projects")
        self.assertEqual([item["id"] for item in result["items"]], [self.project["id"]])
        self.assertNotIn("path", result["items"][0])
        status, result = self.request("/api/agent/v1/search?limit=1")
        self.assertEqual(status, 200)
        self.assertEqual(len(result["items"]), 1)
        self.assertIsNotNone(result["next_cursor"])
        status, result = self.request("/api/agent/v1/search?query=" + quote("知识"))
        self.assertEqual({item["id"] for item in result["items"]}, {self.issue["id"], self.document["id"]})
        self.assertTrue(all("file_path" not in item for item in result["items"]))
        self.assertEqual({item["id"] for item in self.request("/api/agent/v1/search?query=" + quote("普通"))[1]["items"]}, {self.issue["id"]})
        status, result = self.request("/api/agent/v1/catalog?project_id=" + quote(self.project["id"]))
        self.assertEqual(result["document_categories"], ["允许"])
        self.assertEqual(result["priorities"], ["低", "普通", "高", "紧急"])
        status, result = self.request(f"/api/agent/v1/items/issue/{self.issue['id']}?offset=2&length=4")
        self.assertEqual(status, 200)
        self.assertEqual(result["body"], self.issue["body"][2:6])
        self.assertEqual(result["next_offset"], 6)
        self.assertNotIn("file_path", result)

    def test_missing_revoked_rotated_credentials_and_scope_failures(self):
        self.assertEqual(self.request("/api/agent/v1/capabilities", auth=False)[0], 401)
        self.assertEqual(self.request("/api/agent/v1/capabilities", headers={"Authorization": "Bearer bad"})[0], 401)
        self.assertEqual(self.request("/api/agent/v1/capabilities", headers={"X-Workbench-Workspace": "wrong"})[0], 409)
        self.security.change_client(self.client_id, rotate=True)
        self.assertEqual(self.request("/api/agent/v1/capabilities")[0], 401)
        self.config = read_json(self.security.config_dir / f"{self.client_id}.json")
        self.assertEqual(self.request("/api/agent/v1/capabilities")[0], 200)
        clients = self.security.clients()
        clients[self.client_id]["scopes"] = ["propose"]
        self.security.save_clients(clients)
        self.assertEqual(self.request("/api/agent/v1/capabilities")[0], 403)
        self.security.change_client(self.client_id)
        self.assertEqual(self.request("/api/agent/v1/capabilities")[0], 401)
        with self.assertRaises(ValueError):
            self.security.change_client(self.client_id, rotate=True)

    def test_forbidden_resources_unknown_parameters_and_disabled_service(self):
        for suffix in (f"items/issue/{self.secret['id']}", f"items/document/{self.hidden_doc['id']}", "catalog?project_id=" + quote(self.hidden["id"])):
            self.assertEqual(self.request("/api/agent/v1/" + suffix)[0], 404)
        for suffix in ("projects?limit=0", "search?unknown=x", "search?limit=1&limit=2", f"items/document/{self.document['id']}?offset=-1"):
            self.assertEqual(self.request("/api/agent/v1/" + suffix)[0], 400)
        self.assertEqual(self.request("/api/agent/v2/projects")[0], 404)
        del self.repo.agent_service
        self.assertEqual(self.request("/api/agent/v1/capabilities")[0], 404)

    def test_host_origin_and_legacy_api_boundaries(self):
        for headers in ({"Host": "evil.example"}, {"Origin": "https://evil.example"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.request("/api/projects", auth=False, headers=headers)[0], 403)
        self.assertEqual(self.request("/api/projects")[0], 403)
        self.assertEqual(self.request("/api/projects", auth=False)[0], 200)
        self.assertEqual(self.request("/api/projects", auth=False, headers={"Origin": f"http://127.0.0.1:{self.port}"})[0], 200)

    def test_rate_limit_and_blank_unknown_parameter(self):
        self.assertEqual(self.request("/api/agent/v1/search?unknown=")[0], 400)
        from collections import deque
        import time
        self.repo.agent_service.request_windows[self.client_id] = deque([time.monotonic()] * 120)
        self.assertEqual(self.request("/api/agent/v1/capabilities")[0], 429)

    def test_static_whitelist_blocks_source_data_dot_paths_and_head(self):
        for path in ("/", "/index.html", "/app.js?v=123", "/js/core/api.js", "/css/tokens.css"):
            self.assertEqual(self.request(path, auth=False)[0], 200, path)
        for path in ("/server.py", "/AGENTS.md", "/workbench/agent_security.py", "/.git/config", "/workbench-data/config/settings.json", "/css/../server.py", "/%2e%2e/server.py", "/docs/", "/js/"):
            for method in ("GET", "HEAD"):
                self.assertEqual(self.request(path, method, auth=False)[0], 404, path)

    def test_static_allowlisted_symlink_is_not_followed(self):
        from unittest.mock import patch
        fake = self.base / "static"
        fake.mkdir()
        (fake / "index.html").write_text('<script src="app.js?v=1"></script>', encoding="utf-8")
        secret = self.base / "private.txt"
        secret.write_text("must not leak", encoding="utf-8")
        try:
            (fake / "app.js").symlink_to(secret)
        except OSError:
            # Windows junctions do not require the symlink privilege.
            if sys.platform != "win32":
                raise
            import _winapi
            external = self.base / "external-css"
            external.mkdir()
            (external / "preview.css").write_text("must not leak", encoding="utf-8")
            (fake / "index.html").write_text('<link href="css/preview.css?v=1">', encoding="utf-8")
            _winapi.CreateJunction(str(external), str(fake / "css"))
            with patch("workbench.http_api.APP_DIR", fake):
                self.assertEqual(self.request("/css/preview.css", auth=False)[0], 404)
        else:
            with patch("workbench.http_api.APP_DIR", fake):
                self.assertEqual(self.request("/app.js", auth=False)[0], 404)

    def test_credential_files_are_external_and_registry_has_only_hash(self):
        registry = self.security.registry.read_text(encoding="utf-8")
        self.assertNotIn(self.config["token"], registry)
        self.assertFalse(self.security.config_dir.is_relative_to(self.repo.root))
        with self.assertRaises(ValueError):
            AgentSecurity(self.repo.root, self.repo.root / "credentials")
        result = subprocess.run([sys.executable, "server.py", "--data-dir", str(self.repo.root), "--agent-config-dir", str(self.base / "credentials"), "--agent-client-add", "CLI 客户端", "--agent-project", self.project["id"]], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        info = json.loads(result.stdout)
        self.assertNotIn("token", info)
        self.assertEqual(read_json(Path(info["config_file"]))["workspace_id"], self.security.workspace_id)

    def test_http_proposals_preview_revise_commit_and_reload(self):
        for kind in ("issue", "document"):
            content = {"title": "HTTP 入库", "body": "原始总结", **({"project_id": self.project["id"]} if kind == "issue" else {"category": "允许"})}
            status, proposal = self.request("/api/agent/v1/proposals", "POST", {"request_id": "http-" + kind, "kind": kind, "operation": "create", "content": content})
            self.assertEqual(status, 200)
            route = "/api/agent/v1/proposals/" + proposal["proposal_id"]
            status, preview = self.request(route + "/preview")
            self.assertEqual(status, 200)
            payload = {"version": preview["version"], "preview_digest": preview["preview_digest"], "confirmation": {"mode": "agent_attested", "user_confirmed": True}}
            self.assertEqual(self.request(route + "/commit", "POST", {**payload, "body": "偷偷修改"})[0], 400)
            status, revised = self.request(route, "PATCH", {"expected_version": 1, "content": {**content, "body": "用户修改后的总结"}})
            self.assertEqual(status, 200)
            self.assertEqual(revised["version"], 2)
            self.assertEqual(self.request(route + "/commit", "POST", payload)[0], 409)
            status, preview = self.request(route + "/preview")
            payload.update(version=preview["version"], preview_digest=preview["preview_digest"])
            status, receipt = self.request(route + "/commit", "POST", payload)
            self.assertEqual(status, 200)
            self.assertEqual(self.request(route + "/commit", "POST", payload)[1], receipt)
            self.assertEqual(receipt["web_url"], f"http://127.0.0.1:{self.port}/?item={kind}&itemId={receipt['item_id']}")
            self.assertEqual(self.request(receipt["web_path"], auth=False)[0], 200)
            status, result = self.request(route)
            self.assertEqual(result["state"], "committed")
            getter = self.repo.get_record if kind == "issue" else self.repo.get_document
            self.assertEqual(getter(receipt["item_id"])[0]["body"], "用户修改后的总结")
            fresh = Repository(self.repo.root)
            getter = fresh.get_record if kind == "issue" else fresh.get_document
            self.assertEqual(getter(receipt["item_id"])[0]["body"], "用户修改后的总结")

    def test_proposal_http_scope_json_body_and_request_limits(self):
        spec = {"request_id": "bad", "kind": "issue", "operation": "create", "content": {"title": "标题", "project_id": self.hidden["id"]}}
        self.assertEqual(self.request("/api/agent/v1/proposals", "POST", spec)[0], 404)
        self.assertEqual(self.request("/api/agent/v1/proposals", "POST", ["not an object"])[0], 400)
        import http.client
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.putrequest("POST", "/api/agent/v1/proposals")
            connection.putheader("Content-Length", str(1024 * 1024 + 1))
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Authorization", "Bearer " + self.config["token"])
            connection.putheader("X-Workbench-Workspace", self.config["workspace_id"])
            connection.endheaders()
            response = connection.getresponse()
            self.assertEqual(response.status, 413)
            response.read()
        finally:
            connection.close()
        clients = self.security.clients()
        clients[self.client_id]["scopes"] = ["read"]
        self.security.save_clients(clients)
        self.assertEqual(self.request("/api/agent/v1/proposals", "POST", spec)[0], 403)

    def test_real_cli_launch_enables_agent_without_exposing_credentials(self):
        import socket
        import time
        root = self.base / "cli-launch"
        security = AgentSecurity(root, self.base / "cli-credentials")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        info = security.add_client("CLI", ["read"], [], [], f"http://127.0.0.1:{port}")
        config = read_json(Path(info["config_file"]))
        process = subprocess.Popen([sys.executable, "server.py", "--data-dir", str(root), "--agent-config-dir", str(self.base / "cli-credentials"), "--enable-agent", "--port", str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 8
            while True:
                if process.poll() is not None:
                    self.fail(process.stderr.read().decode("utf-8", "replace"))
                try:
                    with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
                        self.assertTrue(json.load(response)["agent_enabled"])
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(0.05)
            request = Request(f"http://127.0.0.1:{port}/api/agent/v1/capabilities", headers={"Authorization": "Bearer " + config["token"], "X-Workbench-Workspace": security.workspace_id})
            with urlopen(request, timeout=3) as response:
                self.assertEqual(json.load(response)["workspace_id"], security.workspace_id)
        finally:
            process.terminate()
            process.wait(5)
            process.stderr.close()

    def test_workspace_migration_rebinds_service_and_old_identity_rejected(self):
        with self.repo.write_lock:
            new = relocate_repository(self.repo, str(self.base / "migrated"), True, self.base / "location.json")
            self.handler.repository = new
        self.assertEqual(self.request("/api/agent/v1/capabilities")[1]["workspace_id"], self.security.workspace_id)
        with new.write_lock:
            opened = relocate_repository(new, str(self.base / "different"), False, self.base / "location.json")
            self.handler.repository = opened
        self.assertEqual(self.request("/api/agent/v1/capabilities")[0], 409)


    def test_dormant_http_has_no_metadata_or_new_operations(self):
        from test_agent_capabilities import grants
        info = self.security.add_client('dormant', ['read', 'propose', 'commit'], [], [], 'http://127.0.0.1:4174', kinds=[], capability_grants=grants())
        self.config = read_json(Path(info['config_file']))
        result = self.request('/api/agent/v1/capabilities')[1]
        self.assertEqual(result['kinds'], [])
        self.assertEqual(result['capability_authorization']['effective'], [])
        for route in ('projects', 'search'):
            self.assertEqual(self.request('/api/agent/v1/' + route)[1]['items'], [])
        self.assertEqual(self.request('/api/agent/v1/catalog')[1], {'tags': [], 'document_categories': []})
        self.assertEqual(self.request('/api/agent/v1/items/issue/' + self.issue['id'])[0], 404)
        from workbench.agent_file_handles import SUPPORTED
        code, files = self.request('/api/agent/v1/files')
        self.assertEqual(code, 200 if SUPPORTED else 503)
        if SUPPORTED:
            self.assertEqual(files, {'items': []})
        self.assertEqual(self.request('/api/agent/v1/files/00000000-0000-0000-0000-000000000000')[0], 404 if SUPPORTED else 503)
        for route in ('attachments', 'uploads'):
            self.assertEqual(self.request('/api/agent/v1/' + route)[0], 404)
        self.assertEqual(result['project_creation']['effective'], False)
        self.assertNotIn('project', result['kind_operations'])
        denied, error = self.request('/api/agent/v1/proposals', 'POST',
                                     {'request_id':'no-project', 'kind':'project', 'operation':'create', 'content':{'name':'禁止'}})
        self.assertEqual((denied, error['code']), (403, 'forbidden'))
        self.assertFalse((self.repo.projects_dir / '禁止').exists())
        self.assertEqual(self.request('/api/agent/v1/proposals', 'POST', {'request_id':'no-issue', 'kind':'issue', 'operation':'create', 'content':{'title':'禁止', 'project_id':self.project['id']}})[0], 403)


if __name__ == "__main__":
    unittest.main()
