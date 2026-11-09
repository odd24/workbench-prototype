"""Explicit staging policy; dormant attachment intentions never grant upload."""

import re
import secrets
import time
import uuid

from .agent_security import AgentError, private_write, read_json, require_scope, allows
from .agent_management import credential_lock, client_version, digest
from .agent_files import file_id, get_authorized


def policy_path(security):
    path = security.config_dir / "upload-policies.json"
    if path.resolve() != path.absolute():
        raise AgentError("invalid_configuration", "暂存授权路径无效", 503)
    return path


def validate_policies(value, security):
    try:
        if set(value) != {"schema_version", "workspace_id", "policies"} or type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["workspace_id"] != security.workspace_id or not isinstance(value["policies"], dict):
            raise ValueError()
        for key, item in value["policies"].items():
            if file_id(key) != item["policy_id"] or set(item) != {"policy_id", "client_id", "client_version", "owner_kind", "owner_id", "stream", "files", "max_bytes", "expires_at", "enabled"}:
                raise ValueError()
            file_id(item["client_id"])
            if not re.fullmatch("[a-f0-9]{64}", item["client_version"]) or item["owner_kind"] not in {"issue", "todo", "info", "document", "project"} or not isinstance(item["owner_id"], str) or not 1 <= len(item["owner_id"]) <= 100 or type(item["stream"]) is not bool or type(item["enabled"]) is not bool or type(item["max_bytes"]) is not int or not 1 <= item["max_bytes"] <= 104857600 or type(item["expires_at"]) is not int or item["expires_at"] <= 0 or not isinstance(item["files"], list) or len(item["files"]) > 100:
                raise ValueError()
            if not item["stream"] and not item["files"]:
                raise ValueError()
            ids = set()
            for source in item["files"]:
                if set(source) != {"file_id", "source_revision"} or file_id(source["file_id"]) in ids or not re.fullmatch("[a-f0-9]{64}", source["source_revision"]):
                    raise ValueError()
                ids.add(source["file_id"])
    except (KeyError, TypeError, ValueError, AgentError):
        raise AgentError("invalid_configuration", "暂存授权格式无效，停止恢复", 503) from None
    return value


def load_policies(security):
    path = policy_path(security)
    try:
        return validate_policies(read_json(path), security) if path.exists() else {"schema_version": 1, "workspace_id": security.workspace_id, "policies": {}}
    except (OSError, ValueError):
        raise AgentError("invalid_configuration", "暂存授权不可读", 503) from None


def save_policies(security, value):
    private_write(policy_path(security), validate_policies(value, security))


def effective_policy(security, client, policy_id, policies=None):
    require_scope(client, "read")
    policy = (load_policies(security) if policies is None else policies)["policies"].get(file_id(policy_id))
    if not policy or policy["client_id"] != client["client_id"] or not policy["enabled"] or policy["expires_at"] <= time.time() or policy["client_version"] != client_version(client):
        raise AgentError("forbidden", "暂存授权无效或已变化，请重新在本机明确批准", 403)
    return policy


def active_policies(repository, security, client):
    result = []
    policies = load_policies(security)
    for policy in policies["policies"].values():
        try:
            effective_policy(security, client, policy["policy_id"], policies)
            authorized_owner(repository, client, policy["owner_kind"], policy["owner_id"])
        except AgentError:
            continue
        sources = []
        for source in policy["files"]:
            try:
                grant = get_authorized(security, client, source["file_id"], "attachment_source")
                if grant["source_revision"] == source["source_revision"]:
                    sources.append(source)
            except AgentError:
                continue
        if policy["stream"] or sources:
            result.append({**policy, "files": sources})
    return result


def owner_snapshot(repository, kind, key):
    if kind == "project":
        owner = repository.project(key)
        if not owner:
            raise AgentError("not_found", "目标不存在", 404)
        return {"kind": kind, "id": key, "title": owner["name"], "revision": digest({"id": key, "name": owner["name"]})}
    if kind not in {"issue", "todo", "info", "document"}:
        raise AgentError("invalid_owner", "不支持的暂存归属")
    owner, path = repository.get_document(key) if kind == "document" else repository.get_record(key)
    if owner and kind != "document":
        repository._forget_record(path)
        owner, path = repository.get_record(key)
    if not owner or owner.get("type") != kind:
        raise AgentError("not_found", "目标不存在", 404)
    return {"kind": kind, "id": key, "title": owner["title"], "revision": owner["revision"]}


def authorized_owner(repository, client, kind, key):
    require_scope(client, "read")
    try:
        snapshot = owner_snapshot(repository, kind, key)
    except AgentError as error:
        if error.code == "not_found":
            raise AgentError("not_found", "目标不存在或不可访问", 404) from None
        raise
    if kind == "project":
        item = {"project_id": key}
    else:
        item, _path = repository.get_document(key) if kind == "document" else repository.get_record(key)
    if not allows(client, item):
        raise AgentError("not_found", "目标不存在或不可访问", 404)
    return snapshot


