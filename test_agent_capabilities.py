"""AG-128 dormant authorization, durable format fences and legacy isolation."""

import copy
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from test_agent_support import AgentFixture
from workbench.agent_management import CredentialManager, client_version, clean_client
from workbench.agent_security import AgentError, AgentSecurity, allows, normalize_capability_grants, read_json


def grants(capability="projects.create", resources=None, operations=None):
    return {"schema_version": 1, "grants": [{"capability": capability,
        "operations": operations or ["create"], "resources": resources or [{"type": "workspace"}],
        "minimum_confirmation_mode": "local_web"}]}


class CapabilityTests(AgentFixture, unittest.TestCase):
    def create(self, request_id=None, **changes):
        params = {"name": "休眠能力", "scopes": ["read", "propose", "commit"], "kinds": [],
                  "project_ids": [], "categories": [], "base_url": "http://127.0.0.1:4174", "capability_grants": grants(), **changes}
        return self.security.manager().run("create", params, request_id=request_id)

    def edit(self, client, **changes):
        params = {key: client[key] for key in ("name", "scopes", "kinds", "project_ids", "categories")}
        return self.security.manager().run("edit", {**params, **changes}, client["client_id"], client_version(client))

    def test_dormant_independent_client_persists_without_business_access(self):
        result = self.create("independent")
        fresh = AgentSecurity(self.repo.root, self.base / "credentials")
        client = fresh.clients()[result["client_id"]]
        config = read_json(Path(result["config_file"]))
        self.assertEqual(fresh.authenticate("Bearer " + config["token"], fresh.workspace_id), client)
        self.assertEqual(client["management_revision"], 1)
        self.assertEqual(client["authorization_schema_version"], 3)
        self.assertEqual(read_json(fresh.registry)["schema_version"], 2)
        self.assertEqual(config["schema_version"], 2)
        self.assertNotIn("capability_grants", config)
        self.assertLess(Path(result["config_file"]).stat().st_size, 16384)
        capabilities = self.service.capabilities(client)
        self.assertEqual(capabilities["kinds"], [])
        from workbench.agent_file_handles import SUPPORTED
        self.assertEqual(capabilities["capability_authorization"], {"configured": grants(), "implemented": (["files.read", "uploads.stage", "attachments.write"] if SUPPORTED else []) + ["concept_maps.read", "concept_maps.write"] + (["items.delete", "projects.create", "projects.delete"] if SUPPORTED else []) + ["categories.write"], "effective": [], "activation": "requires_reauthorization"})
        self.assertFalse(capabilities['project_deletion']['effective'])
        self.assertNotIn('project', capabilities['kind_operations'])
        self.assertEqual(self.service.projects(client, {})["items"], [])
        self.assertEqual(self.service.search(client, {})["items"], [])
        self.assertEqual(self.service.catalog(client, {}), {"tags": [], "document_categories": []})
        issue = self.repo.create_record({"type": "issue", "project_id": self.project["id"], "title": "秘密", "body": "秘密"})
        self.assertFalse(allows(client, issue))
        for action in (lambda: self.service.get_item(client, "issue", issue["id"]), lambda: self.service.catalog(client, {"project_id": self.project["id"]})):
            with self.assertRaises(AgentError) as error:
                action()
            self.assertEqual(error.exception.code, "not_found")
        for capability in ("project", "concept_map", "attachment"):
            with self.assertRaises(AgentError):
                self.service.prepare_proposal(client, {**self.spec(), "kind": capability})
        self.assertEqual(self.create("independent"), result)
        self.assertNotIn(config["token"], json.dumps(clean_client(client)))

    def test_strict_schema_and_invalid_input_never_write(self):
        base = grants()
        invalid = [None, [], {"schema_version": True, "grants": []}, {"schema_version": 99, "grants": []}, {**base, "extra": 1}]
        for change in ({"capability": "files.read"}, {"capability": "*"}, {"operations": ["shell"]}, {"operations": [True]},
                       {"operations": ["create", "create"]}, {"resources": []}, {"resources": [{"type": "workspace", "path": "secret"}]},
                       {"resources": [{"type": "project", "id": "*"}]}, {"minimum_confirmation_mode": "agent_attested"}, {"activated": True}):
            invalid.append({"schema_version": 1, "grants": [{**base["grants"][0], **change}]})
        invalid += [{"schema_version": 1, "grants": base["grants"] * 65}, {"schema_version": 1, "grants": base["grants"] * 2}]
        before = self.security.registry.read_bytes()
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_capability_grants(value)
            with self.subTest(create=value), self.assertRaises((ValueError, AgentError)):
                self.create(capability_grants=value)
            self.assertEqual(self.security.registry.read_bytes(), before)
        for identifier in ("../secret", "C:\\secret", "*", "", " foo", "foo\nbar"):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                normalize_capability_grants(grants("concept_maps.read", [{"type": "concept_map", "id": identifier}], ["read"]))

    def test_edit_clear_rotate_and_stale_cas_never_expand(self):
        result = self.create()
        client = self.security.clients()[result["client_id"]]
        self.edit(client, name="改名")
        updated = self.security.clients()[client["client_id"]]
        self.assertEqual(updated["capability_grants"], client["capability_grants"])
        with self.assertRaises(AgentError) as error:
            self.edit(client, name="旧版本")
        self.assertEqual(error.exception.code, "configuration_conflict")
        rotated = self.security.change_client(client["client_id"], rotate=True, expected_version=client_version(updated))
        updated = self.security.clients()[client["client_id"]]
        self.assertEqual(updated["capability_grants"], grants())
        self.assertEqual(updated["kinds"], [])
        self.edit(updated, capability_grants={"schema_version": 1, "grants": []})
        updated = self.security.clients()[client["client_id"]]
        self.assertEqual(updated["capability_grants"]["grants"], [])
        self.assertEqual(read_json(self.security.registry)["schema_version"], 2)
        self.assertEqual(updated["management_revision"], 4)
        self.assertNotEqual(rotated["version"], client_version(updated))
        self.security.change_client(client["client_id"], expected_version=client_version(updated))
        self.assertFalse(self.security.clients()[client["client_id"]]["enabled"])

    def test_legacy_read_does_not_rewrite_and_catalog_contract_is_scoped(self):
        before = self.security.registry.read_bytes()
        self.service.capabilities(self.client)
        clean_client(self.client)
        self.assertEqual(self.security.registry.read_bytes(), before)
        self.assertEqual(read_json(self.security.registry)["schema_version"], 1)
        self.repo.create_record({"type": "issue", "project_id": self.project["id"], "title": "可见", "tags": ["可见标签"]})
        hidden = self.repo.create_project({"name": "秘密项目"})
        self.repo.create_record({"type": "issue", "project_id": hidden["id"], "title": "隐藏", "tags": ["隐藏标签"]})
        # Global configured tags, independent of their usage, are legacy behavior.
        legacy = copy.deepcopy(self.client)
        legacy["project_ids"] = [self.project["id"]]
        old_names = {item["name"] for item in self.service.catalog(legacy, {})["tags"]}
        self.assertIn("隐藏标签", old_names)
        result = self.create(kinds=["issue"], project_ids=[self.project["id"]])
        client = self.security.clients()[result["client_id"]]
        self.assertEqual({item["name"] for item in self.service.catalog(client, {})["tags"]}, {"可见标签"})
        empty = self.repo.create_project({"name": "空但有权"})
        self.edit(client, project_ids=[empty["id"]])
        client = self.security.clients()[client["client_id"]]
        catalog = self.service.catalog(client, {"project_id": empty["id"]})
        self.assertEqual(catalog["tags"], [])
        self.assertIn("statuses", catalog)

    def test_category_names_cannot_reactivate_dormant_grants(self):
        self.repo.agent_service = self.service
        self.repo.ensure_document_category("旧名称")
        result = self.create(capability_grants=grants("attachments.write", [{"type": "document_category", "name": "旧名称"}]))
        self.repo.rename_document_category("旧名称", "新名称")
        self.repo.ensure_document_category("旧名称")
        client = self.security.clients()[result["client_id"]]
        self.assertEqual(client["capability_grants"]["grants"], [])
        self.assertEqual(client["categories"], [])
        self.assertEqual(self.service.capabilities(client)["capability_authorization"]["effective"], [])

    def test_each_stage_recovers_original_identity_and_scrubs_snapshots(self):
        for stage in ("prepared", "format_fence", "config", "registry", "completed"):
            self.tearDown()
            self.setUp()  # Every stage is a FIRST upgrade of an independent root-1 space.
            self.assertEqual(read_json(self.security.registry)["schema_version"], 1)
            request_id = "fault-" + stage
            def fail(_self, current):
                if current == stage:
                    raise OSError("injected")
            with self.subTest(stage=stage), patch.object(CredentialManager, "checkpoint", fail), self.assertRaises(OSError):
                self.create(request_id)
            fresh = AgentSecurity(self.repo.root, self.base / "credentials")
            fresh.manager().recover()
            result = self.create(request_id)
            client = fresh.clients()[result["client_id"]]
            self.assertEqual(client["capability_grants"], grants())
            self.assertEqual(client["management_revision"], 1)
            log = read_json(fresh.manager().directory / (hashlib.sha256(request_id.encode()).hexdigest() + ".json"))
            self.assertEqual(log["schema_version"], 3)
            self.assertEqual(log["state"], "completed")
            self.assertNotIn("before_config", log)
            self.assertNotIn("after_client", log)

    def test_external_configuration_requires_report_abandon_without_downgrading(self):
        with patch.object(CredentialManager, "checkpoint", side_effect=OSError("stop")), self.assertRaises(OSError):
            self.create("abandon")
        path = self.security.manager().directory / (hashlib.sha256(b"abandon").hexdigest() + ".json")
        log = read_json(path)
        config = self.security.config_dir / (log["client_id"] + ".json")
        config.write_text('{"third_party":true}', encoding="utf-8")
        report = self.security.manager().report()
        self.assertEqual(report[0]["state"], "recovery_required")
        self.security.manager().abandon(path.stem)
        self.assertEqual(config.read_text(encoding="utf-8"), '{"third_party":true}')
        self.assertEqual(read_json(self.security.registry)["schema_version"], 2)
        self.assertEqual(read_json(path)["schema_version"], 3)
        self.assertNotIn("after_config", read_json(path))

    def test_unknown_and_mixed_logs_preflight_before_any_recovery_write(self):
        with patch.object(CredentialManager, "checkpoint", side_effect=OSError("stop")), self.assertRaises(OSError):
            self.security.add_client("旧未决", ["read"], ["*"], [], "http://127.0.0.1:4174", request_id="old-pending")
        directory = self.security.manager().directory
        old_path = directory / (hashlib.sha256(b"old-pending").hexdigest() + ".json")
        original = read_json(old_path)
        new_id = "unknown-new"
        new_path = directory / (hashlib.sha256(new_id.encode()).hexdigest() + ".json")
        for schema in (99, 3):
            value = {**original, "schema_version": schema, "request_id": new_id, "operation_id": new_path.stem, "registry_schema": 2}
            new_path.write_text(json.dumps(value), encoding="utf-8")
            before = {path: path.read_bytes() for path in self.security.config_dir.rglob("*.json")}
            with self.subTest(schema=schema), self.assertRaises(AgentError):
                self.security.manager().recover()
            self.assertEqual(before, {path: path.read_bytes() for path in self.security.config_dir.rglob("*.json")})
        new_path.unlink()  # Test-injected log only, never a recovery procedure.
        config = self.security.config_dir / (original["client_id"] + ".json")
        config.write_text('{"third_party":true}', encoding="utf-8")
        with self.assertRaises(AgentError):
            self.create()
        self.assertEqual(read_json(self.security.registry)["schema_version"], 1)
        self.assertEqual(len(list(directory.glob("*.json"))), 2)  # baseline create + old pending

    def test_real_concurrent_cli_creates_preserve_clients_and_transport_limit(self):
        command = [sys.executable, "server.py", "--data-dir", str(self.repo.root), "--agent-config-dir", str(self.base / "credentials"),
                   "--agent-client-add", "并发休眠", "--agent-no-legacy-kinds", "--agent-grants-json", json.dumps(grants())]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        results = []
        for process in processes:
            output, error = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, error)
            results.append(json.loads(output))
        self.assertEqual(len(self.security.clients()), 3)
        self.assertNotEqual(results[0]["client_id"], results[1]["client_id"])
        for result in results:
            client = self.security.clients()[result["client_id"]]
            self.assertEqual(client["kinds"], [])
            self.assertEqual(client["capability_grants"], grants())
            self.assertNotIn("capability_grants", read_json(Path(result["config_file"])))
        # A populated grant set cannot enlarge the bridge configuration.
        many = grants()
        many["grants"] = [grants("concept_maps.read", [{"type": "concept_map", "id": "CMAP-" + str(index)}], ["read"])["grants"][0] for index in range(64)]
        result = self.create(capability_grants=many)
        self.assertLess(Path(result["config_file"]).stat().st_size, 16384)

    def test_mutated_persisted_activation_is_rejected(self):
        result = self.create()
        clients = self.security.clients()
        clients[result["client_id"]]["capability_grant_state"] = "active"
        self.security.save_clients(clients)
        config = read_json(Path(result["config_file"]))
        with self.assertRaises(AgentError) as error:
            self.security.authenticate("Bearer " + config["token"], self.security.workspace_id)
        self.assertEqual(error.exception.code, "invalid_configuration")

    def test_corrupt_new_authorization_snapshot_never_applies(self):
        with patch.object(CredentialManager, "checkpoint", side_effect=OSError("stop")), self.assertRaises(OSError):
            self.create("corrupt-snapshot")
        path = self.security.manager().directory / (hashlib.sha256(b"corrupt-snapshot").hexdigest() + ".json")
        value = read_json(path)
        value["after_client"]["capability_grant_state"] = "active"
        path.write_text(json.dumps(value), encoding="utf-8")
        before = {item: item.read_bytes() for item in self.security.config_dir.rglob("*.json")}
        with self.assertRaises(AgentError) as error:
            self.security.manager().recover()
        self.assertEqual(error.exception.code, "management_recovery_required")
        self.assertEqual(before, {item: item.read_bytes() for item in self.security.config_dir.rglob("*.json")})


