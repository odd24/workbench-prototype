"""AG-138 scoped project cascade and fixed trash identity."""

import base64
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from test_agent_support import AgentFixture
from workbench.agent_file_handles import SUPPORTED
from workbench.agent_project_delete_authorization import FIELDS, ProjectDeleteGrantManagement, asset_evidence, grant_value, upgraded_project_delete_client
from workbench.agent_management import client_version
from workbench.agent_proposal_management import ProposalManagement
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError
from workbench.project_delete_tree import classify_tree, read_tree
from workbench.write_coordinator import RevisionConflict


@unittest.skipUnless(SUPPORTED, 'native fixed NTFS project cascade')
class ProjectDeleteTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.runtime = self.repo.agent_runtime = AgentRuntime(self.repo, base=self.base / 'credentials')
        self.repo.agent_service = self.service
        self.project_id = self.project['id']
        self.folder = self.repo.projects_dir / self.project_id
        self.management = ProposalManagement(self.runtime)

    def configure(self, *, children=False, assets=False):
        tree = read_tree(self.repo.root, self.folder)
        _, _, standalone, _ = classify_tree(self.repo.root, self.project_id, tree)
        self.client = upgraded_project_delete_client(self.client, grant_value([
            {**FIELDS, 'project_id':self.project_id, 'assets':asset_evidence(standalone) if assets else []},
        ]))
        if children:
            self.client['delete_grants'] = grant_value([
                {'capability':'items.delete', 'operations':['delete'], 'minimum_confirmation_mode':'local_web',
                 'resources':[{'type':'project','id':self.project_id}]},
            ])
        else:
            self.client['delete_grants'] = grant_value()
        self.security.save_clients({self.client['client_id']:self.client})

    def spec_delete(self):
        item = self.service.projects(self.client, {})['items'][0]
        return {'request_id':uuid.uuid4().hex, 'kind':'project', 'operation':'delete',
                'target_id':self.project_id, 'base_revision':item['revision']}

    def test_local_approval_moves_original_tree_and_replays_after_restore(self):
        record = self.repo.create_record({'type':'issue', 'project_id':self.project_id, 'title':'级联内容'})
        self.repo.add_project_asset(self.project_id, '受控附件.txt', base64.b64encode(b'payload').decode())
        with self.assertRaisesRegex(AgentError, '不可级联删除'):
            self.service.prepare_proposal(self.client, self.spec_delete())
        self.configure(children=True, assets=True)
        proposal = self.service.prepare_proposal(self.client, self.spec_delete())
        proposal_id = proposal['proposal_id']
        review = self.management.preview(proposal_id)
        preview = review['preview']
        self.assertEqual(preview['content']['children'][0]['item']['id'], record['id'])
        self.assertTrue(self.folder.exists())
        approval = {'workspace_id':self.security.workspace_id, 'version':preview['version'],
                    'preview_digest':preview['preview_digest'], 'preview_ticket':review['preview_ticket'],
                    'request_id':uuid.uuid4().hex}
        receipt = self.management.approve(proposal_id, approval)['receipt']
        token = receipt['trash_token']
        self.assertFalse(self.folder.exists())
        self.assertTrue(token.startswith('project-agent-'))
        self.assertEqual(self.repo.list_trash()[0]['delete_schema_version'], 2)
        self.assertIn(record['id'], self.repo.reserved_resource_ids())
        from server import Repository
        copied_root = self.base / 'migrated'
        shutil.copytree(self.repo.root, copied_root)
        copied = Repository(copied_root)
        copied_asset = copied.trash_dir / token / 'assets/library/受控附件.txt'
        copied_asset.write_bytes(b'foreign bytes')
        copied.cleanup_trash(retention_days=0)
        self.assertEqual(copied_asset.read_bytes(), b'foreign bytes')
        with self.assertRaisesRegex(AgentError, '完整树证据'):
            copied.purge_trash(token)
        copied_asset.write_bytes(b'payload')
        copied.restore_trash(token)
        self.assertEqual(copied.get_record(record['id'])[0]['title'], '级联内容')
        self.folder.mkdir()
        with self.assertRaises(RevisionConflict):
            self.repo.restore_trash(token)
        self.folder.rmdir()
        self.repo.restore_trash(token)
        self.assertEqual(self.repo.get_record(record['id'])[0]['title'], '级联内容')
        self.assertEqual(self.management.approve(proposal_id, approval)['receipt'], receipt)
        self.assertTrue(self.folder.exists())

    def test_child_and_external_asset_permissions_fail_closed(self):
        self.repo.create_record({'type':'issue', 'project_id':self.project_id, 'title':'级联内容'})
        asset = self.repo.add_project_asset(self.project_id, '受控附件.txt', base64.b64encode(b'payload').decode())
        for children, assets in [(True, False), (False, True)]:
            self.configure(children=children, assets=assets)
            with self.assertRaises(AgentError) as caught:
                self.service.prepare_proposal(self.client, self.spec_delete())
            self.assertEqual(caught.exception.code, 'impact_unavailable')
        self.configure(children=True, assets=True)
        from urllib.parse import quote
        self.repo.create_document({'title':'外部附件', 'category':'允许',
                                   'body':f"[附件](/api/project-assets/{quote(self.project_id)}/{asset['id']})"})
        with self.assertRaises(AgentError) as caught:
            self.service.prepare_proposal(self.client, self.spec_delete())
        self.assertEqual(caught.exception.code, 'impact_unavailable')
        self.assertTrue(self.folder.is_dir())

    def test_fresh_management_grant_and_revoke_preserve_registry_floor(self):
        asset = self.repo.add_project_asset(self.project_id, '受控附件.txt', base64.b64encode(b'payload').decode())
        grants = ProjectDeleteGrantManagement(self.runtime)
        preview = grants.preview(self.client['client_id'], {
            'workspace_id':self.security.workspace_id, 'expected_version':client_version(self.client),
            'project_id':self.project_id, 'asset_ids':[asset['id']],
        })
        approval = {key:preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')}
        approval.update(approved=True, request_id=uuid.uuid4().hex)
        result = grants.approve(self.client['client_id'], approval)
        self.assertEqual(grants.approve(self.client['client_id'], approval), result)
        self.assertEqual(self.security.registry_version(), 7)
        current = self.security.clients()[self.client['client_id']]
        self.assertEqual(current['authorization_schema_version'], 8)
        self.assertEqual(current['project_delete_grants']['grants'][0]['assets'][0]['id'], asset['id'])
        rotated = self.security.manager().run('rotate', {'base_url':'http://127.0.0.1:4174'}, self.client['client_id'], client_version(current))
        grants.revoke(self.client['client_id'], {'workspace_id':self.security.workspace_id,
                      'expected_version':rotated['version'], 'request_id':uuid.uuid4().hex})
        self.assertEqual(self.security.registry_version(), 7)
        self.assertEqual(grants.list(self.client['client_id'])['grants']['grants'], [])

    def test_real_exits_use_original_tree_and_never_repeat_an_unknown_move(self):
        script = r'''
import json, os, sys, uuid
from pathlib import Path
from server import Repository
from workbench.agent_project_delete_authorization import FIELDS, grant_value, upgraded_project_delete_client
from workbench.agent_proposal_management import ProposalManagement
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService

base, stage = Path(sys.argv[1]), sys.argv[2]
repo = Repository(base / 'data')
project = repo.create_project({'name':'原始项目','description':'原文件内容'})
record = repo.create_record({'type':'issue','project_id':project['id'],'title':'持久保留子身份'})
security = AgentSecurity(repo.root, base / 'credentials')
key = security.add_client('验收', ['read','propose','commit'], [project['id']], [], 'http://127.0.0.1:4174')['client_id']
client = upgraded_project_delete_client(security.clients()[key], grant_value([{**FIELDS,'project_id':project['id'],'assets':[]}]))
client['delete_grants'] = grant_value([{'capability':'items.delete','operations':['delete'],
    'minimum_confirmation_mode':'local_web','resources':[{'type':'project','id':project['id']}]}])
security.save_clients({key:client})
repo.agent_runtime = AgentRuntime(repo, base=base / 'credentials')
repo.agent_service = service = AgentService(repo, security)
proposal = service.prepare_proposal(client, {'request_id':'original-project-delete','kind':'project',
    'operation':'delete','target_id':project['id'],'base_revision':service.projects(client,{})['items'][0]['revision']})
local = ProposalManagement(repo.agent_runtime)
review = local.preview(proposal['proposal_id'])
payload = {'workspace_id':security.workspace_id,'request_id':'original-local-approval','version':1,
    'preview_ticket':review['preview_ticket'],'preview_digest':review['preview']['preview_digest']}
(base / 'fixture.json').write_text(json.dumps({'project_id':project['id'],'proposal_id':proposal['proposal_id'],
    'child_id':record['id'],'trash_token':review['preview']['trash_token']}), encoding='utf-8')
service.store.checkpoint = lambda name: os._exit(78) if name == stage else None
local.approve(proposal['proposal_id'], payload)
raise RuntimeError('expected checkpoint not reached')
'''
        from server import Repository
        from workbench.agent_security import AgentSecurity
        from workbench.agent_service import AgentService
        for stage in ('manifest', 'delete_move_applying', 'delete_move', 'delete_index', 'receipt'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                process = subprocess.run([sys.executable, '-c', script, str(base), stage], capture_output=True, timeout=30)
                self.assertEqual(process.returncode, 78, process.stderr.decode(errors='replace'))
                fixture = json.loads((base / 'fixture.json').read_text(encoding='utf-8'))
                repo = Repository(base / 'data')  # Agent-disabled startup must recover/guard before cleanup.
                source = repo.projects_dir / fixture['project_id']
                destination = repo.trash_dir / fixture['trash_token']
                if stage == 'delete_move':
                    source.mkdir()
                    (source / 'external.txt').write_bytes(b'unrelated new source')
                security = AgentSecurity(repo.root, base / 'credentials')
                service = AgentService(repo, security)
                recovery = service.store.recover()
                if stage == 'delete_move_applying':
                    self.assertTrue(recovery['operations'])
                    self.assertTrue(source.is_dir())
                    self.assertFalse(destination.exists())
                    self.assertEqual(repo.list_trash(), [])
                    with self.assertRaises(AgentError):
                        repo.delete_project(fixture['project_id'])
                else:
                    self.assertFalse(recovery['operations'])
                    self.assertTrue(destination.is_dir())
                    self.assertEqual(repo.list_trash()[0]['token'], fixture['trash_token'])
                    self.assertIn(fixture['child_id'], repo.reserved_resource_ids())
                    if stage == 'delete_move':
                        self.assertEqual((source / 'external.txt').read_bytes(), b'unrelated new source')
                    else:
                        self.assertFalse(source.exists())
