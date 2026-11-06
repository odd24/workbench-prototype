"""Bounded UTF-8 MCP stdio transport over the local Agent HTTP API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .agent_tools import AGENT_RULES, TOOLS, validate


PROTOCOL_VERSION = "2025-11-25"
MAX_MESSAGE_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class LocalAgentClient:
    def __init__(self, config_file):
        self.config_file = Path(config_file).resolve()
        if self.config_file.is_relative_to(Path(__file__).resolve().parent.parent):
            raise ValueError("凭据配置必须在仓库外")
        config = self.read_config()
        self.identity = (config["workspace_id"], config["client_id"])
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def read_config(self):
        if self.config_file.stat().st_size > 16384:
            raise ValueError("配置文件过大")
        config = json.loads(self.config_file.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or config.get("schema_version") not in (1, 2):
            raise ValueError("配置格式不受支持")
        if not isinstance(config.get("base_url"), str):
            raise ValueError("配置地址无效")
        parsed = urlsplit(config["base_url"])
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or not 1 <= (parsed.port if parsed.port is not None else 80) <= 65535:
            raise ValueError("只允许配置本机 HTTP origin")
        for key in ("workspace_id", "client_id"):
            if not isinstance(config.get(key), str) or str(uuid.UUID(config[key])) != config[key]:
                raise ValueError("配置身份无效")
        if not isinstance(config.get("token"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{20,512}", config["token"]):
            raise ValueError("配置令牌无效")
        if hasattr(self, "identity") and self.identity != (config["workspace_id"], config["client_id"]):
            raise ValueError("配置身份已变化，请重新连接")
        return config

    def call(self, spec, arguments):
        try:
            config = self.read_config()  # Token rotation takes effect without restarting stdio.
            path_keys = re.findall(r"\{([^}]+)\}", spec["path"])
            route = spec["path"].format_map({key: quote(str(arguments[key]), safe="") for key in path_keys})
            params = {key: value for key, value in arguments.items() if key not in path_keys}
            origin = config["base_url"].rstrip("/")
            parsed_origin = urlsplit(origin)
            if parsed_origin.hostname == "localhost":
                origin = f"http://127.0.0.1:{parsed_origin.port or 80}"
            url = origin + "/api/agent/v1/" + route
            data = None
            if spec["method"] == "GET":
                if params:
                    url += "?" + urlencode(params)
            else:
                data = json.dumps(params, ensure_ascii=False).encode("utf-8")
            request = Request(url, data=data, method=spec["method"], headers={"Authorization": "Bearer " + config["token"],
                              "X-Workbench-Workspace": config["workspace_id"], "Content-Type": "application/json"})
            diagnostic_nonce = os.environ.get("WORKBENCH_DIAGNOSTIC_NONCE", "")
            if re.fullmatch(r"wbdiag-[A-Za-z0-9_-]{32,100}", diagnostic_nonce):
                request.add_header("X-Workbench-Diagnostic", diagnostic_nonce)
            try:
                response = self.opener.open(request, timeout=10)
            except HTTPError as error:
                response = error
            with response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("响应超过限制")
                result = json.loads(body.decode("utf-8"), parse_constant=reject_constant)
                if 300 <= response.status < 400:
                    raise ValueError("不允许 HTTP 重定向")
                if not isinstance(result, dict):
                    raise ValueError("响应格式无效")
                if response.status >= 400:
                    # Only return the stable service error fields, never arbitrary HTML/headers.
                    if not {"code", "message", "retryable", "details", "request_id"} <= result.keys():
                        raise ValueError("响应错误格式无效")
                    return True, {key: result[key] for key in ("code", "message", "retryable", "details", "request_id")}
                return False, result
        except (URLError, TimeoutError, ConnectionError, OSError):
            return True, {"code": "service_unavailable", "message": "无法连接本机工作台，请检查服务、端口和配置；提交失败先查询原提案", "retryable": True, "details": {}, "request_id": None}
        except (ValueError, TypeError, KeyError):
            return True, {"code": "invalid_connection", "message": "配置身份、响应或本机连接无效，请检查配置并重新连接", "retryable": False, "details": {}, "request_id": None}


class MCPServer:
    def __init__(self, client):
        self.client = client
        self.initialized = False
        self.ready = False

    def handle(self, message):
        request_id = message.get("id") if isinstance(message, dict) else None
        valid_id = type(request_id) in {int, str} or request_id is None
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str) or not valid_id:
            return self.error(None, -32600, "JSON-RPC 请求无效")
        method, params = message["method"], message.get("params", {})
        notification = "id" not in message
        if notification:
            if method == "notifications/initialized" and self.initialized:
                self.ready = True
            # Cancellation/EOF never undoes an accepted business commit.
            return None
        try:
            if not isinstance(params, dict):
                raise ValueError("参数必须为对象")
            if method == "ping":
                result = {}
            elif method == "initialize":
                if self.initialized or not isinstance(params.get("protocolVersion"), str) or not isinstance(params.get("clientInfo"), dict) or not isinstance(params.get("capabilities"), dict) or not all(isinstance(params.get("clientInfo", {}).get(key), str) and params["clientInfo"][key] for key in ("name", "version")):
                    raise ValueError("初始化参数或顺序无效")
                self.initialized = True
                result = {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}},
                          "serverInfo": {"name": "workbench-agent", "version": "1.0.0"}, "instructions": AGENT_RULES}
            elif not self.ready:
                return self.error(request_id, -32002, "请先完成 MCP 初始化")
            elif method == "tools/list":
                if set(params) - {"_meta"}:
                    raise ValueError("此工具目录不需要分页参数")
                result = {"tools": [{key: value for key, value in spec.items() if key not in {"path", "method"}} for spec in TOOLS]}
            elif method == "tools/call":
                if set(params) - {"name", "arguments", "_meta"}:
                    raise ValueError("工具调用参数无效")
                spec = next((item for item in TOOLS if item["name"] == params.get("name")), None)
                if not spec:
                    raise ValueError("工具不存在")
                arguments = params.get("arguments", {})
                validate(arguments, spec["inputSchema"])
                failed, payload = self.client.call(spec, arguments)
                result = {"isError": failed, "structuredContent": payload,
                          "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
            else:
                return self.error(request_id, -32601, "不支持此 MCP 方法")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except (ValueError, KeyError, TypeError):
            return self.error(request_id, -32602, "参数或调用顺序无效")
        except Exception:
            return self.error(request_id, -32603, "本机桥接处理失败")

    @staticmethod
    def error(request_id, code, message):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def run(self, source, output):
        while True:
            message = None
            line = source.readline(MAX_MESSAGE_BYTES + 1)
            if not line:
                return
            if len(line) > MAX_MESSAGE_BYTES:
                while line and not line.endswith(b"\n"):
                    line = source.readline(MAX_MESSAGE_BYTES + 1)
                response = self.error(None, -32600, "MCP 消息超过 1 MiB 限制")
            else:
                try:
                    message = json.loads(line.decode("utf-8"), parse_constant=reject_constant)
                    response = self.handle(message)
                except (ValueError, UnicodeError):
                    response = self.error(None, -32700, "JSON 消息无效")
            if response is not None:
                if os.environ.get("WORKBENCH_MCP_TRACE") == "1" and "error" in response:
                    method = message.get("method") if isinstance(message, dict) else None
                    fields = list(message.get("params", {})) if isinstance(message, dict) and isinstance(message.get("params"), dict) else []
                    sys.stderr.write(json.dumps({"method": method, "parameter_fields": fields, "error_code": response["error"]["code"]}, ensure_ascii=True) + "\n")
                    sys.stderr.flush()
                output.write((json.dumps(response, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
                output.flush()


def reject_constant(_value):
    raise ValueError("JSON 常量无效")


def main(argv=None):
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="本机工作台通用 MCP stdio 桥接")
    parser.add_argument("--config", type=Path, required=True, help="工作台生成的外部客户端配置文件")
    args = parser.parse_args(argv)
    try:
        client = LocalAgentClient(args.config)
    except (OSError, ValueError, TypeError, KeyError):
        sys.stderr.write("工作台 MCP 配置无效或无法读取，请检查配置文件；不会输出令牌。\n")
        return 2
    try:
        MCPServer(client).run(sys.stdin.buffer, sys.stdout.buffer)
    except (BrokenPipeError, ConnectionResetError):
        pass
    return 0
