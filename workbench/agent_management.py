"""Recoverable credential administration shared by CLI and local management UI."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
import threading
import uuid
from contextlib import contextmanager

from .agent_security import (AgentError, private_write, read_json, client_kinds, client_confirmation_mode,
                             client_capability_grants, normalize_capability_grants, CAPABILITY_SPECS, client_file_ids)
from .write_coordinator import DataDirectoryLock


_credential_owners = threading.local()


@contextmanager
def credential_lock(directory):
    key = str(directory.resolve())
    held = getattr(_credential_owners, "held", set())
    if key in held:
        yield
        return
    with _credential_lock_once(directory):
        _credential_owners.held = held | {key}
        try:
            yield
        finally:
            _credential_owners.held = held


@contextmanager
def _credential_lock_once(directory):
    deadline = time.monotonic() + 3
    while True:
        try:
            lock = DataDirectoryLock(directory)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise AgentError("management_busy", "凭据正在更新，请稍后重试", 409, True)
            time.sleep(0.02)
    try:
        yield
    finally:
        lock.close()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def client_version(client):
    return digest(client)


def clean_client(client):
    keys = ("client_id", "name", "enabled", "scopes", "project_ids", "categories")
    return {**{key: client[key] for key in keys}, "kinds": client_kinds(client), "minimum_confirmation_mode": client_confirmation_mode(client),
            "authorization_schema_version": client.get("authorization_schema_version", 1),
            "capability_grants": client_capability_grants(client), "capability_grant_state": "dormant",
            "active_file_ids": client_file_ids(client),
            "management_revision": client.get("management_revision", 0), "version": client_version(client)}


class CredentialManager:
    def __init__(self, security):
        self.security = security
        self.directory = security.config_dir / "management-operations"
        if self.directory.resolve() != self.directory.absolute():
            raise AgentError("invalid_configuration", "管理日志目录无效", 503)

    def checkpoint(self, stage):
        """Fault-injection seam; production never executes supplied commands."""

    def _logs(self):
        if not self.directory.exists():
            return []
        return sorted(self.directory.glob("*.json"))

    def _load(self, path):
        if path.is_symlink() or not re.fullmatch(r"[a-f0-9]{64}\.json", path.name):
            raise AgentError("management_recovery_required", "管理日志路径无效，请检查备份", 503)
        try:
            value = read_json(path)
        except (OSError, ValueError):
            raise AgentError("management_recovery_required", "管理日志损坏，请检查备份", 503) from None
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") not in (1, 2, 3, 4) or value.get("workspace_id") != self.security.workspace_id or value.get("state") not in {"prepared", "completed", "recovery_required", "abandoned"}:
            raise AgentError("management_recovery_required", "管理日志版本或工作空间无效", 503)
        try:
            valid_id = str(uuid.UUID(value["client_id"])) == value["client_id"]
        except (ValueError, KeyError, AttributeError, TypeError):
            valid_id = False
        if not valid_id or value.get("operation_id") != path.stem or not isinstance(value.get("request_id"), str) or hashlib.sha256(value["request_id"].encode()).hexdigest() != path.stem:
            raise AgentError("management_recovery_required", "管理日志客户端无效", 503)
        if value["schema_version"] == 4:
            if value.get("registry_schema") != 3 or value.get("operation_family") not in {"credential", "file", "upload_policy", "attachment_policy"}:
                raise AgentError("management_recovery_required", "管理文件授权格式门槛无效", 503)
            if value["state"] in {"prepared", "recovery_required"}:
                try:
                    snapshot = read_json(self._snapshot_path(path.stem))
                except (OSError, ValueError):
                    raise AgentError("management_recovery_required", "管理私人快照缺失或损坏", 503) from None
                if not isinstance(snapshot, dict) or set(snapshot) != {"schema_version", "operation_id", "workspace_id", "client_id", "values", "intent"} or snapshot.get("schema_version") != 1 or snapshot.get("operation_id") != path.stem or snapshot.get("workspace_id") != self.security.workspace_id or snapshot.get("client_id") != value["client_id"] or value.get("private_snapshot_id") != path.stem or digest(snapshot) != value.get("private_snapshot_digest") or not isinstance(snapshot.get("values"), dict) or any(not key.startswith(("before_", "after_")) for key in snapshot["values"]):
                    raise AgentError("management_recovery_required", "管理私人快照校验失败", 503)
                value.update(snapshot["values"])
        snapshot_kind = {"file": "files", "upload_policy": "policies", "attachment_policy": "policies"}.get(value.get("operation_family"), "config")
        required = {"before_client", "after_client", "before_" + snapshot_kind, "after_" + snapshot_kind}
        if value["state"] in {"prepared", "recovery_required"} and not required <= value.keys():
            raise AgentError("management_recovery_required", "管理日志快照缺失", 503)
        if value["schema_version"] in (3, 4):
            if type(value.get("registry_schema")) is not int or value.get("registry_schema") != (3 if value["schema_version"] == 4 else 2):
                raise AgentError("management_recovery_required", "管理格式门槛缺失", 503)
            if value["state"] in {"prepared", "recovery_required"}:
                try:
                    after = value["after_client"]
                    if not isinstance(after, dict) or after.get("client_id") != value["client_id"]:
                        raise ValueError("授权身份不符")
                    self.security.validate_client(after["name"], after["scopes"], after["project_ids"], after["categories"],
                                                  client_kinds(after), client_confirmation_mode(after),
                                                  client_capability_grants(after) if after.get("authorization_schema_version") in (3, 4) else None)
                except (ValueError, KeyError, TypeError, AgentError):
                    raise AgentError("management_recovery_required", "管理授权快照无效，停止恢复", 503) from None
        if value.get("operation_family") == "file" and value["state"] in {"prepared", "recovery_required"}:
            from .agent_files import validate_ledger
            validate_ledger(value["before_files"], self.security)
            validate_ledger(value["after_files"], self.security)
        if value.get("operation_family") in {"upload_policy", "attachment_policy"} and value["state"] in {"prepared", "recovery_required"}:
            from .agent_upload_policy import validate_policies
            validate_policies(value["before_policies"], self.security)
            validate_policies(value["after_policies"], self.security)
        return value

    def blocked_clients(self):
        return {value["client_id"] for path in self._logs() if (value := self._load(path))["state"] in {"prepared", "recovery_required"}}

    def _write(self, path, value):
        self.directory.mkdir(mode=0o700, exist_ok=True)
        if value["schema_version"] != 4:
            private_write(path, value)
            return
        values = {key: item for key, item in value.items() if key.startswith(("before_", "after_"))}
        public = {key: item for key, item in value.items() if key not in values}
        if isinstance(public.get("result"), dict):
            public["result"] = {key: item for key, item in public["result"].items() if key != "config_file"}
        if value["state"] in {"prepared", "recovery_required"}:
            snapshot = {"schema_version": 1, "workspace_id": self.security.workspace_id, "operation_id": path.stem,
                        "client_id": value["client_id"], "values": values, "intent": {key: item for key, item in public.items() if key not in {"private_snapshot_id", "private_snapshot_digest", "snapshot_cleanup_pending"}}}
            snapshot_path = self._snapshot_path(path.stem, create=True)
            private_write(snapshot_path, snapshot)
            self.checkpoint("private_snapshot")
            public.update(private_snapshot_id=path.stem, private_snapshot_digest=digest(snapshot))
            value.update(private_snapshot_id=path.stem, private_snapshot_digest=digest(snapshot))
        private_write(path, public)
        if value["state"] in {"completed", "abandoned"}:
            self.checkpoint("terminal_log")
            self._cleanup_snapshot(path, public)

    def _snapshot_path(self, operation_id, create=False):
        directory = self.security.config_dir / "management-snapshots"
        path = directory / f"{operation_id}.json"
        if not re.fullmatch(r"[a-f0-9]{64}", operation_id) or directory.resolve() != directory.absolute() or path.resolve() != path.absolute():
            raise AgentError("management_recovery_required", "管理私人快照路径无效", 503)
        if create:
            directory.mkdir(mode=0o700, exist_ok=True)
        return path

    def _cleanup_snapshot(self, path, value):
        try:
            self._snapshot_path(path.stem).unlink(missing_ok=True)
            pending = False
        except (OSError, AgentError):
            pending = True
        if value.get("snapshot_cleanup_pending", False) != pending:
            value["snapshot_cleanup_pending"] = pending
            private_write(path, value)

    def _config(self, client_id):
        path = self.security.config_dir / f"{client_id}.json"
        if path.is_symlink():
            raise AgentError("invalid_configuration", "客户端配置不能使用符号链接", 503)
        return path

    def _finish(self, path, value):
        if value.get("operation_family") in {"upload_policy", "attachment_policy"}:
            return self._finish_policy(path, value)
        if value.get("operation_family") == "file":
            return self._finish_file(path, value)
        config_path = self._config(value["client_id"])
        try:
            current_config = read_json(config_path) if config_path.exists() else None
        except (OSError, ValueError):
            current_config = "unreadable"
        clients = self.security.clients()
        current_client = clients.get(value["client_id"])
        if current_config not in (value["before_config"], value["after_config"]) or current_client not in (value["before_client"], value["after_client"]):
            value["state"] = "recovery_required"
            self._write(path, value)
            return False
        if value["schema_version"] in (3, 4):
            self.security.save_clients(clients, minimum_schema=value["registry_schema"])
            self.checkpoint("format_fence")
        if value["after_config"] is not None and current_config != value["after_config"]:
            private_write(config_path, value["after_config"])
        self.checkpoint("config")
        clients[value["client_id"]] = value["after_client"]
        self.security.save_clients(clients)
        self.checkpoint("registry")
        completed = {key: item for key, item in value.items() if key not in {"before_config", "after_config", "before_client", "after_client"}}
        completed["state"] = "completed"
        self._write(path, completed)
        self.checkpoint("completed")
        return True

    def _run_policy(self, path, action, params, before, client_id, request_id, signature):
        from copy import deepcopy
        from .agent_upload_policy import load_policies, validate_policies
        before_policies = load_policies(self.security)
        after_policies = deepcopy(before_policies)
        after = {**before, "authorization_schema_version": 4, "management_revision": int(before.get("management_revision", 0)) + 1}
        for policy in after_policies["policies"].values():
            if policy["client_id"] == client_id:
                policy["enabled"] = False
        policy_id = None
        if action in {"upload_policy", "attachment_policy"}:
            policy = deepcopy(params["policy"])
            if policy["client_id"] != client_id or policy["client_version"] != client_version(after) or policy["expires_at"] <= time.time() or not policy["enabled"] or policy["policy_id"] in after_policies["policies"]:
                raise ValueError("暂存策略身份或批准版本无效")
            policy_id = policy["policy_id"]
            if policy.get("attachment_write"):
                after_policies["schema_version"] = 2
                for old in after_policies["policies"].values():
                    old.setdefault("attachment_write", None)
            elif after_policies["schema_version"] == 2:
                policy["attachment_write"] = None
            after_policies["policies"][policy_id] = policy
        validate_policies(after_policies, self.security)
        result = {"operation_id": path.stem, "client_id": client_id, "policy_id": policy_id, "version": client_version(after)}
        value = {"schema_version": 4, "registry_schema": 3, "operation_family": "attachment_policy" if action == "attachment_policy" else "upload_policy", "workspace_id": self.security.workspace_id, "client_id": client_id,
                 "operation_id": path.stem, "request_id": request_id, "input_digest": signature, "state": "prepared", "before_client": before, "after_client": after,
                 "before_policies": before_policies, "after_policies": after_policies, "result": result}
        self._write(path, value)
        self.checkpoint("prepared")
        if not self._finish_policy(path, value):
            raise AgentError("management_recovery_required", "暂存策略发生外部变化，停止覆盖", 503)
        return result

    def _finish_policy(self, path, value):
        from .agent_upload_policy import load_policies, save_policies
        clients = self.security.clients()
        if clients.get(value["client_id"]) not in (value["before_client"], value["after_client"]) or load_policies(self.security) not in (value["before_policies"], value["after_policies"]):
            value["state"] = "recovery_required"
            self._write(path, value)
            return False
        self.security.save_clients(clients, minimum_schema=3)
        self.checkpoint("format_fence")
        save_policies(self.security, value["after_policies"])
        self.checkpoint("upload_policy")
        clients[value["client_id"]] = value["after_client"]
        self.security.save_clients(clients, minimum_schema=3)
        self.checkpoint("registry")
        completed = {key: item for key, item in value.items() if not key.startswith(("before_", "after_"))}
        completed["state"] = "completed"
        self._write(path, completed)
        self.checkpoint("completed")
        return True

    def _run_file(self, path, action, params, before, client_id, request_id, signature):
        from copy import deepcopy
        from .agent_files import load_ledger, validate_ledger, file_id
        before_files = load_ledger(self.security)
        after_files = deepcopy(before_files)
        after = deepcopy(before)
        ids = client_file_ids(before)
        if action == "file_grant_create":
            record = params["record"]
            key = file_id(record["file_id"])
            if record["client_id"] != client_id or key in after_files["files"] or len(ids) >= 100 or record["status"] != "active" or record["expires_at"] <= time.time():
                raise ValueError("文件授权身份或数量无效")
            after_files["files"][key] = record
            ids = ids + [key]
        else:
            key = file_id(params["file_id"])
            record = after_files["files"].get(key)
            if not record or record["client_id"] != client_id:
                raise AgentError("not_found", "文件授权不存在", 404)
            record.update(status="revoked", version=record["version"] + 1)
            ids = [item for item in ids if item != key]
        validate_ledger(after_files, self.security)
        after.update(authorization_schema_version=4, active_file_ids=ids, management_revision=int(before.get("management_revision", 0)) + 1)
        result = {"operation_id": path.stem, "client_id": client_id, "file_id": key, "state": "completed", "version": client_version(after)}
        value = {"schema_version": 4, "registry_schema": 3, "operation_family": "file", "workspace_id": self.security.workspace_id,
                 "operation_id": path.stem, "request_id": request_id, "input_digest": signature, "client_id": client_id, "state": "prepared",
                 "before_client": before, "after_client": after, "before_files": before_files, "after_files": after_files, "result": result}
        self._write(path, value)
        self.checkpoint("prepared")
        if not self._finish_file(path, value):
            raise AgentError("management_recovery_required", "文件授权发生外部变化，已停止覆盖", 503)
        return result

    def _finish_file(self, path, value):
        from .agent_files import load_ledger, save_ledger
        clients = self.security.clients()
        if clients.get(value["client_id"]) not in (value["before_client"], value["after_client"]) or load_ledger(self.security) not in (value["before_files"], value["after_files"]):
            value["state"] = "recovery_required"
            self._write(path, value)
            return False
        self.security.save_clients(clients, minimum_schema=3)
        self.checkpoint("format_fence")
        save_ledger(self.security, value["after_files"])
        self.checkpoint("file_ledger")
        clients[value["client_id"]] = value["after_client"]
        self.security.save_clients(clients, minimum_schema=3)
        self.checkpoint("registry")
        completed = {key: item for key, item in value.items() if not key.startswith(("before_", "after_"))}
        completed["state"] = "completed"
        self._write(path, completed)
        self.checkpoint("completed")
        return True

    def _recover(self):
        blocked = []
        # Validate every format before applying any older snapshot.
        logs = [(path, self._load(path)) for path in self._logs()]
        orphans = []
        snapshots = self.security.config_dir / "management-snapshots"
        if snapshots.resolve() != snapshots.absolute():
            raise AgentError("management_recovery_required", "管理私人快照目录无效", 503)
        known = {path.stem: value for path, value in logs}
        for snapshot_path in sorted(snapshots.glob("*.json")) if snapshots.exists() else []:
            try:
                snapshot = read_json(self._snapshot_path(snapshot_path.stem))
                if not isinstance(snapshot, dict) or not isinstance(snapshot.get("intent"), dict):
                    raise ValueError()
                intent = snapshot["intent"]
                if set(snapshot) != {"schema_version", "operation_id", "workspace_id", "client_id", "values", "intent"} or snapshot["schema_version"] != 1 or snapshot["workspace_id"] != self.security.workspace_id or snapshot["operation_id"] != snapshot_path.stem or not isinstance(snapshot["values"], dict) or intent.get("schema_version") != 4 or intent.get("registry_schema") != 3 or intent.get("operation_family") not in {"credential", "file", "upload_policy", "attachment_policy"} or intent.get("state") not in {"prepared", "recovery_required"} or intent.get("client_id") != snapshot["client_id"] or intent.get("workspace_id") != self.security.workspace_id or intent.get("operation_id") != snapshot_path.stem or hashlib.sha256(intent["request_id"].encode()).hexdigest() != snapshot_path.stem or str(uuid.UUID(snapshot["client_id"])) != snapshot["client_id"]:
                    raise ValueError()
                if snapshot_path.stem in known:
                    if known[snapshot_path.stem].get("private_snapshot_digest") != digest(snapshot):
                        raise ValueError()
                else:
                    orphans.append({**intent, "private_snapshot_id": snapshot_path.stem, "private_snapshot_digest": digest(snapshot)})
            except (KeyError, TypeError, ValueError, OSError):
                raise AgentError("management_recovery_required", "管理私人快照格式无效，停止全部恢复", 503) from None
        if (self.security.registry_version() == 3 or orphans or any(value["schema_version"] == 4 for _, value in logs)) and any(value["schema_version"] < 4 and value["state"] in {"prepared", "recovery_required"} for _, value in logs):
            raise AgentError("management_recovery_required", "新文件授权日志与旧未决混合，停止恢复", 503)
        if any(value["schema_version"] == 3 for _, value in logs) and any(value["schema_version"] < 3 and value["state"] in {"prepared", "recovery_required"} for _, value in logs):
            raise AgentError("management_recovery_required", "新格式与旧未决日志混合，停止恢复并保留证据", 503)
        # Snapshot-before-prepare exits have never changed authority. Persist a
        # terminal decision before disposing of their private values.
        for intent in orphans:
            self.security.save_clients(self.security.clients(), minimum_schema=3)
            self._write(self.directory / (intent["operation_id"] + ".json"), {**intent, "state": "abandoned", "result": None, "orphaned_before_prepare": True})
        for path, value in logs:
            if value["state"] == "prepared" and not self._finish(path, value):
                blocked.append(value["client_id"])
            elif value["state"] == "recovery_required":
                blocked.append(value["client_id"])
            elif value["schema_version"] == 4:
                self._cleanup_snapshot(path, value)
        return blocked

    def recover(self):
        with credential_lock(self.security.config_dir):
            return self._recover()

    def operation(self, operation_id):
        if not isinstance(operation_id, str) or not re.fullmatch(r"[a-f0-9]{64}", operation_id):
            raise AgentError("not_found", "管理操作不存在", 404)
        path = self.directory / f"{operation_id}.json"
        if not path.exists():
            raise AgentError("not_found", "管理操作不存在", 404)
        with credential_lock(self.security.config_dir):
            self._recover()
            value = self._load(path)
        return {"operation_id": operation_id, "state": value["state"], "client_id": value["client_id"], "snapshot_cleanup_pending": value.get("snapshot_cleanup_pending", False), "result": value.get("result") if value["state"] == "completed" else None}

    def report(self):
        with credential_lock(self.security.config_dir):
            self._recover()
            return [{"operation_id": path.stem, "client_id": value["client_id"], "state": value["state"]} for path in self._logs() if (value := self._load(path))["state"] not in {"completed", "abandoned"}]

    def abandon(self, operation_id):
        if not re.fullmatch(r"[a-f0-9]{64}", operation_id):
            raise ValueError("管理操作标识无效")
        path = self.directory / f"{operation_id}.json"
        with credential_lock(self.security.config_dir):
            value = self._load(path)
            if value["state"] not in {"prepared", "recovery_required"}:
                raise ValueError("只允许放弃未决管理操作")
            clients = self.security.clients()
            if value["schema_version"] in (3, 4):
                self.security.save_clients(clients, minimum_schema=value["registry_schema"])
            client = clients.get(value["client_id"])
            if client:
                clients[value["client_id"]] = {**client, "enabled": False}
                self.security.save_clients(clients)
            result = {key: item for key, item in value.items() if key not in {"before_config", "after_config", "before_client", "after_client"}}
            result.update(state="abandoned", result=None)
            self._write(path, result)
        return {"operation_id": operation_id, "state": "abandoned", "client_id": value["client_id"]}

    def run(self, action, params, client_id=None, expected_version=None, request_id=None):
        request_id = str(uuid.uuid4()) if request_id is None else request_id
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
            raise ValueError("管理请求标识无效")
        if client_id is not None and (not isinstance(client_id, str) or str(uuid.UUID(client_id)) != client_id):
            raise ValueError("客户端标识无效")
        operation_id = hashlib.sha256(request_id.encode()).hexdigest()
        path = self.directory / f"{operation_id}.json"
        signature = digest([action, params.get("approval_digest") if action in {"file_grant_create", "upload_policy", "attachment_policy"} else params, client_id, expected_version])
        with credential_lock(self.security.config_dir):
            blocked = self._recover()
            if path.exists():
                value = self._load(path)
                if value["input_digest"] != signature:
                    raise AgentError("request_conflict", "请求标识已用于其他操作", 409)
                if value["state"] == "completed":
                    result = value["result"]
                    if action == "create" and "config_file" not in result:
                        result = {**result, "config_file": str(self._config(value["client_id"]))}
                    return result
                raise AgentError("management_recovery_required", "原操作尚未完成，请查询或修复", 503)
            if client_id in blocked:
                raise AgentError("management_recovery_required", "该客户端有未决管理操作，请先修复", 503)
            clients = self.security.clients()
            before = clients.get(client_id) if client_id else None
            if action != "create" and before is None:
                raise AgentError("not_found", "客户端不存在", 404)
            if expected_version is not None and client_version(before) != expected_version:
                raise AgentError("configuration_conflict", "客户端授权已变化，请重新核对", 409)
            if before and not before.get("enabled"):
                if action not in {"revoke", "file_grant_revoke", "upload_policy_revoke"}:
                    raise ValueError("已撤销客户端不能重新启用，请新建客户端")
            client_id = client_id or str(uuid.uuid4())
            if action in {"upload_policy", "attachment_policy", "upload_policy_revoke"}:
                if blocked:
                    raise AgentError("management_recovery_required", "先解决全部未决管理操作", 503)
                return self._run_policy(path, action, params, before, client_id, request_id, signature)
            if action in {"file_grant_create", "file_grant_revoke"}:
                if blocked:
                    raise AgentError("management_recovery_required", "先解决全部未决管理操作", 503)
                return self._run_file(path, action, params, before, client_id, request_id, signature)
            config_path = self._config(client_id)
            before_config = read_json(config_path) if config_path.exists() else None
            if before_config is not None and (not isinstance(before_config, dict) or before_config.get("schema_version") not in (1, 2)):
                raise AgentError("unsupported_schema", "客户端配置格式不受支持", 503)
            after_config = before_config
            after = dict(before) if before else {"client_id": client_id, "enabled": True}
            after["management_revision"] = int(after.get("management_revision", 0)) + 1
            if action in {"create", "edit"}:
                file_only = params.get("file_access_only", False)
                if type(file_only) is not bool or file_only and (action != "create" or params.get("kinds") != [] or params["scopes"] != ["read"] or params["project_ids"] or params["categories"]):
                    raise ValueError("文件专用客户端不能隐含旧业务范围")
                new_authorization = "capability_grants" in params or after.get("authorization_schema_version") in (3, 4) or file_only
                grants = normalize_capability_grants(params["capability_grants"]) if "capability_grants" in params else client_capability_grants(after)
                kinds = params.get("kinds", client_kinds(after))
                self.security.validate_client(params["name"], params["scopes"], params["project_ids"], params["categories"], kinds, params.get("minimum_confirmation_mode", client_confirmation_mode(after)), grants if new_authorization else None)
                if action == "create" and not kinds and not grants["grants"] and not file_only:
                    raise ValueError("独立客户端至少配置一项休眠授权")
                schema = 4 if file_only or after.get("authorization_schema_version") == 4 else 3 if new_authorization else 2
                after.update(minimum_confirmation_mode=params.get("minimum_confirmation_mode", client_confirmation_mode(after)), authorization_schema_version=schema, kinds=kinds, name=params["name"].strip(), scopes=sorted(set(params["scopes"])), project_ids=list(dict.fromkeys(params["project_ids"])), categories=list(dict.fromkeys(params["categories"])))
                if file_only:
                    after["active_file_ids"] = []
                if new_authorization:
                    after.update(capability_grants=grants, capability_grant_state="dormant")
            if action in {"create", "rotate", "origin"}:
                if action != "create" and (not isinstance(before_config, dict) or before_config.get("client_id") != client_id or before_config.get("workspace_id") != self.security.workspace_id or hashlib.sha256(str(before_config.get("token", "")).encode()).hexdigest() != before["token_hash"]):
                    raise AgentError("invalid_configuration", "客户端凭据配置不一致，请核查备份或新建客户端", 503)
                if action == "create":
                    self.security.validate_origin(params["base_url"])
                    after_config = {"schema_version": 2, "workspace_id": self.security.workspace_id, "client_id": client_id, "base_url": params["base_url"].rstrip("/")}
                else:
                    after_config = dict(before_config)
                if action == "origin":
                    self.security.validate_origin(params["base_url"])
                    after_config["base_url"] = params["base_url"].rstrip("/")
                else:
                    token = secrets.token_urlsafe(32)
                    after_config["token"] = token
                    after["token_hash"] = hashlib.sha256(token.encode()).hexdigest()
            elif action == "revoke":
                after["enabled"] = False
            elif action != "edit":
                raise ValueError("管理操作无效")
            if after_config is not None:
                after_config = {**after_config, "schema_version": 2, "kinds": client_kinds(after), "minimum_confirmation_mode": client_confirmation_mode(after)}
            result = {"operation_id": operation_id, "client_id": client_id, "enabled": after["enabled"], "rotated": action == "rotate", "version": client_version(after)}
            if action == "create":
                result.update(config_file=str(config_path), workspace_id=self.security.workspace_id)
            value = {"schema_version": 2, "workspace_id": self.security.workspace_id, "operation_id": operation_id, "request_id": request_id, "input_digest": signature, "client_id": client_id,
                     "state": "prepared", "before_client": before, "after_client": after, "before_config": before_config, "after_config": after_config, "result": result}
            if self.security.registry_version() >= 2 or after.get("authorization_schema_version") in (3, 4):
                if blocked:
                    raise AgentError("management_recovery_required", "升级或写入新格式前须解决全部未决操作", 503)
                value.update(schema_version=3, registry_schema=2)
            if self.security.registry_version() == 3 or after.get("authorization_schema_version") == 4:
                value.update(schema_version=4, registry_schema=3, operation_family="credential")
            self._write(path, value)
            self.checkpoint("prepared")
            if not self._finish(path, value):
                raise AgentError("management_recovery_required", "管理文件发生外部变化，已停止覆盖", 503)
            return result


class AgentManagement:
    def __init__(self, runtime):
        self.runtime = runtime
        self.repository = runtime.repository

    def _security(self):
        if not self.runtime.status()["workspace_id"]:
            raise AgentError("not_initialized", "请先开启接入以初始化当前空间", 409)
        security = self.runtime.security()
        security.manager().recover()
        return security

    def list_clients(self):
        if not self.runtime.status()["workspace_id"]:
            return {"items": [], "projects": [{"id": p["id"], "name": p["name"]} for p in self.repository.list_projects()], "categories": self.repository.document_categories()}
        security = self._security()
        blocked = security.manager().blocked_clients()
        project_ids = {p["id"] for p in self.repository.list_projects()}
        categories = set(self.repository.document_categories())
        items = []
        for client in security.clients().values():
            items.append({**clean_client(client), "recovery_required": client["client_id"] in blocked,
                          **self.runtime.diagnostics.observed(client["client_id"]),
                          "invalid_project_ids": [key for key in client["project_ids"] if key != "*" and key not in project_ids],
                          "invalid_categories": [key for key in client["categories"] if key != "*" and key not in categories]})
        return {"items": items, "projects": [{"id": p["id"], "name": p["name"]} for p in self.repository.list_projects()], "categories": list(self.repository.document_categories()),
                "capability_catalog": {name: {"operations": list(spec[0]), "resource_types": list(spec[1])} for name, spec in CAPABILITY_SPECS.items()}}

    def mutate(self, action, payload, client_id=None):
        fields = {"workspace_id", "request_id"} | ({"name", "scopes", "project_ids", "categories"} if action in {"create", "edit"} else set())
        if action != "create":
            fields.add("expected_version")
        optional = {"kinds", "minimum_confirmation_mode", "capability_grants"} if action in {"create", "edit"} else set()
        if action == "create":
            optional.add("file_access_only")
        if not isinstance(payload, dict) or fields - set(payload) or set(payload) - fields - optional:
            raise AgentError("invalid_request", "客户端管理字段无效")
        if payload["workspace_id"] != self.runtime.status()["workspace_id"]:
            raise AgentError("workspace_mismatch", "工作空间已变化，请重新核对", 409)
        if not isinstance(payload["request_id"], str) or not 1 <= len(payload["request_id"]) <= 100:
            raise ValueError("请求标识无效")
        if action != "create" and (not isinstance(payload["expected_version"], str) or not re.fullmatch(r"[a-f0-9]{64}", payload["expected_version"])):
            raise ValueError("客户端预期版本无效，请重新读取授权")
        security = self._security()
        params = {}
        if action in {"create", "edit"}:
            params = {key: payload[key] for key in ("name", "scopes", "project_ids", "categories")}
            for key in ("kinds", "minimum_confirmation_mode", "capability_grants"):
                if key in payload:
                    params[key] = payload[key]
            if "capability_grants" in params:
                params["capability_grants"] = normalize_capability_grants(params["capability_grants"])
            current = security.clients().get(client_id, {})
            validation = {**params, "authorization_schema_version": 4 if payload.get("file_access_only") is True else current.get("authorization_schema_version", 2)}
            if "capability_grants" not in validation and current.get("authorization_schema_version") in (3, 4):
                validation["capability_grants"] = client_capability_grants(current)
            security.validate_client(**validation)
            configured = validation.get("capability_grants", {}).get("grants", [])
            if payload.get("file_access_only") is True:
                params["file_access_only"] = True
                if params.get("kinds") != [] or params["scopes"] != ["read"]:
                    raise ValueError("文件专用客户端只允许只读和空条目类型")
            if sorted(params["scopes"]) not in (["read"], ["commit", "propose", "read"]) or not (params["project_ids"] or params["categories"] or configured or current.get("authorization_schema_version") in (3, 4) or params.get("file_access_only")):
                raise ValueError("请选择只读或整理入库，并至少授权一个范围")
            projects = {item["id"] for item in self.repository.list_projects()}
            categories = set(self.repository.document_categories())
            if any(key != "*" and key not in projects for key in params["project_ids"]) or any(key != "*" and key not in categories for key in params["categories"]):
                raise ValueError("授权项目或分类不存在，请刷新范围")
            if any("*" in params[key] and params[key] != ["*"] for key in ("project_ids", "categories")):
                raise ValueError("全部范围不能与指定范围混用")
        if action == "create":
            params["base_url"] = self.runtime.origin
        if action == "repair":
            params["base_url"] = self.runtime.origin
        result = security.manager().run("origin" if action == "repair" else action, params, client_id, payload.get("expected_version"), payload["request_id"])
        return {key: value for key, value in result.items() if key != "config_file"}


def restrict_categories(repository, old_names):
    """Fail closed before a category can disappear or its name be reused."""
    runtime = getattr(repository, "agent_runtime", None)
    service = getattr(repository, "agent_service", None)
    if runtime:
        if not runtime.status()["workspace_id"]:
            return []
        security = runtime.security()
    elif service:
        security = service.security
    else:
        # Repository-only tools have no knowledge of a custom private config
        # root. Runtime/CLI attach that context; do not invent another root.
        return []
    manager = security.manager()
    restored = []
    for client in security.clients().values():
        grants = client_capability_grants(client)
        narrowed = []
        for grant in grants["grants"]:
            resources = [resource for resource in grant["resources"] if not (resource["type"] == "document_category" and resource["name"] in old_names)]
            if resources:
                narrowed.append({**grant, "resources": resources})
        grant_changed = narrowed != grants["grants"]
        if not client.get("enabled") or not (set(client["categories"]) & set(old_names) or grant_changed):
            continue
        params = {key: client[key] for key in ("name", "scopes", "project_ids", "categories")}
        params["categories"] = [name for name in client["categories"] if name not in old_names]
        if grant_changed:
            params["capability_grants"] = {"schema_version": 1, "grants": narrowed}
        result = manager.run("edit", params, client["client_id"], client_version(client))
        restored.append((manager, client, result["version"]))
    return restored


def restore_renamed_category(changes, old_name, new_name):
    for manager, client, version in changes:
        params = {key: client[key] for key in ("name", "scopes", "project_ids", "categories")}
        params["categories"] = [new_name if name == old_name else name for name in client["categories"]]
        try:
            manager.run("edit", params, client["client_id"], version)
        except (AgentError, OSError, ValueError):
            raise AgentError("authorization_migration_incomplete", "分类已重命名，但部分客户端授权未同步，请在接入管理中重新核对范围", 409) from None
