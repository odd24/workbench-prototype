"""Explicit local-file consent, private grants and bounded text reads.

The source is never copied to a journal or business data directory. Metadata
preview has no content-read handle; approval alone permits hashing the source.
"""

import codecs
import hashlib
import os
import re
import secrets
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .agent_security import AgentError, client_file_ids, private_write, read_json, require_scope
from .agent_management import client_version, credential_lock, digest
from .agent_file_handles import LocalFileHandle, SUPPORTED, MAX_FILE_BYTES, CHUNK_BYTES, lexical_path


ENCODINGS = {"auto", "utf-8", "utf-16-le", "utf-16-be", "ascii", "gb18030", "cp1252", "binary"}
PURPOSES = {"text_read", "attachment_source"}
_slots_lock = threading.Lock()
_slots = {}


def file_id(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise AgentError("not_found", "文件不存在或不可访问", 404) from None
    return value


def empty_ledger(security):
    return {"schema_version": 1, "workspace_id": security.workspace_id, "files": {}}


def validate_ledger(value, security):
    try:
        if set(value) != {"schema_version", "workspace_id", "files"} or type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["workspace_id"] != security.workspace_id or not isinstance(value["files"], dict):
            raise ValueError()
        for key, item in value["files"].items():
            if file_id(key) != item["file_id"] or set(item) != {"file_id", "client_id", "path", "display_name", "identity", "sha256", "source_revision", "encoding", "bom_bytes", "purposes", "expires_at", "max_bytes", "status", "version"}:
                raise ValueError()
            file_id(item["client_id"])
            lexical_path(item["path"])
            if not isinstance(item["display_name"], str) or not 1 <= len(item["display_name"]) <= 240 or re.search(r"[\\/\x00-\x1f]", item["display_name"]) or item["display_name"] != item["path"].rsplit("\\", 1)[-1]:
                raise ValueError()
            identity = item["identity"]
            if set(identity) != {"volume", "index", "size", "created", "written", "changed"} or any(type(number) is not int or number < 0 for number in identity.values()):
                raise ValueError()
            if not re.fullmatch("[a-f0-9]{64}", item["sha256"]) or item["source_revision"] != digest([identity, item["sha256"]]):
                raise ValueError()
            if item["encoding"] not in ENCODINGS - {"auto"} or type(item["bom_bytes"]) is not int or item["bom_bytes"] not in {0, 2, 3} or not isinstance(item["purposes"], list) or not item["purposes"] or set(item["purposes"]) - PURPOSES or len(set(item["purposes"])) != len(item["purposes"]):
                raise ValueError()
            if item["encoding"] == "binary" and "text_read" in item["purposes"]:
                raise ValueError()
            if type(item["max_bytes"]) is not int or not 1 <= item["max_bytes"] <= MAX_FILE_BYTES or identity["size"] > item["max_bytes"] or type(item["expires_at"]) is not int or item["expires_at"] <= 0 or item["status"] not in {"active", "revoked"} or type(item["version"]) is not int or item["version"] < 1:
                raise ValueError()
    except (TypeError, KeyError, ValueError, AgentError):
        raise AgentError("invalid_configuration", "文件授权格式无效，停止读取与恢复", 503) from None
    return value


def ledger_path(security):
    path = security.config_dir / "file-grants.json"
    if path.resolve() != path.absolute():
        raise AgentError("invalid_configuration", "文件授权配置路径无效", 503)
    return path


def load_ledger(security):
    path = ledger_path(security)
    try:
        return validate_ledger(read_json(path), security) if path.exists() else empty_ledger(security)
    except (OSError, ValueError):
        raise AgentError("invalid_configuration", "文件授权配置不可读", 503) from None


def save_ledger(security, value):
    private_write(ledger_path(security), validate_ledger(value, security))


def denied_roots(security):
    home = Path.home()
    return [security.config_dir.parent, security.root / ".agent", security.root / "config",
            home / "AppData" / "Local" / "Google" / "Chrome" / "User Data",
            home / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data",
            home / "AppData" / "Roaming" / "Microsoft" / "Credentials",
            home / "AppData" / "Local" / "Microsoft" / "Credentials",
            home / ".codex", home / ".ssh", home / ".aws",
            *([Path(os.environ["CODEX_HOME"])] if os.environ.get("CODEX_HOME") else [])]


@contextmanager
def io_slot(client_id):
    with _slots_lock:
        if sum(_slots.values()) >= 4 or _slots.get(client_id, 0) >= 2:
            raise AgentError("file_io_busy", "文件读取并发已达上限", 429, True)
        _slots[client_id] = _slots.get(client_id, 0) + 1
    try:
        yield time.monotonic() + 5
    finally:
        with _slots_lock:
            _slots[client_id] -= 1
            if not _slots[client_id]:
                del _slots[client_id]


def public_info(item):
    return {key: item[key] for key in ("file_id", "display_name", "source_revision", "sha256", "encoding", "purposes", "expires_at", "max_bytes", "status", "version")} | {"size_bytes": item["identity"]["size"], "operations": ["get_file_info"] + (["read_file"] if "text_read" in item["purposes"] else [])}


def authorized_files(security, client):
    if not SUPPORTED:
        raise AgentError("unsupported_platform", "本机文件能力在当前平台不可用", 503)
    require_scope(client, "read")
    ledger = load_ledger(security)
    ids = client_file_ids(client)
    return {key: item for key, item in ledger["files"].items() if key in ids and item["client_id"] == client["client_id"] and item["status"] == "active" and item["expires_at"] > time.time()}


def get_authorized(security, client, key, purpose=None):
    item = authorized_files(security, client).get(file_id(key))
    if not item or purpose and purpose not in item["purposes"]:
        raise AgentError("not_found", "文件不存在或不可访问", 404)
    return item


def scan(security, path, expected, encoding, client_id, segment=None):
    """Hash and capture in the SAME pass; never trust sharing flags alone."""
    with io_slot(client_id) as deadline, LocalFileHandle(path, read=True, denied_roots=denied_roots(security)) as handle:
        if handle.initial != expected:
            raise AgentError("source_changed", "源文件已变化，请重新授权", 409)
        if expected["size"] > MAX_FILE_BYTES:
            raise AgentError("file_too_large", "源文件超过授权大小上限", 413)
        checksum, position, captured = hashlib.sha256(), 0, bytearray()
        decoder, resolved, bom = None, encoding, 0
        for chunk in handle.chunks(deadline):
            checksum.update(chunk)
            if position == 0:
                if encoding != "binary":
                    detected = ("utf-8", 3) if chunk.startswith(codecs.BOM_UTF8) else ("utf-16-le", 2) if chunk.startswith(codecs.BOM_UTF16_LE) else ("utf-16-be", 2) if chunk.startswith(codecs.BOM_UTF16_BE) else ("utf-8", 0)
                    resolved = detected[0] if encoding == "auto" else encoding
                    bom = detected[1] if resolved == detected[0] else 0
                    decoder = codecs.getincrementaldecoder(resolved)(errors="strict")
            try:
                if decoder:
                    if segment and position <= segment[0] < position + len(chunk) and segment[0] != 0:
                        boundary = codecs.getincrementaldecoder(resolved)(errors="strict")
                        boundary.setstate(decoder.getstate())
                        boundary.decode(chunk[(bom if position == 0 else 0):segment[0] - position], final=False)
                        if boundary.getstate()[0]:
                            raise AgentError("invalid_range", "起点不是有效字符边界，请使用next_offset")
                    text = decoder.decode(chunk[bom:] if position == 0 else chunk, final=False)
                    if "\x00" in text:
                        raise UnicodeError()
            except UnicodeError:
                raise AgentError("invalid_encoding", "文件不符合所选文本编码，请选择正确编码或仅授权附件来源") from None
            if segment:
                start, end = segment
                captured.extend(chunk[max(0, start - position):max(0, min(len(chunk), end - position))])
            position += len(chunk)
            if position > expected["size"]:
                raise AgentError("source_changed", "源文件大小已变化", 409)
        try:
            if decoder:
                decoder.decode(b"", final=True)
        except UnicodeError:
            raise AgentError("invalid_encoding", "文件文本编码不完整") from None
        if position != expected["size"] or handle.identity() != expected:
            raise AgentError("source_changed", "源文件版本已变化", 409)
        return checksum.hexdigest(), resolved if resolved != "auto" else "utf-8", bom, bytes(captured)


def read_segment(security, item, params):
    if set(params) - {"source_revision", "offset", "length"} or params.get("source_revision") != item["source_revision"]:
        raise AgentError("source_revision_required", "必须提供当前文件版本", 409)
    try:
        offset, length = int(params.get("offset", 0)), int(params.get("length", CHUNK_BYTES))
        if any(type(params.get(key)) is bool for key in ("offset", "length")) or offset < 0 or not 8 <= length <= CHUNK_BYTES or offset > item["identity"]["size"] or offset and offset < item["bom_bytes"] or item["encoding"].startswith("utf-16") and offset % 2:
            raise ValueError()
    except (ValueError, TypeError):
        raise AgentError("invalid_range", "字节范围无效；长度须为8至65536字节") from None
    end = min(offset + length, item["identity"]["size"])
    checksum, _encoding, _bom, data = scan(security, item["path"], item["identity"], item["encoding"], item["client_id"], (offset, end))
    if checksum != item["sha256"]:
        raise AgentError("source_changed", "文件内容已变化，请重新授权", 409)
    prefix = item["bom_bytes"] if offset == 0 else 0
    decoder = codecs.getincrementaldecoder(item["encoding"])(errors="strict")
    try:
        body = decoder.decode(data[prefix:], final=end == item["identity"]["size"])
        remainder = len(decoder.getstate()[0])
    except UnicodeError:
        raise AgentError("invalid_range", "起点不是有效字符边界，请使用上次返回的next_offset") from None
    actual_end = end - remainder
    return {**public_info(item), "body": body, "offset": offset, "end_offset": actual_end, "next_offset": actual_end if actual_end < item["identity"]["size"] else None}


class FileManagement:
    def __init__(self, runtime):
        self.runtime = runtime
        self.security = runtime.security()

    def _client(self, client_id, expected=None):
        client = self.security.clients().get(file_id(client_id))
        if not client or not client.get("enabled") or client_id in self.security.manager().blocked_clients():
            raise AgentError("not_found", "客户端不存在或需要恢复", 404)
        if expected is not None and client_version(client) != expected:
            raise AgentError("configuration_conflict", "客户端授权已变化，请重新预览", 409)
        return client

    def preview(self, client_id, payload):
        if not isinstance(payload, dict) or set(payload) != {"workspace_id", "expected_version", "path", "purposes", "encoding", "max_bytes", "duration_seconds"} or payload["workspace_id"] != self.security.workspace_id:
            raise AgentError("invalid_request", "文件预览参数无效")
        if not isinstance(payload["purposes"], list) or not payload["purposes"] or set(payload["purposes"]) - PURPOSES or len(set(payload["purposes"])) != len(payload["purposes"]) or payload["encoding"] not in ENCODINGS or payload["encoding"] == "binary" and "text_read" in payload["purposes"] or type(payload["max_bytes"]) is not int or not 1 <= payload["max_bytes"] <= MAX_FILE_BYTES or type(payload["duration_seconds"]) is not int or not 1 <= payload["duration_seconds"] <= 86400:
            raise AgentError("invalid_request", "文件用途、编码、大小或期限无效")
        with credential_lock(self.security.config_dir):
            client = self._client(client_id, payload["expected_version"])
        # Metadata handle only. No hash, ReadFile or file contents before consent.
        with LocalFileHandle(payload["path"], denied_roots=denied_roots(self.security)) as handle:
            identity, path = handle.initial, handle.path
        if identity["size"] > payload["max_bytes"]:
            raise AgentError("file_too_large", "源文件超过所选大小上限", 413)
        public = {"workspace_id": self.security.workspace_id, "client_id": client_id, "client_name": client["name"], "expected_version": payload["expected_version"], "path": path, "display_name": path.rsplit("\\", 1)[-1], "identity": identity, "purposes": sorted(payload["purposes"]), "encoding": payload["encoding"], "max_bytes": payload["max_bytes"], "duration_seconds": payload["duration_seconds"],
                  "disclosure": "确认后才读取并校验源文件。授权客户端可将读取内容发往外部模型服务；内容不会自动入库。每段读取都会重新校验完整文件，撤销不能收回已获发布许可的数据。附件来源本身不能上传；暂存还须另行明确批准，正式附件尚未开放。"}
        ticket = secrets.token_hex(32)
        tickets = self.runtime.preview_tickets
        for key in list(tickets):
            if tickets[key].get("file_expiry", float("inf")) < time.monotonic():
                del tickets[key]
        if len(tickets) >= 100:
            raise AgentError("management_limit", "预览数量过多，请重启服务后重试", 429)
        tickets[ticket] = {"file_expiry": time.monotonic() + 600, "preview": public, "digest": digest(public), "generation": self.runtime._generation, "session": digest(self.runtime._token), "runtime_version": self.runtime.status()["version"]}
        return {**public, "preview_id": ticket, "preview_digest": digest(public)}

    def validate_approval(self, client_id, payload):
        if not isinstance(payload, dict) or set(payload) != {"workspace_id", "preview_id", "preview_digest", "expected_version", "request_id", "approved"} or payload["approved"] is not True:
            raise AgentError("approval_required", "需要明确确认完整文件授权预览")
        ticket = self.runtime.preview_tickets.get(payload["preview_id"], {})
        public = ticket.get("preview", {})
        if ticket.get("file_expiry", 0) < time.monotonic() or self.runtime._expires < time.monotonic() or ticket.get("session") != digest(self.runtime._token) or ticket.get("runtime_version") != self.runtime.status()["version"] or ticket.get("generation") != self.runtime._generation or ticket.get("digest") != payload["preview_digest"] or public.get("client_id") != client_id or public.get("workspace_id") != payload["workspace_id"] or public.get("expected_version") != payload["expected_version"]:
            raise AgentError("preview_expired", "授权预览已失效，请重新预览", 409)
        if not isinstance(payload["request_id"], str) or not 1 <= len(payload["request_id"]) <= 100 or ticket.get("request_id", payload["request_id"]) != payload["request_id"]:
            raise AgentError("request_conflict", "此预览已用于其他确认请求", 409)
        self._client(client_id, payload["expected_version"])
        return public, ticket

    def approved_record(self, client_id, payload):
        with credential_lock(self.security.config_dir):
            public, ticket = self.validate_approval(client_id, payload)
            ticket["request_id"] = payload["request_id"]
        checksum, encoding, bom, _data = scan(self.security, public["path"], public["identity"], public["encoding"], client_id)
        return {"file_id": str(uuid.uuid5(uuid.UUID(self.security.workspace_id), payload["preview_id"])), "client_id": client_id, "path": public["path"], "display_name": public["display_name"], "identity": public["identity"], "sha256": checksum,
                "source_revision": digest([public["identity"], checksum]), "encoding": encoding, "bom_bytes": bom, "purposes": public["purposes"], "max_bytes": public["max_bytes"], "expires_at": int(time.time()) + public["duration_seconds"], "status": "active", "version": 1}

    def commit(self, client_id, payload, record):
        # Signature binds the stable preview request, not newly allocated IDs.
        with credential_lock(self.security.config_dir):
            self.validate_approval(client_id, payload)
            return self.security.manager().run("file_grant_create", {"record": record, "approval_digest": payload["preview_digest"]}, client_id, payload["expected_version"], payload["request_id"])

    def list(self, client_id):
        client = self.security.clients().get(file_id(client_id))
        if not client:
            raise AgentError("not_found", "客户端不存在", 404)
        return {"items": [public_info(item) | {"path": item["path"]} for item in load_ledger(self.security)["files"].values() if item["client_id"] == client_id], "expected_version": client_version(client)}
