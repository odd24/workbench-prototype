import json
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

from server import Repository, WorkbenchHandler, WorkbenchHTTPServer
from workbench.agent_diagnostics import probe_mcp, run_bounded
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError, read_json
from workbench.agent_setup import setup_instructions


class AgentDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = Repository(self.base / "data")
        class Handler(WorkbenchHandler):
            def log_message(self, *_args):
                pass
        Handler.repository = self.repo
        self.server = WorkbenchHTTPServer(("127.0.0.1", 0), Handler)
        self.runtime = AgentRuntime(self.repo, port=self.server.server_address[1], base=self.base / "private")
        self.repo.agent_runtime = self.runtime
        self.runtime.set_enabled(True)
        self.security = self.runtime.security()
        self.info = self.security.add_client("diagnostic", ["read"], ["*"], ["*"], self.runtime.origin)
        self.config_path = Path(self.info["config_file"])
        self.config = read_json(self.config_path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.token = self.runtime.status(session=True)["management_token"]

    def tearDown(self):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and any(job["state"] == "running" for job in self.runtime.diagnostics.jobs.values()):
            time.sleep(0.02)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self.temp.cleanup()

    def request(self, resource, method="GET", payload=None, headers=None):
        values = {"X-Workbench-Management":"1", "X-Workbench-Management-Token": self.token, "Origin": self.runtime.origin, "Content-Type": "application/json"}
        values.update(headers or {})
        request = Request(self.runtime.origin + "/api/local/agent-management/" + resource,
                          data=json.dumps(payload).encode() if payload is not None else None, headers=values, method=method)
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def start(self, request_id="diagnostic-one"):
        return self.request("diagnostics", "POST", {"workspace_id": self.security.workspace_id, "client_id": self.info["client_id"], "request_id": request_id})

    def wait(self, operation):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            code, result = self.request("diagnostics/" + operation["operation_id"])
            self.assertEqual(code, 200, result)
            if result["state"] == "completed":
                return result
            time.sleep(0.03)
        self.fail("诊断未在规定时间完成")

    def test_real_bridge_handshake_tools_read_no_writes_and_nonce_separation(self):
        code, operation = self.start()
        self.assertEqual(code, 200, operation)
        result = self.wait(operation)
        steps = {item["name"]: item for item in result["steps"]}
        for name in ("service", "authorization", "configuration", "python", "mcp", "read"):
            self.assertEqual(steps[name]["state"], "passed", result)
        self.assertIn("12", steps["mcp"]["message"])
        self.assertEqual(self.start()[1]["operation_id"], operation["operation_id"])
        observed = self.runtime.diagnostics.observed(self.info["client_id"])
        self.assertIn("last_diagnostic_request_at", observed)
        self.assertNotIn("last_client_request_at", observed)
        self.assertNotIn(self.config["token"], json.dumps(result))
        self.assertNotIn("wbdiag-", json.dumps(result))
        self.assertEqual(Repository(self.repo.root).list_records(), [])
        self.assertEqual(Repository(self.repo.root).list_documents(), [])
        self.assertEqual(self.repo.agent_service.list_proposals(self.security.clients()[self.info["client_id"]], {})["items"], [])
        # A caller-supplied fake diagnostic header is not trusted attribution.
        request = Request(self.runtime.origin + "/api/agent/v1/capabilities", headers={"Authorization": "Bearer " + self.config["token"], "X-Workbench-Workspace": self.security.workspace_id, "X-Workbench-Diagnostic": "wbdiag-forged"})
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)
        self.assertIn("last_client_request_at", self.runtime.diagnostics.observed(self.info["client_id"]))

    def test_disabled_revoked_bad_config_and_wrong_origin_skip_dependencies(self):
        self.runtime.set_enabled(False)
        result = self.wait(self.start("disabled")[1])
        self.assertEqual(result["steps"][0]["state"], "failed")
        self.assertEqual(result["steps"][-1]["state"], "skipped")
        self.runtime.set_enabled(True)
        original = self.config_path.read_bytes()
        self.config_path.write_text("{broken", encoding="utf-8")
        result = self.wait(self.start("broken")[1])
        self.assertEqual(next(item for item in result["steps"] if item["name"] == "configuration")["state"], "failed")
        self.config_path.write_bytes(original)
        self.config_path.write_text(json.dumps({**self.config, "base_url": "http://127.0.0.1:1"}), encoding="utf-8")
        result = self.wait(self.start("wrong-origin")[1])
        self.assertIn("更新服务地址", next(item for item in result["steps"] if item["name"] == "configuration")["message"])
        self.config_path.write_bytes(original)
        self.security.change_client(self.info["client_id"])
        result = self.wait(self.start("revoked")[1])
        self.assertEqual(next(item for item in result["steps"] if item["name"] == "authorization")["state"], "failed")

    def test_task_dedup_validation_and_expired_session(self):
        entered = threading.Event()
        release = threading.Event()
        def probe(*_args):
            entered.set()
            release.wait(5)
            return {"protocol": "2025-11-25", "tool_count": 12, "read_ok": True}
        with patch("workbench.agent_diagnostics.probe_mcp", side_effect=probe):
            try:
                first = self.start("first")[1]
                self.assertTrue(entered.wait(5))
                second = self.start("second")[1]
                self.assertEqual(first["operation_id"], second["operation_id"])
                self.assertEqual(self.request("diagnostics", "POST", {"workspace_id": self.security.workspace_id, "client_id": self.info["client_id"], "request_id": "bad", "command": "whoami"})[0], 400)
            finally:
                release.set()
            self.wait(first)
        self.assertEqual(self.request("diagnostics/missing")[0], 404)
        self.runtime._expires = 0
        self.assertEqual(self.start("expired")[0], 403)

    def test_timeout_output_limits_and_process_cleanup(self):
        created = []
        original = subprocess.Popen
        def tracked(*args, **kwargs):
            value = original(*args, **kwargs)
            created.append(value)
            return value
        with patch("workbench.agent_diagnostics.subprocess.Popen", side_effect=tracked):
            with self.assertRaises(TimeoutError):
                run_bounded([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.1)
            for target in ("stdout", "stderr"):
                with self.assertRaises(ValueError):
                    run_bounded([sys.executable, "-c", f"import sys; sys.{target}.write('private-output' * 10000)"], limit=100)
        for process in created:
            self.assertIsNotNone(process.poll())
            self.assertTrue(process.stdin.closed and process.stdout.closed and process.stderr.closed)

    def test_protocol_pollution_and_timeout_are_redacted(self):
        setup = setup_instructions(self.security, self.info["client_id"], self.runtime.origin)
        with patch("workbench.agent_diagnostics.run_bounded", return_value=b"not-json-private\n"):
            with self.assertRaises(ValueError):
                probe_mcp(setup, "wbdiag-test")
        with patch("workbench.agent_diagnostics.probe_mcp", side_effect=TimeoutError("secret-error")):
            result = self.wait(self.start("timeout")[1])
            self.assertEqual(next(item for item in result["steps"] if item["name"] == "mcp")["state"], "failed")
            self.assertNotIn("secret-error", json.dumps(result))

    def test_missing_codex_does_not_prevent_bridge_and_space_sessions_are_distinct(self):
        with patch("workbench.agent_setup.shutil.which", return_value=None):
            result = self.wait(self.start("no-codex")[1])
        steps = {item["name"]: item for item in result["steps"]}
        self.assertEqual(steps["codex"]["state"], "warning")
        self.assertEqual(steps["read"]["state"], "passed")
        another = Repository(self.base / "other")
        runtime = AgentRuntime(another, base=self.base / "private")
        self.assertEqual(runtime.diagnostics.observed(self.info["client_id"]), {})
        with self.assertRaises(AgentError):
            runtime.diagnostics.get(result["operation_id"])

    def test_real_bridge_offline_reports_read_failure_without_business_write(self):
        import socket
        setup = setup_instructions(self.security, self.info["client_id"], self.runtime.origin)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.config_path.write_text(json.dumps({**self.config, "base_url": f"http://127.0.0.1:{port}"}), encoding="utf-8")
        result = probe_mcp(setup, "wbdiag-" + "x" * 40)
        self.assertFalse(result["read_ok"])
        self.assertEqual(result["error_code"], "service_unavailable")
        self.assertEqual(self.repo.list_records(), [])


if __name__ == "__main__":
    unittest.main()
