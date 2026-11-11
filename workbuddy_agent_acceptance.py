"""Explicit installed-WorkBuddy MCP connection probe, with no model turn.

This is deliberately a partial compatibility check, not the AG-121 write matrix.
The default relay forwards bytes unchanged and records protocol metadata only.
Explicit --protocol-faults injects fixed server requests and consumes only their
replies; it never generates client requests or substitutes a simulated client.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import uuid
from contextlib import contextmanager, nullcontext
from pathlib import Path

from acceptance_process import ClientJob
from codex_agent_acceptance import LocalWorkbench, RpcProcess
from workbench.agent_security import read_json
from workbench.agent_runtime import AgentRuntime
from workbench.agent_tools import TOOLS


ROOT = Path(__file__).resolve().parent


class ProtocolFaultProbe:
    """Explicit server-message injection; never enabled by the default relay."""

    def __init__(self, enabled=False):
        self.enabled = enabled
        self.started = False
        self.pending = {}
        self.completed = threading.Event()

    def requests(self):
        if not self.enabled or self.started:
            return []
        self.started = True
        messages = []
        for name, method in (("ping", "ping"), ("unknown_method", "workbench/probe_unknown_method")):
            request_id = "workbench-fixture-" + str(uuid.uuid4())
            self.pending[request_id] = name
            messages.append({"jsonrpc": "2.0", "id": request_id, "method": method})
        return messages

    def consume(self, message):
        if "method" in message or message.get("id") not in self.pending:
            return None
        name = self.pending.pop(message["id"])
        error = message.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        valid = (message.get("result") == {} and "error" not in message) if name == "ping" else (
            type(code) is int and code == -32601 and "result" not in message)
        event = {"fixture_reply": name, "valid": valid}
        if type(code) is int:
            event["error_code"] = code
        if not self.pending:
            self.completed.set()
        return event


def protocol_metadata(message, pending):
    """Describe wire outcomes without retaining arguments or business content."""
    event = {}
    if "method" in message:
        event["method"] = message["method"]
    if message.get("method") == "notifications/cancelled":
        params = message.get("params")
        request_id = params.get("requestId") if isinstance(params, dict) else None
        tool = pending.get(request_id) if type(request_id) in {int, str} else None
        event["cancelled_request_pending"] = tool is not None
        if tool is not None:
            event["cancelled_tool"] = tool
        # Keep the association: cancellation never proves that business work
        # was undone, and a late response must still be observed separately.
    if message.get("method") == "initialize":
        event.update({key: message["params"].get(key) for key in ("protocolVersion", "clientInfo")})
    if message.get("method") == "tools/call":
        event["tool"] = message.get("params", {}).get("name")
        request_id = message.get("id")
        if request_id is not None:
            if len(pending) >= 256 and request_id not in pending:
                pending.pop(next(iter(pending)))
            pending[request_id] = event["tool"]
    result = message.get("result", {})
    if isinstance(result, dict):
        if "protocolVersion" in result:
            event["protocolVersion"] = result["protocolVersion"]
        if "tools" in result:
            event["tools"] = [tool["name"] for tool in result["tools"]]
    if "method" not in message and message.get("id") in pending:
        event["tool"] = pending.pop(message["id"])
        if "result" in message and isinstance(result, dict):
            is_error = result.get("isError", False)
            if isinstance(is_error, bool):
                event["tool_is_error"] = is_error
            else:
                event["tool_result_malformed"] = True
    if "error" in message:
        code = message["error"]["code"]
        if isinstance(code, int):
            event["error_code"] = code
        else:
            event["rpc_error_malformed"] = True
    return event


@contextmanager
def disposable_directory(prefix="workbench-workbuddy-probe-"):
    temporary = tempfile.TemporaryDirectory(prefix=prefix)
    try:
        yield temporary.name
    finally:
        # Windows may retain the just-exited client's cwd briefly. Retry only
        # this tempfile-owned directory, and report a genuine cleanup failure.
        for attempt in range(10):
            try:
                temporary.cleanup()
                break
            except OSError as error:
                if getattr(error, "winerror", None) not in (5, 32, 145):
                    raise
                if attempt == 9:
                    raise
                time.sleep(0.5)


def relay(protocol_faults=False):
    trace = Path(os.environ["WORKBENCH_PROBE_TRACE"])
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "agent_bridge.py"), "--config", os.environ["WORKBENCH_PROBE_CONFIG"]],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    lock = threading.Lock()
    output_lock = threading.Lock()
    pending = {}
    fault_probe = ProtocolFaultProbe(protocol_faults)

    def forward(source, target, direction):
        try:
            for line in source:
                consumed = None
                injections = []
                with lock, trace.open("a", encoding="utf-8") as stream:
                    event = {"direction": direction}
                    try:
                        message = json.loads(line)
                        if direction == "client_to_server":
                            consumed = fault_probe.consume(message)
                            if message.get("method") == "notifications/initialized":
                                injections = fault_probe.requests()
                        event.update(consumed if consumed is not None else protocol_metadata(message, pending))
                    except (ValueError, TypeError, AttributeError, KeyError):
                        # Metadata parsing must not filter malformed wire input
                        # or change the real server's response to that input.
                        event = {"direction": direction, "unparsed": True}
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                if consumed is not None:
                    # These replies belong to the explicit synthetic server
                    # requests, not to the real workbench server.
                    continue
                if protocol_faults and direction == "server_to_client" and "tools" in event:
                    fault_probe.completed.wait(2)
                with output_lock if direction == "server_to_client" else nullcontext():
                    target.write(line)
                    target.flush()
                for injection in injections:
                    with lock, trace.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps({"direction": "fixture_to_client", "fixture_request": injection["method"]}) + "\n")
                    with output_lock:
                        sys.stdout.buffer.write((json.dumps(injection) + "\n").encode("utf-8"))
                        sys.stdout.buffer.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            if direction == "client_to_server":
                target.close()

    reader = threading.Thread(target=forward, args=(process.stdout, sys.stdout.buffer, "server_to_client"), daemon=True)
    reader.start()
    try:
        forward(sys.stdin.buffer, process.stdin, "client_to_server")
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=5)


def isolated_environment(base):
    # Allowlist environment: do not inherit account tokens, real home/config,
    # injected NODE_OPTIONS, or parent model credentials.
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    for key, name in {
        "USERPROFILE": "home", "HOME": "home", "APPDATA": "roaming", "LOCALAPPDATA": "local",
        "TEMP": "tmp", "TMP": "tmp", "CODEBUDDY_CONFIG_DIR": "config", "WORKBUDDY_CONFIG_DIR": "config",
        "XDG_CONFIG_HOME": "xdg-config", "XDG_CACHE_HOME": "xdg-cache", "XDG_DATA_HOME": "xdg-data",
        "XDG_STATE_HOME": "xdg-state",
    }.items():
        path = base / name
        path.mkdir(exist_ok=True)
        env[key] = str(path)
    drive, tail = os.path.splitdrive(env["USERPROFILE"])
    env.update(HOMEDRIVE=drive, HOMEPATH=tail, PYTHONIOENCODING="utf-8", NO_COLOR="1",
               DISABLE_AUTOUPDATER="1", DISABLE_TELEMETRY="1", DISABLE_GALILEO="1",
               CODEBUDDY_REMOTE_CONFIG_DISABLED="1", CODEBUDDY_DISABLE_COMPILE_CACHE="1",
               HTTP_PROXY="http://127.0.0.1:1", HTTPS_PROXY="http://127.0.0.1:1", NO_PROXY="127.0.0.1,localhost")
    return env


def installed_cli_bundle(install):
    """Use the vendor launcher's fixed lite selector for lite-only packages."""
    dist = install / "resources" / "app.asar.unpacked" / "cli" / "dist"
    if not (dist / "codebuddy.js").is_file() and (dist / "codebuddy-lite-wb.mjs").is_file():
        return "lite-wb"
    return "default"


