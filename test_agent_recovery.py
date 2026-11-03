import subprocess
import os
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from test_agent_support import AgentFixture
from workbench.agent_security import AgentError, read_json
from workbench.persistence import atomic_write_json
from workbench import agent_proposals


class AgentRecoveryTests(AgentFixture, unittest.TestCase):
    def interrupt(self, preview, stage):
        def fail(checkpoint):
            if checkpoint == stage:
                raise OSError("模拟落盘中断")
        with patch.object(self.store, "checkpoint", side_effect=fail), self.assertRaises(AgentError) as error:
            self.commit(preview)
        self.assertEqual(error.exception.status, 503)

    def test_create_recovery_at_every_durable_boundary(self):
        for stage in ("snapshots", "manifest", "committing", "applying", "history", "target", "receipt", "proposal"):
            with self.subTest(stage=stage):
                if self.store.blocked:
                    # Isolate intentionally unresolved operations from subsequent cases.
                    self.tearDown()
                    self.setUp()
                preview = self.prepare_preview()
                self.interrupt(preview, stage)
                self.reload()
                status = self.service.get_proposal(self.client, preview["proposal_id"])
                if stage == "snapshots":
                    self.assertEqual(status["state"], "previewed")
                    receipt = self.commit(preview)
                elif stage in {"applying", "history"}:
                    self.assertEqual(status["state"], "recovery_required")
                    self.assertTrue(self.store.blocked)
                    with self.assertRaises(AgentError):
                        self.repo.create_document({"title": "不能绕过恢复"})
                    continue
                else:
                    self.assertEqual(status["state"], "committed")
                    receipt = status["receipt"]
                self.assertEqual(self.commit(preview), receipt)
                self.assertEqual(len([item for item in self.repo.list_records() if item["id"] == receipt["item_id"]]), 1)

    def test_update_recovery_reuses_one_history_snapshot(self):
        for kind in ("issue", "document"):
            for stage in ("manifest", "applying", "history", "target", "receipt", "proposal"):
                with self.subTest(kind=kind, stage=stage):
                    receipt = self.commit(self.prepare_preview(self.spec(kind)))
                    item = self.service.get_item(self.client, kind, receipt["item_id"])
                    preview = self.prepare_preview(self.spec(kind, "update", target_id=item["id"], base_revision=item["revision"], content={"body": "更新后的正文"}))
                    self.interrupt(preview, stage)
                    self.reload()
                    status = self.service.get_proposal(self.client, preview["proposal_id"])
                    self.assertEqual(status["state"], "committed")
                    self.assertEqual(self.service.get_item(self.client, kind, item["id"])["body"], "更新后的正文")
                    history = self.repo.list_document_history(item["id"]) if kind == "document" else self.repo.list_history(item["id"])
                    self.assertEqual(len(history), 1)

    def test_third_party_edit_is_never_overwritten(self):
        preview = self.prepare_preview()
        self.interrupt(preview, "manifest")
        manifest_path = next(self.store.operations.glob("*/manifest.json"))
        manifest = read_json(manifest_path)
        target = self.repo.root / manifest["relative_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("第三方独立内容", encoding="utf-8")
        self.reload()
        self.assertTrue(self.store.blocked)
        self.assertEqual(target.read_text(encoding="utf-8"), "第三方独立内容")
        status = self.service.get_proposal(self.client, preview["proposal_id"])
        self.assertEqual(status["state"], "recovery_required")

    def test_receipt_prevents_recreation_after_target_deleted(self):
        preview = self.prepare_preview()
        self.interrupt(preview, "receipt")
        manifest = read_json(next(self.store.operations.glob("*/manifest.json")))
        target = self.repo.root / manifest["relative_path"]
        target.unlink()
        self.reload()
        self.assertFalse(self.store.blocked)
        self.assertEqual(self.service.get_proposal(self.client, preview["proposal_id"])["state"], "committed")
        self.assertFalse(target.exists())

    def test_corrupt_snapshots_unknown_schema_and_escaping_manifest_block_writes(self):
        for change in ("snapshot", "schema", "path"):
            with self.subTest(change=change):
                if self.store.blocked:
                    self.tearDown()
                    self.setUp()
                preview = self.prepare_preview()
                self.interrupt(preview, "manifest")
                manifest_path = next(self.store.operations.glob("*/manifest.json"))
                manifest = read_json(manifest_path)
                if change == "snapshot":
                    (manifest_path.parent / "after.md").write_bytes(b"broken")
                elif change == "schema":
                    atomic_write_json(manifest_path, {**manifest, "schema_version": 999})
                else:
                    atomic_write_json(manifest_path, {**manifest, "relative_path": "../../outside.md"})
                self.reload()
                self.assertTrue(self.store.blocked)
                self.assertFalse((self.base / "outside.md").exists())
                with self.assertRaises(AgentError):
                    self.repo.create_record({"type": "issue", "title": "不能写入", "project_id": self.project["id"]})

    def test_accepting_disk_cancels_ambiguous_create_without_writing_target(self):
        preview = self.prepare_preview()
        self.interrupt(preview, "applying")
        self.reload()
        report = self.store.recovery_report()
        self.assertTrue(report["blocked"])
        self.assertEqual(len(report["details"]), 1)
        operation_id = report["operations"][0]
        report_process = subprocess.run([sys.executable, "server.py", "--data-dir", str(self.repo.root), "--agent-recovery-report"], capture_output=True, timeout=10, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(report_process.returncode, 0, report_process.stderr)
        self.assertTrue(json.loads(report_process.stdout)["blocked"])
        abandon_process = subprocess.run([sys.executable, "server.py", "--data-dir", str(self.repo.root), "--agent-recovery-abandon", operation_id], capture_output=True, timeout=10, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(abandon_process.returncode, 0, abandon_process.stderr)
        self.reload()
        self.assertFalse(self.store.blocked)
        self.assertEqual(self.service.get_proposal(self.client, preview["proposal_id"])["state"], "cancelled")
        self.assertEqual(self.repo.list_records(), [])
        self.repo.create_document({"title": "恢复后可正常保存"})

    def test_snapshot_write_failure_preserves_input_and_original(self):
        receipt = self.commit(self.prepare_preview(self.spec("document")))
        item = self.service.get_item(self.client, "document", receipt["item_id"])
        preview = self.prepare_preview(self.spec("document", "update", target_id=item["id"], base_revision=item["revision"], content={"body": "需要保留的输入"}))
        original = agent_proposals.atomic_write_bytes
        def fail_before(path, content):
            if Path(path).name == "before.md":
                raise OSError("磁盘空间不足")
            return original(path, content)
        with patch("workbench.agent_proposals.atomic_write_bytes", side_effect=fail_before), self.assertRaises(AgentError):
            self.commit(preview)
        self.reload()
        self.assertEqual(self.service.get_item(self.client, "document", item["id"])["body"], item["body"])
        self.assertEqual(self.service.get_proposal(self.client, preview["proposal_id"])["normalized_content"]["body"], "需要保留的输入")
        self.commit(preview)
        self.assertEqual(self.service.get_item(self.client, "document", item["id"])["body"], "需要保留的输入")

    def test_actual_process_exit_after_target_recovers_without_duplicate(self):
        preview = self.prepare_preview()
        payload_path = self.base / "confirmed.json"
        atomic_write_json(payload_path, {"proposal_id": preview["proposal_id"], "payload": self.confirmation(preview), "client_id": self.client["client_id"]})
        script = '''
import os, sys
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity, read_json
from workbench.agent_service import AgentService
repo = Repository(Path(sys.argv[1]))
security = AgentSecurity(repo.root, Path(sys.argv[2]))
service = AgentService(repo, security)
confirmed = read_json(Path(sys.argv[3]))
def crash(stage):
    if stage == 'target':
        os._exit(77)
service.store.checkpoint = crash
service.commit_proposal(security.clients()[confirmed['client_id']], confirmed['proposal_id'], confirmed['payload'])
'''
        result = subprocess.run([sys.executable, "-c", script, str(self.repo.root), str(self.base / "credentials"), str(payload_path)], capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 77, result.stderr)
        self.reload()
        self.assertEqual(self.service.get_proposal(self.client, preview["proposal_id"])["state"], "committed")
        self.assertEqual(len(self.repo.list_records()), 1)


if __name__ == "__main__":
    unittest.main()
