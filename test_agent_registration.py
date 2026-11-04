import json
import os
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from server import Repository
from workbench.agent_management import AgentManagement
from workbench.agent_registration import CodexRegistration
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError, read_json
from workbench.agent_setup import detect_codex


class CodexRegistrationTests(unittest.TestCase):
    def setUp(self):
        if not detect_codex():
            self.skipTest("真实隔离登记需要本机 Codex CLI")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "Codex 中文 & O'Brien % !"
        self.environment = patch.dict(os.environ, {"CODEX_HOME": str(self.home)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.repo = Repository(self.base / "data")
        self.runtime = AgentRuntime(self.repo, base=self.base / "private")
        self.runtime.set_enabled(True)
        self.security = self.runtime.security()
        self.client = AgentManagement(self.runtime).mutate("create", {"workspace_id": self.security.workspace_id,
            "request_id": "create", "name": "Codex", "scopes": ["read"], "project_ids": ["*"], "categories": []})["client_id"]
        self.registration = CodexRegistration(self.runtime, self.security)
        self.target = self.home / "config.toml"

    def preview(self, name="workbench"):
        return self.registration.preview(self.client, {"workspace_id": self.security.workspace_id, "name": name})

    def payload(self, preview=None, request="register", replace=False):
        preview = preview or self.preview()
        return {"workspace_id": self.security.workspace_id, "name": preview["name"], "expected_version": preview["expected_version"], "replace_existing": replace, "request_id": request}

    def write(self, content):
        self.home.mkdir(exist_ok=True)
        self.target.write_bytes(content)

    def test_real_cli_new_registration_persists_and_repeat_is_idempotent(self):
        preview = self.preview()
        self.assertEqual(preview["state"], "absent")
        self.assertFalse(self.home.exists(), "只检查不能初始化 Codex 目录")
        payload = self.payload(preview)
        result = self.registration.register(self.client, payload)
        self.assertTrue(result["registered"])
        persisted = tomllib.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(persisted["mcp_servers"]["workbench"], preview["desired"])
        original = self.target.read_bytes()
        self.assertEqual(CodexRegistration(self.runtime, self.security).register(self.client, payload), result)
        self.assertEqual(self.preview()["state"], "identical")
        self.registration.register(self.client, self.payload(request="identical"))
        self.assertEqual(self.target.read_bytes(), original)
        self.assertIsNone(result["backup_path"])
        with self.assertRaises(AgentError) as error:
            self.registration.register(self.client, {**payload, "name": "different"})
        self.assertEqual(error.exception.code, "request_conflict")
        self.target.write_bytes(original + b'\n# external change\n')
        changed = self.registration.get(payload["request_id"])
        self.assertTrue(changed["registered"])
        self.assertFalse(changed["configuration_unchanged"])
        self.assertEqual(self.registration.register(self.client, payload), changed)

    def test_conflict_requires_explicit_replace_and_preserves_other_settings_and_backup(self):
        original = b'# keep comment\nmodel = "example"\n[mcp_servers.workbench]\ncommand = "SECRET-COMMAND"\nargs = ["SECRET-ARG"]\n[mcp_servers.workbench.env]\nTOKEN = "SECRET-TOKEN"\n[mcp_servers.other]\nurl = "https://example.invalid/secret"\n'
        self.write(original)
        preview = self.preview()
        self.assertEqual(preview["state"], "conflict")
        self.assertNotIn("SECRET", json.dumps(preview))
        with self.assertRaises(AgentError) as error:
            self.registration.register(self.client, self.payload(preview))
        self.assertEqual(error.exception.code, "registration_conflict")
        self.assertEqual(self.target.read_bytes(), original)
        result = self.registration.register(self.client, self.payload(preview, replace=True))
        self.assertTrue(result["registered"])
        self.assertEqual(Path(result["backup_path"]).read_bytes(), original)
        changed = tomllib.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(changed["model"], "example")
        self.assertEqual(changed["mcp_servers"]["other"], {"url": "https://example.invalid/secret"})
        self.assertEqual(changed["mcp_servers"]["workbench"], preview["desired"])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_stale_preview_and_client_change_do_not_write(self):
        payload = self.payload()
        self.write(b'model = "external"\n')
        with self.assertRaises(AgentError) as error:
            self.registration.register(self.client, payload)
        self.assertEqual(error.exception.code, "version_conflict")
        payload = self.payload(request="permission")
        clients = self.security.clients()
        clients[self.client]["categories"] = ["*"]
        self.security.save_clients(clients)
        with self.assertRaises(AgentError) as error:
            self.registration.register(self.client, payload)
        self.assertEqual(error.exception.code, "version_conflict")
        self.assertEqual(self.target.read_bytes(), b'model = "external"\n')

    def test_invalid_configuration_missing_cli_and_strict_input(self):
        for content in (b'broken=[', b'\xff', b'mcp_servers = 3', b'x="' + b'a' * (2 * 1024 * 1024) + b'"'):
            self.write(content)
            with self.assertRaises(AgentError):
                self.preview()
            self.assertEqual(self.target.read_bytes(), content)
        self.target.unlink()
        with patch("workbench.agent_setup.detect_codex", return_value=None), self.assertRaises(AgentError) as error:
            self.preview()
        self.assertEqual(error.exception.code, "codex_missing")
        for payload in ({"workspace_id": "other", "name": "workbench"}, {"workspace_id": self.security.workspace_id, "name": "../path"}, {"workspace_id": self.security.workspace_id, "name": "ok", "command": "evil"}):
            with self.assertRaises((AgentError, ValueError)):
                self.registration.preview(self.client, payload)
        with self.assertRaises(AgentError):
            self.registration.get("../invalid")
        payload = self.payload(request="damaged-receipt")
        self.registration.register(self.client, payload)
        receipt = self.registration._operation(payload["request_id"]) / "receipt.json"
        original_receipt = receipt.read_bytes()
        for content in (b'broken', b'[]', original_receipt.replace(b'"schema_version": 1', b'"schema_version": 999')):
            receipt.write_bytes(content)
            with self.assertRaises(AgentError):
                self.registration.get(payload["request_id"])
            self.assertEqual(receipt.read_bytes(), content)
        receipt.write_bytes(original_receipt)
        self.runtime.set_enabled(False)
        with self.assertRaises(AgentError):
            self.preview()

    def test_generation_timeout_or_unexpected_cli_changes_preserve_original(self):
        self.write(b'model = "original"\n')
        for failure in (TimeoutError("timeout"), ValueError("oversize"), OSError("missing")):
            with patch("workbench.agent_registration.run_bounded", side_effect=failure), self.assertRaises(AgentError) as error:
                self.registration.register(self.client, self.payload())
            self.assertEqual(error.exception.code, "registration_failed")
            self.assertEqual(self.target.read_bytes(), b'model = "original"\n')
        def corrupt(_command, **kwargs):
            (Path(kwargs["env"]["CODEX_HOME"]) / "config.toml").write_text('model="unexpected"', encoding="utf-8")
        with patch("workbench.agent_registration.run_bounded", side_effect=corrupt), self.assertRaises(AgentError):
            self.registration.register(self.client, self.payload())
        self.assertEqual(self.target.read_bytes(), b'model = "original"\n')

    def test_each_crash_stage_is_queryable_after_new_manager_without_replay(self):
        self.write(b'model = "original"\n')
        for stage in ("prepared", "installed", "completed"):
            with self.subTest(stage=stage):
                self.write(b'model = "original"\n')
                payload = self.payload(request="crash-" + stage)
                def fail(current):
                    if current == stage:
                        raise OSError("simulated crash")
                with patch.object(self.registration, "checkpoint", side_effect=fail), self.assertRaises(OSError):
                    self.registration.register(self.client, payload)
                before_query = self.target.read_bytes()
                fresh = CodexRegistration(self.runtime, self.security)
                result = fresh.get(payload["request_id"])
                self.assertEqual(result["state"], "not_applied" if stage == "prepared" else "completed")
                self.assertEqual(self.target.read_bytes(), before_query)
                self.assertEqual(fresh.register(self.client, payload), result)
                self.assertEqual(Path(result["backup_path"]).read_bytes(), b'model = "original"\n')

    def test_external_change_at_install_and_during_recovery_never_overwritten(self):
        self.write(b'model = "original"\n')
        def external(stage):
            if stage == "prepared":
                self.write(b'model = "external"\n')
        payload = self.payload()
        with patch.object(self.registration, "checkpoint", side_effect=external), self.assertRaises(AgentError):
            self.registration.register(self.client, payload)
        self.assertEqual(self.registration.get(payload["request_id"])["state"], "recovery_required")
        self.assertEqual(self.target.read_bytes(), b'model = "external"\n')
        payload = self.payload(request="third-party")
        def fail(stage):
            if stage == "installed":
                raise OSError("crash")
        with patch.object(self.registration, "checkpoint", side_effect=fail), self.assertRaises(OSError):
            self.registration.register(self.client, payload)
        self.write(b'model = "third-party"\n')
        self.assertEqual(self.registration.get(payload["request_id"])["state"], "recovery_required")
        self.assertEqual(self.target.read_bytes(), b'model = "third-party"\n')

    def test_concurrent_duplicate_request_applies_once(self):
        payload = self.payload()
        results, failures = [], []
        def run():
            try:
                results.append(CodexRegistration(self.runtime, self.security).register(self.client, payload))
            except Exception as error:
                failures.append(error)
        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(15)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(list(self.registration.directory.glob("*/receipt.json"))), 1)
        config = read_json(self.security.config_dir / f"{self.client}.json")
        self.assertNotIn(config["token"], json.dumps(results))

    def test_real_process_exit_before_and_after_install_recovers_by_query(self):
        for stage in ("prepared", "installed"):
            with self.subTest(stage=stage):
                self.write(b'model = "original"\n')
                payload = self.payload(request="exit-" + stage)
                script = '''import json, os, sys
from pathlib import Path
from server import Repository
from workbench.agent_runtime import AgentRuntime
from workbench.agent_registration import CodexRegistration
repo = Repository(Path(sys.argv[1]))
runtime = AgentRuntime(repo, base=Path(sys.argv[2]))
runtime.set_enabled(True)
registration = CodexRegistration(runtime, runtime.security())
registration.checkpoint = lambda stage: os._exit(23) if stage == sys.argv[3] else None
registration.register(sys.argv[4], json.loads(sys.argv[5]))
'''
                result = subprocess.run([sys.executable, "-c", script, str(self.repo.root), str(self.runtime.base), stage, self.client, json.dumps(payload)], capture_output=True, timeout=15,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                self.assertEqual(result.returncode, 23, result.stderr.decode(errors="replace"))
                current = self.target.read_bytes()
                recovered = CodexRegistration(self.runtime, self.security).get(payload["request_id"])
                self.assertEqual(recovered["state"], "not_applied" if stage == "prepared" else "completed")
                self.assertEqual(self.target.read_bytes(), current)

    def test_different_workspaces_share_target_lock_and_reject_stale_configuration(self):
        other_runtime = AgentRuntime(Repository(self.base / "other-data"), base=self.runtime.base)
        other_runtime.set_enabled(True)
        other_security = other_runtime.security()
        other_client = other_security.add_client("Other", ["read"], ["*"], [], other_runtime.origin)["client_id"]
        other = CodexRegistration(other_runtime, other_security)
        preview = other.preview(other_client, {"workspace_id": other_security.workspace_id, "name": "other"})
        other_payload = {"workspace_id": other_security.workspace_id, "name": "other", "expected_version": preview["expected_version"], "request_id": "other", "replace_existing": False}
        prepared, release, waiting = threading.Event(), threading.Event(), threading.Event()
        first_payload = self.payload()
        failures = []
        def pause(stage):
            if stage == "prepared":
                prepared.set()
                if not release.wait(5):
                    raise TimeoutError("test release missing")
        def first():
            try:
                with patch.object(self.registration, "checkpoint", side_effect=pause):
                    self.registration.register(self.client, first_payload)
            except Exception as error:
                failures.append(error)
        def second():
            waiting.set()
            try:
                other.register(other_client, other_payload)
            except Exception as error:
                failures.append(error)
        one = threading.Thread(target=first)
        two = threading.Thread(target=second)
        one.start()
        self.assertTrue(prepared.wait(10))
        two.start()
        self.assertTrue(waiting.wait(1))
        self.assertTrue(two.is_alive())
        release.set()
        one.join(15)
        two.join(15)
        self.assertFalse(one.is_alive() or two.is_alive())
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], AgentError)
        self.assertEqual(failures[0].code, "version_conflict")
        document = tomllib.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(set(document["mcp_servers"]), {"workbench"})


if __name__ == "__main__":
    unittest.main()
