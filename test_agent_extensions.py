"""Extension contracts, legacy authorization and mixed durable-format tests."""
import unittest
from unittest.mock import patch

from test_agent_support import AgentFixture
from workbench.agent_management import client_version
from workbench.agent_proposals import digest
from workbench.agent_security import AgentError, allows, client_kinds, read_json
from workbench.persistence import atomic_write_json


class AgentExtensionTests(AgentFixture, unittest.TestCase):
    def test_legacy_authorization_and_explicit_type_intersection(self):
        legacy = {key: value for key, value in self.client.items() if key not in {"kinds", "authorization_schema_version"}}
        self.assertEqual(client_kinds(legacy), ["issue", "document"])
        for kind in ("todo", "info", "idea"):
            self.assertFalse(allows(legacy, {"type": kind, "project_id": self.project["id"]}))
        document_only = {**legacy, "kinds": ["document"]}
        self.assertEqual(self.service.projects(document_only, {})["items"], [])
        self.assertEqual(self.service.capabilities(document_only)["kinds"], ["document"])
        with self.assertRaises(AgentError):
            self.service.prepare_proposal(document_only, self.spec())
        hidden = self.repo.create_record({"type": "todo", "project_id": self.project["id"], "title": "hidden"})
        request = self.spec()
        request["content"]["body"] = "[[" + hidden["id"] + "]]"
        with self.assertRaises(AgentError) as caught:
            self.service.prepare_proposal(legacy, request)
        self.assertEqual(caught.exception.code, "invalid_reference")

    def test_edit_rotate_and_category_sync_preserve_explicit_types(self):
        manager = self.security.manager()
        params = {key: self.client[key] for key in ("name", "scopes", "project_ids", "categories")}
        params["kinds"] = ["issue", "todo"]
        manager.run("edit", params, self.client["client_id"], client_version(self.client))
        params.pop("kinds")
        for action, supplied in (("edit", params), ("rotate", {})):
            current = self.security.clients()[self.client["client_id"]]
            manager.run(action, supplied, current["client_id"], client_version(current))
            self.assertEqual(client_kinds(self.security.clients()[current["client_id"]]), ["issue", "todo"])
            config = read_json(self.security.config_dir / (current["client_id"] + ".json"))
            self.assertEqual(config["kinds"], ["issue", "todo"])
        self.repo.agent_service = self.service
        self.repo.rename_document_category("允许", "重命名")
        self.assertEqual(client_kinds(self.security.clients()[self.client["client_id"]]), ["issue", "todo"])

    def test_invalid_type_authorization_is_not_wildcard(self):
        for kinds in ([], ["*"], ["idea"], "todo", [True], None):
            with self.subTest(kinds=kinds), self.assertRaises((ValueError, AgentError)):
                self.security.manager().run("edit", {**{key: self.client[key] for key in ("name", "scopes", "project_ids", "categories")}, "kinds": kinds}, self.client["client_id"])
        self.assertEqual(client_kinds(self.security.clients()[self.client["client_id"]]), ["issue", "document"])

    def test_legacy_preview_digest_is_preserved_in_mixed_store_and_recovery(self):
        old = self.service.prepare_proposal(self.client, self.spec())
        proposal = self.store._load(old["proposal_id"])
        proposal["schema_version"] = 1
        for key in ("digest_algorithm", "confirmation_mode", "approval"):
            proposal.pop(key)
        self.store._save(proposal)
        preview = self.service.preview_proposal(self.client, old["proposal_id"])
        self.assertNotIn("confirmation_mode", preview)
        expected = digest(self.store.preview_payload(proposal))
        self.assertEqual(preview["preview_digest"], expected)
        fresh = self.prepare_preview()
        self.assertEqual(fresh["confirmation_mode"], "agent_attested")
        self.assertEqual(fresh["digest_algorithm"], "sha256-json-v2")
        def interrupt(stage):
            if stage == "target":
                raise OSError("fault after target")
        with patch.object(self.store, "checkpoint", side_effect=interrupt), self.assertRaises(AgentError):
            self.commit(preview)
        self.reload()
        self.assertEqual(self.store._load(old["proposal_id"])["preview_digest"], expected)
        self.assertEqual(self.service.get_proposal(self.client, old["proposal_id"])["state"], "committed")
        self.commit(fresh)
        self.reload()
        self.assertEqual(len(self.repo.list_records()), 2)

    def test_unknown_schema_cleanup_and_abandon_preserve_evidence(self):
        preview = self.prepare_preview()
        with patch.object(self.store, "checkpoint", side_effect=lambda stage: (_ for _ in ()).throw(OSError()) if stage == "manifest" else None), self.assertRaises(AgentError):
            self.commit(preview)
        path = next(self.store.operations.glob("*/manifest.json"))
        manifest = read_json(path)
        atomic_write_json(path, {**manifest, "schema_version": 999})
        before = path.read_bytes()
        self.reload()
        self.assertTrue(self.store.blocked)
        with self.assertRaises(AgentError):
            self.store.abandon(manifest["operation_id"])
        self.assertEqual(path.read_bytes(), before)
        proposal = self.store._load(preview["proposal_id"])
        proposal["schema_version"] = 999
        self.store._save(proposal)
        before = (self.store.proposals / (preview["proposal_id"] + ".json")).read_bytes()
        with self.assertRaises(AgentError):
            self.store.cleanup()
        self.assertEqual((self.store.proposals / (preview["proposal_id"] + ".json")).read_bytes(), before)
class TodoAgentTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.client = {**self.client, "kinds": ["issue", "document", "todo"]}

    def spec(self, kind="todo", operation="create", **overrides):
        result = super().spec("issue" if kind == "todo" else kind, operation, **overrides)
        result["kind"] = kind
        return result

    def test_three_operations_dates_search_read_and_persistence(self):
        spec = self.spec()
        spec["content"]["due"] = "2028-02-29"
        preview = self.prepare_preview(spec)
        self.assertEqual(preview["content"]["due"], "2028-02-29")
        self.assertFalse(preview["content"]["completed"])
        receipt = self.commit(preview)
        for operation in ("append", "update"):
            self.reload()
            item = self.service.get_item(self.client, "todo", receipt["item_id"])
            data = {"body": "补充正文"} if operation == "append" else {"due": None, "priority": "高"}
            preview = self.prepare_preview(self.spec(operation=operation, target_id=item["id"], base_revision=item["revision"], content=data))
            receipt = self.commit(preview)
            self.assertEqual(self.commit(preview), receipt)
        self.reload()
        saved = self.service.get_item(self.client, "todo", receipt["item_id"])
        self.assertIsNone(saved["due"])
        self.assertEqual(saved["priority"], "高")
        self.assertIn("补充正文", saved["body"])
        self.assertEqual(self.service.read_item(self.client, "todo", saved["id"], {"length": 3})["body"], saved["body"][:3])
        self.assertEqual(self.service.search(self.client, {"kind": "todo"})["items"][0]["id"], saved["id"])
        self.assertEqual(len(self.service.catalog(self.client, {"project_id": self.project["id"], "kind": "todo"})["statuses"]), len(self.repo.config()["status_templates"]["todo"]))

    def test_invalid_dates_fields_and_append_metadata_never_write(self):
        for due in ("2026-02-29", "2026-1-01", "", "2026-01-01T00:00:00Z", 12, False):
            spec = self.spec()
            spec["content"]["due"] = due
            with self.subTest(due=due), self.assertRaises(AgentError):
                self.prepare_preview(spec)
        for field in ("completed", "info_fields", "category"):
            spec = self.spec()
            spec["content"][field] = True
            with self.subTest(field=field), self.assertRaises(AgentError):
                self.prepare_preview(spec)
        item = self.repo.create_record({"type": "todo", "project_id": self.project["id"], "title": "原记录"})
        with self.assertRaises(AgentError):
            self.prepare_preview(self.spec(operation="append", target_id=item["id"], base_revision=item["revision"], content={"body": "新增", "title": "不许修改"}))

    def test_legacy_due_metadata_and_converted_id_remain_usable(self):
        item = self.repo.create_record({"type": "issue", "project_id": self.project["id"], "title": "旧格式", "due": "2020-01-02T03:04:05", "links": ["source"], "attachments": [{"name": "旧附件"}]})
        item = self.repo.convert_record(item["id"], "todo")
        preview = self.prepare_preview(self.spec(operation="update", target_id=item["id"], base_revision=item["revision"], content={"body": "仅改正文", "status": "待办"}))
        receipt = self.commit(preview)
        self.assertIsNone(receipt["web_path"])
        self.reload()
        saved = self.repo.get_record(item["id"])[0]
        self.assertEqual(saved["due"], item["due"])
        self.assertEqual(saved["attachments"], item["attachments"])
        self.assertEqual(saved["links"], item["links"])

    def test_conflict_workflow_narrowed_permission_and_external_changes(self):
        receipt = self.commit(self.prepare_preview())
        item = self.service.get_item(self.client, "todo", receipt["item_id"])
        preview = self.prepare_preview(self.spec(operation="update", target_id=item["id"], base_revision=item["revision"], content={"body": "候选"}))
        self.repo.update_record(item["id"], {"body": "外部变更"})
        with self.assertRaises(AgentError): self.commit(preview)
        self.assertEqual(self.repo.get_record(item["id"])[0]["body"], "外部变更")
        preview = self.prepare_preview()
        workflows = self.repo.config()["workflow_templates"]
        workflows[0]["statuses"]["todo"][0]["name"] = "已改名"
        self.repo.save_workflow_templates(workflows)
        with self.assertRaises(AgentError): self.commit(preview)
        with self.assertRaises(AgentError):
            self.service.get_proposal({**self.client, "kinds": ["issue", "document"]}, preview["proposal_id"])

    def test_recovery_all_boundaries_and_deleted_project(self):
        for stage in ("snapshots", "manifest", "committing", "applying", "history", "target", "receipt", "proposal"):
            with self.subTest(stage=stage):
                if self.store.blocked:
                    self.tearDown(); self.setUp()
                preview = self.prepare_preview()
                def interrupt(checkpoint):
                    if checkpoint == stage: raise OSError("fault")
                with patch.object(self.store, "checkpoint", side_effect=interrupt), self.assertRaises(AgentError): self.commit(preview)
                self.reload()
                proposal = self.service.get_proposal(self.client, preview["proposal_id"])
                expected = "previewed" if stage == "snapshots" else "recovery_required" if stage in {"applying", "history"} else "committed"
                self.assertEqual(proposal["state"], expected)
        preview = self.prepare_preview()
        self.repo.delete_project(self.project["id"])
        with self.assertRaises(AgentError): self.commit(preview)

    def test_update_recovery_and_concurrent_replay_preserve_one_history(self):
        from concurrent.futures import ThreadPoolExecutor
        for stage in ("manifest", "applying", "history", "target", "receipt", "proposal"):
            with self.subTest(stage=stage):
                receipt = self.commit(self.prepare_preview())
                item = self.service.get_item(self.client, "todo", receipt["item_id"])
                preview = self.prepare_preview(self.spec(operation="update", target_id=item["id"], base_revision=item["revision"], content={"body": "恢复候选", "due": "2027-01-01"}))
                def interrupt(checkpoint):
                    if checkpoint == stage: raise OSError("fault")
                with patch.object(self.store, "checkpoint", side_effect=interrupt), self.assertRaises(AgentError): self.commit(preview)
                self.reload()
                self.assertFalse(self.store.blocked)
                with ThreadPoolExecutor(max_workers=4) as pool:
                    receipts = list(pool.map(lambda _: self.commit(preview), range(4)))
                self.assertTrue(all(value == receipts[0] for value in receipts))
                self.assertEqual(len(self.repo.list_history(item["id"])), 1)
                self.assertEqual(self.repo.get_record(item["id"])[0]["due"], "2027-01-01")


class InfoAgentTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.client = {**self.client, "kinds": ["issue", "document", "todo", "info"]}

    def spec(self, kind="info", operation="create", **overrides):
        spec = super().spec("issue" if kind == "info" else kind, operation, **overrides)
        spec["kind"] = kind
        return spec

    def fields(self):
        return [{"name": "命令", "value": "  echo 'one'\n  echo \"two\"  ", "note": "  第一行\n第二行  "}, {"name": "空白", "value": "  "}]

    def test_ordered_fields_roundtrip_append_reorder_clear_and_metadata(self):
        spec = self.spec()
        spec["content"]["info_fields"] = self.fields()
        preview = self.prepare_preview(spec)
        self.assertEqual(preview["content"]["info_fields"], self.fields())
        self.assertTrue({"status", "priority", "due", "completed"}.isdisjoint(preview["content"]))
        self.assertNotIn("statuses", self.service.catalog(self.client, {"kind": "info", "project_id": self.project["id"]}))
        receipt = self.commit(preview)
        self.repo.update_record(receipt["item_id"], {"info_color": "#123456", "attachments": [{"name": "附件"}], "links": ["source"]})
        for operation, content in (("append", {"body": "追加正文"}), ("update", {"info_fields": list(reversed(self.fields()))}), ("update", {"info_fields": []})):
            self.reload()
            item = self.service.get_item(self.client, "info", receipt["item_id"])
            if operation == "append": self.assertEqual(item["info_fields"], self.fields())
            preview = self.prepare_preview(self.spec(operation=operation, target_id=item["id"], base_revision=item["revision"], content=content))
            receipt = self.commit(preview)
            saved = self.repo.get_record(item["id"])[0]
            self.assertEqual(saved["info_fields"], preview["content"]["info_fields"])
            self.assertEqual(saved["info_color"], "#123456")
            self.assertEqual(saved["attachments"], [{"name": "附件"}])
            self.assertEqual(saved["links"], ["source"])
        self.reload()
        self.assertEqual(self.repo.get_record(receipt["item_id"])[0]["info_fields"], [])
        self.assertEqual(self.service.search(self.client, {"kind": "info"})["items"][0]["id"], receipt["item_id"])

    def test_invalid_fields_limits_and_no_silent_truncation(self):
        invalid = [None, {}, [{"name": "x"}], [{"name": "x", "value": 1}], [{"name": "x", "value": "v", "unknown": "x"}], [{"name": "x", "value": "nul\x00"}], [{"name": "x" * 201, "value": "v"}], [{"name": "x", "value": "中" * 21846}], [{"name": "x", "value": "v", "note": "a" * 65537}], [{"name": "x", "value": "v"}] * 201]
        for fields in invalid:
            spec = self.spec(); spec["content"]["info_fields"] = fields
            with self.subTest(fields=str(fields)[:80]), self.assertRaises(AgentError): self.prepare_preview(spec)
        spec = self.spec(); spec["content"].update(body="a" * 200000, info_fields=[{"name": "x", "value": "a" * 65536}])
        with self.assertRaises(AgentError): self.prepare_preview(spec)
        spec = self.spec(); spec["content"]["info_fields"] = [{"name": "名" * 200, "value": "v"}] * 200
        receipt = self.commit(self.prepare_preview(spec)); self.reload()
        self.assertEqual(len(self.repo.get_record(receipt["item_id"])[0]["info_fields"]), 200)
        for field in ("status", "priority", "due", "completed", "info_color"):
            spec = self.spec(); spec["content"][field] = "x"
            with self.subTest(field=field), self.assertRaises(AgentError): self.prepare_preview(spec)

    def test_old_dictionary_fields_and_oversized_read_do_not_hide_content(self):
        from workbench.markdown_io import dump_markdown
        item = self.repo.create_record({"type": "info", "title": "旧字段", "project_id": self.project["id"], "info_fields": self.fields()})
        self.assertEqual(item["info_fields"], self.fields())
        _, path = self.repo.get_record(item["id"])
        raw = path.read_text(encoding="utf-8")
        # Legacy Python dictionaries wrapped in JSON strings are still parsed.
        import json
        path.write_text(raw.replace(json.dumps(self.fields()[1], ensure_ascii=False, separators=(",", ":")), json.dumps(str(self.fields()[1]), ensure_ascii=False)), encoding="utf-8")
        self.reload()
        self.assertEqual(self.service.get_item(self.client, "info", item["id"])["info_fields"], self.fields())
        meta = {"id": item["id"], "type": "info", "title": "large", "project_id": self.project["id"], "info_fields": [{"name": str(i), "value": "x"} for i in range(201)]}
        path.write_text(dump_markdown(meta, "body"), encoding="utf-8")
        self.reload()
        current = self.service.get_item(self.client, "info", item["id"])
        self.assertEqual(len(current["info_fields"]), 201)
        with self.assertRaises(AgentError): self.prepare_preview(self.spec(operation="update", target_id=item["id"], base_revision=current["revision"], content={"body": "new"}))
        self.assertEqual(len(self.repo.get_record(item["id"])[0]["info_fields"]), 201)

    def test_recovery_update_and_original_fields_survive_external_conflict(self):
        for stage in ("snapshots", "manifest", "committing", "applying", "history", "target", "receipt", "proposal"):
            with self.subTest(stage=stage):
                spec = self.spec(); spec["content"]["info_fields"] = self.fields()
                receipt = self.commit(self.prepare_preview(spec))
                item = self.service.get_item(self.client, "info", receipt["item_id"])
                preview = self.prepare_preview(self.spec(operation="update", target_id=item["id"], base_revision=item["revision"], content={"info_fields": list(reversed(self.fields()))}))
                def interrupt(checkpoint):
                    if checkpoint == stage: raise OSError("fault")
                with patch.object(self.store, "checkpoint", side_effect=interrupt), self.assertRaises(AgentError): self.commit(preview)
                self.reload()
                if stage == "snapshots": self.commit(preview)
                self.assertEqual(self.repo.get_record(item["id"])[0]["info_fields"], list(reversed(self.fields())))
                self.assertEqual(len(self.repo.list_history(item["id"])), 1)
                self.assertEqual(self.commit(preview)["item_id"], item["id"])
        item = self.service.get_item(self.client, "info", item["id"])
        preview = self.prepare_preview(self.spec(operation="append", target_id=item["id"], base_revision=item["revision"], content={"body": "append"}))
        self.repo.update_record(item["id"], {"body": "external"})
        with self.assertRaises(AgentError): self.commit(preview)
        self.assertEqual(self.repo.get_record(item["id"])[0]["body"], "external")
        with self.assertRaises(AgentError):
            self.prepare_preview(self.spec(operation="append", target_id=item["id"], base_revision=item["revision"], content={"body": "x", "info_fields": self.fields()}))


if __name__ == "__main__":
    unittest.main()
