"""Bounded, read-only MCP diagnostics. No user configuration or model turns."""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone

from .agent_security import AgentError
from .agent_setup import setup_instructions
from .agent_tools import TOOLS
from .mcp_stdio import PROTOCOL_VERSION


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def run_bounded(command, data=b"", env=None, timeout=8, limit=128 * 1024):
    """Fixed callers only; cap each pipe while reading, and reap on all exits."""
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=env, bufsize=0, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    buffers = [bytearray(), bytearray()]
    exceeded = threading.Event()
    def read(stream, target):
        try:
            while chunk := stream.read(4096):
                if len(target) + len(chunk) > limit:
                    exceeded.set()
                    process.kill()
                    break
                target.extend(chunk)
        except OSError:
            pass
    readers = [threading.Thread(target=read, args=(stream, buffers[index]), daemon=True) for index, stream in enumerate((process.stdout, process.stderr))]
    for reader in readers:
        reader.start()
    try:
        if len(data) > 4096:
            raise ValueError("诊断输入过大")
        if data:
            process.stdin.write(data)
        process.stdin.close()
        process.wait(timeout=timeout)
        for reader in readers:
            reader.join(timeout=1)
        if exceeded.is_set():
            raise ValueError("诊断输出超过限制")
        if any(reader.is_alive() for reader in readers):
            raise TimeoutError("诊断输出未结束")
        if process.returncode:
            raise ValueError("诊断程序退出失败")
        return bytes(buffers[0])
    except subprocess.TimeoutExpired:
        raise TimeoutError("诊断程序超时") from None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)
        for reader in readers:
            reader.join(timeout=1)
        for stream in (process.stdin, process.stdout, process.stderr):
            if not stream.closed:
                stream.close()


def probe_mcp(setup, nonce):
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "workbench-diagnostic", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "workbench_capabilities", "arguments": {}}},
    ]
    data = b"".join((json.dumps(message) + "\n").encode() for message in messages)
    output = run_bounded([setup["command"], *setup["args"]], data,
                         env={**os.environ, "WORKBENCH_DIAGNOSTIC_NONCE": nonce}, timeout=8)
    responses = [json.loads(line) for line in output.decode("utf-8").splitlines() if line.strip()]
    if len(responses) != 3 or any(not isinstance(value, dict) or value.get("jsonrpc") != "2.0" or "error" in value for value in responses):
        raise ValueError("MCP 响应格式无效")
    mapped = {value["id"]: value["result"] for value in responses}
    if set(mapped) != {1, 2, 3} or mapped[1].get("protocolVersion") != PROTOCOL_VERSION:
        raise ValueError("MCP 握手版本无效")
    names = {tool["name"] for tool in mapped[2]["tools"]}
    if names != {tool["name"] for tool in TOOLS}:
        raise ValueError("MCP 工具目录不完整")
    call = mapped[3]
    content = call.get("structuredContent", {})
    return {"protocol": PROTOCOL_VERSION, "tool_count": len(names), "read_ok": not call.get("isError") and content.get("workspace_id") == setup["workspace_id"],
            "error_code": content.get("code") if call.get("isError") else None}