def run_acceptance(install, protocol_faults=False):
    cli = install / "resources" / "app.asar.unpacked" / "cli" / "bin" / "codebuddy"
    node = shutil.which("node")
    if not cli.is_file() or not node:
        raise RuntimeError("Installed WorkBuddy CLI or Node executable unavailable")
    with disposable_directory() as directory:
        base = Path(directory)
        env = isolated_environment(base)
        bundle = installed_cli_bundle(install)
        if bundle == "lite-wb":
            env["CODEBUDDY_FORCE_LITE_WB_BUNDLE"] = "1"
        cwd = base / "workspace"
        cwd.mkdir()
        job = ClientJob()
        workbench = None
        try:
            workbench = LocalWorkbench(base / "data", base / "private")
            project = workbench.repository.create_project({"name": "WorkBuddy 临时连接验收"})
            info = workbench.security.add_client("WorkBuddy disposable probe", ["read", "propose", "commit"],
                [project["id"]], [], workbench.base_url, kinds=["issue", "todo", "info", "document"])
            config = read_json(Path(info["config_file"]))
            trace = base / "protocol.jsonl"
            mcp = {"mcpServers": {"workbench_probe": {"type": "stdio", "command": sys.executable,
                "args": [str(Path(__file__).resolve()), "--relay", *(["--protocol-faults"] if protocol_faults else [])], "env": {
                    "WORKBENCH_PROBE_TRACE": str(trace), "WORKBENCH_PROBE_CONFIG": info["config_file"]}}}}
            (base / "config" / ".mcp.json").write_text(json.dumps(mcp), encoding="utf-8")
            version = subprocess.run([node, str(cli), "--version"], cwd=cwd, env=env,
                capture_output=True, timeout=15, check=True).stdout.decode("utf-8").strip()
            # The real installed CLI performs initialize and tools/list. No print
            # prompt, model credentials, user-config copy, or inference endpoint.
            process = subprocess.Popen([node, str(cli), "mcp", "list"], cwd=cwd, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            job.assign(process)
            timed_out = False
            try:
                stdout, stderr = process.communicate(timeout=45)
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    process.kill()
                stdout, stderr = process.communicate(timeout=10)
            assert config["token"].encode() not in stdout + stderr, "Temporary credential leaked by client"
            events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()] if trace.exists() else []
            requests = [item for item in events if item["direction"] == "client_to_server"]
            inventories = [item["tools"] for item in events if "tools" in item]
            initialized = next((item for item in requests if item.get("method") == "initialize"), None)
            connected = b"Connected" in stdout
            assert not timed_out and process.returncode == 0 and connected, "Installed client connection check failed"
            assert initialized and initialized["protocolVersion"] == "2025-11-25", "Client initialize not observed"
            assert any(item.get("method") == "notifications/initialized" for item in requests), "Client initialized notification missing"
            expected_tools = sorted(tool['name'] for tool in TOOLS)
            assert inventories and all(sorted(items) == expected_tools for items in inventories), "Installed client did not discover the full tool catalog"
            errors = [item["error_code"] for item in events if "error_code" in item and "fixture_reply" not in item]
            probe_replies = [item for item in events if "fixture_reply" in item]
            assert not errors, "Protocol error observed"
            if protocol_faults:
                assert {item["fixture_reply"] for item in probe_replies} == {"ping", "unknown_method"}, "Client did not answer injected server requests"
                assert all(item["valid"] for item in probe_replies), "Client gave an unexpected server-request response"
            return {"cli_version": version, "cli_bundle": bundle, "exit_code": process.returncode, "timed_out": timed_out,
                "connected": connected, "initialize": initialized,
                "methods": [item["method"] for item in requests if "method" in item], "tool_count": len(inventories[0]),
                "tools": expected_tools,
                "server_protocols": [item["protocolVersion"] for item in events if item["direction"] == "server_to_client" and "protocolVersion" in item],
                "protocol_errors": errors, "protocol_faults": protocol_faults,
                "fixture_replies": probe_replies,
                "model_turns_started": 0, "real_user_config_changed": False,
                "write_matrix": "not_run_no_public_direct_tool_call_entry_verified",
                "ag121_complete": False}
        finally:
            job.close()
            try:
                if workbench and "info" in locals():
                    workbench.security.change_client(info["client_id"])
            finally:
                if workbench:
                    workbench.close()


