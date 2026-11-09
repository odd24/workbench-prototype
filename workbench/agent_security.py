"""Local client credentials and workspace-scoped Agent authorization."""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import re
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


LEGACY_KINDS = ("issue", "document")
AGENT_KINDS = (*LEGACY_KINDS, "todo", "info")


CONFIRMATION_MODES = ("agent_attested", "local_web")

# Configuration vocabulary only. No new business handler is implemented here.
CAPABILITY_SPECS = {
    "attachments.read": (("read",), ("project", "item", "document_category")),
    "attachments.write": (("create",), ("project", "item", "document_category")),
    "concept_maps.read": (("read",), ("project", "concept_map", "concept_map_category")),
    "concept_maps.write": (("create", "update"), ("project", "concept_map", "concept_map_category")),
    "items.delete": (("delete",), ("project", "item", "document_category", "concept_map", "concept_map_category")),
    "projects.create": (("create",), ("workspace",)),
    "projects.delete": (("delete",), ("project",)),
    "categories.write": (("create", "rename", "delete", "reorder"), ("document_category", "concept_map_category", "project_attachment_category")),
    "workflows.write": (("create", "copy", "rename", "add_status", "rename_status", "delete_status", "reorder", "switch"), ("workflow_template", "project")),
}
WEB_CAPABILITIES = {"items.delete", "projects.create", "projects.delete", "categories.write", "workflows.write"}
RESOURCE_FIELDS = {
    "workspace": (), "project": ("id",), "item": ("kind", "id"),
    "document_category": ("name",), "concept_map": ("id",),
    "concept_map_category": ("name",), "project_attachment_category": ("project_id", "name"),
    "workflow_template": ("id",),
}


def normalize_capability_grants(value):
    """Strict dormant configuration; never an executable permission."""
    if not isinstance(value, dict) or set(value) != {"schema_version", "grants"} or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("新能力授权格式无效")
    grants = value["grants"]
    if not isinstance(grants, list) or len(grants) > 64:
        raise ValueError("新能力授权最多64项")
    result, seen = [], set()
    for grant in grants:
        if not isinstance(grant, dict) or set(grant) != {"capability", "operations", "resources", "minimum_confirmation_mode"}:
            raise ValueError("新能力授权字段无效")
        capability = grant["capability"]
        if not isinstance(capability, str) or capability not in CAPABILITY_SPECS:
            raise ValueError("能力不支持配置；具体文件授权须等待文件能力开放")
        operations, types = CAPABILITY_SPECS[capability]
        requested = grant["operations"]
        mode = grant["minimum_confirmation_mode"]
        if not isinstance(requested, list) or not requested or any(not isinstance(op, str) or op not in operations for op in requested) or len(set(requested)) != len(requested):
            raise ValueError("能力操作无效")
        if not isinstance(mode, str) or mode not in CONFIRMATION_MODES or capability in WEB_CAPABILITIES and mode != "local_web":
            raise ValueError("能力最低确认方式无效")
        resources = grant["resources"]
        if not isinstance(resources, list) or not 1 <= len(resources) <= 64:
            raise ValueError("请明确选择能力资源（最多64项）")
        normalized, resource_seen = [], set()
        for resource in resources:
            if not isinstance(resource, dict) or not isinstance(resource.get("type"), str) or resource["type"] not in types:
                raise ValueError("能力资源类型无效")
            resource_type = resource["type"]
            if set(resource) != {"type", *RESOURCE_FIELDS[resource_type]}:
                raise ValueError("能力资源字段无效")
            for key, item in resource.items():
                if not isinstance(item, str) or not item.strip() or item != item.strip() or len(item) > 200 or "*" in item or re.search(r"[\x00-\x1f\\/]", item):
                    raise ValueError("能力资源标识无效")
                if key in {"id", "project_id"} and (item in {".", ".."} or ":" in item):
                    raise ValueError("能力资源不是路径")
            if resource_type == "item" and resource["kind"] not in AGENT_KINDS:
                raise ValueError("条目资源类型无效")
            signature = json.dumps(resource, sort_keys=True, ensure_ascii=False)
            if signature in resource_seen:
                raise ValueError("能力资源重复")
            resource_seen.add(signature)
            normalized.append(dict(resource))
        cleaned = {**grant, "operations": sorted(requested), "resources": sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))}
        signature = json.dumps(cleaned, sort_keys=True, ensure_ascii=False)
        if signature in seen:
            raise ValueError("能力授权重复")
        seen.add(signature)
        result.append(cleaned)
    return {"schema_version": 1, "grants": sorted(result, key=lambda item: json.dumps(item, sort_keys=True))}


def client_capability_grants(client):
    try:
        value = normalize_capability_grants(client.get("capability_grants", {"schema_version": 1, "grants": []}))
        if "capability_grants" in client and (client.get("authorization_schema_version") not in (3, 4) or client.get("capability_grant_state") != "dormant"):
            raise ValueError("授权必须休眠")
        return value
    except ValueError:
        raise AgentError("invalid_configuration", "客户端新能力授权无效", 503) from None


