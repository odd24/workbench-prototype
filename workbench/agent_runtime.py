"""Workspace-local Agent lifecycle; read-only discovery never initializes a space."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
import uuid
from pathlib import Path

from .agent_security import AgentError, AgentSecurity, private_write, read_json
from .write_coordinator import DataDirectoryLock


LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def config_base(value=None):
    return Path(value) if value is not None else Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "Workbench" / "agent"


def discover(root, base=None):
    """Return identity and preference without mkdir, ACL changes, or credentials."""
    root = Path(root).resolve()
    identity = root / ".agent" / "workspace.json"
    result = {"workspace_id": None, "startup_preference": False, "preference_error": None}
    try:
        if identity.parent.is_symlink() or identity.is_symlink() or not identity.resolve().is_relative_to(root):
            raise ValueError("工作空间身份路径无效")
        if not identity.exists():
            return result
        value = read_json(identity)
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("工作空间身份版本不受支持")
        result["workspace_id"] = str(uuid.UUID(value["workspace_id"]))
        directory = (config_base(base) / result["workspace_id"]).resolve()
        if directory.is_relative_to(root) or directory.is_relative_to(Path(__file__).resolve().parent.parent):
            raise ValueError("凭据目录必须位于仓库和业务数据目录外")
        preference = directory / "runtime.json"
        if preference.is_symlink():
            raise ValueError("启动配置不能使用符号链接")
        if preference.exists():
            value = read_json(preference)
            if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("workspace_id") != result["workspace_id"] or type(value.get("startup_enabled")) is not bool:
                raise ValueError("启动配置格式或工作空间无效")
            result["startup_preference"] = value["startup_enabled"]
    except (OSError, ValueError, TypeError, KeyError):
        result["preference_error"] = "接入配置不可用，请备份并检查身份与启动配置；未自动启用"
    return result


def startup_enabled(root, base=None, override=None):
    return override if override is not None else discover(root, base)["startup_preference"]


class AgentRuntime:
    def __init__(self, repository, host="127.0.0.1", port=4173, base=None, source="preference"):
        self.repository = repository
        self.host, self.port = host, port
        self.base = config_base(base)
        self.source = source
        self._token = secrets.token_urlsafe(32)
        self._expires = time.monotonic() + 3600
        self._generation = secrets.token_hex(16)
        self.operations = {}
        from .agent_diagnostics import AgentDiagnostics
        self.diagnostics = AgentDiagnostics(self)

    @property
    def origin(self):
        return f"http://{'[::1]' if self.host == '::1' else self.host}:{self.port}"

    def status(self, session=False):
        value = discover(self.repository.root, self.base)
        enabled = bool(getattr(self.repository, "agent_service", None))
        value.update(runtime_state="enabled" if enabled else "disabled" if value["workspace_id"] else "uninitialized",
                     enabled=enabled, effective_source=self.source, origin=self.origin)
        value["version"] = hashlib.sha256(json.dumps([self._generation, value], sort_keys=True).encode()).hexdigest()
        if session:
            if time.monotonic() >= self._expires:
                self._token = secrets.token_urlsafe(32)
                self._expires = time.monotonic() + 3600
            value["management_token"] = self._token
        return value

    def authorize(self, token):
        if time.monotonic() >= self._expires or not isinstance(token, str) or not secrets.compare_digest(token, self._token):
            raise AgentError("management_session_expired", "管理会话已失效，请刷新接入页面后重试", 403)

    def security(self):
        return AgentSecurity(self.repository.root, self.base)

    def set_enabled(self, enabled):
        if enabled:
            if self.host not in LOOPBACK:
                raise AgentError("not_loopback", "Agent 接入只允许本机监听", 403)
            if discover(self.repository.root, self.base)["preference_error"]:
                raise AgentError("invalid_configuration", "接入配置异常，请先修复配置", 503)
            store = getattr(self.repository, "agent_proposals", None)
            if store:
                store.recover()
                store.guard_writes()
            if not getattr(self.repository, "agent_service", None):
                from .agent_service import AgentService
                security = self.security()
                security.manager().recover()
                self.repository.agent_service = AgentService(self.repository, security)
        else:
            self.repository.agent_service = None

    def update(self, payload):
        allowed = {"workspace_id", "expected_version", "request_id", "enabled", "startup_preference"}
        if not isinstance(payload, dict) or set(payload) - allowed or not {"workspace_id", "expected_version", "request_id"} <= payload.keys():
            raise AgentError("invalid_request", "接入设置字段无效")
        request_id = payload["request_id"]
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100 or not all(c.isalnum() or c in "-_" for c in request_id):
            raise AgentError("invalid_request", "请求标识无效")
        if not {"enabled", "startup_preference"} & payload.keys() or any(type(payload[key]) is not bool for key in ("enabled", "startup_preference") if key in payload):
            raise AgentError("invalid_request", "启用状态和启动偏好必须是布尔值")
        signature = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        previous = self.operations.get(request_id)
        if previous:
            if previous[0] != signature:
                raise AgentError("request_conflict", "请求标识已用于其他设置", 409)
            return previous[1]
        if len(self.operations) >= 1000:
            raise AgentError("management_limit", "本次服务管理操作过多，请重启服务后重试", 429)
        current = self.status()
        if payload["workspace_id"] != current["workspace_id"] or payload["expected_version"] != current["version"]:
            raise AgentError("configuration_conflict", "工作空间或设置已变化，请重新核对", 409)
        if "enabled" in payload:
            self.set_enabled(payload["enabled"])
            self.source = "ui"
        error = None
        if "startup_preference" in payload:
            try:
                if self.status()["preference_error"]:
                    raise ValueError("启动配置异常")
                security = self.security()
                with DataDirectoryLock(security.config_dir):
                    private_write(security.config_dir / "runtime.json", {"schema_version": 1, "workspace_id": security.workspace_id, "startup_enabled": payload["startup_preference"]})
            except (OSError, ValueError, AgentError):
                error = "启动偏好保存失败；当前运行状态请见下方，可重新查询后重试保存"
        result = {"operation_id": request_id, "status": self.status(), "preference_error": error}
        self.operations[request_id] = (signature, result)
        return result

    def relocated(self, repository, migrate):
        other = AgentRuntime(repository, self.host, self.port, self.base)
        if migrate:
            other.source = self.source
            enabled = bool(getattr(self.repository, "agent_service", None))
        else:
            enabled = startup_enabled(repository.root, self.base)
        if enabled:
            other.set_enabled(True)
        repository.agent_runtime = other
        return other
