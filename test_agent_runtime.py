import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import Repository, WorkbenchHandler, WorkbenchHTTPServer, build_argument_parser
from workbench.agent_runtime import AgentRuntime, discover, startup_enabled
from workbench.agent_security import AgentError, read_json
from workbench.paths import relocate_repository


PREFIX = "/api/local/agent-management/"


class AgentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = Repository(self.base / "data")
        self.runtime = AgentRuntime(self.repo, base=self.base / "private")
        self.repo.agent_runtime = self.runtime

    def tearDown(self):
        self.temp.cleanup()

    def update(self, **values):
        status = self.runtime.status()
        return self.runtime.update({"workspace_id": status["workspace_id"], "expected_version": status["version"], "request_id": "request-" + str(len(self.runtime.operations)), **values})

    def test_read_only_discovery_and_default_disabled(self):
        before = sorted(str(p.relative_to(self.base)) for p in self.base.rglob("*"))
        self.assertEqual(self.runtime.status()["runtime_state"], "uninitialized")
        self.assertFalse(startup_enabled(self.repo.root, self.runtime.base))
        self.assertEqual(before, sorted(str(p.relative_to(self.base)) for p in self.base.rglob("*")))
        self.assertFalse(self.runtime.base.exists())

    def test_enable_persist_reload_and_cli_overrides(self):
        result = self.update(enabled=True, startup_preference=True)
        self.assertIsNone(result["preference_error"])
        self.assertTrue(result["status"]["enabled"])
        workspace = result["status"]["workspace_id"]
        self.assertTrue(read_json(self.runtime.base / workspace / "runtime.json")["startup_enabled"])
        other = Repository(self.repo.root)
        fresh = AgentRuntime(other, base=self.runtime.base)
        self.assertTrue(startup_enabled(other.root, fresh.base))
        self.assertFalse(startup_enabled(other.root, fresh.base, False))
        self.assertTrue(startup_enabled(other.root, fresh.base, True))
        fresh.set_enabled(True)
        self.assertTrue(fresh.status()["enabled"])
        self.update(enabled=False)
        self.assertFalse(self.runtime.status()["enabled"])
        self.assertTrue(self.runtime.status()["startup_preference"])
        self.assertEqual(self.runtime.status()["workspace_id"], workspace)
        args = build_argument_parser().parse_args(["--disable-agent"])
        self.assertTrue(args.disable_agent)
        with self.assertRaises(SystemExit), patch("sys.stderr"):
            build_argument_parser().parse_args(["--disable-agent", "--enable-agent"])

    def test_real_server_restart_reads_preference_and_explicit_disable(self):
        self.update(enabled=True, startup_preference=True)
        for extra, expected in (([], True), (["--disable-agent"], False)):
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            process = subprocess.Popen([sys.executable, "server.py", "--data-dir", str(self.repo.root), "--agent-config-dir", str(self.runtime.base), "--port", str(port), *extra], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 10
                health = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail("临时服务提前退出：" + process.stderr.read().decode(errors="replace"))
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.3) as response:
                            health = json.load(response)
                        break
                    except OSError:
                        time.sleep(0.05)
                self.assertIsNotNone(health)
                self.assertEqual(health["agent_enabled"], expected)
            finally:
                process.terminate()
                process.communicate(timeout=5)
        self.assertTrue(startup_enabled(self.repo.root, self.runtime.base))

    def test_version_space_idempotency_and_types(self):
        status = self.runtime.status()
        payload = {"workspace_id": None, "expected_version": status["version"], "request_id": "once", "enabled": True}
        first = self.runtime.update(payload)
        self.assertEqual(first, self.runtime.update(payload))
        with self.assertRaises(AgentError) as error:
            self.runtime.update({**payload, "enabled": False})
        self.assertEqual(error.exception.status, 409)
        with self.assertRaises(AgentError):
            self.runtime.update({**payload, "request_id": "old"})
        for changes in ({"enabled": "false"}, {"extra": True}, {"request_id": []}):
            with self.assertRaises(AgentError):
                self.runtime.update({**payload, **changes})

    def test_partial_failure_retains_runtime_and_retry_is_explicit(self):
        with patch("workbench.agent_runtime.private_write", side_effect=OSError("private failure")):
            result = self.update(enabled=True, startup_preference=True)
        self.assertTrue(result["status"]["enabled"])
        self.assertIsNotNone(result["preference_error"])
        self.assertFalse(discover(self.repo.root, self.runtime.base)["startup_preference"])
        self.assertIsNone(self.update(startup_preference=True)["preference_error"])
        self.assertTrue(startup_enabled(self.repo.root, self.runtime.base))

    def test_corrupt_preference_not_overwritten_and_nonloopback_rejected(self):
        self.update(enabled=True)
        preference = self.runtime.security().config_dir / "runtime.json"
        preference.write_text('{"schema_version":999}', encoding="utf-8")
        original = preference.read_bytes()
        self.assertFalse(startup_enabled(self.repo.root, self.runtime.base))
        self.assertIsNotNone(self.runtime.status()["preference_error"])
        result = self.update(startup_preference=True)
        self.assertIsNotNone(result["preference_error"])
        self.assertEqual(preference.read_bytes(), original)
        other = AgentRuntime(self.repo, host="0.0.0.0", base=self.runtime.base)
        with self.assertRaises(AgentError) as error:
            other.set_enabled(True)
        self.assertEqual(error.exception.status, 403)

    def test_migration_and_switch_use_target_settings_and_new_session(self):
        self.update(enabled=True, startup_preference=True)
        token = self.runtime.status(session=True)["management_token"]
        target = relocate_repository(self.repo, str(self.base / "migrated"), True, self.base / "location.json")
        self.assertEqual(target.agent_runtime.status()["workspace_id"], self.runtime.status()["workspace_id"])
        self.assertTrue(target.agent_runtime.status()["enabled"])
        with self.assertRaises(AgentError):
            target.agent_runtime.authorize(token)
        switched = relocate_repository(target, str(self.base / "another"), False, self.base / "location.json")
        self.assertEqual(switched.agent_runtime.status()["runtime_state"], "uninitialized")
        self.assertEqual(switched.agent_runtime.base, self.runtime.base)
        self.assertFalse((switched.root / ".agent" / "workspace.json").exists())

    def test_portable_backup_restores_new_identity_and_existing_space_preferences(self):
        import io
        import zipfile
        self.update(enabled=True, startup_preference=True)
        self.repo.create_project({"name": "备份项目"})
        source_id = self.runtime.status()["workspace_id"]
        archive = self.repo.export_zip()
        restored = self.base / "restored"
        restored.mkdir()
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            self.assertTrue(package.namelist())
            self.assertFalse(any(".agent" in name or "management-operations" in name or name.endswith("runtime.json") for name in package.namelist()))
            package.extractall(restored)
        # export_zip members may have a workbench wrapper; locate its project root.
        candidates = [restored, *restored.iterdir()]
        root = next(path for path in candidates if path.is_dir() and (path / "projects").is_dir())
        other = Repository(root)
        new_runtime = AgentRuntime(other, base=self.runtime.base)
        self.assertFalse(startup_enabled(root, self.runtime.base))
        new_runtime.set_enabled(True)
        self.assertNotEqual(new_runtime.status()["workspace_id"], source_id)
        self.assertEqual(new_runtime.security().clients(), {})
        other.agent_runtime = new_runtime
        state = new_runtime.status()
        new_runtime.update({"workspace_id": state["workspace_id"], "expected_version": state["version"], "request_id": "save-target", "startup_preference": True})
        switched = relocate_repository(self.repo, str(root), False, self.base / "location.json")
        self.assertTrue(switched.agent_runtime.status()["enabled"])
        self.assertEqual(switched.agent_runtime.status()["workspace_id"], new_runtime.status()["workspace_id"])


