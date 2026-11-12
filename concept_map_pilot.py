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
from codex_pilot_anchor import anchor_slot
from workbench.agent_concept_execution import candidate_graph
from workbench.agent_management import client_version
from workbench.agent_security import read_json
from workbench.agent_tools import TOOLS
from workbench.concept_maps import ConceptMapRepository
from workbench.persistence import atomic_write_json
from workbench.write_coordinator import content_revision
from workbuddy_agent_acceptance import (GRAPH_ATTESTED_CASE, GRAPH_ATTESTED_GATE, GRAPH_ATTESTED_TOOLS, GRAPH_PILOT_TOOLS,
                                        PILOT_ATTESTED_CONFIRMATION, PILOT_BINDING_FIELDS, disposable_directory,
                                        graph_attested_proposal_matches, isolated_environment, pilot_discovered)


WINDOW_SECONDS = 1200
DISCOVERY_SECONDS = 1200
GRANT_REVIEW_SECONDS = 540
SERVER = 'workbench_ag142_graph'
ATTESTED_SERVER = 'workbench_ag142_graph_attested'


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


def emit_stopped(base, slot, audit):
    status = {'temporary_directory_removed':not base.exists(), **audit}
    if slot and slot.cleanup_error:
        error = slot.cleanup_error
        emit({'mode':'anchor_cleanup_failed', 'anchor_idle':False, **status, 'error_type':type(error).__name__,
              'errno':getattr(error, 'errno', None), 'winerror':getattr(error, 'winerror', None)})
        raise SystemExit(1)
    if slot:
        status['anchor_idle'] = True
    emit({'mode':'stopped', **status})


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
                      catalog=GRAPH_PILOT_TOOLS, relay_flag=None, slot=None, port=None):
    if slot and (not codex or project_dir != slot.root):
        raise ValueError('Managed anchor does not match the Codex project')
    entry = {'command':sys.executable, 'args':[str(Path(__file__).with_name('workbuddy_agent_acceptance.py')), '--relay'],
             'env':{'WORKBENCH_PROBE_TRACE':str(trace), 'WORKBENCH_PROBE_CONFIG':client_config}}
    if not codex:
        if relay_flag:
            entry['args'].append(relay_flag)
        tools = list(catalog) if relay_flag else [tool['name'] for tool in TOOLS]
        return entry, {'config':{'mcpServers':{server:entry}}}, tools
    entry['args'].append(relay_flag or '--relay-graph-pilot')
    config = project_dir / '.codex' / 'config.toml'
    text = '[mcp_servers.workbench]\nenabled = false\n\n' + server_toml(server, entry, catalog)
    assert tomllib.loads(text)['mcp_servers'] == {
        'workbench':{'enabled':False}, server:{**entry, 'enabled_tools':list(catalog)}}
    if slot:
        slot.publish(text, port)
    else:
        config.parent.mkdir()
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


