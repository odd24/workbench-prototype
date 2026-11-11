"""Disposable AG-142 desktop concept-map create pilot. Never launches a model."""

import argparse
import json
import socket
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from codex_agent_acceptance import LocalWorkbench, RpcProcess
from workbench.agent_management import client_version
from workbench.agent_security import read_json
from workbench.agent_tools import TOOLS
from workbench.concept_maps import ConceptMapRepository
from workbench.write_coordinator import content_revision
from workbuddy_agent_acceptance import disposable_directory, isolated_environment, pilot_discovered


WINDOW_SECONDS = 1200
GRANT_REVIEW_SECONDS = 540
SERVER = 'workbench_ag142_graph'


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


def wait_for_signal(signal, stop):
    deadline = time.monotonic() + GRANT_REVIEW_SECONDS
    while time.monotonic() < deadline and not stop.exists():
        if signal.exists():
            signal.unlink()
            return True
        time.sleep(0.25)
    return False


def check_create(base, project_dir, entry, workbench, workspace, spec, local):
    rpc = RpcProcess([entry['command'], *entry['args']], project_dir,
                     {**isolated_environment(base), **entry['env']}, terminate_tree=True)
    try:
        assert rpc.call('initialize', {'protocolVersion':'2025-11-25', 'capabilities':{},
                        'clientInfo':{'name':'ag142-graph-fixture-check', 'version':'1'}})['protocolVersion'] == '2025-11-25'
        rpc.notify('notifications/initialized')
        assert {item['name'] for item in rpc.call('tools/list')['tools']} == {item['name'] for item in TOOLS}
        assert pilot_discovered(Path(entry['env']['WORKBENCH_PROBE_TRACE']))

        def call(name, arguments=None, error=None):
            result = rpc.call('tools/call', {'name':'workbench_' + name, 'arguments':arguments or {}})
            assert result['isError'] is bool(error), result
            value = result['structuredContent']
            if error:
                assert value['code'] == error, value
            return value

        caps = call('capabilities')
        assert caps['workspace_id'] == workspace and caps['kind_operations'] == {'concept_map':['create']}
        assert caps['capability_authorization']['effective'] == ['concept_maps.read', 'concept_maps.write']
        assert not call('list_concept_maps')['items']
        proposal = call('prepare_proposal', spec)
        key = {'proposal_id':proposal['proposal_id']}
        preview = call('preview_proposal', key)
        graph = spec['content']['graph']
        assert preview['content']['graph'] == graph
        path = base / 'data' / 'concept-maps' / (proposal['target_id'] + '.json')
        store = workbench.repository.agent_service.store
        assert not path.exists() and not list(store.receipts.glob('*.json'))
        version = {name:preview[name] for name in ('version', 'preview_digest')}
        call('commit_proposal', {**key, **version, 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}},
             error='confirmation_required')
        route = 'proposals/' + key['proposal_id']
        local_review = local(route + '/preview')
        assert local_review['preview']['preview_digest'] == version['preview_digest']
        assert local_review['preview']['prepared_graph'] == preview['prepared_graph']
        assert all(name in local_review['preview'] for name in ('graph_diff', 'base_graph', 'warnings', 'execution_plan'))
        assert not path.exists() and not list(store.receipts.glob('*.json'))
        approval = {**version, 'workspace_id':workspace, 'preview_ticket':local_review['preview_ticket'],
                    'request_id':'ag142-graph-pilot-approve'}
        result = local(route + '/approve', approval)
        raw = path.read_bytes()
        assert result['state'] == 'completed' and result['receipt']['item_id'] == path.stem
        assert result == local(route + '/approve', approval)
        assert path.read_bytes() == raw and list(path.parent.glob('CMAP-*.json')) == [path]
        assert len(list(store.receipts.glob('*.json'))) == 1
        receipt = call('get_proposal', key)['receipt']
        assert all(receipt[name] == value for name, value in result['receipt'].items())
        read = call('get_concept_map', {'map_id':path.stem})
        assert read['revision'] == receipt['revision'] == content_revision(raw) and read['editable_graph'] == graph
        call('prepare_proposal', {'request_id':'ag142-graph-pilot-deny-update', 'kind':'concept_map', 'operation':'update',
             'target_id':path.stem, 'base_revision':read['revision'], 'content':{'graph':graph}}, error='not_found')
        return {'catalog':len(TOOLS), 'graph_count':1, 'receipt_count':1, 'proposal_id':key['proposal_id'], 'item_id':path.stem,
                'version':version['version'], 'preview_digest':version['preview_digest'], 'revision':read['revision'],
                'preapproval_no_graph_or_receipt':True, 'self_attestation_denied':True,
                'full_management_preview':True, 'same_approval_replayed':True, 'update_denied':True}
    finally:
        rpc.close()


