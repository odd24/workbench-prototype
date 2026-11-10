"""AG-139 category authorization, privacy and the common execution journal."""

import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from test_agent_support import AgentFixture
from workbench.agent_category_management import CategoryGrantManagement
from workbench.agent_management import client_version
from workbench.agent_proposal_management import ProposalManagement
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError
from workbench.category_prepared import DOCUMENT


class AgentCategoryTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.runtime = self.repo.agent_runtime = AgentRuntime(self.repo, base=self.base / 'credentials')
        self.management = ProposalManagement(self.runtime)
        self.grants = CategoryGrantManagement(self.runtime)
        self.item = self.repo.create_document({'title':'要迁移的文档', 'category':'旧分类', 'body':'完整正文'})
        self.selection = {'family':DOCUMENT, 'name':'旧分类'}

    def grant(self, operation):
        key = self.client['client_id']
        preview = self.grants.preview(key, {'workspace_id':self.security.workspace_id,
                                'expected_version':client_version(self.client),
                                'selection':{**self.selection, 'operation':operation, 'project_id':None}})
        request = {field:preview[field] for field in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')}
        request.update(approved=True, request_id=uuid.uuid4().hex)
        first = self.grants.approve(key, request)
        self.assertEqual(self.grants.approve(key, request), first)
        self.client = self.security.clients()[key]

    def propose(self):
        return self.service.prepare_proposal(self.client, {'kind':'category', 'operation':'rename',
                                             'request_id':uuid.uuid4().hex,
                                             'content':{**self.selection, 'new_name':'新分类'}})

    def test_agent_rename_with_exact_scope_narrows_then_restores(self):
        key = self.client['client_id']
        self.security.manager().run('edit', {**{k:self.client[k] for k in ('name', 'scopes', 'project_ids')}, 'categories':['旧分类']}, key, client_version(self.client))
        self.client = self.security.clients()[key]
        self.grant('rename')
        self.assertEqual(self.security.registry_version(), 8)
        proposal = self.propose()
        self.assertNotIn('category_local_details', proposal)
        result = self.management.preview(proposal['proposal_id'])
        preview = result['preview']
        self.assertEqual(preview['content']['members'][0]['before']['body'], '完整正文')
        self.assertEqual(result['local_category_plan']['authorization'][0]['narrow']['categories'], [])
        approved = self.management.approve(proposal['proposal_id'], {
            'workspace_id':self.security.workspace_id, 'version':1, 'preview_digest':preview['preview_digest'],
            'preview_ticket':result['preview_ticket'], 'request_id':uuid.uuid4().hex})
        self.assertEqual(approved['receipt']['kind'], 'category')
        self.assertEqual(self.repo.get_document(self.item['id'])[0]['category'], '新分类')
        self.assertEqual(self.security.clients()[key]['categories'], ['新分类'])
        self.assertFalse(self.repo.agent_proposals.recover()['blocked'])

    def test_local_category_uses_journal_without_agent_identity(self):
        original = self.security.clients()
        preview = self.repo.preview_category_change({'operation':'rename', 'selection':{**self.selection, 'new_name':'网页分类'}})
        self.assertEqual(self.repo.get_document(self.item['id'])[0]['category'], '旧分类')
        receipt = self.repo.approve_category_change({'ticket':preview['ticket']})
        self.assertEqual(self.repo.approve_category_change({'ticket':preview['ticket']}), receipt)
        stored = self.repo.agent_proposals._load(receipt['proposal_id'], expire=False)
        self.assertTrue(stored['local_category_origin'])
        self.assertEqual(self.security.clients(), original)
        self.assertEqual(self.repo.get_document(self.item['id'])[0]['category'], '网页分类')

    def test_destination_default_scope_must_not_gain_members(self):
        self.security.add_client('只读默认', ['read'], [], ['未分类'], 'http://127.0.0.1:4173')
        with self.assertRaisesRegex(AgentError, '扩大'):
            self.repo.preview_category_change({'operation':'delete', 'selection':self.selection})
        self.assertEqual(self.repo.get_document(self.item['id'])[0]['category'], '旧分类')

    def test_revision_requires_a_new_local_preview(self):
        self.grant('rename')
        proposal = self.propose()
        review = self.management.preview(proposal['proposal_id'])
        revised = self.service.revise_proposal(self.client, proposal['proposal_id'], {
            'expected_version':1, 'content':{**self.selection, 'new_name':'另一个分类'}})
        self.assertEqual(revised['version'], 2)
        with self.assertRaises(AgentError):
            self.management.approve(proposal['proposal_id'], {
                'workspace_id':self.security.workspace_id, 'version':1,
                'preview_digest':review['preview']['preview_digest'], 'preview_ticket':review['preview_ticket'],
                'request_id':uuid.uuid4().hex})
        self.assertEqual(self.repo.get_document(self.item['id'])[0]['category'], '旧分类')

    def test_implicit_activation_consumes_create_grant_even_when_name_is_reused(self):
        self.selection = {**self.selection, 'name':'未来名称'}
        self.grant('create')
        self.repo.ensure_document_category('未来名称')
        self.assertEqual(self.security.clients()[self.client['client_id']]['category_write_grants']['grants'], [])
        self.repo.delete_document_category('未来名称')
        with self.assertRaises(AgentError):
            self.service.prepare_proposal(self.security.clients()[self.client['client_id']], {
                'kind':'category', 'operation':'create', 'request_id':'stale-create', 'content':self.selection})
        self.assertNotIn('未来名称', self.repo.document_categories())

    def test_after_content_with_missing_original_history_keeps_client_narrowed(self):
        key = self.client['client_id']
        self.security.manager().run('edit', {**{field:self.client[field] for field in ('name','scopes','project_ids')},
                                            'categories':['旧分类']}, key, client_version(self.client))
        review = self.repo.preview_category_change({'operation':'rename', 'selection':{**self.selection, 'new_name':'新分类'}})

        def interrupted(stage):
            if stage == 'category_restore_applying':
                raise OSError('停止在补发之前')

        with patch.object(self.store, 'checkpoint', side_effect=interrupted), self.assertRaises(AgentError):
            self.repo.approve_category_change({'ticket':review['ticket']})
        self.assertEqual(self.repo.get_document(self.item['id'])[0]['category'], '新分类')
        self.assertEqual(self.security.clients()[key]['categories'], [])
        history, = (self.repo.root / 'history' / self.item['id']).glob('*.md')
        original = history.read_bytes()
        history.unlink()
        self.assertTrue(self.store.recover()['blocked'])
        self.assertEqual(self.security.clients()[key]['categories'], [])
        history.write_bytes(original)
        self.assertFalse(self.store.recover()['blocked'])
        self.assertEqual(self.security.clients()[key]['categories'], ['新分类'])

    def test_real_exits_replay_local_receipt_after_restart(self):
        from server import Repository

        script = '''
import os, sys
from pathlib import Path
from server import Repository
from workbench.agent_runtime import AgentRuntime
root, base = map(Path, sys.argv[1:3])
source, destination, point = sys.argv[3:]
repo = Repository(root)
repo.agent_runtime = AgentRuntime(repo, base=base)
review = repo.preview_category_change({'operation':'rename','selection':{
    'family':'document_category','name':source,'new_name':destination}})
print(review['ticket'], flush=True)
repo.agent_proposals.checkpoint = lambda stage: os._exit(73) if stage == point else None
repo.approve_category_change({'ticket':review['ticket']})
'''
        key = self.client['client_id']
        self.security.manager().run('edit', {**{field:self.client[field] for field in ('name','scopes','project_ids')},
                                            'categories':['旧分类']}, key, client_version(self.client))
        source = '旧分类'
        stages = ('category_manifest', 'category_client_narrowed', 'category_history', 'category_write',
                  'category_client_restored', 'receipt')
        for index, stage in enumerate(stages):
            with self.subTest(stage=stage):
                destination = f'恢复后分类{index}'
                result = subprocess.run([sys.executable, '-X', 'utf8', '-c', script, str(self.repo.root),
                                         str(self.base / 'credentials'), source, destination, stage],
                                        cwd=Path(__file__).resolve().parent, capture_output=True,
                                        text=True, encoding='utf-8', timeout=20)
                self.assertEqual(result.returncode, 73, result.stderr)
                scope = [source] if stage == 'category_manifest' else [destination] if stage in {'category_client_restored','receipt'} else []
                self.assertEqual(self.security.clients()[key]['categories'], scope)
                reopened = Repository(self.repo.root)
                reopened.agent_runtime = AgentRuntime(reopened, base=self.base / 'credentials')
                request = {'ticket':result.stdout.strip()}
                receipt = reopened.approve_category_change(request)
                self.assertEqual(reopened.approve_category_change(request), receipt)
                self.assertEqual(reopened.get_document(self.item['id'])[0]['category'], destination)
                self.assertEqual(self.security.clients()[key]['categories'], [destination])
                self.assertEqual(list((self.security.config_dir / 'category-plans').glob('*.json')), [])
                source = destination