class GraphAttestedCase:
    def __init__(self, base, workbench, workspace, client_id, spec, trace, stop):
        self.repo = workbench.repository
        self.service = self.repo.agent_service
        self.store = self.service.store
        self.directory = self.repo.root / 'concept-maps'
        self.original = {path:path.read_bytes() for path in self.directory.glob('CMAP-*.json')}
        self.spec = spec
        self.case_path = base / GRAPH_ATTESTED_CASE
        self.gate = base / GRAPH_ATTESTED_GATE
        self.trace = trace
        self.stop = stop
        self.client_id = client_id
        self.workspace = workspace

    def open_window(self):
        self.deadline = time.monotonic() + WINDOW_SECONDS
        self.case = {'workspace_id':self.workspace, 'client_id':self.client_id, 'request':self.spec,
                     'expires_at':int(time.time() + WINDOW_SECONDS)}
        atomic_write_json(self.case_path, self.case)

    def unchanged(self):
        if ({path:path.read_bytes() for path in self.directory.glob('CMAP-*.json')} != self.original
                or list(self.repo.history_dir.rglob('*.json')) or list(self.store.receipts.glob('*.json'))):
            raise ValueError('Graph, history or receipt changed before confirmation')

    def preview_binding(self):
        files = list(self.store.proposals.glob('*.json'))
        if not files:
            return None
        [path] = files
        proposal = read_json(path)
        if proposal['state'] != 'previewed':
            return None
        preview = self.store.preview_result(proposal)
        original = next(iter(self.original.values()), None)
        if (not graph_attested_proposal_matches(self.case, proposal, path.stem)
                or proposal['previewed_version'] != proposal['version']
                or proposal['preview_digest'] != preview['preview_digest']
                or preview['content'] != self.spec['content']
                or preview['base_graph'] != (json.loads(original) if original else {})
                or preview['prepared_graph'] != candidate_graph(proposal)
                or not all(field in preview for field in ('graph_diff','warnings','execution_plan'))):
            raise ValueError('Graph preview does not match the fixed candidate and original bytes')
        self.unchanged()
        return {field:proposal[field] for field in PILOT_BINDING_FIELDS}

    def commit_arguments(self, binding):
        return {**binding, 'confirmation':PILOT_ATTESTED_CONFIRMATION}

    def durable_result(self, binding):
        from server import Repository

        proposal = read_json(self.store.proposals / (binding['proposal_id'] + '.json'))
        [receipt_path] = self.store.receipts.glob('*.json')
        receipt = read_json(receipt_path)
        manifest = read_json(self.store.operations / f'{binding["proposal_id"]}-{binding["version"]}' / 'manifest.json')
        item, path = Repository(self.repo.root).get_concept_map(receipt['item_id'])
        original = self.original.get(path)
        histories = list(self.repo.history_dir.rglob('*.json'))
        if (proposal['state'] != 'committed' or proposal['receipt'] != receipt
                or receipt_path.stem != binding['proposal_id']
                or any(proposal[field] != binding[field] for field in PILOT_BINDING_FIELDS)
                or manifest['state'] != 'committed' or manifest['receipt'] != receipt
                or manifest['confirmation'] != PILOT_ATTESTED_CONFIRMATION
                or manifest['confirmation_mode'] != 'agent_attested' or manifest['preview_digest'] != binding['preview_digest']
                or not item or item['revision'] != receipt['revision']
                or json.loads(path.read_bytes()) != candidate_graph(proposal, manifest['managed_time'])
                or list(self.directory.glob('CMAP-*.json')) != [path]
                or (self.original and (not original or path.read_bytes() == original or len(histories) != 1
                                       or histories[0].parent.name != path.stem or histories[0].read_bytes() != original))
                or (not self.original and histories)):
            raise ValueError('Graph publication, original history or unique receipt did not match')
        return {'receipt':receipt, 'graph_count':1, 'receipt_count':1, 'history_count':len(histories),
                'first_commit_response_verified':True, 'receipt_query_matches':True}

    def observed_result(self, binding):
        evidence = []
        for line in self.trace.read_text(encoding='utf-8').splitlines():
            try:
                event = json.loads(line).get('graph_attested_evidence')
            except ValueError:
                continue
            if event:
                evidence.append(event)
        if evidence and evidence[0] == 'committed' and 'queried' in evidence[1:]:
            return self.durable_result(binding)
        return None

    def check(self, invoke):
        def call(tool, args):
            result = invoke('workbench_' + tool, args)
            assert result['isError'] is False, result
            return result['structuredContent']

        def denied(tool, args):
            try:
                invoke('workbench_' + tool, args)
            except RuntimeError as error:
                assert 'outside the graph confirmation pilot scope' in str(error), error
            else:
                raise AssertionError('Graph relay accepted an unapproved request')

        caps = call('capabilities', {})
        assert caps['workspace_id'] == self.workspace and caps['kind_operations'] == {'concept_map':[self.spec['operation']]}
        denied('prepare_proposal', {**self.spec, 'request_id':'ag142-unapproved-graph'})
        proposal = call('prepare_proposal', self.spec)
        query = {'proposal_id':proposal['proposal_id']}
        call('preview_proposal', query)
        old = self.preview_binding()
        denied('commit_proposal', self.commit_arguments(old))
        client = self.service.security.clients()[self.client_id]
        revision = {'expected_version':old['version'], 'content':self.spec['content']}
        if 'base_revision' in self.spec:
            revision['base_revision'] = self.spec['base_revision']
        self.service.revise_proposal(client, query['proposal_id'], revision)
        call('preview_proposal', query)
        binding = self.preview_binding()
        assert binding['version'] == old['version'] + 1
        atomic_write_json(self.gate, old)
        denied('commit_proposal', self.commit_arguments(old))
        atomic_write_json(self.gate, binding)
        args = self.commit_arguments(binding)
        denied('commit_proposal', {**args, 'preview_digest':'0' * 64})
        denied('commit_proposal', {**args, 'confirmation':{'mode':'agent_attested','user_confirmed':False}})
        self.unchanged()
        first = call('commit_proposal', args)
        observed = call('get_proposal', query)
        result = self.observed_result(binding)
        assert result and all(first[field] == value == observed['receipt'][field]
                              for field, value in result['receipt'].items())
        graph = call('get_concept_map', {'map_id':first['item_id']})
        assert graph['editable_graph'] == self.spec['content']['graph'] and graph['revision'] == first['revision']
        denied('commit_proposal', args)
        assert self.durable_result(binding) == result
        return {**result, 'locked_commit_denied':True, 'stale_binding_denied':True, 'wrong_binding_denied':True,
                'duplicate_commit_denied':True, 'tool_count':len(GRAPH_ATTESTED_TOOLS)}

    def run_window(self, prompt, audit):
        from attachment_pilot import await_value

        self.open_window()
        expires = self.case['expires_at']
        emit({'mode':'ready_preview', 'execution_expires_at':expires, 'prompt':prompt})
        binding = await_value(self.preview_binding, self.stop, self.deadline)
        signal = self.case_path.with_name('CONFIRM_GRAPH.json')
        if not binding:
            return
        if signal.exists():
            raise ValueError('Graph confirmation signal appeared before preview review')
        confirm = ('我已核对完整预览，明确确认以下提案的 ID、版本和摘要。'
                   '请复述绑定并等待下一条消息，此时不要调用工具。\n'
                   + json.dumps(binding, ensure_ascii=False, indent=2))
        emit({'mode':'await_user_confirmation', 'binding':binding, 'signal_file':str(signal),
              'execution_expires_at':expires, 'prompt':confirm})
        value = await_value(lambda: read_json(signal) if signal.exists() else None, self.stop, self.deadline)
        if value is None:
            return
        if (value != binding or type(value.get('version')) is not int or self.preview_binding() != binding
                or self.stop.exists() or time.monotonic() >= self.deadline):
            raise ValueError('Graph confirmation does not match the current preview')
        signal.unlink()
        atomic_write_json(self.gate, binding)
        commit = (f'只用 {ATTESTED_SERVER}，按上一条用户确认的绑定提交一次。'
                  '成功后只查询同一原提案并展示原回执，随后停止。超时或失败先查询原提案，禁止重试或重建。\n'
                  + json.dumps(self.commit_arguments(binding), ensure_ascii=False, indent=2))
        emit({'mode':'ready_commit', 'execution_expires_at':expires, 'prompt':commit})
        result = await_value(lambda: self.observed_result(binding), self.stop, self.deadline)
        if result:
            audit.update(result)
            emit({'mode':'committed', **result})
            await_value(lambda: None, self.stop, self.deadline)
        elif self.case_path.with_suffix('.claim').exists():
            audit['first_response_or_query_unverified'] = True


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


