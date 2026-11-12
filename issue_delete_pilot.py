"""Disposable Codex pilot for one synthetic issue deletion. No model is started."""

import argparse
import hashlib
import io
import json
import socket
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from attachment_pilot import await_value, review_grant
from codex_agent_acceptance import LocalWorkbench
from codex_pilot_anchor import anchor_slot
from concept_map_pilot import (DISCOVERY_SECONDS, WINDOW_SECONDS, check_app_server, emit, emit_stopped,
                               pilot_directory, project_connector, wait_for_signal)
from server import Repository
from workbench.agent_management import client_version
from workbench.agent_security import read_json
from workbench.persistence import atomic_write_json
from workbuddy_agent_acceptance import DELETE_PILOT_CASE, DELETE_PILOT_TOOLS, pilot_discovered


SERVER = 'workbench_ag142_delete'
ASSET = b'AG142 RETAINED ASSET\n'


class ProposalCase:
    def before_approval(self, client_id):
        proposals = list(self.store.proposals.glob('*.json'))
        if not proposals:
            return None
        if len(proposals) != 1:
            raise ValueError('Expected exactly one proposal')
        proposal = read_json(proposals[0])
        if proposal['state'] != 'previewed':
            return None
        expected = {key:self.request[key] for key in ('kind', 'operation', 'request_id', 'confirmation_mode')}
        expected.update(target_id=self.target, base_revision=self.request.get('base_revision'),
                        client_id=client_id, previewed_version=proposal['version'])
        if not proposal['preview_digest'] or any(proposal.get(key) != value for key, value in expected.items()):
            raise ValueError('Proposal does not match the fixed case')
        self.check_preview(proposal)
        self.check_original()
        return {key:proposal[key] for key in ('proposal_id', 'version', 'preview_digest')}


class DeletionCase(ProposalCase):
    case_file = DELETE_PILOT_CASE

    @property
    def project_ids(self):
        return [self.project]

    def check(self, invoke, client_id, workspace, local):
        return check_case(invoke, self, client_id, workspace, local)

    def run_window(self, client_id, workspace, stop, audit, local):
        run_window(self, client_id, workspace, stop, audit)

    def final_state(self):
        return {'original_present':self.path.exists(), 'trash_count':len(self.repo.list_trash()),
                'receipt_count':len(list(self.store.receipts.glob('*.json')))}


