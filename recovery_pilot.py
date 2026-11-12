"""Coordinate a disposable AG-142 graph recovery pilot without launching a model."""

import argparse
import json
import socket
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from attachment_pilot import await_value, check_workbuddy, review_grant
from codex_agent_acceptance import LocalWorkbench, RpcProcess
from codex_pilot_anchor import anchor_slot
from concept_map_pilot import (DISCOVERY_SECONDS, WINDOW_SECONDS, check_app_server, emit, emit_stopped,
                               pilot_directory, project_connector, wait_for_signal)
from workbench.agent_management import client_version
from workbench.agent_security import AgentError, private_write, read_json
from workbench.concept_maps import ConceptMapRepository
from workbench.persistence import atomic_write_json
from workbench.write_coordinator import content_revision
from workbuddy_agent_acceptance import (RECOVERY_PILOT_CASE, RECOVERY_PILOT_TOOLS, isolated_environment,
                                       pilot_discovered)


SERVER = 'workbench_ag142_recovery'
CONFIRMATION = {'mode':'agent_attested', 'user_confirmed':True, 'note':'隔离协议预演的程序化确认'}
DESKTOP_CONFIRMATION = {'mode':'agent_attested', 'user_confirmed':True}
BINDING_KEYS = ('proposal_id','version','preview_digest')


def port_closed(port):
    with socket.socket() as probe:
        return probe.connect_ex(('127.0.0.1', port)) != 0


@contextmanager
def direct_stdio(base, cwd, entry):
    rpc = RpcProcess([entry['command'], *entry['args']], cwd,
                     {**isolated_environment(base), **entry['env']}, terminate_tree=True)
    try:
        hello = rpc.call('initialize', {'protocolVersion':'2025-11-25', 'capabilities':{},
                         'clientInfo':{'name':'ag142-recovery-check', 'version':'1'}})
        assert hello['protocolVersion'] == '2025-11-25'
        rpc.notify('notifications/initialized')
        assert {item['name'] for item in rpc.call('tools/list')['tools']} == set(RECOVERY_PILOT_TOOLS)
        assert pilot_discovered(Path(entry['env']['WORKBENCH_PROBE_TRACE']), RECOVERY_PILOT_TOOLS)

        def invoke(tool, arguments):
            return rpc.call('tools/call', {'name':tool, 'arguments':arguments})

        yield invoke
    finally:
        rpc.close()


def version_binding(preview):
    return {key:preview[key] for key in BINDING_KEYS}


def binding(preview, confirmation=CONFIRMATION):
    return {**version_binding(preview), 'confirmation':confirmation}