def run_session(install, protocol_faults=False):
    """Prepare a disposable desktop project; never launch the real profile.

    The user must explicitly accept task/recent-project history in the existing
    desktop profile before opening this project. No login data is copied/read.
    """
    cli = install / "resources" / "app.asar.unpacked" / "cli" / "bin" / "codebuddy"
    if not cli.is_file():
        raise RuntimeError("Installed WorkBuddy CLI unavailable")
    with disposable_directory() as directory:
        base = Path(directory)
        cwd = base / "workspace"
        cwd.mkdir()
        workbench = LocalWorkbench(base / "data", base / "private")
        try:
            runtime = AgentRuntime(workbench.repository, port=workbench.server.server_address[1], base=base / "private")
            workbench.repository.agent_runtime = runtime
            runtime.set_enabled(True)
            project = workbench.repository.create_project({"name": "WorkBuddy 隔离验收"})
            workbench.repository.ensure_document_category("验收知识")
            info = workbench.security.add_client("WorkBuddy isolated session", ["read", "propose", "commit"],
                [project["id"]], ["验收知识"], workbench.base_url, kinds=["issue", "todo", "info", "document"])
            mcp = {"mcpServers": {"workbench_probe": {"type": "stdio", "command": sys.executable,
                "args": [str(Path(__file__).resolve()), "--relay", *(["--protocol-faults"] if protocol_faults else [])], "env": {
                    "WORKBENCH_PROBE_TRACE": str(base / "protocol.jsonl"), "WORKBENCH_PROBE_CONFIG": info["config_file"]}}}}
            # Documented desktop path plus bundled CLI's project path. These
            # are candidate project files; discovery must be verified live.
            (cwd / ".workbuddy").mkdir()
            for path in (cwd / ".mcp.json", cwd / ".workbuddy" / "mcp.json"):
                path.write_text(json.dumps(mcp, ensure_ascii=False, indent=2), encoding="utf-8")
            manifest = {"workbench_url": workbench.base_url, "project_id": project["id"],
                "category": "验收知识", "temporary_workspace": str(cwd), "stop_file": str(base / "STOP"),
                "desktop_launched": False, "model_turns_started_by_fixture": 0,
                "protocol_faults": protocol_faults,
                "requires_user_decision": "Existing desktop profile may persist task/recent-project history; project MCP discovery unverified"}
            (base / "session.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
            deadline = time.monotonic() + 7200
            while not (base / "STOP").exists() and time.monotonic() < deadline:
                time.sleep(0.25)
        finally:
            try:
                if "info" in locals():
                    workbench.security.change_client(info["client_id"])
            finally:
                workbench.close()


def run_readonly_pilot(client, check_only=False, codex_project_guard=False):
    """Create one single-client AG-142 fixture without opening a desktop."""
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
    from workbench.agent_management import client_version

    prefix = f'workbench-ag142-pilot-{client}-'
    with disposable_directory(prefix) as directory:
        base = Path(directory).resolve()
        project_dir = base / 'desktop-project'
        project_dir.mkdir()
        workbench = LocalWorkbench(base / 'data', base / 'private')
        client_id = None
        token = None
        audit = {}
        try:
            project = workbench.repository.create_project({'name':'AG142 隔离项目'})
            info = workbench.security.add_client(f'AG142 {client} read-only', ['read'], [project['id']], [],
                                                  workbench.base_url, kinds=['issue'])
            client_id = info['client_id']
            workspace = info['workspace_id']
            token = read_json(Path(info['config_file']))['token']
            source = base / 'AG142-fixture.txt'
            text = '  UTF-8 中文与引号 "原文"\n第二段 🧪\n尾部空格  '
            source.write_bytes(text.encode())

            headers = {'Origin':workbench.base_url, 'X-Workbench-Management':'1', 'Content-Type':'application/json'}

            def local(route, payload=None, method=None):
                body = json.dumps(payload).encode() if payload is not None else None
                request = Request(workbench.base_url + '/api/local/agent-management/' + route,
                                  data=body, headers=headers, method=method)
                with urlopen(request, timeout=10) as response:
                    return json.load(response)

            headers['X-Workbench-Management-Token'] = local('status')['management_token']
            files_route = f'clients/{client_id}/files'
            preview = local(files_route + '/preview', {'workspace_id':workspace,
                            'expected_version':client_version(workbench.security.clients()[client_id]),
                            'path':str(source), 'purposes':['text_read'], 'encoding':'utf-8', 'max_bytes':4096, 'duration_seconds':1200})
            ticket = {key:preview[key] for key in ('workspace_id','expected_version','preview_id','preview_digest')}
            granted = local(files_route + '/confirm', {**ticket, 'request_id':'ag142-pilot-file', 'approved':True})
            file_id = granted['file_id']

            name = 'workbench_ag142'
            trace = base / 'protocol.jsonl'
            entry = {'command':sys.executable, 'args':[str(Path(__file__).resolve()), '--relay'],
                     'env':{'WORKBENCH_PROBE_TRACE':str(trace), 'WORKBENCH_PROBE_CONFIG':info['config_file']}}
            guarded_tools = ['workbench_capabilities', 'workbench_list_file_grants',
                             'workbench_get_file_info', 'workbench_read_file']
            if client == 'codex':
                config = project_dir / '.codex' / 'config.toml'
                encoded = json.dumps
                lines = [f'[mcp_servers.{name}]', f'command = {encoded(entry["command"])}',
                         f'args = {encoded(entry["args"])}']
                expected = {name:entry}
                if codex_project_guard:
                    lines[:0] = ['[mcp_servers.workbench]', 'enabled = false', '']
                    lines.extend(['enabled = true', f'enabled_tools = {encoded(guarded_tools)}'])
                    expected = {'workbench':{'enabled':False},
                                name:{**entry, 'enabled':True, 'enabled_tools':guarded_tools}}
                lines.extend([f'[mcp_servers.{name}.env]', *(f'{key} = {encoded(value)}' for key, value in entry['env'].items())])
                content = '\n'.join(lines) + '\n'
                assert tomllib.loads(content)['mcp_servers'] == expected
            else:
                config = project_dir / '.workbuddy' / 'mcp.json'
                content = json.dumps({'mcpServers':{name:entry}}, ensure_ascii=False, indent=2) + '\n'
            config.parent.mkdir()
            config.write_text(content, encoding='utf-8')

            project_query = '' if codex_project_guard else f'再查项目 {project["id"]}。'
            prompt = (f'只使用 {name} 对应的 MCP 工具。先查询 capabilities，核对空间 {workspace}。{project_query}'
                      f'列出本次可见的工具名和协议证据。查找已批准的 AG142-fixture.txt（file_id {file_id}），用 get_file_info 的 '
                      'source_revision 和每段 next_offset，按每段 12 原始字节读到结束。把合成文本原样放入代码块，另列各段字节区间和服务返回的 SHA-256。'
                      '仅做上述读取。工具缺失、空间不符或任一分段失败时报告原错误并停止。不要使用终端、读取路径、改配置或提交。')
            prompt_path = project_dir / 'PROMPT.txt'
            prompt_path.write_text(prompt + '\n', encoding='utf-8')
            stop = base / 'STOP'
            review = {'mode':'check' if check_only else 'ready', 'client':client, 'workbench_url':workbench.base_url,
                      'workspace_id':workspace, 'project_id':project['id'], 'scopes':['read'], 'file_purposes':['text_read'],
                      'source_sha256':hashlib.sha256(text.encode()).hexdigest(),
                      'desktop_project':str(project_dir), 'config_path':str(config), 'config_text':content,
                      'prompt_path':str(prompt_path), 'prompt':prompt, 'trace_path':str(trace), 'stop_file':str(stop),
                      'timeout_seconds':1200, 'desktop_launched':False, 'model_turns_started':0}
            if codex_project_guard:
                review.update(expected_callable_server=name, expected_tools=guarded_tools,
                              project_disabled_servers=['workbench'])
            print(json.dumps(review, ensure_ascii=False, indent=2), flush=True)

            if check_only:
                env = {**isolated_environment(base), **entry['env']}
                rpc = RpcProcess([entry['command'], *entry['args']], project_dir, env, terminate_tree=True)
                try:
                    init = rpc.call('initialize', {'protocolVersion':'2025-11-25', 'capabilities':{},
                                    'clientInfo':{'name':'ag142-pilot-fixture-check', 'version':'1'}})
                    assert init['protocolVersion'] == '2025-11-25'
                    rpc.notify('notifications/initialized')
                    assert sorted(tool['name'] for tool in rpc.call('tools/list')['tools']) == sorted(tool['name'] for tool in TOOLS)

                    def call(tool, arguments=None, error=False):
                        result = rpc.call('tools/call', {'name':'workbench_' + tool, 'arguments':arguments or {}})
                        assert result['isError'] is error
                        return result['structuredContent']

                    assert call('capabilities')['workspace_id'] == workspace
                    assert [item['id'] for item in call('list_projects')['items']] == [project['id']]
                    assert [item['file_id'] for item in call('list_file_grants')['items']] == [file_id]
                    metadata = call('get_file_info', {'file_id':file_id})
                    offset, parts = 0, []
                    while offset is not None:
                        data = call('read_file', {'file_id':file_id, 'source_revision':metadata['source_revision'], 'offset':offset, 'length':12})
                        assert 'path' not in data and offset < data['end_offset'] <= metadata['size_bytes']
                        parts.append(data['body'])
                        offset = data['next_offset']
                        assert offset is None or offset == data['end_offset']
                    assert ''.join(parts) == text and metadata['sha256'] == review['source_sha256']
                    denied = call('prepare_proposal', {'kind':'issue', 'operation':'create', 'request_id':'ag142-denied',
                                  'content':{'title':'不得创建', 'project_id':project['id'], 'body':'只读拒绝测试'}}, error=True)
                    assert denied['code'] == 'forbidden'
                    assert not list(workbench.repository.agent_proposals.proposals.glob('*.json'))
                    audit.update(file_read_segments=len(parts), write_denied=True)
                finally:
                    rpc.close()
            else:
                deadline = time.monotonic() + review['timeout_seconds']
                while not stop.exists() and time.monotonic() < deadline:
                    time.sleep(0.25)
            if trace.exists():
                expected = sorted(tool['name'] for tool in TOOLS)
                with trace.open(encoding='utf-8') as stream:
                    for line in stream:
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        version = event.get('protocolVersion')
                        if isinstance(version, str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', version):
                            if event.get('method') == 'initialize' and event.get('direction') == 'client_to_server':
                                audit.update(initialize=True, offered_protocol=version)
                            elif event.get('direction') == 'server_to_client':
                                audit['server_protocol'] = version
                        if event.get('method') == 'notifications/initialized':
                            audit['initialized'] = True
                        if 'tools' in event and sorted(event['tools']) == expected:
                            audit['tool_count'] = len(expected)
                        if event.get('tool_is_error') is False and event.get('tool') in expected:
                            successes = audit.setdefault('successful_tools', {})
                            tool = event['tool']
                            successes[tool] = successes.get(tool, 0) + 1
        finally:
            try:
                if client_id:
                    workbench.security.change_client(client_id)
                    assert not workbench.security.clients()[client_id]['enabled']
                if token:
                    request = Request(workbench.base_url + '/api/agent/v1/capabilities',
                                      headers={'Authorization':'Bearer ' + token, 'X-Workbench-Workspace':workspace})
                    try:
                        with urlopen(request, timeout=5):
                            raise AssertionError('Revoked pilot credential still accepted')
                    except HTTPError as error:
                        with error:
                            assert error.code == 401
                    audit['revoked_credential_denied'] = True
            finally:
                workbench.close()
    print(json.dumps({'client':client, 'stopped':True, 'port_closed':True, 'temporary_directory_removed':not base.exists(),
                      'check_only':check_only, 'model_turns_started_by_fixture':0, 'audit':audit}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path,
        default=Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "WorkBuddy")
    parser.add_argument("--relay", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--protocol-faults", action="store_true", help="Explicitly inject fixed server ping/unknown requests; no model or business writes")
    parser.add_argument("--desktop-session", action="store_true", help="Prepare temporary project files only; never launch or modify the real desktop profile")
    parser.add_argument('--readonly-pilot', choices=('codex','workbuddy'), help='Prepare a disposable AG-142 read-only project; never launch the desktop')
    parser.add_argument('--pilot-check', action='store_true', help='Verify and immediately close the read-only pilot without a desktop')
    parser.add_argument('--codex-project-guard', action='store_true', help='Disable inherited workbench and allow four tools in the temporary Codex project')
    args = parser.parse_args()
    if (args.pilot_check and not args.readonly_pilot) or (args.readonly_pilot and (args.relay or args.desktop_session or args.protocol_faults)):
        parser.error('Select one read-only pilot mode independently of the legacy probe')
    if args.codex_project_guard and args.readonly_pilot != 'codex':
        parser.error('--codex-project-guard requires --readonly-pilot codex')
    if args.relay:
        relay(args.protocol_faults)
    elif args.readonly_pilot:
        run_readonly_pilot(args.readonly_pilot, args.pilot_check, args.codex_project_guard)
    elif args.desktop_session:
        run_session(args.install_dir, args.protocol_faults)
    else:
        print(json.dumps(run_acceptance(args.install_dir, args.protocol_faults), ensure_ascii=False, indent=2))
