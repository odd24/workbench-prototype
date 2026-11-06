"""Independent local approval and persistence boundaries."""
import unittest
from unittest.mock import patch
from test_agent_support import AgentFixture
from workbench.agent_proposal_management import ProposalManagement
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError


class WebApprovalTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.runtime = AgentRuntime(self.repo, base=self.base / "credentials")
        self.repo.agent_runtime = self.runtime
        self.management = ProposalManagement(self.runtime)

    def web_preview(self):
        spec = self.spec(); spec["confirmation_mode"] = "local_web"
        proposal = self.service.prepare_proposal(self.client, spec)
        return self.management.preview(proposal["proposal_id"])

    def approve_payload(self, detail, request_id="approve-one"):
        return {"workspace_id": self.security.workspace_id, "version": detail["version"], "preview_digest": detail["preview"]["preview_digest"], "preview_ticket": detail["preview_ticket"], "request_id": request_id}

    def test_agent_cannot_attest_web_approval_and_web_commits_once(self):
        detail = self.web_preview()
        preview = self.service.preview_proposal(self.client, detail["proposal_id"])
        with self.assertRaises(AgentError) as caught: self.commit(preview)
        self.assertEqual(caught.exception.code, "confirmation_required")
        payload = self.approve_payload(detail)
        result = self.management.approve(detail["proposal_id"], payload)
        self.assertEqual(result["state"], "completed")
        self.assertEqual(self.management.approve(detail["proposal_id"], payload), result)
        self.assertEqual(self.management.action(payload["request_id"]), result)
        self.reload()
        self.assertEqual(len(self.repo.list_records()), 1)
        self.assertEqual(self.repo.get_record(result["receipt"]["item_id"])[0]["body"], preview["content"]["body"])
        self.assertNotIn(detail["preview_ticket"], str(self.store._load(detail["proposal_id"])))

    def test_approval_before_manifest_never_auto_submits(self):
        for stage in ("approval_record", "approval_proposal"):
            detail = self.web_preview(); payload = self.approve_payload(detail, stage)
            def fault(checkpoint):
                if checkpoint == stage: raise OSError("interrupt")
            with patch.object(self.management, "checkpoint", side_effect=fault), self.assertRaises(OSError): self.management.approve(detail["proposal_id"], payload)
            self.assertEqual(self.management.action(stage)["state"], "not_applied")
            self.assertEqual(self.repo.list_records(), [])

    def test_approval_recovery_after_target_and_receipt(self):
        for stage in ("manifest", "committing", "target", "receipt", "proposal"):
            detail = self.web_preview(); payload = self.approve_payload(detail, stage)
            def fault(checkpoint):
                if checkpoint == stage: raise OSError("interrupt")
            with patch.object(self.store, "checkpoint", side_effect=fault), self.assertRaises(AgentError): self.management.approve(detail["proposal_id"], payload)
            result = self.management.action(stage)
            self.assertEqual(result["state"], "completed", result)
            self.assertEqual(self.management.action(stage), result)

    def test_policy_tightening_reversions_and_legacy_digest_upgrade(self):
        from workbench.agent_management import client_version
        old = self.prepare_preview()
        legacy = self.store._load(old["proposal_id"])
        legacy["schema_version"] = 1
        for key in ("confirmation_mode", "digest_algorithm", "approval"):
            legacy.pop(key, None)
        self.store._save(legacy)
        old = self.service.preview_proposal(self.client, old["proposal_id"])
        client = self.security.clients()[self.client["client_id"]]
        params = {key: client[key] for key in ("name", "scopes", "project_ids", "categories")}
        self.security.manager().run("edit", {**params, "minimum_confirmation_mode": "local_web"}, client["client_id"], client_version(client))
        self.client = self.security.clients()[client["client_id"]]
        with self.assertRaises(AgentError): self.commit(old)
        fresh = self.service.get_proposal(self.client, old["proposal_id"])
        self.assertEqual(fresh["confirmation_mode"], "local_web")
        self.assertEqual(fresh["version"], 2)
        self.assertIsNone(fresh["preview_digest"])
        request = self.spec(); request["confirmation_mode"] = "agent_attested"
        proposal = self.service.prepare_proposal(self.client, request)
        self.assertEqual(proposal["confirmation_mode"], "local_web")
        self.security.manager().run("edit", {**params, "minimum_confirmation_mode": "agent_attested"}, client["client_id"])
        self.client = self.security.clients()[client["client_id"]]
        self.assertEqual(self.service.get_proposal(self.client, proposal["proposal_id"])["confirmation_mode"], "local_web")

    def test_expired_tampered_foreign_session_revised_and_permission_tickets(self):
        for change in ("expiry", "ticket", "session", "revision", "permission"):
            detail = self.web_preview(); payload = self.approve_payload(detail, change)
            if change == "expiry": self.runtime.preview_tickets[payload["preview_ticket"]]["expires"] = 0
            elif change == "ticket": payload["preview_ticket"] = "made-up"
            elif change == "session": self.runtime._token = "other-session"
            elif change == "revision": self.service.revise_proposal(self.client, detail["proposal_id"], {"expected_version": 1, "content": {**{key: value for key, value in detail["preview"]["content"].items() if key != "completed"}, "title": "changed"}})
            else:
                from workbench.agent_management import client_version
                client = self.security.clients()[self.client["client_id"]]
                params = {key: client[key] for key in ("name", "scopes", "project_ids", "categories")}
                self.security.manager().run("edit", {**params, "scopes": ["read"]}, client["client_id"], client_version(client))
            with self.subTest(change=change), self.assertRaises(AgentError): self.management.approve(detail["proposal_id"], payload)
        self.assertEqual(self.repo.list_records(), [])

    def test_prepared_recovery_respects_revocation_but_applied_receipt_is_completed(self):
        for stage in ("manifest", "target"):
            with self.subTest(stage=stage):
                if stage == "target": self.tearDown(); self.setUp()
                detail = self.web_preview(); payload = self.approve_payload(detail, stage)
                def fault(checkpoint):
                    if checkpoint == stage: raise OSError("interrupt")
                with patch.object(self.store, "checkpoint", side_effect=fault), self.assertRaises(AgentError): self.management.approve(detail["proposal_id"], payload)
                self.security.change_client(self.client["client_id"])
                result = self.management.action(stage)
                self.assertEqual(result["state"], "recovery_required" if stage == "manifest" else "completed")
                self.assertEqual(len(self.repo.list_records()), 0 if stage == "manifest" else 1)

    def test_target_conflict_and_request_replay_do_not_overwrite(self):
        detail = self.web_preview(); payload = self.approve_payload(detail)
        result = self.management.approve(detail["proposal_id"], payload)
        with self.assertRaises(AgentError): self.management.approve(detail["proposal_id"], {**payload, "version": 2})
        receipt = result["receipt"]
        self.repo.delete_record(receipt["item_id"])
        self.assertEqual(self.management.action(payload["request_id"]), result)
        self.assertEqual(self.repo.list_records(), [])

    def test_parallel_tabs_write_once_and_keep_no_ticket_in_logs(self):
        from concurrent.futures import ThreadPoolExecutor
        detail = self.web_preview(); payload = self.approve_payload(detail)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.management.approve(detail["proposal_id"], payload), range(4)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len(self.repo.list_records()), 1)
        for path in (self.repo.root / ".agent").rglob("*.json"):
            self.assertNotIn(payload["preview_ticket"], path.read_text(encoding="utf-8"))
            self.assertNotIn(self.runtime._token, path.read_text(encoding="utf-8"))

    def test_four_types_three_operations_use_the_same_web_engine(self):
        from workbench.agent_management import client_version
        client = self.security.clients()[self.client["client_id"]]
        params = {key: client[key] for key in ("name", "scopes", "project_ids", "categories")}
        self.security.manager().run("edit", {**params, "kinds": ["issue", "todo", "info", "document"]}, client["client_id"], client_version(client))
        self.client = self.security.clients()[client["client_id"]]
        for kind in ("issue", "todo", "info", "document"):
            receipt = None
            for operation in ("create", "append", "update"):
                with self.subTest(kind=kind, operation=operation):
                    content = {"title": "Web " + kind, "body": "完整正文", **({"category": "允许"} if kind == "document" else {"project_id": self.project["id"]})}
                    if kind == "info": content["info_fields"] = [{"name": "命令", "value": "  echo one\necho two  "}]
                    spec = {"request_id": kind + operation, "kind": kind, "operation": operation, "confirmation_mode": "local_web", "content": content}
                    if receipt:
                        item = self.service.get_item(self.client, kind, receipt["item_id"])
                        spec.update(target_id=item["id"], base_revision=item["revision"], content={"body": "新增正文"})
                    proposal = self.service.prepare_proposal(self.client, spec)
                    detail = self.management.preview(proposal["proposal_id"])
                    result = self.management.approve(proposal["proposal_id"], self.approve_payload(detail, kind + operation))
                    receipt = result["receipt"]
                    self.assertEqual(receipt["approval"]["mode"], "local_web")
                    self.assertEqual(self.service.get_item(self.client, kind, receipt["item_id"])["body"], detail["preview"]["content"]["body"])

    def test_real_process_exit_after_target_recovers_original_approval(self):
        import subprocess, sys, textwrap
        from workbench.agent_security import read_json
        detail = self.web_preview(); payload = self.approve_payload(detail, "process-exit")
        import json
        script = textwrap.dedent(r"""
            import json, os, sys
            from pathlib import Path
            from server import Repository
            from workbench.agent_runtime import AgentRuntime
            from workbench.agent_proposal_management import ProposalManagement
            from workbench.agent_service import AgentService
            repo = Repository(Path(sys.argv[1]))
            runtime = AgentRuntime(repo, base=Path(sys.argv[2]))
            repo.agent_runtime = runtime
            service = AgentService(repo, runtime.security())
            manager = ProposalManagement(runtime)
            detail = manager.preview(sys.argv[3])
            payload = {'workspace_id':detail['workspace_id'], 'version':detail['version'], 'preview_digest':detail['preview']['preview_digest'], 'preview_ticket':detail['preview_ticket'], 'request_id':'process-exit'}
            service.store.checkpoint = lambda stage: os._exit(72) if stage == 'target' else None
            manager.approve(sys.argv[3], payload)
        """)
        result = subprocess.run([sys.executable, "-c", script, str(self.repo.root), str(self.base / "credentials"), detail["proposal_id"]], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 72, result.stderr)
        self.reload()
        runtime = AgentRuntime(self.repo, base=self.base / "credentials")
        self.repo.agent_runtime = runtime
        result = ProposalManagement(runtime).action("process-exit")
        self.assertEqual(result["state"], "completed")
        self.assertEqual(len(self.repo.list_records()), 1)
        self.assertEqual(result["receipt"]["approval"]["mode"], "local_web")

    def test_create_applying_without_target_never_recreates_and_missing_proof_blocks(self):
        from workbench.agent_security import read_json
        from workbench.persistence import atomic_write_json
        for stage in ("snapshots", "applying", "history"):
            if self.store.blocked: self.tearDown(); self.setUp()
            detail = self.web_preview(); payload = self.approve_payload(detail, stage)
            def fault(checkpoint):
                if checkpoint == stage: raise OSError("interrupt")
            with patch.object(self.store, "checkpoint", side_effect=fault), self.assertRaises(AgentError): self.management.approve(detail["proposal_id"], payload)
            result = self.management.action(stage)
            self.assertEqual(result["state"], "not_applied" if stage == "snapshots" else "recovery_required")
            self.assertEqual(self.repo.list_records(), [])
        self.tearDown(); self.setUp()
        detail = self.web_preview(); payload = self.approve_payload(detail, "missing-proof")
        with patch.object(self.store, "checkpoint", side_effect=lambda stage: (_ for _ in ()).throw(OSError()) if stage == "manifest" else None), self.assertRaises(AgentError):
            self.management.approve(detail["proposal_id"], payload)
        path = self.management._action_path(payload["request_id"])
        action = read_json(path); atomic_write_json(path, {**action, "schema_version": 999})
        self.store.recover()
        self.assertTrue(self.store.blocked)
        self.assertEqual(self.repo.list_records(), [])
        with self.assertRaises(AgentError): self.management.action(payload["request_id"])

    def test_expired_proposal_and_target_revision_change_block_approval(self):
        from datetime import datetime, timedelta, timezone
        detail = self.web_preview(); payload = self.approve_payload(detail)
        proposal = self.store._load(detail["proposal_id"])
        proposal["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.store._save(proposal)
        with self.assertRaises(AgentError): self.management.approve(detail["proposal_id"], payload)
        receipt = self.commit(self.prepare_preview())
        item = self.service.get_item(self.client, "issue", receipt["item_id"])
        spec = self.spec(operation="update", target_id=item["id"], base_revision=item["revision"], content={"body": "候选"}); spec["confirmation_mode"] = "local_web"
        proposal = self.service.prepare_proposal(self.client, spec)
        detail = self.management.preview(proposal["proposal_id"])
        self.repo.update_record(item["id"], {"body": "磁盘修改"})
        with self.assertRaises(AgentError): self.management.approve(detail["proposal_id"], self.approve_payload(detail, "revision-changed"))
        self.assertEqual(self.repo.get_record(item["id"])[0]["body"], "磁盘修改")

    def test_real_recovery_cli_uses_explicit_private_context_for_prepared_approval(self):
        import subprocess, sys, json
        detail = self.web_preview(); payload = self.approve_payload(detail, "cli-prepared")
        with patch.object(self.store, "checkpoint", side_effect=lambda stage: (_ for _ in ()).throw(OSError()) if stage == "manifest" else None), self.assertRaises(AgentError):
            self.management.approve(detail["proposal_id"], payload)
        result = subprocess.run([sys.executable, "server.py", "--data-dir", str(self.repo.root), "--agent-config-dir", str(self.base / "credentials"), "--agent-recovery-report"], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["blocked"])
        self.reload()
        self.assertEqual(len(self.repo.list_records()), 1)


if __name__ == "__main__": unittest.main()
