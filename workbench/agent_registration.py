"""Explicit local Codex registration, staged by the CLI and installed with receipts."""

import hashlib
import json
import os
import re
import tempfile
import tomllib
from pathlib import Path

from .agent_diagnostics import run_bounded
from .agent_management import client_version, credential_lock, digest
from .agent_security import AgentError, private_directory, private_write, read_json
from .agent_setup import registration_command, setup_instructions
from .persistence import atomic_write_bytes


MAX_CONFIG = 2 * 1024 * 1024


def codex_home():
    # Only the service user's environment is authoritative; no HTTP path input.
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()


def snapshot(path):
    if path.is_symlink() or path.exists() and not path.is_file():
        raise AgentError("invalid_configuration", "Codex 配置必须是普通文件", 409)
    if not path.exists():
        return None
    with path.open("rb") as stream:
        value = stream.read(MAX_CONFIG + 1)
    if len(value) > MAX_CONFIG:
        raise AgentError("invalid_configuration", "Codex 配置超过 2 MiB，请手工核查", 409)
    return value


def fingerprint(value):
    return hashlib.sha256(b"missing" if value is None else b"file:" + value).hexdigest()


def parse(value):
    try:
        result = tomllib.loads((value or b"").decode("utf-8"))
        if not isinstance(result.get("mcp_servers", {}), dict):
            raise ValueError()
        return result
    except (ValueError, UnicodeError):
        raise AgentError("invalid_configuration", "Codex config.toml 损坏或格式不支持，请先修复；原文件已保留", 409) from None


