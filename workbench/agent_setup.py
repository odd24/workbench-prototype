"""Read-only local MCP setup instructions, without modifying Codex configuration."""

import re
import hashlib
import shutil
import sys
import os
from pathlib import Path

from .agent_security import AgentError, read_json


def powershell_quote(value):
    # PowerShell single-quoted literals do not expand $, backticks or newlines.
    if any(ord(character) < 32 for character in str(value)):
        raise ValueError("配置路径包含无效控制字符")
    return "'" + str(value).replace("'", "''") + "'"


def cmd_quote(value):
    value = str(value)
    if any(ord(character) < 32 or character in '"%!' for character in value):
        raise ValueError("路径含 CMD 无法安全复制的引号、百分号或感叹号，请选择 PowerShell")
    return '"' + value + '"'


def detect_codex():
    found = shutil.which("codex")
    if found:
        return str(Path(found).resolve())
    # Desktop installations are versioned and may not be on the server PATH.
    # Inspect only the current user's known installation root, not arbitrary files.
    local = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local:
        root = Path(local) / "OpenAI" / "Codex" / "bin"
        try:
            candidates = [path for path in root.glob("*/codex.exe") if path.is_file() and path.resolve().is_relative_to(root.resolve())]
            if candidates:
                return str(max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path))).resolve())
        except OSError:
            pass
    return None


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
    if not isinstance(config, dict) or config.get("schema_version") not in (1, 2) or config.get("workspace_id") != security.workspace_id or config.get("client_id") != client_id or hashlib.sha256(str(config.get("token", "")).encode()).hexdigest() != client["token_hash"]:
        raise AgentError("invalid_configuration", "客户端配置与空间不一致", 503)
    bridge = Path(__file__).resolve().parent.parent / "agent_bridge.py"
    executable = str(Path(sys.executable).resolve())
    codex = detect_codex()
    name = "workbench"
    arguments = [executable, str(bridge), "--config", str(config_path)]
    setup = {"client_id": client_id, "workspace_id": security.workspace_id, "default_name": name,
            "codex_executable": codex, "python_executable": executable, "python_version": sys.version.split()[0],
            "bridge_exists": bridge.is_file(), "configuration_origin": config.get("base_url"), "origin_matches": config.get("base_url") == origin,
            "command": executable, "args": arguments[1:],
            "instructions": "先检查同名 MCP 登记，避免覆盖其他工作空间；执行后重启 Codex 并开启新聊天，调用 capabilities/项目/分类进行只读验证。",
            "reference": "https://learn.chatgpt.com/docs/extend/mcp"}
    return command_variants(setup, name)


def registration_command(setup, name, terminal="powershell"):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("MCP 名称须以英文字母开头，仅含字母、数字、下划线或连字符，最多 64 字符")
    if terminal not in {"cmd", "powershell"}:
        raise ValueError("请选择 CMD 或 PowerShell 终端")
    quote = cmd_quote if terminal == "cmd" else powershell_quote
    prefix = "" if terminal == "cmd" else "& "
    return prefix + quote(setup["codex_executable"] or "codex") + " mcp add " + quote(name) + " -- " + " ".join(quote(value) for value in [setup["command"], *setup["args"]])


def command_variants(setup, name):
    setup["powershell_command"] = registration_command(setup, name)
    try:
        setup["cmd_command"] = registration_command(setup, name, "cmd")
        setup["cmd_error"] = None
    except ValueError as error:
        setup["cmd_command"] = None
        setup["cmd_error"] = str(error)
    setup["default_terminal"] = "cmd" if os.name == "nt" and setup["cmd_command"] else "powershell"
    return setup