def run(check_only):
    audit = {}
    with disposable_directory('workbench-ag142-graph-') as directory:
        base = Path(directory).resolve()
        project_dir = base / 'desktop-project'
        project_dir.mkdir()
        workbench = LocalWorkbench(base / 'data', base / 'private')
        info = token = None
        try:
            repo = workbench.repository
            project = repo.create_project({'name':'AG142 图隔离项目'})
            repo.ensure_concept_map_category('未分类')
            resource = {'type':'project', 'id':project['id']}
            read_grant = {'capability':'concept_maps.read', 'operations':['read'], 'resources':[resource],
                          'minimum_confirmation_mode':'agent_attested'}
            # Independent client bootstrap requires a dormant entry. Only the
            # separately approved graph grant below activates graph access.
            info = workbench.security.add_client('AG142 图新建单案', ['read', 'propose', 'commit'], [], [],
                                                 workbench.base_url, kinds=[], minimum_confirmation_mode='local_web',
                                                 capability_grants={'schema_version':1, 'grants':[read_grant]})
            workspace, client_id = info['workspace_id'], info['client_id']
            token = read_json(Path(info['config_file']))['token']
            headers = {'Origin':workbench.base_url, 'X-Workbench-Management':'1', 'Content-Type':'application/json'}

            def local(route, payload=None):
                request = Request(workbench.base_url + '/api/local/agent-management/' + route,
                                  headers=headers, data=json.dumps(payload).encode() if payload is not None else None)
                with urlopen(request, timeout=10) as response:
                    return json.load(response)

            headers['X-Workbench-Management-Token'] = local('status')['management_token']
            route = f'clients/{client_id}/concept-maps'
            grants = {'schema_version':1, 'grants':[
                read_grant,
                {'capability':'concept_maps.write', 'operations':['create'], 'resources':[resource], 'minimum_confirmation_mode':'local_web'}]}
            grant = local(route + '/preview', {'workspace_id':workspace, 'grants':grants,
                          'expected_version':client_version(workbench.security.clients()[client_id])})
            approve, stop = base / 'APPROVE_GRANT', base / 'STOP'
            if not check_only:
                emit({'mode':'grant_review', 'workbench_url':workbench.base_url, 'grant_preview':grant,
                      'approval_file':str(approve), 'stop_file':str(stop), 'wait_seconds':GRANT_REVIEW_SECONDS})
            if check_only or wait_for_signal(approve, stop):
                ticket = {key:grant[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')}
                local(route + '/confirm', {**ticket, 'approved':True, 'request_id':'ag142-graph-pilot-grant'})
                graph = ConceptMapRepository.normalize({'title':'AG142 关系图', 'project_id':project['id'],
                    'focus_question':'甲与乙有什么联系？',
                    'nodes':[{'id':'a', 'text':'甲', 'x':100, 'y':120}, {'id':'b', 'text':'乙', 'x':420, 'y':220}],
                    'edges':[{'id':'edge', 'from':'a', 'to':'b', 'label':'联系'}]})
                spec = {'request_id':'ag142-graph-pilot-create', 'kind':'concept_map', 'operation':'create',
                        'confirmation_mode':'local_web', 'content':{'graph':graph}}
                trace = base / 'protocol.jsonl'
                entry = {'command':sys.executable, 'args':[str(Path(__file__).with_name('workbuddy_agent_acceptance.py')), '--relay'],
                         'env':{'WORKBENCH_PROBE_TRACE':str(trace), 'WORKBENCH_PROBE_CONFIG':info['config_file']}}
                if check_only:
                    audit.update(check_create(base, project_dir, entry, workbench, workspace, spec, local))
                else:
                    prompt = (f'只用 {SERVER}。用 capabilities 核对空间 {workspace}，查该项目是否已有图。'
                              '为空时仅准备下列完整提案，调用 preview_proposal 展示完整图、原图、全部字段、差异、警告、版本、摘要和执行依据，然后停止。'
                              '等待用户在隔离工作台网页独立批准。禁止自行提交、访问其他连接器、读取文件或执行命令。\n'
                              + json.dumps(spec, ensure_ascii=False, indent=2))
                    emit({'mode':'ready', 'workbench_url':workbench.base_url, 'workspace_id':workspace,
                          'desktop_project':str(project_dir), 'config':{'mcpServers':{SERVER:entry}},
                          'expected_catalog':[tool['name'] for tool in TOOLS],
                          'trace_path':str(trace), 'stop_file':str(stop), 'wait_seconds':WINDOW_SECONDS, 'prompt':prompt})
                    deadline = time.monotonic() + WINDOW_SECONDS
                    while not stop.exists() and time.monotonic() < deadline:
                        time.sleep(0.25)
                    store = repo.agent_service.store
                    audit.update(graph_count=len(list((repo.root / 'concept-maps').glob('CMAP-*.json'))),
                                 receipt_count=len(list(store.receipts.glob('*.json'))))
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
            finally:
                workbench.close()
    with socket.socket() as sock:
        audit['port_closed'] = sock.connect_ex(('127.0.0.1', port)) != 0
    emit({'mode':'stopped', 'temporary_directory_removed':not base.exists(), **audit})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Run the isolated synthetic approval and replay, then exit')
    run(parser.parse_args().check)
