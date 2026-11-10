"""Local-only proposal management boundaries and durable cancellation."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from test_agent_support import AgentFixture
import test_agent_runtime as runtime_tests
from workbench.agent_proposal_management import ProposalManagement, recovery_status
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError, read_json
from workbench.persistence import atomic_write_json


class ProposalManagementTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.runtime = AgentRuntime(self.repo, base=self.base / "credentials")
        self.management = ProposalManagement(self.runtime)

    def test_cross_client_summary_filters_preview_does_not_submit(self):
        first = self.prepare_preview()
        second_client = {**self.client, "client_id": "unregistered-other"}
        second = self.service.prepare_proposal(second_client, self.spec())
        listing = self.management.list({})
        self.assertEqual(len(listing["items"]), 2)
        self.assertNotIn("normalized_content", listing["items"][0])
        self.assertNotIn("token_hash", str(listing))
        self.assertEqual(len(self.management.list({"client_id": self.client["client_id"]})["items"]), 1)
        self.assertEqual(self.management.list({"state": "draft"})["items"][0]["proposal_id"], second["proposal_id"])
        detail = self.management.preview(second["proposal_id"])
        self.assertFalse(detail["authorization_available"])
        self.assertEqual(detail["preview"]["content"], second["normalized_content"])
        self.assertEqual(self.store._load(second["proposal_id"])["state"], "draft")
        self.assertEqual(self.repo.list_records(), [])
        with self.assertRaises(AgentError): self.service.get_proposal(self.client, second["proposal_id"])
        for params in ({"limit": 101}, {"kind": "idea"}, {"state": "unknown"}, {"extra": "x"}):
            with self.assertRaises(AgentError): self.management.list(params)

    def test_pagination_defaults_and_no_full_body_in_summaries(self):
        for _ in range(23): self.service.prepare_proposal(self.client, self.spec())
        first = self.management.list({})
        self.assertEqual(len(first["items"]), 20)
        second = self.management.list({"cursor": first["next_cursor"]})
        self.assertEqual(len(second["items"]), 3)
        self.assertIsNone(second["next_cursor"])
        self.assertTrue({p["proposal_id"] for p in first["items"]}.isdisjoint(p["proposal_id"] for p in second["items"]))
        self.assertNotIn("body", str(first["items"]))

    def test_cancel_stages_replay_input_conflict_version_and_restart(self):
        for stage in ("cancel_prepared", "cancel_applied", "cancel_completed"):
            with self.subTest(stage=stage):
                preview = self.prepare_preview()
                payload = {"workspace_id": self.security.workspace_id, "request_id": stage, "expected_version": 1}
                def fault(checkpoint):
                    if checkpoint == stage: raise OSError("interrupted")
                with patch.object(self.management, "checkpoint", side_effect=fault), self.assertRaises(OSError): self.management.cancel(preview["proposal_id"], payload)
                management = ProposalManagement(self.runtime)
                result = management.cancel(preview["proposal_id"], payload)
                self.assertEqual(result["state"], "cancelled")
                self.assertEqual(management.cancel(preview["proposal_id"], payload), result)
                with self.assertRaises(AgentError): management.cancel(preview["proposal_id"], {**payload, "expected_version": 2})
        preview = self.prepare_preview()
        with self.assertRaises(AgentError): self.management.cancel(preview["proposal_id"], {"workspace_id": self.security.workspace_id, "request_id": "old", "expected_version": 2})
        self.commit(preview)
        with self.assertRaises(AgentError): self.management.cancel(preview["proposal_id"], {"workspace_id": self.security.workspace_id, "request_id": "committed", "expected_version": 1})

    def test_cleaned_receipts_have_no_partial_approvable_preview(self):
        preview = self.prepare_preview()
        self.commit(preview)
        proposal = self.store._load(preview["proposal_id"])
        proposal["finished_at"] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        self.store._save(proposal)
        self.store.cleanup()
        result = self.management.preview(preview["proposal_id"])
        self.assertTrue(result["content_cleaned"])
        self.assertIsNone(result["preview"])
        self.assertIn("receipt", result)

    def test_recovery_status_and_original_approval_after_accepting_disk(self):
        self.runtime.status(session=True)
        proposal = self.service.prepare_proposal(self.client, {**self.spec(), 'confirmation_mode':'local_web'})
        key = proposal['proposal_id']
        operation = f'{key}-1'
        preview = self.management.preview(key)
        payload = {field:preview[field] for field in ('workspace_id', 'version', 'preview_digest', 'preview_ticket')}
        payload['request_id'] = 'interrupted-approval'
        expired = self.service.prepare_proposal(self.client, self.spec())
        self.store._save({**expired, 'expires_at':'2000-01-01T00:00:00+00:00'})

        def fault(stage):
            if stage == 'applying':
                raise OSError('synthetic failure')

        with patch.object(self.store, 'checkpoint', side_effect=fault), self.assertRaises(AgentError):
            self.management.approve(key, payload)
        def evidence():
            return {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in self.base.rglob('*') if path.is_file()}

        before = evidence()
        expected = {'operation_id':operation, 'proposal_id':key, 'state':'needs_review'}
        with patch.object(self.store, 'recover', side_effect=AssertionError('report attempted recovery')):
            report = recovery_status(self.runtime)
        self.assertEqual(report, {'workspace_id':self.security.workspace_id, 'operations':[expected], 'evidence_error':False})
        self.assertEqual(evidence(), before)
        self.assertEqual(self.store._load(expired['proposal_id'], expire=False)['state'], 'draft')
        self.assertEqual(self.management.action(payload['request_id'])['state'], 'recovery_required')

        manifest_path = self.store.operations / operation / 'manifest.json'
        manifest = read_json(manifest_path)
        hidden_manifest = manifest_path.with_suffix('.hidden')
        manifest_path.rename(hidden_manifest)
        before = evidence()
        self.assertTrue(recovery_status(self.runtime)['evidence_error'])
        self.assertEqual(evidence(), before)
        hidden_manifest.rename(manifest_path)
        atomic_write_json(manifest_path, {**manifest, 'schema_version':999, 'relative_path':'private-evidence-marker'})
        before = evidence()
        report = recovery_status(self.runtime)
        self.assertEqual(report, {'workspace_id':self.security.workspace_id, 'operations':[], 'evidence_error':True})
        self.assertEqual(evidence(), before)
        atomic_write_json(manifest_path, manifest)

        self.store.abandon(operation)
        before = evidence()
        self.assertEqual(recovery_status(self.runtime)['operations'], [{**expected, 'state':'abandoned'}])
        original = self.management.action(payload['request_id'])
        self.assertEqual(original['state'], 'abandoned')
        self.assertEqual(original['outcome'], 'accepted_disk_not_undone')
        self.assertIsNone(original['receipt'])
        self.assertEqual(self.management.approve(key, payload), original)
        self.assertEqual(self.repo.list_records(), [])
        self.assertEqual(evidence(), before)


class ProposalManagementHTTPTests(unittest.TestCase):
    setUp = runtime_tests.AgentManagementHTTPTests.setUp
    tearDown = runtime_tests.AgentManagementHTTPTests.tearDown
    request = runtime_tests.AgentManagementHTTPTests.request

    def test_uninitialized_read_only_and_local_boundary(self):
        status = self.request("status")[1]
        headers = {"X-Workbench-Management-Token": status["management_token"]}
        self.assertEqual(self.request("proposals", headers=headers)[1]["items"], [])
        self.assertEqual(self.request('proposal-recovery', headers=headers),
                         (200, {'workspace_id':None, 'operations':[], 'evidence_error':False}))
        self.assertFalse((self.repo.root / ".agent").exists())
        self.assertFalse((self.base / "private").exists())
        for bad in ({}, {**headers, "Authorization": "Bearer secret"}, {**headers, "Origin": "http://evil.test"}, {**headers, "Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.request("proposals", headers=bad)[0], 403)
            self.assertEqual(self.request('proposal-recovery', headers=bad)[0], 403)
        self.assertEqual(self.request('proposal-recovery', 'POST', {}, {**headers, 'Origin':self.origin})[0], 404)
        self.assertEqual(self.request("proposals?limit=1&limit=2", headers=headers)[0], 400)
        self.assertEqual(self.request("proposals?extra=x", headers=headers)[0], 400)
        self.assertEqual(self.request("clients?limit=1", headers=headers)[0], 400)

    def test_detail_preview_cancel_and_disabled_approval_http(self):
        self.repo.agent_runtime.set_enabled(True)
        service = self.repo.agent_service
        project = self.repo.create_project({"name": "项目"})
        info = service.security.add_client("temporary", ["read", "propose", "commit"], ["*"], [], self.origin)
        client = service.security.clients()[info["client_id"]]
        proposal = service.prepare_proposal(client, {"request_id": "http", "kind": "issue", "operation": "create", "content": {"title": "private-body", "body": "Secret preview", "project_id": project["id"]}})
        status = self.request("status")[1]
        headers = {"X-Workbench-Management-Token": status["management_token"], "Origin": self.origin}
        route = "proposals/" + proposal["proposal_id"]
        for endpoint in (route, route + "/preview", "proposals?kind=issue"):
            self.assertEqual(self.request(endpoint, headers=headers)[0], 200)
            self.assertEqual(self.request(endpoint)[0], 403)
        self.assertEqual(self.request(route + "/preview", headers=headers)[1]["preview"]["content"]["body"], "Secret preview")
        payload = {"workspace_id": status["workspace_id"], "request_id": "cancel-once", "expected_version": 1}
        self.assertEqual(self.request(route + "/approve", "POST", payload, headers)[0], 400)
        self.assertEqual(self.request(route + "/cancel", "POST", payload, {**headers, "Authorization": "Bearer secret"})[0], 403)
        result = self.request(route + "/cancel", "POST", payload, headers)
        self.assertEqual(result[0], 200, result)
        self.assertEqual(self.request(route + "/cancel", "POST", payload, headers), result)
        self.assertEqual(self.repo.list_records(), [])

        self.repo.agent_runtime.set_enabled(False)
        report = self.request('proposal-recovery', headers=headers)
        self.assertEqual(report, (200, {'workspace_id':status['workspace_id'], 'operations':[], 'evidence_error':False}))


if __name__ == "__main__":
    unittest.main()
