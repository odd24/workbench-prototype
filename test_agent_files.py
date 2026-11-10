"""AG-130 native handles, consent, byte segments and durable authorization."""

import codecs
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from test_agent_support import AgentFixture
from workbench.agent_file_handles import LocalFileHandle, SUPPORTED, lexical_path
from workbench.agent_files import FileManagement, load_ledger, authorized_files, read_segment, io_slot, scan
from workbench.agent_management import CredentialManager, client_version, digest
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError, AgentSecurity, read_json, private_write


@unittest.skipUnless(SUPPORTED, "Native file grants require Windows fixed NTFS")
class FileTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.runtime = AgentRuntime(self.repo, base=self.base / "credentials")
        self.repo.agent_runtime = self.runtime
        self.repo.agent_service = self.service
        self.files = FileManagement(self.runtime)
        self.source = self.base / "source.txt"
        self.source.write_bytes("临时原文😀\nsecond line\n".encode())

    def preview(self, **changes):
        self.client = self.security.clients()[self.client["client_id"]]
        return self.files.preview(self.client["client_id"], {"workspace_id": self.security.workspace_id, "expected_version": client_version(self.client),
                                  "path": str(self.source), "purposes": ["text_read"], "encoding": "auto", "max_bytes": 10485760, "duration_seconds": 3600, **changes})

    def approve(self, preview=None, **changes):
        preview = preview or self.preview()
        payload = {key: preview[key] for key in ("workspace_id", "preview_id", "preview_digest", "expected_version")}
        payload.update(request_id=uuid.uuid4().hex, approved=True, **changes)
        return payload, self.files.approved_record(self.client["client_id"], payload)

    def grant(self, **options):
        payload, record = self.approve(self.preview(**options))
        result = self.files.commit(self.client["client_id"], payload, record)
        self.client = self.security.clients()[self.client["client_id"]]
        return record, result

    def test_metadata_preview_never_reads_or_hashes_source_and_requires_explicit_consent(self):
        with patch.object(LocalFileHandle, "chunks", side_effect=AssertionError("body read before consent")):
            preview = self.preview()
            self.assertNotIn("sha256", preview)
        payload = {key: preview[key] for key in ("workspace_id", "preview_id", "preview_digest", "expected_version")}
        for change in ({"approved": False}, {"approved": True, "path": str(self.source)}, {"approved": True, "preview_digest": "0" * 64}):
            with patch.object(LocalFileHandle, "chunks", side_effect=AssertionError("unauthorized read")), self.assertRaises(AgentError):
                self.files.approved_record(self.client["client_id"], {**payload, "request_id": "no", **change})
        self.assertEqual(load_ledger(self.security)["files"], {})
        self.assertEqual(self.security.registry_version(), 1)

    def test_file_only_client_no_implicit_legacy_kinds_or_dormant_activation(self):
        from workbench.agent_management import AgentManagement
        result = AgentManagement(self.runtime).mutate("create", {"workspace_id": self.security.workspace_id, "request_id": "file-only", "name": "文件专用", "scopes": ["read"], "kinds": [], "project_ids": [], "categories": [], "file_access_only": True})
        client = self.security.clients()[result["client_id"]]
        self.assertEqual(client["kinds"], [])
        self.assertEqual(client["active_file_ids"], [])
        self.assertEqual(self.service.search(client, {})["items"], [])
        self.assertEqual(self.security.registry_version(), 3)
        self.assertEqual(self.service.capabilities(client)["capability_authorization"]["effective"], [])

    def test_grant_persists_intersection_revocation_and_no_path_in_public_or_journal(self):
        record, result = self.grant()
        fresh = AgentSecurity(self.repo.root, self.base / "credentials")
        self.assertEqual(fresh.registry_version(), 3)
        client = fresh.clients()[self.client["client_id"]]
        self.assertEqual(client["authorization_schema_version"], 4)
        self.assertEqual(client["kinds"], ["issue", "document"])
        self.assertEqual(list(authorized_files(fresh, client)), [record["file_id"]])
        metadata = self.service.get_file_info(client, record["file_id"])
        self.assertNotIn("path", metadata)
        body = self.service.read_file(client, record["file_id"], {"source_revision": record["source_revision"]})
        self.assertEqual(body["body"].encode(), self.source.read_bytes())
        for path in fresh.manager().directory.glob("*.json"):
            value = read_json(path)
            if value["schema_version"] == 4:
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(str(self.source).replace("\\", "\\\\"), text)
                self.assertNotIn("token_hash", text)
                self.assertNotIn("before_files", text)
        self.assertFalse(list((fresh.config_dir / "management-snapshots").glob("*.json")))
        private_write(fresh.registry, {**read_json(fresh.registry), "clients": {**fresh.clients(), client["client_id"]: {**client, "active_file_ids": []}}})
        self.assertEqual(authorized_files(fresh, fresh.clients()[client["client_id"]]), {})
        fresh.save_clients({**fresh.clients(), client["client_id"]: client})
        fresh.manager().run("file_grant_revoke", {"file_id": record["file_id"]}, client["client_id"], client_version(client), "revoke-file")
        self.assertEqual(authorized_files(fresh, fresh.clients()[client["client_id"]]), {})
        self.assertEqual(load_ledger(fresh)["files"][record["file_id"]]["status"], "revoked")

    def test_attachment_intent_does_not_enable_text_or_upload(self):
        self.source.write_bytes(b"\x00\xffbinary")
        record, _ = self.grant(purposes=["attachment_source"], encoding="binary")
        self.assertNotIn("read_file", self.service.get_file_info(self.client, record["file_id"])["operations"])
        self.assertNotIn("read_file", self.service.capabilities(self.client)["file_access"]["operations"])
        with self.assertRaises(AgentError):
            self.service.read_file(self.client, record["file_id"], {"source_revision": record["source_revision"]})

    def test_real_handles_reject_hardlinks_devices_ads_secret_names_and_writers(self):
        for value in (r"\\server\share\x", r"\\?\C:\x", r"\\.\PhysicalDrive0", r"C:\x:stream", r"C:\x\..\y", r"C:\x\CON", r"C:\x\a."):
            with self.assertRaises(AgentError):
                lexical_path(value)
        secret = self.base / ".env"
        secret.write_text("synthetic secret", encoding="utf-8")
        for path in (secret, self.security.registry):
            with self.assertRaises(AgentError):
                self.preview(path=str(path))
        link = self.base / "hard.txt"
        os.link(self.source, link)
        with self.assertRaises(AgentError):
            self.preview()
        link.unlink()
        with LocalFileHandle(str(self.source), read=True):
            with self.assertRaises(OSError):
                self.source.write_bytes(b"changed")
        with LocalFileHandle(str(self.source)) as handle:
            self.assertEqual(handle.initial["size"], self.source.stat().st_size)
            with self.assertRaises(AgentError):
                next(handle.chunks(time.monotonic() + 1))

    def test_junction_parent_rejected_without_reading(self):
        target = self.base / "junction-target"
        target.mkdir()
        (target / "x.txt").write_bytes(b"synthetic")
        link = self.base / "junction"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            with patch.object(LocalFileHandle, "chunks", side_effect=AssertionError()), self.assertRaises(AgentError):
                self.preview(path=str(link / "x.txt"))
        finally:
            link.rmdir()  # Remove ONLY the junction itself, never its target tree.

    def test_replaced_modified_expired_foreign_and_tampered_sources_refuse(self):
        preview = self.preview()
        self.source.write_bytes(b"changed before consent")
        with self.assertRaises(AgentError):
            self.approve(preview)
        record, _ = self.grant()
        self.source.write_bytes(b"changed after consent")
        with self.assertRaises(AgentError):
            self.service.read_file(self.client, record["file_id"], {"source_revision": record["source_revision"]})
        altered = {**record, "identity": {**record["identity"], "changed": 0}}
        with self.assertRaises(AgentError):
            read_segment(self.security, altered, {"source_revision": record["source_revision"]})
        for change in ({"expires_at": 1}, {"client_id": str(uuid.uuid4())}, {"status": "revoked"}):
            ledger = load_ledger(self.security)
            ledger["files"][record["file_id"]].update(change)
            private_write(self.security.config_dir / "file-grants.json", ledger)
            self.assertEqual(authorized_files(self.security, self.client), {})
            ledger["files"][record["file_id"]] = record
            private_write(self.security.config_dir / "file-grants.json", ledger)

    def test_encodings_raw_segments_bom_surrogates_four_bytes_and_offsets(self):
        text = "甲乙😀𠀀 abcd\n" * 10
        for encoding, bom in (("utf-8", b""), ("utf-8", codecs.BOM_UTF8), ("utf-16-le", codecs.BOM_UTF16_LE), ("utf-16-be", codecs.BOM_UTF16_BE), ("gb18030", b"")):
            with self.subTest(encoding=encoding, bom=bom):
                self.source.write_bytes(bom + text.encode(encoding))
                record, _ = self.grant(encoding="auto" if bom else encoding)
                offset, pieces = 0, []
                while offset is not None:
                    part = read_segment(self.security, record, {"source_revision": record["source_revision"], "offset": offset, "length": 9})
                    self.assertGreater(part["end_offset"], offset)
                    self.assertLessEqual(part["end_offset"] - offset, 9)
                    pieces.append(part["body"])
                    offset = part["next_offset"]
                self.assertEqual("".join(pieces), text)
                for offset in (len(bom) + 1,):
                    with self.assertRaises(AgentError):
                        read_segment(self.security, record, {"source_revision": record["source_revision"], "offset": offset})
                eof = read_segment(self.security, record, {"source_revision": record["source_revision"], "offset": record["identity"]["size"]})
                self.assertEqual((eof["body"], eof["next_offset"]), ("", None))
        for encoding, data in (("ascii", b"plain\n"), ("cp1252", b"caf\xe9"), ("utf-8", b"")):
            self.source.write_bytes(data)
            record, _ = self.grant(encoding=encoding)
            self.assertEqual(read_segment(self.security, record, {"source_revision": record["source_revision"]})["body"], data.decode(encoding))
        for encoding, data in (("ascii", b"\xff"), ("cp1252", b"\x81"), ("utf-8", b"\xf0\x9f"), ("utf-16-le", b"\x00\xd8"), ("auto", b"\x00binary")):
            self.source.write_bytes(data)
            with self.assertRaises(AgentError):
                self.approve(self.preview(encoding=encoding))

    def test_byte_limit_hash_mismatch_range_and_deadline(self):
        with self.assertRaises(AgentError):
            self.preview(max_bytes=1)
        for changes in ({"max_bytes": 104857601}, {"duration_seconds": 86401}, {"encoding": "unknown"}, {"purposes": ["upload"]}):
            with self.assertRaises(AgentError):
                self.preview(**changes)
        record, _ = self.grant(max_bytes=104857600, duration_seconds=86400)
        for params in ({}, {"source_revision": "0" * 64}, {"source_revision": record["source_revision"], "length": 65537}, {"source_revision": record["source_revision"], "offset": -1}, {"source_revision": record["source_revision"], "length": True}):
            with self.assertRaises(AgentError):
                read_segment(self.security, record, params)
        with self.assertRaises(AgentError):
            read_segment(self.security, {**record, "sha256": "0" * 64}, {"source_revision": record["source_revision"]})
        with LocalFileHandle(str(self.source), read=True) as handle, self.assertRaises(AgentError):
            list(handle.chunks(time.monotonic() - 1))
        with io_slot("quota"), io_slot("quota"), self.assertRaises(AgentError):
            with io_slot("quota"):
                pass

    def test_session_ticket_expiry_and_long_hash_final_approval_recheck(self):
        for change in ("session", "ticket", "management_expiry"):
            preview = self.preview()
            payload, record = self.approve(preview)
            ticket = self.runtime.preview_tickets[preview["preview_id"]]
            if change == "session":
                self.runtime._token = "new-session"
            elif change == "ticket":
                ticket["file_expiry"] = time.monotonic() - 1
            else:
                self.runtime._expires = time.monotonic() - 1
            with self.assertRaises(AgentError):
                self.files.commit(self.client["client_id"], payload, record)
            self.assertEqual(load_ledger(self.security)["files"], {})
            self.runtime.status(session=True)
        preview = self.preview()
        self.runtime._token = "another-session"
        with patch.object(LocalFileHandle, "chunks", side_effect=AssertionError("new session must not hash")), self.assertRaises(AgentError):
            self.approve(preview)

    def test_large_source_requires_explicit_limit_and_uses_bounded_memory(self):
        import tracemalloc
        with self.source.open("wb") as stream:
            for _index in range(176):
                stream.write(b"x" * 65536)
        with self.assertRaises(AgentError):
            self.preview()
        record, _ = self.grant(max_bytes=12 * 1048576)
        tracemalloc.start()
        try:
            result = read_segment(self.security, record, {"source_revision": record["source_revision"], "offset": 65530, "length": 65536})
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(len(result["body"]), 65536)
        self.assertLess(peak, 4 * 1048576)

    def test_simulated_unsupported_branch_refuses_all_three_files_but_keeps_legacy_business(self):
        # Branch coverage only; this is not evidence of a native non-Windows run.
        from workbench.agent_files import public_info
        record, _ = self.grant()
        with patch("workbench.agent_file_handles.SUPPORTED", False), patch("workbench.agent_files.SUPPORTED", False):
            capabilities = self.service.capabilities(self.client)
            authorization = capabilities["capability_authorization"]
            self.assertEqual(authorization["implemented"], ["concept_maps.read", "concept_maps.write", "categories.write"])
            self.assertEqual(authorization["effective"], [])
            self.assertEqual(capabilities["concept_maps"]["grants"], {"schema_version": 1, "grants": []})
            self.assertEqual(capabilities["concept_maps"]["operations"], [])
            for operation in (lambda: self.service.list_file_grants(self.client), lambda: self.service.get_file_info(self.client, record["file_id"]), lambda: self.service.read_file(self.client, record["file_id"], {"source_revision": record["source_revision"]})):
                with self.assertRaises(AgentError) as error:
                    operation()
                self.assertEqual(error.exception.code, "unsupported_platform")
            self.assertTrue(self.service.projects(self.client, {})["items"])

    def test_short_name_case_and_subst_aliases_do_not_bypass_sensitive_roots(self):
        import ctypes
        synthetic = self.security.config_dir / "Synthetic Private Long Name.txt"
        synthetic.write_bytes(b"synthetic private")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        short = ctypes.create_unicode_buffer(32768)
        count = kernel.GetShortPathNameW(str(synthetic), short, len(short))
        self.assertGreater(count, 0)
        for path in (short.value, str(synthetic).swapcase()):
            with self.assertRaises(AgentError):
                self.preview(path=path)
        used = kernel.GetLogicalDrives()
        letter = next(chr(number + 65) for number in range(25, 3, -1) if not used & (1 << number))
        drive = letter + ":"
        process = subprocess.run(["subst", drive, str(self.security.config_dir)], capture_output=True, timeout=5)
        self.assertEqual(process.returncode, 0, process.stderr)
        try:
            with patch.object(LocalFileHandle, "chunks", side_effect=AssertionError()), self.assertRaises(AgentError):
                self.preview(path=drive + "\\" + synthetic.name)
        finally:
            process = subprocess.run(["subst", drive, "/D"], capture_output=True, timeout=5)
            self.assertEqual(process.returncode, 0, process.stderr)
        with io_slot("a"), io_slot("b"), io_slot("c"), io_slot("d"), self.assertRaises(AgentError):
            with io_slot("e"):
                pass

    def test_authorization_cas_before_and_after_hash_and_stable_replay(self):
        preview = self.preview()
        self.security.manager().run("edit", {key: self.client[key] for key in ("name", "scopes", "project_ids", "categories")}, self.client["client_id"], client_version(self.client))
        with patch.object(LocalFileHandle, "chunks", side_effect=AssertionError()), self.assertRaises(AgentError):
            self.approve(preview)
        payload, record = self.approve()
        current = self.security.clients()[self.client["client_id"]]
        self.security.change_client(current["client_id"], expected_version=client_version(current))
        with self.assertRaises(AgentError):
            self.files.commit(current["client_id"], payload, record)
        self.assertEqual(load_ledger(self.security)["files"], {})

    def test_four_format_log_snapshots_cleanup_failure_and_unknown_preflight(self):
        payload, record = self.approve()
        manager = self.security.manager()
        original = Path.unlink
        def fail_snapshot(path, *args, **kwargs):
            if path.parent.name == "management-snapshots":
                raise PermissionError("synthetic")
            return original(path, *args, **kwargs)
        with patch.object(Path, "unlink", fail_snapshot):
            result = manager.run("file_grant_create", {"record": record, "approval_digest": payload["preview_digest"]}, self.client["client_id"], payload["expected_version"], payload["request_id"])
            operation = manager.operation(result["operation_id"])
            self.assertTrue(operation["snapshot_cleanup_pending"])
            self.assertTrue(list((self.security.config_dir / "management-snapshots").glob("*.json")))
        self.assertFalse(manager.operation(result["operation_id"])["snapshot_cleanup_pending"])
        replay = manager.run("file_grant_create", {"record": None, "approval_digest": payload["preview_digest"]}, self.client["client_id"], payload["expected_version"], payload["request_id"])
        self.assertEqual(result, replay)
        self.assertEqual(len(load_ledger(self.security)["files"]), 1)
        log = manager.directory / (result["operation_id"] + ".json")
        value = read_json(log)
        private_write(log, {**value, "schema_version": 999})
        before = {str(path): path.read_bytes() for path in self.security.config_dir.rglob("*.json")}
        with self.assertRaises(AgentError):
            manager.recover()
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.security.config_dir.rglob("*.json")})

    def test_real_exit_each_file_stage_recovers_without_source_read_and_old_binary_refuses(self):
        with tempfile.TemporaryDirectory() as old:
            archive = subprocess.check_output(["git", "archive", "--format=zip", "9b6924d"])
            with zipfile.ZipFile(io.BytesIO(archive)) as package:
                package.extractall(old)
            runner = '''
import json, os, sys
from pathlib import Path
from workbench.agent_security import AgentSecurity
from workbench.agent_management import CredentialManager
s=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2]))
def fault(self,stage):
    if stage==sys.argv[3]: os._exit(73)
CredentialManager.checkpoint=fault
s.manager().run('file_grant_create',json.loads(sys.argv[4]),sys.argv[5],sys.argv[6],sys.argv[7])
'''
            old_runner = '''
from pathlib import Path
import sys
from workbench.agent_security import AgentSecurity
s=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2]))
s.manager().recover()
s.clients()
'''
            for stage in ("prepared", "format_fence", "file_ledger", "registry", "terminal_log", "completed"):
                with self.subTest(stage=stage):
                    self.tearDown(); self.setUp()
                    payload, record = self.approve()
                    params = {"record": record, "approval_digest": payload["preview_digest"]}
                    result = subprocess.run([sys.executable, "-c", runner, str(self.repo.root), str(self.base / "credentials"), stage, json.dumps(params), self.client["client_id"], payload["expected_version"], payload["request_id"]], capture_output=True, timeout=20)
                    self.assertEqual(result.returncode, 73, result.stderr)
                    before = {str(path): path.read_bytes() for path in self.security.config_dir.rglob("*.json")}
                    result = subprocess.run([sys.executable, "-c", old_runner, str(self.repo.root), str(self.base / "credentials")], cwd=old, capture_output=True, timeout=20)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(before, {str(path): path.read_bytes() for path in self.security.config_dir.rglob("*.json")})
                    with patch.object(LocalFileHandle, "chunks", side_effect=AssertionError("recovery reread source")):
                        self.security.manager().recover()
                    self.assertEqual(len(load_ledger(self.security)["files"]), 1)
                    self.assertEqual(self.security.registry_version(), 3)
                    self.assertFalse(list((self.security.config_dir / "management-snapshots").glob("*.json")))

    def test_root_three_credential_operations_real_exit_all_stages_keep_file_authority(self):
        runner = '''
import json, os, sys
from pathlib import Path
from workbench.agent_security import AgentSecurity
from workbench.agent_management import CredentialManager
s=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2]))
def fault(self,stage):
    if stage==sys.argv[3]: os._exit(74)
CredentialManager.checkpoint=fault
s.manager().run(sys.argv[4],json.loads(sys.argv[5]),sys.argv[6] or None,sys.argv[7] or None,sys.argv[8])
'''
        for action in ("create", "edit", "rotate", "revoke"):
            for stage in ("private_snapshot", "prepared", "format_fence", "config", "registry", "terminal_log", "completed"):
                with self.subTest(action=action, stage=stage):
                    self.tearDown(); self.setUp()
                    record, _ = self.grant()
                    client = self.client
                    params = {}
                    if action in {"create", "edit"}:
                        params = {key: client[key] for key in ("name", "scopes", "project_ids", "categories", "kinds")}
                        params["name"] = "更新名称"
                    if action == "create":
                        params["base_url"] = "http://127.0.0.1:4174"
                    request_id = action + stage
                    result = subprocess.run([sys.executable, "-c", runner, str(self.repo.root), str(self.base / "credentials"), stage, action, json.dumps(params), client["client_id"] if action != "create" else "", client_version(client) if action != "create" else "", request_id], capture_output=True, timeout=20)
                    self.assertEqual(result.returncode, 74, result.stderr)
                    with patch.object(LocalFileHandle, "chunks", side_effect=AssertionError("credential recovery must not read source")):
                        self.security.manager().recover()
                    current = self.security.clients()[client["client_id"]]
                    self.assertEqual(current["active_file_ids"], [record["file_id"]])
                    self.assertEqual(current["kinds"], client["kinds"])
                    self.assertEqual(current["enabled"], not (action == "revoke" and stage != "private_snapshot"))
                    config = read_json(self.security.config_dir / (client["client_id"] + ".json"))
                    self.assertEqual(hashlib.sha256(config["token"].encode()).hexdigest(), current["token_hash"])
                    log = read_json(self.security.manager().directory / (hashlib.sha256(request_id.encode()).hexdigest() + ".json"))
                    self.assertEqual(log["state"], "abandoned" if stage == "private_snapshot" else "completed")
                    self.assertNotIn("before_config", log)
                    self.assertNotIn("token_hash", json.dumps(log))
                    self.assertFalse(list((self.security.config_dir / "management-snapshots").glob("*.json")))

    def test_old_three_pending_mixed_with_four_stops_before_any_recovery_write(self):
        manager = self.security.manager()
        params = {key: self.client[key] for key in ("name", "scopes", "project_ids", "categories")}
        params["capability_grants"] = {"schema_version": 1, "grants": []}
        def fault(stage):
            if stage == "prepared":
                raise OSError("stop old prepared")
        with patch.object(manager, "checkpoint", fault), self.assertRaises(OSError):
            manager.run("edit", params, self.client["client_id"], client_version(self.client), "old-three")
        path = manager.directory / (hashlib.sha256(b"old-three").hexdigest() + ".json")
        old = read_json(path)
        manager.recover()
        self.grant()
        private_write(path, old)
        before = {str(path): path.read_bytes() for path in self.security.config_dir.rglob("*.json")}
        with self.assertRaises(AgentError):
            manager.recover()
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.security.config_dir.rglob("*.json")})

    def test_file_first_snapshot_exit_abandons_without_publishing_then_terminal_exit_cleans(self):
        payload, record = self.approve()
        runner = '''
import json, os, sys
from pathlib import Path
from workbench.agent_security import AgentSecurity
from workbench.agent_management import CredentialManager
s=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2]))
def fault(self,stage):
    if stage==sys.argv[3]: os._exit(75)
CredentialManager.checkpoint=fault
if sys.argv[4]=='recover': s.manager().recover()
else: s.manager().run('file_grant_create',json.loads(sys.argv[4]),sys.argv[5],sys.argv[6],sys.argv[7])
'''
        args = [sys.executable, "-c", runner, str(self.repo.root), str(self.base / "credentials")]
        result = subprocess.run(args + ["private_snapshot", json.dumps({"record": record, "approval_digest": payload["preview_digest"]}), self.client["client_id"], payload["expected_version"], payload["request_id"]], capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertEqual(load_ledger(self.security)["files"], {})
        self.assertEqual(self.security.registry_version(), 1)
        result = subprocess.run(args + ["terminal_log", "recover"], capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 75, result.stderr)
        path = self.security.manager().directory / (hashlib.sha256(payload["request_id"].encode()).hexdigest() + ".json")
        self.assertEqual(read_json(path)["state"], "abandoned")
        self.assertTrue(list((self.security.config_dir / "management-snapshots").glob("*.json")))
        with patch.object(LocalFileHandle, "chunks", side_effect=AssertionError("orphan recovery must not read source")):
            self.security.manager().recover()
        self.assertEqual(load_ledger(self.security)["files"], {})
        self.assertFalse(self.security.clients()[self.client["client_id"]].get("active_file_ids"))
        self.assertFalse(list((self.security.config_dir / "management-snapshots").glob("*.json")))


@unittest.skipUnless(SUPPORTED, "Native file grants require Windows fixed NTFS")
class FileHTTPTests(unittest.TestCase):
    def setUp(self):
        from codex_agent_acceptance import LocalWorkbench
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.workbench = LocalWorkbench(self.base / "data", self.base / "credentials")
        self.repo, self.security = self.workbench.repository, self.workbench.security
        self.runtime = AgentRuntime(self.repo, port=self.workbench.server.server_address[1], base=self.base / "credentials")
        self.repo.agent_runtime = self.runtime
        self.info = self.security.manager().run("create", {"name": "HTTP文件", "scopes": ["read"], "kinds": [], "project_ids": [], "categories": [], "base_url": self.workbench.base_url, "file_access_only": True})
        self.client_id = self.info["client_id"]
        self.config = read_json(Path(self.info["config_file"]))
        self.source = self.base / "source.txt"
        self.source.write_text("HTTP与MCP测试临时原文😀\n" * 30, encoding="utf-8")
        self.token = self.runtime.status(session=True)["management_token"]

    def tearDown(self):
        self.workbench.close()
        self.temp.cleanup()

    def request(self, path, payload=None, method="GET", management=False, extra=None):
        headers = {"Content-Type": "application/json", "Origin": self.workbench.base_url}
        if management:
            headers.update({"X-Workbench-Management": "1", "X-Workbench-Management-Token": self.token})
        else:
            headers.update({"Authorization": "Bearer " + self.config["token"], "X-Workbench-Workspace": self.security.workspace_id})
        headers.update(extra or {})
        request = Request(self.workbench.base_url + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers, method=method)
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def manage(self, suffix, payload=None, method="GET", extra=None):
        return self.request("/api/local/agent-management/clients/" + self.client_id + "/files" + suffix, payload, method, True, extra)

    def grant(self):
        version = client_version(self.security.clients()[self.client_id])
        status, preview = self.manage("/preview", {"workspace_id": self.security.workspace_id, "expected_version": version, "path": str(self.source), "purposes": ["text_read"], "encoding": "auto", "max_bytes": 10485760, "duration_seconds": 3600}, "POST")
        self.assertEqual(status, 200, preview)
        payload = {key: preview[key] for key in ("workspace_id", "expected_version", "preview_id", "preview_digest")}
        payload.update(request_id=uuid.uuid4().hex, approved=True)
        status, result = self.manage("/confirm", payload, "POST")
        self.assertEqual(status, 200, result)
        return result, payload

    def read(self, key, revision):
        return self.request(f"/api/agent/v1/files/{key}/content?source_revision={revision}")

    def revoke(self, key):
        return self.manage("/" + key, {"workspace_id": self.security.workspace_id, "expected_version": client_version(self.security.clients()[self.client_id]), "request_id": uuid.uuid4().hex}, "DELETE")

    def test_real_http_preview_approval_replay_fixed_routes_secrets_and_disabled(self):
        result, payload = self.grant()
        key = result["file_id"]
        replay = self.manage("/confirm", payload, "POST")
        self.assertEqual(replay, (200, result))
        status, listing = self.request("/api/agent/v1/files")
        self.assertEqual(status, 200)
        self.assertEqual(len(listing["items"]), 1)
        metadata = listing["items"][0]
        self.assertNotIn("path", json.dumps(listing))
        self.assertEqual(self.request(f"/api/agent/v1/files/{key}")[1], metadata)
        status, read = self.read(key, metadata["source_revision"])
        self.assertEqual(status, 200, read)
        self.assertEqual(read["body"].encode(), self.source.read_bytes())
        for path in ("/api/agent/v1/files?path=x", f"/api/agent/v1/files/{key}/content?source_revision={metadata['source_revision']}&length=9&length=9", "/api/agent/v1/files/not-uuid", f"/api/agent/v1/files/{key}/content"):
            status, value = self.request(path)
            self.assertGreaterEqual(status, 400)
            self.assertNotIn(str(self.source), json.dumps(value))
            self.assertNotIn("body", value)
        self.assertEqual(self.manage("", extra={"Authorization": "Bearer " + self.config["token"]})[0], 403)
        self.assertEqual(self.manage("", extra={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.revoke(key)[0], 200)
        self.assertEqual(self.read(key, metadata["source_revision"])[0], 404)
        self.runtime.set_enabled(False)
        self.assertEqual(self.request("/api/agent/v1/files")[0], 404)

    def test_real_stdio_three_file_tools_and_schema_refusal(self):
        from codex_agent_acceptance import RpcProcess
        from test_mcp_stdio import INITIALIZE
        result, _ = self.grant()
        rpc = RpcProcess([sys.executable, "agent_bridge.py", "--config", self.info["config_file"]], Path(__file__).resolve().parent, {**os.environ, "PYTHONIOENCODING": "utf-8"})
        try:
            rpc.call("initialize", INITIALIZE)
            rpc.notify("notifications/initialized")
            tools = rpc.call("tools/list")["tools"]
            self.assertEqual(len(tools), 22)
            files = rpc.call("tools/call", {"name": "workbench_list_file_grants", "arguments": {}})["structuredContent"]
            item = files["items"][0]
            metadata = rpc.call("tools/call", {"name": "workbench_get_file_info", "arguments": {"file_id": result["file_id"]}})["structuredContent"]
            self.assertEqual(item, metadata)
            content = rpc.call("tools/call", {"name": "workbench_read_file", "arguments": {"file_id": result["file_id"], "source_revision": item["source_revision"], "length": 9}})
            self.assertFalse(content["isError"])
            self.assertNotIn("path", content["structuredContent"])
            with self.assertRaises(RuntimeError):
                rpc.call("tools/call", {"name": "workbench_read_file", "arguments": {"path": str(self.source)}})
            self.revoke(result["file_id"])
            failed = rpc.call("tools/call", {"name": "workbench_get_file_info", "arguments": {"file_id": result["file_id"]}})
            self.assertTrue(failed["isError"])
            self.assertEqual(failed["structuredContent"]["code"], "not_found")
        finally:
            rpc.close()

    def test_long_hash_does_not_hold_locks_and_revocation_prevents_publication(self):
        result, _ = self.grant()
        key = result["file_id"]
        revision = load_ledger(self.security)["files"][key]["source_revision"]
        entered, release = threading.Event(), threading.Event()
        original = LocalFileHandle.chunks
        def slow(handle, deadline):
            entered.set()
            if not release.wait(5):
                raise AssertionError("revoke blocked behind read")
            yield from original(handle, deadline)
        output = []
        with patch.object(LocalFileHandle, "chunks", slow):
            worker = threading.Thread(target=lambda: output.append(self.read(key, revision)))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.revoke(key)[0], 200)
            finally:
                release.set(); worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertGreaterEqual(output[0][0], 400)
        self.assertNotIn("body", output[0][1])

    def test_workspace_switch_and_disable_during_hash_refuse_old_result(self):
        from server import Repository
        result, _ = self.grant()
        key = result["file_id"]
        revision = load_ledger(self.security)["files"][key]["source_revision"]
        original = LocalFileHandle.chunks
        for change in ("switch", "disable"):
            entered, release = threading.Event(), threading.Event()
            def slow(handle, deadline):
                entered.set(); release.wait(5)
                yield from original(handle, deadline)
            output = []
            with patch.object(LocalFileHandle, "chunks", slow):
                worker = threading.Thread(target=lambda: output.append(self.read(key, revision)))
                worker.start()
                try:
                    self.assertTrue(entered.wait(3))
                    handler = self.workbench.server.RequestHandlerClass
                    with handler.repository_switch_lock:
                        if change == "switch":
                            handler.repository = Repository(self.base / "other")
                        else:
                            self.runtime.set_enabled(False)
                finally:
                    release.set(); worker.join(10)
            self.assertEqual(output[0][0], 409)
            self.assertNotIn("body", output[0][1])
            handler.repository = self.repo

    def test_socket_publication_has_no_locks_and_prepermitted_response_can_arrive_late(self):
        result, _ = self.grant()
        key = result["file_id"]
        revision = load_ledger(self.security)["files"][key]["source_revision"]
        handler = self.workbench.server.RequestHandlerClass
        original = handler._json
        entered, release = threading.Event(), threading.Event()
        def delayed(instance, value, *args, **kwargs):
            if "body" in value:
                entered.set(); release.wait(5)
            return original(instance, value, *args, **kwargs)
        output = []
        with patch.object(handler, "_json", delayed):
            worker = threading.Thread(target=lambda: output.append(self.read(key, revision)))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.revoke(key)[0], 200)
            finally:
                release.set(); worker.join(10)
        self.assertEqual(output[0][0], 200)
        self.assertIn("body", output[0][1])

    def test_post_file_approval_hash_releases_outer_write_locks_for_revoke_disable_and_switch(self):
        from server import Repository
        original = LocalFileHandle.chunks
        for change in ("revoke", "disable", "switch"):
            with self.subTest(change=change):
                if change != "revoke":
                    self.tearDown(); self.setUp()
                version = client_version(self.security.clients()[self.client_id])
                status, preview = self.manage("/preview", {"workspace_id": self.security.workspace_id, "expected_version": version, "path": str(self.source), "purposes": ["text_read"], "encoding": "auto", "max_bytes": 10485760, "duration_seconds": 3600}, "POST")
                self.assertEqual(status, 200, preview)
                payload = {key: preview[key] for key in ("workspace_id", "expected_version", "preview_id", "preview_digest")}
                payload.update(approved=True, request_id=uuid.uuid4().hex)
                entered, release = threading.Event(), threading.Event()
                def slow(handle, deadline):
                    entered.set()
                    release.wait(5)
                    yield from original(handle, deadline)
                output = []
                handler = self.workbench.server.RequestHandlerClass
                with patch.object(LocalFileHandle, "chunks", slow):
                    worker = threading.Thread(target=lambda: output.append(self.manage("/confirm", payload, "POST")))
                    worker.start()
                    try:
                        self.assertTrue(entered.wait(3))
                        started = time.monotonic()
                        if change == "revoke":
                            status, value = self.request(f"/api/local/agent-management/clients/{self.client_id}/revoke", {"workspace_id": self.security.workspace_id, "expected_version": version, "request_id": uuid.uuid4().hex}, "POST", True)
                            self.assertEqual(status, 200, value)
                        elif change == "disable":
                            status, value = self.request("/api/local/agent-management/runtime", {"workspace_id": self.security.workspace_id, "expected_version": self.runtime.status()["version"], "request_id": uuid.uuid4().hex, "enabled": False}, "PATCH", True)
                            self.assertEqual(status, 200, value)
                        else:
                            with handler.repository_switch_lock:
                                handler.repository = Repository(self.base / "changed-workspace")
                        self.assertLess(time.monotonic() - started, 2, "management mutation waited for file hash")
                    finally:
                        release.set(); worker.join(10)
                handler.repository = self.repo
                self.assertFalse(worker.is_alive())
                self.assertGreaterEqual(output[0][0], 400)
                self.assertEqual(load_ledger(self.security)["files"], {})


if __name__ == "__main__":
    unittest.main()
