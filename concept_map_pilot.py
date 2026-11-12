"""Disposable AG-142 desktop concept-map pilot. Never launches a model."""

import argparse
import json
import shutil
import socket
import sys
import time
import tomllib
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from codex_agent_acceptance import LocalWorkbench, RpcProcess
from workbench.agent_management import client_version
from workbench.agent_security import read_json
from workbench.agent_tools import TOOLS
from workbench.concept_maps import ConceptMapRepository
from workbench.write_coordinator import content_revision
from workbuddy_agent_acceptance import GRAPH_PILOT_TOOLS, disposable_directory, isolated_environment, pilot_discovered


WINDOW_SECONDS = 1200
DISCOVERY_SECONDS = 1200
GRANT_REVIEW_SECONDS = 540
SERVER = 'workbench_ag142_graph'


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


def wait_for_signal(signal, stop, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not stop.exists():
        if signal.exists():
            signal.unlink()
            return not stop.exists() and time.monotonic() < deadline
        time.sleep(0.25)
    return False


def server_toml(name, entry, catalog=()):
    quote = json.dumps
    lines = [f'[mcp_servers.{name}]', f'command = {quote(entry["command"])}', f'args = {quote(entry["args"])}']
    if catalog:
        lines.append(f'enabled_tools = {quote(catalog)}')
    lines.append(f'[mcp_servers.{name}.env]')
    lines.extend(f'{key} = {quote(value)}' for key, value in entry['env'].items())
    return '\n'.join(lines) + '\n'


def project_connector(project_dir, trace, client_config, codex, *, server=SERVER,
                      catalog=GRAPH_PILOT_TOOLS, relay_flag='--relay-graph-pilot'):
    entry = {'command':sys.executable, 'args':[str(Path(__file__).with_name('workbuddy_agent_acceptance.py')), '--relay'],
             'env':{'WORKBENCH_PROBE_TRACE':str(trace), 'WORKBENCH_PROBE_CONFIG':client_config}}
    if not codex:
        return entry, {'config':{'mcpServers':{SERVER:entry}}}, [tool['name'] for tool in TOOLS]
    entry['args'].append(relay_flag)
    config = project_dir / '.codex' / 'config.toml'
    config.parent.mkdir()
    text = '[mcp_servers.workbench]\nenabled = false\n\n' + server_toml(server, entry, catalog)
    assert tomllib.loads(text)['mcp_servers'] == {
        'workbench':{'enabled':False}, server:{**entry, 'enabled_tools':list(catalog)}}
    config.write_text(text, encoding='utf-8')
    return entry, {'config_path':str(config), 'config_text':text,
                   'project_disabled_servers':['workbench']}, list(catalog)


@contextmanager
def check_app_server(base, project_dir, entry, *, server=SERVER, catalog=GRAPH_PILOT_TOOLS):
    executable = shutil.which('codex')
    if not executable:
        raise RuntimeError('Codex CLI is required for the isolated App Server check')
    home = base / 'codex-home'
    home.mkdir()
    untrusted = base / 'untrusted-project'
    untrusted.mkdir()
    shutil.copytree(project_dir / '.codex', untrusted / '.codex')
    control = {**entry, 'args':entry['args'][:-1], 'env':{
        **entry['env'], 'WORKBENCH_PROBE_TRACE':str(base / 'control-protocol.jsonl')}}
    config = '\n'.join([
        'model = "workbench-test-model"', 'model_provider = "workbench_test"',
        '[model_providers.workbench_test]', 'name = "Local protocol acceptance (no inference)"',
        'base_url = "http://127.0.0.1:1/v1"', 'wire_api = "responses"', 'requires_openai_auth = false',
        '[analytics]', 'enabled = false', '[features]', 'plugins = false', 'apps = false', 'remote_plugin = false',
        f'[projects.{json.dumps(str(project_dir))}]', 'trust_level = "trusted"',
        f'[projects.{json.dumps(str(untrusted))}]', 'trust_level = "untrusted"', server_toml('workbench', control)])
    (home / 'config.toml').write_text(config, encoding='utf-8')
    rpc = RpcProcess([executable, 'app-server', '--stdio'], project_dir,
                     {**isolated_environment(base), 'CODEX_HOME':str(home)}, terminate_tree=True)
    try:
        rpc.call('initialize', {'clientInfo':{'name':'workbench_graph_pilot', 'version':'1'},
                                'capabilities':{'experimentalApi':True}})
        rpc.notify('initialized')

        def inventory(cwd):
            thread = rpc.call('thread/start', {'cwd':str(cwd), 'ephemeral':True, 'approvalPolicy':'never', 'sandbox':'read-only'})
            key = thread['thread']['id']
            status = rpc.call('mcpServerStatus/list', {'threadId':key, 'detail':'toolsAndAuthOnly'})
            return key, {item['name']:set(item['tools']) for item in status['data']}

        _, outside = inventory(untrusted)
        assert outside.get('workbench') == {tool['name'] for tool in TOOLS} and server not in outside, outside
        thread_id, inside = inventory(project_dir)
        assert inside.get('workbench', set()) == set() and inside.get(server) == set(catalog), inside
        assert pilot_discovered(Path(entry['env']['WORKBENCH_PROBE_TRACE']), catalog)

        def invoke(tool, arguments, server_name=server):
            return rpc.call('mcpServer/tool/call', {'threadId':thread_id, 'server':server_name, 'tool':tool,
                                                   'arguments':arguments})

        try:
            invoke('workbench_capabilities', {}, server_name='workbench')
        except RuntimeError as error:
            assert '-32603' in str(error), error
        else:
            raise AssertionError('Trusted project could call the inherited workbench server')
        yield invoke
    finally:
        rpc.close()


@contextmanager
def check_connection(base, project_dir, entry, codex):
    trace = Path(entry['env']['WORKBENCH_PROBE_TRACE'])
    expected = GRAPH_PILOT_TOOLS if codex else [tool['name'] for tool in TOOLS]
    rpc = RpcProcess([entry['command'], *entry['args']], project_dir,
                     {**isolated_environment(base), **entry['env']}, terminate_tree=True)
    try:
        assert rpc.call('initialize', {'protocolVersion':'2025-11-25', 'capabilities':{},
                        'clientInfo':{'name':'ag142-graph-fixture-check', 'version':'1'}})['protocolVersion'] == '2025-11-25'
        rpc.notify('notifications/initialized')
        assert {item['name'] for item in rpc.call('tools/list')['tools']} == set(expected)
        assert pilot_discovered(trace, expected)

        def invoke(tool, arguments):
            return rpc.call('tools/call', {'name':tool, 'arguments':arguments})

        if codex:
            try:
                invoke('workbench_commit_proposal', {})
            except RuntimeError as error:
                assert 'Tool is outside the graph pilot allowlist' in str(error), error
            else:
                raise AssertionError('Graph relay accepted an excluded tool')
        else:
            yield invoke
    finally:
        rpc.close()
    if codex:
        # Give the App Server a fresh trace so the direct probe cannot satisfy its handshake check.
        trace.unlink()
        with check_app_server(base, project_dir, entry) as invoke:
            yield invoke


def check_graph(base, project_dir, entry, workbench, workspace, spec, local, codex):
    with check_connection(base, project_dir, entry, codex) as invoke:

        def call(name, arguments=None, error=None):
            result = invoke('workbench_' + name, arguments or {})
            assert result['isError'] is bool(error), result
            value = result['structuredContent']
            if error:
                assert value['code'] == error, value
            return value

        updating = spec['operation'] == 'update'
        target_id = spec.get('target_id')
        graph = spec['content']['graph']
        caps = call('capabilities')
        assert caps['workspace_id'] == workspace and caps['kind_operations'] == {'concept_map':[spec['operation']]}
        assert caps['capability_authorization']['effective'] == ['concept_maps.read', 'concept_maps.write']
        call('prepare_proposal', {'request_id':'ag142-graph-pilot-deny-issue', 'kind':'issue', 'operation':'create',
             'content':{'title':'不得创建', 'body':'隔离拒绝对照', 'project_id':spec['content']['graph']['project_id']}},
             error='forbidden')
        assert [item['id'] for item in call('list_concept_maps')['items']] == ([target_id] if updating else [])
        graph_dir = base / 'data' / 'concept-maps'
        if updating:
            current = call('get_concept_map', {'map_id':target_id})
            before = (graph_dir / f'{target_id}.json').read_bytes()
            assert current['revision'] == spec['base_revision'] == content_revision(before)
            assert {**current['editable_graph'], 'title':graph['title']} == graph
        else:
            before = None
        proposal = call('prepare_proposal', spec)
        key = {'proposal_id':proposal['proposal_id']}
        preview = call('preview_proposal', key)
        assert preview['content']['graph'] == graph
        assert not updating or proposal['target_id'] == target_id
        path = graph_dir / (proposal['target_id'] + '.json')
        history_dir = workbench.repository.history_dir / path.stem
        store = workbench.repository.agent_service.store

        def assert_unpublished():
            assert (path.read_bytes() if path.exists() else None) == before
            assert not list(history_dir.glob('*.json')) and not list(store.receipts.glob('*.json'))

        assert_unpublished()
        version = {name:preview[name] for name in ('version', 'preview_digest')}
        if not codex:
            call('commit_proposal', {**key, **version, 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}},
                 error='confirmation_required')
        route = 'proposals/' + key['proposal_id']
        local_review = local(route + '/preview')
        assert local_review['preview']['preview_digest'] == version['preview_digest']
        assert local_review['preview']['prepared_graph'] == preview['prepared_graph']
        assert all(name in local_review['preview'] for name in ('graph_diff', 'base_graph', 'warnings', 'execution_plan'))
        if updating:
            assert local_review['preview']['base_graph'] == json.loads(before)
            assert local_review['preview']['base_revision'] == spec['base_revision']
        assert_unpublished()
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
        if updating:
            [history] = history_dir.glob('*.json')
            assert history.read_bytes() == before and raw != before
            call('prepare_proposal', {**spec, 'request_id':'ag142-graph-pilot-deny-stale'}, error='revision_conflict')
            call('prepare_proposal', {'request_id':'ag142-graph-pilot-deny-create', 'kind':'concept_map', 'operation':'create',
                 'content':{'graph':graph}}, error='not_found')
            assert len(list(store.proposals.glob('*.json'))) == 1 and path.read_bytes() == raw
        else:
            call('prepare_proposal', {'request_id':'ag142-graph-pilot-deny-update', 'kind':'concept_map', 'operation':'update',
                 'target_id':path.stem, 'base_revision':read['revision'], 'content':{'graph':graph}}, error='not_found')
        return {'catalog':len(GRAPH_PILOT_TOOLS if codex else TOOLS), 'graph_count':1, 'receipt_count':1,
                'proposal_id':key['proposal_id'], 'item_id':path.stem,
                'version':version['version'], 'preview_digest':version['preview_digest'], 'revision':read['revision'],
                **({'preapproval_original_bytes_unchanged':True, 'raw_history_matches':True, 'stale_revision_denied':True,
                    'create_denied':True} if updating else {'preapproval_no_graph_or_receipt':True, 'update_denied':True}),
                **({'app_server_project_guard':True, 'relay_commit_denied':True} if codex else {'self_attestation_denied':True}),
                'full_management_preview':True, 'same_approval_replayed':True,
                'unrelated_kind_denied':True}


