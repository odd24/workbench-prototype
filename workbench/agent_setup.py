"""Read-only local MCP setup instructions, without modifying Codex configuration."""

import re
import hashlib
import shutil
import sys
from pathlib import Path

from .agent_security import AgentError, read_json


def powershell_quote(value):
    # PowerShell single-quoted literals do not expand $, backticks or newlines.
    if any(ord(character) < 32 for character in str(value)):
        raise ValueError("配置路径包含无效控制字符")
    return "'" + str(value).replace("'", "''") + "'"


def setup_instructions(security, client_id, origin):
    client = security.clients().get(client_id)
    if not client or not client.get("enabled"):
        raise AgentError("not_found", "客户端不存在或已撤销", 404)
    if client_id in security.manager().blocked_clients():
        raise AgentError("management_recovery_required", "客户端有未决凭据操作，请先恢复", 503)
    # UUID validation prevents public identifiers from being used as paths.
    config_path = security.manager()._config(client_id)
    try:
        config = read_json(config_path)
    except (OSError, ValueError):
        raise AgentError("invalid_configuration", "客户端配置缺失或损坏，请核查备份或新建客户端", 503) from None
    if not isinstance(config, dict) or config.get("schema_version") != 1 or config.get("workspace_id") != security.workspace_id or config.get("client_id") != client_id or hashlib.sha256(str(config.get("token", "")).encode()).hexdigest() != client["token_hash"]:
        raise AgentError("invalid_configuration", "客户端配置与空间不一致", 503)
    bridge = Path(__file__).resolve().parent.parent / "agent_bridge.py"
    executable = str(Path(sys.executable).resolve())
    codex = shutil.which("codex")
    name = "workbench"
    arguments = [executable, str(bridge), "--config", str(config_path)]
    command = "& " + powershell_quote(codex or "codex") + " mcp add " + powershell_quote(name) + " -- " + " ".join(powershell_quote(value) for value in arguments)
    return {"client_id": client_id, "workspace_id": security.workspace_id, "default_name": name,
            "codex_executable": codex, "python_executable": executable, "python_version": sys.version.split()[0],
            "bridge_exists": bridge.is_file(), "configuration_origin": config.get("base_url"), "origin_matches": config.get("base_url") == origin,
            "command": executable, "args": arguments[1:], "powershell_command": command,
            "instructions": "先检查同名 MCP 登记，避免覆盖其他工作空间；执行后重启 Codex 并开启新聊天，调用 capabilities/项目/分类进行只读验证。",
            "reference": "https://learn.chatgpt.com/docs/extend/mcp"}


def registration_command(setup, name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("MCP 名称须以英文字母开头，仅含字母、数字、下划线或连字符，最多 64 字符")
    return "& " + powershell_quote(setup["codex_executable"] or "codex") + " mcp add " + powershell_quote(name) + " -- " + " ".join(powershell_quote(value) for value in [setup["command"], *setup["args"]])