class DeleteCase(DeletionCase):
    server = SERVER
    tools = DELETE_PILOT_TOOLS
    relay_flag = '--relay-delete-pilot'
    directory_prefix = 'workbench-ag142-issue-delete-'
    request_prefix = 'ag142-issue'
    client_name = 'AG142 单条删除'
    kinds = ['issue']

    def authorize(self, grant):
        return grant('deletions', 'DELETE', grants=self.grants)

    def check_tool_access(self, call, rejected, invoke):
        assert call('get_item', {'kind':'issue', 'item_id':self.target})['revision'] == self.revision
        rejected('get_item', {'kind':'issue', 'item_id':self.source}, 'outside the issue deletion pilot scope')
        rejected('prepare_proposal', {**self.request, 'target_id':self.source}, 'outside the issue deletion pilot scope')
        return {}

    def prompt(self, workspace):
        return (f'只用 {self.server}。capabilities 核对空间 {workspace}。get_item 使用 kind=issue、'
                f'item_id={self.target}，核对 revision 与以下固定请求一致后才调用 prepare_proposal。'
                '调用 preview_proposal，完整展示目标与引用原文、元数据、附件保留、命中引用、排序与历史保留、'
                '回收期限、警告、提案 ID、版本、摘要和执行依据。随后停止，等待用户在隔离网页独立批准。'
                '不得自行提交、恢复、清空或永久删除。版本或授权异常先报告并停止。')

    def __init__(self, repo):
        self.repo = repo
        self.project = repo.create_project({'name':'AG142 删除隔离项目'})['id']
        target = repo.create_record({'type':'issue', 'project_id':self.project, 'title':'AG142 单条删除',
                                     'body':'合成删除原文\n  保留空格与引号 "甲"  \n第二段'})
        self.target = target['id']
        repo.add_record_attachment_stream(self.target, 'ag142-retained.txt', io.BytesIO(ASSET), len(ASSET), append_to_body=False)
        source = repo.create_record({'type':'issue', 'project_id':self.project, 'title':'AG142 活动引用',
                                     'body':f'合成活动来源 [[{self.target}]]\n引用正文保留。'})
        self.source = source['id']
        self.path = repo.get_record(self.target)[1]
        self.source_path = repo.get_record(self.source)[1]
        self.asset_path = repo.attachment_path(self.target, 'ag142-retained.txt')
        self.raw = self.path.read_bytes()
        self.source_raw = self.source_path.read_bytes()
        self.readme = repo.projects_dir / self.project / 'README.md'
        self.sorting_raw = self.readme.read_bytes()
        self.revision = hashlib.sha256(self.raw).hexdigest()
        self.store = repo.agent_service.store
        self.request = {'request_id':'ag142-exact-delete', 'kind':'issue', 'operation':'delete',
                        'target_id':self.target, 'base_revision':self.revision, 'confirmation_mode':'local_web',
                        'source_note':'仅本轮合成 issue 删除验收'}
        self.grants = {'schema_version':1, 'grants':[
            {'capability':'items.delete', 'operations':['delete'], 'minimum_confirmation_mode':'local_web',
             'resources':[{'type':'item', 'kind':'issue', 'id':self.target}]}]}

    def check_retained(self):
        if (self.asset_path.read_bytes() != ASSET or self.source_path.read_bytes() != self.source_raw
                or self.readme.read_bytes() != self.sorting_raw):
            raise ValueError('Retained source, attachment or project sorting changed')

    def check_preview(self, proposal):
        content = proposal['normalized_content']
        target = content['target']
        [impact] = content['impacts']
        if (target['raw_source'].encode() != self.raw or
                impact['source']['raw_source'].encode() != self.source_raw or
                impact['source']['item']['id'] != self.source or not impact['references'] or
                not any(item['exists'] and item['retained'] for item in target['attachments'])):
            raise ValueError('Deletion preview did not preserve the complete fixed impact evidence')

    def check_original(self):
        if self.path.read_bytes() != self.raw or self.repo.list_trash() or list(self.store.receipts.glob('*.json')):
            raise ValueError('Original, trash or receipt state changed before approval')
        self.check_retained()

    def after_approval(self, binding):
        key = binding['proposal_id']
        proposal = read_json(self.store.proposals / f'{key}.json')
        if proposal['state'] != 'committed':
            return None
        receipt = read_json(self.store.receipts / f'{key}.json')
        token = receipt['trash_token']
        reopened = Repository(self.repo.root)
        index = reopened._trash_index()
        if (receipt != proposal['receipt'] or proposal['preview_digest'] != binding['preview_digest'] or
                receipt['version'] != binding['version'] or receipt['revision'] != self.revision or
                not receipt['deleted'] or receipt['item_id'] != self.target or self.path.exists() or
                (reopened.trash_dir / token).read_bytes() != self.raw or
                set(index) != {token} or index[token]['agent_operation_id'] != f'{key}-{binding["version"]}' or
                len(list(self.store.receipts.glob('*.json'))) != 1):
            raise ValueError('Original trash bytes, index or receipt failed verification')
        self.check_retained()
        return {'receipt':receipt, 'trash_sha256':self.revision, 'retained_bytes_match':True}


def check_case(invoke, case, client_id, workspace, local):
    def call(name, args=None):
        result = invoke('workbench_' + name, args or {})
        assert not result['isError'], result
        return result['structuredContent']

    def rejected(name, args=None, reason='is disabled for MCP server'):
        try:
            invoke('workbench_' + name, args or {})
        except RuntimeError as error:
            assert reason in str(error), error
        else:
            raise AssertionError('Deletion pilot forwarded an excluded call')

    assert call('capabilities')['workspace_id'] == workspace
    access_evidence = case.check_tool_access(call, rejected, invoke)
    proposal = call('prepare_proposal', case.request)
    preview = call('preview_proposal', {'proposal_id':proposal['proposal_id']})
    binding = case.before_approval(client_id)
    assert binding and preview['preview_digest'] == binding['preview_digest']
    rejected('commit_proposal', {**binding, 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}})
    assert case.before_approval(client_id) == binding
    route = 'proposals/' + binding['proposal_id']
    review = local(route + '/preview')
    assert review['preview']['content'] == preview['content']
    assert review['preview_digest'] == binding['preview_digest']
    approval = {'workspace_id':workspace, 'version':binding['version'], 'preview_digest':binding['preview_digest'],
                'preview_ticket':review['preview_ticket'], 'request_id':case.request['request_id'] + '-approve'}
    result = local(route + '/approve', approval)
    assert result['state'] == 'completed' and local(route + '/approve', approval) == result
    evidence = case.after_approval(binding)
    observed = call('get_proposal', {'proposal_id':binding['proposal_id']})['receipt']
    assert all(observed[key] == value for key, value in evidence['receipt'].items())
    return {'tool_count':len(case.tools), 'approval_replay_matches':True,
            'preapproval_original_unchanged':True, 'other_target_denied':True, 'agent_commit_disabled':True, **access_evidence, **evidence}