class RecoveryCase:
    def __init__(self, base):
        self.base = base
        self.workbench = LocalWorkbench(base / 'data', base / 'private')
        self.info = None
        self.audit = {}

    def setup(self):
        repo = self.workbench.repository
        project = repo.create_project({'name':'AG142 恢复对照项目'})
        graph = ConceptMapRepository.normalize({
            'title':'AG142 原图', 'project_id':project['id'],
            'nodes':[{'id':'a','text':'甲'}, {'id':'b','text':'乙'}],
            'edges':[{'id':'link','from':'a','to':'b','label':'关系'}],
        })
        created = repo.create_concept_map(graph)
        self.graph_id = created['id']
        self.path = repo.get_concept_map(self.graph_id)[1]
        self.original = self.path.read_bytes()
        self.history = repo.history_dir / self.graph_id
        self.graph = graph
        resource = {'type':'concept_map', 'id':self.graph_id}
        read = {'capability':'concept_maps.read', 'operations':['read'], 'resources':[resource],
                'minimum_confirmation_mode':'agent_attested'}
        write = {**read, 'capability':'concept_maps.write', 'operations':['update']}
        self.info = self.workbench.security.add_client('AG142 图恢复对照', ['read','propose','commit'], [], [],
                    self.workbench.base_url, kinds=[], capability_grants={'schema_version':1, 'grants':[read]})
        self.client_id = self.info['client_id']
        self.workspace = self.info['workspace_id']
        self.config = Path(self.info['config_file'])
        self.token = read_json(self.config)['token']
        self.headers = {'Origin':self.workbench.base_url, 'X-Workbench-Management':'1', 'Content-Type':'application/json'}
        self.headers['X-Workbench-Management-Token'] = self.local('status')['management_token']
        self.grants = {'schema_version':1, 'grants':[read, write]}
        self.a = self.request('a', 'AG142 待取消候选')
        self.b = self.request('b', 'AG142 唯一提交候选')
        self.gate = self.base / RECOVERY_PILOT_CASE
        self.stop = self.base / 'STOP'
        self.trace = self.base / 'protocol.jsonl'
        self.state = {'phase':'preview', 'expires_at':0, 'workspace_id':self.workspace, 'client_id':self.client_id,
                      'graph_id':self.graph_id, 'requests':[self.a, self.b], 'proposal_ids':[]}
        self.publish()

    def authorize(self, check):
        grant = {'workspace_id':self.workspace, 'expected_version':client_version(self.client()), 'grants':self.grants}
        return review_grant(self.local, f'clients/{self.client_id}/concept-maps', grant, self.workspace, self.stop,
                            check, 'RECOVERY_GRAPH', request_prefix='ag142-recovery')

    def open_window(self):
        self.deadline = time.monotonic() + WINDOW_SECONDS
        self.publish(expires_at=int(time.time()) + WINDOW_SECONDS)

    def local(self, route, payload=None):
        request = Request(self.workbench.base_url + '/api/local/agent-management/' + route, headers=self.headers,
                          data=json.dumps(payload).encode() if payload is not None else None)
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    def client(self):
        return self.workbench.security.clients()[self.client_id]

    def request(self, label, title):
        return {'request_id':f'ag142-recovery-{label}', 'kind':'concept_map', 'operation':'update',
                'target_id':self.graph_id, 'base_revision':content_revision(self.original),
                'confirmation_mode':'agent_attested', 'content':{'graph':{**self.graph, 'title':title}}}

    def publish(self, **changes):
        self.state.update(changes)
        atomic_write_json(self.gate, self.state)

    def receipts(self):
        return self.workbench.repository.agent_service.store.receipts

    def unchanged(self):
        assert self.path.read_bytes() == self.original
        assert not list(self.history.glob('*.json')) and not list(self.receipts().glob('*.json'))

    def cancel_a(self, preview):
        service = self.workbench.repository.agent_service
        client = self.client()
        key = preview['proposal_id']
        revise = self.request('a', 'AG142 已修订待取消候选')['content']
        revised = service.revise_proposal(client, key, {'expected_version':preview['version'], 'content':revise})
        current = service.preview_proposal(client, key)
        assert revised['version'] == current['version'] == preview['version'] + 1
        assert current['content'] == revise

        def denied(candidate, code):
            payload = binding(candidate)
            payload.pop('proposal_id')
            try:
                service.commit_proposal(client, key, payload)
            except AgentError as error:
                assert error.code == code, error
            else:
                raise AssertionError('An invalid approval for candidate A was accepted')

        denied(preview, 'version_conflict')
        assert service.cancel_proposal(client, key, {'expected_version':current['version']})['state'] == 'cancelled'
        denied(current, 'invalid_state')
        self.unchanged()

    def arm_first(self, preview, confirmed, confirmation=CONFIRMATION):
        expected = binding(preview, confirmation)
        if confirmed != expected or self.state['phase'] != 'preview' or self.state['proposal_ids'][1:] != [expected['proposal_id']]:
            raise ValueError('Confirmation does not match the exact candidate B binding')
        key = expected['proposal_id']
        store = self.workbench.repository.agent_service.store
        proposal = read_json(store.proposals / f'{key}.json')
        if (proposal['state'] != 'previewed' or proposal['client_id'] != self.client_id
                or proposal['request_id'] != self.b['request_id'] or proposal['normalized_content'] != self.b['content']
                or proposal['confirmation_mode'] != 'agent_attested'
                or proposal['previewed_version'] != expected['version']
                or version_binding(store.preview_result(proposal)) != version_binding(expected)
                or proposal['preview_digest'] != expected['preview_digest']):
            raise ValueError('Candidate B preview changed before the confirmation gate')
        self.unchanged()
        self.workbench.drop_response_path = f'/api/agent/v1/proposals/{key}/commit'
        self.publish(phase='first', commit=expected, candidate_b=key)

    def check_receipt(self, received, persisted):
        assert all(received[key] == value for key, value in persisted.items())
        if 'web_url' in received:
            assert received['web_url'] == self.workbench.base_url + persisted['web_path']

    def durable_result(self, commit, queried):
        receipt = queried['receipt']
        assert queried['state'] == 'committed'
        assert all(queried[key] == commit[key] for key in ('proposal_id','version','preview_digest'))
        [receipt_file] = self.receipts().glob('*.json')
        persisted = read_json(receipt_file)
        assert receipt_file.stem == commit['proposal_id']
        self.check_receipt(receipt, persisted)
        [old] = self.history.glob('*.json')
        raw = self.path.read_bytes()
        assert old.read_bytes() == self.original and list(self.path.parent.glob('CMAP-*.json')) == [self.path]
        current, original = json.loads(raw), json.loads(self.original)
        expected = {**original, **self.b['content']['graph'], 'updated':current['updated']}
        assert current == expected and content_revision(raw) == receipt['revision']
        return persisted, raw, receipt_file.read_bytes(), old.name

    def restart(self, slot=None):
        previous = self.workbench
        port = previous.server.server_address[1]
        previous.close()
        assert port_closed(port)
        self.audit['first_port_closed'] = True
        self.workbench = LocalWorkbench(self.base / 'data', self.base / 'private')
        assert self.workbench.security.workspace_id == self.workspace
        if slot:
            slot.update_port(port, self.workbench.server.server_address[1])
        original = read_json(self.config)
        assert original['client_id'] == self.client_id and original['token'] == self.token
        private_write(self.config, {**original, 'base_url':self.workbench.base_url})

    def previews(self):
        store = self.workbench.repository.agent_service.store
        by_request = {}
        expected_requests = {spec['request_id']:spec for spec in (self.a,self.b)}
        for path in store.proposals.glob('*.json'):
            proposal = read_json(path)
            request_id = proposal['request_id']
            spec = expected_requests.get(request_id)
            if (not spec or request_id in by_request or proposal['client_id'] != self.client_id
                    or proposal['workspace_id'] != self.workspace or path.stem != proposal['proposal_id']
                    or any(proposal[key] != spec[key] for key in ('kind','operation','target_id','base_revision','confirmation_mode'))
                    or proposal['normalized_content'] != spec['content']):
                raise ValueError('Unexpected recovery proposal on disk')
            if proposal['state'] != 'previewed':
                if proposal['state'] != 'draft':
                    raise ValueError('Unexpected recovery proposal state')
                continue
            preview = store.preview_result(proposal)
            if (proposal['version'] != 1 or proposal['previewed_version'] != 1
                    or preview['preview_digest'] != proposal['preview_digest']
                    or preview['base_graph'] != json.loads(self.original)):
                raise ValueError('Recovery preview evidence changed')
            by_request[request_id] = preview
        if len(by_request) == 2:
            self.unchanged()
            return by_request[self.a['request_id']], by_request[self.b['request_id']]
        return None

    def phase_signal(self, mode, filename, *, expected=None, **details):
        signal = self.base / filename
        if signal.exists():
            raise ValueError('Recovery stage signal appeared before its review')
        emit({'mode':mode, 'signal_file':str(signal), 'execution_expires_at':self.state['expires_at'], **details})
        if expected is None:
            return wait_for_signal(signal, self.stop, max(0, self.deadline - time.monotonic()))
        value = await_value(lambda: read_json(signal) if signal.exists() else None, self.stop, self.deadline)
        if value is None:
            return False
        if (not isinstance(value, dict) or type(value.get('version')) is not int or value != expected):
            raise ValueError('Recovery stage signal does not match the current binding')
        signal.unlink()
        return not self.stop.exists() and time.monotonic() < self.deadline

    def wait_evidence(self, *expected):
        def observed():
            stages = []
            if self.trace.exists():
                for line in self.trace.read_text(encoding='utf-8').splitlines():
                    try:
                        event = json.loads(line).get('recovery_evidence')
                    except ValueError:
                        continue  # The relay may still be appending its current line.
                    if event:
                        if event.startswith('unexpected_'):
                            raise ValueError('Recovery tool outcome could not be verified')
                        stages.append(event)
            # Further identical reads are harmless; commit outcomes still require a unique claim.
            stages = list(dict.fromkeys(stages))
            if stages != list(expected[:len(stages)]):
                raise ValueError('Recovery tool outcome arrived out of sequence')
            return True if stages == list(expected) else None

        return await_value(observed, self.stop, self.deadline)

    def current_result(self, commit):
        store = self.workbench.repository.agent_service.store
        observed = read_json(store.proposals / f'{commit["proposal_id"]}.json')
        return self.durable_result(commit, observed)

    def run_window(self, slot):
        self.open_window()
        prompt = (f'只用 {SERVER}。capabilities 核对空间 {self.workspace}。'
                  '依次对以下两个固定请求执行 prepare_proposal 和 preview_proposal。完整展示两个候选、原图、'
                  '差异、警告、版本、摘要和执行依据，随后停止。此轮只预览。\n'
                  + json.dumps([self.a,self.b], ensure_ascii=False, indent=2))
        emit({'mode':'ready_preview', 'prompt':prompt, 'execution_expires_at':self.state['expires_at']})
        previews = await_value(self.previews, self.stop, self.deadline)
        if not previews:
            return
        a, b = previews
        self.publish(proposal_ids=[a['proposal_id'],b['proposal_id']])
        self.cancel_a(a)
        self.audit.update(candidate_a_cancelled=True, stale_and_cancelled_denied=True)
        version = version_binding(b)
        approved = binding(b, DESKTOP_CONFIRMATION)
        confirm_prompt = ('我已核对完整预览，明确确认以下当前提案的 ID、版本和摘要。'
                          '本条只作确认，请复述绑定并等待下一条执行消息，此时不调用工具。\n'
                          + json.dumps(version, ensure_ascii=False, indent=2))
        if not self.phase_signal('await_user_confirmation', 'CONFIRM_B.json', expected=version, binding=version,
                                 cancelled_proposal_id=a['proposal_id'], prompt=confirm_prompt):
            return
        self.arm_first(b, approved, DESKTOP_CONFIRMATION)
        emit({'mode':'ready_commit', 'execution_expires_at':self.state['expires_at'],
              'prompt':(f'只用 {SERVER}。按上一条用户确认的精确绑定提交一次。'
                        '预期响应丢失；若返回 service_unavailable，先用 get_proposal 查询同一提案，'
                        '展示原回执后停止。任何其他结果均报告并停止。禁止重试或重建。\n'
                        + json.dumps(approved, ensure_ascii=False, indent=2))})
        sequence = ('first_lost','first_queried')
        if not self.wait_evidence(*sequence):
            return
        if self.workbench.drop_response_path is not None:
            raise ValueError('The fixed successful response was not intercepted')
        first = self.current_result(approved)
        self.publish(phase='query')
        self.audit['lost_commit_response_queried'] = True
        if not self.phase_signal('await_restart', 'RESTART', receipt=first[0]):
            return
        self.restart(slot)
        self.publish(phase='restart')
        emit({'mode':'ready_restart_query', 'workbench_url':self.workbench.base_url,
              'execution_expires_at':self.state['expires_at'],
              'prompt':f'只用 {SERVER} 查询原提案 {b["proposal_id"]}，展示原回执后停止。此轮只查询。'})
        sequence += ('restart_queried',)
        if not self.wait_evidence(*sequence):
            return
        if self.current_result(approved) != first:
            raise ValueError('Original evidence differs after restart')
        self.audit['restart_query_matches'] = True
        if not self.phase_signal('await_replay', 'REPLAY_B.json', expected=version, binding=version):
            return
        if self.current_result(approved) != first:
            raise ValueError('Original evidence changed while awaiting replay')
        self.publish(phase='replay')
        emit({'mode':'ready_replay', 'execution_expires_at':self.state['expires_at'],
              'prompt':(f'只用 {SERVER} 按原绑定重放一次已提交的原操作，展示返回的原回执后停止。'
                        '出错只报告，禁止重试或新建。\n' + json.dumps(approved, ensure_ascii=False, indent=2))})
        if self.wait_evidence(*sequence, 'replayed'):
            if self.current_result(approved) != first:
                raise ValueError('Replay changed the original evidence')
            self.audit.update(exact_replay_matches=True, one_graph=True, one_history=True, one_receipt=True,
                              first_port_closed=True)
            self.publish(phase='query')
            emit({'mode':'committed', 'receipt':first[0], **self.audit})
            await_value(lambda: None, self.stop, self.deadline)

    def check(self, invoke):
        def call(name, args=None, *, error=None):
            result = invoke('workbench_' + name, args or {})
            assert result['isError'] == bool(error), result
            value = result['structuredContent']
            if error:
                assert value['code'] == error, value
            return value

        def rejected(name, args):
            try:
                invoke('workbench_' + name, args)
            except RuntimeError as error:
                assert 'outside the recovery pilot scope' in str(error), error
            else:
                raise AssertionError('Recovery pilot forwarded an excluded call')

        expires_at = self.state['expires_at']
        self.publish(expires_at=0)
        rejected('capabilities', {})
        self.publish(expires_at=expires_at)
        capabilities = call('capabilities')
        assert capabilities['workspace_id'] == self.workspace
        assert capabilities['kind_operations'] == {'concept_map':['update']}
        graph = call('get_concept_map', {'map_id':self.graph_id})
        assert graph['revision'] == content_revision(self.original) and graph['editable_graph'] == self.graph
        rejected('get_concept_map', {'map_id':'CMAP-9999'})
        rejected('prepare_proposal', {**self.b, 'request_id':'not-approved'})
        a, b = [call('prepare_proposal', spec)['proposal_id'] for spec in (self.a,self.b)]
        assert a != b
        self.publish(proposal_ids=[a,b])
        rejected('get_proposal', {'proposal_id':'00000000-0000-0000-0000-000000000000'})
        preview_a, preview_b = [call('preview_proposal', {'proposal_id':key}) for key in (a,b)]
        for preview, spec in ((preview_a,self.a),(preview_b,self.b)):
            assert preview['content'] == spec['content'] and preview['base_graph'] == json.loads(self.original)
            assert all(preview[key] for key in ('graph_diff','warnings','execution_plan'))
        approved = binding(preview_b)
        rejected('commit_proposal', approved)
        self.cancel_a(preview_a)
        assert call('get_proposal', {'proposal_id':a})['state'] == 'cancelled'
        bad = {**approved, 'preview_digest':'0' * 64}
        try:
            self.arm_first(preview_b, bad)
        except ValueError:
            pass
        else:
            raise AssertionError('Mismatched B confirmation armed the first commit')
        self.arm_first(preview_b, approved)
        rejected('commit_proposal', bad)
        rejected('commit_proposal', binding(preview_a))
        call('commit_proposal', approved, error='service_unavailable')
        assert self.workbench.drop_response_path is None
        rejected('commit_proposal', approved)
        self.publish(phase='query')
        original_result = self.durable_result(approved, call('get_proposal', {'proposal_id':b}))
        self.publish(phase='restart')
        self.restart()
        assert call('capabilities')['workspace_id'] == self.workspace
        rejected('commit_proposal', approved)
        assert self.durable_result(approved, call('get_proposal', {'proposal_id':b})) == original_result
        self.publish(phase='replay')
        self.check_receipt(call('commit_proposal', approved), original_result[0])
        rejected('commit_proposal', approved)
        assert self.durable_result(approved, call('get_proposal', {'proposal_id':b})) == original_result
        self.audit.update(tool_count=len(RECOVERY_PILOT_TOOLS), candidate_a_cancelled=True, stale_and_cancelled_denied=True,
                          lost_commit_response_queried=True, restart_query_matches=True, exact_replay_matches=True,
                          one_graph=True, one_history=True, one_receipt=True, first_port_closed=True)

    def close(self):
        workbench = self.workbench
        port = workbench.server.server_address[1]
        try:
            if self.info is not None:
                workbench.security.change_client(self.client_id)
                request = Request(workbench.base_url + '/api/agent/v1/capabilities', headers={
                    'Authorization':'Bearer ' + self.token, 'X-Workbench-Workspace':self.workspace})
                try:
                    with urlopen(request, timeout=5):
                        raise AssertionError('Revoked recovery identity was accepted')
                except HTTPError as error:
                    with error:
                        assert error.code == 401
                self.audit['revoked_credential_denied'] = True
        finally:
            workbench.close()
        self.audit['port_closed'] = port_closed(port)
        assert self.audit['port_closed']