class AgentDiagnostics:
    def __init__(self, runtime):
        self.runtime = runtime
        self.lock = threading.RLock()
        self.jobs = {}
        self.requests = {}
        self.nonces = {}
        self.observations = {}

    def observe(self, client_id, nonce):
        with self.lock:
            # The prefix alone is not proof: only a server-issued live nonce is.
            expected = self.nonces.get(nonce) if nonce else None
            diagnostic = bool(expected and expected[0] == client_id and time.monotonic() < expected[1])
            key = "last_diagnostic_request_at" if diagnostic else "last_client_request_at"
            value = self.observations.setdefault(client_id, {})
            value[key] = timestamp()
            value["source_verified"] = False

    def observed(self, client_id):
        with self.lock:
            return dict(self.observations.get(client_id, {}))

    def get(self, operation_id):
        with self.lock:
            value = self.jobs.get(operation_id)
            if not value:
                raise AgentError("not_found", "诊断任务不存在，服务重启后请重新检查", 404)
            return json.loads(json.dumps(value))

    def start(self, client_id, request_id):
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", request_id):
            raise ValueError("诊断请求标识无效")
        if not self.runtime.status()["workspace_id"]:
            raise AgentError("not_initialized", "请先开启接入以初始化当前空间", 409)
        security = self.runtime.security()
        if client_id not in security.clients():
            raise AgentError("not_found", "客户端不存在", 404)
        with self.lock:
            self.nonces = {key: value for key, value in self.nonces.items() if value[1] > time.monotonic()}
            if request_id in self.requests:
                operation_id, original_client = self.requests[request_id]
                if original_client != client_id:
                    raise AgentError("request_conflict", "诊断请求标识已用于其他客户端", 409)
                return self.get(operation_id)
            running = next((value for value in self.jobs.values() if value["client_id"] == client_id and value["state"] == "running"), None)
            if running:
                return self.get(running["operation_id"])
            if len(self.jobs) >= 50:
                oldest = next((key for key, value in self.jobs.items() if value["state"] != "running"), None)
                if oldest is None:
                    raise AgentError("diagnostic_busy", "诊断任务过多，请稍后重试", 429, True)
                del self.jobs[oldest]
                self.requests = {key: value for key, value in self.requests.items() if value[0] != oldest}
            operation_id = str(uuid.uuid4())
            self.jobs[operation_id] = {"operation_id": operation_id, "client_id": client_id, "workspace_id": security.workspace_id, "state": "running", "started_at": timestamp(), "steps": []}
            self.requests[request_id] = (operation_id, client_id)
            threading.Thread(target=self._run, args=(operation_id, security), daemon=True).start()
            return self.get(operation_id)

    def _run(self, operation_id, security):
        client_id = self.get(operation_id)["client_id"]
        steps = []
        nonce = "wbdiag-" + secrets.token_urlsafe(32)
        def step(name, state, message):
            steps.append({"name": name, "state": state, "message": message, "checked_at": timestamp()})
        try:
            if not self.runtime.status()["enabled"]:
                step("service", "failed", "Agent 接入已关闭，请先开启接入")
                return
            step("service", "passed", "当前工作台 Agent API 已开启")
            client = security.clients()[client_id]
            if not client.get("enabled") or client_id in security.manager().blocked_clients():
                step("authorization", "failed", "授权已撤销或需要恢复，请检查客户端状态")
                return
            step("authorization", "passed", "客户端授权有效")
            try:
                setup = setup_instructions(security, client_id, self.runtime.origin)
                if not setup["origin_matches"]:
                    step("configuration", "failed", "配置服务地址与当前服务不同，请先更新服务地址")
                    return
            except (AgentError, OSError, ValueError, KeyError, TypeError):
                step("configuration", "failed", "凭据配置缺失、损坏或身份不一致，请核查配置")
                return
            step("configuration", "passed", "配置身份、凭据和当前服务地址一致")
            step("python", "passed" if setup["bridge_exists"] else "failed", "Python " + setup["python_version"] + ("，桥接脚本已找到" if setup["bridge_exists"] else "，桥接脚本缺失"))
            if not setup["bridge_exists"]:
                return
            if setup["codex_executable"]:
                try:
                    version = run_bounded([setup["codex_executable"], "--version"], timeout=3).decode("utf-8").strip()
                    if not re.fullmatch(r"codex-cli [A-Za-z0-9.+_-]{1,80}", version):
                        raise ValueError("版本输出无效")
                    step("codex", "passed", version)
                except (OSError, ValueError, TimeoutError, UnicodeError):
                    step("codex", "warning", "Codex 版本检测失败，可核查安装或使用通用 MCP 指引")
            else:
                step("codex", "warning", "未在服务环境找到 Codex CLI，可手工检查安装；仍可验证通用桥接")
            with self.lock:
                self.nonces[nonce] = (client_id, time.monotonic() + 15)
            try:
                result = probe_mcp(setup, nonce)
            except TimeoutError:
                step("mcp", "failed", "MCP 检查超时，请核查服务、解释器和端口后重试")
                return
            except (OSError, ValueError, KeyError, TypeError, UnicodeError):
                step("mcp", "failed", "MCP 检查失败：协议、工具目录或输出无效，请核查桥接配置")
                return
            step("mcp", "passed", f"MCP {result['protocol']}，发现 {result['tool_count']} 个工具；不代表当前聊天已接入")
            step("read", "passed" if result["read_ok"] else "failed", "自检 capabilities 只读请求成功" if result["read_ok"] else "自检只读请求失败，请核查最新权限与服务状态")
        except Exception:
            step("service", "failed", "诊断无法完成，请检查配置后重试；未修改业务内容")
        finally:
            names = {value["name"] for value in steps}
            for name in ("service", "authorization", "configuration", "python", "codex", "mcp", "read"):
                if name not in names:
                    step(name, "skipped", "前置检查未通过，本项未执行")
            with self.lock:
                self.nonces.pop(nonce, None)
                self.jobs[operation_id].update(state="completed", steps=steps, finished_at=timestamp())