def client_confirmation_mode(client):
    mode = client.get("minimum_confirmation_mode", "agent_attested")
    if mode not in CONFIRMATION_MODES:
        raise AgentError("invalid_configuration", "客户端确认策略无效", 503)
    return mode


def client_kinds(client):
    kinds = client.get("kinds", list(LEGACY_KINDS))
    version = client.get("authorization_schema_version", 1)
    if type(version) is not int or version not in (1, 2, 3, 4):
        raise AgentError("unsupported_schema", "客户端授权版本不受支持", 503)
    if not isinstance(kinds, list) or (not kinds and version not in (3, 4)) or any(not isinstance(kind, str) or kind not in AGENT_KINDS for kind in kinds):
        raise AgentError("invalid_configuration", "客户端类型授权无效", 503)
    client_capability_grants(client)
    client_file_ids(client)
    return list(dict.fromkeys(kinds))


def client_file_ids(client):
    values = client.get("active_file_ids", [])
    try:
        if "active_file_ids" in client and client.get("authorization_schema_version") != 4:
            raise ValueError()
        if not isinstance(values, list) or len(values) > 100 or len(set(values)) != len(values) or any(not isinstance(value, str) or str(uuid.UUID(value)) != value for value in values):
            raise ValueError()
        return values.copy()
    except (ValueError, TypeError, AttributeError):
        raise AgentError("invalid_configuration", "客户端文件授权引用无效", 503) from None


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
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") not in (1, 2, 3) or value.get("workspace_id") != self.workspace_id or not isinstance(value.get("clients"), dict):
            raise AgentError("unsupported_schema", "客户端配置格式或工作空间不匹配", 503)
        return value["clients"]

    def registry_version(self):
        self.clients()  # Validate before any overwrite.
        return read_json(self.registry)["schema_version"] if self.registry.exists() else 1

    def save_clients(self, clients, minimum_schema=1):
        version = max(self.registry_version(), minimum_schema)
        if any(client.get("authorization_schema_version") == 3 for client in clients.values()):
            version = max(version, 2)
        if any(client.get("authorization_schema_version") == 4 for client in clients.values()):
            version = 3
        private_write(self.registry, {"schema_version": version, "workspace_id": self.workspace_id, "clients": clients})

    @staticmethod
    def validate_client(name, scopes, project_ids, categories, kinds=None, minimum_confirmation_mode="agent_attested", capability_grants=None, authorization_schema_version=2):
        if minimum_confirmation_mode not in CONFIRMATION_MODES:
            raise ValueError("客户端确认策略无效")
        try:
            client_kinds({"kinds": list(LEGACY_KINDS) if kinds is None else kinds, "authorization_schema_version": 3 if capability_grants is not None else authorization_schema_version})
        except AgentError:
            raise ValueError("客户端类型授权无效") from None
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("客户端名称无效")
        if not isinstance(scopes, list) or not scopes or any(not isinstance(scope, str) for scope in scopes) or set(scopes) - {"read", "propose", "commit"}:
            raise ValueError("客户端权限无效")
        for values in (project_ids, categories):
            if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
                raise ValueError("范围必须是非空字符串列表；空列表表示不授权")
        if capability_grants is not None:
            normalize_capability_grants(capability_grants)

    @staticmethod
    def validate_origin(base_url):
        from urllib.parse import urlsplit
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or not 1 <= (parsed.port if parsed.port is not None else 80) <= 65535:
            raise ValueError("Agent 地址必须是本机 HTTP origin")

    def manager(self):
        from .agent_management import CredentialManager
        return CredentialManager(self)

    def add_client(self, name, scopes, project_ids, categories, base_url, request_id=None, kinds=None, minimum_confirmation_mode="agent_attested", capability_grants=None):
        return self.manager().run("create", {"minimum_confirmation_mode": minimum_confirmation_mode, **({"kinds": kinds} if kinds is not None else {}), **({"capability_grants": capability_grants} if capability_grants is not None else {}), "name": name, "scopes": scopes, "project_ids": project_ids, "categories": categories, "base_url": base_url}, request_id=request_id)

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
                client_kinds(client)
                return client
        raise AgentError("unauthenticated", "Agent 凭据已失效或被撤销", 401)


def require_scope(client, scope):
    if scope not in client.get("scopes", []):
        raise AgentError("forbidden", "此客户端未获授权执行该操作", 403)


def allows(client, item):
    kind = item.get("type")
    kinds = client_kinds(client)
    if kind is not None and kind not in kinds:
        return False
    if kind is None and not set(kinds) & {"issue", "todo", "info"}:
        return False
    key = "categories" if item.get("type") == "document" else "project_ids"
    value = item.get("category", "未分类") if key == "categories" else item.get("project_id")
    values = client.get(key, [])
    return "*" in values or value in values
