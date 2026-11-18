"""Serial runtime/version checks using the lifecycle acceptance's existing fixture.

No fixture construction, real workspace, desktop client or model invocation.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from workbench.agent_security import read_json
from workbench.agent_management import client_version
from workbench.persistence import atomic_write_json


CODE = Path(__file__).resolve().parent
LEGACY = '9e43aa3'
OUTPUT_LIMIT = 65536


def evidence(*roots):
    return [{path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in root.rglob('*')
             if path.is_file() and path.name != '.workbench-service.lock'} for root in roots]


def clone(base, name, data, private):
    target = base / name
    shutil.copytree(data, target / 'data')
    shutil.copytree(private, target / 'private')
    # Existing startup behavior, normalized before the zero-write comparison.
    atomic_write_json(target / 'data/config/settings.json', {
        'version': 1, 'data_dir': str((target / 'data').resolve())})
    return target / 'data', target / 'private'


def child_environment():
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8'}
    env.pop('PYTHONPATH', None)
    return env


def child_options():
    return {'env': child_environment(),
            'creationflags': subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0}


def bounded_run(args, *, cwd=CODE, timeout=20):
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        result = subprocess.run(args, cwd=cwd, stdout=output, stderr=errors,
                                timeout=timeout, **child_options())
        assert output.tell() <= OUTPUT_LIMIT and errors.tell() <= OUTPUT_LIMIT
        output.seek(0)
        errors.seek(0)
        return result.returncode, output.read(OUTPUT_LIMIT), errors.read(OUTPUT_LIMIT)


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def http(origin, path, method='GET', payload=None, headers=None):
    management = {'X-Workbench-Management': '1'} if path.startswith('/api/local/agent-management/') else {}
    request = Request(origin + path, method=method,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={'Content-Type': 'application/json', **management, **(headers or {})})
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read(2 * 1024 * 1024 + 1)
        assert len(raw) <= 2 * 1024 * 1024
        return response.status, json.loads(raw)


def server_command(data, private, port, enabled, code):
    return [sys.executable, str(code / 'server.py'), '--data-dir', str(data),
            '--agent-config-dir', str(private), '--host', '127.0.0.1',
            '--port', str(port), '--enable-agent' if enabled else '--disable-agent']


@contextmanager
def running_server(data, private, *, enabled, code=CODE):
    port = free_port()
    origin = f'http://127.0.0.1:{port}'
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(server_command(data, private, port, enabled, code),
                                   cwd=code, stdout=subprocess.DEVNULL, stderr=errors, **child_options())
        try:
            health = None
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                assert process.poll() is None, 'Disposable server exited before health check'
                try:
                    status, health = http(origin, '/api/health')
                    assert status == 200 and health['agent_enabled'] is enabled
                    break
                except OSError:
                    time.sleep(0.05)
            assert health is not None, 'Disposable server startup timed out'
            yield origin
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            assert errors.tell() <= OUTPUT_LIMIT
            with socket.socket() as probe:
                assert probe.connect_ex(('127.0.0.1', port)) != 0


def assert_rejected_startup(data, private, *, code=CODE):
    port = free_port()
    result, _, errors = bounded_run(server_command(data, private, port, True, code), cwd=code, timeout=15)
    assert result != 0, 'Incompatible state unexpectedly started with Agent enabled'
    assert b'workbench.agent_security.AgentError:' in errors, 'Startup failed outside the format/recovery guard'
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', port)) != 0


def agent_headers(transport):
    return {'Authorization': 'Bearer ' + transport['token'],
            'X-Workbench-Workspace': transport['workspace_id']}


def verify_disabled_http(base, data, private, transport, receipts):
    data, private = clone(base, 'http-stopped-copy', data, private)
    original = evidence(data, private)
    headers = agent_headers(transport)
    with running_server(data, private, enabled=True) as origin:
        assert http(origin, '/api/agent/v1/capabilities', headers=headers)[0] == 200
        status, state = http(origin, '/api/local/agent-management/status')
        assert status == 200
        assert state['workspace_id'] == transport['workspace_id']
        status, result = http(origin, '/api/local/agent-management/runtime', 'PATCH', {
            'workspace_id': state['workspace_id'], 'expected_version': state['version'],
            'request_id': 'mixed-runtime-disable', 'enabled': False}, {
                'Origin': origin, 'X-Workbench-Management-Token': state['management_token']})
        assert status == 200 and result['status']['enabled'] is False
        assert http(origin, '/api/agent/v1/capabilities', headers=headers)[0] == 404
        assert http(origin, '/api/records')[0] == 200
    assert evidence(data, private) == original
    # An explicit stopped-service restart must honor the disabled CLI override too.
    created = []
    with running_server(data, private, enabled=False) as origin:
        assert http(origin, '/api/agent/v1/capabilities', headers=headers)[0] == 404
        with urlopen(origin + '/', timeout=5) as response:
            assert response.status == 200 and b'<html' in response.read(1024 * 1024)
        status, records = http(origin, '/api/records')
        assert status == 200 and len(records) == 3
        status, documents = http(origin, '/api/documents')
        assert status == 200 and len(documents) == 1
        project_id = records[0]['project_id']
        fields = next(item['info_fields'] for item in records if item['type'] == 'info')
        for route, payload in (
            ('records', {'type': 'info', 'project_id': project_id, 'title': '停用期间结构化信息',
                         'info_fields': fields, 'body': '普通网页首次保存'}),
            ('documents', {'category': documents[0]['category'], 'title': '停用期间知识',
                           'body': '普通网页首次保存'})):
            status, item = http(origin, '/api/' + route, 'POST', payload)
            assert status == 201, (route, status)
            status, item = http(origin, '/api/' + route + '/' + item['id'])
            assert status == 200
            status, saved = http(origin, '/api/' + route + '/' + item['id'], 'PATCH', {
                'body': '普通网页更新并重新加载\n\n保留正文', 'expected_revision': item['revision']})
            assert status == 200, (route, status)
            created.append((route, item['id'], saved['revision']))
    with running_server(data, private, enabled=False) as origin:
        for route, key, revision in created:
            status, actual = http(origin, '/api/' + route + '/' + key)
            assert status == 200 and actual['revision'] == revision
            assert actual['body'] == '普通网页更新并重新加载\n\n保留正文'
            if route == 'records':
                assert actual['info_fields'] == fields
        for receipt in receipts:
            assert read_json(data / '.agent/receipts' / (receipt['proposal_id'] + '.json')) == receipt
    assert evidence(private) == [original[1]]
    assert evidence(data / '.agent') == [{
        name.removeprefix('.agent/'): digest for name, digest in original[0].items()
        if name.startswith('.agent/')}]
    return True


def verify_disabled_pending_http(base, transport):
    data, private = clone(base, 'http-pending-copy', base / 'pending-copy/data', base / 'pending-copy/private')
    pending = [read_json(path) for path in (data / '.agent/operations').glob('*/manifest.json')
               if read_json(path)['state'] not in {'committed', 'abandoned'}]
    [manifest] = pending
    token = manifest['trash_token']
    original = evidence(data, private)
    with running_server(data, private, enabled=False) as origin:
        assert http(origin, '/api/agent/v1/capabilities', headers=agent_headers(transport))[0] == 404
        code, records = http(origin, '/api/records')
        assert code == 200
        code, status = http(origin, '/api/local/agent-management/status')
        assert code == 200 and status['enabled'] is False
        code, report = http(origin, '/api/local/agent-management/proposal-recovery', headers={
            'Origin': origin, 'X-Workbench-Management-Token': status['management_token']})
        assert code == 200 and any(row['operation_id'] == manifest['operation_id']
                                   for row in report['operations'])
        for route, method, payload in (
            ('/api/trash/' + token + '/restore', 'POST', {}),
            ('/api/trash/' + token, 'DELETE', None),
            ('/api/orphan-assets', 'DELETE', None),
            ('/api/records', 'POST', {'type': 'issue', 'project_id': records[0]['project_id'], 'title': '必须受阻'})):
            code, _ = http(origin, route, method, payload)
            assert code == 503, (route, code)
    assert evidence(data, private) == original
    return True


def verify_unknown_formats(base, data, private, transport):
    results = {}
    for kind in ('execution', 'approval', 'registry', 'authorization', 'management', 'transport'):
        copied, secret = clone(base, 'future-' + kind, data, private)
        directory = secret / transport['workspace_id']
        if kind == 'execution':
            path = next((copied / '.agent/operations').glob('*/manifest.json'))
            field = 'execution_schema_version'
        elif kind == 'approval':
            path = next((copied / '.agent/proposal-actions').glob('*.json'))
            field = 'schema_version'
        elif kind == 'management':
            path = next((directory / 'management-operations').glob('*.json'))
            field = 'schema_version'
        elif kind == 'transport':
            path, field = directory / (transport['client_id'] + '.json'), 'schema_version'
        else:
            path, field = directory / 'clients.json', 'schema_version'
        value = read_json(path)
        if kind == 'authorization':
            value['clients'][transport['client_id']]['authorization_schema_version'] = 99
        else:
            value[field] = 99
        atomic_write_json(path, value)
        before = evidence(copied, secret)
        if kind in {'authorization', 'transport'}:
            # These formats are checked at authentication or credential mutation,
            # rather than preventing the ordinary local service from starting.
            with running_server(copied, secret, enabled=True) as origin:
                status, failure = http(origin, '/api/agent/v1/capabilities', headers=agent_headers(transport))
                if kind == 'authorization':
                    assert status == 503 and failure['code'] == 'unsupported_schema'
                    status, failure = http(origin, '/api/agent/v1/proposals', 'POST', {}, agent_headers(transport))
                    assert status == 503 and failure['code'] == 'unsupported_schema'
                else:
                    assert status == 200
                status, state = http(origin, '/api/local/agent-management/status')
                assert status == 200
                client = read_json(directory / 'clients.json')['clients'][transport['client_id']]
                if kind == 'transport':
                    status, failure = http(origin, '/api/local/agent-management/clients/' + transport['client_id'] + '/rotate',
                        'POST', {'workspace_id': transport['workspace_id'], 'request_id': 'future-transport-rotate',
                                 'expected_version': client_version(client)}, {
                            'Origin': origin, 'X-Workbench-Management-Token': state['management_token']})
                    assert status == 503 and failure['code'] == 'unsupported_schema'
        else:
            assert_rejected_startup(copied, secret)
        assert evidence(copied, secret) == before, kind
        results[kind] = True
    return results


@contextmanager
def legacy_worktree(base):
    directory = (base / 'ag134-code').resolve()
    assert directory.is_relative_to(base.resolve()) and not directory.exists()
    result, _, _ = bounded_run(['git', 'worktree', 'add', '--detach', str(directory), LEGACY], timeout=30)
    assert result == 0
    try:
        result, revision, _ = bounded_run(['git', 'rev-parse', 'HEAD'], cwd=directory)
        assert result == 0 and revision.decode().startswith(LEGACY)
        yield directory
    finally:
        result, _, _ = bounded_run(['git', 'worktree', 'remove', str(directory)], timeout=30)
        assert result == 0 and not directory.exists()


def verify_legacy(base, data, private, archive):
    with legacy_worktree(base) as code:
        copied, secret = clone(base, 'legacy-reject', data, private)
        before = evidence(copied, secret)
        # The actual old validators/readers must refuse; do not manufacture old versions.
        probe = '''import json,sys
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity,AgentError
from workbench.agent_runtime import AgentRuntime
from workbench.agent_proposal_management import ProposalManagement
r=Repository(Path(sys.argv[1]));s=AgentSecurity(r.root,Path(sys.argv[2]))
r.agent_runtime=AgentRuntime(r,base=Path(sys.argv[2]))
assert r.agent_proposals.recover()['blocked']
for operation in (s.clients,s.manager().report):
 try: operation()
 except AgentError: pass
 else: raise AssertionError('Old credential reader accepted new state')
m=ProposalManagement(r.agent_runtime)
actions=[json.loads(p.read_text(encoding='utf-8')) for p in m.directory.glob('*.json')]
action=next(a for a in actions if json.loads((r.agent_proposals.proposals/(a['proposal_id']+'.json')).read_text(encoding='utf-8'))['kind']=='concept_map')
# Approval schema 3 itself is unchanged: a completed historical query may
# return its original receipt, even though new execution and credentials fail.
completed=m.action(action['request_id'])
assert completed['state']=='completed' and completed['receipt']==action['result']
print(json.dumps({'execution':True,'credentials':True,'completed_approval_original_receipt':True}))
'''
        result, output, errors = bounded_run([sys.executable, '-c', probe, str(copied), str(secret)], cwd=code)
        assert result == 0, ('Frozen old-code format probe failed', errors.decode(errors='replace')[-2000:])
        assert all(json.loads(output).values()) and evidence(copied, secret) == before
        assert_rejected_startup(copied, secret, code=code)
        assert evidence(copied, secret) == before

        # Compatible old backups are generated by that same old program from the
        # portable business copy, never by downgrading modern journals in place.
        old_data, old_private = base / 'legacy-origin/data', base / 'legacy-origin/private'
        old_data.mkdir(parents=True)
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            package.extractall(old_data)
        initialize = '''import json,sys
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService
r=Repository(Path(sys.argv[1]));s=AgentSecurity(r.root,Path(sys.argv[2]));a=AgentService(r,s)
r.agent_service=a
project=r.list_projects()[0]['id']
created=s.add_client('old matched backup',['read','propose','commit'],[project],[],'http://127.0.0.1:4173',kinds=['issue'])
c=s.clients()[created['client_id']]
p=a.prepare_proposal(c,{'request_id':'old-backup-create','kind':'issue','operation':'create','confirmation_mode':'agent_attested','content':{'project_id':project,'title':'旧版原生匹配备份','body':'旧版实际生成'}})
v=a.preview_proposal(c,p['proposal_id'])
receipt=a.commit_proposal(c,p['proposal_id'],{'version':v['version'],'preview_digest':v['preview_digest'],'confirmation':{'mode':'agent_attested','user_confirmed':True,'note':'isolated acceptance'}})
print(json.dumps({'receipt':receipt,'config_file':created['config_file']}))
'''
        result, output, _ = bounded_run([sys.executable, '-c', initialize, str(old_data), str(old_private)], cwd=code)
        assert result == 0, 'Frozen old-code backup initialization failed'
        old_result = json.loads(output)
        old_transport = read_json(Path(old_result['config_file']))
        source_before = evidence(old_data, old_private)
        restored, restored_private = clone(base, 'legacy-matched-backup', old_data, old_private)
        before = evidence(restored, restored_private)
        source_before[0]['config/settings.json'] = before[0]['config/settings.json']
        assert source_before == before
        with running_server(restored, restored_private, enabled=True, code=code) as origin:
            assert http(origin, '/api/agent/v1/capabilities', headers=agent_headers(old_transport))[0] == 200
            receipt = old_result['receipt']
            status, proposal = http(origin, '/api/agent/v1/proposals/' + receipt['proposal_id'],
                                    headers=agent_headers(old_transport))
            assert status == 200
            assert proposal['receipt'] == {**receipt, 'web_url': origin + receipt['web_path']}
            assert read_json(restored / '.agent/receipts' / (receipt['proposal_id'] + '.json')) == receipt
            status, item = http(origin, '/api/records/' + receipt['item_id'])
            assert status == 200 and item['body'] == '旧版实际生成', (status, item)
        assert evidence(restored, restored_private) == before
    return {'commit': LEGACY, 'incompatible_execution_and_credentials_rejected': True,
            'compatible_completed_approval_receipt_unchanged': True, 'matched_old_backup': True}


def verify_runtime_boundaries(base, data, private, transport, receipts, archive):
    original = evidence(data, private)
    result = {
        'enabled_disable_restart_and_web_persistence': verify_disabled_http(base, data, private, transport, receipts),
        'disabled_pending_protection': verify_disabled_pending_http(base, transport),
        'unknown_format_zero_write': verify_unknown_formats(base, data, private, transport),
        'legacy': verify_legacy(base, data, private, archive),
    }
    assert evidence(data, private) == original
    return result
