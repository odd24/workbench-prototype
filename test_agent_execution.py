"""Schema-3 production Markdown execution and legacy journal compatibility."""

import copy
import json
import socket
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from test_agent_support import AgentFixture
from workbench.agent_execution import concrete_plan, fingerprint
from workbench.agent_management import client_version
from workbench.agent_proposals import digest
from workbench.agent_security import AgentError, read_json
from workbench.persistence import atomic_write_json
from workbench.markdown_io import load_markdown
from workbench.agent_runtime import AgentRuntime
from workbench.agent_proposal_management import ProposalManagement


class ExecutionTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        params = {key: self.client[key] for key in ("name", "scopes", "project_ids", "categories")}
        self.security.manager().run("edit", {**params, "kinds": ["issue", "document", "todo", "info"]}, self.client["client_id"], client_version(self.client))
        self.client = self.security.clients()[self.client["client_id"]]

    def candidate(self, kind="issue", operation="create", target=None, **changes):
        content = {"title": "执行候选", "body": "已预览正文", "tags": [], **({"category": "允许"} if kind == "document" else {"project_id": self.project["id"]})}
        if operation != "create":
            content = {"body": "追加内容" if operation == "append" else "更新内容"}
        content.update(changes)
        return {"request_id": uuid.uuid4().hex, "kind": kind, "operation": operation, "content": content,
                **({"target_id": target["id"], "base_revision": target["revision"]} if target else {})}

    def update_preview(self, kind="issue"):
        receipt = self.commit(self.prepare_preview(self.candidate(kind)))
        item = self.service.get_item(self.client, kind, receipt["item_id"])
        return self.prepare_preview(self.candidate(kind, "update", item)), item

    def interrupt(self, preview, stage):
        def fault(value):
            if value == stage:
                raise OSError("fault after durable write")
        with patch.object(self.store, "checkpoint", side_effect=fault), self.assertRaises(AgentError) as error:
            self.commit(preview)
        self.assertEqual(error.exception.code, "commit_interrupted")

    def manifest(self, preview):
        path = self.store.operations / f"{preview['proposal_id']}-{preview['version']}" / "manifest.json"
        return path, read_json(path)

    def test_four_types_three_operations_and_replay_use_real_handler(self):
        for kind in ("issue", "document", "todo", "info"):
            target = None
            for operation in ("create", "append", "update"):
                preview = self.prepare_preview(self.candidate(kind, operation, target))
                self.assertEqual(preview["digest_algorithm"], "sha256-json-v3")
                self.assertEqual(preview["execution_plan"]["handler"], "markdown@1")
                receipt = self.commit(preview)
                self.assertEqual(self.commit(preview), receipt)
                path, manifest = self.manifest(preview)
                self.assertEqual(manifest["step_states"], ["completed", "completed"])
                self.assertEqual(manifest["execution_schema_version"], 1)
                self.assertEqual(receipt["plan_digest"], preview["plan_digest"])
                target = self.service.get_item(self.client, kind, receipt["item_id"])
                self.assertEqual(target["revision"], receipt["revision"])
        self.reload()
        self.assertFalse(self.store.blocked)

    def test_relevant_status_set_members_added_removed_conflict(self):
        for operation in ("add", "remove"):
            self.tearDown(); self.setUp()
            preview = self.prepare_preview()
            path = self.repo.config_dir / "workflow-templates.json"
            values = read_json(path)
            template = next(value for value in values if value["id"] == self.repo.project(self.project["id"])["workflow_template"])
            if operation == "add":
                template["statuses"]["issue"].append({"name": "新增成员", "color": "#123456", "completed": False})
            else:
                template["statuses"]["issue"].pop()
            atomic_write_json(path, values)
            with self.assertRaises(AgentError) as error:
                self.commit(preview)
            self.assertEqual(error.exception.code, "dependency_changed")
            self.assertFalse(list(self.store.operations.glob("*/manifest.json")))

    def test_unrelated_project_description_sort_category_and_item_do_not_conflict(self):
        preview = self.prepare_preview()
        self.repo.update_project(self.project["id"], {"description": "无关说明变化", "issue_record_sort": "title"})
        self.repo.create_project({"name": "无关项目"})
        self.repo.ensure_document_category("无关分类")
        self.repo.create_record({"type": "info", "project_id": self.project["id"], "title": "无关条目"})
        self.assertEqual(self.commit(preview)["version"], 1)

    def test_fixed_reference_revision_changes_conflict_without_binding_other_items(self):
        receipt = self.commit(self.prepare_preview())
        item = self.service.get_item(self.client, "issue", receipt["item_id"])
        preview = self.prepare_preview(self.candidate(body="引用 [[" + item["id"] + "]]"))
        self.repo.update_record(item["id"], {"body": "引用对象已变"})
        with self.assertRaises(AgentError) as error:
            self.commit(preview)
        self.assertEqual(error.exception.code, "dependency_changed")

    def test_history_partial_application_rechecks_revocation_before_body_publish(self):
        preview, item = self.update_preview()
        self.interrupt(preview, "history")
        path, manifest = self.manifest(preview)
        self.assertEqual(manifest["step_states"], ["pending", "pending"])
        self.security.change_client(self.client["client_id"])
        self.reload()
        self.assertTrue(self.store.blocked)
        self.assertEqual(self.repo.get_record(item["id"])[0]["body"], item["body"])
        self.assertEqual(len(self.repo.list_history(item["id"])), 1)
        self.assertFalse((self.store.receipts / (preview["proposal_id"] + ".json")).exists())

    def test_body_after_image_finishes_original_receipt_despite_revocation(self):
        preview, item = self.update_preview()
        self.interrupt(preview, "target")
        self.security.change_client(self.client["client_id"])
        self.reload()
        result = self.store._load(preview["proposal_id"])
        self.assertEqual(result["state"], "committed")
        self.assertEqual(self.repo.get_record(item["id"])[0]["body"], "更新内容")
        self.assertEqual(len(self.repo.list_history(item["id"])), 1)

    def test_kind_directory_tampering_with_recomputed_hashes_never_publishes(self):
        preview = self.prepare_preview()
        self.interrupt(preview, "manifest")
        path, manifest = self.manifest(preview)
        proposal = self.store._load(preview["proposal_id"])
        manifest["kind"] = "document"
        manifest["relative_path"] = f"documents/{manifest['item_id']}-wrong.md"
        manifest["execution_plan"] = concrete_plan(manifest, proposal)
        manifest["execution_plan_digest"] = fingerprint(manifest["execution_plan"])
        manifest["receipt"]["execution_plan_digest"] = manifest["execution_plan_digest"]
        atomic_write_json(path, manifest)
        before = {value: value.read_bytes() for value in self.store.root.rglob("*.json")}
        self.assertTrue(self.store.recover()["blocked"])
        self.assertEqual(before, {value: value.read_bytes() for value in self.store.root.rglob("*.json")})
        self.assertFalse((self.repo.root / manifest["relative_path"]).exists())
        with self.assertRaises(AgentError): self.store.abandon(manifest["operation_id"])

    def test_unknown_format_preflight_is_zero_write_and_protects_cleanup(self):
        preview, _ = self.update_preview()
        self.interrupt(preview, "manifest")
        path, manifest = self.manifest(preview)
        original = copy.deepcopy(manifest)
        proposal_path = self.store.proposals / (preview["proposal_id"] + ".json")
        original_proposal = read_json(proposal_path)
        for change in ("version", "step", "algorithm", "confirmation", "cleaned", "proposal_id"):
            atomic_write_json(proposal_path, original_proposal)
            manifest = copy.deepcopy(original)
            if change == "version": manifest["execution_schema_version"] = 99
            elif change == "step": manifest["execution_plan"]["steps"] = ["shell"]
            elif change == "algorithm": manifest["digest_algorithm"] = "sha256-future"
            elif change == "confirmation": manifest["confirmation"]["user_confirmed"] = False
            elif change == "cleaned":
                proposal = read_json(proposal_path); proposal["content_cleaned"] = True; atomic_write_json(proposal_path, proposal)
            else:
                proposal = read_json(proposal_path); proposal["proposal_id"] = str(uuid.uuid4()); atomic_write_json(proposal_path, proposal)
            atomic_write_json(path, manifest)
            before = {value: value.read_bytes() for value in self.store.root.rglob("*") if value.is_file()}
            self.assertTrue(self.store.recover()["blocked"])
            with self.assertRaises(AgentError): self.store.cleanup()
            with self.assertRaises(AgentError): self.store.abandon(manifest["operation_id"])
            self.assertEqual(before, {value: value.read_bytes() for value in self.store.root.rglob("*") if value.is_file()})

    def test_mixed_legacy_previews_keep_bytes_and_recover_original_schemas(self):
        previews = []
        originals = {}
        for schema in (1, 2, 3):
            proposal = self.service.prepare_proposal(self.client, self.candidate())
            saved = self.store._load(proposal["proposal_id"])
            if schema < 3:
                saved["schema_version"] = schema
                for key in ("execution_plan", "plan_digest", "authorization_revision", "dependencies"):
                    saved.pop(key)
                if schema == 1:
                    for key in ("digest_algorithm", "confirmation_mode", "approval"): saved.pop(key)
                else: saved["digest_algorithm"] = "sha256-json-v2"
                self.store._save(saved)
            preview = self.service.preview_proposal(self.client, saved["proposal_id"])
            previews.append(preview)
            originals[saved["proposal_id"]] = (self.store.proposals / (saved["proposal_id"] + ".json")).read_bytes()
        self.reload()
        for proposal_id, before in originals.items():
            self.assertEqual((self.store.proposals / (proposal_id + ".json")).read_bytes(), before)
        for schema, preview in zip((1, 2, 3), previews):
            self.interrupt(preview, "manifest")
            self.reload()
            result = self.service.get_proposal(self.client, preview["proposal_id"])
            self.assertEqual(result["schema_version"], schema)
            self.assertEqual(result["preview_digest"], preview["preview_digest"])
            self.assertEqual(self.commit(preview), result["receipt"])
        # A real schema-2 update journal retains its original history replay behavior.
        item = self.service.get_item(self.client, "issue", result["receipt"]["item_id"])
        legacy = self.service.prepare_proposal(self.client, self.candidate("issue", "update", item))
        saved = self.store._load(legacy["proposal_id"])
        saved.update(schema_version=2, digest_algorithm="sha256-json-v2")
        for key in ("execution_plan", "plan_digest", "authorization_revision", "dependencies"): saved.pop(key)
        self.store._save(saved)
        preview = self.service.preview_proposal(self.client, saved["proposal_id"])
        self.interrupt(preview, "history")
        self.reload()
        self.assertEqual(self.store._load(saved["proposal_id"])["preview_digest"], preview["preview_digest"])
        self.assertEqual(self.commit(preview)["item_id"], item["id"])
        self.assertEqual(len(self.repo.list_history(item["id"])), 1)

    def test_cleanup_keeps_inflight_and_receipts_survive_snapshot_removal(self):
        preview, item = self.update_preview()
        self.interrupt(preview, "history_logged")
        with self.assertRaises(AgentError): self.store.cancel(self.store._load(preview["proposal_id"]), preview["version"])
        self.store.cleanup()
        path, manifest = self.manifest(preview)
        self.assertTrue((path.parent / "before.md").exists())
        self.reload()
        result = self.store._load(preview["proposal_id"])
        receipt = result["receipt"]
        result["finished_at"] = "2000-01-01T00:00:00+00:00"; self.store._save(result)
        self.store.cleanup()
        self.assertFalse((path.parent / "after.md").exists())
        self.assertEqual(self.commit(preview), receipt)

    def test_preflight_does_not_scan_operations_once_per_completed_proposal(self):
        receipt = self.commit(self.prepare_preview())
        for _ in range(15): self.commit(self.prepare_preview())
        source = self.store._load(receipt["proposal_id"])
        for _ in range(120):
            value = copy.deepcopy(source); value["proposal_id"] = str(uuid.uuid4()); value["request_id"] = uuid.uuid4().hex
            value["state"] = "cancelled"; self.store._save(value)
        original = Path.glob
        original_read = Path.read_bytes
        scans = []
        markdown_reads = []
        def counted(path, pattern):
            if path == self.store.operations: scans.append(pattern)
            return original(path, pattern)
        def counted_read(path):
            if path.suffix == ".md": markdown_reads.append(path)
            return original_read(path)
        with patch.object(Path, "glob", counted), patch.object(Path, "read_bytes", counted_read): self.store.preflight()
        self.assertEqual(scans, ["*/manifest.json"])
        self.assertEqual(markdown_reads, [])  # Terminal format/receipt checks do not reread content snapshots.

    def test_web_approval_binds_plan_and_unknown_action_format_is_zero_write(self):
        runtime = AgentRuntime(self.repo, base=self.base / "credentials")
        self.repo.agent_runtime = runtime
        management = ProposalManagement(runtime)
        request = self.candidate(); request["confirmation_mode"] = "local_web"
        proposal = self.service.prepare_proposal(self.client, request)
        detail = management.preview(proposal["proposal_id"])
        payload = {"workspace_id": self.security.workspace_id, "version": detail["version"], "preview_digest": detail["preview"]["preview_digest"], "preview_ticket": detail["preview_ticket"], "request_id": "web-plan"}
        with patch.object(management, "checkpoint", side_effect=lambda stage: (_ for _ in ()).throw(OSError()) if stage == "approval_committed" else None), self.assertRaises(OSError):
            management.approve(proposal["proposal_id"], payload)
        result = management.action("web-plan")
        self.assertEqual(result["state"], "completed")
        self.assertEqual(management.approve(proposal["proposal_id"], payload), result)
        action_path = management._action_path("web-plan")
        action = read_json(action_path)
        self.assertEqual(action["schema_version"], 3)
        self.assertEqual(action["approval"]["plan_digest"], detail["preview"]["plan_digest"])
        for change in ("version", "authorization", "receipt"):
            corrupted = copy.deepcopy(action)
            if change == "version": corrupted["schema_version"] = 99
            elif change == "authorization": corrupted["approval"]["authorization_revision"] = []
            else: corrupted["result"]["proposal_id"] = str(uuid.uuid4())
            atomic_write_json(action_path, corrupted)
            before = {value: value.read_bytes() for value in self.store.root.rglob("*") if value.is_file()}
            self.assertTrue(self.store.recover()["blocked"])
            with self.assertRaises(AgentError): management.action("web-plan")
            self.assertEqual(before, {value: value.read_bytes() for value in self.store.root.rglob("*") if value.is_file()})

    def test_tightened_policy_keeps_schema3_and_rebinds_new_preview(self):
        preview = self.prepare_preview()
        params = {key: self.client[key] for key in ("name", "scopes", "project_ids", "categories", "kinds")}
        self.security.manager().run("edit", {**params, "minimum_confirmation_mode": "local_web"}, self.client["client_id"], client_version(self.client))
        self.client = self.security.clients()[self.client["client_id"]]
        runtime = AgentRuntime(self.repo, base=self.base / "credentials"); self.repo.agent_runtime = runtime
        management = ProposalManagement(runtime)
        detail = management.preview(preview["proposal_id"])
        self.assertEqual(self.store._load(preview["proposal_id"])["schema_version"], 3)
        self.assertEqual(detail["version"], 2)
        payload = {"workspace_id": self.security.workspace_id, "version": detail["version"], "preview_digest": detail["preview"]["preview_digest"], "preview_ticket": detail["preview_ticket"], "request_id": "tightened"}
        self.assertEqual(management.approve(preview["proposal_id"], payload)["state"], "completed")


    def test_real_process_exit_before_and_after_step_progress_logging(self):
        script = '''
import os, sys
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity, read_json
from workbench.agent_service import AgentService
repo=Repository(Path(sys.argv[1])); security=AgentSecurity(repo.root,Path(sys.argv[2])); service=AgentService(repo,security)
confirmed=read_json(Path(sys.argv[3]))
def fault(stage):
    if stage==sys.argv[4]: os._exit(79)
service.store.checkpoint=fault
service.commit_proposal(security.clients()[confirmed['client_id']],confirmed['proposal_id'],confirmed['payload'])
'''
        for stage in ("snapshots", "manifest", "committing", "applying", "history", "history_logged", "target", "target_logged", "receipt", "proposal"):
            with self.subTest(stage=stage):
                self.tearDown(); self.setUp()
                preview, item = self.update_preview()
                confirmed = self.base / "confirmed.json"
                atomic_write_json(confirmed, {"client_id": self.client["client_id"], "proposal_id": preview["proposal_id"], "payload": self.confirmation(preview)})
                process = subprocess.run([sys.executable, "-c", script, str(self.repo.root), str(self.base / "credentials"), str(confirmed), stage], capture_output=True, timeout=20)
                self.assertEqual(process.returncode, 79, process.stderr)
                self.reload()
                if stage == "snapshots": self.commit(preview)
                result = self.store._load(preview["proposal_id"])
                self.assertEqual(result["state"], "committed", self.store.recovery_report())
                self.assertEqual(self.commit(preview), result["receipt"])
                self.assertEqual(len(self.repo.list_history(item["id"])), 1)
                self.assertEqual(self.repo.get_record(item["id"])[0]["body"], "更新内容")

    def test_disabled_real_server_recovers_with_private_auth_and_blocks_without_it(self):
        for available in (True, False):
            with self.subTest(private_auth=available):
                self.tearDown(); self.setUp()
                preview, item = self.update_preview()
                self.interrupt(preview, "history")
                with socket.socket() as listener:
                    listener.bind(("127.0.0.1", 0)); port = listener.getsockname()[1]
                process = subprocess.Popen([sys.executable, "server.py", "--data-dir", str(self.repo.root), "--agent-config-dir", str(self.base / ("credentials" if available else "unavailable")), "--disable-agent", "--port", str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                try:
                    health = None
                    deadline = time.monotonic() + 12
                    while time.monotonic() < deadline:
                        try:
                            with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response: health = json.load(response)
                            break
                        except OSError: time.sleep(0.05)
                    self.assertIsNotNone(health)
                    self.assertFalse(health["agent_enabled"])
                    _, manifest = self.manifest(preview)
                    self.assertEqual(manifest["state"], "committed" if available else "applying")
                    _, disk_body = load_markdown(Path(item["file_path"]) if "file_path" in item else self.repo.get_record(item["id"])[1])
                    self.assertEqual(disk_body, "更新内容" if available else item["body"])
                finally:
                    process.terminate(); process.wait(10)
                    process.stderr.close()

    def test_authorization_revision_requires_new_preview_and_concurrent_replay_is_once(self):
        preview, item = self.update_preview()
        params = {key: self.client[key] for key in ("name", "scopes", "project_ids", "categories", "kinds")}
        self.security.manager().run("edit", {**params, "name": "授权版本变化"}, self.client["client_id"], client_version(self.client))
        self.client = self.security.clients()[self.client["client_id"]]
        with self.assertRaises(AgentError) as error: self.commit(preview)
        self.assertEqual(error.exception.code, "authorization_changed")
        self.service.revise_proposal(self.client, preview["proposal_id"], {"expected_version": preview["version"], "content": {"body": "重新预览内容"}})
        latest = self.service.preview_proposal(self.client, preview["proposal_id"])
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            receipts = list(executor.map(lambda _: self.commit(latest), range(8)))
        self.assertTrue(all(value == receipts[0] for value in receipts))
        self.assertEqual(len(self.repo.list_history(item["id"])), 1)


if __name__ == "__main__":
    unittest.main()
