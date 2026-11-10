"""Explicit real-Codex MCP acceptance in disposable configuration and data.

Uses App Server's direct tool-call API, never starts a model turn or changes the
user's Codex settings. Not included in unittest discovery.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from acceptance_process import ClientJob
from server import Repository, WorkbenchHandler, WorkbenchHTTPServer
from workbench.agent_security import AgentSecurity, private_write, read_json
from workbench.agent_service import AgentService
from workbench.agent_tools import TOOLS


ROOT = Path(__file__).resolve().parent


class RpcProcess:
    def __init__(self, command, cwd, env=None, terminate_tree=False):
        self.terminate_tree = terminate_tree
        self.job = ClientJob() if terminate_tree and os.name == "nt" else None
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if self.job:
            try:
                self.job.assign(self.process)
            except BaseException:
                self.job.close()
                raise
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
            # Job ownership survives root exit. It also closes descendants that
            # inherited stdout/cwd, without relying on a live PID tree lookup.
            if self.job:
                self.job.close()
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
        self.drop_response_path = None
        self.repository = Repository(root)
        self.security = AgentSecurity(root, credentials)
        self.repository.agent_service = AgentService(self.repository, self.security)
        class QuietHandler(WorkbenchHandler):
            def log_message(self, *_args):
                pass

            def _json(handler, payload, status=200):
                if status == 200 and handler.path == self.drop_response_path:
                    self.drop_response_path = None
                    handler.close_connection = True
                    handler.connection.shutdown(socket.SHUT_RDWR)
                    return
                return super()._json(payload, status)
        QuietHandler.repository = self.repository
        self.server = WorkbenchHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)


def run_local_capabilities(call, local_request, workbench, project, info, session):
    """Exercise the current business tools through the installed App Server."""
    from urllib.parse import quote
    from urllib.request import Request, urlopen
    from workbench.agent_file_handles import SUPPORTED
    from workbench.agent_management import client_version
    from workbench.concept_maps import ConceptMapRepository

    workspace = info['workspace_id']
    client_id = info['client_id']
    project_id = project['id']
    resource = {'type':'project', 'id':project_id}
    attested = {'mode':'agent_attested', 'user_confirmed':True, 'note':'程序化协议验收'}

    def post(route, payload):
        return local_request(route, 'POST', payload, session)

    def confirm(route, preview, request_id):
        payload = {key:preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')}
        return post(route + '/confirm', {**payload, 'approved':True, 'request_id':request_id})

    def grant(suffix, request_id, **selection):
        route = f'clients/{client_id}/{suffix}'
        version = client_version(workbench.security.clients()[client_id])
        preview = post(route + '/preview', {'workspace_id':workspace, 'expected_version':version, **selection})
        return confirm(route, preview, request_id)

    def preview(kind, operation, request_id, **fields):
        candidate = call('prepare_proposal', {'request_id':request_id, 'kind':kind, 'operation':operation, **fields})
        return call('preview_proposal', {'proposal_id':candidate['proposal_id']})

    def commit_payload(candidate):
        return {**{key:candidate[key] for key in ('proposal_id', 'version', 'preview_digest')}, 'confirmation':attested}

    def web_approve(candidate, request_id):
        arguments = commit_payload(candidate)
        assert call('commit_proposal', arguments, error=True)['code'] == 'confirmation_required'
        route = 'proposals/' + candidate['proposal_id']
        review = local_request(route + '/preview', token=session)
        assert review['preview']['preview_digest'] == candidate['preview_digest']
        result = post(route + '/approve', {'workspace_id':workspace, 'version':review['version'],
                      'preview_digest':candidate['preview_digest'], 'preview_ticket':review['preview_ticket'], 'request_id':request_id})
        assert result['state'] == 'completed'
        observed = call('get_proposal', {'proposal_id':candidate['proposal_id']})['receipt']
        assert all(observed[key] == value for key, value in result['receipt'].items())
        return result['receipt']

    workbench.repository.ensure_concept_map_category('未分类')
    graph = ConceptMapRepository.normalize({'title':'Codex 图原文', 'project_id':project_id,
        'nodes':[{'id':'a', 'text':'甲'}, {'id':'b', 'text':'乙'}],
        'edges':[{'id':'edge', 'from':'a', 'to':'b', 'label':'联系'}]})
    assert not call('list_concept_maps')['items']
    grant('concept-maps', 'codex-graph-grant', grants={'schema_version':1, 'grants':[
        {'capability':'concept_maps.read', 'operations':['read'], 'resources':[resource], 'minimum_confirmation_mode':'agent_attested'},
        {'capability':'concept_maps.write', 'operations':['create','update'], 'resources':[resource], 'minimum_confirmation_mode':'agent_attested'}]})
    candidate = preview('concept_map', 'create', 'codex-graph-create', content={'graph':graph})
    assert candidate['content']['graph'] == graph
    created = call('commit_proposal', commit_payload(candidate))
    assert call('commit_proposal', commit_payload(candidate)) == created
    graph_id = created['item_id']
    assert graph_id in {item['id'] for item in call('list_concept_maps')['items']}
    current = call('get_concept_map', {'map_id':graph_id})
    edited = {**current['editable_graph'], 'title':'Codex 图更新'}
    candidate = preview('concept_map', 'update', 'codex-graph-update', target_id=graph_id,
                        base_revision=current['revision'], content={'graph':edited})
    assert candidate['content']['graph'] == edited
    workbench.drop_response_path = '/api/agent/v1/proposals/' + candidate['proposal_id'] + '/commit'
    assert call('commit_proposal', commit_payload(candidate), error=True)['code'] == 'service_unavailable'
    assert workbench.drop_response_path is None
    queried = call('get_proposal', {'proposal_id':candidate['proposal_id']})
    assert queried['state'] == 'committed'
    assert call('commit_proposal', commit_payload(candidate)) == queried['receipt']
    assert call('get_concept_map', {'map_id':graph_id})['graph']['title'] == edited['title']

    grant('project-creation', 'codex-project-grant')
    candidate = preview('project', 'create', 'codex-project-create', content={'name':'Codex 隔离项目', 'description':'仅为兼容验收',
                        'status':'paused', 'color':'#4d78e8', 'workflow_template':'standard'})
    receipt = web_approve(candidate, 'codex-project-approve')
    created_project_id = receipt['item_id']
    project_route = 'proposals/' + candidate['proposal_id'] + '/project-access'
    assert receipt['item_id'] not in {item['id'] for item in call('list_projects')['items']}
    review = local_request(project_route + '/preview', token=session)
    confirm(project_route, review, 'codex-project-access')
    assert receipt['item_id'] in {item['id'] for item in call('list_projects')['items']}

    def create_category(family, owner=None, refresh_visibility=None):
        name = 'Codex ' + family
        selection = {'family':family, 'name':name, 'project_id':owner}
        grant('category-writes', 'codex-grant-' + family, selection={**selection, 'operation':'create'})
        if refresh_visibility:
            refresh_visibility()
        content = {key:value for key,value in selection.items() if value is not None}
        candidate = preview('category', 'create', 'codex-create-' + family, content=content)
        web_approve(candidate, 'codex-approve-' + family)

    create_category('concept_map_category')
    result = {'graph_create_update':True, 'lost_commit_response_original_receipt':True,
              'project_separate_access':True, 'concept_map_category':True,
              'ntfs_cases':'unsupported_platform' if not SUPPORTED else 'passed'}
    if not SUPPORTED:
        return result

    source = workbench.repository.root.parent / 'codex-fixture.txt'
    original = '  UTF-8 中文与引号 "原文"\n第二段 🧪\n尾部空格  '.encode()
    source.write_bytes(original)
    file_grant = grant('files', 'codex-file-grant', path=str(source), purposes=['text_read','attachment_source'],
                       encoding='auto', max_bytes=10485760, duration_seconds=3600)
    file_id = file_grant['file_id']
    metadata = call('get_file_info', {'file_id':file_id})
    assert metadata in call('list_file_grants')['items'] and 'path' not in metadata
    offset, parts = 0, []
    while offset is not None:
        chunk = call('read_file', {'file_id':file_id, 'source_revision':metadata['source_revision'], 'offset':offset, 'length':12})
        parts.append(chunk['body'])
        assert chunk['offset'] == offset and offset < chunk['end_offset'] <= len(original) and 'path' not in chunk
        offset = chunk['next_offset']
        assert offset is None or offset == chunk['end_offset']
    assert len(parts) > 1 and ''.join(parts).encode() == original
    checksum = hashlib.sha256(original).hexdigest()
    file_binding = {'file_id':file_id, 'source_revision':metadata['source_revision']}
    def approve_attachment_policy(request_id):
        return grant('upload-policy', request_id, owner_kind='project', owner_id=project_id,
                     stream=True, files=[file_binding], max_bytes=10485760, duration_seconds=3600,
                     attachment_write=True, minimum_confirmation_mode='agent_attested')

    policy = approve_attachment_policy('codex-attachment-grant')
    for mode in ('file', 'stream'):
        source_selection = {'mode':mode, **(file_binding if mode == 'file' else {})}
        upload = call('create_upload', {'request_id':'codex-upload-' + mode, 'policy_id':policy['policy_id'],
                      'owner_kind':'project', 'owner_id':project_id, 'source':source_selection,
                      'filename':metadata['display_name'] if mode == 'file' else 'codex-stream.txt', 'bytes':len(original), 'sha256':checksum})
        upload_id = upload['upload_id']
        if mode == 'stream':
            config = read_json(Path(info['config_file']))
            request = Request(workbench.base_url + f'/api/agent/v1/uploads/{upload_id}/content', data=original, method='PUT',
                              headers={'Authorization':'Bearer ' + config['token'], 'X-Workbench-Workspace':workspace,
                                       'Content-Type':'application/octet-stream'})
            with urlopen(request, timeout=10) as response:
                assert response.status == 200
        assert call('complete_upload', {'upload_id':upload_id})['state'] == 'ready'
        target = call('get_attachment_target', {'owner_kind':'project', 'owner_id':project_id})
        candidate = preview('attachment', 'create', 'codex-attachment-' + mode, target_id=project_id, base_revision=target['revision'],
                            content={'owner_kind':'project', 'owner_id':project_id, 'upload_id':upload_id,
                                     'display_name':'codex-' + mode + '.txt', 'category':'', 'insert_link':False})
        assert candidate['content']['attachment']['sha256'] == checksum
        receipt = call('commit_proposal', commit_payload(candidate))
        assert call('commit_proposal', commit_payload(candidate)) == receipt
        url = workbench.base_url + f'/api/project-assets/{quote(project_id, safe="")}/{receipt["item_id"]}'
        with urlopen(url, timeout=10) as response:
            assert response.read() == original
    create_category('project_attachment_category', project_id,
                    lambda:approve_attachment_policy('codex-attachment-visibility-refresh'))

    item = workbench.repository.create_record({'type':'issue', 'project_id':project_id, 'title':'Codex 单条删除验收', 'body':'完整合成正文'})
    item = call('get_item', {'kind':'issue', 'item_id':item['id']})
    deletion = {'target_id':item['id'], 'base_revision':item['revision']}
    denied = call('prepare_proposal', {'request_id':'codex-delete-denied', 'kind':'issue', 'operation':'delete', **deletion}, error=True)
    assert denied['code'] in {'forbidden','not_found'}
    grant('deletions', 'codex-delete-grant', grants={'schema_version':1, 'grants':[
        {'capability':'items.delete', 'operations':['delete'], 'resources':[resource], 'minimum_confirmation_mode':'local_web'}]})
    candidate = preview('issue', 'delete', 'codex-delete', **deletion)
    assert '完整合成正文' in candidate['content']['target']['raw_source']
    receipt = web_approve(candidate, 'codex-delete-approve')
    assert (workbench.repository.trash_dir / receipt['trash_token']).is_file()
    grant('project-deletions', 'codex-project-delete-grant', project_id=created_project_id, asset_ids=[])
    project_to_remove = next(item for item in call('list_projects')['items'] if item['id'] == created_project_id)
    candidate = preview('project', 'delete', 'codex-project-delete', target_id=created_project_id, base_revision=project_to_remove['revision'])
    receipt = web_approve(candidate, 'codex-project-delete-approve')
    assert (workbench.repository.trash_dir / receipt['trash_token']).is_dir()
    return {**result, 'file_read_segments':len(parts), 'file_attachment':True, 'mixed_http_stream_attachment':True,
            'project_attachment_category':True, 'item_delete':True, 'project_delete':True}


def run_acceptance(codex=None):
    executable = codex or shutil.which("codex")
    if not executable:
        raise RuntimeError("未找到 Codex CLI，无法完成真实客户端验收")
    with tempfile.TemporaryDirectory(prefix="workbench-codex-acceptance-") as directory:
        base = Path(directory)
        data, credentials = base / "data", base / "credentials"
        workbench = LocalWorkbench(data, credentials)
        rpc = None
        identities = []
        try:
            project = workbench.repository.create_project({"name": "Codex 接入验收"})
            workbench.repository.ensure_document_category("验收知识")
            info = workbench.security.add_client("Codex 临时验收", ["read", "propose", "commit"], [project["id"]], ["验收知识"], workbench.base_url, kinds=["issue", "document", "todo", "info"])
            identities.append(info['client_id'])
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
            from workbench.persistence import atomic_write_text
            atomic_write_text(codex_home / "config.toml", config)
            allowed = {'PATH','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE'}
            env = {key:value for key,value in os.environ.items() if key.upper() in allowed}
            for variable, name in {'USERPROFILE':'home', 'HOME':'home', 'APPDATA':'roaming', 'LOCALAPPDATA':'local',
                                   'TEMP':'tmp', 'TMP':'tmp', 'XDG_CONFIG_HOME':'xdg-config', 'XDG_CACHE_HOME':'xdg-cache'}.items():
                path = base / name
                path.mkdir(exist_ok=True)
                env[variable] = str(path)
            drive, tail = os.path.splitdrive(env['USERPROFILE'])
            env.update(CODEX_HOME=str(codex_home), PYTHONIOENCODING='utf-8', HOMEDRIVE=drive, HOMEPATH=tail,
                       HTTP_PROXY='http://127.0.0.1:1', HTTPS_PROXY='http://127.0.0.1:1', NO_PROXY='127.0.0.1,localhost')

            rpc = RpcProcess([executable, "app-server", "--stdio"], cwd, env, terminate_tree=True)
            rpc.call("initialize", {"clientInfo": {"name": "workbench_acceptance", "version": "1.0"}, "capabilities": {"experimentalApi": True}})
            rpc.notify("initialized")
            thread = rpc.call("thread/start", {"cwd": str(cwd), "ephemeral": True, "approvalPolicy": "never", "sandbox": "read-only"})
            thread_id = thread["thread"]["id"]
            status = rpc.call("mcpServerStatus/list", {"threadId": thread_id, "serverName": "workbench", "detail": "toolsAndAuthOnly"})
            inventory = next(item for item in status["data"] if item["name"] == "workbench")
            assert sorted(inventory['tools']) == sorted(tool['name'] for tool in TOOLS)
            assert inventory["serverCapabilities"] == {"tools": {}}

            def reconnect(config_text):
                nonlocal thread_id
                atomic_write_text(codex_home / 'config.toml', config_text)
                rpc.call('config/mcpServer/reload', {})
                fresh = rpc.call('thread/start', {'cwd':str(cwd), 'ephemeral':True, 'approvalPolicy':'never', 'sandbox':'read-only'})
                thread_id = fresh['thread']['id']
                refreshed = rpc.call('mcpServerStatus/list', {'threadId':thread_id, 'serverName':'workbench', 'detail':'toolsAndAuthOnly'})
                assert refreshed['data'][0]['name'] == 'workbench' and refreshed['data'][0]['tools'] == inventory['tools']

            def call(name, args=None, error=False):
                result = rpc.call("mcpServer/tool/call", {"threadId": thread_id, "server": "workbench", "tool": "workbench_" + name, "arguments": args or {}})
                if error is not None and bool(result.get("isError")) != error:
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
            grant_route = f"clients/{info['client_id']}/category-writes"
            selected = {"family":"document_category", "name":"Codex 验收空分类"}
            current_grants = local_request(grant_route, token=session)
            grant_preview = local_request(grant_route + "/preview", "POST", {
                "workspace_id":info["workspace_id"], "expected_version":current_grants["expected_version"],
                "selection":{**selected, "project_id":None, "operation":"create"}}, session)
            grant_request = {key:grant_preview[key] for key in ("workspace_id","expected_version","preview_id","preview_digest")}
            local_request(grant_route + "/confirm", "POST", {**grant_request, "approved":True, "request_id":"codex-category-grant"}, session)
            category = call("prepare_proposal", {"request_id":"codex-category", "kind":"category", "operation":"create", "content":selected})
            category_id = category["proposal_id"]
            category_preview = call("preview_proposal", {"proposal_id":category_id})
            assert not category_preview["content"]["members"] and "category_local_details" not in category
            denied = call("commit_proposal", {"proposal_id":category_id, "version":1,
                "preview_digest":category_preview["preview_digest"],
                "confirmation":{"mode":"agent_attested", "user_confirmed":True}}, error=True)
            assert denied["code"] == "confirmation_required"
            category_route = "proposals/" + category_id
            review = local_request(category_route + "/preview", token=session)
            assert selected["name"] in review["local_category_plan"]["configuration"]["after"]
            category_result = local_request(category_route + "/approve", "POST", {"workspace_id":info["workspace_id"],
                "version":1, "preview_digest":review["preview"]["preview_digest"], "preview_ticket":review["preview_ticket"],
                "request_id":"codex-category-approve"}, session)
            assert category_result["state"] == "completed"
            assert call("get_proposal", {"proposal_id":category_id})["receipt"] == category_result["receipt"]
            workflow_route = f"clients/{info['client_id']}/workflow-writes"
            workflow_name = "Codex 工作流隔离验收"
            workflow_grants = local_request(workflow_route, token=session)
            workflow_grant = local_request(workflow_route + "/preview", "POST", {
                "workspace_id":info["workspace_id"], "expected_version":workflow_grants["expected_version"],
                "selection":{"operation":"create", "name":workflow_name}}, session)
            grant_request = {key:workflow_grant[key] for key in ("workspace_id","expected_version","preview_id","preview_digest")}
            local_request(workflow_route + "/confirm", "POST", {**grant_request,"approved":True,"request_id":"codex-workflow-grant"}, session)
            workflow = call("prepare_proposal", {"request_id":"codex-workflow","kind":"workflow",
                "operation":"create","content":{"name":workflow_name}})
            workflow_id = workflow["proposal_id"]
            workflow_preview = call("preview_proposal", {"proposal_id":workflow_id})
            assert workflow_preview["content"]["templates"]["after"]["name"] == workflow_name
            assert "workflow_local_details" not in workflow
            denied = call("commit_proposal", {"proposal_id":workflow_id, "version":1,
                "preview_digest":workflow_preview["preview_digest"],
                "confirmation":{"mode":"agent_attested","user_confirmed":True}}, error=True)
            assert denied["code"] == "confirmation_required"
            proposal_route = "proposals/" + workflow_id
            review = local_request(proposal_route + "/preview", token=session)
            assert review["local_workflow_plan"]["catalogue"]["after"][-1]["name"] == workflow_name
            workflow_result = local_request(proposal_route + "/approve", "POST", {"workspace_id":info["workspace_id"],
                "version":1,"preview_digest":review["preview"]["preview_digest"],"preview_ticket":review["preview_ticket"],
                "request_id":"codex-workflow-approve"}, session)
            assert workflow_result["state"] == "completed"
            assert call("get_proposal", {"proposal_id":workflow_id})["receipt"] == workflow_result["receipt"]
            original_config = read_json(client_config)
            expanded = workbench.security.add_client('Codex 新能力验收', ['read','propose','commit'], [project['id']], ['验收知识'],
                                                     workbench.base_url, kinds=['issue','document','todo','info'])
            identities.append(expanded['client_id'])
            reconnect(config.replace(quote(client_config), quote(expanded['config_file'])))
            local_capabilities = run_local_capabilities(call, local_request, workbench, project, expanded, session)
            workbench.security.change_client(expanded['client_id'])
            assert call('capabilities', error=True)['code'] == 'unauthenticated'
            workbench.close()
            workbench = LocalWorkbench(data, credentials)
            assert selected["name"] in workbench.repository.document_categories()
            assert workflow_name in {item["name"] for item in workbench.repository.config()["workflow_templates"]}
            original_config['base_url'] = workbench.base_url
            mismatch_config = credentials / 'wrong-workspace.json'
            private_write(mismatch_config, {**original_config, 'workspace_id':str(uuid.uuid4())})
            reconnect(config.replace(quote(client_config), quote(mismatch_config)))
            assert call('capabilities', error=True)['code'] == 'workspace_mismatch'
            private_write(client_config, original_config)
            reconnect(config)
            for receipt in receipts:
                assert call("get_item", {"kind": receipt["kind"], "item_id": receipt["item_id"]})["revision"] == receipt["revision"]
            workbench.security.change_client(info['client_id'], rotate=True)
            rotated = read_json(client_config)
            private_write(client_config, original_config)
            assert call('capabilities', error=True)['code'] == 'unauthenticated'
            private_write(client_config, rotated)
            assert call('capabilities')['workspace_id'] == info['workspace_id']
            for _ in range(121):
                probe = call('capabilities', error=None)
                if probe.get('code'):
                    assert probe['code'] == 'rate_limited' and probe['retryable']
                    break
            else:
                raise AssertionError('Codex did not receive the rate limit')
            workbench.security.change_client(info["client_id"])
            assert call("capabilities", error=True)["code"] == "unauthenticated"
            version = subprocess.run([executable, "--version"], cwd=cwd, env=env, capture_output=True,
                                     text=True, check=True, timeout=15).stdout.strip()
            return {"passed": True, "codex_version": version, "protocol": "2025-11-25", "tool_count": len(inventory["tools"]),
                    "created": [item["kind"] for item in receipts], "preview_revision_confirmation": True,
                    "issue_append_document_update": True, "local_web_independent_approval": True, "category_local_web":True, "workflow_local_web":True,
                    "retry_cancel_restart_rotate_revoke": True, "workspace_mismatch":True, "rate_limited":True, "catalog_reload":True,
                    "local_capabilities":local_capabilities,
                    "model_turns_started": 0, "user_config_changed": False}
        except Exception as error:
            diagnostics = "\n".join(rpc.errors[-12:]) if rpc else ""
            raise RuntimeError(str(error) + "\n" + diagnostics) from error
        finally:
            try:
                for client_id in identities:
                    if workbench.security.clients()[client_id]['enabled']:
                        workbench.security.change_client(client_id)
            finally:
                if rpc:
                    rpc.close()
                workbench.close()


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2))