def run(check_only, codex=False, operation='create', anchor=None, confirmation_mode='local_web'):
    audit = {}
    attested = confirmation_mode == 'agent_attested'
    server = ATTESTED_SERVER if attested else SERVER
    if anchor is not None and not codex:
        raise ValueError('A managed anchor requires the Codex project connector')
    with pilot_directory() as base, anchor_slot(anchor) as slot:
        project_dir = slot.root if slot else base / 'desktop-project'
        if not slot:
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
                                                 workbench.base_url, kinds=[], minimum_confirmation_mode=confirmation_mode,
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
                {'capability':'concept_maps.write', 'operations':[operation], 'resources':[resource],
                 'minimum_confirmation_mode':confirmation_mode}]}
            discovered, approve, stop = base / 'DISCOVERED', base / 'APPROVE_GRANT', base / 'STOP'
            trace = base / 'protocol.jsonl'
            entry, config, catalog = project_connector(project_dir, trace, info['config_file'], codex, server=server,
                catalog=GRAPH_ATTESTED_TOOLS if attested else GRAPH_PILOT_TOOLS,
                relay_flag='--relay-graph-attested-pilot' if attested else None, slot=slot, port=workbench.server.server_address[1])
            connection = {'workbench_url':workbench.base_url, 'workspace_id':workspace,
                          'operation':operation, **target,
                          'desktop_project':str(project_dir), **config, 'expected_catalog':catalog,
                          'trace_path':str(trace), 'stop_file':str(stop), 'managed_anchor':slot is not None}
            if attested:
                connection['confirmation_mode'] = confirmation_mode
            may_review = True
            if (codex or attested) and not check_only:
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
                        **target, 'confirmation_mode':confirmation_mode, 'content':{'graph':graph}}
                if attested and check_only:
                    from attachment_pilot import check_workbuddy

                    case = GraphAttestedCase(base, workbench, workspace, client_id, spec, trace, stop)
                    case.open_window()
                    context = (check_app_server(base, project_dir, entry, server=server, catalog=catalog) if codex
                               else check_workbuddy(base, project_dir, entry, config['config'], catalog, token, audit, server=server))
                    with context as invoke:
                        audit.update(case.check(invoke))
                elif check_only:
                    audit.update(check_graph(base, project_dir, entry, workbench, workspace, spec, local, codex))
                else:
                    discovery = '查该项目是否已有图。为空时继续。'
                    if target:
                        discovery = (f'列出已授权图，再用 get_concept_map 完整读取 {target["target_id"]}，'
                                     '核对当前 revision 与下列 base_revision 相同。只把标题改为候选标题，'
                                     '其余 editable_graph 字段与固定候选一致时继续。任何差异均停止。')
                    confirmation = ('等待用户之后的新消息确认。' if attested
                                    else '等待用户在隔离工作台网页独立批准。')
                    identifier = '提案 ID、' if attested else ''
                    prompt = (f'只用 {server}。用 capabilities 核对空间 {workspace}。{discovery}'
                              '仅准备下列完整提案，调用 preview_proposal 展示完整图、原图、全部字段、差异、警告、'
                              f'{identifier}版本、摘要和执行依据，然后停止。'
                              + confirmation + '禁止自行提交、访问其他连接器、读取文件或执行命令。\n'
                              + json.dumps(spec, ensure_ascii=False, indent=2))
                    if attested:
                        case = GraphAttestedCase(base, workbench, workspace, client_id, spec, trace, stop)
                        case.run_window(prompt, audit)
                    else:
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
    emit_stopped(base, slot, audit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', choices=('workbuddy', 'codex'), default='workbuddy')
    parser.add_argument('--operation', choices=('create', 'update'), default='create')
    parser.add_argument('--confirmation-mode', choices=('local_web', 'agent_attested'), default='local_web')
    parser.add_argument('--anchor', type=Path, help='Use an explicitly initialized Codex pilot directory')
    parser.add_argument('--check', action='store_true', help='Run the isolated synthetic approval and replay, then exit')
    args = parser.parse_args()
    run(args.check, args.client == 'codex', args.operation, args.anchor, args.confirmation_mode)
