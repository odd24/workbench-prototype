"""Independent project creation grants and local approval integration."""

import unittest
import uuid
import subprocess
import sys
import hashlib
import io
import zipfile
from pathlib import Path

from test_agent_support import AgentFixture
from workbench.agent_file_handles import SUPPORTED
from workbench.agent_management import client_version
from workbench.agent_project_authorization import ProjectCreateGrantManagement, can_create_project
from workbench.agent_proposal_management import ProposalManagement
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError


@unittest.skipUnless(SUPPORTED, 'native project publication requires Windows')
class ProjectCreationTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.repo.agent_service = self.service
        self.runtime = self.repo.agent_runtime = AgentRuntime(self.repo, base=self.base / 'credentials')
        self.grants = ProjectCreateGrantManagement(self.runtime)
        self.manager = self.security.manager()
        self.key = self.client['client_id']
        self.manager.run('edit', {'name':'验收', 'scopes':['read','propose','commit'],
                                  'project_ids':['future-project'], 'categories':['允许']},
                         self.key, client_version(self.client))
        self.client = self.security.clients()[self.key]

    def approve_grant(self):
        preview = self.grants.preview(self.key, {'workspace_id':self.security.workspace_id, 'expected_version':client_version(self.client)})
        approval = {name:preview[name] for name in ('workspace_id','expected_version','preview_id','preview_digest')}
        approval.update(approved=True, request_id=uuid.uuid4().hex)
        result = self.grants.approve(self.key, approval)
        self.runtime.preview_tickets.clear()
        self.assertEqual(self.grants.approve(self.key, approval), result)
        self.client = self.security.clients()[self.key]

    def spec_project(self, **extras):
        return {'request_id':uuid.uuid4().hex, 'kind':'project', 'operation':'create',
                'content':{'name':'future-project','description':'完整项目说明\n第二行'}, **extras}

    def local_review(self, proposal):
        management = ProposalManagement(self.runtime)
        preview = management.preview(proposal['proposal_id'])
        payload = {'workspace_id':self.security.workspace_id, 'version':preview['version'],
                   'preview_digest':preview['preview']['preview_digest'], 'preview_ticket':preview['preview_ticket'],
                   'request_id':uuid.uuid4().hex}
        return management, preview, payload

    def test_local_creation_no_hidden_order_or_access_and_original_receipt(self):
        with self.assertRaises(AgentError):
            self.service.prepare_proposal(self.client, self.spec_project())
        self.approve_grant()
        self.assertEqual(self.security.registry_version(), 6)
        self.assertEqual(self.client['authorization_schema_version'], 7)
        self.assertEqual(self.client['project_ids'], ['future-project'])
        self.assertTrue(can_create_project(self.client))
        self.assertEqual(self.service.projects(self.client, {})['items'], [])
        with self.assertRaises(AgentError):
            self.service.prepare_proposal(self.client, self.spec_project(confirmation_mode='agent_attested'))
        proposal = self.service.prepare_proposal(self.client, self.spec_project())
        self.assertEqual(proposal['target_id'], 'future-project-2')
        self.assertNotIn('project_sort_details', proposal)
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        self.assertNotIn(self.project['id'], str(preview))
        path = self.repo.projects_dir / proposal['target_id']
        self.assertFalse(path.exists())
        with self.assertRaises(AgentError):
            self.commit(preview)
        management, local, payload = self.local_review(proposal)
        self.assertEqual(local['local_project_plan']['visible_after'], [self.project['id'], proposal['target_id']])
        result = management.approve(proposal['proposal_id'], payload)
        self.assertEqual(result['state'], 'completed')
        receipt = result['receipt']
        self.assertEqual(receipt['item_id'], proposal['target_id'])
        self.assertEqual(self.service.projects(self.client, {})['items'], [])
        self.assertEqual(management.action(payload['request_id'])['receipt'], receipt)
        self.reload()
        self.assertEqual(self.repo.project(proposal['target_id'])['description'], '完整项目说明\n第二行')
        self.repo.update_project(proposal['target_id'], {'description':'稍后编辑'})
        self.assertEqual(self.commit(preview), receipt)
        self.assertEqual(self.repo.project(proposal['target_id'])['description'], '稍后编辑')

    def test_reservation_and_revocation_preserve_old_format_fields(self):
        self.approve_grant()
        proposal = self.service.prepare_proposal(self.client, self.spec_project(content={'name':'reserved'}))
        self.assertEqual(proposal['target_id'], 'reserved')
        self.assertEqual(self.repo.create_project({'name':'reserved'})['id'], 'reserved-2')
        revised = self.service.revise_proposal(self.client, proposal['proposal_id'], {'expected_version':1, 'content':{'name':'重命名'}})
        self.assertEqual(revised['target_id'], 'reserved')
        self.service.cancel_proposal(self.client, proposal['proposal_id'], {'expected_version':2})
        self.assertEqual(self.repo.create_project({'name':'reserved'})['id'], 'reserved-3')
        self.grants.revoke(self.key, {'workspace_id':self.security.workspace_id, 'expected_version':client_version(self.client),
                                     'request_id':uuid.uuid4().hex})
        client = self.security.clients()[self.key]
        self.assertFalse(can_create_project(client))
        self.assertEqual(client['delete_grants'], self.client['delete_grants'])
        self.assertEqual(client['concept_map_grants'], self.client['concept_map_grants'])
        self.assertEqual(self.security.registry_version(), 6)

    def test_optional_access_is_independent_and_refuses_a_replacement_project(self):
        from workbench.agent_project_access import ProjectAccessManagement
        self.approve_grant()
        proposal = self.service.prepare_proposal(self.client, self.spec_project())
        management, _, payload = self.local_review(proposal)
        receipt = management.approve(proposal['proposal_id'], payload)['receipt']
        access = ProjectAccessManagement(self.runtime)
        preview = access.preview(proposal['proposal_id'])
        self.assertEqual(preview['before']['project_ids'], ['future-project'])
        self.assertEqual(preview['after']['project_ids'], ['future-project', proposal['target_id']])
        self.assertEqual(preview['before']['scopes'], preview['after']['scopes'])
        self.assertEqual(self.service.projects(self.client,{})['items'], [])
        permission = {name:preview[name] for name in ('workspace_id','expected_version','preview_id','preview_digest')}
        permission.update(request_id=uuid.uuid4().hex, approved=True)
        root = self.repo.projects_dir / proposal['target_id']
        parked = self.repo.root / 'parked-original'
        original = (root / 'README.md').read_bytes()
        root.rename(parked)
        root.mkdir()
        (root / 'README.md').write_bytes(original)
        with self.assertRaises(AgentError):
            access.approve(proposal['proposal_id'], permission)
        self.assertEqual(self.security.clients()[self.key]['project_ids'], ['future-project'])
        self.assertEqual(management.action(payload['request_id'])['receipt'], receipt)
        root.rename(self.repo.root / 'parked-imitation')
        parked.rename(root)
        result = access.approve(proposal['proposal_id'], permission)
        self.runtime.preview_tickets.clear()
        self.assertEqual(access.approve(proposal['proposal_id'], permission), result)
        self.assertNotEqual(result['operation_id'], receipt['approval']['operation_id'])
        client = self.security.clients()[self.key]
        self.assertEqual(client['project_ids'], ['future-project', proposal['target_id']])
        self.assertEqual([p['id'] for p in self.service.projects(client,{})['items']], [proposal['target_id']])
        self.assertTrue(access.preview(proposal['proposal_id'])['already_covered'])

    def test_real_exit_project_boundaries(self):
        from server import Repository
        from workbench.agent_service import AgentService
        script = '''
import os, sys, uuid
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService
from workbench.agent_runtime import AgentRuntime
from workbench.agent_proposal_management import ProposalManagement
root, base, proposal_id, point = sys.argv[1:]
repo=Repository(Path(root)); security=AgentSecurity(repo.root,Path(base))
repo.agent_service=AgentService(repo,security)
repo.agent_runtime=AgentRuntime(repo,base=Path(base))
m=ProposalManagement(repo.agent_runtime); p=m.preview(proposal_id)
repo.agent_service.store.checkpoint=lambda stage:os._exit(73) if stage==point else None
m.approve(proposal_id,{'workspace_id':security.workspace_id,'version':1,'preview_digest':p['preview']['preview_digest'],
                       'preview_ticket':p['preview_ticket'],'request_id':'exit-'+point})
'''
        stages = ('snapshots','manifest','committing','project_stage_applying','project_staged','project_stage_logged',
                  'project_publish_applying','project_published','project_sort_applying','project_sort_written',
                  'project_sort_logged','receipt','proposal')
        self.approve_grant()
        for index, stage in enumerate(stages):
            with self.subTest(stage=stage):
                proposal = self.service.prepare_proposal(self.client, self.spec_project(content={'name':f'exit-{index}'}))
                target = self.repo.projects_dir / proposal['target_id']
                child = subprocess.run([sys.executable,'-c',script,str(self.repo.root),str(self.base / 'credentials'),
                                        proposal['proposal_id'],stage], cwd=Path(__file__).resolve().parent,
                                       capture_output=True,timeout=20)
                self.assertEqual(child.returncode, 73, child.stderr.decode(errors='replace'))
                self.repo = Repository(self.repo.root)
                self.service = self.repo.agent_service = AgentService(self.repo,self.security)
                self.store = self.service.store
                self.store.recover()
                self.runtime = self.repo.agent_runtime = AgentRuntime(self.repo,base=self.base / 'credentials')
                report = ProposalManagement(self.runtime).action('exit-'+stage)
                if stage in ('project_stage_applying','project_staged','project_publish_applying'):
                    self.assertTrue(self.store.blocked)
                    self.assertFalse(target.exists())
                    with self.assertRaises(AgentError):
                        self.repo.create_project({'name':'不得绕过'})
                    self.store.abandon(proposal['proposal_id'] + '-1')
                    self.assertEqual(ProposalManagement(self.runtime).action('exit-'+stage)['state'],'abandoned')
                    self.assertFalse(target.exists())
                elif stage == 'snapshots':
                    self.assertEqual(report['state'],'not_applied')
                    self.assertFalse(target.exists())
                else:
                    self.assertEqual(report['state'],'completed')
                    self.assertEqual(report['receipt']['item_id'],proposal['target_id'])
                    self.assertEqual(self.repo.project(proposal['target_id'])['name'],f'exit-{index}')
                    self.assertEqual(self.repo.project_sort()['order'][-1],proposal['target_id'])

    def test_published_project_preserves_foreign_sort_and_reports_separate_evidence(self):
        self.approve_grant()
        proposal = self.service.prepare_proposal(self.client, self.spec_project())
        management, _, payload = self.local_review(proposal)
        sort_path = self.repo.config_dir / 'project-sort.json'
        foreign = b'{"mode":"name","order":[]}'
        target = self.repo.projects_dir / proposal['target_id'] / 'README.md'
        def alter(stage):
            if stage == 'project_published':
                sort_path.write_bytes(foreign)
        self.store.checkpoint = alter
        with self.assertRaises(AgentError):
            management.approve(proposal['proposal_id'], payload)
        original = target.read_bytes()
        self.reload()
        evidence = self.store.recovery_report()['details'][0]
        self.assertEqual(evidence['project_state'], 'published_original')
        self.assertEqual(evidence['sorting_state'], 'foreign')
        self.assertEqual(sort_path.read_bytes(), foreign)
        self.store.abandon(proposal['proposal_id'] + '-1')
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(sort_path.read_bytes(), foreign)
        self.assertNotEqual(self.repo.create_project({'name':'future-project'})['id'], proposal['target_id'])

    def test_old_release_refuses_new_private_intent_and_project_proposal_without_writes(self):
        archive = subprocess.check_output(['git','archive','--format=zip','986d6fe'],cwd=Path(__file__).resolve().parent)
        old = self.base / 'old-release'
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            source.extractall(old)
        def evidence():
            return {str(path):hashlib.sha256(path.read_bytes()).hexdigest()
                    for root in (self.repo.root,self.security.config_dir) for path in root.rglob('*.json')}
        def old_refuses(code):
            before = evidence()
            result = subprocess.run([sys.executable,'-c',code,str(self.repo.root),str(self.base / 'credentials')],
                                    cwd=old,capture_output=True,timeout=20)
            self.assertEqual(result.returncode, 73, result.stderr.decode(errors='replace'))
            self.assertEqual(evidence(), before)
        def stop(stage):
            if stage == 'private_snapshot':
                raise OSError('synthetic first private snapshot interruption')
        self.manager.checkpoint = stop
        with self.assertRaises(OSError):
            self.manager.run('project_create_grant',{'approval_digest':'a'*64},self.key,client_version(self.client),'new-private')
        old_refuses('''import sys
from pathlib import Path
from workbench.agent_security import AgentSecurity, AgentError
try: AgentSecurity(Path(sys.argv[1]),Path(sys.argv[2])).manager().report()
except AgentError: sys.exit(73)
''')

        self.manager.checkpoint = lambda _:None
        self.manager.report()
        self.assertFalse(can_create_project(self.security.clients()[self.key]))
        self.approve_grant()
        self.service.prepare_proposal(self.client,self.spec_project())
        old_refuses('''import sys
from pathlib import Path
from types import SimpleNamespace
from workbench.agent_proposals import ProposalStore
from workbench.agent_security import AgentError
try: ProposalStore(SimpleNamespace(root=Path(sys.argv[1]))).preflight()
except AgentError: sys.exit(73)
''')

    def test_scope_cas_revoke_and_credential_family_floor(self):
        from workbench.agent_project_access import ProjectAccessManagement
        from workbench.agent_files import FileManagement
        from workbench.agent_upload_policy import UploadPolicyManagement
        from workbench.agent_concept_authorization import GraphGrantManagement
        from workbench.agent_delete_authorization import DeleteGrantManagement
        from test_agent_concept_maps import graph_grants
        from test_agent_deletions import delete_grants
        from workbench.agent_security import read_json
        self.approve_grant()
        proposal = self.service.prepare_proposal(self.client, self.spec_project())
        management, _, payload = self.local_review(proposal)
        receipt = management.approve(proposal['proposal_id'],payload)['receipt']
        access = ProjectAccessManagement(self.runtime)
        def approval(preview):
            return {**{k:preview[k] for k in ('workspace_id','expected_version','preview_id','preview_digest')},
                    'request_id':uuid.uuid4().hex, 'approved':True}
        stale = approval(access.preview(proposal['proposal_id']))
        self.manager.run('edit', {'name':'版本变化','scopes':self.client['scopes'],'project_ids':self.client['project_ids'],'categories':['允许']},
                         self.key,client_version(self.client))
        with self.assertRaises(AgentError):
            access.approve(proposal['proposal_id'],stale)
        self.assertEqual(management.action(payload['request_id'])['receipt'],receipt)
        current = self.security.clients()[self.key]
        self.manager.run('edit', {'name':'版本变化','scopes':current['scopes'],'project_ids':['*'],'categories':['允许']},
                         self.key,client_version(current))
        self.assertTrue(access.preview(proposal['proposal_id'])['already_covered'])
        files = FileManagement(self.runtime)
        source = self.base / 'source.txt'; source.write_text('synthetic',encoding='utf-8')
        current = self.security.clients()[self.key]
        preview = files.preview(self.key, {'workspace_id':self.security.workspace_id,'expected_version':client_version(current),
                             'path':str(source),'purposes':['text_read'],'encoding':'auto','max_bytes':1024,'duration_seconds':3600})
        pay = approval(preview); record = files.approved_record(self.key,pay)
        files.commit(self.key,pay,record)
        current = self.security.clients()[self.key]
        self.manager.run('file_grant_revoke',{'file_id':record['file_id']},self.key,client_version(current))
        for attachment in (False,True):
            policies = UploadPolicyManagement(self.runtime)
            current = self.security.clients()[self.key]
            fields = {'workspace_id':self.security.workspace_id,'expected_version':client_version(current),'owner_kind':'project',
                      'owner_id':self.project['id'],'stream':True,'files':[],'max_bytes':1048576,'duration_seconds':3600}
            if attachment:
                fields.update(attachment_write=True,minimum_confirmation_mode='local_web')
            policies.approve(self.key,approval(policies.preview(self.key,fields)))
        for grants, api in ((graph_grants({'type':'project','id':self.project['id']}),GraphGrantManagement(self.runtime)),
                            (delete_grants({'type':'project','id':self.project['id']}),DeleteGrantManagement(self.runtime))):
            current = self.security.clients()[self.key]
            review = api.preview(self.key,{'workspace_id':self.security.workspace_id,'expected_version':client_version(current),'grants':grants})
            api.approve(self.key,approval(review))
        current = self.security.clients()[self.key]
        self.assertTrue(can_create_project(current))
        self.assertEqual(current['authorization_schema_version'],7)
        self.assertEqual(self.security.registry_version(),6)
        self.assertTrue(current['concept_map_grants']['grants'])
        self.assertTrue(current['delete_grants']['grants'])
        self.manager.run('rotate',{},self.key,client_version(current))
        current = self.security.clients()[self.key]
        self.assertTrue(can_create_project(current))
        self.manager.run('revoke',{},self.key,client_version(current))
        with self.assertRaises(AgentError):
            access.preview(proposal['proposal_id'])
        self.assertEqual(management.action(payload['request_id'])['receipt'],receipt)
        newest = [read_json(path) for path in self.manager.directory.glob('*.json') if read_json(path)['schema_version']==7]
        self.assertTrue({'project_create','credential','file','upload_policy','attachment_policy','concept_map','delete'} <= {entry['operation_family'] for entry in newest})
        self.assertTrue(all(entry['registry_schema']==6 for entry in newest))

    def test_access_recovery_does_not_grant_after_project_changes_and_abandon_keeps_project(self):
        from workbench.agent_project_access import ProjectAccessManagement
        self.approve_grant()
        proposal = self.service.prepare_proposal(self.client,self.spec_project())
        management, _, payload = self.local_review(proposal)
        receipt = management.approve(proposal['proposal_id'],payload)['receipt']
        access = ProjectAccessManagement(self.runtime)
        preview = access.preview(proposal['proposal_id'])
        path = self.repo.projects_dir / proposal['target_id'] / 'README.md'
        original = path.read_bytes()
        fields = {k:preview[k] for k in ('workspace_id','expected_version','preview_id','preview_digest')}
        fields.update(request_id='scope-interruption',approved=True)
        operation = hashlib.sha256(b'scope-interruption').hexdigest()
        def stop(stage):
            if stage == 'prepared':
                path.write_bytes(original + b'\nexternal edit\n')
                raise OSError('synthetic interruption after durable scope intent')
        from unittest.mock import patch
        with patch('workbench.agent_management.CredentialManager.checkpoint', side_effect=stop):
            with self.assertRaises(OSError):
                access.approve(proposal['proposal_id'],fields)
        self.assertEqual(self.manager.operation(operation)['state'],'recovery_required')
        self.assertNotIn(proposal['target_id'],self.security.clients()[self.key]['project_ids'])
        self.assertEqual(management.action(payload['request_id'])['receipt'],receipt)
        path.write_bytes(original)
        self.assertEqual(self.manager.operation(operation)['state'],'recovery_required')
        self.assertEqual(self.manager.abandon(operation)['state'],'abandoned')
        self.assertNotIn(proposal['target_id'],self.security.clients()[self.key]['project_ids'])
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(management.action(payload['request_id'])['receipt'],receipt)

    def test_access_intent_recovers_when_original_project_and_client_are_unchanged(self):
        from workbench.agent_project_access import ProjectAccessManagement
        from unittest.mock import patch
        self.approve_grant()
        proposal = self.service.prepare_proposal(self.client,self.spec_project())
        management, _, payload = self.local_review(proposal)
        receipt = management.approve(proposal['proposal_id'],payload)['receipt']
        access = ProjectAccessManagement(self.runtime)
        preview = access.preview(proposal['proposal_id'])
        fields = {k:preview[k] for k in ('workspace_id','expected_version','preview_id','preview_digest')}
        fields.update(request_id='scope-resume',approved=True)
        def stop(stage):
            if stage == 'prepared':
                raise OSError('synthetic interruption before registry publication')
        with patch('workbench.agent_management.CredentialManager.checkpoint', side_effect=stop):
            with self.assertRaises(OSError):
                access.approve(proposal['proposal_id'],fields)
        self.assertNotIn(proposal['target_id'],self.security.clients()[self.key]['project_ids'])
        recovered = self.security.manager().operation(hashlib.sha256(b'scope-resume').hexdigest())
        self.assertEqual(recovered['state'],'completed')
        self.assertEqual(recovered['result']['project_id'],proposal['target_id'])
        self.assertEqual(access.approve(proposal['proposal_id'],fields),recovered['result'])
        self.assertEqual(management.action(payload['request_id'])['receipt'],receipt)

    def test_real_exit_creation_grant_preserves_registry_floor_and_exact_scope(self):
        script = '''
import os,sys
from pathlib import Path
from workbench.agent_security import AgentSecurity
from workbench.agent_management import client_version
root, base, key, point = sys.argv[1:]
security=AgentSecurity(Path(root),Path(base)); manager=security.manager(); before=security.clients()[key]
manager.checkpoint=lambda stage:os._exit(74) if stage==point else None
manager.run('project_create_grant',{'approval_digest':'a'*64},key,client_version(before),'grant-'+point)
'''
        for point in ('private_snapshot','prepared','format_fence','config','registry','terminal_log','completed'):
            with self.subTest(point=point):
                before = self.security.clients()[self.key]
                child = subprocess.run([sys.executable,'-c',script,str(self.repo.root),str(self.base / 'credentials'),self.key,point],
                                       cwd=Path(__file__).resolve().parent,capture_output=True,timeout=20)
                self.assertEqual(child.returncode,74,child.stderr.decode(errors='replace'))
                result = self.manager.operation(hashlib.sha256(('grant-'+point).encode()).hexdigest()) if point != 'private_snapshot' else None
                if point == 'private_snapshot':
                    self.manager.report()
                    result = self.manager.operation(hashlib.sha256(('grant-'+point).encode()).hexdigest())
                    self.assertEqual(result['state'],'abandoned')
                else:
                    self.assertEqual(result['state'],'completed')
                after = self.security.clients()[self.key]
                self.assertEqual(after['project_ids'],before['project_ids'])
                self.assertEqual(after['scopes'],before['scopes'])
                self.assertEqual(can_create_project(after),point != 'private_snapshot')
                self.assertEqual(self.security.registry_version(),6)
