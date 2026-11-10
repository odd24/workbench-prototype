"""AG-136 fresh deletion authorization and, later, proposal recovery contracts."""

import copy
import hashlib
import unittest
import uuid
import io
import os
import subprocess
import sys
import zipfile
import json
from pathlib import Path
from unittest.mock import patch

from test_agent_support import AgentFixture
from workbench.agent_delete_authorization import (DeleteGrantManagement, client_delete_grants, delete_allows,
                                                  deletion_confirmation_mode, normalize_delete_grants, validate_narrowing)
from workbench.agent_management import client_version
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError, client_kinds, read_json


def delete_grants(resource):
    return {'schema_version':1, 'grants':[{'capability':'items.delete', 'operations':['delete'],
                                         'resources':[resource], 'minimum_confirmation_mode':'local_web'}]}


class DeleteGrantTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.runtime = AgentRuntime(self.repo, base=self.base / 'credentials')
        self.repo.agent_runtime = self.runtime
        self.management = DeleteGrantManagement(self.runtime)
        self.record = self.repo.create_record({'type':'issue', 'project_id':self.project['id'], 'title':'待预览完整条目'})

    def evidence(self):
        return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for directory in (self.repo.root, self.security.config_dir)
                for p in directory.rglob('*.json')}

    def preview(self):
        fresh = self.security.clients()[self.client['client_id']]
        return self.management.preview(fresh['client_id'], {'workspace_id':self.security.workspace_id,
                                      'expected_version':client_version(fresh),
                                      'grants':delete_grants({'type':'project', 'id':self.project['id']})})

    def approve(self, preview=None):
        preview = preview or self.preview()
        payload = {key:preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')}
        payload.update(approved=True, request_id=uuid.uuid4().hex)
        result = self.management.approve(self.client['client_id'], payload)
        self.client = self.security.clients()[self.client['client_id']]
        return payload, result

    def test_full_fresh_preview_zero_write_no_implicit_read_and_original_replay(self):
        before = self.evidence()
        self.assertFalse(delete_allows(self.client, self.record))
        preview = self.preview()
        self.assertEqual(self.evidence(), before)
        self.assertEqual(preview['resources'][0]['items'][0]['id'], self.record['id'])
        payload, result = self.approve(preview)
        self.assertEqual(self.security.registry_version(), 5)
        self.assertEqual(self.client['authorization_schema_version'], 6)
        self.assertEqual(self.client['kinds'], ['issue', 'document'])
        self.assertTrue(delete_allows(self.client, self.record))
        self.assertEqual(self.client['concept_map_grants'], {'schema_version':1, 'grants':[]})
        self.assertEqual(client_kinds(self.client), ['issue', 'document'])
        self.runtime.preview_tickets.clear()
        before = self.evidence()
        self.assertEqual(self.management.approve(self.client['client_id'], payload), result)
        self.assertEqual(self.evidence(), before)
        no_read = {**self.client, 'project_ids':[]}
        self.assertFalse(delete_allows(no_read, self.record))
        self.assertFalse(delete_allows({**self.client, 'kinds':[]}, self.record))
        graph = self.repo.create_concept_map({'title':'不隐含图读取', 'project_id':self.project['id']})
        self.assertFalse(delete_allows(self.client, {**graph, 'type':'concept_map'}))
        with patch('workbench.deletion_prepared.SUPPORTED', False):
            self.assertFalse(delete_allows(self.client, self.record))
            self.assertTrue(self.service.projects(self.client, {})['items'])

    def test_confirmation_and_schema_fail_closed_and_dormant_never_activates(self):
        self.assertEqual(deletion_confirmation_mode(), 'local_web')
        self.assertEqual(deletion_confirmation_mode('local_web'), 'local_web')
        for mode in ('agent_attested', 'unknown', False):
            with self.assertRaises(AgentError):
                deletion_confirmation_mode(mode)
        self.assertEqual(client_delete_grants(self.client), {'schema_version':1, 'grants':[]})
        with self.assertRaises(AgentError):
            client_delete_grants({**self.client, 'delete_grants':delete_grants({'type':'project', 'id':self.project['id']})})
        with self.assertRaises(AgentError):
            client_delete_grants({**self.client, 'authorization_schema_version':6})
        for change in ({'minimum_confirmation_mode':'agent_attested'}, {'capability':'projects.delete'}, {'operations':['read']}):
            value = delete_grants({'type':'project', 'id':self.project['id']})
            value['grants'][0].update(change)
            with self.assertRaises(ValueError):
                normalize_delete_grants(value)
        with self.assertRaises(ValueError):
            normalize_delete_grants(delete_grants({'type':'item', 'kind':'idea', 'id':'IDEA-0001'}))

    def test_stale_ticket_runtime_client_resource_and_unknown_scope_do_not_write(self):
        for cause in ('session', 'runtime', 'ticket', 'client', 'resource'):
            with self.subTest(cause=cause):
                preview = self.preview()
                payload = {key:preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')}
                payload.update(approved=True, request_id=uuid.uuid4().hex)
                ticket = self.runtime.preview_tickets[preview['preview_id']]
                if cause == 'session': ticket['session'] = 'changed'
                elif cause == 'runtime': ticket['runtime_version'] = 'changed'
                elif cause == 'ticket': ticket['expires'] = 0
                elif cause == 'client': self.security.manager().run('rotate', {}, self.client['client_id'], client_version(self.security.clients()[self.client['client_id']]))
                else: self.repo.create_document({'title':'集合新增也需重预览'})
                before = self.evidence()
                with self.assertRaises(AgentError):
                    self.management.approve(self.client['client_id'], payload)
                self.assertEqual(self.evidence(), before)

    def test_edit_rotate_graph_change_and_revoke_preserve_all_format_floors(self):
        self.approve()
        from workbench.agent_concept_authorization import GraphGrantManagement
        from test_agent_concept_maps import graph_grants
        graphs = GraphGrantManagement(self.runtime)
        preview = graphs.preview(self.client['client_id'], {'workspace_id':self.security.workspace_id, 'expected_version':client_version(self.client),
                                 'grants':graph_grants({'type':'project', 'id':self.project['id']})})
        graphs.approve(self.client['client_id'], {key:preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')} | {'approved':True, 'request_id':'graph-after-delete'})
        current = self.security.clients()[self.client['client_id']]
        original_delete, original_graph = copy.deepcopy(current['delete_grants']), copy.deepcopy(current['concept_map_grants'])
        manager = self.security.manager()
        for action, params in (('edit', {key:current[key] for key in ('name', 'scopes', 'project_ids', 'categories', 'kinds')}), ('rotate', {})):
            current = self.security.clients()[current['client_id']]
            manager.run(action, params, current['client_id'], client_version(current))
            current = self.security.clients()[current['client_id']]
            self.assertEqual(current['authorization_schema_version'], 6)
            self.assertEqual(current['delete_grants'], original_delete)
            self.assertEqual(current['concept_map_grants'], original_graph)
        self.management.revoke(current['client_id'], {'workspace_id':self.security.workspace_id, 'expected_version':client_version(current), 'request_id':'delete-revoke'})
        current = self.security.clients()[current['client_id']]
        self.assertEqual(current['delete_grants']['grants'], [])
        self.assertEqual(current['concept_map_grants'], original_graph)
        self.assertEqual(self.security.registry_version(), 5)
        self.assertTrue(all(read_json(path)['schema_version'] == 6 for path in manager.directory.glob('*.json') if read_json(path).get('registry_schema') == 5))
        self.assertFalse(list((self.security.config_dir / 'management-snapshots').glob('*.json')))

    def test_narrow_cannot_add_resources_or_types_and_clearing_keeps_schema(self):
        self.approve()
        before = self.client
        with self.assertRaises(ValueError):
            validate_narrowing(before['delete_grants'], delete_grants({'type':'project', 'id':'different'}))
        manager = self.security.manager()
        manager.run('delete_grants_narrow', {'grants':{'schema_version':1, 'grants':[]}}, before['client_id'], client_version(before), 'narrow-empty')
        current = self.security.clients()[before['client_id']]
        self.assertEqual(current['authorization_schema_version'], 6)
        self.assertEqual(current['kinds'], before['kinds'])
        self.assertFalse(delete_allows(current, self.record))

    def test_real_management_exits_old_version_fences_and_new_recovery(self):
        from workbench.security import validate_archive_member
        legacy = self.base / 'legacy-code'
        archive = subprocess.check_output(['git', 'archive', '--format=zip', 'fe32140'], cwd=Path(__file__).parent)
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            for name in source.namelist():
                validate_archive_member(name.rstrip('/'))
            source.extractall(legacy)
        script = '''import os,sys
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_management import client_version
from workbench.agent_delete_authorization import grant_dependencies
r=Repository(Path(sys.argv[1]));s=AgentSecurity(r.root,Path(sys.argv[2]));c=s.clients()[sys.argv[3]]
g={'schema_version':1,'grants':[{'capability':'items.delete','operations':['delete'],'resources':[{'type':'project','id':sys.argv[4]}],'minimum_confirmation_mode':'local_web'}]}
m=s.manager();m.checkpoint=lambda stage:os._exit(77) if stage==sys.argv[5] else None
m.run('delete_grants',{'grants':g,'approval_digest':'a'*64,'resource_dependencies':grant_dependencies(r,g)},c['client_id'],client_version(c),'real-delete-'+sys.argv[5])
'''
        old_probe = '''import sys
from pathlib import Path
from workbench.agent_security import AgentSecurity,AgentError
try:
 s=AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2]));s.manager().recover()
except AgentError as error:
 print(error.code)
else:
 raise AssertionError('Old management accepted new deletion evidence')
'''
        for stage in ('private_snapshot', 'prepared', 'format_fence', 'config', 'registry', 'terminal_log', 'completed'):
            with self.subTest(stage=stage):
                fixture = AgentFixture()
                fixture.setUp()
                try:
                    args = [str(fixture.repo.root), str(fixture.base / 'credentials'), fixture.client['client_id'], fixture.project['id'], stage]
                    crash = subprocess.run([sys.executable, '-c', script, *args], cwd=Path(__file__).parent, capture_output=True, timeout=30)
                    self.assertEqual(crash.returncode, 77, crash.stderr)
                    def evidence():
                        return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in (fixture.repo.root, fixture.security.config_dir) for p in root.rglob('*.json')}
                    before = evidence()
                    old = subprocess.run([sys.executable, '-c', old_probe, *args[:2]], cwd=legacy, capture_output=True, timeout=20,
                                         env={**os.environ, 'PYTHONPATH':str(legacy)})
                    self.assertEqual(old.returncode, 0, old.stderr)
                    self.assertEqual(evidence(), before)
                    fixture.security.manager().recover()
                    current = fixture.security.clients()[fixture.client['client_id']]
                    self.assertEqual(fixture.security.registry_version(), 5)
                    self.assertEqual(bool(client_delete_grants(current)['grants']), stage != 'private_snapshot')
                    self.assertFalse(list((fixture.security.config_dir / 'management-snapshots').glob('*.json')))
                finally:
                    fixture.tearDown()

    def test_file_upload_and_attachment_families_preserve_delete_grants(self):
        from workbench.agent_files import FileManagement
        from workbench.agent_upload_policy import UploadPolicyManagement
        self.approve()
        key = self.client['client_id']
        saved = copy.deepcopy(self.client['delete_grants'])
        files = FileManagement(self.runtime)
        source = self.base / 'synthetic-source.txt'
        source.write_text('本轮合成原文', encoding='utf-8')
        preview = files.preview(key, {'workspace_id':self.security.workspace_id, 'expected_version':client_version(self.client),
                                      'path':str(source), 'purposes':['text_read'], 'encoding':'auto', 'max_bytes':1048576, 'duration_seconds':3600})
        payload = {name:preview[name] for name in ('workspace_id', 'preview_id', 'preview_digest', 'expected_version')}
        payload.update(request_id=uuid.uuid4().hex, approved=True)
        record = files.approved_record(key, payload)
        files.commit(key, payload, record)
        current = self.security.clients()[key]
        self.assertEqual(current['authorization_schema_version'], 6)
        self.assertEqual(current['delete_grants'], saved)
        self.security.manager().run('file_grant_revoke', {'file_id':record['file_id']}, key, client_version(current), 'delete-then-file-revoke')
        policies = UploadPolicyManagement(self.runtime)
        for attachment in (False, True):
            current = self.security.clients()[key]
            values = {'workspace_id':self.security.workspace_id, 'expected_version':client_version(current), 'owner_kind':'project', 'owner_id':self.project['id'], 'stream':True, 'files':[], 'max_bytes':1048576, 'duration_seconds':3600}
            if attachment:
                values.update(attachment_write=True, minimum_confirmation_mode='local_web')
            preview = policies.preview(key, values)
            payload = {name:preview[name] for name in ('workspace_id', 'preview_id', 'preview_digest', 'expected_version')}
            payload.update(request_id=uuid.uuid4().hex, approved=True)
            policies.approve(key, payload)
            current = self.security.clients()[key]
            self.assertEqual(current['authorization_schema_version'], 6)
            self.assertEqual(current['delete_grants'], saved)
        self.security.manager().run('upload_policy_revoke', {}, key, client_version(current), 'delete-then-upload-revoke')
        current = self.security.clients()[key]
        self.assertEqual(current['delete_grants'], saved)
        self.assertEqual(current['authorization_schema_version'], 6)

    def test_category_failure_keeps_delete_scope_narrow_and_never_grants_uncategorized(self):
        self.repo.create_document({'title':'分类内文档', 'category':'允许'})
        grants = delete_grants({'type':'document_category', 'name':'允许'})
        preview = self.management.preview(self.client['client_id'], {'workspace_id':self.security.workspace_id, 'expected_version':client_version(self.client), 'grants':grants})
        self.approve(preview)
        def interrupted(point):
            if point == 'category_business_applying':
                raise OSError('synthetic category failure')
        with patch.object(self.repo.agent_proposals, 'checkpoint', side_effect=interrupted), self.assertRaises(AgentError):
            self.repo.rename_document_category('允许', '新名称')
        current = self.security.clients()[self.client['client_id']]
        self.assertEqual(current['authorization_schema_version'], 6)
        self.assertEqual(current['delete_grants']['grants'], [])
        self.assertFalse(delete_allows(current, {'id':'DOC-9999', 'type':'document', 'category':'未分类'}))


class DeleteProposalTests(AgentFixture, unittest.TestCase):
    evidence = DeleteGrantTests.evidence
    preview = DeleteGrantTests.preview
    approve = DeleteGrantTests.approve

    def setUp(self):
        super().setUp()
        self.runtime = AgentRuntime(self.repo, base=self.base / 'credentials')
        self.repo.agent_runtime = self.runtime
        self.repo.agent_service = self.service
        self.management = DeleteGrantManagement(self.runtime)
        manager = self.security.manager()
        manager.run('edit', {**{key:self.client[key] for key in ('name', 'scopes', 'project_ids', 'categories')},
                            'kinds':['issue', 'todo', 'info', 'document']}, self.client['client_id'], client_version(self.client))
        self.client = self.security.clients()[self.client['client_id']]
        from workbench.agent_concept_authorization import GraphGrantManagement
        from test_agent_concept_maps import graph_grants
        graph_management = GraphGrantManagement(self.runtime)
        graph_preview = graph_management.preview(self.client['client_id'], {'workspace_id':self.security.workspace_id,
                                    'expected_version':client_version(self.client), 'grants':graph_grants({'type':'project', 'id':self.project['id']})})
        graph_management.approve(self.client['client_id'], {key:graph_preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')} | {'approved':True, 'request_id':'graph-read-before-delete'})
        self.client = self.security.clients()[self.client['client_id']]
        grants = delete_grants({'type':'project', 'id':self.project['id']})
        grants['grants'][0]['resources'].append({'type':'document_category', 'name':'允许'})
        preview = self.management.preview(self.client['client_id'], {'workspace_id':self.security.workspace_id, 'expected_version':client_version(self.client), 'grants':grants})
        self.approve(preview)
        from workbench.agent_proposal_management import ProposalManagement
        self.proposal_management = ProposalManagement(self.runtime)

    def create_target(self, kind):
        if kind == 'concept_map':
            item = self.repo.create_concept_map({'title':'待删除完整图', 'project_id':self.project['id']})
            path = self.repo.get_concept_map(item['id'])[1]
        elif kind == 'document':
            item = self.repo.create_document({'title':'待删除知识', 'body':'完整正文\n第二行', 'category':'允许'})
            path = self.repo.get_document(item['id'])[1]
        else:
            item = self.repo.create_record({'type':kind, 'project_id':self.project['id'], 'title':'待删除记录', 'body':'完整原文',
                                           **({'info_fields':[{'name':'命令', 'value':'echo one\n  echo two'}]} if kind == 'info' else {})})
            path = self.repo.get_record(item['id'])[1]
        return item, path

    def deletion_preview(self, kind, item, path):
        proposal = self.service.prepare_proposal(self.client, {'request_id':uuid.uuid4().hex, 'operation':'delete', 'kind':kind,
                                        'target_id':item['id'], 'base_revision':hashlib.sha256(path.read_bytes()).hexdigest(), 'source_note':'仅本轮临时删除验证'})
        return self.service.preview_proposal(self.client, proposal['proposal_id'])

    def local_payload(self, preview):
        review = self.proposal_management.preview(preview['proposal_id'])
        self.assertTrue(review['authorization_available'])
        return {'workspace_id':self.security.workspace_id, 'version':preview['version'], 'preview_digest':preview['preview_digest'],
                'preview_ticket':review['preview_ticket'], 'request_id':uuid.uuid4().hex}

    def test_five_types_full_preview_local_approval_trash_restore_and_original_replay(self):
        for kind in ('issue', 'todo', 'info', 'document', 'concept_map'):
            with self.subTest(kind=kind):
                item, path = self.create_target(kind)
                raw = path.read_bytes()
                preview = self.deletion_preview(kind, item, path)
                self.assertEqual(preview['confirmation_mode'], 'local_web')
                self.assertEqual(preview['content']['target']['raw_source'].encode('utf-8'), raw)
                self.assertTrue(path.exists())
                self.assertEqual(self.repo.list_trash(), [])

                self.assertNotIn('delete_binding', self.service.get_proposal(self.client, preview['proposal_id']))
                with self.assertRaises(AgentError):
                    self.service.commit_proposal(self.client, preview['proposal_id'], self.confirmation(preview))
                payload = self.local_payload(preview)
                result = self.proposal_management.approve(preview['proposal_id'], payload)
                receipt = result['receipt']
                self.assertTrue(receipt['deleted'])
                self.assertEqual(receipt['trash_token'], preview['trash_token'])
                self.assertFalse(path.exists())
                self.assertEqual((self.repo.trash_dir / receipt['trash_token']).read_bytes(), raw)
                self.assertEqual(self.repo._trash_index()[receipt['trash_token']]['agent_operation_id'], f"{preview['proposal_id']}-1")
                restored = self.repo.restore_trash(receipt['trash_token'])
                self.assertEqual(Path(restored['restored_path']).read_bytes(), raw)
                self.assertEqual(self.service.commit_proposal(self.client, preview['proposal_id'], self.confirmation(preview)), receipt)
                self.assertTrue(Path(restored['restored_path']).exists())
                self.assertEqual(self.repo.list_trash(), [])

    def test_hidden_active_matches_refuse_generically_and_nonmatches_never_leak(self):
        item, path = self.create_target('document')
        hidden = self.repo.create_document({'title':'私人标题不得泄露', 'category':'隐藏', 'body':'未引用的私人正文'})
        client = {**self.client, 'categories':['允许']}
        request = {'request_id':uuid.uuid4().hex, 'kind':'document', 'operation':'delete', 'target_id':item['id'], 'base_revision':hashlib.sha256(path.read_bytes()).hexdigest()}
        proposal = self.service.prepare_proposal(client, request)
        preview = self.service.preview_proposal(client, proposal['proposal_id'])
        self.assertNotIn(hidden['id'], str(preview))
        self.assertNotIn('私人标题', str(preview))
        self.assertNotIn('relative_path', str(preview))
        self.repo.update_document(hidden['id'], {'body':f"[[{item['id']}]]"})
        with self.assertRaises(AgentError) as error:
            self.service.prepare_proposal(client, {**request, 'request_id':uuid.uuid4().hex})
        self.assertEqual(error.exception.code, 'impact_unavailable')
        self.assertNotIn(hidden['id'], str(error.exception.payload()))
        self.assertNotIn('私人标题', str(error.exception.payload()))
        self.repo.update_document(hidden['id'], {'body':'不引用'})
        self.repo.update_project(self.project['id'], {'description':f"[[{item['id']}]]"})
        with self.assertRaises(AgentError) as error:
            self.service.prepare_proposal(self.client, {**request, 'request_id':uuid.uuid4().hex})
        self.assertEqual(error.exception.code, 'impact_unavailable')

    def test_source_replacement_or_set_change_invalidates_approval_and_input_cannot_supply_held_source(self):
        item, path = self.create_target('issue')
        preview = self.deletion_preview('issue', item, path)
        payload = self.local_payload(preview)
        self.repo.create_document({'title':'无关新来源也应冲突'})
        with self.assertRaises(AgentError):
            self.proposal_management.approve(preview['proposal_id'], payload)
        self.assertTrue(path.exists())
        replacement_preview = self.deletion_preview('issue', item, path)
        replacement_payload = self.local_payload(replacement_preview)
        raw = path.read_bytes()
        sibling = path.with_suffix('.replacement')
        sibling.write_bytes(raw)
        sibling.replace(path)
        with self.assertRaises(AgentError):
            self.proposal_management.approve(replacement_preview['proposal_id'], replacement_payload)
        self.assertEqual(path.read_bytes(), raw)
        for extra in ({'content':{}}, {'held_source':{}}, {'body':'replacement'}, {'path':'elsewhere'}, {'confirmation_mode':'agent_attested'}):
            with self.assertRaises(AgentError):
                self.service.prepare_proposal(self.client, {'request_id':uuid.uuid4().hex, 'kind':'issue', 'operation':'delete', 'target_id':item['id'], 'base_revision':hashlib.sha256(path.read_bytes()).hexdigest(), **extra})

    def test_unknown_index_before_preview_or_changed_index_before_move_never_deletes(self):
        item, path = self.create_target('issue')
        index_path = self.repo.trash_dir / 'index.json'
        original = index_path.read_bytes()
        for raw in (b'[]', b'{"x":{},"x":{}}', b'{"x":{"delete_schema_version":99}}'):
            index_path.write_bytes(raw)
            before = self.evidence()
            with self.assertRaises(AgentError):
                self.deletion_preview('issue', item, path)
            self.assertTrue(path.exists())
            self.assertEqual(self.evidence(), before)
        index_path.write_bytes(original)
        preview = self.deletion_preview('issue', item, path)
        payload = self.local_payload(preview)
        index_path.write_bytes(original + b'\n')
        with self.assertRaises(AgentError):
            self.proposal_management.approve(preview['proposal_id'], payload)
        self.assertTrue(path.exists())
        self.assertEqual(self.repo.list_trash(), [])

    def test_actual_utf8_preview_budget_accepts_boundary_and_refuses_one_more_byte(self):
        from workbench.agent_delete_service import checked_preview
        payload = {'完整原文':'中', 'body':''}
        overhead = len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8'))
        payload['body'] = 'x' * (2097152 - overhead)
        self.assertEqual(len(json.dumps(payload, ensure_ascii=False).encode('utf-8')), 2097152)
        self.assertEqual(checked_preview(payload), payload)
        payload['body'] += 'x'
        with self.assertRaises(AgentError) as error:
            checked_preview(payload)
        self.assertEqual(error.exception.status, 413)
        self.assertEqual(len(payload['body']), 2097153 - overhead)



if __name__ == '__main__':
    unittest.main()