class LegacyFenceTests(AgentFixture, unittest.TestCase):
    # Only explicit methods below: inherit fixture helpers, not duplicate tests.
    @classmethod
    def setUpClass(cls):
        cls.archive_temp = tempfile.TemporaryDirectory()
        cls.legacy_root = Path(cls.archive_temp.name)
        try:
            source = subprocess.check_output(["git", "archive", "--format=zip", "ba24e37"], stderr=subprocess.PIPE)
        except (OSError, subprocess.CalledProcessError):
            cls.archive_temp.cleanup()
            raise unittest.SkipTest("AG-128 legacy fence requires baseline ba24e37 Git object")
        with zipfile.ZipFile(io.BytesIO(source)) as archive:
            archive.extractall(cls.legacy_root)

    @classmethod
    def tearDownClass(cls):
        cls.archive_temp.cleanup()

    def legacy(self, body, *args):
        return subprocess.run([sys.executable, "-c", body, str(self.repo.root), str(self.base / "credentials"), *args], cwd=self.legacy_root, capture_output=True, timeout=20)

    def fingerprints(self):
        return {str(path.relative_to(self.security.config_dir)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.security.config_dir.rglob("*.json")}

    def test_matching_preupgrade_backup_restores_to_separate_directory(self):
        # No server is running. Preserve the upgraded evidence, restore elsewhere.
        backup = self.base / "matching-backup"
        shutil.copytree(self.repo.root, backup / "data")
        shutil.copytree(self.base / "credentials", backup / "credentials")
        token = read_json(self.security.config_dir / (self.client["client_id"] + ".json"))["token"]
        self.security.add_client("new", ["read"], [], [], "http://127.0.0.1:4174", kinds=[], capability_grants=grants())
        upgraded = self.fingerprints()
        restored = self.base / "restored"
        shutil.copytree(backup, restored)
        probe = '''
from pathlib import Path
import sys
from server import Repository
from workbench.agent_security import AgentSecurity
s = AgentSecurity(Path(sys.argv[1]), Path(sys.argv[2]))
client = s.authenticate('Bearer '+sys.argv[3], s.workspace_id)
assert client['kinds'] == ['issue','document']
assert Repository(Path(sys.argv[1])).list_projects()
'''
        result = subprocess.run([sys.executable, "-c", probe, str(restored / "data"), str(restored / "credentials"), token],
                                cwd=self.legacy_root, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(upgraded, self.fingerprints())
        self.assertEqual(read_json(restored / "credentials" / self.security.workspace_id / "clients.json")["schema_version"], 1)

    def test_real_exit_every_stage_old_entrypoints_refuse_and_new_recovers(self):
        runner = '''
import json, os, sys
from pathlib import Path
from workbench.agent_security import AgentSecurity
from workbench.agent_management import CredentialManager
security = AgentSecurity(Path(sys.argv[1]), Path(sys.argv[2]))
def checkpoint(self, stage):
    if stage == sys.argv[3]: os._exit(73)
CredentialManager.checkpoint = checkpoint
security.add_client('crash', ['read'], [], [], 'http://127.0.0.1:4174', request_id=sys.argv[4], kinds=[], capability_grants=json.loads(sys.argv[5]))
'''
        old_auth = "from pathlib import Path; import sys; from workbench.agent_security import AgentSecurity; s=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2])); s.authenticate('Bearer '+sys.argv[3],s.workspace_id)"
        old_recover = "from pathlib import Path; import sys; from workbench.agent_security import AgentSecurity; AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2])).manager().recover()"
        old_start = "from pathlib import Path; import sys; from server import Repository; from workbench.agent_runtime import AgentRuntime; AgentRuntime(Repository(Path(sys.argv[1])),base=Path(sys.argv[2])).set_enabled(True)"
        token = read_json(self.security.config_dir / (self.client["client_id"] + ".json"))["token"]
        for stage in ("prepared", "format_fence", "config", "registry", "completed"):
            with self.subTest(stage=stage):
                self.tearDown()
                self.setUp()  # Do not reuse root 2 from the previous fault point.
                self.assertEqual(read_json(self.security.registry)["schema_version"], 1)
                token = read_json(self.security.config_dir / (self.client["client_id"] + ".json"))["token"]
                request_id = "exit-" + stage
                args = [sys.executable, "-c", runner, str(self.repo.root), str(self.base / "credentials"), stage, request_id, json.dumps(grants())]
                process = subprocess.run(args, capture_output=True, timeout=20)
                self.assertEqual(process.returncode, 73, process.stderr)
                log_id = hashlib.sha256(request_id.encode()).hexdigest()
                probes = [(old_auth, (token,)), (old_recover, ()), (old_start, ()),
                          ("from pathlib import Path; import sys; from workbench.agent_security import AgentSecurity; AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2])).manager().abandon(sys.argv[3])", (log_id,))]
                if stage != "prepared":
                    probes.append(("from pathlib import Path; import sys; from workbench.agent_security import AgentSecurity; AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2])).clients()", ()))
                for body, extra in probes:
                    before = self.fingerprints()
                    old = self.legacy(body, *extra)
                    self.assertNotEqual(old.returncode, 0, old.stdout)
                    self.assertIn(b"AgentError", old.stderr)
                    self.assertEqual(before, self.fingerprints())
                cli = subprocess.run([sys.executable, "server.py", "--data-dir", str(self.repo.root), "--agent-config-dir", str(self.base / "credentials"), "--agent-client-add", "old"], cwd=self.legacy_root, capture_output=True, timeout=20)
                self.assertNotEqual(cli.returncode, 0)
                self.assertIn(b"AgentError", cli.stderr)
                self.assertEqual(before, self.fingerprints())
                fresh = AgentSecurity(self.repo.root, self.base / "credentials")
                fresh.manager().recover()
                log = read_json(fresh.manager().directory / (log_id + ".json"))
                self.assertEqual(log["state"], "completed")
                self.assertEqual(fresh.clients()[log["client_id"]]["capability_grants"], grants())


if __name__ == "__main__":
    unittest.main()
