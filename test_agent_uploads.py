"""Isolated staging policies, real byte evidence and crash recovery."""

import copy
import hashlib
import io
import json
import os
import socket
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

from test_agent_support import AgentFixture
from workbench.agent_security import AgentError, private_write, read_json
from workbench.agent_management import client_version, credential_lock
from workbench.agent_file_handles import SUPPORTED, LocalFileHandle
from workbench.agent_runtime import AgentRuntime
from workbench.agent_files import FileManagement
from workbench.agent_upload_policy import UploadPolicyManagement, load_policies, effective_policy
from workbench.agent_uploads import UploadStore, LIMITS, public_session


@unittest.skipUnless(SUPPORTED, "Native NTFS staging verification requires Windows")
class UploadTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.repo.agent_service = self.service
        self.runtime = AgentRuntime(self.repo, base=self.base / "credentials")
        self.repo.agent_runtime = self.runtime
        self.policies = UploadPolicyManagement(self.runtime)
        self.uploads = self.service.uploads

    def policy(self, stream=True, files=None, **changes):
        self.client = self.security.clients()[self.client["client_id"]]
        preview = self.policies.preview(self.client["client_id"], {"workspace_id": self.security.workspace_id, "expected_version": client_version(self.client), "owner_kind": "project", "owner_id": self.project["id"], "stream": stream, "files": files or [], "max_bytes": 104857600, "duration_seconds": 3600, **changes})
        payload = {key: preview[key] for key in ("workspace_id", "expected_version", "preview_id", "preview_digest")}
        payload.update(request_id=uuid.uuid4().hex, approved=True)
        result = self.policies.approve(self.client["client_id"], payload)
        self.client = self.security.clients()[self.client["client_id"]]
        self.assertEqual(preview["policy"]["client_version"], client_version(self.client))
        return result["policy_id"]

    def spec(self, content=b"private staging data", policy_id=None, **changes):
        return {"request_id": uuid.uuid4().hex, "policy_id": policy_id or self.policy_id, "source": {"mode": "stream"}, "owner_kind": "project", "owner_id": self.project["id"], "filename": "temporary.bin", "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), **changes}

    def permit(self, value, publish=False):
        with self.repo.write_lock, credential_lock(self.security.config_dir):
            current = self.security.clients()[self.client["client_id"]]
            if not current["enabled"]:
                raise AgentError("forbidden", "revoked", 403)
            source = self.uploads.authorize(current, value)
            if publish:
                self.uploads.publish_ready(value)
            return source

    def receive(self, spec=None, data=b"private staging data"):
        session = self.uploads.create(self.client, spec or self.spec(data))
        result = self.uploads.receive(session["upload_id"], (data[i:i + 65536] for i in range(0, len(data), 65536)), self.permit)
        return session["upload_id"], result

    def file_source(self, purposes=None, large_bytes=0):
        source = self.base / "source.bin"
        if large_bytes:
            with source.open("wb") as stream:
                for _index in range(large_bytes // 65536):
                    stream.write(b"x" * 65536)
        else:
            source.write_bytes(b"file source" * 100)
        management = FileManagement(self.runtime)
        preview = management.preview(self.client["client_id"], {"workspace_id": self.security.workspace_id, "expected_version": client_version(self.client), "path": str(source), "purposes": purposes or ["attachment_source"], "encoding": "binary" if not purposes else "utf-8", "max_bytes": 104857600 if large_bytes else 10485760, "duration_seconds": 3600})
        payload = {key: preview[key] for key in ("workspace_id", "expected_version", "preview_id", "preview_digest")}
        payload.update(request_id=uuid.uuid4().hex, approved=True)
        record = management.approved_record(self.client["client_id"], payload)
        management.commit(self.client["client_id"], payload, record)
        self.client = self.security.clients()[self.client["client_id"]]
        return source, record

    def test_explicit_policy_post_revision_persistence_old_authority_and_owner_restrictions(self):
        with self.assertRaises(AgentError):
            self.uploads.create(self.client, self.spec(policy_id=str(uuid.uuid4())))
        params = {name: self.client[name] for name in ("name", "scopes", "project_ids", "categories")}
        dormant = {"schema_version": 1, "grants": [{"capability": "attachments.write", "operations": ["create"], "resources": [{"type": "project", "id": self.project["id"]}], "minimum_confirmation_mode": "local_web"}]}
        self.security.manager().run("edit", {**params, "capability_grants": dormant}, self.client["client_id"], client_version(self.client))
        self.client = self.security.clients()[self.client["client_id"]]
        with self.assertRaises(AgentError):
            self.uploads.create(self.client, self.spec(policy_id=str(uuid.uuid4())))
        self.assertFalse(self.uploads.directory.exists())
        key = self.policy()
        self.assertEqual(self.security.clients()[self.client["client_id"]]["capability_grant_state"], "dormant")
        self.assertEqual(effective_policy(self.security, self.client, key)["client_version"], client_version(self.client))
        self.assertTrue(load_policies(self.security)["policies"][key]["enabled"])
        other = self.repo.create_project({"name": "other"})
        self.policy_id = key
        with self.assertRaises(AgentError):
            self.uploads.create(self.client, self.spec(owner_id=other["id"]))
        params = {name: self.client[name] for name in ("name", "scopes", "project_ids", "categories")}
        self.security.manager().run("edit", {**params, "project_ids": []}, self.client["client_id"], client_version(self.client))
        self.client = self.security.clients()[self.client["client_id"]]
        with self.assertRaises(AgentError):
            self.policy()

    def test_stream_sealing_ready_and_idempotence_are_real_bytes_not_attachment(self):
        self.policy_id = self.policy()
        data = b"stream\x00bytes" * 10000
        spec = self.spec(data)
        key, received = self.receive(spec, data)
        self.assertEqual(received["state"], "receiving")
        self.assertEqual(received["sealed"], {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        self.assertFalse(received["formal_attachment_created"])
        ready = self.uploads.complete(key, self.permit)
        self.assertEqual(ready["state"], "ready")
        self.assertEqual(self.uploads.complete(key, self.permit), ready)
        self.assertEqual(self.uploads.path(key, "blob.bin").read_bytes(), data)
        self.assertEqual(UploadStore(self.repo, self.security).load(key)["state"], "ready")
        self.assertEqual(self.uploads.create(self.client, spec)["upload_id"], key)
        with self.assertRaises(AgentError):
            self.uploads.create(self.client, {**spec, "filename": "different.bin"})
        self.assertFalse(list(self.repo.root.rglob("*.bin")))
        self.assertNotIn("path", json.dumps(ready))

    def test_file_source_requires_both_explicit_policy_and_attachment_purpose(self):
        source, record = self.file_source()
        candidate = self.spec(source.read_bytes(), policy_id=str(uuid.uuid4()), source={"mode": "file", "file_id": record["file_id"], "source_revision": record["source_revision"]}, filename=source.name)
        with self.assertRaises(AgentError):
            self.uploads.create(self.client, candidate)
        self.assertFalse(self.uploads.directory.exists())
        self.policy_id = self.policy(stream=False, files=[{"file_id": record["file_id"], "source_revision": record["source_revision"]}])
        spec = self.spec(source.read_bytes(), source={"mode": "file", "file_id": record["file_id"], "source_revision": record["source_revision"]}, filename=source.name)
        key = self.uploads.create(self.client, spec)["upload_id"]
        result = self.uploads.complete(key, self.permit)
        self.assertEqual(result["state"], "ready")
        self.assertEqual(self.uploads.path(key, "blob.bin").read_bytes(), source.read_bytes())
        source.write_bytes(b"changed")
        key = self.uploads.create(self.client, {**spec, "request_id": uuid.uuid4().hex})["upload_id"]
        with self.assertRaises(AgentError):
            self.uploads.complete(key, self.permit)
        self.assertNotEqual(self.uploads.load(key)["state"], "ready")
        self.client = self.security.clients()[self.client["client_id"]]
        _source, text = self.file_source(["text_read"])
        with self.assertRaises(AgentError):
            self.policy(stream=False, files=[{"file_id": text["file_id"], "source_revision": text["source_revision"]}])

    def test_zero_bytes_ranges_truncation_overflow_wrong_hash_and_cancel(self):
        self.policy_id = self.policy()
        key, _ = self.receive(self.spec(b""), b"")
        self.assertEqual(self.uploads.complete(key, self.permit)["sealed"]["bytes"], 0)
        for spec, data in ((self.spec(b"long"), b"short but over length"), (self.spec(b"long"), b"lo"), (self.spec(b"hash"), b"oops")):
            key = self.uploads.create(self.client, spec)["upload_id"]
            with self.assertRaises(AgentError):
                self.uploads.receive(key, iter([data]), self.permit)
            self.assertEqual(self.uploads.load(key)["state"], "failed")
            with self.assertRaises(AgentError):
                self.uploads.complete(key, self.permit)
        key = self.uploads.create(self.client, self.spec())["upload_id"]
        cancelled = self.uploads.cancel(key, self.client)
        self.assertEqual(self.uploads.cancel(key, self.client), cancelled)
        with self.assertRaises(AgentError):
            self.uploads.receive(key, iter([b"x"]), self.permit)

    def test_changed_authority_owner_policy_and_tampered_ready_refuse_availability(self):
        self.policy_id = self.policy()
        key, _ = self.receive()
        self.uploads.complete(key, self.permit)
        self.policy()
        result = self.uploads.get(key, self.client, self.permit)
        self.assertEqual(result["state"], "ready")
        self.assertFalse(result["available_for_binding"])
        self.assertEqual(result["unavailable_reason"], "forbidden")
        with self.assertRaises(AgentError):
            self.uploads.complete(key, self.permit)
        self.policy_id = self.policy()
        key, _ = self.receive()
        self.uploads.complete(key, self.permit)
        self.uploads.path(key, "blob.bin").write_bytes(b"third party")
        with self.assertRaises(AgentError):
            self.uploads.get(key, self.client, self.permit)
        self.assertEqual(self.uploads.path(key, "blob.bin").read_bytes(), b"third party")

    def test_quota_reservations_cross_process_and_disk_shortage(self):
        self.policy_id = self.policy()
        spec = self.spec(b"", bytes=104857600)
        runner = '''
import json, sys
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity,AgentError
from workbench.agent_uploads import UploadStore
s=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2]))
try:
 result=UploadStore(Repository(Path(sys.argv[1])),s).create(s.clients()[sys.argv[3]],json.loads(sys.argv[4])); print('created')
except AgentError as error: print(error.code); sys.stderr.write(json.dumps({'message':str(error),'details':error.details}))
'''
        processes = []
        for _index in range(6):
            candidate = {**spec, "request_id": uuid.uuid4().hex}
            processes.append(subprocess.Popen([sys.executable, "-c", runner, str(self.repo.root), str(self.base / "credentials"), self.client["client_id"], json.dumps(candidate)], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        output = []
        diagnostics = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, stderr)
            output.append(stdout.strip())
            diagnostics.append((stdout.strip(), stderr))
        self.assertEqual(output.count(b"created"), 5, diagnostics)
        self.assertEqual(output.count(b"upload_quota"), 1, diagnostics)
        self.assertEqual(sum(value["declared_bytes"] for value in self.uploads.catalog()), 500 * 1048576)
        with patch("workbench.agent_uploads.shutil.disk_usage", return_value=type("Disk", (), {"free": 0})()), self.assertRaises(AgentError):
            self.uploads.create(self.client, self.spec(b""))

    def test_workspace_storage_quota_exact_boundary_across_clients(self):
        for index in range(2):
            if index:
                info = self.security.add_client("配额第二客户端", ["read"], [self.project["id"]], [], "http://127.0.0.1:4174")
                self.client = self.security.clients()[info["client_id"]]
            self.policy_id = self.policy()
            for _number in range(5):
                self.uploads.create(self.client, self.spec(b"", bytes=100 * 1048576))
        info = self.security.add_client("配额第三客户端", ["read"], [self.project["id"]], [], "http://127.0.0.1:4174")
        self.client = self.security.clients()[info["client_id"]]
        self.policy_id = self.policy()
        with self.assertRaises(AgentError) as error:
            self.uploads.create(self.client, self.spec(b"", bytes=25 * 1048576))
        self.assertEqual(error.exception.code, "upload_quota")
        self.uploads.create(self.client, self.spec(b"", bytes=24 * 1048576))
        self.assertEqual(sum(value["declared_bytes"] for value in self.uploads.catalog()), 1024 * 1048576)
        with self.assertRaises(AgentError) as error:
            self.uploads.create(self.client, self.spec(b"x"))
        self.assertEqual(error.exception.code, "upload_quota")

    def test_interrupted_known_partial_can_clean_but_unlogged_tail_and_unknown_format_stay(self):
        self.policy_id = self.policy()
        key = self.uploads.create(self.client, self.spec(b"x" * 100000))["upload_id"]
        def interrupted():
            yield b"x" * 65536
            raise OSError("synthetic stream interruption")
        with self.assertRaises(OSError):
            self.uploads.receive(key, interrupted(), self.permit)
        self.assertEqual(self.uploads.load(key)["evidence"]["bytes"], 65536)
        old = int(time.time()) - 100000
        value = self.uploads.load(key)
        value.update(created_at=old, expires_at=old + 86400)
        self.uploads.write(value)
        self.uploads.recover_and_cleanup(self.permit, True)
        self.assertTrue(self.uploads.load(key)["removed"])
        self.assertFalse(self.uploads.path(key, "part.bin").exists())
        key = self.uploads.create(self.client, self.spec(b"x" * 100000))["upload_id"]
        with self.assertRaises(OSError):
            self.uploads.receive(key, interrupted(), self.permit)
        with self.uploads.path(key, "part.bin").open("ab") as stream:
            stream.write(b"unknown tail")
        value = self.uploads.load(key)
        value.update(created_at=old, expires_at=old + 86400)
        self.uploads.write(value)
        with self.assertRaises(AgentError):
            self.uploads.recover_and_cleanup(self.permit, True)
        self.assertFalse(self.uploads.load(key)["removed"])
        self.assertTrue(self.uploads.path(key, "part.bin").read_bytes().endswith(b"unknown tail"))
        metadata = self.uploads.path(key, "session.json")
        private_write(metadata, {**self.uploads.load(key), "schema_version": 999})
        before = {str(path): path.read_bytes() for path in self.uploads.directory.rglob("*") if path.is_file()}
        with self.assertRaises(AgentError):
            self.uploads.recover_and_cleanup(self.permit, True)
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.uploads.directory.rglob("*") if path.is_file()})

    def test_expired_known_cleanup_uses_verified_handle_and_keeps_binding_unknown_or_tamper(self):
        self.policy_id = self.policy()
        key, _ = self.receive()
        self.uploads.complete(key, self.permit)
        value = self.uploads.load(key)
        old = int(time.time()) - 100000
        value.update(created_at=old, expires_at=old + 86400)
        self.uploads.write(value)
        with patch.object(LocalFileHandle, "delete_verified", side_effect=AgentError("upload_cleanup_pending", "simulated", 409)), self.assertRaises(AgentError):
            self.uploads.recover_and_cleanup(self.permit, True)
        self.assertFalse(self.uploads.load(key)["removed"])
        self.assertTrue(self.uploads.path(key, "blob.bin").exists())
        self.uploads.recover_and_cleanup(self.permit, True)
        self.assertTrue(self.uploads.load(key)["removed"])
        self.assertFalse(self.uploads.path(key, "blob.bin").exists())
        key, _ = self.receive()
        self.uploads.complete(key, self.permit)
        value = self.uploads.load(key)
        value.update(created_at=old, expires_at=old + 86400, binding={"schema_version": 1, "proposal_id": str(uuid.uuid4()), "version": 1, "owner_revision": value["owner"]["revision"]})
        # First check binding protection while the authorization/session is live.
        live = {**value, "created_at": int(time.time()), "expires_at": int(time.time()) + 86400}
        self.uploads.write(live)
        self.assertFalse(self.uploads.complete(key, self.permit)["available_for_binding"])
        self.assertFalse(self.uploads.get(key, self.client, self.permit)["available_for_binding"])
        with self.assertRaises(AgentError):
            self.uploads.cancel(key, self.client)
        with self.assertRaises(AgentError):
            self.uploads.consumer_contract(key, "arbitrary consumer")
        self.uploads.write(value)
        self.uploads.recover_and_cleanup(self.permit, True)
        self.assertTrue(self.uploads.path(key, "blob.bin").exists())
        value["binding"] = None
        self.uploads.write(value)
        self.uploads.path(key, "blob.bin").write_bytes(b"external")
        before = self.uploads.path(key, "blob.bin").read_bytes()
        with self.assertRaises(AgentError):
            self.uploads.recover_and_cleanup(self.permit, True)
        self.assertEqual(self.uploads.path(key, "blob.bin").read_bytes(), before)
        self.assertFalse(self.uploads.load(key)["removed"])
        unknown = self.uploads.folder(key) / "unknown.bin"
        unknown.write_bytes(b"preserve")
        snapshot = {str(path): path.read_bytes() for path in self.uploads.directory.rglob("*") if path.is_file()}
        with self.assertRaises(AgentError):
            self.uploads.recover_and_cleanup(self.permit, True)
        self.assertEqual(snapshot, {str(path): path.read_bytes() for path in self.uploads.directory.rglob("*") if path.is_file()})

    def test_removed_tombstones_do_not_exhaust_active_session_limit_or_lose_idempotence(self):
        self.policy_id = self.policy()
        old = int(time.time()) - 100000
        specs, keys = [], []
        with patch.dict(LIMITS, {"sessions": 2}):
            for _index in range(2):
                candidate = self.spec(b"")
                specs.append(candidate)
                key = self.uploads.create(self.client, candidate)["upload_id"]
                keys.append(key)
                value = self.uploads.load(key)
                value.update(created_at=old, expires_at=old + 86400)
                self.uploads.write(value)
            with self.assertRaises(AgentError):
                self.uploads.create(self.client, self.spec(b""))
            self.uploads.recover_and_cleanup(self.permit, True)
            self.assertTrue(all(self.uploads.load(key)["removed"] for key in keys))
            fresh = self.uploads.create(self.client, self.spec(b""))
            self.assertEqual(fresh["state"], "created")
            self.assertNotIn(fresh["upload_id"], keys)
            for candidate, key in zip(specs, keys):
                replay = self.uploads.create(self.client, candidate)
                self.assertEqual(replay["upload_id"], key)
                self.assertTrue(replay["removed"])
                self.assertEqual(replay["state"], "expired")

    def test_concurrent_session_locks_enforce_client_and_workspace_limits(self):
        from contextlib import ExitStack
        self.policy_id = self.policy()
        own = [self.uploads.create(self.client, self.spec(b""))["upload_id"] for _index in range(3)]
        original_client, original_policy = self.client, self.policy_id
        info = self.security.add_client("第二客户端", ["read"], [self.project["id"]], [], "http://127.0.0.1:4174")
        self.client = self.security.clients()[info["client_id"]]
        self.policy_id = self.policy()
        other = [self.uploads.create(self.client, self.spec(b""))["upload_id"] for _index in range(2)]
        self.client, self.policy_id = original_client, original_policy
        with self.uploads.session_lock(own[0]), self.uploads.session_lock(own[1]), self.assertRaises(AgentError):
            with self.uploads.session_lock(own[2]):
                pass
        with ExitStack() as stack:
            for key in own[:2] + other:
                stack.enter_context(self.uploads.session_lock(key))
            with self.assertRaises(AgentError):
                with self.uploads.session_lock(own[2]):
                    pass
        with self.uploads.session_lock(own[2]):
            self.assertEqual(self.uploads.load(own[2])["state"], "created")

    def test_owner_hidden_missing_and_cross_type_share_not_found_without_metadata(self):
        params = {key: self.client[key] for key in ("name", "scopes", "categories")}
        self.security.manager().run("edit", {**params, "project_ids": []}, self.client["client_id"], client_version(self.client))
        self.client = self.security.clients()[self.client["client_id"]]
        errors = []
        for kind, key in (("project", self.project["id"]), ("project", "missing"), ("document", self.project["id"])):
            with self.assertRaises(AgentError) as caught:
                self.policy(owner_kind=kind, owner_id=key)
            errors.append((caught.exception.code, caught.exception.status, str(caught.exception)))
        self.assertEqual(len(set(errors)), 1)
        self.assertEqual(errors[0], ("not_found", 404, "目标不存在或不可访问"))

    def test_quota_snapshot_serializes_promote_and_delete_but_not_long_hash(self):
        self.policy_id = self.policy()
        data = b"q" * 100
        key = self.uploads.create(self.client, self.spec(data))["upload_id"]
        def interrupt(stage):
            if stage == "sealed":
                raise SystemExit("sealed before rename")
        with patch.object(self.uploads, "checkpoint", interrupt), self.assertRaises(SystemExit):
            self.uploads.receive(key, iter([data]), self.permit)
        value = self.uploads.load(key)
        attempted, done = threading.Event(), threading.Event()
        errors = []
        def promote():
            attempted.set()
            try:
                self.uploads.promote(value)
            except BaseException as error:
                errors.append(error)
            finally:
                done.set()
        worker = threading.Thread(target=promote)
        original = self.uploads.materialized
        observed = []
        def snapshot(catalog):
            worker.start()
            self.assertTrue(attempted.wait(1))
            self.assertFalse(done.wait(0.1), "rename must wait for quota snapshot")
            size = original(catalog)
            observed.append(size)
            return size
        free = type("Disk", (), {"free": LIMITS["disk_reserve_bytes"] + 1})()
        with patch.object(self.uploads, "materialized", snapshot), patch("workbench.agent_uploads.shutil.disk_usage", return_value=free):
            self.uploads.create(self.client, self.spec(b"a"))
        worker.join(3)
        self.assertEqual(errors, [])
        self.assertTrue(done.is_set())
        self.assertEqual(observed, [100])
        self.assertFalse(self.uploads.path(key, "part.bin").exists())
        self.assertTrue(self.uploads.path(key, "blob.bin").exists())
        # Long hash proceeds while create holds the quota snapshot; only the
        # final same-handle deletion and removed-budget publication wait.
        old = int(time.time()) - 100000
        value.update(state="expired", error="expired", created_at=old, expires_at=old + 86400)
        self.uploads.write(value)
        hashed, deleted = threading.Event(), threading.Event()
        native_chunks = LocalFileHandle.chunks
        def chunks(handle, deadline):
            yield from native_chunks(handle, deadline)
            if handle.path == str(self.uploads.path(key, "blob.bin")):
                hashed.set()
        def delete():
            try:
                self.uploads.verify(value, delete=True)
            except BaseException as error:
                errors.append(error)
            finally:
                deleted.set()
        deletion = threading.Thread(target=delete)
        observed.clear()
        def delete_snapshot(catalog):
            deletion.start()
            self.assertTrue(hashed.wait(2), "hash must run outside quota lock")
            self.assertFalse(deleted.wait(0.1), "delete commit must wait for quota snapshot")
            size = original(catalog)
            observed.append(size)
            return size
        # The previously created one-byte reservation is not yet materialized.
        free = type("Disk", (), {"free": LIMITS["disk_reserve_bytes"] + 2})()
        with patch.object(LocalFileHandle, "chunks", chunks), patch.object(self.uploads, "materialized", delete_snapshot), patch("workbench.agent_uploads.shutil.disk_usage", return_value=free):
            self.uploads.create(self.client, self.spec(b"b"))
            deletion.join(3)
        self.assertEqual(errors, [])
        self.assertTrue(deleted.is_set())
        self.assertEqual(observed, [100])
        self.assertTrue(self.uploads.load(key)["removed"])
        self.assertFalse(self.uploads.path(key, "blob.bin").exists())

    def test_missing_leaf_validation_and_atomic_metadata_scan_do_not_report_false_aliases(self):
        missing = self.uploads.directory / str(uuid.uuid4()) / "session.json"
        resolve = Path.resolve
        def existing_only(path, *args, **kwargs):
            if not path.exists():
                raise AssertionError("must not canonicalize a missing leaf during parent creation")
            return resolve(path, *args, **kwargs)
        with patch.object(Path, "resolve", existing_only):
            self.assertEqual(self.uploads._safe(missing), missing)
        self.policy_id = self.policy()
        key = self.uploads.create(self.client, self.spec(b"x"))["upload_id"]
        from workbench.persistence import _replace_with_retry
        metadata_open, release, created = threading.Event(), threading.Event(), threading.Event()
        errors = []
        def delayed(source, destination, *args, **kwargs):
            if destination == self.uploads.path(key, "session.json") and read_json(source).get("evidence") is not None and not metadata_open.is_set():
                metadata_open.set(); release.wait(3)
            return _replace_with_retry(source, destination, *args, **kwargs)
        def receiving():
            try:
                self.uploads.receive(key, iter([b"x"]), self.permit)
            except BaseException as error:
                errors.append(error)
        def creating():
            try:
                self.uploads.create(self.client, self.spec(b"y"))
                created.set()
            except BaseException as error:
                errors.append(error)
        receiver, creator = threading.Thread(target=receiving), threading.Thread(target=creating)
        with patch("workbench.persistence._replace_with_retry", delayed):
            receiver.start()
            try:
                self.assertTrue(metadata_open.wait(2))
                creator.start()
                self.assertFalse(created.wait(0.1), "catalog must not see in-flight atomic temporary JSON")
            finally:
                release.set(); receiver.join(5); creator.join(5)
        self.assertEqual(errors, [])
        self.assertTrue(created.is_set())
        self.assertEqual(self.uploads.load(key)["sealed"]["bytes"], 1)
        # An actual private-directory junction is still rejected, including a
        # missing child. Only the missing-leaf false-positive was removed.
        target = self.base / "synthetic-target"
        target.mkdir()
        link = self.uploads.directory / str(uuid.uuid4())
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            with self.assertRaises(AgentError):
                self.uploads._safe(link / "session.json")
            target.rmdir()
            self.assertFalse(link.exists())
            with self.assertRaises(AgentError):
                self.uploads._safe(link / "session.json")
        finally:
            target.mkdir(exist_ok=True)
            link.rmdir()

    def test_dangling_private_symlink_is_rejected_before_missing_leaf_resolution(self):
        self.uploads.directory.mkdir()
        link = self.uploads.directory / str(uuid.uuid4())
        target = self.base / "never-created-target"
        try:
            os.symlink(target, link, target_is_directory=True)
        except OSError as error:
            if getattr(error, "winerror", None) == 1314:
                self.skipTest("Windows symlink privilege unavailable; native junction tested separately")
            raise
        try:
            self.assertFalse(link.exists())
            self.assertTrue(link.is_symlink())
            with self.assertRaises(AgentError):
                self.uploads._safe(link / "session.json")
        finally:
            link.unlink()

    def test_real_process_exit_all_staging_stages_recovers_from_disk_without_source_replay(self):
        self.policy_id = self.policy()
        runner = '''
import json, os, sys
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_uploads import UploadStore
from workbench.agent_management import credential_lock
s=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2])); r=Repository(Path(sys.argv[1])); st=UploadStore(r,s); client=s.clients()[sys.argv[3]]
def fault(stage):
 if stage==sys.argv[4]: os._exit(76)
st.checkpoint=fault
def permit(v,publish):
 with r.write_lock,credential_lock(s.config_dir):
  grant=st.authorize(client,v)
  if publish: st.publish_ready(v)
  return grant
v=st.create(client,json.loads(sys.argv[5])); key=v['upload_id']; st.receive(key,iter([b'private staging data']),permit); st.complete(key,permit)
'''
        for stage in ("created", "receiving", "partial_evidence", "part_fsynced", "sealed", "blob_renamed", "ready"):
            with self.subTest(stage=stage):
                spec = self.spec()
                process = subprocess.run([sys.executable, "-c", runner, str(self.repo.root), str(self.base / "credentials"), self.client["client_id"], stage, json.dumps(spec)], capture_output=True, timeout=20)
                self.assertEqual(process.returncode, 76, process.stderr)
                key = str(uuid.uuid5(uuid.UUID(self.security.workspace_id), self.client["client_id"] + ":" + spec["request_id"]))
                other = UploadStore(self.repo, self.security)
                original = self.uploads
                self.uploads = other
                try:
                    result = other.get(key, self.client, self.permit)
                    self.assertEqual(result["state"], "created" if stage == "created" else "failed" if stage in {"receiving", "partial_evidence", "part_fsynced"} else "ready")
                    if result["state"] == "ready":
                        self.assertEqual(other.path(key, "blob.bin").read_bytes(), b"private staging data")
                finally:
                    self.uploads = original

    def test_hundred_mib_file_streaming_memory_and_real_disk_evidence(self):
        import tracemalloc
        source, record = self.file_source(large_bytes=104857600)
        self.policy_id = self.policy(stream=False, files=[{"file_id": record["file_id"], "source_revision": record["source_revision"]}])
        spec = self.spec(b"", bytes=record["identity"]["size"], sha256=record["sha256"], filename=source.name, source={"mode": "file", "file_id": record["file_id"], "source_revision": record["source_revision"]})
        key = self.uploads.create(self.client, spec)["upload_id"]
        tracemalloc.start()
        started = time.monotonic()
        try:
            result = self.uploads.complete(key, self.permit)
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(result["sealed"], {"bytes": 104857600, "sha256": record["sha256"]})
        self.assertEqual(self.uploads.path(key, "blob.bin").stat().st_size, 104857600)
        self.assertLess(peak, 8 * 1048576)
        self.assertLess(time.monotonic() - started, 60)
        print(json.dumps({"staging_sample_bytes": 104857600, "python_peak_bytes": peak, "elapsed_seconds": round(time.monotonic() - started, 3)}))

    def test_upload_policy_real_crash_private_snapshot_cleanup_and_old_binary_refusal(self):
        with tempfile.TemporaryDirectory() as legacy:
            archive = subprocess.check_output(["git", "archive", "--format=zip", "eeeaf86"])
            with zipfile.ZipFile(io.BytesIO(archive)) as package:
                package.extractall(legacy)
            runner = '''
import os,json,sys
from pathlib import Path
from workbench.agent_security import AgentSecurity
from workbench.agent_management import CredentialManager
s=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2]))
def fault(self,stage):
 if stage==sys.argv[3]: os._exit(77)
CredentialManager.checkpoint=fault
s.manager().run('upload_policy',json.loads(sys.argv[4]),sys.argv[5],sys.argv[6],sys.argv[7])
'''
            old = "from pathlib import Path; import sys; from workbench.agent_security import AgentSecurity; s=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2])); s.manager().recover()"
            for stage in ("private_snapshot", "prepared", "format_fence", "upload_policy", "registry", "terminal_log", "completed"):
                self.tearDown(); self.setUp()
                preview = self.policies.preview(self.client["client_id"], {"workspace_id": self.security.workspace_id, "expected_version": client_version(self.client), "owner_kind": "project", "owner_id": self.project["id"], "stream": True, "files": [], "max_bytes": 104857600, "duration_seconds": 3600})
                params = {"policy": preview["policy"], "approval_digest": preview["preview_digest"]}
                result = subprocess.run([sys.executable, "-c", runner, str(self.repo.root), str(self.base / "credentials"), stage, json.dumps(params), self.client["client_id"], preview["expected_version"], stage], capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 77, result.stderr)
                if stage != "private_snapshot":
                    before = {str(path): path.read_bytes() for path in self.security.config_dir.rglob("*.json")}
                    result = subprocess.run([sys.executable, "-c", old, str(self.repo.root), str(self.base / "credentials")], cwd=legacy, capture_output=True, timeout=20)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(before, {str(path): path.read_bytes() for path in self.security.config_dir.rglob("*.json")})
                self.security.manager().recover()
                policies = load_policies(self.security)["policies"]
                self.assertEqual(len(policies), 0 if stage == "private_snapshot" else 1)
                self.assertFalse(list((self.security.config_dir / "management-snapshots").glob("*.json")))


@unittest.skipUnless(SUPPORTED, "Native staging requires Windows NTFS")
class UploadHTTPTests(unittest.TestCase):
    def setUp(self):
        from test_agent_files import FileHTTPTests
        FileHTTPTests.setUp(self)
        self.project = self.repo.create_project({"name": "上传归属"})
        client = self.security.clients()[self.client_id]
        params = {name: client[name] for name in ("name", "scopes", "categories")}
        self.security.manager().run("edit", {**params, "kinds": ["issue"], "project_ids": [self.project["id"]]}, self.client_id, client_version(client))

    def tearDown(self):
        self.workbench.close(); self.temp.cleanup()

    def request(self, *args, **kwargs):
        from test_agent_files import FileHTTPTests
        return FileHTTPTests.request(self, *args, **kwargs)

    def policy(self, files=None):
        prefix = f"/api/local/agent-management/clients/{self.client_id}/upload-policy"
        payload = {"workspace_id": self.security.workspace_id, "expected_version": client_version(self.security.clients()[self.client_id]), "owner_kind": "project", "owner_id": self.project["id"], "stream": True, "files": files or [], "max_bytes": 104857600, "duration_seconds": 3600}
        code, preview = self.request(prefix + "/preview", payload, "POST", True)
        self.assertEqual(code, 200, preview)
        confirm = {name: preview[name] for name in ("workspace_id", "expected_version", "preview_id", "preview_digest")}
        confirm.update(request_id=uuid.uuid4().hex, approved=True)
        code, result = self.request(prefix + "/confirm", confirm, "POST", True)
        self.assertEqual(code, 200, result)
        self.assertEqual(self.request(prefix + "/confirm", confirm, "POST", True), (200, result))
        return result["policy_id"]

    def create(self, data=b"binary\x00stream", **changes):
        payload = {"request_id": uuid.uuid4().hex, "policy_id": self.policy_id, "source": {"mode": "stream"}, "owner_kind": "project", "owner_id": self.project["id"], "filename": "incoming.bin", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), **changes}
        code, value = self.request("/api/agent/v1/uploads", payload, "POST")
        self.assertEqual(code, 200, value)
        return value["upload_id"]

    def put(self, key, data=b"binary\x00stream", lengths=None, extra=None, half_close=False):
        import http.client
        connection = http.client.HTTPConnection("127.0.0.1", self.workbench.server.server_address[1], timeout=10)
        try:
            connection.putrequest("PUT", f"/api/agent/v1/uploads/{key}/content")
            headers = {"Authorization": "Bearer " + self.config["token"], "X-Workbench-Workspace": self.security.workspace_id, "Content-Type": "application/octet-stream", **(extra or {})}
            for name, value in headers.items():
                connection.putheader(name, value)
            for length in ([str(len(data))] if lengths is None else lengths):
                connection.putheader("Content-Length", length)
            connection.endheaders()
            if data:
                connection.send(data)
            if half_close:
                connection.sock.shutdown(socket.SHUT_WR)
            response = connection.getresponse()
            value = json.loads(response.read())
            self.assertTrue(response.will_close)
            return response.status, value
        finally:
            connection.close()

    def test_stream_http_explicit_policy_real_bytes_complete_replay_and_history(self):
        self.policy_id = self.policy()
        key = self.create()
        code, staged = self.put(key)
        self.assertEqual(code, 200, staged)
        code, ready = self.request(f"/api/agent/v1/uploads/{key}/complete", {}, "POST")
        self.assertEqual(code, 200, ready)
        self.assertEqual(ready["state"], "ready")
        self.assertTrue(ready["available_for_binding"])
        self.assertFalse(ready["formal_attachment_created"])
        self.assertEqual(self.request(f"/api/agent/v1/uploads/{key}")[1], ready)
        self.assertEqual(self.request(f"/api/agent/v1/uploads/{key}/complete", {}, "POST"), (200, ready))
        self.assertNotIn("path", json.dumps(ready))
        self.policy()
        code, receipt = self.request(f"/api/agent/v1/uploads/{key}")
        self.assertEqual(code, 200)
        self.assertEqual(receipt["state"], "ready")
        self.assertFalse(receipt["available_for_binding"])
        self.assertGreaterEqual(self.request(f"/api/agent/v1/uploads/{key}/complete", {}, "POST")[0], 400)

    def test_raw_stream_cl_te_surplus_truncation_wrong_hash_and_idle(self):
        self.policy_id = self.policy()
        for lengths, extra, data, half_close, expected in ((["13", "13"], {}, b"", False, 400), ([], {}, b"", False, 411), (["13"], {"Transfer-Encoding": "chunked"}, b"", False, 400), (["-1"], {}, b"", False, 400), (["104857601"], {}, b"", False, 413), (["13"], {}, b"short", True, 409), (["13"], {}, b"binary\x00streamEXTRA", False, 413), (["13"], {}, b"xxxxxxxxxxxxx", False, 409)):
            key = self.create()
            code, value = self.put(key, data, lengths, extra, half_close)
            self.assertEqual(code, expected, value)
            self.assertNotIn("path", json.dumps(value))
            self.assertNotEqual(self.workbench.repository.agent_service.uploads.load(key)["state"], "ready")
        key = self.create()
        with patch.dict(LIMITS, {"socket_idle_seconds": 0.1, "total_seconds": 0.25}):
            self.assertEqual(self.put(key, b"", ["13"])[0], 408)

    def test_long_raw_stream_revoke_does_not_block_or_publish_ready(self):
        import http.client
        self.policy_id = self.policy()
        data = b"x" * 65537
        key = self.create(data)
        connection = http.client.HTTPConnection("127.0.0.1", self.workbench.server.server_address[1], timeout=10)
        connection.putrequest("PUT", f"/api/agent/v1/uploads/{key}/content")
        for name, value in {"Authorization": "Bearer " + self.config["token"], "X-Workbench-Workspace": self.security.workspace_id, "Content-Type": "application/octet-stream", "Content-Length": str(len(data))}.items():
            connection.putheader(name, value)
        connection.endheaders(); connection.send(data[:65536])
        store = self.repo.agent_service.uploads
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and store.load(key)["evidence"] is None:
            time.sleep(0.01)
        self.assertIsNotNone(store.load(key)["evidence"])
        code, busy = self.request(f"/api/agent/v1/uploads/{key}/cancel", {}, "POST")
        self.assertEqual(code, 409, busy)
        self.assertEqual(busy["code"], "upload_busy")
        self.assertEqual(store.load(key)["state"], "receiving")
        started = time.monotonic()
        prefix = f"/api/local/agent-management/clients/{self.client_id}/upload-policy"
        code, value = self.request(prefix, {"workspace_id": self.security.workspace_id, "expected_version": client_version(self.security.clients()[self.client_id]), "request_id": uuid.uuid4().hex}, "DELETE", True)
        self.assertEqual(code, 200, value)
        self.assertLess(time.monotonic() - started, 2)
        connection.send(data[-1:])
        response = connection.getresponse(); value = json.loads(response.read()); connection.close()
        self.assertGreaterEqual(response.status, 400, value)
        self.assertNotEqual(store.load(key)["state"], "ready")

    def test_long_raw_stream_switch_and_disable_reject_old_workspace_publication(self):
        import http.client
        from server import Repository
        for change in ("switch", "disable"):
            if change == "disable":
                self.tearDown(); self.setUp()
            self.policy_id = self.policy()
            data = b"y" * 65537
            key = self.create(data)
            connection = http.client.HTTPConnection("127.0.0.1", self.workbench.server.server_address[1], timeout=10)
            connection.putrequest("PUT", f"/api/agent/v1/uploads/{key}/content")
            for name, value in {"Authorization": "Bearer " + self.config["token"], "X-Workbench-Workspace": self.security.workspace_id, "Content-Type": "application/octet-stream", "Content-Length": str(len(data))}.items():
                connection.putheader(name, value)
            connection.endheaders(); connection.send(data[:65536])
            store = self.repo.agent_service.uploads
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and store.load(key)["evidence"] is None:
                time.sleep(0.01)
            self.assertIsNotNone(store.load(key)["evidence"])
            handler = self.workbench.server.RequestHandlerClass
            try:
                started = time.monotonic()
                with handler.repository_switch_lock:
                    if change == "switch":
                        handler.repository = Repository(self.base / "new-space")
                    else:
                        self.runtime.set_enabled(False)
                self.assertLess(time.monotonic() - started, 2)
                connection.send(data[-1:])
                response = connection.getresponse(); value = json.loads(response.read())
                self.assertEqual(response.status, 409, value)
                self.assertNotEqual(store.load(key)["state"], "ready")
            finally:
                connection.close(); handler.repository = self.repo

    def test_slow_budget_total_deadline_and_untrusted_route_headers(self):
        import http.client
        self.policy_id = self.policy()
        data = b"z" * 100
        key = self.create(data)
        connection = http.client.HTTPConnection("127.0.0.1", self.workbench.server.server_address[1], timeout=3)
        try:
            with patch.dict(LIMITS, {"socket_idle_seconds": 1, "total_seconds": 0.3}):
                connection.putrequest("PUT", f"/api/agent/v1/uploads/{key}/content")
                for name, value in {"Authorization": "Bearer " + self.config["token"], "X-Workbench-Workspace": self.security.workspace_id, "Content-Type": "application/octet-stream", "Content-Length": "100"}.items():
                    connection.putheader(name, value)
                connection.endheaders()
                connection.send(b"z"); time.sleep(0.18); connection.send(b"z")
                started = time.monotonic()
                response = connection.getresponse(); value = json.loads(response.read())
                self.assertEqual(response.status, 408, value)
                self.assertLess(time.monotonic() - started, 0.8)
        finally:
            connection.close()
        for route in (f"/api/agent/v1/uploads/{key}?x=1", "/api/agent/v1/uploadsBAD", f"/api/agent/v1/uploads/{key}/content?x=1"):
            self.assertGreaterEqual(self.request(route)[0], 400)
        self.assertEqual(self.request(f"/api/agent/v1/uploads/{key}", extra={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.request(f"/api/agent/v1/uploads/{key}", extra={"Host": "evil.example"})[0], 403)

    def test_real_mcp_file_source_and_old_tools_remain_schema_safe(self):
        from codex_agent_acceptance import RpcProcess
        from test_mcp_stdio import INITIALIZE
        client = self.security.clients()[self.client_id]
        manager = FileManagement(self.runtime)
        preview = manager.preview(self.client_id, {"workspace_id": self.security.workspace_id, "expected_version": client_version(client), "path": str(self.source), "purposes": ["attachment_source"], "encoding": "binary", "max_bytes": 10485760, "duration_seconds": 3600})
        payload = {name: preview[name] for name in ("workspace_id", "expected_version", "preview_id", "preview_digest")}
        payload.update(request_id=uuid.uuid4().hex, approved=True)
        record = manager.approved_record(self.client_id, payload)
        manager.commit(self.client_id, payload, record)
        self.policy_id = self.policy(files=[{"file_id": record["file_id"], "source_revision": record["source_revision"]}])
        rpc = RpcProcess([sys.executable, "agent_bridge.py", "--config", self.info["config_file"]], Path(__file__).resolve().parent, {**os.environ, "PYTHONIOENCODING": "utf-8"})
        try:
            rpc.call("initialize", INITIALIZE); rpc.notify("notifications/initialized")
            tools = rpc.call("tools/list")["tools"]
            self.assertEqual(len(tools), 19)
            def tool(name, arguments):
                return rpc.call("tools/call", {"name": "workbench_" + name, "arguments": arguments})
            self.assertFalse(tool("capabilities", {})["isError"])
            self.assertFalse(tool("list_projects", {})["isError"])
            self.assertFalse(tool("list_file_grants", {})["isError"])
            spec = {"request_id": "mcp-file", "policy_id": self.policy_id, "source": {"mode": "file", "file_id": record["file_id"], "source_revision": record["source_revision"]}, "owner_kind": "project", "owner_id": self.project["id"], "filename": record["display_name"], "bytes": record["identity"]["size"], "sha256": record["sha256"]}
            created = tool("create_upload", spec)
            self.assertFalse(created["isError"], created)
            key = created["structuredContent"]["upload_id"]
            complete = tool("complete_upload", {"upload_id": key})
            self.assertFalse(complete["isError"], complete)
            self.assertEqual(complete["structuredContent"]["state"], "ready")
            self.assertFalse(tool("get_upload", {"upload_id": key})["isError"])
            with self.assertRaises(RuntimeError):
                tool("create_upload", {**spec, "body_base64": "AAAA"})
            with self.assertRaises(RuntimeError):
                tool("complete_upload", {"upload_id": key, "path": str(self.source)})
            self.assertEqual(tool("cancel_upload", {"upload_id": key})["structuredContent"]["state"], "failed")
        finally:
            rpc.close()


if __name__ == "__main__":
    unittest.main()
