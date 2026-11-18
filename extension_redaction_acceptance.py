"""Explicit output checks over the lifecycle acceptance's existing mixed sample."""
from __future__ import annotations

import io
import json
import os
import socket
import sys
import time
import uuid
import zipfile
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote

from extension_runtime_acceptance import CODE, bounded_run, evidence, http, agent_headers, free_port, server_command, running_server
from workbench.agent_management import client_version
from workbench.agent_proposal_management import recovery_status
from workbench.agent_proposals import ProposalStore
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import read_json
from workbench.mcp_stdio import PROTOCOL_VERSION
from workbench.persistence import atomic_write_json


PUBLIC_BODY = 'AG143_PUBLIC_BODY_MARKER_72ea'
NONCE_SUFFIX = 'AG143_DIAGNOSTIC_NONCE_MARKER_72ea_000000000'


def assert_private_absent(value, markers):
    raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
    for label, marker in markers.items():
        text = marker.decode() if isinstance(marker, bytes) else str(marker)
        variants = {text, text.replace('\\', '/'), json.dumps(text, ensure_ascii=False)[1:-1], quote(text, safe='')}
        assert all(variant.encode() not in raw for variant in variants), 'Private marker leaked: ' + label


def stdio(config, calls):
    messages = [
        {'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {
            'protocolVersion': PROTOCOL_VERSION, 'capabilities': {},
            'clientInfo': {'name': 'ag143-redaction', 'version': '1'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
    ]
    messages.extend({'jsonrpc': '2.0', 'id': index, 'method': 'tools/call',
                     'params': {'name': name, 'arguments': arguments}}
                    for index, (name, arguments) in enumerate(calls, 1))
    data = b''.join((json.dumps(message) + '\n').encode() for message in messages)
    with patch.dict(os.environ, {'WORKBENCH_MCP_TRACE': '1'}):
        code, stdout, stderr = bounded_run(
            [sys.executable, str(CODE / 'agent_bridge.py'), '--config', str(config)],
            input_data=data, timeout=20)
    assert code == 0
    responses = [json.loads(line) for line in stdout.splitlines()]
    assert len(responses) == len(calls) + 1
    assert [row['id'] for row in responses] == list(range(len(calls) + 1))
    assert all(row['jsonrpc'] == '2.0' for row in responses)
    return responses, stdout, stderr


def diagnostic(origin, runtime, transport, headers, request_id):
    code, operation = http(origin, '/api/local/agent-management/diagnostics', 'POST', {
        'workspace_id': transport['workspace_id'], 'client_id': transport['client_id'],
        'request_id': request_id}, headers)
    assert code == 200
    deadline = time.monotonic() + 18
    while time.monotonic() < deadline:
        code, result = http(origin, '/api/local/agent-management/diagnostics/' + operation['operation_id'], headers=headers)
        assert code == 200
        if result['state'] == 'completed':
            assert runtime.diagnostics.nonces == {}
            return result
        time.sleep(0.05)
    raise AssertionError('Disposable diagnostic timed out')


def verify_live_redaction(base, workbench, runtime, transport, config, items, graph_id,
                          file_id, policy_id, source_path, secret, archive):
    repo, security, origin = workbench.repository, workbench.security, workbench.base_url
    markers = {'token': transport['token'], 'source_path': source_path,
               'private_root': str(security.config_dir), 'config_path': str(config.resolve()),
               'source_body': secret, 'nonce': 'wbdiag-' + NONCE_SUFFIX, 'nonce_suffix': NONCE_SUFFIX}
    before = evidence(repo.root, security.config_dir.parent)
    private = [path.read_bytes() for path in security.config_dir.rglob('*') if path.is_file()
               and path.name != '.workbench-service.lock']
    assert any(transport['token'].encode() in raw for raw in private)
    assert any(json.dumps(source_path)[1:-1].encode() in raw for raw in private)
    assert any(raw == secret for raw in private)
    headers = agent_headers(transport)
    public = []
    for route in ('capabilities', 'projects', 'files', 'files/' + file_id,
                  'items/info/' + items['info'], 'concept-maps/' + graph_id):
        status, result = http(origin, '/api/agent/v1/' + route, headers=headers)
        assert status == 200, route
        assert_private_absent(result, markers)
        public.append(result)
    assert PUBLIC_BODY in public[4]['body']
    assert public[4]['info_fields'] == repo.get_record(items['info'])[0]['info_fields']
    assert file_id in json.dumps(public) and policy_id in json.dumps(public)
    info = public[3]
    status, read = http(origin, '/api/agent/v1/files/' + file_id + '/content?source_revision=' + info['source_revision'], headers=headers)
    assert status == 200 and read['body'] == secret.decode()
    assert_private_absent({key: value for key, value in read.items() if key != 'body'}, markers)

    bad_token = 'AG143_REJECTED_TOKEN_MARKER_72ea_' + transport['token'][-12:]
    markers['rejected_token'] = bad_token
    for route, values, expected in (
        ('capabilities', {**headers, 'Authorization': 'Bearer ' + bad_token}, 401),
        ('capabilities', {**headers, 'X-Workbench-Workspace': str(uuid.uuid4())}, 409),
        ('files/' + str(uuid.uuid4()), headers, 404),
        ('capabilities?unexpected=' + quote(source_path, safe=''), headers, 400)):
        status, result = http(origin, '/api/agent/v1/' + route, headers=values)
        assert status == expected, (route.split('?')[0], status)
        assert_private_absent(result, markers)

    calls = [
        ('workbench_capabilities', {}), ('workbench_list_file_grants', {}),
        ('workbench_get_file_info', {'file_id': file_id}),
        ('workbench_get_item', {'kind': 'info', 'item_id': items['info']}),
        ('workbench_get_concept_map', {'map_id': graph_id}),
        ('workbench_read_file', {'file_id': file_id, 'source_revision': info['source_revision']}),
        ('workbench_get_file_info', {'file_id': str(uuid.uuid4())}),
        ('workbench_capabilities', {'unexpected': source_path + secret.decode()}),
    ]
    responses, stdout, stderr = stdio(config, calls)
    assert responses[-1]['error']['code'] == -32602 and stderr
    assert responses[-2]['result']['isError'] is True
    for index, row in enumerate(responses):
        if index == 6:
            result = row['result']
            payload = result['structuredContent']
            assert result['isError'] is False and payload['body'] == secret.decode()
            assert json.loads(result['content'][0]['text']) == payload
            sanitized = {key: value for key, value in payload.items() if key != 'body'}
            assert_private_absent(sanitized, markers)
        else:
            assert_private_absent(row, markers)
    # The only permitted secret in raw stdout is the authorized body, once in
    # structuredContent and once in its required text representation.
    assert stdout.count(secret) == 2
    assert_private_absent(stdout, {key: value for key, value in markers.items() if key != 'source_body'})
    assert_private_absent(stderr, markers)
    assert PUBLIC_BODY in responses[4]['result']['structuredContent']['body']

    for name, changes, expected in (
        ('wrong-token', {'token': bad_token}, 'unauthenticated'),
        ('wrong-workspace', {'workspace_id': str(uuid.uuid4())}, 'workspace_mismatch')):
        copied_config = base / ('redaction-' + name + '.json')
        atomic_write_json(copied_config, {**transport, **changes})
        rows, out, err = stdio(copied_config, [('workbench_capabilities', {})])
        assert rows[1]['result']['isError'] is True
        assert rows[1]['result']['structuredContent']['code'] == expected
        assert_private_absent(out + err, {**markers, 'copied_config': str(copied_config.resolve())})
    broken = base / 'redaction-future-config.json'
    atomic_write_json(broken, {**transport, 'schema_version': 99, 'debug_source': source_path, 'debug_body': secret.decode()})
    code, out, err = bounded_run([sys.executable, str(CODE / 'agent_bridge.py'), '--config', str(broken)], input_data=b'')
    assert code == 2 and out == b'' and err
    assert_private_absent(err, {**markers, 'broken_config': str(broken.resolve())})

    status, management = http(origin, '/api/local/agent-management/status')
    assert status == 200
    local_headers = {'Origin': origin, 'X-Workbench-Management-Token': management['management_token']}
    diagnostic_markers = {**markers, 'management_token': management['management_token']}
    with patch('workbench.agent_diagnostics.secrets.token_urlsafe', return_value=NONCE_SUFFIX):
        passed = diagnostic(origin, runtime, transport, local_headers, 'ag143-redaction-success')
        steps = {item['name']: item['state'] for item in passed['steps']}
        assert all(steps[name] == 'passed' for name in ('service', 'authorization', 'configuration', 'python', 'mcp', 'read'))
        assert_private_absent(passed, diagnostic_markers)
        with patch('workbench.agent_diagnostics.probe_mcp', side_effect=TimeoutError(source_path + secret.decode())):
            failed = diagnostic(origin, runtime, transport, local_headers, 'ag143-redaction-failure')
        assert next(item['state'] for item in failed['steps'] if item['name'] == 'mcp') == 'failed'
        assert_private_absent(failed, diagnostic_markers)

    # The local complete-properties view deliberately includes the approved source.
    status, local_files = http(origin, '/api/local/agent-management/clients/' + transport['client_id'] + '/files', headers=local_headers)
    assert status == 200
    [approved] = local_files['items']
    assert approved['path'] == source_path
    assert_private_absent({**approved, 'path': None}, markers)
    with patch.object(repo.agent_proposals, 'recover', side_effect=AssertionError('Read-only report attempted recovery')):
        status, report = http(origin, '/api/local/agent-management/proposal-recovery', headers=local_headers)
        assert status == 200 and report == {'workspace_id': transport['workspace_id'], 'operations': [], 'evidence_error': False}
        assert_private_absent(report, diagnostic_markers)
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        assert package.testzip() is None
        members = {name: package.read(name) for name in package.namelist()}
        assert any(PUBLIC_BODY.encode() in raw for raw in members.values())
        assert_private_absent(list(members), diagnostic_markers)
        for raw in members.values():
            assert_private_absent(raw, diagnostic_markers)
    assert evidence(repo.root, security.config_dir.parent) == before
    return {'api_and_stdio_success_rejection': True, 'authorized_body_preserved': True,
            'diagnostic_success_failure_nonce_hidden': True, 'portable_public_facts_preserved': True}


def verify_readonly_redaction_reports(base, markers):
    """Assemble existing on-disk stores without Repository startup/recovery."""
    checked = []
    for name in ('pending-copy', 'future-execution', 'future-approval', 'future-registry', 'future-authorization', 'future-management', 'future-transport'):
        data, private = base / name / 'data', base / name / 'private'
        before = evidence(data, private)
        mtimes = {path: path.stat().st_mtime_ns for root in (data, private) for path in root.rglob('*')
                  if path.is_file() and path.name != '.workbench-service.lock'}
        # Path-only assembly avoids Repository's startup recovery; actual store
        # validators still verify the complete journals and history paths.
        repository = SimpleNamespace(root=data.resolve(), history_dir=data.resolve() / 'history')
        store = repository.agent_proposals = ProposalStore(repository, create_directories=False)
        runtime = AgentRuntime(repository, base=private)
        with patch.object(store, 'recover', side_effect=AssertionError('Report attempted recovery')), \
                patch.object(store, 'cleanup', side_effect=AssertionError('Report attempted cleanup')), \
                patch.object(store, 'abandon', side_effect=AssertionError('Report attempted abandon')), \
                patch.object(store, '_save', side_effect=AssertionError('Report attempted proposal write')):
            report = recovery_status(runtime)
        assert set(report) == {'workspace_id', 'operations', 'evidence_error'}
        if name in {'future-execution', 'future-approval'}:
            assert report['evidence_error'] is True and report['operations'] == []
        elif name == 'pending-copy':
            [operation] = report['operations']
            assert set(operation) == {'operation_id', 'proposal_id', 'state'} and operation['state'] == 'needs_review'
            assert report['evidence_error'] is False
        else:
            assert report['evidence_error'] is False and report['operations'] == []
        assert_private_absent(report, {**markers, 'current_private_root': str(private.resolve()),
                                      'current_business_root': str(data.resolve())})
        # Inspect private journal evidence directly; CredentialManager.report()
        # is intentionally not used because it invokes recovery itself.
        for path in private.rglob('management-operations/*.json'):
            value = read_json(path)
            assert isinstance(value, dict) and isinstance(value['operation_id'], str)
        assert evidence(data, private) == before
        assert all(path.stat().st_mtime_ns == stamp for path, stamp in mtimes.items())
        checked.append(name)
    return {'existing_copies': len(checked), 'read_only_bytes_mtimes': True, 'reports_only_ids_and_states': True}


def verify_unknown_error_outputs(base, transport, markers):
    checked = []
    for name in ('execution', 'approval', 'registry', 'management', 'authorization', 'transport'):
        data, private = base / ('future-' + name) / 'data', base / ('future-' + name) / 'private'
        before = evidence(data, private)
        current_markers = {**markers, 'current_private_root': str(private.resolve())}
        if name in {'execution', 'approval', 'registry', 'management'}:
            port = free_port()
            code, out, err = bounded_run(server_command(data, private, port, True, CODE), timeout=15)
            assert code != 0 and b'workbench.agent_security.AgentError:' in err
            assert_private_absent(out + err, current_markers)
            with socket.socket() as probe:
                assert probe.connect_ex(('127.0.0.1', port)) != 0
        else:
            with running_server(data, private, enabled=True) as origin:
                status, result = http(origin, '/api/agent/v1/capabilities', headers=agent_headers(transport))
                assert status == (503 if name == 'authorization' else 200)
                assert_private_absent(result, current_markers)
                if name == 'authorization':
                    config = base / 'redaction-future-authorization-connection.json'
                    atomic_write_json(config, {**transport, 'base_url': origin})
                    rows, out, err = stdio(config, [('workbench_capabilities', {})])
                    assert rows[1]['result']['isError'] and rows[1]['result']['structuredContent']['code'] == 'unsupported_schema'
                    assert_private_absent(out + err, {**current_markers, 'config': str(config.resolve())})
                else:
                    status, state = http(origin, '/api/local/agent-management/status')
                    assert status == 200
                    client = read_json(private / transport['workspace_id'] / 'clients.json')['clients'][transport['client_id']]
                    status, failure = http(origin, '/api/local/agent-management/clients/' + transport['client_id'] + '/rotate', 'POST', {
                        'workspace_id': transport['workspace_id'], 'request_id': 'redaction-future-transport',
                        'expected_version': client_version(client)}, {
                            'Origin': origin, 'X-Workbench-Management-Token': state['management_token']})
                    assert status == 503 and failure['code'] == 'unsupported_schema'
                    assert_private_absent(failure, {**current_markers, 'management_token': state['management_token']})
        assert evidence(data, private) == before
        checked.append(name)
    return {'existing_future_copies': len(checked), 'api_stdio_startup_errors_hidden': True, 'evidence_unchanged': True}
