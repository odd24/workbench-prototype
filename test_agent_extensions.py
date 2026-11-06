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


if __name__ == "__main__":
    unittest.main()
