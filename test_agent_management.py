import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import Repository
from workbench.agent_management import AgentManagement, CredentialManager, client_version
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError, AgentSecurity, read_json


class AgentManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = Repository(self.base / "data")
        self.project = self.repo.create_project({"name": "项目"})
        self.repo.save_document_categories(["原分类", "其他"])
        self.runtime = AgentRuntime(self.repo, base=self.base / "private")
        self.repo.agent_runtime = self.runtime
        self.runtime.set_enabled(True)
        self.security = self.runtime.security()
        self.management = AgentManagement(self.runtime)

    def tearDown(self):
        self.temp.cleanup()

    def create(self, request_id="create-one"):
        return self.management.mutate("create", {"workspace_id": self.security.workspace_id, "request_id": request_id,
            "name": "Codex", "scopes": ["read", "propose", "commit"], "project_ids": [self.project["id"]], "categories": ["原分类"]})

    def test_create_edit_rotate_revoke_persist_idempotency_and_scrub(self):
        result = self.create()
        self.assertEqual(self.create(), result)
        self.assertNotIn("config_file", result)
        clients = self.management.list_clients()["items"]
        self.assertEqual(len(clients), 1)
        self.assertNotIn("token_hash", clients[0])
        client_id = result["client_id"]
        config_path = self.security.config_dir / f"{client_id}.json"
        original = read_json(config_path)
        params = {"workspace_id": self.security.workspace_id, "request_id": "rotate-one", "expected_version": clients[0]["version"]}
        rotated = self.management.mutate("rotate", params, client_id)
        self.assertEqual(rotated, self.management.mutate("rotate", params, client_id))
        fresh = AgentSecurity(self.repo.root, self.base / "private")
        with self.assertRaises(AgentError):
            fresh.authenticate("Bearer " + original["token"], fresh.workspace_id)
        updated = read_json(config_path)
        self.assertEqual(fresh.authenticate("Bearer " + updated["token"], fresh.workspace_id)["client_id"], client_id)
        edited = self.management.mutate("edit", {"workspace_id": fresh.workspace_id, "request_id": "edit-one", "expected_version": rotated["version"],
            "name": "改名", "scopes": ["read"], "project_ids": [], "categories": ["其他"]}, client_id)
        self.assertEqual(AgentSecurity(self.repo.root, self.base / "private").clients()[client_id]["categories"], ["其他"])
        self.assertEqual(self.management.mutate("rotate", params, client_id), rotated)
        for path in (self.security.config_dir / "management-operations").glob("*.json"):
            self.assertNotIn(updated["token"], path.read_text(encoding="utf-8"))

    def test_stale_new_request_revoke_and_replay_after_revoke(self):
        result = self.create()
        client_id = result["client_id"]
        params = {"workspace_id": self.security.workspace_id, "request_id": "revoke", "expected_version": result["version"]}
        receipt = self.management.mutate("revoke", params, client_id)
        self.assertFalse(receipt["enabled"])
        self.assertEqual(self.management.mutate("revoke", params, client_id), receipt)
        with self.assertRaises(AgentError) as error:
            self.management.mutate("rotate", {**params, "request_id": "stale"}, client_id)
        self.assertEqual(error.exception.status, 409)
        with self.assertRaises(ValueError):
            self.management.mutate("rotate", {**params, "request_id": "revoked", "expected_version": receipt["version"]}, client_id)
        token = read_json(self.security.config_dir / f"{client_id}.json")["token"]
        with self.assertRaises(AgentError):
            self.security.authenticate("Bearer " + token, self.security.workspace_id)

    def test_invalid_inputs_missing_old_format_and_receipt_redaction(self):
        base = {"workspace_id": self.security.workspace_id, "request_id": "bad", "name": "Codex", "scopes": ["read"], "project_ids": [self.project["id"]], "categories": []}
        for changes in ({"scopes": ["commit"]}, {"project_ids": [], "categories": []}, {"categories": ["不存在"]}, {"project_ids": ["*", self.project["id"]]}, {"workspace_id": "other"}, {"extra": True}):
            with self.assertRaises((ValueError, AgentError)):
                self.management.mutate("create", {**base, **changes})
        with self.assertRaises(AgentError) as error:
            self.management.mutate("rotate", {"workspace_id": self.security.workspace_id, "request_id": "missing", "expected_version": "0" * 64}, "00000000-0000-0000-0000-000000000000")
        self.assertEqual(error.exception.status, 404)
        result = self.create()
        config = read_json(self.security.config_dir / f"{result['client_id']}.json")
        logs = list((self.security.config_dir / "management-operations").glob("*.json"))
        self.assertTrue(logs)
        for path in logs:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(config["token"], text)
            self.assertNotIn("before_config", text)
            self.assertEqual(read_json(path)["state"], "completed")
        self.assertNotIn("token", json.dumps(self.management.list_clients()))
        # Existing schema-v1 registry fields need no migration to be listed.
        self.assertEqual(read_json(self.security.registry)["schema_version"], 1)

    def test_each_failure_stage_recovers_without_reissuing_credentials(self):
        for stage in ("prepared", "config", "registry", "completed"):
            with self.subTest(stage=stage):
                before = set(self.security.clients())
                def fail(_self, current):
                    if current == stage:
                        raise OSError("injected")
                with patch.object(CredentialManager, "checkpoint", fail):
                    with self.assertRaises(OSError):
                        self.create("stage-" + stage)
                fresh = AgentSecurity(self.repo.root, self.base / "private")
                fresh.manager().recover()
                result = self.create("stage-" + stage)
                self.assertEqual(set(fresh.clients()) - before, {result["client_id"]})
                config = read_json(fresh.config_dir / f"{result['client_id']}.json")
                self.assertEqual(fresh.authenticate("Bearer " + config["token"], fresh.workspace_id)["client_id"], result["client_id"])
                self.assertEqual(fresh.manager().operation(result["operation_id"])["state"], "completed")

    def test_rotate_stages_recover_and_other_clients_still_authenticate(self):
        target = self.create()
        other = self.create("other")
        other_token = read_json(self.security.config_dir / f"{other['client_id']}.json")["token"]
        for stage in ("prepared", "config", "registry"):
            client = self.security.clients()[target["client_id"]]
            old_config = read_json(self.security.config_dir / f"{target['client_id']}.json")
            def fail(_self, current):
                if current == stage:
                    raise OSError("injected")
            with patch.object(CredentialManager, "checkpoint", fail), self.assertRaises(OSError):
                self.security.change_client(target["client_id"], True, client_version(client), "rotate-" + stage)
            self.assertEqual(self.security.authenticate("Bearer " + other_token, self.security.workspace_id)["client_id"], other["client_id"])
            with self.assertRaises(AgentError):
                self.security.authenticate("Bearer " + old_config["token"], self.security.workspace_id)
            self.security.manager().recover()
            config = read_json(self.security.config_dir / f"{target['client_id']}.json")
            self.assertNotEqual(config["token"], old_config["token"])
            self.security.authenticate("Bearer " + config["token"], self.security.workspace_id)

    def test_third_party_config_preserved_and_abandon_revokes(self):
        result = self.create()
        client_id = result["client_id"]
        with patch.object(CredentialManager, "checkpoint", side_effect=OSError("stop")), self.assertRaises(OSError):
            self.security.change_client(client_id, True, result["version"], "uncertain")
        path = self.security.config_dir / f"{client_id}.json"
        third_party = {**read_json(path), "token": "third-party-keep"}
        path.write_text(json.dumps(third_party), encoding="utf-8")
        report = self.security.manager().report()
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["state"], "recovery_required")
        self.assertEqual(read_json(path), third_party)
        self.security.manager().abandon(report[0]["operation_id"])
        self.assertFalse(self.security.clients()[client_id]["enabled"])
        self.assertEqual(read_json(path), third_party)
        self.assertEqual(self.security.manager().report(), [])
        log = read_json(self.security.config_dir / "management-operations" / (report[0]["operation_id"] + ".json"))
        self.assertNotIn("after_config", log)

    def test_real_process_crash_after_configuration_and_cli_recovery(self):
        script = """
import os, sys
from pathlib import Path
from workbench.agent_security import AgentSecurity
from workbench.agent_management import CredentialManager
security = AgentSecurity(Path(sys.argv[1]), Path(sys.argv[2]))
def checkpoint(self, stage):
    if stage == 'config': os._exit(73)
CredentialManager.checkpoint = checkpoint
security.add_client('crash', ['read'], ['*'], [], 'http://127.0.0.1:4173', request_id='real-crash')
"""
        result = subprocess.run([sys.executable, "-c", script, str(self.repo.root), str(self.base / "private")], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 73, result.stderr)
        result = subprocess.run([sys.executable, "server.py", "--data-dir", str(self.repo.root), "--agent-config-dir", str(self.base / "private"), "--agent-management-report"], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"operations": []})
        self.assertEqual(len(self.security.clients()), 1)
        client = next(iter(self.security.clients().values()))
        token = read_json(self.security.config_dir / (client["client_id"] + ".json"))["token"]
        self.security.authenticate("Bearer " + token, self.security.workspace_id)

    def test_category_rename_delete_and_empty_removal_do_not_regrant(self):
        result = self.create()
        client_id = result["client_id"]
        self.repo.rename_document_category("原分类", "新分类")
        self.assertEqual(self.security.clients()[client_id]["categories"], ["新分类"])
        self.repo.delete_document_category("新分类")
        self.assertEqual(self.security.clients()[client_id]["categories"], [])
        self.repo.save_document_categories(["新分类", "原分类", "其他"])
        self.assertEqual(self.security.clients()[client_id]["categories"], [])
        other = self.security.add_client("empty", ["read"], [], ["其他"], self.runtime.origin)
        self.repo.save_document_categories(["原分类"])
        self.assertEqual(self.security.clients()[other["client_id"]]["categories"], [])

    def test_real_concurrent_cli_writers_preserve_both_clients(self):
        command = [sys.executable, "server.py", "--data-dir", str(self.repo.root), "--agent-config-dir", str(self.base / "private"), "--agent-client-add", "parallel", "--agent-project", "*"]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        results = [process.communicate(timeout=15) for process in processes]
        for process, (_, error) in zip(processes, results):
            self.assertEqual(process.returncode, 0, error)
        ids = {json.loads(output)["client_id"] for output, _ in results}
        fresh = AgentSecurity(self.repo.root, self.base / "private")
        self.assertEqual(set(fresh.clients()), ids)
        self.assertEqual(len(ids), 2)

    def test_category_failure_is_fail_closed_and_invalid_input_changes_nothing(self):
        result = self.create()
        before = self.security.clients()[result["client_id"]]
        with self.assertRaises(ValueError):
            self.repo.save_document_categories(["长" * 81])
        self.assertEqual(self.security.clients()[result["client_id"]], before)
        with patch.object(self.repo._configuration_repository, "save_document_categories", side_effect=OSError("failed")), self.assertRaises(OSError):
            self.repo.rename_document_category("原分类", "新分类")
        self.assertEqual(self.security.clients()[result["client_id"]]["categories"], [])
        self.assertIn("原分类", self.repo.document_categories())
        # The business failure never grants the new name or a broad fallback.
        self.assertNotIn("新分类", self.repo.document_categories())

    def test_narrowed_permissions_reject_previously_previewed_proposal(self):
        result = self.create()
        client_id = result["client_id"]
        service = self.repo.agent_service
        client = self.security.clients()[client_id]
        proposal = service.prepare_proposal(client, {"request_id": "preview-old", "kind": "document", "operation": "create", "content": {"title": "待确认", "body": "正文", "category": "原分类"}})
        preview = service.preview_proposal(client, proposal["proposal_id"])
        self.management.mutate("edit", {"workspace_id": self.security.workspace_id, "request_id": "narrow", "expected_version": result["version"], "name": "Codex", "scopes": ["read"], "project_ids": [self.project["id"]], "categories": []}, client_id)
        with self.assertRaises(AgentError) as error:
            service.commit_proposal(self.security.clients()[client_id], proposal["proposal_id"], {"version": preview["version"], "preview_digest": preview["preview_digest"], "confirmation": {"mode": "agent_attested", "user_confirmed": True}})
        self.assertEqual(error.exception.status, 403)
        self.assertEqual(Repository(self.repo.root).list_documents(), [])

    def test_origin_repair_keeps_token_and_changes_management_version(self):
        result = self.create()
        path = self.security.config_dir / (result["client_id"] + ".json")
        before = read_json(path)
        self.runtime.port = 4999
        repaired = self.management.mutate("repair", {"workspace_id": self.security.workspace_id, "request_id": "repair-origin", "expected_version": result["version"]}, result["client_id"])
        after = read_json(path)
        self.assertEqual(after["base_url"], "http://127.0.0.1:4999")
        self.assertEqual(after["token"], before["token"])
        self.assertNotEqual(repaired["version"], result["version"])

    def test_corrupt_and_unknown_logs_refuse_recovery_without_overwrite(self):
        result = self.create()
        path = self.security.config_dir / "management-operations" / (result["operation_id"] + ".json")
        for raw in ('{broken', json.dumps({**read_json(path), "schema_version": 99})):
            original = path.read_bytes()
            try:
                path.write_text(raw, encoding="utf-8")
                with self.assertRaises(AgentError) as error:
                    self.security.manager().recover()
                self.assertEqual(error.exception.status, 503)
                self.assertEqual(path.read_text(encoding="utf-8"), raw)
                with self.assertRaises(AgentError):
                    self.security.manager().abandon(result["operation_id"])
            finally:
                path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
