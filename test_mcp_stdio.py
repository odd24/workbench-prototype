import io
import json
import os
import queue
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from codex_agent_acceptance import LocalWorkbench, ROOT, RpcProcess
from workbench.agent_security import private_write, read_json
from workbench.agent_tools import TOOLS
from workbench.mcp_stdio import LocalAgentClient, MAX_MESSAGE_BYTES, MAX_RESPONSE_BYTES, MCPServer, PROTOCOL_VERSION


INITIALIZE = {"protocolVersion": PROTOCOL_VERSION, "clientInfo": {"name": "test-client", "version": "1"}, "capabilities": {}}


class StubClient:
    def __init__(self):
        self.calls = []

    def call(self, spec, arguments):
        self.calls.append((spec["name"], arguments))
        return False, {"value": "中文结构化结果"}


class MCPProtocolTests(unittest.TestCase):
    def setUp(self):
        self.client = StubClient()
        self.server = MCPServer(self.client)

    def call(self, method, params=None, request_id=1):
        return self.server.handle({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})

    def initialize(self):
        result = self.call("initialize", INITIALIZE)["result"]
        self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result

    def test_lifecycle_version_fallback_capabilities_and_notification_silence(self):
        self.assertEqual(self.call("tools/list")["error"]["code"], -32002)
        self.assertEqual(self.call("ping")["result"], {})
        result = self.call("initialize", {**INITIALIZE, "protocolVersion": "future-client-version"})["result"]
        self.assertEqual(result["protocolVersion"], PROTOCOL_VERSION)
        self.assertEqual(result["capabilities"], {"tools": {}})
        self.assertIn("完整预览", result["instructions"])
        for rule in ("关键原文摘录到正文代码块", "外部日志路径仅作来源补充", "确认已保存在工作台", "未取得日志原文须明确标注待补充"):
            self.assertIn(rule, result["instructions"])
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 2}}))
        self.assertIn("error", self.call("initialize", INITIALIZE))

    def test_tools_schemas_annotations_unknown_fields_and_business_results(self):
        self.initialize()
        tools = self.call("tools/list", {"_meta": {}})["result"]["tools"]
        self.assertEqual(len(tools), 22)
        self.assertEqual(len({item["name"] for item in tools}), 22)
        for name in ("workbench_capabilities", "workbench_prepare_proposal"):
            description = next(item["description"] for item in tools if item["name"] == name)
            self.assertIn("关键原文摘录到正文代码块", description)
            self.assertIn("外部日志路径仅作来源补充", description)
        self.assertTrue(all(item["inputSchema"]["additionalProperties"] is False for item in tools))
        self.assertFalse(next(item for item in tools if item["name"] == "workbench_preview_proposal")["annotations"]["readOnlyHint"])
        self.assertNotIn("path", tools[0])
        result = self.call("tools/call", {"name": "workbench_capabilities", "arguments": {}})["result"]
        self.assertEqual(result["structuredContent"], json.loads(result["content"][0]["text"]))
        self.assertFalse(result["isError"])
        for arguments in ({"unknown": "x"}, None, []):
            self.assertEqual(self.call("tools/call", {"name": "workbench_capabilities", "arguments": arguments})["error"]["code"], -32602)
        self.assertEqual(self.call("tools/call", {"name": "shell_execute"})["error"]["code"], -32602)
        self.assertEqual(self.call("resources/list")["error"]["code"], -32601)
        self.assertEqual(len(self.client.calls), 1)

    def test_invalid_json_utf8_oversize_and_non_request_shapes(self):
        messages = b'not-json\n\xff\n[]\n{"jsonrpc":"2.0","id":true,"method":"ping"}\n'
        messages += b'x' * (MAX_MESSAGE_BYTES + 2) + b'\n'
        messages += b'{"jsonrpc":"2.0","id":5,"method":"ping"}\n'
        output = io.BytesIO()
        with patch.dict(os.environ, {"WORKBENCH_MCP_TRACE": "1"}), patch("sys.stderr", new=io.StringIO()):
            self.server.run(io.BytesIO(messages), output)
        results = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([result["error"]["code"] for result in results[:-1]], [-32700, -32700, -32600, -32600, -32600])
        self.assertEqual(results[-1], {"jsonrpc": "2.0", "id": 5, "result": {}})


class MCPBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.workbench = LocalWorkbench(self.base / "data", self.base / "credentials")
        self.project = self.workbench.repository.create_project({"name": "MCP 桥接"})
        self.info = self.workbench.security.add_client("桥接测试", ["read", "propose", "commit"], ["*"], ["*"], self.workbench.base_url)
        self.config_file = Path(self.info["config_file"])
        self.config = read_json(self.config_file)
        self.rpc = None

    def tearDown(self):
        if self.rpc:
            self.rpc.close()
        self.workbench.close()
        self.temp.cleanup()

    def start_bridge(self):
        self.rpc = RpcProcess([sys.executable, str(ROOT / "agent_bridge.py"), "--config", str(self.config_file)], self.base,
                              {**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.rpc.call("initialize", INITIALIZE)
        self.rpc.notify("notifications/initialized")

    def tool(self, name, arguments=None):
        return self.rpc.call("tools/call", {"name": "workbench_" + name, "arguments": arguments or {}})

    def test_real_stdio_full_workflow_eof_rotation_and_no_secret_output(self):
        self.start_bridge()
        self.assertEqual(len(self.rpc.call("tools/list")["tools"]), 22)
        result = self.tool("prepare_proposal", {"request_id": "stdio-1", "kind": "issue", "operation": "create", "content": {"title": "中文入库", "project_id": self.project["id"], "body": "多行\n\necho 'one'\necho two"}})
        self.assertFalse(result["isError"])
        proposal_id = result["structuredContent"]["proposal_id"]
        preview = self.tool("preview_proposal", {"proposal_id": proposal_id})["structuredContent"]
        self.rpc.notify("notifications/cancelled", {"requestId": 100})
        receipt = self.tool("commit_proposal", {"proposal_id": proposal_id, "version": preview["version"], "preview_digest": preview["preview_digest"], "confirmation": {"mode": "agent_attested", "user_confirmed": True}})["structuredContent"]
        self.assertEqual(self.workbench.repository.get_record(receipt["item_id"])[0]["body"], preview["content"]["body"])
        self.workbench.security.change_client(self.info["client_id"], True)
        self.assertFalse(self.tool("capabilities")["isError"])
        self.workbench.security.change_client(self.info["client_id"])
        denied = self.tool("capabilities")
        self.assertTrue(denied["isError"])
        self.assertEqual(denied["structuredContent"]["code"], "unauthenticated")
        self.assertNotIn(self.config["token"], json.dumps([preview, denied]) + "\n".join(self.rpc.errors))
        self.rpc.close()
        self.assertEqual(self.rpc.process.returncode, 0)
        self.rpc = None

    def test_dormant_stdio_uses_existing_tools_and_rejects_new_operations(self):
        from test_agent_capabilities import grants
        from workbench.agent_management import client_version
        client = self.workbench.security.clients()[self.info['client_id']]
        params = {key: client[key] for key in ('name', 'scopes', 'project_ids', 'categories')}
        self.workbench.security.manager().run('edit', {**params, 'kinds':[], 'project_ids':[], 'categories':[], 'capability_grants':grants()}, client['client_id'], client_version(client))
        self.start_bridge()
        self.assertEqual(len(self.rpc.call('tools/list')['tools']), 22)
        result = self.tool('capabilities')
        self.assertFalse(result['isError'])
        self.assertEqual(result['structuredContent']['capability_authorization']['effective'], [])
        self.assertEqual(self.tool('get_catalog')['structuredContent'], {'tags':[], 'document_categories':[]})
        self.assertTrue(self.tool('get_item', {'kind':'issue', 'item_id':'ISSUE-0001'})['isError'])
        self.assertTrue(any(item['name'] == 'workbench_read_file' for item in self.rpc.call('tools/list')['tools']))
        self.assertEqual(self.tool('list_file_grants')['structuredContent'], {'items':[]})
        self.assertTrue(self.tool('get_file_info', {'file_id':'00000000-0000-0000-0000-000000000000'})['isError'])

    def test_service_down_invalid_config_and_remote_or_identity_changes(self):
        client = LocalAgentClient(self.config_file)
        self.workbench.close()
        failed, result = client.call(TOOLS[0], {})
        self.assertTrue(failed)
        self.assertTrue(result["retryable"])
        for update in ({"base_url": "http://127.0.0.1:0"}, {"base_url": "http://127.0.0.1:65536"}, {"base_url": "https://example.com"}, {"base_url": "http://127.0.0.1@evil.example"}, {"base_url": "http://127.0.0.1:4174/path"}, {"base_url": []}, {"client_id": "not-a-uuid"}):
            private_write(self.config_file, {**self.config, **update})
            with self.assertRaises(ValueError):
                client.read_config()
        private_write(self.config_file, {**self.config, "workspace_id": "00000000-0000-0000-0000-000000000000"})
        self.assertTrue(client.call(TOOLS[0], {})[0])
        private_write(self.config_file, {**self.config, "token": "invalid\nsecret"})
        process = subprocess.run([sys.executable, str(ROOT / "agent_bridge.py"), "--config", str(self.config_file)], input=b'', capture_output=True)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stdout, b'')
        self.assertNotIn(b'invalid\nsecret', process.stderr)

    def test_localhost_is_pinned_to_numeric_loopback(self):
        private_write(self.config_file, {**self.config, "base_url": "http://localhost:4174"})
        client = LocalAgentClient(self.config_file)
        response = HTTPError(self.config["base_url"], 200, "ok", {}, io.BytesIO(b'{}'))
        with patch.object(client.opener, "open", return_value=response) as opened:
            self.assertFalse(client.call(TOOLS[0], {})[0])
            self.assertEqual(opened.call_args.args[0].full_url, "http://127.0.0.1:4174/api/agent/v1/capabilities")

    def test_live_http_redirect_never_receives_forwarded_credentials(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        received = []
        class Sink(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                received.append(self.headers.get("Authorization"))
                self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
        sink = ThreadingHTTPServer(("127.0.0.1", 0), Sink)
        class Redirect(Sink):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{sink.server_address[1]}/sink")
                self.end_headers()
                self.wfile.write(b'{}')
        source = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in (source, sink)]
        for thread in threads:
            thread.start()
        try:
            private_write(self.config_file, {**self.config, "base_url": f"http://127.0.0.1:{source.server_address[1]}"})
            failed, result = LocalAgentClient(self.config_file).call(TOOLS[0], {})
            self.assertTrue(failed)
            self.assertEqual(result["code"], "invalid_connection")
            self.assertEqual(received, [])
        finally:
            for server in (source, sink):
                server.shutdown(); server.server_close()
            for thread in threads:
                thread.join(3)

    def test_redirect_and_oversize_responses_are_errors(self):
        client = LocalAgentClient(self.config_file)
        error = HTTPError(self.workbench.base_url, 302, "redirect", {"Location": "http://example.com"}, io.BytesIO(b'{}'))
        with patch.object(client.opener, "open", side_effect=error):
            failed, result = client.call(TOOLS[0], {})
        self.assertTrue(failed)
        self.assertEqual(result["code"], "invalid_connection")
        response = HTTPError(self.workbench.base_url, 200, "large", {}, io.BytesIO(b'x' * (MAX_RESPONSE_BYTES + 1)))
        with patch.object(client.opener, "open", return_value=response):
            self.assertTrue(client.call(TOOLS[0], {})[0])


if __name__ == "__main__":
    unittest.main()