@contextmanager
def pilot_directory(prefix='workbench-ag142-graph-'):
    stopped = False
    try:
        with disposable_directory(prefix) as directory:
            yield Path(directory).resolve()
            stopped = True
    except OSError as error:
        if stopped:
            emit({'mode':'cleanup_failed', 'temporary_directory_removed':False,
                  'errno':error.errno, 'winerror':getattr(error, 'winerror', None)})
            raise SystemExit(1) from None
        raise


def run(check_only, codex=False, operation='create'):
    audit = {}
    with pilot_directory() as base:
        project_dir = base / 'desktop-project'
        project_dir.mkdir()
        workbench = LocalWorkbench(base / 'data', base / 'private')
        info = token = None
        try:
            repo = workbench.repository
            project = repo.create_project({'name':'AG142 图隔离项目'})
            repo.ensure_concept_map_category('未分类')
            graph = ConceptMapRepository.normalize({'title':'AG142 关系图', 'project_id':project['id'],
                'focus_question':'甲与乙有什么联系？',
                'nodes':[{'id':'a', 'text':'甲', 'x':100, 'y':120}, {'id':'b', 'text':'乙', 'x':420, 'y':220}],
                'edges':[{'id':'edge', 'from':'a', 'to':'b', 'label':'联系'}]})
            resource = {'type':'project', 'id':project['id']}
            target = {}
            if operation == 'update':
                original = repo.create_concept_map(graph)
                resource = {'type':'concept_map', 'id':original['id']}
                target = {'target_id':original['id'], 'base_revision':original['revision']}
                graph = {**graph, 'title':'AG142 关系图更新'}
            read_grant = {'capability':'concept_maps.read', 'operations':['read'], 'resources':[resource],
                          'minimum_confirmation_mode':'agent_attested'}
            # Independent client bootstrap requires a dormant entry. Only the
            # separately approved graph grant below activates graph access.
            info = workbench.security.add_client('AG142 图更新单案' if target else 'AG142 图新建单案',
                                                 ['read', 'propose', 'commit'], [], [],
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
                {'capability':'concept_maps.write', 'operations':[operation], 'resources':[resource], 'minimum_confirmation_mode':'local_web'}]}
            discovered, approve, stop = base / 'DISCOVERED', base / 'APPROVE_GRANT', base / 'STOP'
            trace = base / 'protocol.jsonl'
            entry, config, catalog = project_connector(project_dir, trace, info['config_file'], codex)
            connection = {'workbench_url':workbench.base_url, 'workspace_id':workspace,
                          'operation':operation, **target,
                          'desktop_project':str(project_dir), **config, 'expected_catalog':catalog,
                          'trace_path':str(trace), 'stop_file':str(stop)}
            may_review = True
            if codex and not check_only:
                emit({'mode':'pending_discovery', **connection, 'discovery_file':str(discovered),
                      'wait_seconds':DISCOVERY_SECONDS, 'graph_granted':False})
                signaled = wait_for_signal(discovered, stop, DISCOVERY_SECONDS)
                may_review = signaled and pilot_discovered(trace, catalog) and not stop.exists()
                if may_review:
                    audit['discovery'] = 'verified'
                elif stop.exists():
                    audit['discovery'] = 'stopped'
                else:
                    audit['discovery'] = 'missing_handshake' if signaled else 'timeout'

            approved = False
            if may_review:
                grant = local(route + '/preview', {'workspace_id':workspace, 'grants':grants,
                              'expected_version':client_version(workbench.security.clients()[client_id])})
                if check_only:
                    approved = True
                elif approve.exists():
                    audit['grant_review'] = 'early_approval_signal'
                else:
                    emit({'mode':'grant_review', 'workbench_url':workbench.base_url, 'grant_preview':grant,
                          'approval_file':str(approve), 'stop_file':str(stop), 'wait_seconds':GRANT_REVIEW_SECONDS})
                    approved = wait_for_signal(approve, stop, GRANT_REVIEW_SECONDS)
            audit['graph_granted'] = False
            if approved:
                ticket = {key:grant[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')}
                local(route + '/confirm', {**ticket, 'approved':True, 'request_id':'ag142-graph-pilot-grant'})
                audit['graph_granted'] = True
                spec = {'request_id':f'ag142-graph-pilot-{operation}', 'kind':'concept_map', 'operation':operation,
                        **target, 'confirmation_mode':'local_web', 'content':{'graph':graph}}
                if check_only:
                    audit.update(check_graph(base, project_dir, entry, workbench, workspace, spec, local, codex))
                else:
                    discovery = '查该项目是否已有图。为空时继续。'
                    if target:
                        discovery = (f'列出已授权图，再用 get_concept_map 完整读取 {target["target_id"]}，'
                                     '核对当前 revision 与下列 base_revision 相同。只把标题改为候选标题，'
                                     '其余 editable_graph 字段与固定候选一致时继续。任何差异均停止。')
                    prompt = (f'只用 {SERVER}。用 capabilities 核对空间 {workspace}。{discovery}'
                              '仅准备下列完整提案，调用 preview_proposal 展示完整图、原图、全部字段、差异、警告、版本、摘要和执行依据，然后停止。'
                              '等待用户在隔离工作台网页独立批准。禁止自行提交、访问其他连接器、读取文件或执行命令。\n'
                              + json.dumps(spec, ensure_ascii=False, indent=2))
                    emit({'mode':'ready', **connection, 'graph_granted':True,
                          'wait_seconds':WINDOW_SECONDS, 'execution_expires_at':int(time.time() + WINDOW_SECONDS),
                          'prompt':prompt})
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
            emit({'mode':'service_stopped', **audit})
    emit({'mode':'stopped', 'temporary_directory_removed':not base.exists(), **audit})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', choices=('workbuddy', 'codex'), default='workbuddy')
    parser.add_argument('--operation', choices=('create', 'update'), default='create')
    parser.add_argument('--check', action='store_true', help='Run the isolated synthetic approval and replay, then exit')
    args = parser.parse_args()
    run(args.check, args.client == 'codex', args.operation)
