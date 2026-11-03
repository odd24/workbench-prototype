"""Local client credentials and workspace-scoped Agent authorization."""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import uuid
from pathlib import Path

from .persistence import atomic_write_json
from .write_coordinator import DataDirectoryLock


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
        if value.get("schema_version") != 1 or value.get("workspace_id") != self.workspace_id:
            raise AgentError("unsupported_schema", "客户端配置格式或工作空间不匹配", 503)
        return value["clients"]

    def save_clients(self, clients):
        private_write(self.registry, {"schema_version": 1, "workspace_id": self.workspace_id, "clients": clients})

    def add_client(self, name, scopes, project_ids, categories, base_url):
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("客户端名称无效")
        if not scopes or set(scopes) - {"read", "propose", "commit"}:
            raise ValueError("客户端权限无效")
        for values in (project_ids, categories):
            if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
                raise ValueError("范围必须是非空字符串列表；空列表表示不授权")
        from urllib.parse import urlsplit
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("Agent 地址必须是本机 HTTP origin")
        client_id, token = str(uuid.uuid4()), secrets.token_urlsafe(32)
        with DataDirectoryLock(self.config_dir):
            clients = self.clients()
            clients[client_id] = {"client_id": client_id, "name": name.strip(), "enabled": True,
                                  "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                                  "scopes": sorted(set(scopes)), "project_ids": project_ids, "categories": categories}
            config = {"schema_version": 1, "base_url": base_url.rstrip("/"), "workspace_id": self.workspace_id, "client_id": client_id, "token": token}
            private_write(self.config_dir / f"{client_id}.json", config)
            self.save_clients(clients)
        return {"client_id": client_id, "config_file": str(self.config_dir / f"{client_id}.json"), "workspace_id": self.workspace_id}

    def change_client(self, client_id, rotate=False):
        with DataDirectoryLock(self.config_dir):
            clients = self.clients()
            client = clients.get(client_id)
            if not client:
                raise ValueError("客户端不存在")
            if rotate:
                if not client.get("enabled"):
                    raise ValueError("已撤销客户端不能通过轮换重新启用，请新建客户端")
                token = secrets.token_urlsafe(32)
                config_path = self.config_dir / f"{client_id}.json"
                config = read_json(config_path)
                private_write(config_path, {**config, "token": token})
                client["token_hash"] = hashlib.sha256(token.encode()).hexdigest()
            else:
                client["enabled"] = False
            self.save_clients(clients)
        return {"client_id": client_id, "enabled": client["enabled"], "rotated": rotate}

    def authenticate(self, authorization, workspace_id):
        if not authorization or not authorization.startswith("Bearer "):
            raise AgentError("unauthenticated", "需要有效的 Agent 凭据", 401)
        if workspace_id != self.workspace_id:
            raise AgentError("workspace_mismatch", "工作空间标识不匹配，请检查客户端配置", 409)
        token_hash = hashlib.sha256(authorization[7:].encode()).hexdigest()
        for client in self.clients().values():
            if client.get("enabled") and hmac.compare_digest(client.get("token_hash", ""), token_hash):
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