def run(check, client, anchor=None):
    if client == 'stdio' and not check or client != 'codex' and anchor is not None:
        raise ValueError('Direct stdio requires --check; --anchor is for Codex')
    with pilot_directory('workbench-ag142-recovery-') as base, anchor_slot(anchor) as slot:
        cwd = slot.root if slot else base / 'desktop-project'
        if not slot:
            cwd.mkdir()
        case = RecoveryCase(base)
        try:
            case.setup()
            codex = client != 'workbuddy'
            entry, config, catalog = project_connector(cwd, case.trace, str(case.config), codex, server=SERVER,
                catalog=RECOVERY_PILOT_TOOLS, relay_flag='--relay-recovery-pilot', slot=slot,
                port=case.workbench.server.server_address[1])
            if check:
                if not case.authorize(True):
                    raise ValueError('Recovery check authorization failed')
                case.open_window()
                if client == 'codex':
                    context = check_app_server(base, cwd, entry, server=SERVER, catalog=catalog)
                elif client == 'workbuddy':
                    context = check_workbuddy(base, cwd, entry, config['config'], catalog, case.token, case.audit, server=SERVER)
                else:
                    context = direct_stdio(base, cwd, entry)
                with context as invoke:
                    case.check(invoke)
            else:
                discovered = base / 'DISCOVERED'
                emit({'mode':'pending_discovery', 'client':client, 'workspace_id':case.workspace,
                      'desktop_project':str(cwd), 'workbench_url':case.workbench.base_url, **config, 'expected_catalog':catalog, 'trace_path':str(case.trace),
                      'stop_file':str(case.stop), 'discovery_file':str(discovered), 'wait_seconds':DISCOVERY_SECONDS})
                if (wait_for_signal(discovered, case.stop, DISCOVERY_SECONDS)
                        and pilot_discovered(case.trace, catalog) and case.authorize(False)):
                    case.run_window(slot)
        finally:
            if not check:
                first_claimed = (base / 'recovery-first.claim').exists()
                case.audit.update(first_claimed=first_claimed, replay_claimed=(base / 'recovery-replay.claim').exists(),
                                  receipt_count=len(list(case.receipts().glob('*.json'))))
                if first_claimed and not case.audit.get('exact_replay_matches'):
                    case.audit['replay_unverified'] = True
            case.close()
            emit({'mode':'service_stopped', 'client':client, 'model_turns_started_by_fixture':0, **case.audit})
    emit_stopped(base, slot, {'client':client, 'model_turns_started_by_fixture':0, **case.audit})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Run the zero-model preflight')
    parser.add_argument('--client', choices=('codex','stdio','workbuddy'), default='codex')
    parser.add_argument('--anchor', type=Path, help='Use an initialized dedicated Codex project')
    args = parser.parse_args()
    run(args.check, args.client, args.anchor)