def run(check, anchor=None, case_type=DeleteCase):
    audit = {}
    with pilot_directory(case_type.directory_prefix) as base, anchor_slot(anchor) as slot:
        cwd = slot.root if slot else base / 'desktop-project'
        if not slot:
            cwd.mkdir()
        workbench = LocalWorkbench(base / 'data', base / 'private')
        info = token = case = None
        try:
            case = case_type(workbench.repository)
            info = workbench.security.add_client(case.client_name, ['read', 'propose', 'commit'], case.project_ids, [],
                                                 workbench.base_url, kinds=case.kinds, minimum_confirmation_mode='local_web')
            workspace, client_id = info['workspace_id'], info['client_id']
            token = read_json(Path(info['config_file']))['token']
            headers = {'Origin':workbench.base_url, 'X-Workbench-Management':'1', 'Content-Type':'application/json'}

            def local(route, payload=None):
                request = Request(workbench.base_url + '/api/local/agent-management/' + route, headers=headers,
                                  data=json.dumps(payload).encode() if payload is not None else None)
                with urlopen(request, timeout=10) as response:
                    return json.load(response)

            headers['X-Workbench-Management-Token'] = local('status')['management_token']
            trace, stop, discovered = base / 'protocol.jsonl', base / 'STOP', base / 'DISCOVERED'
            atomic_write_json(base / case.case_file, case.request)
            entry, config, catalog = project_connector(cwd, trace, info['config_file'], True, server=case.server,
                catalog=case.tools, relay_flag=case.relay_flag, slot=slot,
                port=workbench.server.server_address[1])
            if not check:
                emit({'mode':'pending_discovery', 'workspace_id':workspace, 'workbench_url':workbench.base_url,
                      'desktop_project':str(cwd), **config, 'expected_catalog':catalog, 'trace_path':str(trace),
                      'stop_file':str(stop), 'discovery_file':str(discovered), 'wait_seconds':DISCOVERY_SECONDS,
                      'managed_anchor':slot is not None, 'target_id':case.target})
            if check or (wait_for_signal(discovered, stop, DISCOVERY_SECONDS) and pilot_discovered(trace, catalog)):
                def grant(route, label, **payload):
                    current = workbench.security.clients()[client_id]
                    return review_grant(local, f'clients/{client_id}/{route}', {
                        'workspace_id':workspace, 'expected_version':client_version(current), **payload},
                        workspace, stop, check, label, request_prefix=case.request_prefix)

                if case.authorize(grant):
                    if check:
                        with check_app_server(base, cwd, entry, server=case.server, catalog=catalog) as invoke:
                            audit.update(case.check(invoke, client_id, workspace, local))
                    else:
                        case.run_window(client_id, workspace, stop, audit, local)
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
                if case:
                    audit.update(case.final_state())
            finally:
                workbench.close()
            with socket.socket() as probe:
                audit['port_closed'] = probe.connect_ex(('127.0.0.1', port)) != 0
            emit({'mode':'service_stopped', **audit})
    emit_stopped(base, slot, audit)


def run_window(case, client_id, workspace, stop, audit):
    deadline = time.monotonic() + WINDOW_SECONDS
    expires_at = int(time.time() + WINDOW_SECONDS)
    prompt = case.prompt(workspace) + '\n' + json.dumps(case.request, ensure_ascii=False, indent=2)
    emit({'mode':'ready_preview', 'execution_expires_at':expires_at, 'prompt':prompt})
    binding = await_value(lambda: case.before_approval(client_id), stop, deadline)
    if not binding:
        return
    emit({'mode':'await_web_approval', **binding, 'source_sha256':case.revision, 'original_present':True,
          'trash_count':0, 'receipt_count':0, 'execution_expires_at':expires_at})
    evidence = await_value(lambda: case.after_approval(binding), stop, deadline)
    if evidence:
        audit.update(evidence)
        emit({'mode':'committed', **evidence})
        await_value(lambda: None, stop, deadline)


def main(case_type=DeleteCase, description=__doc__):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--check', action='store_true', help='Run the isolated App Server preflight without a model')
    parser.add_argument('--anchor', type=Path, help='Use an explicitly initialized Codex pilot directory')
    args = parser.parse_args()
    run(args.check, args.anchor, case_type)


if __name__ == '__main__':
    main()
