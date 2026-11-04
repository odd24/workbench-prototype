"""Local client credentials and workspace-scoped Agent authorization."""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import subprocess
import uuid
from pathlib import Path

from .persistence import atomic_write_json


class AgentError(Exception):
    def __init__(self, code, message, status=400, retryable=False, details=None):
        super().__init__(message)
        self.code, self.status, self.retryable = code, status, retryable
        self.details = details or {}

    def payload(self, request_id=None):
        return {"code": self.code, "message": str(self), "retryable": self.retryable,
                "details": self.details, "request_id": request_id}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def private_directory(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, check=True)
        sid = next(csv.reader([result.stdout.strip()]))[-1]
        if not sid.startswith("S-1-"):
            raise ValueError("无法确认当前用户权限")
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F"], capture_output=True, check=True)
    else:
        path.chmod(0o700)


def private_write(path, value):
    atomic_write_json(path, value)
    if os.name != "nt":
        path.chmod(0o600)


class AgentSecurity:
    def __init__(self, root: Path, config_dir: Path | None = None):
        self.root = root.resolve()
        workspace_path = self.root / ".agent" / "workspace.json"
        if workspace_path.parent.is_symlink() or workspace_path.is_symlink() or not workspace_path.resolve().is_relative_to(self.root):
            raise ValueError("Agent 状态目录不能使用符号链接")
        if not workspace_path.exists():
            atomic_write_json(workspace_path, {"schema_version": 1, "workspace_id": str(uuid.uuid4())})
        value = read_json(workspace_path)
        if value.get("schema_version") != 1:
            raise AgentError("unsupported_schema", "工作空间格式不受支持", 503)
        self.workspace_id = str(uuid.UUID(value["workspace_id"]))
        base = config_dir or Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "Workbench" / "agent"
        self.config_dir = (Path(base) / self.workspace_id).resolve()
        if self.config_dir.is_relative_to(self.root) or self.config_dir.is_relative_to(Path(__file__).resolve().parent.parent):
            raise ValueError("Agent 凭据目录必须位于仓库与业务数据目录外")
        private_directory(self.config_dir)
        self.registry = self.config_dir / "clients.json"

    def clients(self):
        if not self.registry.exists():
            return {}
        value = read_json(self.registry)
        if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("workspace_id") != self.workspace_id or not isinstance(value.get("clients"), dict):
            raise AgentError("unsupported_schema", "客户端配置格式或工作空间不匹配", 503)
        return value["clients"]

    def save_clients(self, clients):
        private_write(self.registry, {"schema_version": 1, "workspace_id": self.workspace_id, "clients": clients})

    @staticmethod
    def validate_client(name, scopes, project_ids, categories):
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("客户端名称无效")
        if not isinstance(scopes, list) or not scopes or any(not isinstance(scope, str) for scope in scopes) or set(scopes) - {"read", "propose", "commit"}:
            raise ValueError("客户端权限无效")
        for values in (project_ids, categories):
            if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
                raise ValueError("范围必须是非空字符串列表；空列表表示不授权")

    @staticmethod
    def validate_origin(base_url):
        from urllib.parse import urlsplit
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or not 1 <= (parsed.port if parsed.port is not None else 80) <= 65535:
            raise ValueError("Agent 地址必须是本机 HTTP origin")

    def manager(self):
        from .agent_management import CredentialManager
        return CredentialManager(self)

    def add_client(self, name, scopes, project_ids, categories, base_url, request_id=None):
        return self.manager().run("create", {"name": name, "scopes": scopes, "project_ids": project_ids, "categories": categories, "base_url": base_url}, request_id=request_id)

    def change_client(self, client_id, rotate=False, expected_version=None, request_id=None):
        return self.manager().run("rotate" if rotate else "revoke", {}, client_id, expected_version, request_id)

    def authenticate(self, authorization, workspace_id):
        if not authorization or not authorization.startswith("Bearer "):
            raise AgentError("unauthenticated", "需要有效的 Agent 凭据", 401)
        if workspace_id != self.workspace_id:
            raise AgentError("workspace_mismatch", "工作空间标识不匹配，请检查客户端配置", 409)
        token_hash = hashlib.sha256(authorization[7:].encode()).hexdigest()
        blocked = self.manager().blocked_clients()
        for client in self.clients().values():
            if client.get("enabled") and client.get("client_id") not in blocked and hmac.compare_digest(client.get("token_hash", ""), token_hash):
                return client
        raise AgentError("unauthenticated", "Agent 凭据已失效或被撤销", 401)


def require_scope(client, scope):
    if scope not in client.get("scopes", []):
        raise AgentError("forbidden", "此客户端未获授权执行该操作", 403)


def allows(client, item):
    key = "categories" if item.get("type") == "document" else "project_ids"
    value = item.get("category", "未分类") if key == "categories" else item.get("project_id")
    values = client.get(key, [])
    return "*" in values or value in values