class UploadPolicyManagement:
    def __init__(self, runtime):
        self.runtime = runtime
        self.security = runtime.security()

    def client(self, key, expected=None):
        client = self.security.clients().get(file_id(key))
        if not client or not client.get("enabled") or key in self.security.manager().blocked_clients():
            raise AgentError("not_found", "客户端不存在或需要恢复", 404)
        if expected is not None and client_version(client) != expected:
            raise AgentError("configuration_conflict", "客户端授权变化，请重新预览", 409)
        return client

    def preview(self, key, payload):
        if not isinstance(payload, dict) or set(payload) != {"workspace_id", "expected_version", "owner_kind", "owner_id", "stream", "files", "max_bytes", "duration_seconds"} or payload["workspace_id"] != self.security.workspace_id or type(payload["duration_seconds"]) is not int or not 1 <= payload["duration_seconds"] <= 86400:
            raise AgentError("invalid_request", "暂存授权预览字段无效")
        with self.runtime.repository.write_lock, credential_lock(self.security.config_dir):
            client = self.client(key, payload["expected_version"])
            owner = authorized_owner(self.runtime.repository, client, payload["owner_kind"], payload["owner_id"])
            after = {**client, "authorization_schema_version": 4, "management_revision": int(client.get("management_revision", 0)) + 1}
            policy = {"policy_id": str(uuid.uuid4()), "client_id": key, "client_version": client_version(after), "owner_kind": payload["owner_kind"], "owner_id": payload["owner_id"], "stream": payload["stream"], "files": payload["files"], "max_bytes": payload["max_bytes"], "expires_at": int(time.time()) + payload["duration_seconds"], "enabled": True}
            validate_policies({"schema_version": 1, "workspace_id": self.security.workspace_id, "policies": {policy["policy_id"]: policy}}, self.security)
            names = []
            for source in policy["files"]:
                grant = get_authorized(self.security, client, source["file_id"], "attachment_source")
                if grant["source_revision"] != source["source_revision"]:
                    raise AgentError("source_changed", "来源版本变化，请重新批准", 409)
                names.append({"file_id": grant["file_id"], "display_name": grant["display_name"], "source_revision": grant["source_revision"]})
        preview = {"workspace_id": self.security.workspace_id, "client_id": key, "client_name": client["name"], "expected_version": client_version(client), "policy": policy, "owner": owner, "sources": names,
                   "disclosure": "仅授权上传暂存，不创建正式附件或写入正文。替代本客户端旧暂存策略；任何客户端授权或凭据变化均需重新批准。来源文件须另有有效附件来源授权；内容仅存本机私人暂存，24小时后按安全规则清理。"}
        ticket = secrets.token_hex(32)
        for ticket_id, value in list(self.runtime.preview_tickets.items()):
            if "upload_preview" in value and value.get("expires", 0) < time.monotonic():
                del self.runtime.preview_tickets[ticket_id]
        if len(self.runtime.preview_tickets) >= 100:
            raise AgentError("management_limit", "预览过多，请稍后或重启服务重试", 429)
        self.runtime.preview_tickets[ticket] = {"upload_preview": preview, "digest": digest(preview), "session": digest(self.runtime._token), "expires": time.monotonic() + 600, "runtime_version": self.runtime.status()["version"]}
        return {**preview, "preview_id": ticket, "preview_digest": digest(preview)}

    def approve(self, key, payload):
        if not isinstance(payload, dict) or set(payload) != {"workspace_id", "preview_id", "preview_digest", "expected_version", "request_id", "approved"} or payload["approved"] is not True or payload["workspace_id"] != self.security.workspace_id:
            raise AgentError("approval_required", "需要明确批准当前暂存授权预览")
        with self.runtime.repository.write_lock, credential_lock(self.security.config_dir):
            ticket = self.runtime.preview_tickets.get(payload["preview_id"], {})
            preview = ticket.get("upload_preview", {})
            if ticket.get("expires", 0) < time.monotonic() or self.runtime._expires < time.monotonic() or ticket.get("session") != digest(self.runtime._token) or ticket.get("runtime_version") != self.runtime.status()["version"] or ticket.get("digest") != payload["preview_digest"] or preview.get("client_id") != key or preview.get("expected_version") != payload["expected_version"]:
                raise AgentError("preview_expired", "暂存授权预览失效，请重新预览", 409)
            self.client(key, payload["expected_version"])
            if owner_snapshot(self.runtime.repository, preview["owner"]["kind"], preview["owner"]["id"]) != preview["owner"]:
                raise AgentError("owner_changed", "目标变化，请重新预览", 409)
            return self.security.manager().run("upload_policy", {"policy": preview["policy"], "approval_digest": payload["preview_digest"]}, key, payload["expected_version"], payload["request_id"])

    def list(self, key):
        client = self.security.clients().get(file_id(key))
        if not client:
            raise AgentError("not_found", "客户端不存在", 404)
        return {"items": [policy for policy in load_policies(self.security)["policies"].values() if policy["client_id"] == key], "expected_version": client_version(client)}