class AgentManagementHTTPTests(unittest.TestCase):
    def test_registration_http_requires_local_session_and_returns_persisted_result(self):
        with patch.dict(os.environ, {"CODEX_HOME": str(self.base / "isolated-codex")}):
            status = self.request("status")[1]
            headers = {"Origin": self.origin, "X-Workbench-Management-Token": status["management_token"]}
            self.request("runtime", "PATCH", {"workspace_id": None, "expected_version": status["version"], "request_id": "enable", "enabled": True}, headers)
            workspace = self.repo.agent_runtime.status()["workspace_id"]
            created = self.request("clients", "POST", {"workspace_id": workspace, "request_id": "create", "name": "Codex", "scopes": ["read"], "project_ids": ["*"], "categories": []}, headers)[1]
            route = f"clients/{created['client_id']}/registration-preview"
            payload = {"workspace_id": workspace, "name": "workbench"}
            for invalid in ({}, {**headers, "Origin": "http://evil.test"}, {**headers, "Authorization": "Bearer invalid"}, {**headers, "Sec-Fetch-Site": "cross-site"}):
                self.assertEqual(self.request(route, "POST", payload, invalid)[0], 403)
            for invalid in ({**payload, "path": "arbitrary"}, {**payload, "workspace_id": "other"}):
                self.assertIn(self.request(route, "POST", invalid, headers)[0], {400, 409})
            code, preview = self.request(route, "POST", payload, headers)
            self.assertEqual(code, 200, preview)
            self.assertFalse((self.base / "isolated-codex").exists())
            register = {**payload, "expected_version": preview["expected_version"], "replace_existing": False, "request_id": "http-register"}
            code, result = self.request(f"clients/{created['client_id']}/registration", "POST", register, headers)
            self.assertEqual(code, 200, result)
            self.assertTrue(result["registered"])
            self.assertEqual(self.request("registrations/http-register", headers=headers)[1], result)
            self.assertEqual(self.request("registrations/http-register")[0], 403)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = Repository(self.base / "data")
        class Handler(WorkbenchHandler):
            def log_message(self, *_args):
                pass
        Handler.repository = self.repo
        self.handler = Handler
        self.server = WorkbenchHTTPServer(("127.0.0.1", 0), Handler)
        self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.repo.agent_runtime = AgentRuntime(self.repo, port=self.server.server_address[1], base=self.base / "private")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self.temp.cleanup()

    def request(self, route, method="GET", payload=None, headers=None):
        values = {"X-Workbench-Management": "1"}
        values.update(headers or {})
        if payload is not None:
            values.setdefault("Content-Type", "application/json")
        request = Request(self.origin + PREFIX + route, data=json.dumps(payload).encode() if payload is not None else None, headers=values, method=method)
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")
            return response.status, json.loads(response.read())

    def test_status_no_side_effect_and_http_enable_query_disable(self):
        code, status = self.request("status")
        self.assertEqual(code, 200)
        self.assertFalse((self.base / "private").exists())
        payload = {"workspace_id": None, "expected_version": status["version"], "request_id": "http-enable", "enabled": True, "startup_preference": True}
        headers = {"Origin": self.origin, "X-Workbench-Management-Token": status["management_token"]}
        code, result = self.request("runtime", "PATCH", payload, headers)
        self.assertEqual(code, 200, result)
        self.assertTrue(result["status"]["enabled"])
        self.assertEqual(self.request("operations/http-enable", headers=headers)[1], result)
        self.assertEqual(self.request("runtime", "PATCH", payload, headers)[1], result)
        self.assertEqual(self.request("runtime", "PATCH", {**payload, "request_id": "stale"}, headers)[0], 409)
        status = self.request("status")[1]
        self.assertEqual(self.request("runtime", "PATCH", {**payload, "workspace_id": status["workspace_id"], "expected_version": status["version"], "request_id": "disable", "enabled": False}, headers)[0], 200)
        self.assertFalse(self.repo.agent_runtime.status()["enabled"])

    def test_boundary_missing_origin_token_agent_credentials_and_expiry(self):
        status = self.request("status")[1]
        payload = {"workspace_id": None, "expected_version": status["version"], "request_id": "no", "enabled": True}
        token = {"X-Workbench-Management-Token": status["management_token"]}
        for headers in ({}, token, {"Origin": self.origin}, {**token, "Origin": "http://evil.test"}, {**token, "Origin": self.origin, "Authorization": "Bearer invalid"}):
            self.assertEqual(self.request("runtime", "PATCH", payload, headers)[0], 403)
        for headers in ({"X-Workbench-Management": "0"}, {"Sec-Fetch-Site": "cross-site"}, {"Origin": "http://evil.test"}, {"Authorization": "Bearer invalid"}):
            self.assertEqual(self.request("status", headers=headers)[0], 403)
        self.repo.agent_runtime._expires = 0
        self.assertEqual(self.request("runtime", "PATCH", payload, {**token, "Origin": self.origin})[0], 403)
        self.assertEqual(self.request("status?unknown=x")[0], 400)
        self.assertEqual(self.request("operations/missing", headers={"X-Workbench-Management-Token": self.request("status")[1]["management_token"]})[0], 404)

    def test_close_waits_for_protected_write_and_concurrent_versions_conflict(self):
        status = self.request("status")[1]
        headers = {"Origin": self.origin, "X-Workbench-Management-Token": status["management_token"]}
        payload = {"workspace_id": None, "expected_version": status["version"], "request_id": "enable", "enabled": True}
        self.assertEqual(self.request("runtime", "PATCH", payload, headers)[0], 200)
        status = self.request("status")[1]
        payload.update(workspace_id=status["workspace_id"], expected_version=status["version"], enabled=False, request_id="close")
        finished = threading.Event()
        results = []
        def close():
            results.append(self.request("runtime", "PATCH", payload, headers))
            finished.set()
        with self.repo.write_lock:
            worker = threading.Thread(target=close)
            worker.start()
            self.assertFalse(finished.wait(0.1))
            self.assertTrue(self.repo.agent_service)
        worker.join(5)
        self.assertTrue(finished.is_set())
        self.assertEqual(results[0][0], 200)
        self.assertFalse(self.repo.agent_service)
        self.assertEqual(self.request("runtime", "PATCH", {**payload, "request_id": "another"}, headers)[0], 409)

    def test_client_management_http_scopes_conflicts_and_redaction(self):
        project = self.repo.create_project({"name": "HTTP 项目"})
        status = self.request("status")[1]
        headers = {"Origin": self.origin, "X-Workbench-Management-Token": status["management_token"]}
        enable = {"workspace_id": None, "expected_version": status["version"], "request_id": "enable", "enabled": True}
        workspace = self.request("runtime", "PATCH", enable, headers)[1]["status"]["workspace_id"]
        create = {"workspace_id": workspace, "request_id": "new-client", "name": "Codex", "scopes": ["read"], "project_ids": [project["id"]], "categories": []}
        code, result = self.request("clients", "POST", create, headers)
        self.assertEqual(code, 200, result)
        self.assertEqual(self.request("clients", "POST", create, headers)[1], result)
        code, listing = self.request("clients", headers=headers)
        self.assertEqual(code, 200)
        self.assertNotIn("token_hash", json.dumps(listing))
        self.assertNotIn("config_file", result)
        client_id = result["client_id"]
        config = read_json(self.repo.agent_runtime.security().config_dir / f"{client_id}.json")
        self.assertNotIn(config["token"], json.dumps(listing))
        mutation = {"workspace_id": workspace, "request_id": "rotate", "expected_version": result["version"]}
        code, rotated = self.request(f"clients/{client_id}/rotate", "POST", mutation, headers)
        self.assertEqual(code, 200, rotated)
        self.assertEqual(self.request(f"clients/{client_id}/rotate", "POST", {**mutation, "request_id": "stale"}, headers)[0], 409)
        op = self.request("operations/rotate", headers=headers)[1]
        self.assertEqual(op["state"], "completed")
        self.assertEqual(op["result"], rotated)
        edit = {**create, "expected_version": rotated["version"], "request_id": "edit", "name": "新名称"}
        code, edited = self.request(f"clients/{client_id}", "PATCH", edit, headers)
        self.assertEqual(code, 200, edited)
        self.assertEqual(self.request(f"clients/{client_id}/revoke", "POST", {**mutation, "request_id": "revoke", "expected_version": edited["version"]}, headers)[0], 200)
        self.assertFalse(self.request("clients", headers=headers)[1]["items"][0]["enabled"])
        self.assertEqual(self.request("clients", headers={**headers, "Authorization": "Bearer " + config["token"]})[0], 403)

    def test_dormant_client_http_strict_create_edit_clear_and_cas(self):
        from test_agent_capabilities import grants
        self.repo.agent_runtime.set_enabled(True)
        status = self.request("status")[1]
        headers = {"Origin": self.origin, "X-Workbench-Management-Token": status["management_token"]}
        create = {"workspace_id": status["workspace_id"], "request_id": "dormant-http", "name": "休眠独立客户端",
                  "scopes": ["read"], "kinds": [], "project_ids": [], "categories": [], "capability_grants": grants()}
        for bad in ({"activated": True}, {"capability_grants": None}, {"capability_grants": []}, {"capability_grants": {"schema_version": 99, "grants": []}}):
            self.assertEqual(self.request("clients", "POST", {**create, **bad}, headers)[0], 400)
        code, result = self.request("clients", "POST", create, headers)
        self.assertEqual(code, 200, result)
        self.assertEqual(self.request("clients", "POST", create, headers)[1], result)
        client_id = result["client_id"]
        listing = self.request("clients", headers=headers)[1]
        self.assertEqual(listing["items"][0]["kinds"], [])
        self.assertEqual(listing["items"][0]["capability_grant_state"], "dormant")
        self.assertNotIn("files.read", listing["capability_catalog"])
        config = read_json(self.repo.agent_runtime.security().config_dir / (client_id + ".json"))
        self.assertEqual(self.request("clients", "POST", create, {**headers, "Authorization": "Bearer " + config["token"]})[0], 403)
        edit = {**create, "request_id": "clear", "expected_version": result["version"], "capability_grants": {"schema_version": 1, "grants": []}}
        code, changed = self.request("clients/" + client_id, "PATCH", edit, headers)
        self.assertEqual(code, 200, changed)
        self.assertEqual(self.request("clients/" + client_id, "PATCH", {**edit, "request_id": "stale"}, headers)[0], 409)
        self.assertEqual(self.request("clients", headers=headers)[1]["items"][0]["capability_grants"]["grants"], [])


if __name__ == "__main__":
    unittest.main()
