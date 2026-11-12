"""Isolated AG-142 Codex attachment pilot. Never starts a model turn."""

import argparse
import hashlib
import json
import socket
import time
from pathlib import Path
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from codex_agent_acceptance import LocalWorkbench
from codex_pilot_anchor import anchor_slot
from concept_map_pilot import (DISCOVERY_SECONDS, GRANT_REVIEW_SECONDS, WINDOW_SECONDS, check_app_server,
                               emit, emit_stopped, pilot_directory, project_connector, wait_for_signal)
from server import Repository
from workbench.agent_management import client_version
from workbench.agent_security import read_json
from workbench.persistence import atomic_write_json
from workbuddy_agent_acceptance import ATTACHMENT_COMMIT_GATE, ATTACHMENT_PILOT_TOOLS, STREAM_PILOT_TOOLS, pilot_discovered


SERVER = 'workbench_ag142_attachment'
SOURCE = '  UTF-8 中文与引号 "原文"\n第二段 🧪\n尾部空格  '.encode()
FILENAME = 'AG142-attachment.txt'
SHA256 = hashlib.sha256(SOURCE).hexdigest()


def review_grant(local, route, payload, workspace, stop, check, label):
    preview = local(route + '/preview', payload)
    signal = stop.with_name('APPROVE_' + label)
    if not check:
        if signal.exists():
            return None
        emit({'mode':'review_' + label.lower(), 'workspace_id':workspace, 'preview':preview,
              'approval_file':str(signal), 'wait_seconds':GRANT_REVIEW_SECONDS})
        if not wait_for_signal(signal, stop, GRANT_REVIEW_SECONDS):
            return None
    ticket = {key:preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')}
    return local(route + '/confirm', {**ticket, 'approved':True, 'request_id':'ag142-attachment-' + label.lower()})


def proposal_binding(repo, project_id, client_id, upload_args):
    service = repo.agent_service
    candidates = list(service.store.proposals.glob('*.json'))
    if not candidates:
        return None
    if len(candidates) != 1:
        raise ValueError('Expected exactly one isolated attachment proposal')
    proposal = read_json(candidates[0])
    if proposal['state'] != 'previewed':
        return None
    view = proposal['normalized_content']
    mode = 'local_web' if upload_args['source']['mode'] == 'stream' else 'agent_attested'
    expected_proposal = {'client_id':client_id, 'kind':'attachment', 'operation':'create',
                         'confirmation_mode':mode, 'previewed_version':proposal['version'],
                         'request_id':f'ag142-{upload_args["source"]["mode"]}-prepare'}
    expected_view = {'owner_id':project_id, 'owner_kind':'project', 'policy_id':upload_args['policy_id'],
                     'display_name':FILENAME, 'category':'', 'insert_link':False,
                     'source':{'filename':FILENAME, 'source':upload_args['source'], 'sha256':SHA256, 'bytes':len(SOURCE)}}
    if not proposal['preview_digest'] or any(proposal.get(key) != value for key, value in expected_proposal.items()):
        raise ValueError('Proposal does not match the isolated attachment case')
    if any(view.get(key) != value for key, value in expected_view.items()):
        raise ValueError('Attachment candidate differs from the fixed source or target')
    if service.uploads.load(view['upload_id'])['state'] != 'ready':
        raise ValueError('Attachment source is not ready')
    if repo.project_assets(project_id) or list(service.store.receipts.glob('*.json')):
        raise ValueError('Unexpected formal attachment or receipt before confirmation')
    return {key:proposal[key] for key in ('proposal_id', 'version', 'preview_digest')}


def stream_session(repo, workspace, client_id, upload_args):
    sessions = repo.agent_service.uploads.catalog()
    if not sessions:
        return None
    if len(sessions) != 1:
        raise ValueError('Expected exactly one isolated stream session')
    [session] = sessions
    expected = {'workspace_id':workspace, 'client_id':client_id, 'request_id':upload_args['request_id'],
                'policy_id':upload_args['policy_id'], 'source':{'mode':'stream'}, 'state':'created',
                'filename':FILENAME, 'declared_bytes':len(SOURCE), 'declared_sha256':SHA256,
                'sealed':None, 'removed':False, 'error':None}
    if (any(session.get(key) != value for key, value in expected.items()) or
            session['owner']['kind'] != 'project' or session['owner']['id'] != upload_args['owner_id']):
        raise ValueError('Stream session does not match this fixed case')
    return session['upload_id']


def put_stream(workbench, workspace, client_id, upload_args, expected_id, token):
    if stream_session(workbench.repository, workspace, client_id, upload_args) != expected_id:
        raise ValueError('The observed stream session changed before transmission')
    connection = HTTPConnection('127.0.0.1', workbench.server.server_address[1], timeout=10)
    try:
        connection.request('PUT', f'/api/agent/v1/uploads/{expected_id}/content', body=SOURCE, headers={
            'Authorization':'Bearer ' + token, 'X-Workbench-Workspace':workspace,
            'Content-Type':'application/octet-stream', 'Content-Length':str(len(SOURCE))})
        with connection.getresponse() as response:
            if response.status != 200:
                raise RuntimeError(f'Fixed stream PUT returned HTTP {response.status}; query the original session')
            response.read(65536)
    finally:
        connection.close()
    session = workbench.repository.agent_service.uploads.load(expected_id)
    if session['sealed'] != {'bytes':len(SOURCE), 'sha256':SHA256}:
        raise ValueError('Server did not seal the expected stream bytes')


def committed_evidence(repo, project_id, binding):
    service = repo.agent_service
    receipt_path = service.store.receipts / f'{binding["proposal_id"]}.json'
    proposal = read_json(service.store.proposals / receipt_path.name)
    if proposal['state'] != 'committed':
        return None
    receipt = read_json(receipt_path)
    assert receipt == proposal['receipt'] and receipt['version'] == binding['version']
    assert proposal['preview_digest'] == binding['preview_digest']
    assert len(list(service.store.receipts.glob('*.json'))) == 1
    reopened = Repository(repo.root)
    assert [asset['id'] for asset in reopened.project_assets(project_id)] == [receipt['item_id']]
    assert reopened.project_asset_path(project_id, receipt['item_id']).read_bytes() == SOURCE
    assert receipt['attachment']['sha256'] == SHA256 and service.uploads.load(receipt['upload_id'])['state'] == 'consumed'
    return {'receipt':receipt, 'disk_sha256':SHA256, 'consumed':True}


def check_attachment(invoke, repo, workspace, client_id, project_id, upload_args, gate, *, put=None, local=None):
    def call(name, arguments):
        result = invoke('workbench_' + name, arguments)
        assert not result['isError'], result
        return result['structuredContent']

    def rejected(tool, arguments, message='outside the attachment pilot scope'):
        try:
            invoke('workbench_' + tool, arguments)
        except RuntimeError as error:
            assert message in str(error), error
        else:
            raise AssertionError('Relay accepted an excluded attachment pilot call')

    assert call('capabilities', {})['workspace_id'] == workspace
    rejected('read_file', {}, 'is disabled for MCP server')
    rejected('prepare_proposal', {'kind':'issue', 'operation':'create', 'request_id':'denied-pilot-issue'})
    if put is None:
        meta = call('get_file_info', {'file_id':upload_args['source']['file_id']})
        assert meta['purposes'] == ['attachment_source'] and meta['sha256'] == SHA256 and 'path' not in meta
    upload = call('create_upload', upload_args)['upload_id']
    if put is not None:
        try:
            put('00000000-0000-0000-0000-000000000000')
        except ValueError as error:
            assert 'changed before transmission' in str(error), error
        else:
            raise AssertionError('Fixed helper accepted a different session')
        put(upload)
        assert not repo.project_assets(project_id)
    assert call('complete_upload', {'upload_id':upload})['state'] == 'ready'
    target = call('get_attachment_target', {'owner_kind':'project', 'owner_id':project_id})
    proposal = call('prepare_proposal', {'request_id':'ag142-stream-prepare' if put else 'ag142-file-prepare',
                    'kind':'attachment', 'operation':'create',
                    'target_id':project_id, 'base_revision':target['revision'],
                    'confirmation_mode':'local_web' if put else 'agent_attested',
                    'content':{'owner_kind':'project', 'owner_id':project_id, 'upload_id':upload,
                               'display_name':FILENAME, 'category':'', 'insert_link':False}})
    preview = call('preview_proposal', {'proposal_id':proposal['proposal_id']})
    assert preview['content']['attachment']['sha256'] == SHA256 and preview['execution_plan']
    binding = proposal_binding(repo, project_id, client_id, upload_args)
    args = {**binding, 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
    rejected('commit_proposal', args, 'is disabled for MCP server' if put else 'outside the attachment pilot scope')
    assert proposal_binding(repo, project_id, client_id, upload_args) == binding
    if put:
        route = 'proposals/' + binding['proposal_id']
        review = local(route + '/preview')
        assert review['preview_digest'] == binding['preview_digest']
        assert review['preview']['content'] == preview['content']
        assert proposal_binding(repo, project_id, client_id, upload_args) == binding
        approval = {'workspace_id':workspace, 'version':binding['version'], 'preview_digest':binding['preview_digest'],
                    'preview_ticket':review['preview_ticket'], 'request_id':'ag142-stream-approval'}
        result = local(route + '/approve', approval)
        assert result['state'] == 'completed' and local(route + '/approve', approval) == result
        receipt = result['receipt']
        rejected('commit_proposal', args, 'is disabled for MCP server')
        verified = {'fixed_stream_put':True, 'wrong_session_denied':True, 'local_web_approved':True}
    else:
        atomic_write_json(gate, binding)
        rejected('commit_proposal', {**args, 'preview_digest':'0' * 64})
        receipt = call('commit_proposal', args)
        assert call('commit_proposal', args) == receipt
        verified = {'wrong_digest_denied':True}
    assert call('get_proposal', {'proposal_id':binding['proposal_id']})['receipt'] == receipt
    evidence = committed_evidence(repo, project_id, binding)
    assert evidence['receipt'] == receipt
    return {'relay_preconfirmation_denied':True, 'replay_matches':True, **verified, **evidence}


def preview_prompt(workspace, project_id, upload_args):
    return (f'只用 {SERVER}。用 capabilities 核对空间 {workspace}。用 get_file_info 核对固定文件来源的 '
            'file_id、source_revision、字节数和摘要。按下列 JSON 调用 create_upload，并用 complete_upload 得到 ready。'
            f'用 get_attachment_target 获取项目 {project_id} 的当前 revision。只准备一个 attachment/create 提案，'
            f'目标为该项目，使用本次 upload_id，request_id=ag142-file-prepare，display_name={FILENAME}，'
            'category 为空，insert_link=false，confirmation_mode=agent_attested。用 preview_proposal 完整展示'
            '目标、来源与附件字段、差异、警告、版本、摘要、执行依据和确认方式，随后停止并等待用户新消息。'
            '禁止调用 commit_proposal、直接读文件或使用终端。任何错误先报告并停止。\n'
            + json.dumps(upload_args, ensure_ascii=False, indent=2))


def await_value(get, stop, deadline):
    while not stop.exists() and time.monotonic() < deadline:
        value = get()
        if value is not None:
            return value
        time.sleep(0.25)
    return None


def run(check, source_mode='file', anchor=None):
    audit = {}
    stream = source_mode == 'stream'
    with pilot_directory('workbench-ag142-attachment-') as base, anchor_slot(anchor) as slot:
        cwd = slot.root if slot else base / 'desktop-project'
        if not slot:
            cwd.mkdir()
        workbench = LocalWorkbench(base / 'data', base / 'private')
        repo = workbench.repository
        info = token = project_id = None
        try:
            project_id = repo.create_project({'name':'AG142 附件隔离项目'})['id']
            info = workbench.security.add_client('AG142 单文件附件', ['read', 'propose', 'commit'],
                                                 [project_id], [], workbench.base_url, kinds=['issue'])
            workspace, client_id = info['workspace_id'], info['client_id']
            token = read_json(Path(info['config_file']))['token']
            headers = {'Origin':workbench.base_url, 'X-Workbench-Management':'1', 'Content-Type':'application/json'}

            def local(route, payload=None):
                request = Request(workbench.base_url + '/api/local/agent-management/' + route, headers=headers,
                                  data=json.dumps(payload).encode() if payload is not None else None)
                with urlopen(request, timeout=10) as response:
                    return json.load(response)

            headers['X-Workbench-Management-Token'] = local('status')['management_token']
            trace, stop = base / 'protocol.jsonl', base / 'STOP'
            discovered, gate = base / 'DISCOVERED', base / ATTACHMENT_COMMIT_GATE
            entry, config, catalog = project_connector(cwd, trace, info['config_file'], True, server=SERVER,
                catalog=STREAM_PILOT_TOOLS if stream else ATTACHMENT_PILOT_TOOLS,
                relay_flag='--relay-stream-pilot' if stream else '--relay-attachment-pilot',
                slot=slot, port=workbench.server.server_address[1])
            context = {'workbench_url':workbench.base_url, 'workspace_id':workspace, 'desktop_project':str(cwd),
                       **config, 'source_mode':source_mode, 'expected_catalog':catalog,
                       'trace_path':str(trace), 'stop_file':str(stop), 'managed_anchor':slot is not None}
            if not check:
                emit({'mode':'pending_discovery', **context, 'discovery_file':str(discovered), 'wait_seconds':DISCOVERY_SECONDS})
            if check or (wait_for_signal(discovered, stop, DISCOVERY_SECONDS) and pilot_discovered(trace, catalog)):
                def grant(route, label, **selection):
                    return review_grant(local, f'clients/{client_id}/{route}', {
                        'workspace_id':workspace, 'expected_version':client_version(workbench.security.clients()[client_id]),
                        **selection}, workspace, stop, check, label)

                source_selection = {'mode':'stream'} if stream else None
                if not stream:
                    source = base / FILENAME
                    source.write_bytes(SOURCE)
                    file = grant('files', 'FILE', path=str(source), purposes=['attachment_source'],
                                 encoding='binary', max_bytes=len(SOURCE), duration_seconds=3600)
                    if file:
                        [meta] = local(f'clients/{client_id}/files')['items']
                        assert meta['file_id'] == file['file_id'] and meta['sha256'] == SHA256
                        source_selection = {'mode':'file', **{key:meta[key] for key in ('file_id', 'source_revision')}}
                if source_selection:
                    files = [] if stream else [{key:source_selection[key] for key in ('file_id', 'source_revision')}]
                    policy = grant('upload-policy', 'POLICY', owner_kind='project', owner_id=project_id, stream=stream,
                                   files=files, max_bytes=len(SOURCE), duration_seconds=3600, attachment_write=True,
                                   minimum_confirmation_mode='local_web' if stream else 'agent_attested')
                    if policy:
                        upload_args = {'request_id':f'ag142-{source_mode}-stage', 'policy_id':policy['policy_id'], 'owner_kind':'project',
                                       'owner_id':project_id, 'source':source_selection, 'filename':FILENAME,
                                       'bytes':len(SOURCE), 'sha256':SHA256}

                        def put(upload_id):
                            put_stream(workbench, workspace, client_id, upload_args, upload_id, token)

                        if check:
                            with check_app_server(base, cwd, entry, server=SERVER, catalog=catalog) as invoke:
                                audit.update(check_attachment(invoke, repo, workspace, client_id, project_id, upload_args, gate,
                                                              put=put if stream else None, local=local))
                        elif stream:
                            run_stream_window(repo, project_id, client_id, upload_args, workspace, put, stop, audit)
                        else:
                            run_desktop_window(repo, project_id, client_id, upload_args, workspace, gate, stop, audit)
        finally:
            port = workbench.server.server_address[1]
            try:
                if info:
                    workbench.security.change_client(info['client_id'])
                if token:
                    request = Request(workbench.base_url + '/api/agent/v1/capabilities', headers={
                        'Authorization':'Bearer ' + token, 'X-Workbench-Workspace':workspace})
                    try:
                        with urlopen(request, timeout=5):
                            raise AssertionError('Revoked pilot credential still accepted')
                    except HTTPError as error:
                        with error:
                            assert error.code == 401
                    audit['revoked_credential_denied'] = True
                audit.update(attachment_count=len(repo.project_assets(project_id)) if project_id else 0,
                             receipt_count=len(list(repo.agent_service.store.receipts.glob('*.json'))))
            finally:
                workbench.close()
            with socket.socket() as sock:
                audit['port_closed'] = sock.connect_ex(('127.0.0.1', port)) != 0
            emit({'mode':'service_stopped', **audit})
    emit_stopped(base, slot, audit)


def run_desktop_window(repo, project_id, client_id, upload_args, workspace, gate, stop, audit):
    deadline = time.monotonic() + WINDOW_SECONDS
    expires_at = int(time.time() + WINDOW_SECONDS)
    emit({'mode':'ready_preview', 'execution_expires_at':expires_at, 'prompt':preview_prompt(workspace, project_id, upload_args)})
    get_binding = lambda: proposal_binding(repo, project_id, client_id, upload_args)
    binding = await_value(get_binding, stop, deadline)
    signal = gate.with_name('ENABLE_COMMIT')
    if not binding or signal.exists():
        return
    emit({'mode':'await_user_confirmation', **binding, 'attachment_count':0, 'receipt_count':0,
          'approval_file':str(signal), 'execution_expires_at':expires_at})
    if not wait_for_signal(signal, stop, max(0, deadline - time.monotonic())) or get_binding() != binding:
        return
    atomic_write_json(gate, binding)
    prompt = (f'我已核对完整预览，明确确认下列当前提案版本及摘要。只用 {SERVER} 提交该版本一次，'
              'confirmation 使用 agent_attested 且 user_confirmed=true。随后查询原提案与回执。失败或超时先查原提案，禁止重建。\n'
              + json.dumps(binding, ensure_ascii=False, indent=2))
    emit({'mode':'ready_commit', 'execution_expires_at':expires_at, 'prompt':prompt})
    report_commit(repo, project_id, binding, stop, deadline, audit)


def run_stream_window(repo, project_id, client_id, upload_args, workspace, put, stop, audit):
    deadline = time.monotonic() + WINDOW_SECONDS
    expires_at = int(time.time() + WINDOW_SECONDS)
    prompt = (f'只用 {SERVER}。用 capabilities 核对空间 {workspace}，再按下列 JSON 创建唯一原始流暂存会话。'
              '展示 upload_id 和会话状态后停止，等待本机助手。不要读取文件、上传字节、执行命令、完成会话或准备提案。\n'
              + json.dumps(upload_args, ensure_ascii=False, indent=2))
    emit({'mode':'ready_stream_session', 'execution_expires_at':expires_at, 'prompt':prompt})
    upload = await_value(lambda: stream_session(repo, workspace, client_id, upload_args), stop, deadline)
    signal = stop.with_name('SEND_STREAM')
    if not upload or signal.exists():
        return
    emit({'mode':'await_stream_put', 'upload_id':upload, 'bytes':len(SOURCE), 'sha256':SHA256,
          'send_file':str(signal), 'execution_expires_at':expires_at})
    if not wait_for_signal(signal, stop, max(0, deadline - time.monotonic())):
        return
    put(upload)
    prompt = (f'只用 {SERVER}。本机助手已向原会话 {upload} 写入并核对 {len(SOURCE)} 字节与摘要 {SHA256}。'
              f'对这一个会话调用 complete_upload 得到 ready，再用 get_attachment_target 读取项目 {project_id} 的 revision。'
              f'只准备该项目的 attachment/create，request_id=ag142-stream-prepare，使用原 upload_id、display_name={FILENAME}、'
              '空分类、insert_link=false、confirmation_mode=local_web。调用 preview_proposal 完整展示目标、来源与附件字段、'
              '差异、警告、版本、摘要和执行依据，随后停止，等待用户在隔离网页独立批准。不要重传、换会话或自行提交。')
    emit({'mode':'ready_stream_preview', 'execution_expires_at':expires_at, 'prompt':prompt})
    binding = await_value(lambda: proposal_binding(repo, project_id, client_id, upload_args), stop, deadline)
    if binding:
        emit({'mode':'await_web_approval', **binding, 'attachment_count':0, 'receipt_count':0,
              'execution_expires_at':expires_at})
        report_commit(repo, project_id, binding, stop, deadline, audit)


def report_commit(repo, project_id, binding, stop, deadline, audit):
    evidence = await_value(lambda: committed_evidence(repo, project_id, binding), stop, deadline)
    if evidence:
        audit.update(evidence)
        emit({'mode':'committed', **evidence})
        await_value(lambda: None, stop, deadline)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('file', 'stream'), default='file')
    parser.add_argument('--anchor', type=Path, help='Use an explicitly initialized Codex pilot directory')
    parser.add_argument('--check', action='store_true', help='Run the isolated App Server preflight without a model')
    args = parser.parse_args()
    run(args.check, args.source, args.anchor)
