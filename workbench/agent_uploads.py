"""Private, quota-reserved staging. This module never creates an attachment."""

import hashlib
import ntpath
import os
import re
import shutil
import stat
import time
import uuid
from contextlib import contextmanager

from .agent_security import AgentError, read_json, private_write
from .agent_management import credential_lock, digest, client_version
from .agent_files import file_id, get_authorized, denied_roots
from .agent_file_handles import LocalFileHandle, SUPPORTED, native_attributes
from .agent_upload_policy import effective_policy, authorized_owner
from .write_coordinator import DataDirectoryLock


LIMITS = {"file_bytes": 100 * 1048576, "client_bytes": 500 * 1048576, "workspace_bytes": 1024 * 1048576,
          "client_streams": 2, "workspace_streams": 4, "retention_seconds": 86400, "chunk_bytes": 65536,
          "socket_idle_seconds": 5, "total_seconds": 60, "disk_reserve_bytes": 16 * 1048576, "sessions": 1000}
STATES = {"created", "receiving", "ready", "consumed", "expired", "failed"}
HASH = re.compile("[a-f0-9]{64}")


def filename(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 200 or value != ntpath.basename(value) or re.search(r'[\\/:*?"<>|\x00-\x1f]', value) or value.endswith((".", " ")) or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", value, re.I):
        raise AgentError("invalid_filename", "文件名必须是普通文件名称，不能包含路径")
    return value


def public_session(value, available=False):
    keys = ("upload_id", "request_id", "state", "policy_id", "owner", "filename", "source", "declared_bytes", "declared_sha256", "created_at", "expires_at", "sealed", "binding", "consumption", "removed", "error")
    return {key: value[key] for key in keys} | {"available_for_binding": available, "formal_attachment_created": False}


def bindable(value):
    return value["state"] == "ready" and not value["removed"] and value["error"] is None and value["binding"] is None and value["consumption"] is None


class UploadStore:
    def __init__(self, repository, security):
        self.repository, self.security = repository, security
        self.directory = security.config_dir / "uploads"
        self._safe(self.directory)

    def checkpoint(self, stage):
        """Real process-exit test seam; never invokes caller commands."""

    @contextmanager
    def quota_lock(self):
        self._safe(self.directory)
        self._safe(self.directory / ".workbench-service.lock")
        with credential_lock(self.directory):
            self._safe(self.directory)
            yield

    def _safe(self, path):
        # Resolve only an existing ancestor. On Windows, resolving a missing
        # leaf while its parent is concurrently created can return a transient
        # partially normalized path. A missing server-derived UUID is not an
        # object yet; mkdir(exist_ok=False) and later opens validate it again.
        attributes = native_attributes(path)
        if attributes is not None and attributes & 0x400:
            raise AgentError("upload_recovery_required", "暂存包含重解析对象，保留现场", 503)
        try:
            leaf = path.lstat()
        except FileNotFoundError:
            leaf = None
        reparsed = leaf is not None and (stat.S_ISLNK(leaf.st_mode) or getattr(leaf, "st_file_attributes", 0) & 0x400)
        probe = path.parent if leaf is not None and not stat.S_ISDIR(leaf.st_mode) else path
        while not probe.exists():
            attributes = native_attributes(probe)
            if attributes is not None and attributes & 0x400:
                raise AgentError("upload_recovery_required", "暂存包含失效重解析对象，保留现场", 503)
            try:
                attributes = probe.lstat()
            except FileNotFoundError:
                probe = probe.parent
                continue
            if getattr(attributes, "st_file_attributes", 0) & 0x400 or probe.is_symlink():
                raise AgentError("upload_recovery_required", "暂存包含失效重解析对象，保留现场", 503)
            probe = probe.parent
        aliased = probe.resolve() != probe.absolute()
        linked = leaf is not None and stat.S_ISREG(leaf.st_mode) and leaf.st_nlink != 1
        if aliased or linked or reparsed:
            object_type = path.name if path.name in {"session.json", "part.bin", "blob.bin", ".workbench-service.lock"} else "directory"
            raise AgentError("upload_recovery_required", "暂存路径出现链接或别名，保留现场", 503, details={"reason": "alias" if aliased else "reparse" if reparsed else "link_count", "object": object_type})
        return path

    def folder(self, key, create=False):
        path = self._safe(self.directory / file_id(key))
        if create:
            path.mkdir(mode=0o700)
        return path

    def path(self, key, name):
        if name not in {"session.json", "part.bin", "blob.bin", ".workbench-service.lock"}:
            raise AgentError("invalid_request", "不支持的暂存对象")
        return self._safe(self.folder(key) / name)

    def _validate(self, value, key):
        try:
            fields = {"schema_version", "workspace_id", "upload_id", "client_id", "client_version", "policy_id", "owner", "filename", "source", "declared_bytes", "declared_sha256", "request_id", "input_digest", "created_at", "expires_at", "state", "sealed", "evidence", "binding", "consumption", "removed", "error"}
            if not isinstance(value, dict) or set(value) != fields or type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["workspace_id"] != self.security.workspace_id or file_id(value["upload_id"]) != key:
                raise ValueError()
            file_id(value["client_id"]); file_id(value["policy_id"])
            if not HASH.fullmatch(value["client_version"]) or not HASH.fullmatch(value["input_digest"]) or not isinstance(value["request_id"], str) or not 1 <= len(value["request_id"]) <= 100 or key != str(uuid.uuid5(uuid.UUID(self.security.workspace_id), value["client_id"] + ":" + value["request_id"])):
                raise ValueError()
            filename(value["filename"])
            if type(value["declared_bytes"]) is not int or not 0 <= value["declared_bytes"] <= LIMITS["file_bytes"] or not HASH.fullmatch(value["declared_sha256"]) or type(value["created_at"]) is not int or type(value["expires_at"]) is not int or not 0 < value["expires_at"] - value["created_at"] <= LIMITS["retention_seconds"] or value["state"] not in STATES or type(value["removed"]) is not bool or value["error"] not in {None, "interrupted", "cancelled", "expired", "verification_failed", "authorization_changed", "recovery_required"}:
                raise ValueError()
            owner = value["owner"]
            if set(owner) != {"kind", "id", "title", "revision"} or owner["kind"] not in {"issue", "todo", "info", "document", "project"} or not isinstance(owner["id"], str) or not isinstance(owner["title"], str) or not HASH.fullmatch(owner["revision"]):
                raise ValueError()
            source = value["source"]
            if source != {"mode": "stream"}:
                if set(source) != {"mode", "file_id", "source_revision"} or source["mode"] != "file" or not HASH.fullmatch(source["source_revision"]):
                    raise ValueError()
                file_id(source["file_id"])
            sealed = value["sealed"]
            if sealed is not None and (set(sealed) != {"bytes", "sha256"} or sealed["bytes"] != value["declared_bytes"] or sealed["sha256"] != value["declared_sha256"]):
                raise ValueError()
            if value["state"] in {"ready", "consumed"} and sealed is None:
                raise ValueError()
            evidence = value["evidence"]
            if evidence is not None and (set(evidence) != {"bytes", "sha256"} or type(evidence["bytes"]) is not int or not 0 <= evidence["bytes"] <= value["declared_bytes"] or not HASH.fullmatch(evidence["sha256"])):
                raise ValueError()
            binding = value["binding"]
            if binding is not None:
                if set(binding) != {"schema_version", "proposal_id", "version", "owner_revision"} or binding["schema_version"] != 1 or type(binding["version"]) is not int or binding["version"] < 1 or not HASH.fullmatch(binding["owner_revision"]):
                    raise ValueError()
                file_id(binding["proposal_id"])
            consumed = value["consumption"]
            if consumed is not None and (binding is None or set(consumed) != {"schema_version", "operation_id"} or consumed["schema_version"] != 1 or not HASH.fullmatch(consumed["operation_id"])):
                raise ValueError()
            if value["removed"] and value["state"] not in {"expired", "failed", "consumed"} or value["state"] == "consumed" and consumed is None:
                raise ValueError()
        except (KeyError, TypeError, ValueError, AgentError):
            raise AgentError("upload_recovery_required", "暂存格式未知或损坏，保留全部现场", 503) from None
        return value

    def load(self, key):
        self._safe(self.directory)
        if not self.directory.exists():
            raise AgentError("not_found", "暂存会话不存在或不可访问", 404)
        try:
            with self.quota_lock():
                return self._validate(read_json(self.path(key, "session.json")), key)
        except FileNotFoundError:
            raise AgentError("not_found", "暂存会话不存在或不可访问", 404) from None
        except (OSError, ValueError):
            raise AgentError("upload_recovery_required", "暂存元数据不可读，保留现场", 503) from None

    def write(self, value):
        with self.quota_lock():
            self._validate(value, value["upload_id"])
            private_write(self.path(value["upload_id"], "session.json"), value)

    def catalog(self):
        self._safe(self.directory)
        if not self.directory.exists():
            return []
        with self.quota_lock():
            return self._catalog()

    def _catalog(self):
        if not self.directory.exists():
            return []
        result = []
        for path in sorted(self.directory.iterdir()):
            if path.name == ".workbench-service.lock" and path.is_file() and self._safe(path):
                continue
            try:
                key = file_id(path.name)
            except AgentError:
                raise AgentError("upload_recovery_required", "暂存含未知目录，保留全部现场", 503) from None
            self._safe(path)
            if not path.is_dir():
                raise AgentError("upload_recovery_required", "暂存目录有未知对象，保留现场", 503)
            for child in path.iterdir():
                if child.name not in {"session.json", "part.bin", "blob.bin", ".workbench-service.lock"} or not self._safe(child).is_file():
                    raise AgentError("upload_recovery_required", "暂存会话有未知对象，保留现场", 503)
            try:
                value = self.load(key)
            except AgentError as error:
                if error.code == "not_found":
                    raise AgentError("upload_recovery_required", "暂存目录缺少元数据，保留现场", 503) from None
                raise
            content = [self.path(key, name) for name in ("part.bin", "blob.bin") if self.path(key, name).exists()]
            if len(content) > 1 or value["removed"] and content or value["state"] == "created" and content or any(child.stat().st_size > value["declared_bytes"] for child in content):
                raise AgentError("upload_recovery_required", "暂存磁盘布局与预留不一致，保留现场", 503)
            result.append(value)
        return result

    @contextmanager
    def session_lock(self, key):
        folder = self.folder(key)
        if not folder.exists():
            raise AgentError("not_found", "暂存会话不存在", 404)
        self.path(key, ".workbench-service.lock")
        try:
            lock = DataDirectoryLock(folder)
        except FileExistsError:
            raise AgentError("upload_busy", "该会话正在传输或校验，请查询原会话", 409, True) from None
        try:
            with self.quota_lock():
                current = self.load(key)
                active = []
                for other in self.catalog():
                    if other["upload_id"] == key:
                        continue
                    try:
                        probe = DataDirectoryLock(self.folder(other["upload_id"]))
                    except FileExistsError:
                        active.append(other)
                    else:
                        probe.close()
                if len(active) >= LIMITS["workspace_streams"] or sum(item["client_id"] == current["client_id"] for item in active) >= LIMITS["client_streams"]:
                    raise AgentError("upload_busy", "暂存I/O并发已满", 429, True)
            yield
        finally:
            lock.close()

    def authorize(self, client, value):
        if value["client_id"] != client["client_id"]:
            raise AgentError("not_found", "暂存会话不存在或不可访问", 404)
        policy = effective_policy(self.security, client, value["policy_id"])
        if value["client_version"] != client_version(client) or policy["owner_kind"] != value["owner"]["kind"] or policy["owner_id"] != value["owner"]["id"] or value["declared_bytes"] > policy["max_bytes"] or value["expires_at"] <= time.time():
            raise AgentError("authorization_changed", "暂存授权、期限或目标已变化", 409)
        owner = authorized_owner(self.repository, client, value["owner"]["kind"], value["owner"]["id"])
        if owner != value["owner"]:
            raise AgentError("owner_changed", "目标版本变化，请重新建立暂存", 409)
        source = value["source"]
        if source["mode"] == "stream":
            if not policy["stream"]:
                raise AgentError("forbidden", "未授权字节流暂存", 403)
            return None
        if {"file_id": source["file_id"], "source_revision": source["source_revision"]} not in policy["files"]:
            raise AgentError("forbidden", "来源未单独获准暂存", 403)
        grant = get_authorized(self.security, client, source["file_id"], "attachment_source")
        if grant["source_revision"] != source["source_revision"] or grant["sha256"] != value["declared_sha256"] or grant["identity"]["size"] != value["declared_bytes"] or value["declared_bytes"] > grant["max_bytes"] or value["filename"] != grant["display_name"]:
            raise AgentError("source_changed", "已批准来源版本不匹配", 409)
        return grant

    def create(self, client, payload):
        if not SUPPORTED:
            raise AgentError("unsupported_platform", "暂存文件校验仅支持已验证Windows固定NTFS", 503)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "policy_id", "source", "owner_kind", "owner_id", "filename", "bytes", "sha256"} or not isinstance(payload["request_id"], str) or not 1 <= len(payload["request_id"]) <= 100:
            raise AgentError("invalid_request", "暂存创建字段无效")
        if type(payload["bytes"]) is not int or payload["bytes"] < 0:
            raise AgentError("invalid_length", "暂存声明长度无效")
        if payload["bytes"] > LIMITS["file_bytes"]:
            raise AgentError("upload_overflow", "暂存超过单文件100MiB上限", 413)
        key = str(uuid.uuid5(uuid.UUID(self.security.workspace_id), client["client_id"] + ":" + payload["request_id"]))
        if self.directory.exists():
            with self.quota_lock():
                if self.path(key, "session.json").exists():
                    existing = self.load(key)
                    if existing["input_digest"] != digest(payload):
                        raise AgentError("request_conflict", "请求已用于不同暂存内容", 409)
                    return public_session(existing)
        now = int(time.time())
        owner = authorized_owner(self.repository, client, payload["owner_kind"], payload["owner_id"])
        value = {"schema_version": 1, "workspace_id": self.security.workspace_id, "upload_id": key, "client_id": client["client_id"], "client_version": client_version(client), "policy_id": payload["policy_id"], "owner": owner, "filename": filename(payload["filename"]), "source": payload["source"], "declared_bytes": payload["bytes"], "declared_sha256": payload["sha256"],
                 "request_id": payload["request_id"], "input_digest": digest(payload), "created_at": now, "expires_at": now + LIMITS["retention_seconds"], "state": "created", "sealed": None, "evidence": None, "binding": None, "consumption": None, "removed": False, "error": None}
        try:
            self._validate(value, key)
        except AgentError:
            raise AgentError("invalid_request", "暂存来源或声明字段无效") from None
        self.authorize(client, value)
        self.directory.mkdir(mode=0o700, exist_ok=True)
        with self.quota_lock():
            catalog = self.catalog()  # Full format preflight before any mutation.
            existing = next((item for item in catalog if item["upload_id"] == key), None)
            if existing:
                if existing["input_digest"] != value["input_digest"]:
                    raise AgentError("request_conflict", "请求已用于不同暂存内容", 409)
                return public_session(existing)
            used = sum(item["declared_bytes"] for item in catalog if not item["removed"])
            own = sum(item["declared_bytes"] for item in catalog if not item["removed"] and item["client_id"] == client["client_id"])
            reserved = value["declared_bytes"]
            if sum(not item["removed"] for item in catalog) >= LIMITS["sessions"] or used + reserved > LIMITS["workspace_bytes"] or own + reserved > LIMITS["client_bytes"]:
                raise AgentError("upload_quota", "暂存预留配额不足，请安全清理后重试", 429)
            materialized = self.materialized(catalog)
            if not 0 <= materialized <= used:
                raise AgentError("upload_recovery_required", "磁盘占用与预留不一致，保留现场", 503)
            outstanding = used - materialized
            if shutil.disk_usage(self.security.config_dir).free < outstanding + reserved + LIMITS["disk_reserve_bytes"]:
                raise AgentError("insufficient_storage", "磁盘可用空间不足，未预留暂存", 507)
            # A crash before the first session log leaves an unknown folder;
            # recovery deliberately preserves it for explicit inspection.
            self.folder(key, create=True)
            self.write(value)
            self.checkpoint("created")
        return public_session(value)

    def materialized(self, catalog):
        """Caller holds directory quota lock shared by promote/delete commits."""
        return sum(self.path(item["upload_id"], name).stat().st_size for item in catalog if not item["removed"] for name in ("part.bin", "blob.bin") if self.path(item["upload_id"], name).exists())

    def promote(self, value):
        with self.quota_lock():
            key = value["upload_id"]
            if self.load(key) != value or value["sealed"] is None or self.path(key, "blob.bin").exists():
                raise AgentError("upload_recovery_required", "暂存发布布局变化，停止重命名", 503)
            os.rename(self.path(key, "part.bin"), self.path(key, "blob.bin"))

    def _begin(self, value):
        with self.quota_lock():
            catalog = self.catalog()
            if value["state"] != "created" or value["binding"] is not None or value["removed"]:
                raise AgentError("invalid_upload_state", "会话不能再次传输，请查询原状态", 409)
            value["state"] = "receiving"
            self.write(value)
            self.checkpoint("receiving")

    def _capture(self, value, chunks):
        key = value["upload_id"]
        if self.path(key, "part.bin").exists() or self.path(key, "blob.bin").exists():
            raise AgentError("upload_recovery_required", "暂存内容已存在，停止覆盖", 503)
        checksum, count = hashlib.sha256(), 0
        with self.path(key, "part.bin").open("xb") as stream:
            try:
                for chunk in chunks:
                    if not isinstance(chunk, bytes) or len(chunk) > LIMITS["chunk_bytes"]:
                        raise AgentError("invalid_stream", "暂存读块无效")
                    if count + len(chunk) > value["declared_bytes"]:
                        raise AgentError("upload_overflow", "实际上传长度超过声明", 413)
                    stream.write(chunk)
                    count += len(chunk)
                    checksum.update(chunk)
                    if count == len(chunk) or count % 1048576 == 0:
                        stream.flush(); os.fsync(stream.fileno())
                        value["evidence"] = {"bytes": count, "sha256": checksum.hexdigest()}
                        self.write(value)
                        self.checkpoint("partial_evidence")
            finally:
                stream.flush(); os.fsync(stream.fileno())
                value["evidence"] = {"bytes": count, "sha256": checksum.hexdigest()}
                self.write(value)
        self.checkpoint("part_fsynced")
        if count != value["declared_bytes"] or checksum.hexdigest() != value["declared_sha256"]:
            raise AgentError("upload_incomplete", "真实暂存长度或摘要不符合声明", 409)
        value["sealed"] = {"bytes": count, "sha256": checksum.hexdigest()}
        self.write(value)
        self.checkpoint("sealed")
        self.promote(value)
        self.checkpoint("blob_renamed")
        return value

    def receive(self, key, chunks, permit):
        with self.session_lock(key):
            value = self.load(key)
            permit(value, False)
            self._begin(value)
            try:
                value = self._capture(value, chunks)
                permit(value, False)
                return public_session(value)
            except Exception:
                # Do not erase a conflicting cancellation/terminal decision.
                current = self.load(key)
                if current["state"] == "receiving":
                    current.update(state="failed", error="verification_failed")
                    self.write(current)
                raise

    def verify(self, value, name="blob.bin", evidence=None, delete=False):
        path = self.path(value["upload_id"], name)
        checksum, count = hashlib.sha256(), 0
        expected = evidence or {"bytes": value["declared_bytes"], "sha256": value["declared_sha256"]}
        # Private staging is also subject to ordinary-file identity/link checks.
        with LocalFileHandle(str(path), read=True, delete=delete) as handle:
            if handle.initial["size"] != expected["bytes"]:
                raise AgentError("upload_recovery_required", "暂存磁盘大小不匹配，保留现场", 503)
            for chunk in handle.chunks(time.monotonic() + LIMITS["total_seconds"]):
                count += len(chunk); checksum.update(chunk)
            if handle.identity() != handle.initial or count != expected["bytes"] or checksum.hexdigest() != expected["sha256"]:
                raise AgentError("upload_recovery_required", "暂存磁盘摘要或身份不匹配，保留现场", 503)
            if delete:
                with self.quota_lock():
                    if self.load(value["upload_id"]) != value:
                        raise AgentError("upload_recovery_required", "删除前暂存记录变化，保留现场", 503)
                    handle.delete_verified()
                    handle.__exit__(None, None, None)  # Close/delete under quota lock.
                    if path.exists():
                        raise AgentError("upload_cleanup_pending", "暂存仍占用磁盘，保留预算", 409)
                    value["removed"] = True
                    self.write(value)

    def complete(self, key, permit):
        with self.session_lock(key):
            value = self.load(key)
            grant = permit(value, False)
            if value["state"] == "ready":
                self.verify(value)
                permit(value, False)
                return public_session(value, bindable(value))
            if value["state"] == "created" and value["source"]["mode"] == "file":
                self._begin(value)
                try:
                    with LocalFileHandle(grant["path"], read=True, denied_roots=denied_roots(self.security)) as handle:
                        if handle.initial != grant["identity"]:
                            raise AgentError("source_changed", "来源文件已变化", 409)
                        value = self._capture(value, handle.chunks(time.monotonic() + 5))
                        if handle.identity() != grant["identity"]:
                            raise AgentError("source_changed", "来源读取期间版本已变化", 409)
                except Exception:
                    value.update(state="failed", error="verification_failed")
                    self.write(value)
                    raise
            if value["state"] != "receiving" or value["sealed"] is None:
                raise AgentError("upload_incomplete", "暂存尚未完整传输或已终结", 409)
            self.verify(value)
            # The transport calls this under the final authorization/switch lock
            # and publishes this tiny metadata transition before releasing it.
            permit(value, True)
            self.checkpoint("ready")
            return public_session(value, bindable(value))

    def publish_ready(self, value):
        current = self.load(value["upload_id"])
        if current != value or current["state"] != "receiving" or current["sealed"] is None or current["error"] is not None or current["removed"] or current["binding"] is not None or current["consumption"] is not None:
            raise AgentError("invalid_upload_state", "暂存状态变化，不能发布ready", 409)
        value["state"] = "ready"
        self.write(value)

    def cancel(self, key, client):
        with self.session_lock(key):
            value = self.load(key)
            if value["client_id"] != client["client_id"]:
                raise AgentError("not_found", "暂存会话不可访问", 404)
            if value["binding"] is not None or value["consumption"] is not None:
                raise AgentError("upload_in_use", "暂存已被受控消费流程保护", 409)
            if value["state"] not in {"failed", "expired"}:
                value.update(state="failed", error="cancelled")
                self.write(value)
            return public_session(value)

    def get(self, key, client, permit):
        value = self.load(key)
        if value["client_id"] != client["client_id"]:
            raise AgentError("not_found", "暂存会话不存在或不可访问", 404)
        try:
            permit(value, False)
        except AgentError as error:
            return public_session(value) | {"unavailable_reason": error.code}
        try:
            with self.session_lock(key):
                value = self.load(key)
                if value["state"] == "receiving":
                    if value["sealed"] is None:
                        value.update(state="failed", error="interrupted")
                        self.write(value)
                    else:
                        if self.path(key, "part.bin").exists() and not self.path(key, "blob.bin").exists():
                            self.verify(value, "part.bin")
                            self.promote(value)
                        self.verify(value)
                        permit(value, True)
                if value["state"] == "ready":
                    self.verify(value)
                    permit(value, False)
                    return public_session(value, bindable(value))
                return public_session(value)
        except AgentError as error:
            if error.code == "upload_busy":
                return public_session(self.load(key))
            raise

    def consumer_contract(self, *_args, **_kwargs):
        raise AgentError("unsupported_operation", "正式附件绑定和消费尚未实现", 409)

    def recover_and_cleanup(self, permit, cleanup=False):
        # Full metadata/path preflight, then nonblocking per-session ownership.
        if not self.directory.exists():
            return []
        with self.quota_lock():
            catalog = self.catalog()
        results = []
        for original in catalog:
            try:
                with self.session_lock(original["upload_id"]):
                    value = self.load(original["upload_id"])
                    if value["binding"] is not None or value["consumption"] is not None:
                        results.append(public_session(value) | {"maintenance": "protected"})
                        continue
                    key = value["upload_id"]
                    if value["state"] == "receiving":
                        if value["sealed"] is not None:
                            if self.path(key, "part.bin").exists() and not self.path(key, "blob.bin").exists():
                                self.verify(value, "part.bin")
                                self.promote(value)
                            self.verify(value)
                            try:
                                permit(value, True)
                            except AgentError:
                                value.update(state="failed", error="authorization_changed")
                                self.write(value)
                        else:
                            value.update(state="failed", error="interrupted")
                            self.write(value)
                    if cleanup and value["expires_at"] <= time.time() and value["state"] != "consumed":
                        value.update(state="expired", error="expired")
                        self.write(value)  # Terminal decision before disposal.
                        for name in ("part.bin", "blob.bin"):
                            path = self.path(key, name)
                            if path.exists():
                                # Never discard third-party bytes. Incomplete
                                # parts have no sealed digest and need inspection.
                                evidence = value["sealed"] if name == "blob.bin" else value["evidence"]
                                if evidence is None:
                                    raise AgentError("upload_recovery_required", "未核验半成品需人工核查，保留占用", 503)
                                self.verify(value, name, evidence, delete=True)
                                if path.exists():
                                    raise AgentError("upload_cleanup_pending", "暂存文件仍占用磁盘，保留预算", 409)
                        with self.quota_lock():
                            value["removed"] = True
                            self.write(value)
                    results.append(public_session(value))
            except AgentError as error:
                if error.code == "upload_busy":
                    results.append(public_session(original) | {"maintenance": "busy"})
                else:
                    raise
        return results