class CodexRegistration:
    def __init__(self, runtime, security):
        self.runtime, self.security = runtime, security
        self.home = codex_home()
        self.target = self.home / "config.toml"
        self.directory = security.config_dir / "codex-registrations"
        if self.directory.is_symlink():
            raise AgentError("invalid_configuration", "登记日志目录无效", 503)

    def checkpoint(self, stage):
        """Fault-injection seam; never supplied by an HTTP caller."""

    def _fields(self, payload, fields):
        if not isinstance(payload, dict) or set(payload) != fields:
            raise AgentError("invalid_request", "Codex 登记参数无效")
        if payload["workspace_id"] != self.security.workspace_id:
            raise AgentError("workspace_mismatch", "工作空间已变化，请重新检查", 409)

    def _context(self, client_id, name):
        setup = setup_instructions(self.security, client_id, self.runtime.origin)
        registration_command(setup, name)  # Reuse the validated public name contract.
        if not setup["codex_executable"] or os.name == "nt" and Path(setup["codex_executable"]).suffix.lower() != ".exe":
            raise AgentError("codex_missing", "未找到可直接运行的 Codex 程序，请使用高级手工接入或安装桌面版", 409)
        if not self.runtime.status()["enabled"] or not setup["origin_matches"] or not setup["bridge_exists"]:
            raise AgentError("configuration_unavailable", "请先开启接入、更新服务地址并检查桥接脚本", 409)
        before = snapshot(self.target)
        document = parse(before)
        desired = {"command": setup["command"], "args": setup["args"]}
        existing = document.get("mcp_servers", {}).get(name)
        state = "absent" if existing is None else "identical" if existing == desired else "conflict"
        version = digest({"target": str(self.target), "configuration": fingerprint(before), "desired": desired,
                          "client": client_version(self.security.clients()[client_id]), "name": name,
                          "codex": setup["codex_executable"], "workspace": self.security.workspace_id})
        # Existing config can contain secrets in any field, including command/args.
        summary = None if existing is None else {"transport": "stdio" if isinstance(existing, dict) and "command" in existing else "其他",
                  "argument_count": len(existing.get("args", [])) if isinstance(existing, dict) and isinstance(existing.get("args", []), list) else 0,
                  "fields": sorted(existing) if isinstance(existing, dict) else []}
        preview = {"workspace_id": self.security.workspace_id, "client_id": client_id, "name": name,
                   "config_path": str(self.target), "codex_executable": setup["codex_executable"], "state": state,
                   "expected_version": version, "existing": summary, "desired": desired}
        return preview, before, document, setup

    def preview(self, client_id, payload):
        self._fields(payload, {"workspace_id", "name"})
        with credential_lock(self.security.config_dir):
            return self._context(client_id, payload["name"])[0]

    def _operation(self, request_id):
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", request_id):
            raise AgentError("invalid_request", "登记请求标识无效")
        path = self.directory / hashlib.sha256(request_id.encode()).hexdigest()
        if path.is_symlink():
            raise AgentError("invalid_configuration", "登记日志路径无效", 503)
        return path

    def _read_receipt(self, operation):
        if operation.is_symlink() or not operation.resolve().is_relative_to(self.directory.resolve()):
            raise AgentError("invalid_configuration", "登记日志路径无效", 503)
        receipt_path = operation / "receipt.json"
        if receipt_path.is_symlink():
            raise AgentError("invalid_configuration", "登记回执路径无效", 503)
        if not receipt_path.is_file():
            raise AgentError("not_found", "未找到已接受的登记操作，可重新检查后接入", 404)
        try:
            receipt = read_json(receipt_path)
        except (OSError, ValueError):
            raise AgentError("invalid_configuration", "登记回执损坏，请保留日志并核查备份", 503) from None
        fields = {"schema_version", "workspace_id", "request_id", "input_hash", "target", "client_id", "name", "before_exists", "before_hash", "after_hash", "state"}
        if (not isinstance(receipt, dict) or set(receipt) != fields or receipt.get("schema_version") != 1
                or receipt.get("workspace_id") != self.security.workspace_id or receipt.get("target") != str(self.target)
                or receipt.get("state") not in {"prepared", "completed", "not_applied", "recovery_required"}
                or type(receipt.get("before_exists")) is not bool
                or any(not isinstance(receipt.get(key), str) or not re.fullmatch(r"[a-f0-9]{64}", receipt[key]) for key in ("input_hash", "before_hash", "after_hash"))
                or not isinstance(receipt.get("request_id"), str) or hashlib.sha256(receipt["request_id"].encode()).hexdigest() != operation.name
                or not isinstance(receipt.get("client_id"), str) or not isinstance(receipt.get("name"), str)):
            raise AgentError("invalid_configuration", "登记回执与当前目标不一致，请按维护说明核查", 409)
        return receipt

    def _result(self, operation, receipt):
        current = fingerprint(snapshot(self.target))
        if receipt["state"] == "prepared":
            receipt["state"] = "completed" if current == receipt["after_hash"] else "not_applied" if current == receipt["before_hash"] else "recovery_required"
            private_write(operation / "receipt.json", receipt)
        return {"request_id": receipt["request_id"], "client_id": receipt["client_id"], "name": receipt["name"],
                "state": receipt["state"], "config_path": str(self.target), "backup_path": str(operation / "before.toml") if receipt["before_exists"] else None,
                "registered": receipt["state"] == "completed", "configuration_unchanged": current == receipt["after_hash"]}

    def get(self, request_id):
        operation = self._operation(request_id)
        # Query never replays a write to Codex, even following a crash.
        with credential_lock(self.security.config_dir):
            return self._result(operation, self._read_receipt(operation))

    def register(self, client_id, payload):
        self._fields(payload, {"workspace_id", "name", "expected_version", "replace_existing", "request_id"})
        if type(payload["replace_existing"]) is not bool or not isinstance(payload["expected_version"], str) or not re.fullmatch(r"[a-f0-9]{64}", payload["expected_version"]):
            raise AgentError("invalid_request", "请先检查登记配置并明确选择是否替换")
        operation = self._operation(payload["request_id"])
        input_hash = digest({**payload, "client_id": client_id})
        with credential_lock(self.security.config_dir):
            if (operation / "receipt.json").exists():
                receipt = self._read_receipt(operation)
                if receipt["input_hash"] != input_hash:
                    raise AgentError("request_conflict", "请求标识已用于其他登记内容", 409)
                return self._result(operation, receipt)
            preview, before, document, setup = self._context(client_id, payload["name"])
            if preview["expected_version"] != payload["expected_version"]:
                raise AgentError("version_conflict", "配置或授权已变化，请重新检查后确认", 409)
            if preview["state"] == "conflict" and not payload["replace_existing"]:
                raise AgentError("registration_conflict", "同名登记不同，请改名或明确选择替换", 409)
            private_directory(self.directory)
            if not self.home.exists():
                private_directory(self.home)
            # A target-wide lock also serializes different workspaces/processes.
            with credential_lock(self.home):
                if snapshot(self.target) != before:
                    raise AgentError("version_conflict", "Codex 配置已变化，请重新检查", 409)
                after = before
                if preview["state"] != "identical":
                    try:
                        with tempfile.TemporaryDirectory(prefix="stage-", dir=self.directory) as stage:
                            stage_path = Path(stage) / "config.toml"
                            if before is not None:
                                atomic_write_bytes(stage_path, before)
                            run_bounded([setup["codex_executable"], "mcp", "add", payload["name"], "--", setup["command"], *setup["args"]],
                                        env={**os.environ, "CODEX_HOME": stage}, timeout=8)
                            after = snapshot(stage_path)
                            changed = parse(after)
                            expected = {**document, "mcp_servers": {**document.get("mcp_servers", {}), payload["name"]: preview["desired"]}}
                            if after is None or changed != expected:
                                raise ValueError("unexpected CLI configuration")
                            verified = json.loads(run_bounded([setup["codex_executable"], "mcp", "get", payload["name"], "--json"],
                                                            env={**os.environ, "CODEX_HOME": stage}, timeout=3))
                            if not isinstance(verified, dict) or verified.get("enabled") is not True or not isinstance(verified.get("transport"), dict):
                                raise ValueError("CLI readback failed")
                            transport = verified["transport"]
                            if transport.get("type") != "stdio" or transport.get("command") != setup["command"] or transport.get("args") != setup["args"]:
                                raise ValueError("CLI readback differs")
                    except (OSError, ValueError, TimeoutError):
                        raise AgentError("registration_failed", "Codex 登记生成失败或超时，原配置未修改；可使用高级手工接入", 503) from None
                private_directory(operation)
                if before is not None:
                    atomic_write_bytes(operation / "before.toml", before)
                atomic_write_bytes(operation / "after.toml", after)
                receipt = {"schema_version": 1, "workspace_id": self.security.workspace_id, "request_id": payload["request_id"],
                           "input_hash": input_hash, "target": str(self.target), "client_id": client_id, "name": payload["name"],
                           "before_exists": before is not None, "before_hash": fingerprint(before), "after_hash": fingerprint(after), "state": "prepared"}
                private_write(operation / "receipt.json", receipt)
                self.checkpoint("prepared")
                if snapshot(self.target) != before:
                    receipt["state"] = "recovery_required"
                    private_write(operation / "receipt.json", receipt)
                    raise AgentError("version_conflict", "写入前发现外部修改，请先查询上次登记结果", 409)
                if after != before:
                    atomic_write_bytes(self.target, after)
                self.checkpoint("installed")
                if snapshot(self.target) != after:
                    raise AgentError("registration_uncertain", "登记后配置发生变化，请查询结果并核查备份", 503)
                receipt["state"] = "completed"
                private_write(operation / "receipt.json", receipt)
                self.checkpoint("completed")
                return self._result(operation, receipt)
