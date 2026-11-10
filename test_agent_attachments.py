"""Isolated formal attachment authorization, proposals and disk recovery."""

import hashlib
import json
import unittest
import uuid
import threading
import time
import tempfile
import shutil
import subprocess
import sys
import os
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

from test_agent_support import AgentFixture
import test_agent_uploads as upload_tests
from workbench.agent_file_handles import SUPPORTED
from workbench.agent_security import AgentError
from workbench.agent_runtime import AgentRuntime
from workbench.agent_upload_policy import UploadPolicyManagement, load_policies
from workbench.agent_attachments import AttachmentService


@unittest.skipUnless(SUPPORTED, 'Native NTFS attachment staging requires Windows')
class AttachmentTests(AgentFixture, unittest.TestCase):
    policy = upload_tests.UploadTests.policy
    spec = upload_tests.UploadTests.spec
    permit = upload_tests.UploadTests.permit
    receive = upload_tests.UploadTests.receive

    def setUp(self):
        super().setUp()
        self.repo.agent_service = self.service
        self.runtime = AgentRuntime(self.repo, base=self.base / 'credentials')
        self.repo.agent_runtime = self.runtime
        self.policies = UploadPolicyManagement(self.runtime)
        self.uploads = self.service.uploads
        self.attachments = AttachmentService(self.service)

    def proposal(self, kind='project', owner_id=None, mode='agent_attested', data=b'formal bytes', insert_link=None):
        owner_id = owner_id or self.project['id']
        self.policy_id = self.policy(owner_kind=kind, owner_id=owner_id, attachment_write=True, minimum_confirmation_mode=mode)
        upload_id, _ = self.receive(self.spec(data, owner_kind=kind, owner_id=owner_id), data)
        self.uploads.complete(upload_id, self.permit)
        target = self.attachments.target(self.client, kind, owner_id)
        payload = {'request_id':uuid.uuid4().hex, 'kind':'attachment', 'operation':'create', 'target_id':owner_id,
                   'base_revision':target['revision'], 'content':{'owner_kind':kind, 'owner_id':owner_id,
                    'upload_id':upload_id, 'display_name':'正式附件.txt', 'category':self.repo.get_document(owner_id)[0]['category'] if kind == 'document' else '', 'insert_link':kind != 'project' if insert_link is None else insert_link}}
        return self.service.prepare_proposal(self.client, payload), upload_id, payload

    def test_document_joint_policy_commit_history_and_retirement(self):
        document = self.repo.create_document({'title':'文档附件', 'category':'允许', 'body':'保留正文'})
        path = Path(document['file_path'])
        path.write_text(path.read_text(encoding='utf-8').replace('type: "document"\n', 'type: "document"\nproject_id: "legacy-unknown-project-field"\n'), encoding='utf-8')
        proposal, upload_id, payload = self.proposal('document', document['id'])
        self.assertEqual(proposal['access_target'], {'type':'document', 'category':'允许'})
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        receipt = self.commit(preview)
        self.assertEqual(receipt['owner_kind'], 'document')
        self.assertIsNone(receipt['project_id'])
        self.assertIn('item=document', receipt['web_path'])
        self.assertEqual(self.repo.attachment_path(document['id'], receipt['attachment']['name']).read_bytes(), b'formal bytes')
        saved, _ = self.repo.get_document(document['id'])
        self.assertIn('保留正文', saved['body'])
        self.assertEqual(saved['project_id'], 'legacy-unknown-project-field')
        self.assertEqual(len(saved['attachments']), 1)
        self.assertEqual(len(self.repo.list_document_history(document['id'])), 1)
        target = next(x for x in self.repo.list_reference_targets() if x['id'] == document['id'])
        self.assertEqual(target['attachments'][0]['name'], receipt['attachment']['name'])
        self.uploads.recover_and_cleanup(self.permit, cleanup=True)
        self.assertTrue(self.uploads.load(upload_id)['removed'])
        self.assertEqual(self.commit(preview), receipt)

    def test_document_stage_only_and_category_change_never_expand_access(self):
        document = self.repo.create_document({'title':'文档类别', 'category':'允许'})
        self.policy_id = self.policy(owner_kind='document', owner_id=document['id'])
        with self.assertRaises(AgentError):
            self.attachments.target(self.client, 'document', document['id'])
        proposal, upload_id, payload = self.proposal('document', document['id'])
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        self.repo.rename_document_category('允许', '改名')
        with self.assertRaises((AgentError, FileExistsError)):
            self.commit(preview)
        self.assertFalse(self.repo.get_document(document['id'])[0].get('attachments'))
        self.assertFalse((self.repo.global_assets_dir / 'files' / '正式附件.txt').exists())

    def test_joint_policy_has_no_revision_loop_and_preview_has_no_formal_writes(self):
        proposal, upload_id, payload = self.proposal()
        self.assertEqual(load_policies(self.security)['schema_version'], 2)
        self.assertEqual(proposal['kind'], 'attachment')
        self.assertEqual(proposal['execution_plan']['handler'], 'attachment@1')
        self.assertEqual(self.uploads.load(upload_id)['binding']['proposal_id'], proposal['proposal_id'])
        self.assertEqual(self.service.prepare_proposal(self.client, payload)['proposal_id'], proposal['proposal_id'])
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        self.assertEqual(preview['content']['attachment']['sha256'], hashlib.sha256(b'formal bytes').hexdigest())
        self.assertTrue(preview['content']['unparsed_binary'])
        self.assertFalse((self.repo.root / preview['content']['binary_relative']).exists())
        self.assertFalse((self.repo.root / preview['content']['metadata_relative']).exists())
        self.assertEqual(self.attachments.prepare_submission(self.client, self.service.store._load(proposal['proposal_id'])).view, preview['content'])

    def test_old_stage_and_dormant_permissions_do_not_grant_formal_write(self):
        self.policy_id = self.policy()
        with self.assertRaises(AgentError) as caught:
            self.attachments.target(self.client, 'project', self.project['id'])
        self.assertEqual(caught.exception.code, 'forbidden')

    def test_unreadable_legacy_attachment_metadata_does_not_create_invalid_proposal(self):
        record = self.repo.create_record({'type':'issue', 'title':'旧附件损坏', 'project_id':self.project['id'], 'attachments':['not JSON']})
        before = Path(record['file_path']).read_bytes()
        with self.assertRaises(ValueError):
            self.proposal('issue', record['id'])
        self.assertEqual(Path(record['file_path']).read_bytes(), before)
        self.assertEqual(list(self.service.store.proposals.glob('*.json')), [])
        self.service.store.preflight()

    def test_formal_project_commit_consumes_once_and_persists_real_bytes(self):
        from workbench.agent_attachment_execution import AttachmentExecution
        from server import Repository
        proposal, upload_id, payload = self.proposal()
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
        execution = AttachmentExecution(self.service)
        receipt = execution.commit(self.client, proposal['proposal_id'], request)
        self.assertEqual(execution.commit(self.client, proposal['proposal_id'], request), receipt)
        self.assertTrue(self.service.get_proposal(self.client, proposal['proposal_id'])['current_item']['exists'])
        reopened = Repository(self.repo.root)
        assets = reopened.project_assets(self.project['id'])
        self.assertEqual(len(assets), 1)
        self.assertEqual(reopened.project_asset_path(self.project['id'], assets[0]['id']).read_bytes(), b'formal bytes')
        self.assertEqual(self.uploads.load(upload_id)['state'], 'consumed')
        self.assertEqual(self.uploads.load(upload_id)['consumption']['operation_id'], receipt['consumption_id'])

    def test_formal_record_commit_preserves_history_and_does_not_recreate_deleted_attachment(self):
        from workbench.agent_attachment_execution import AttachmentExecution
        record = self.repo.create_record({'type':'issue', 'title':'旧正文', 'body':'原正文', 'project_id':self.project['id']})
        proposal, upload_id, payload = self.proposal('issue', record['id'])
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
        execution = AttachmentExecution(self.service)
        receipt = execution.commit(self.client, proposal['proposal_id'], request)
        self.assertEqual(len(self.repo.list_history(record['id'])), 1)
        self.assertEqual(self.repo.attachment_path(record['id'], receipt['attachment']['name']).read_bytes(), b'formal bytes')
        self.repo.delete_record_attachment(record['id'], receipt['attachment']['name'])
        self.assertEqual(execution.commit(self.client, proposal['proposal_id'], request), receipt)
        self.assertIsNone(self.repo.attachment_path(record['id'], receipt['attachment']['name']))

    def test_record_preview_preserves_body_and_metadata_and_minimum_mode(self):
        record = self.repo.create_record({'type':'info', 'project_id':self.project['id'], 'title':'字段',
                                         'info_fields':[{'name':'命令', 'value':' a\n"b" ', 'note':'尾部 '}]})
        # Existing explicit legacy kind permission remains necessary.
        result = self.security.manager().run('edit', {**{key:self.client[key] for key in ('name', 'scopes', 'project_ids', 'categories')}, 'kinds':['issue', 'todo', 'info']}, self.client['client_id'])
        self.client = self.security.clients()[self.client['client_id']]
        proposal, upload_id, payload = self.proposal('info', record['id'], 'local_web')
        self.assertEqual(proposal['confirmation_mode'], 'local_web')
        self.assertEqual(proposal['normalized_content']['metadata_before']['info_fields'], proposal['normalized_content']['metadata_after']['info_fields'])
        self.assertEqual(self.repo.get_record(record['id'])[0]['body'], record['body'])

    def test_commit_times_are_actual_acceptance_times_and_replay_is_stable(self):
        from datetime import datetime
        from workbench.agent_attachment_execution import AttachmentExecution
        record = self.repo.create_record({'type':'issue', 'title':'时间', 'project_id':self.project['id']})
        with patch('workbench.agent_proposals.stamp', return_value='2000-01-01T00:00:00+00:00'):
            proposal, upload_id, payload = self.proposal('issue', record['id'])
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
        execution = AttachmentExecution(self.service)
        receipt = execution.commit(self.client, proposal['proposal_id'], request)
        accepted = datetime.fromisoformat(receipt['committed_at'])
        self.assertNotEqual(accepted.year, 2000)
        self.assertTrue(self.repo.list_history(record['id'])[0]['version'].startswith(accepted.astimezone().strftime('%Y%m%d-%H%M%S-')))
        self.assertEqual(self.repo.get_record(record['id'])[0]['updated'], accepted.astimezone().isoformat(timespec='seconds'))
        self.assertEqual(execution.commit(self.client, proposal['proposal_id'], request), receipt)

    def test_completed_consumption_can_retire_source_and_keep_receipt_and_idempotence(self):
        from workbench.agent_attachment_execution import AttachmentExecution
        from workbench.agent_uploads import LIMITS
        receipts = []
        with patch.dict(LIMITS, client_bytes=len(b'formal bytes')):
            for iteration in range(3):
                proposal, upload_id, payload = self.proposal()
                preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
                request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
                execution = AttachmentExecution(self.service)
                receipt = execution.commit(self.client, proposal['proposal_id'], request)
                old = self.uploads.load(upload_id)
                with self.assertRaises(AgentError) as caught:
                    self.uploads.create(self.client, self.spec(b'formal bytes'))
                self.assertEqual(caught.exception.code, 'upload_quota')
                self.uploads.recover_and_cleanup(self.permit, cleanup=True)
                self.assertTrue(self.uploads.load(upload_id)['removed'])
                self.assertFalse(self.uploads.path(upload_id, 'blob.bin').exists())
                replay = self.uploads.create(self.client, self.spec(b'formal bytes', policy_id=old['policy_id'], request_id=old['request_id']))
                self.assertEqual(replay['upload_id'], upload_id)
                self.assertTrue(replay['removed'])
                self.assertEqual(execution.commit(self.client, proposal['proposal_id'], request), receipt)
                receipts.append(receipt)
        self.assertEqual(len(self.repo.project_assets(self.project['id'])), 3)
        self.assertEqual(len({item['item_id'] for item in receipts}), 3)

    def test_record_body_is_byte_preserved_without_link_and_corrupt_body_is_rejected(self):
        from workbench.agent_attachment_execution import AttachmentExecution
        from workbench.attachment_prepared import raw_markdown_body
        record = self.repo.create_record({'type':'issue', 'title':'原文', 'project_id':self.project['id']})
        path = Path(record['file_path'])
        header = path.read_text(encoding='utf-8').split('\n---\n', 1)[0]
        path.write_bytes((header + '\nprivate_extra: "保留  空格"\n---\n\n  leading \r\n末尾 \n  ').encode('utf-8'))
        self.repo._forget_record(path)
        before_body = raw_markdown_body(path.read_bytes())
        proposal, upload_id, payload = self.proposal('issue', record['id'], insert_link=False)
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        self.assertEqual(preview['content']['body'], before_body)
        request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
        AttachmentExecution(self.service).commit(self.client, proposal['proposal_id'], request)
        self.assertEqual(raw_markdown_body(path.read_bytes()), before_body)
        self.assertEqual(self.repo.get_record(record['id'])[0]['private_extra'], '保留  空格')
        other = self.repo.create_record({'type':'issue', 'title':'损坏正文', 'project_id':self.project['id']})
        proposal, _, _ = self.proposal('issue', other['id'], insert_link=False)
        raw = self.service.store._load(proposal['proposal_id'])
        raw['normalized_content']['body'] = '未经授权的正文'
        from workbench.agent_execution import bind_context
        bind_context(raw, self.client, raw['dependencies'])
        self.service.store._save(raw)
        with self.assertRaises(AgentError):
            self.service.store.preflight()

    def test_occupied_preview_name_never_adopts_same_or_different_bytes_and_revision_repreviews(self):
        from workbench.agent_attachment_execution import AttachmentExecution
        for content in (b'formal bytes', b'other bytes'):
            case = AttachmentTests(self._testMethodName)
            case.setUp()
            try:
                proposal, upload_id, payload = case.proposal()
                preview = case.service.preview_proposal(case.client, proposal['proposal_id'])
                binary = case.repo.root / preview['content']['binary_relative']
                binary.parent.mkdir(parents=True, exist_ok=True)
                binary.write_bytes(content)
                request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
                with self.assertRaises(AgentError) as caught:
                    AttachmentExecution(case.service).commit(case.client, proposal['proposal_id'], request)
                self.assertEqual(caught.exception.code, 'attachment_name_conflict')
                self.assertEqual(binary.read_bytes(), content)
                self.assertFalse((case.repo.root / preview['content']['metadata_relative']).exists())
                revised = case.service.revise_proposal(case.client, proposal['proposal_id'], {'expected_version':1, 'content':payload['content']})
                self.assertNotEqual(revised['normalized_content']['binary_relative'], preview['content']['binary_relative'])
                with self.assertRaises(AgentError):
                    AttachmentExecution(case.service).commit(case.client, proposal['proposal_id'], request)
            finally:
                case.tearDown()

    def test_hundred_mib_formal_copy_has_bounded_memory_and_real_persistent_bytes(self):
        import tracemalloc
        from workbench.agent_attachment_execution import AttachmentExecution
        self.policy_id = self.policy(attachment_write=True, minimum_confirmation_mode='agent_attested')
        chunk = b'x' * 65536
        checksum = hashlib.sha256()
        for _ in range(1600):
            checksum.update(chunk)
        spec = self.spec(b'', bytes=104857600, sha256=checksum.hexdigest())
        session = self.uploads.create(self.client, spec)
        self.uploads.receive(session['upload_id'], (chunk for _ in range(1600)), self.permit)
        self.uploads.complete(session['upload_id'], self.permit)
        target = self.attachments.target(self.client, 'project', self.project['id'])
        proposal = self.service.prepare_proposal(self.client, {'request_id':uuid.uuid4().hex, 'kind':'attachment', 'operation':'create',
                  'target_id':self.project['id'], 'base_revision':target['revision'], 'content':{'owner_kind':'project', 'owner_id':self.project['id'],
                  'upload_id':session['upload_id'], 'display_name':'large.bin', 'category':'', 'insert_link':False}})
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
        tracemalloc.start(); start = time.monotonic()
        try:
            receipt = AttachmentExecution(self.service).commit(self.client, proposal['proposal_id'], request)
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 8 * 1048576)
        formal = self.repo.project_asset_path(self.project['id'], receipt['item_id'])
        actual = hashlib.sha256()
        with formal.open('rb') as stream:
            while value := stream.read(65536):
                actual.update(value)
        self.assertEqual(formal.stat().st_size, 104857600)
        self.assertEqual(actual.hexdigest(), checksum.hexdigest())
        print(json.dumps({'attachment_copy_bytes':104857600, 'python_peak_bytes':peak, 'elapsed_seconds':round(time.monotonic() - start, 3)}))

    def test_disabled_server_startup_recovers_previously_accepted_attachment_unlocked(self):
        from urllib.request import urlopen
        from urllib.error import URLError
        import socket
        from workbench.agent_attachment_execution import AttachmentExecution
        proposal, upload_id, payload = self.proposal()
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
        def crash(stage):
            if stage == 'attachment_binary':
                raise OSError('synthetic exit before metadata')
        with patch.object(self.service.store, 'checkpoint', crash), self.assertRaises(OSError):
            AttachmentExecution(self.service).commit(self.client, proposal['proposal_id'], request)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
        process = subprocess.Popen([sys.executable, 'server.py', '--data-dir', str(self.repo.root), '--agent-config-dir', str(self.base / 'credentials'), '--disable-agent', '--port', str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for _attempt in range(100):
                if process.poll() is not None:
                    self.fail(process.stderr.read().decode(errors='replace'))
                try:
                    with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=0.2) as response:
                        self.assertTrue(json.load(response)['ok'])
                    break
                except (URLError, TimeoutError):
                    time.sleep(0.05)
            else:
                self.fail('isolated disabled server did not start')
            state = json.loads((self.repo.root / '.agent' / 'proposals' / (proposal['proposal_id'] + '.json')).read_text(encoding='utf-8'))
            self.assertEqual(state['state'], 'committed')
            self.assertEqual((self.repo.root / preview['content']['binary_relative']).read_bytes(), b'formal bytes')
        finally:
            process.terminate(); process.communicate(timeout=10)

    def test_mixed_markdown_and_todo_attachment_contracts_and_actual_old_binary_refusal(self):
        import io
        import zipfile
        from workbench.agent_attachment_execution import AttachmentExecution
        from workbench.agent_service import AgentService
        params = {key:self.client[key] for key in ('name', 'scopes', 'project_ids', 'categories')}
        self.security.manager().run('edit', {**params, 'kinds':['issue', 'todo', 'info']}, self.client['client_id'])
        self.client = self.security.clients()[self.client['client_id']]
        todo = self.repo.create_record({'type':'todo', 'title':'附件待办', 'project_id':self.project['id'], 'due':'2026-12-31'})
        attachment, upload_id, _payload = self.proposal('todo', todo['id'])
        markdown = self.service.prepare_proposal(self.client, {'request_id':uuid.uuid4().hex, 'kind':'issue', 'operation':'create', 'content':{'title':'旧处理器', 'body':'原Markdown流程', 'project_id':self.project['id']}})
        preview = self.service.preview_proposal(self.client, markdown['proposal_id'])
        self.service.commit_proposal(self.client, markdown['proposal_id'], {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}})
        preview = self.service.preview_proposal(self.client, attachment['proposal_id'])
        AttachmentExecution(self.service).commit(self.client, attachment['proposal_id'], {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}})
        reopened = self.repo.get_record(todo['id'])[0]
        for key in ('due', 'status', 'priority', 'completed'):
            self.assertEqual(reopened[key], todo[key])
        legacy = self.repo.create_record({'type':'issue', 'title':'旧ID转换待办', 'project_id':self.project['id']})
        converted = self.repo.convert_record(legacy['id'], 'todo')
        legacy_proposal, _, _ = self.proposal('todo', converted['id'])
        legacy_preview = self.service.preview_proposal(self.client, legacy_proposal['proposal_id'])
        legacy_receipt = self.service.commit_proposal(self.client, legacy_proposal['proposal_id'], {'version':1, 'preview_digest':legacy_preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}})
        self.assertIsNone(legacy_receipt['web_path'])
        self.assertTrue(self.repo.attachment_path(converted['id'], legacy_receipt['attachment']['name']).exists())
        self.assertEqual(self.repo.get_record(converted['id'])[0]['id'], legacy['id'])
        self.service.store.preflight()
        json_before = {str(file):file.read_bytes() for root in (self.repo.root, self.security.config_dir) for file in root.rglob('*.json')}
        archive = subprocess.run(['git', 'archive', '--format=zip', 'b7ce3fe'], capture_output=True, check=True).stdout
        with tempfile.TemporaryDirectory(prefix='workbench-old-attachment-') as old:
            with zipfile.ZipFile(io.BytesIO(archive)) as package:
                package.extractall(old)
            worker = '''
import sys,json
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity,AgentError
repo=Repository(Path(sys.argv[1]))
assert repo.agent_proposals.recovery_report()['blocked'] is True
try: AgentSecurity(repo.root,Path(sys.argv[2])).manager().recover()
except AgentError as error: assert error.code=='management_recovery_required'
else: raise AssertionError('old manager accepted future policy')
print('old binary rejected future attachment contracts')
'''
            result = subprocess.run([sys.executable, '-c', worker, str(self.repo.root), str(self.base / 'credentials')], cwd=old, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual({str(file):file.read_bytes() for root in (self.repo.root, self.security.config_dir) for file in root.rglob('*.json')}, json_before)
        manifest = self.service.store.operations / (attachment['proposal_id'] + '-1') / 'manifest.json'
        value = json.loads(manifest.read_text(encoding='utf-8'))
        value['execution_schema_version'] = 99
        manifest.write_text(json.dumps(value), encoding='utf-8')
        before = {str(file):file.read_bytes() for file in self.repo.root.rglob('*') if file.is_file()}
        with self.assertRaises(AgentError):
            self.service.store.cleanup()
        self.assertEqual({str(file):file.read_bytes() for file in self.repo.root.rglob('*') if file.is_file()}, before)

    def test_joint_policy_real_exit_converts_stage_schema_without_implicit_write_grants(self):
        from workbench.agent_management import client_version
        worker = '''
import os,sys,json
from pathlib import Path
from workbench.agent_security import AgentSecurity
from workbench.agent_management import CredentialManager
def checkpoint(self,stage):
 if stage==sys.argv[3]: os._exit(79)
CredentialManager.checkpoint=checkpoint
security=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2]))
security.manager().run('attachment_policy',json.loads(sys.argv[4]),sys.argv[5],sys.argv[6],sys.argv[7])
'''
        for stage in ['private_snapshot', 'prepared', 'format_fence', 'upload_policy', 'registry', 'terminal_log', 'completed']:
            with self.subTest(stage=stage):
                case = AttachmentTests(self._testMethodName); case.setUp()
                try:
                    old = case.policy()
                    preview = case.policies.preview(case.client['client_id'], {'workspace_id':case.security.workspace_id, 'expected_version':client_version(case.client),
                              'owner_kind':'project', 'owner_id':case.project['id'], 'stream':True, 'files':[], 'max_bytes':104857600, 'duration_seconds':3600,
                              'attachment_write':True, 'minimum_confirmation_mode':'local_web'})
                    params = {'policy':preview['policy'], 'approval_digest':preview['preview_digest']}
                    child = subprocess.run([sys.executable, '-c', worker, str(case.repo.root), str(case.base / 'credentials'), stage,
                                            json.dumps(params), case.client['client_id'], preview['expected_version'], stage], capture_output=True, timeout=20)
                    self.assertEqual(child.returncode, 79, child.stderr.decode(errors='replace'))
                    case.security.manager().recover()
                    ledger = load_policies(case.security)
                    self.assertEqual(ledger['schema_version'], 1 if stage == 'private_snapshot' else 2)
                    if stage != 'private_snapshot':
                        self.assertFalse(ledger['policies'][old]['enabled'])
                        self.assertIsNone(ledger['policies'][old]['attachment_write'])
                        replay = case.security.manager().run('attachment_policy', {'policy':None, 'approval_digest':preview['preview_digest']}, case.client['client_id'], preview['expected_version'], stage)
                        self.assertEqual(replay['policy_id'], preview['policy']['policy_id'])
                    self.assertFalse(list((case.security.config_dir / 'management-snapshots').glob('*.json')))
                finally:
                    case.tearDown()

    def test_published_name_replaced_with_same_or_different_bytes_is_never_adopted(self):
        from workbench.agent_attachment_execution import AttachmentExecution
        worker = '''
import os,sys,json
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService
from workbench.agent_proposals import ProposalStore
from workbench.agent_attachment_execution import AttachmentExecution
def checkpoint(self,stage):
 if stage=='attachment_binary': os._exit(80)
ProposalStore.checkpoint=checkpoint
repo=Repository(Path(sys.argv[1])); security=AgentSecurity(repo.root,Path(sys.argv[2])); service=AgentService(repo,security)
AttachmentExecution(service).commit(security.clients()[sys.argv[3]],sys.argv[4],json.loads(sys.argv[5]))
'''
        for content in (b'formal bytes', b'third party bytes'):
            with self.subTest(same=content == b'formal bytes'):
                case = AttachmentTests(self._testMethodName); case.setUp()
                try:
                    proposal, upload_id, payload = case.proposal()
                    preview = case.service.preview_proposal(case.client, proposal['proposal_id'])
                    request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
                    child = subprocess.run([sys.executable, '-c', worker, str(case.repo.root), str(case.base / 'credentials'), case.client['client_id'], proposal['proposal_id'], json.dumps(request)], capture_output=True, timeout=20)
                    self.assertEqual(child.returncode, 80, child.stderr.decode(errors='replace'))
                    binary = case.repo.root / preview['content']['binary_relative']
                    replacement = binary.with_name('external-replacement.bin')
                    replacement.write_bytes(content)
                    os.replace(replacement, binary)
                    report = AttachmentExecution(case.service).recover()
                    self.assertTrue(report['blocked'])
                    self.assertEqual(binary.read_bytes(), content)
                    self.assertFalse((case.repo.root / preview['content']['metadata_relative']).exists())
                    self.assertIsNone(case.uploads.load(upload_id)['consumption'])
                    with self.assertRaises(AgentError):
                        case.repo.cleanup_orphan_assets()
                    self.assertEqual(binary.read_bytes(), content)
                finally:
                    case.tearDown()

    def test_category_collection_change_and_revocation_before_or_after_metadata_are_distinct(self):
        import io
        from workbench.agent_attachment_execution import AttachmentExecution
        legacy = self.repo.add_project_asset_stream(self.project['id'], 'legacy.txt', io.BytesIO(b'legacy'), 6, '遗留分类')
        category_file = self.repo.projects_dir / self.project['id'] / 'assets' / 'categories.json'
        category_file.unlink()  # Synthetic legacy inferred-category fixture.
        record = self.repo.create_record({'type':'issue', 'title':'类别版本', 'project_id':self.project['id']})
        proposal, upload_id, payload = self.proposal('issue', record['id'])
        revised = self.service.revise_proposal(self.client, proposal['proposal_id'], {'expected_version':1, 'content':{**payload['content'], 'category':'遗留分类'}})
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        index = self.repo.projects_dir / self.project['id'] / 'assets' / 'index.json'
        items = json.loads(index.read_text(encoding='utf-8')); items[0]['category'] = ''
        index.write_text(json.dumps(items, ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(AgentError) as caught:
            AttachmentExecution(self.service).commit(self.client, proposal['proposal_id'], {'version':2, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}})
        self.assertEqual(caught.exception.code, 'dependency_changed')
        self.assertFalse((self.repo.root / revised['normalized_content']['binary_relative']).exists())
        for stage in ('attachment_binary', 'attachment_target'):
            with self.subTest(stage=stage):
                case = AttachmentTests(self._testMethodName); case.setUp()
                try:
                    record = case.repo.create_record({'type':'issue', 'title':'撤销阶段', 'project_id':case.project['id']})
                    proposal, upload_id, _payload = case.proposal('issue', record['id'])
                    preview = case.service.preview_proposal(case.client, proposal['proposal_id'])
                    def interrupt(current):
                        if current == stage:
                            raise OSError('synthetic interruption')
                    with patch.object(case.service.store, 'checkpoint', interrupt), self.assertRaises(OSError):
                        AttachmentExecution(case.service).commit(case.client, proposal['proposal_id'], {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}})
                    case.security.manager().run('revoke', {}, case.client['client_id'])
                    report = AttachmentExecution(case.service).recover()
                    state = case.service.store._load(proposal['proposal_id'])
                    self.assertEqual(report['blocked'], stage == 'attachment_binary')
                    self.assertEqual(state['state'] == 'committed', stage == 'attachment_target')
                    self.assertEqual(case.uploads.load(upload_id)['consumption'] is not None, stage == 'attachment_target')
                finally:
                    case.tearDown()

    def test_real_process_exit_recovers_fixed_plan_copy_publish_metadata_consume_and_receipt(self):
        for kind in ('issue', 'document'):
            with self.subTest(owner_kind=kind):
                self._assert_real_attachment_exit(kind)

    def _assert_real_attachment_exit(self, kind):
        from server import Repository
        from workbench.agent_security import AgentSecurity
        from workbench.agent_service import AgentService
        from workbench.agent_attachment_execution import AttachmentExecution
        record = self.repo.create_document({'title':'故障恢复文档', 'body':'不可丢失的原文', 'category':'允许'}) if kind == 'document' else self.repo.create_record({'type':'issue', 'title':'故障恢复', 'body':'不可丢失的原文', 'project_id':self.project['id']})
        proposal, upload_id, payload = self.proposal(kind, record['id'], data=b'x' * 131072)
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
        worker = '''
import os,sys,json
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService
from workbench.agent_proposals import ProposalStore
from workbench.agent_attachment_execution import AttachmentExecution
def checkpoint(self,stage):
 if stage==sys.argv[3]: os._exit(76)
ProposalStore.checkpoint=checkpoint
repo=Repository(Path(sys.argv[1]))
security=AgentSecurity(repo.root,Path(sys.argv[2]))
service=AgentService(repo,security)
AttachmentExecution(service).commit(security.clients()[sys.argv[4]],sys.argv[5],json.loads(sys.argv[6]))
'''
        stages = ['attachment_snapshots', 'attachment_manifest', 'attachment_committing', 'attachment_copy_partial',
                  'attachment_copy_fsynced', 'attachment_copy_evidence', 'attachment_copy_evidence_logged',
                  'attachment_applying', 'attachment_binary', 'attachment_binary_logged', 'attachment_history',
                  'attachment_target', 'attachment_consumed', 'receipt', 'proposal']
        for stage in stages:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(prefix='workbench-attachment-exit-') as case:
                root = Path(case) / 'data'
                credentials = Path(case) / 'credentials'
                shutil.copytree(self.repo.root, root)
                shutil.copytree(self.base / 'credentials', credentials)
                result = subprocess.run([sys.executable, '-c', worker, str(root), str(credentials), stage,
                                          self.client['client_id'], proposal['proposal_id'], json.dumps(request)], capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 76, result.stderr.decode(errors='replace'))
                repo = Repository(root)
                security = AgentSecurity(root, credentials)
                service = AgentService(repo, security)
                report = AttachmentExecution(service).recover()
                reopened = service.store._load(proposal['proposal_id'])
                if stage in {'attachment_snapshots', 'attachment_copy_partial'}:
                    self.assertFalse((root / preview['content']['binary_relative']).exists())
                    self.assertNotEqual(reopened['state'], 'committed')
                    self.assertEqual(report['blocked'], stage == 'attachment_copy_partial')
                else:
                    self.assertFalse(report['blocked'], report)
                    self.assertEqual(reopened['state'], 'committed')
                    self.assertEqual((root / preview['content']['binary_relative']).read_bytes(), b'x' * 131072)
                    self.assertEqual(len(repo.list_document_history(record['id']) if kind == 'document' else repo.list_history(record['id'])), 1)
                    self.assertEqual(service.uploads.load(upload_id)['state'], 'consumed')
                    self.assertEqual(AttachmentExecution(service).commit(security.clients()[self.client['client_id']], proposal['proposal_id'], request), reopened['receipt'])

    def test_real_process_exit_retirement_releases_only_proven_consumed_source(self):
        from server import Repository
        from workbench.agent_security import AgentSecurity
        from workbench.agent_service import AgentService
        from workbench.agent_attachment_execution import AttachmentExecution
        proposal, upload_id, payload = self.proposal()
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
        receipt = AttachmentExecution(self.service).commit(self.client, proposal['proposal_id'], request)
        worker = '''
import os,sys
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService
from workbench.agent_uploads import UploadStore
def checkpoint(self,stage):
 if stage==sys.argv[3]: os._exit(77)
UploadStore.checkpoint=checkpoint
repo=Repository(Path(sys.argv[1])); security=AgentSecurity(repo.root,Path(sys.argv[2]))
AgentService(repo,security).uploads.recover_and_cleanup(None,True)
'''
        for stage in ['retirement_proven', 'disposal_verified', 'disposal_removed', 'disposal_metadata']:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(prefix='workbench-retire-exit-') as case:
                root, credentials = Path(case) / 'data', Path(case) / 'credentials'
                shutil.copytree(self.repo.root, root)
                shutil.copytree(self.base / 'credentials', credentials)
                child = subprocess.run([sys.executable, '-c', worker, str(root), str(credentials), stage], capture_output=True, timeout=20)
                self.assertEqual(child.returncode, 77, child.stderr.decode(errors='replace'))
                repo = Repository(root)
                security = AgentSecurity(root, credentials)
                service = AgentService(repo, security)
                service.uploads.recover_and_cleanup(None, True)
                self.assertTrue(service.uploads.load(upload_id)['removed'])
                self.assertEqual(service.store._load(proposal['proposal_id'])['receipt'], receipt)
                self.assertEqual((root / preview['content']['binary_relative']).read_bytes(), b'formal bytes')

    def test_real_process_exit_proposal_source_mirror_gaps_remain_protected(self):
        from server import Repository
        from workbench.agent_security import AgentSecurity, private_write
        from workbench.agent_service import AgentService
        proposal, upload_id, payload = self.proposal()
        worker = '''
import os,sys,json
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService
from workbench.agent_proposals import ProposalStore
def checkpoint(self,stage):
 if stage==sys.argv[3]: os._exit(78)
ProposalStore.checkpoint=checkpoint
repo=Repository(Path(sys.argv[1])); security=AgentSecurity(repo.root,Path(sys.argv[2])); service=AgentService(repo,security)
client=security.clients()[sys.argv[4]]; payload=json.loads(sys.argv[6])
if sys.argv[5]=='prepare': service.prepare_proposal(client,payload)
elif sys.argv[5]=='cancel': service.cancel_proposal(client,payload['proposal_id'],{'expected_version':1})
else: service.revise_proposal(client,payload['proposal_id'],{'expected_version':1,'content':payload['content']})
'''
        for operation, stage in [('prepare', 'attachment_proposal_created'), ('cancel', 'attachment_proposal_cancelled'), ('revise', 'attachment_proposal_revised')]:
            with self.subTest(operation=operation), tempfile.TemporaryDirectory(prefix='workbench-mirror-exit-') as case:
                root, credentials = Path(case) / 'data', Path(case) / 'credentials'
                shutil.copytree(self.repo.root, root)
                shutil.copytree(self.base / 'credentials', credentials)
                security = AgentSecurity(root, credentials)
                if operation == 'prepare':
                    (root / '.agent' / 'proposals' / (proposal['proposal_id'] + '.json')).unlink()
                    value = self.uploads.load(upload_id)
                    value['binding'] = None
                    private_write(security.config_dir / 'uploads' / upload_id / 'session.json', value)
                    child_payload = payload
                else:
                    child_payload = {'proposal_id':proposal['proposal_id'], 'content':{**payload['content'], 'display_name':'修订名称.txt'}}
                child = subprocess.run([sys.executable, '-c', worker, str(root), str(credentials), stage,
                                         self.client['client_id'], operation, json.dumps(child_payload)], capture_output=True, timeout=20)
                self.assertEqual(child.returncode, 78, child.stderr.decode(errors='replace'))
                repo = Repository(root)
                service = AgentService(repo, security)
                client = security.clients()[self.client['client_id']]
                if operation == 'cancel':
                    service.uploads.cancel(upload_id, client)
                    self.assertIsNone(service.uploads.load(upload_id)['binding'])
                else:
                    with self.assertRaises(AgentError) as caught:
                        service.uploads.cancel(upload_id, client)
                    self.assertEqual(caught.exception.code, 'upload_in_use')
                    bound = service.uploads.load(upload_id)['binding']
                    self.assertEqual(bound['version'], 2 if operation == 'revise' else 1)
                    result = service.uploads.recover_and_cleanup(None, True)
                    self.assertEqual(result[0]['maintenance'], 'protected')
                self.assertTrue(service.uploads.path(upload_id, 'blob.bin').exists())


@unittest.skipUnless(SUPPORTED, 'Native attachment transport requires Windows NTFS')
class AttachmentHTTPTests(unittest.TestCase):
    request = upload_tests.UploadHTTPTests.request
    create = upload_tests.UploadHTTPTests.create
    put = upload_tests.UploadHTTPTests.put

    def setUp(self):
        upload_tests.UploadHTTPTests.setUp(self)
        from workbench.agent_management import client_version
        client = self.security.clients()[self.client_id]
        self.security.manager().run('edit', {**{key:client[key] for key in ('name', 'kinds', 'categories', 'project_ids')},
                                            'scopes':['read', 'propose', 'commit']}, self.client_id, client_version(client))

    def tearDown(self):
        upload_tests.UploadHTTPTests.tearDown(self)

    def proposal(self, mode='agent_attested', kind='project', owner_id=None):
        from workbench.agent_management import client_version
        if kind == 'document':
            owner_id = owner_id or self.repo.create_document({'title':'MCP文档附件', 'category':'原分类', 'body':'保留正文'})['id']
            client = self.security.clients()[self.client_id]
            self.security.manager().run('edit', {**{key:client[key] for key in ('name', 'scopes', 'project_ids')}, 'kinds':['issue', 'document'], 'categories':['原分类']}, self.client_id, client_version(client))
        owner_id = owner_id or self.project['id']
        prefix = f'/api/local/agent-management/clients/{self.client_id}/upload-policy'
        code, preview = self.request(prefix + '/preview', {'workspace_id':self.security.workspace_id, 'expected_version':client_version(self.security.clients()[self.client_id]),
                                      'owner_kind':kind, 'owner_id':owner_id, 'stream':True, 'files':[], 'max_bytes':104857600,
                                      'duration_seconds':3600, 'attachment_write':True, 'minimum_confirmation_mode':mode}, 'POST', True)
        self.assertEqual(code, 200, preview)
        confirm = {key:preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')}
        confirm.update(request_id=uuid.uuid4().hex, approved=True)
        code, approved = self.request(prefix + '/confirm', confirm, 'POST', True)
        self.assertEqual(code, 200, approved)
        self.assertEqual(self.request(prefix + '/confirm', confirm, 'POST', True), (code, approved))
        self.policy_id = approved['policy_id']
        upload_id = self.create(owner_kind=kind, owner_id=owner_id)
        self.assertEqual(self.put(upload_id)[0], 200)
        self.assertEqual(self.request(f'/api/agent/v1/uploads/{upload_id}/complete', {}, 'POST')[0], 200)
        code, target = self.request(f'/api/agent/v1/attachment-targets/{kind}/' + quote(owner_id))
        self.assertEqual(code, 200, target)
        code, proposal = self.request('/api/agent/v1/proposals', {'request_id':uuid.uuid4().hex, 'kind':'attachment', 'operation':'create',
                                         'target_id':owner_id, 'base_revision':target['revision'],
                                         'content':{'owner_kind':kind, 'owner_id':owner_id, 'upload_id':upload_id, 'display_name':'原始附件.txt', 'category':target['categories'][0] if kind == 'document' else '', 'insert_link':kind != 'project'}}, 'POST')
        self.assertEqual(code, 200, proposal)
        return proposal, upload_id

    def test_real_agent_http_formal_commit_download_and_export(self):
        from urllib.request import urlopen
        import zipfile
        import io
        proposal, upload_id = self.proposal()
        code, preview = self.request(f"/api/agent/v1/proposals/{proposal['proposal_id']}/preview")
        self.assertEqual(code, 200, preview)
        request = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
        code, receipt = self.request(f"/api/agent/v1/proposals/{proposal['proposal_id']}/commit", request, 'POST')
        self.assertEqual(code, 200, receipt)
        code, result = self.request(f"/api/agent/v1/proposals/{proposal['proposal_id']}")
        self.assertEqual(code, 200, result)
        self.assertTrue(result['current_item']['exists'])
        with urlopen(self.workbench.base_url + f"/api/project-assets/{quote(self.project['id'])}/{receipt['item_id']}") as response:
            self.assertEqual(response.read(), b'binary\x00stream')
        archive = self.repo.export_zip(self.project['id'])
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            self.assertIn(b'binary\x00stream', [package.read(name) for name in package.namelist()])
            self.assertFalse(any('.agent/' in name or 'binary.part' in name for name in package.namelist()))

    def test_real_local_web_approval_cannot_be_self_attested(self):
        proposal, upload_id = self.proposal('local_web')
        key = proposal['proposal_id']
        code, preview = self.request(f'/api/agent/v1/proposals/{key}/preview')
        self.assertEqual(code, 200, preview)
        self.assertEqual(self.request(f'/api/agent/v1/proposals/{key}/commit', {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}, 'POST')[0], 409)
        self.runtime.preview_tickets['synthetic-file-ticket'] = {'file_expiry':time.monotonic() + 600}
        code, reviewed = self.request(f'/api/local/agent-management/proposals/{key}/preview', management=True)
        self.assertEqual(code, 200, reviewed)
        payload = {'workspace_id':self.security.workspace_id, 'version':1, 'preview_digest':reviewed['preview']['preview_digest'], 'preview_ticket':reviewed['preview_ticket'], 'request_id':uuid.uuid4().hex}
        code, result = self.request(f'/api/local/agent-management/proposals/{key}/approve', payload, 'POST', True)
        self.assertEqual(code, 200, result)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(self.request(f'/api/local/agent-management/proposals/{key}/approve', payload, 'POST', True), (200, result))

    def test_real_stdio_formal_attachment_uses_existing_proposal_tools(self):
        for kind in ('project', 'document'):
            with self.subTest(owner_kind=kind):
                self._assert_stdio_formal_attachment(kind)

    def _assert_stdio_formal_attachment(self, kind):
        from codex_agent_acceptance import RpcProcess
        from test_mcp_stdio import INITIALIZE
        proposal, upload_id = self.proposal(kind=kind)
        owner_id = proposal['normalized_content']['owner_id']
        category = proposal['normalized_content']['category']
        rpc = RpcProcess([sys.executable, 'agent_bridge.py', '--config', self.info['config_file']], Path(__file__).resolve().parent, {**os.environ, 'PYTHONIOENCODING':'utf-8'})
        try:
            rpc.call('initialize', INITIALIZE); rpc.notify('notifications/initialized')
            self.assertEqual(len(rpc.call('tools/list')['tools']), 22)
            def tool(name, arguments):
                return rpc.call('tools/call', {'name':'workbench_' + name, 'arguments':arguments})
            self.assertEqual(tool('capabilities', {})['structuredContent']['execution_schema_versions'], [1, 2, 3, 4])
            self.assertFalse(tool('cancel_proposal', {'proposal_id':proposal['proposal_id'], 'expected_version':1})['isError'])
            target = tool('get_attachment_target', {'owner_kind':kind, 'owner_id':owner_id})
            self.assertFalse(target['isError'], target)
            request = {'request_id':uuid.uuid4().hex, 'kind':'attachment', 'operation':'create', 'target_id':owner_id, 'base_revision':target['structuredContent']['revision'],
                       'content':{'owner_kind':kind, 'owner_id':owner_id, 'upload_id':upload_id, 'display_name':'MCP[文件](1)%#.txt', 'category':category, 'insert_link':kind != 'project'}}
            prepared = tool('prepare_proposal', request)
            self.assertFalse(prepared['isError'], prepared)
            key = prepared['structuredContent']['proposal_id']
            preview = tool('preview_proposal', {'proposal_id':key})
            self.assertFalse(preview['isError'], preview)
            commit = {'proposal_id':key, 'version':1, 'preview_digest':preview['structuredContent']['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True, 'note':'合成测试确认，不代表真实模型新能力验收'}}
            result = tool('commit_proposal', commit)
            self.assertFalse(result['isError'], result)
            self.assertEqual(tool('commit_proposal', commit)['structuredContent'], result['structuredContent'])
            self.assertTrue(tool('get_proposal', {'proposal_id':key})['structuredContent']['current_item']['exists'])
            self.assertFalse(tool('get_attachment_target', {'owner_kind':kind, 'owner_id':owner_id})['structuredContent']['binary_download'])
            with self.assertRaises(RuntimeError):
                tool('get_attachment_target', {'owner_kind':kind, 'owner_id':owner_id, 'path':'C:\\synthetic'})
        finally:
            rpc.close()

    def test_long_agent_and_management_requests_allow_revoke_disable_and_switch(self):
        from workbench.agent_file_handles import LocalFileHandle
        from workbench.agent_management import client_version
        from server import Repository
        for mode, change in [('agent_attested', 'revoke'), ('local_web', 'disable'), ('local_web', 'switch')]:
            with self.subTest(mode=mode, change=change):
                case = AttachmentHTTPTests(self._testMethodName)
                case.setUp()
                try:
                    proposal, upload_id = case.proposal(mode)
                    key = proposal['proposal_id']
                    if mode == 'agent_attested':
                        _, preview = case.request(f'/api/agent/v1/proposals/{key}/preview')
                        path = f'/api/agent/v1/proposals/{key}/commit'
                        payload = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
                    else:
                        _, reviewed = case.request(f'/api/local/agent-management/proposals/{key}/preview', management=True)
                        preview = reviewed['preview']
                        path = f'/api/local/agent-management/proposals/{key}/approve'
                        payload = {'workspace_id':case.security.workspace_id, 'version':1, 'preview_digest':preview['preview_digest'], 'preview_ticket':reviewed['preview_ticket'], 'request_id':uuid.uuid4().hex}
                    entered, release = threading.Event(), threading.Event()
                    original = LocalFileHandle.chunks
                    def slow(handle, deadline):
                        if not entered.is_set():
                            entered.set()
                            if not release.wait(5):
                                raise AssertionError('test did not release native copy')
                        yield from original(handle, deadline)
                    output = []
                    handler = case.workbench.server.RequestHandlerClass
                    with patch.object(LocalFileHandle, 'chunks', slow):
                        worker = threading.Thread(target=lambda:output.append(case.request(path, payload, 'POST', mode == 'local_web')))
                        worker.start()
                        try:
                            self.assertTrue(entered.wait(3))
                            start = time.monotonic()
                            self.assertEqual(case.request('/api/projects', extra={'Authorization':''})[0], 200)
                            self.assertEqual(case.request('/api/orphan-assets', method='DELETE', extra={'Authorization':''})[0], 503)
                            if change == 'revoke':
                                body = {'workspace_id':case.security.workspace_id, 'expected_version':client_version(case.security.clients()[case.client_id]), 'request_id':uuid.uuid4().hex}
                                self.assertEqual(case.request(f'/api/local/agent-management/clients/{case.client_id}/upload-policy', body, 'DELETE', True)[0], 200)
                            elif change == 'disable':
                                status = case.runtime.status()
                                body = {'workspace_id':case.security.workspace_id, 'expected_version':status['version'], 'request_id':uuid.uuid4().hex, 'enabled':False}
                                self.assertEqual(case.request('/api/local/agent-management/runtime', body, 'PATCH', True)[0], 200)
                            else:
                                with handler.repository_switch_lock:
                                    handler.repository = Repository(case.base / 'other')
                            self.assertLess(time.monotonic() - start, 2)
                        finally:
                            release.set()
                            worker.join(10)
                    self.assertFalse(worker.is_alive())
                    self.assertGreaterEqual(output[0][0], 400, output)
                    self.assertFalse((case.repo.root / preview['content']['binary_relative']).exists())
                    self.assertNotEqual(case.repo.agent_service.uploads.load(upload_id)['state'] if case.repo.agent_service else 'disabled', 'consumed')
                finally:
                    case.workbench.server.RequestHandlerClass.repository = case.repo
                    case.tearDown()

    def test_web_and_agent_acceptance_barriers_precede_second_manifest_in_both_directions(self):
        import http.client
        from workbench.agent_file_handles import LocalFileHandle
        from workbench.agent_management import client_version
        for first in ('agent', 'web'):
            with self.subTest(first=first):
                case = AttachmentHTTPTests(self._testMethodName); case.setUp()
                connection = None
                try:
                    document = case.repo.create_document({'title':'接受屏障文档', 'body':'原正文'})
                    proposal, upload_id = case.proposal()
                    code, preview = case.request(f'/api/agent/v1/proposals/{proposal["proposal_id"]}/preview')
                    self.assertEqual(code, 200)
                    commit_path = f'/api/agent/v1/proposals/{proposal["proposal_id"]}/commit'
                    commit_body = {'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
                    code, markdown = case.request('/api/agent/v1/proposals', {'request_id':uuid.uuid4().hex, 'kind':'issue', 'operation':'create', 'content':{'title':'另一正式计划', 'project_id':case.project['id'], 'body':'正文'}}, 'POST')
                    self.assertEqual(code, 200)
                    code, markdown_preview = case.request(f'/api/agent/v1/proposals/{markdown["proposal_id"]}/preview')
                    self.assertEqual(code, 200)
                    markdown_body = {'version':1, 'preview_digest':markdown_preview['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
                    key = str(uuid.uuid4())
                    route = f'/api/documents/{document["id"]}/attachments/uploads/{key}?name=web.txt&expected_revision={document["revision"]}'
                    connection = http.client.HTTPConnection('127.0.0.1', case.workbench.server.server_address[1], timeout=5)
                    if first == 'agent':
                        connection.putrequest('POST', route); connection.putheader('Content-Length', '10'); connection.endheaders(); connection.send(b'a')
                        deadline = time.monotonic() + 3
                        while time.monotonic() < deadline and not case.repo.document_uploads.report()['items']:
                            time.sleep(0.01)
                        self.assertEqual(case.repo.document_uploads.report()['items'][0]['state'], 'receiving')
                    entered, release, output = threading.Event(), threading.Event(), []
                    original = LocalFileHandle.chunks
                    def slow(handle, deadline):
                        match = str(handle.path).endswith('blob.bin') if first == 'agent' else '.workbench-document-uploads' in str(handle.path) and str(handle.path).endswith('binary.part')
                        if match and not entered.is_set():
                            entered.set()
                            if not release.wait(8): raise AssertionError('test failed to release upload')
                        yield from original(handle, deadline)
                    def web():
                        connection.request('POST', route, body=b'web bytes')
                        response = connection.getresponse(); output.append((response.status, response.read()))
                    with patch.object(LocalFileHandle, 'chunks', slow):
                        worker = threading.Thread(target=(lambda:output.append(case.request(commit_path, commit_body, 'POST'))) if first == 'agent' else web)
                        worker.start()
                        try:
                            self.assertTrue(entered.wait(3))
                            start = time.monotonic()
                            self.assertEqual(case.request('/api/documents', extra={'Authorization':''})[0], 200)
                            # Revoking another explicit client must remain possible
                            # without changing the accepted operation's credentials.
                            other = case.security.manager().run('create', {'name':'可撤销客户端', 'scopes':['read'], 'kinds':[], 'project_ids':[], 'categories':[], 'base_url':case.workbench.base_url, 'file_access_only':True})
                            other_id = other['client_id']
                            revoke = {'workspace_id':case.security.workspace_id, 'expected_version':client_version(case.security.clients()[other_id]), 'request_id':uuid.uuid4().hex}
                            self.assertEqual(case.request(f'/api/local/agent-management/clients/{other_id}/revoke', revoke, 'POST', True)[0], 200)
                            if first == 'agent':
                                connection.send(b'b' * 9); response = connection.getresponse(); response.read()
                                self.assertIn(response.status, (409, 503))
                                self.assertEqual(case.repo.document_uploads.load(key)['state'], 'failed')
                                self.assertFalse((case.repo.document_uploads.folder(key) / 'before.md').exists())
                                self.assertEqual(len(list(case.repo.agent_service.store.operations.glob('*/manifest.json'))), 1)
                            else:
                                self.assertIn(case.request(commit_path, commit_body, 'POST')[0], (409, 503))
                                self.assertIn(case.request(f'/api/agent/v1/proposals/{markdown["proposal_id"]}/commit', markdown_body, 'POST')[0], (409, 503))
                                self.assertEqual(list(case.repo.agent_service.store.operations.glob('*/manifest.json')), [])
                            self.assertLess(time.monotonic() - start, 2)
                        finally:
                            release.set(); worker.join(12)
                    self.assertFalse(worker.is_alive())
                    self.assertEqual(output[0][0], 200 if first == 'agent' else 201, output)
                    if first == 'web':
                        self.assertEqual(case.request(commit_path, commit_body, 'POST')[0], 200)
                        self.assertEqual(case.repo.get_document(document['id'])[0]['attachments'][0]['name'], 'web.txt')
                    else:
                        self.assertEqual(case.repo.agent_service.uploads.load(upload_id)['state'], 'consumed')
                finally:
                    if connection: connection.close()
                    case.tearDown()


if __name__ == '__main__':
    unittest.main()
