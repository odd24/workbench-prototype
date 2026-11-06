"""Explicit real-Codex MCP acceptance in disposable configuration and data.

Uses App Server's direct tool-call API, never starts a model turn or changes the
user's Codex settings. Not included in unittest discovery.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from server import Repository, WorkbenchHandler, WorkbenchHTTPServer
from workbench.agent_security import AgentSecurity, private_write, read_json
from workbench.agent_service import AgentService


ROOT = Path(__file__).resolve().parent


class RpcProcess:
    def __init__(self, command, cwd, env=None, terminate_tree=False):
        self.terminate_tree = terminate_tree
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.messages = queue.Queue()
        self.errors = []
        self.events = []
        self.sequence = 0
        self.readers = [threading.Thread(target=self._read, daemon=True), threading.Thread(target=self._stderr, daemon=True)]
        for reader in self.readers:
            reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                self.messages.put(json.loads(line.decode("utf-8")))
        except Exception as error:
            self.messages.put(error)
        finally:
            self.messages.put(EOFError("协议进程已关闭"))

    def _stderr(self):
        try:
            for line in self.process.stderr:
                if len(self.errors) < 100:
                    self.errors.append(line.decode("utf-8", "replace").rstrip())
        except OSError:
            pass

    def send(self, message):
        self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        self.process.stdin.flush()

    def notify(self, method, params=None):
        self.send({"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {})})

    def call(self, method, params=None, timeout=45):
        self.sequence += 1
        request_id = self.sequence
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"协议请求超时：{method}")
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f"协议请求超时：{method}") from None
            if isinstance(message, Exception):
                raise message
            if message.get("id") != request_id or "method" in message:
                # This test never grants an unexpected request, approval or elicitation.
                if "method" in message and "id" in message:
                    self.send({"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "Unsupported test-client request"}})
                if len(self.events) < 1000:
                    self.events.append(message)
                continue
            if "error" in message:
                raise RuntimeError(str(message["error"]))
            return message["result"]

    def close(self):
        try:
            # Codex can retain helper descendants with the isolated config as
            # their cwd. Reap the test-owned tree while its root is still alive;
            # letting the root exit first can orphan inherited Windows pipes.
            if self.terminate_tree and os.name == "nt" and self.process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            if self.process.stdin and not self.process.stdin.closed:
                self.process.stdin.close()
            self.process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self.process.terminate()
            self.process.wait(timeout=5)
        for reader in self.readers:
            reader.join(timeout=2)
        # A descendant can inherit a pipe after the direct child exits. Closing
        # a raw Windows pipe while another thread is blocked in read can itself
        # block indefinitely. Daemon readers own those handles until EOF; never
        # wait on their close after the bounded joins above.
        for reader, stream in zip(self.readers, (self.process.stdout, self.process.stderr)):
            if not reader.is_alive():
                stream.close()


class LocalWorkbench:
    def __init__(self, root, credentials):
        self.repository = Repository(root)
        self.security = AgentSecurity(root, credentials)
        self.repository.agent_service = AgentService(self.repository, self.security)
        class QuietHandler(WorkbenchHandler):
            def log_message(self, *_args):
                pass
        QuietHandler.repository = self.repository
        self.server = WorkbenchHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)


def run_acceptance(codex=None):
    executable = codex or shutil.which("codex")
    if not executable:
        raise RuntimeError("未找到 Codex CLI，无法完成真实客户端验收")
    with tempfile.TemporaryDirectory(prefix="workbench-codex-acceptance-") as directory:
        base = Path(directory)
        data, credentials = base / "data", base / "credentials"
        workbench = LocalWorkbench(data, credentials)
        rpc = None
        try:
            project = workbench.repository.create_project({"name": "Codex 接入验收"})
            workbench.repository.ensure_document_category("验收知识")
            info = workbench.security.add_client("Codex 临时验收", ["read", "propose", "commit"], [project["id"]], ["验收知识"], workbench.base_url, kinds=["issue", "document", "todo", "info"])
            client_config = Path(info["config_file"])
            codex_home = base / "isolated-codex"
            codex_home.mkdir()
            cwd = base / "isolated-project"
            cwd.mkdir()
            # TOML string literals use JSON quoting; no secrets enter this file.
            quote = lambda value: json.dumps(str(value))
            config = '\n'.join([
                'model = "workbench-test-model"', 'model_provider = "workbench_test"',
                '[model_providers.workbench_test]', 'name = "Local protocol acceptance (no inference)"',
                'base_url = "http://127.0.0.1:1/v1"', 'wire_api = "responses"', 'requires_openai_auth = false',
                '[analytics]', 'enabled = false',
                # This fixture tests direct MCP only. Background marketplace
                # cloning is unrelated and can retain Windows file handles.
                '[features]', 'plugins = false', 'apps = false', 'remote_plugin = false',
                '[mcp_servers.workbench]', 'command = ' + quote(sys.executable),
                'args = [' + quote(ROOT / 'agent_bridge.py') + ', "--config", ' + quote(client_config) + ']',
                'env = { WORKBENCH_MCP_TRACE = "1" }',
            ])
            # This is the child's genuine config home, not a shell scratch variable.
            from workbench.persistence import atomic_write_text
            atomic_write_text(codex_home / "config.toml", config)
            env = {**os.environ, "CODEX_HOME": str(codex_home), "PYTHONIOENCODING": "utf-8"}
            for key in list(env):
                if key == "CODEX_THREAD_ID" or (key.startswith(("OPENAI_", "CHATGPT_", "CODEX_")) and any(marker in key for marker in ("TOKEN", "KEY", "AUTH"))):
                    env.pop(key)

            rpc = RpcProcess([executable, "app-server", "--stdio"], cwd, env, terminate_tree=True)
            rpc.call("initialize", {"clientInfo": {"name": "workbench_acceptance", "version": "1.0"}, "capabilities": {"experimentalApi": True}})
            rpc.notify("initialized")
            thread = rpc.call("thread/start", {"cwd": str(cwd), "ephemeral": True, "approvalPolicy": "never", "sandbox": "read-only"})
            thread_id = thread["thread"]["id"]
            status = rpc.call("mcpServerStatus/list", {"threadId": thread_id, "serverName": "workbench", "detail": "toolsAndAuthOnly"})
            inventory = next(item for item in status["data"] if item["name"] == "workbench")
            assert len(inventory["tools"]) == 12 and inventory["serverCapabilities"] == {"tools": {}}
            def call(name, args=None, error=False):
                result = rpc.call("mcpServer/tool/call", {"threadId": thread_id, "server": "workbench", "tool": "workbench_" + name, "arguments": args or {}})
                if bool(result.get("isError")) != error:
                    raise AssertionError(result)
                return result.get("structuredContent") or json.loads(result["content"][0]["text"])
            capabilities = call("capabilities")
            assert capabilities["workspace_id"] == info["workspace_id"]
            assert call("list_projects")["items"][0]["id"] == project["id"]
            call("get_catalog", {"project_id": project["id"]})
            receipts = []
            for kind in ("issue", "document", "todo", "info"):
                content = {"title": "Codex 客户端验收 " + kind, "body": "## 已验证事实\n\n临时测试，不含真实工作资料。\n\n```sh\necho 'test only'\n```"}
                content.update({"project_id": project["id"]} if kind != "document" else {"category": "验收知识"})
                if kind == "info":
                    content["info_fields"] = [{"name": "命令", "value": "  echo \"quoted\"\n  echo two  ", "note": "  首尾空格  "}]
                proposal = call("prepare_proposal", {"request_id": "codex-create-" + kind, "kind": kind, "operation": "create", "content": content})
                preview = call("preview_proposal", {"proposal_id": proposal["proposal_id"]})
                assert preview["content"]["body"] == content["body"]
                revised = {**content, "body": content["body"] + "\n\n用户要求补充的验证说明。"}
                call("revise_proposal", {"proposal_id": proposal["proposal_id"], "expected_version": preview["version"], "content": revised})
                call("commit_proposal", {"proposal_id": proposal["proposal_id"], "version": preview["version"], "preview_digest": preview["preview_digest"], "confirmation": {"mode": "agent_attested", "user_confirmed": True}}, error=True)
                preview = call("preview_proposal", {"proposal_id": proposal["proposal_id"]})
                confirmation = {"proposal_id": preview["proposal_id"], "version": preview["version"], "preview_digest": preview["preview_digest"], "confirmation": {"mode": "agent_attested", "user_confirmed": True, "note": "程序化客户端确认测试夹具"}}
                receipt = call("commit_proposal", confirmation)
                assert call("commit_proposal", confirmation) == receipt
                assert call("get_proposal", {"proposal_id": proposal["proposal_id"]})["state"] == "committed"
                assert call("get_item", {"kind": kind, "item_id": receipt["item_id"]})["body"] == revised["body"]
                if kind == "info":
                    assert call("get_item", {"kind": kind, "item_id": receipt["item_id"]})["info_fields"] == content["info_fields"]
                receipts.append(receipt)
            for index, (kind, operation, body) in enumerate([("issue", "append", "新增排查进展"), ("document", "update", "## 知识总结\n\n已更新的完整内容。")]):
                current = call("get_item", {"kind": kind, "item_id": receipts[index]["item_id"]})
                proposed = call("prepare_proposal", {"request_id": "codex-" + operation, "kind": kind, "operation": operation, "target_id": current["id"], "base_revision": current["revision"], "content": {"body": body}})
                preview = call("preview_proposal", {"proposal_id": proposed["proposal_id"]})
                expected = current["body"] + "\n\n" + body if operation == "append" else body
                assert preview["content"]["body"] == expected
                receipts[index] = call("commit_proposal", {"proposal_id": preview["proposal_id"], "version": preview["version"], "preview_digest": preview["preview_digest"], "confirmation": {"mode": "agent_attested", "user_confirmed": True, "note": "程序化更新确认测试"}})
                assert call("get_item", {"kind": kind, "item_id": receipts[index]["item_id"]})["body"] == expected
            cancelled = call("prepare_proposal", {"request_id": "codex-cancel", "kind": "document", "operation": "create", "content": {"title": "取消测试", "category": "验收知识", "body": "不应入库"}})
            call("preview_proposal", {"proposal_id": cancelled["proposal_id"]})
            assert call("cancel_proposal", {"proposal_id": cancelled["proposal_id"], "expected_version": 1})["state"] == "cancelled"
            call("list_proposals")
            assert len(call("search")["items"]) == 4
            # Real Codex prepares a web-only proposal and cannot self-attest it.
            web_proposal = call("prepare_proposal", {"request_id": "codex-local-web", "kind": "issue", "operation": "create", "confirmation_mode": "local_web", "content": {"title": "网页独立批准验收", "body": "临时完整正文", "project_id": project["id"]}})
            web_preview = call("preview_proposal", {"proposal_id": web_proposal["proposal_id"]})
            denied = call("commit_proposal", {"proposal_id": web_proposal["proposal_id"], "version": web_preview["version"], "preview_digest": web_preview["preview_digest"], "confirmation": {"mode": "agent_attested", "user_confirmed": True}}, error=True)
            assert denied["code"] == "confirmation_required"
            from urllib.request import Request, urlopen
            def local_request(route, method="GET", payload=None, token=None):
                headers = {"X-Workbench-Management": "1", "Origin": workbench.base_url, "Content-Type": "application/json"}
                if token: headers["X-Workbench-Management-Token"] = token
                req = Request(workbench.base_url + "/api/local/agent-management/" + route, data=json.dumps(payload).encode() if payload is not None else None, headers=headers, method=method)
                with urlopen(req, timeout=10) as response: return json.load(response)
            session = local_request("status")["management_token"]
            review = local_request("proposals/" + web_proposal["proposal_id"] + "/preview", token=session)
            approved = local_request("proposals/" + web_proposal["proposal_id"] + "/approve", "POST", {"workspace_id": workbench.security.workspace_id, "version": review["version"], "preview_digest": review["preview"]["preview_digest"], "preview_ticket": review["preview_ticket"], "request_id": "codex-web-approve"}, session)
            assert approved["state"] == "completed"
            observed_receipt = call("get_proposal", {"proposal_id": web_proposal["proposal_id"]})["receipt"]
            assert all(observed_receipt[key] == value for key, value in approved["receipt"].items())
            workbench.close()
            workbench = LocalWorkbench(data, credentials)
            private_write(client_config, {**read_json(client_config), "base_url": workbench.base_url})
            for receipt in receipts:
                assert call("get_item", {"kind": receipt["kind"], "item_id": receipt["item_id"]})["revision"] == receipt["revision"]
            workbench.security.change_client(info["client_id"])
            assert call("capabilities", error=True)["code"] == "unauthenticated"
            version = subprocess.run([executable, "--version"], capture_output=True, text=True, check=True).stdout.strip()
            return {"passed": True, "codex_version": version, "protocol": "2025-11-25", "tool_count": len(inventory["tools"]),
                    "created": [item["kind"] for item in receipts], "preview_revision_confirmation": True,
                    "issue_append_document_update": True, "local_web_independent_approval": True, "retry_cancel_restart_revoke": True, "model_turns_started": 0, "user_config_changed": False}
        except Exception as error:
            diagnostics = "\n".join(rpc.errors[-12:]) if rpc else ""
            raise RuntimeError(str(error) + "\n" + diagnostics) from error
        finally:
            if rpc:
                rpc.close()
            workbench.close()


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2))
