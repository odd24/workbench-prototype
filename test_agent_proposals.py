import io
import zipfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from test_agent_support import AgentFixture
from workbench.agent_security import AgentError


class AgentProposalTests(AgentFixture, unittest.TestCase):
    def test_prepare_preview_and_commit_roundtrip_for_both_types(self):
        for kind in ("issue", "document"):
            spec = self.spec(kind)
            before_ids = {item["id"] for item in self.service.search(self.client, {})["items"]}
            preview = self.prepare_preview(spec)
            self.assertEqual({item["id"] for item in self.service.search(self.client, {})["items"]}, before_ids)
            self.assertEqual(preview["content"]["body"], spec["content"]["body"])
            self.assertIn("warnings", preview)
            receipt = self.commit(preview)
            self.reload()
            item = self.service.get_item(self.client, kind, receipt["item_id"])
            self.assertEqual(item["body"], preview["content"]["body"])
            self.assertEqual(item["revision"], receipt["revision"])
            self.assertEqual(self.commit(preview), receipt)
            self.assertEqual(self.service.prepare_proposal(self.client, spec)["receipt"], receipt)

    def test_preview_is_required_and_missing_confirmation_never_writes(self):
        proposal = self.service.prepare_proposal(self.client, self.spec())
        with self.assertRaises(AgentError):
            self.service.commit_proposal(self.client, proposal["proposal_id"], {"version": 1, "preview_digest": "invented"})
        preview = self.service.preview_proposal(self.client, proposal["proposal_id"])
        for confirmation in (None, {"mode": "agent_attested", "user_confirmed": False}, {"mode": "other", "user_confirmed": True}):
            with self.assertRaises(AgentError):
                self.service.commit_proposal(self.client, proposal["proposal_id"], {**self.confirmation(preview), "confirmation": confirmation})
        self.assertEqual(self.repo.list_records(), [])
        self.assertEqual(self.repo.list_documents(), [])

    def test_revise_requires_new_preview_and_rejects_old_version(self):
        preview = self.prepare_preview()
        content = {key: value for key, value in preview["content"].items() if key != "completed"}
        revised = self.service.revise_proposal(self.client, preview["proposal_id"], {"expected_version": 1, "content": {**content, "body": "用户修订"}})
        self.assertEqual(revised["version"], 2)
        with self.assertRaises(AgentError):
            self.commit(preview)
        fresh = self.service.preview_proposal(self.client, preview["proposal_id"])
        receipt = self.commit(fresh)
        self.assertEqual(self.service.get_item(self.client, "issue", receipt["item_id"])["body"], "用户修订")

    def test_append_update_and_external_conflict_keep_original(self):
        receipt = self.commit(self.prepare_preview())
        target = self.service.get_item(self.client, "issue", receipt["item_id"])
        spec = self.spec(operation="append", target_id=target["id"], base_revision=target["revision"], content={"body": "追加进展"})
        preview = self.prepare_preview(spec)
        self.assertEqual(preview["content"]["body"], target["body"] + "\n\n追加进展")
        self.assertIn("+追加进展", preview["body_diff"])
        self.commit(preview)
        self.reload()
        latest = self.service.get_item(self.client, "issue", target["id"])
        update = self.prepare_preview(self.spec(operation="update", target_id=target["id"], base_revision=latest["revision"], content={"body": "拟覆盖"}))
        self.repo.update_record(target["id"], {"body": "其他编辑器保存"})
        with self.assertRaises(AgentError) as error:
            self.commit(update)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.service.get_item(self.client, "issue", target["id"])["body"], "其他编辑器保存")
        self.assertEqual(self.service.get_proposal(self.client, update["proposal_id"])["state"], "conflicted")

    def test_cancel_expiry_and_unknown_or_foreign_proposals(self):
        preview = self.prepare_preview()
        other = {**self.client, "client_id": "different-client"}
        with self.assertRaises(AgentError) as error:
            self.service.get_proposal(other, preview["proposal_id"])
        self.assertEqual(error.exception.status, 404)
        self.service.cancel_proposal(self.client, preview["proposal_id"], {"expected_version": 1})
        with self.assertRaises(AgentError):
            self.commit(preview)
        expired = self.prepare_preview()
        proposal = self.store._load(expired["proposal_id"])
        proposal["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.store._save(proposal)
        with self.assertRaises(AgentError) as error:
            self.commit(expired)
        self.assertEqual(error.exception.status, 410)
        with self.assertRaises(AgentError):
            self.service.get_proposal(self.client, "../../other")

    def test_duplicate_prepare_and_concurrent_commit_create_exactly_one_item(self):
        spec = self.spec()
        with ThreadPoolExecutor(max_workers=5) as pool:
            proposals = list(pool.map(lambda _: self.service.prepare_proposal(self.client, spec), range(5)))
        self.assertEqual(len({item["proposal_id"] for item in proposals}), 1)
        with self.assertRaises(AgentError) as error:
            self.service.prepare_proposal(self.client, {**spec, "source_note": "不同内容"})
        self.assertEqual(error.exception.status, 409)
        preview = self.service.preview_proposal(self.client, proposals[0]["proposal_id"])
        with ThreadPoolExecutor(max_workers=5) as pool:
            receipts = list(pool.map(lambda _: self.commit(preview), range(5)))
        self.assertTrue(all(item == receipts[0] for item in receipts))
        self.reload()
        self.assertEqual(len(self.repo.list_records()), 1)

    def test_deleted_committed_item_is_not_recreated_and_id_is_not_reused(self):
        preview = self.prepare_preview()
        receipt = self.commit(preview)
        trashed = self.repo.delete_record(receipt["item_id"])
        self.repo.purge_trash(trashed["token"])
        self.reload()
        self.assertEqual(self.commit(preview), receipt)
        status = self.service.get_proposal(self.client, preview["proposal_id"])
        self.assertFalse(status["current_item"]["exists"])
        self.assertEqual(self.repo.list_records(), [])
        next_receipt = self.commit(self.prepare_preview())
        self.assertNotEqual(next_receipt["item_id"], receipt["item_id"])

    def test_validation_rejects_extra_fields_limits_scope_and_invalid_references(self):
        cases = [({"title": ""}, 400), ({"title": "字" * 201}, 400), ({"body": "字" * 100000}, 413),
                 ({"status": "虚构状态"}, 400), ({"priority": "重要"}, 400), ({"tags": ["虚构标签"]}, 400),
                 ({"file_path": "../outside.md"}, 400), ({"body": "[[ISSUE-9999]]"}, 400), ({"body": 123}, 400)]
        for changes, expected in cases:
            spec = self.spec()
            with self.subTest(changes=list(changes)), self.assertRaises(AgentError) as error:
                self.service.prepare_proposal(self.client, {**spec, "content": {**spec["content"], **changes}})
            self.assertEqual(error.exception.status, expected)
        spec = self.spec("document", content={"title": "文档", "body": "文本", "category": "新建分类"})
        with self.assertRaises(AgentError):
            self.service.prepare_proposal(self.client, spec)
        self.assertNotIn("新建分类", self.repo.document_categories())
        denied = {**self.client, "scopes": ["read"]}
        with self.assertRaises(AgentError) as error:
            self.service.prepare_proposal(denied, self.spec())
        self.assertEqual(error.exception.status, 403)

    def test_configuration_changes_require_a_new_preview(self):
        preview = self.prepare_preview(self.spec("document"))
        self.repo.save_document_categories(["未分类"])
        with self.assertRaises(AgentError) as error:
            self.commit(preview)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.repo.list_documents(), [])
        preview = self.prepare_preview()
        workflows = self.repo.config()["workflow_templates"]
        workflows[0]["statuses"]["issue"][0]["completed"] = True
        self.repo.save_workflow_templates(workflows)
        with self.assertRaises(AgentError) as error:
            self.commit(preview)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.repo.list_records(), [])

    def test_editing_stored_content_after_preview_cannot_bypass_digest(self):
        preview = self.prepare_preview()
        proposal = self.store._load(preview["proposal_id"])
        proposal["normalized_content"]["body"] = "未预览内容"
        self.store._save(proposal)
        with self.assertRaises(AgentError):
            self.commit(preview)
        self.assertEqual(self.repo.list_records(), [])

    def test_cleanup_preserves_receipt_and_prepare_idempotency(self):
        spec = self.spec("document")
        preview = self.prepare_preview(spec)
        receipt = self.commit(preview)
        proposal = self.store._load(preview["proposal_id"])
        proposal["finished_at"] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        self.store._save(proposal)
        self.store.cleanup()
        cleaned = self.store._load(preview["proposal_id"])
        self.assertNotIn("normalized_content", cleaned)
        self.assertEqual(self.commit(preview), receipt)
        self.assertEqual(self.service.prepare_proposal(self.client, spec)["receipt"], receipt)
        with zipfile.ZipFile(io.BytesIO(self.repo.export_zip())) as archive:
            self.assertTrue(all(not name.startswith(".agent/") for name in archive.namelist()))


if __name__ == "__main__":
    unittest.main()
