"""Workflow grants, complete previews, publication, and local compatibility."""

import subprocess
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from test_agent_support import AgentFixture
from workbench.agent_management import client_version
from workbench.agent_proposal_management import ProposalManagement
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError
from workbench.agent_workflow_management import WorkflowGrantManagement


class AgentWorkflowTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.repo.agent_runtime = AgentRuntime(self.repo, base=self.base / 'credentials')
        self.proposals = ProposalManagement(self.repo.agent_runtime)
        self.grants = WorkflowGrantManagement(self.repo.agent_runtime)
        key = self.client['client_id']
        self.security.manager().run('edit', {
            **{field:self.client[field] for field in ('name','scopes','categories')},
            'kinds':['issue','todo','document','info'], 'project_ids':[self.project['id']]}, key, client_version(self.client))
        self.client = self.security.clients()[key]
        self.item = self.repo.create_record({'type':'todo','project_id':self.project['id'],'title':'完整待办',
                                             'status':'进行中','body':'原正文'})
        active = next(row for row in self.repo.config()['workflow_templates'][0]['statuses']['todo'] if row['name'] == '进行中')
        self.selection = {'template_id':'standard','record_type':'todo','status_id':active['id']}

    def grant(self, choice):
        client = self.client
        review = self.grants.preview(client['client_id'], {'workspace_id':self.security.workspace_id,
            'expected_version':client_version(client), 'selection':choice})
        request = {key:review[key] for key in ('workspace_id','expected_version','preview_id','preview_digest')}
        request.update(approved=True, request_id=uuid.uuid4().hex)
        result = self.grants.approve(client['client_id'], request)
        self.assertEqual(self.grants.approve(client['client_id'], request), result)
        self.client = self.security.clients()[client['client_id']]
        return review

    def prepare(self, operation, selection):
        return self.service.prepare_proposal(self.client, {'kind':'workflow','operation':operation,
            'request_id':uuid.uuid4().hex,'content':selection})

    def approval(self, proposal):
        review = self.proposals.preview(proposal['proposal_id'])
        preview = review['preview']
        return review, {'workspace_id':self.security.workspace_id,'version':preview['version'],
            'preview_digest':preview['preview_digest'],'preview_ticket':review.get('preview_ticket', 'x' * 43),
            'request_id':uuid.uuid4().hex}

    def test_used_state_requires_mapping_and_new_independent_approval(self):
        grant = self.grant({'operation':'delete_status','template_id':'standard','record_type':'todo'})
        self.assertIn('当前和以后合法状态', grant['disclosure'])
        self.assertEqual(self.security.registry_version(), 9)
        proposed = self.prepare('delete_status', self.selection)
        self.assertNotIn('workflow_local_details', proposed)
        self.assertEqual(proposed['normalized_content']['unmapped'][0]['record_id'], self.item['id'])
        old, request = self.approval(proposed)
        self.assertIn('local_workflow_plan', old)
        self.assertNotIn('preview_ticket', old)
        with self.assertRaises(AgentError):
            self.proposals.approve(proposed['proposal_id'], request)
        revised = self.service.revise_proposal(self.client, proposed['proposal_id'], {
            'expected_version':1, 'content':{**self.selection,'target_status_id':'done'}})
        self.assertEqual(revised['version'], 2)
        with self.assertRaises(AgentError):
            self.proposals.approve(proposed['proposal_id'], request)
        review, current = self.approval(revised)
        self.assertEqual(review['preview']['content']['records'][0]['before']['body'].strip(), '原正文')
        self.assertTrue(review['preview']['content']['records'][0]['after']['completed'])
        with ThreadPoolExecutor(max_workers=2) as worker:
            result, replay = worker.map(lambda _:self.proposals.approve(proposed['proposal_id'], current), range(2))
        self.assertEqual(replay, result)
        self.assertEqual(result['receipt']['kind'], 'workflow')
        self.assertEqual(self.repo.get_record(self.item['id'])[0]['status'], '已完成')
        self.assertFalse(self.store.recover()['blocked'])

    def test_template_permission_cannot_read_other_project_or_hidden_counts(self):
        hidden = self.repo.create_project({'name':'不可见项目'})
        self.repo.create_record({'type':'todo','project_id':hidden['id'],'title':'不可见正文','status':'进行中'})
        self.grant({'operation':'rename_status','template_id':'standard','record_type':'todo'})
        with self.assertRaises(AgentError) as error:
            self.prepare('rename_status', {**self.selection,'name':'待验收'})
        self.assertEqual(error.exception.status, 404)
        self.assertEqual(error.exception.details, {})
        self.assertNotIn(hidden['id'], str(error.exception))

    def test_read_scope_hides_unchanged_manual_ids_and_rejects_unreadable_mixed_changes(self):
        hidden = self.repo.create_record({'type':'issue','project_id':self.project['id'],'title':'隐藏事项','status':'待处理'})
        key = self.client['client_id']
        self.security.manager().run('edit', {
            **{field:self.client[field] for field in ('name','scopes','categories','project_ids')},
            'kinds':['todo']}, key, client_version(self.client))
        self.client = self.security.clients()[key]
        self.grant({'operation':'rename_status','template_id':'standard','record_type':'todo'})
        self.repo.update_project(self.project['id'], {'mixed_record_order':[hidden['id'],self.item['id']]})
        result = self.prepare('rename_status', {**self.selection,'name':'待验收'})
        self.assertNotIn(hidden['id'], str(result))
        self.assertNotIn('mixed_record_order', str(result))
        self.repo.update_project(self.project['id'], {'mixed_status_order':['进行中']})
        with self.assertRaises(AgentError) as error:
            self.prepare('rename_status', {**self.selection,'name':'待验收'})
        self.assertEqual((error.exception.status,error.exception.details), (404,{}))

    def test_local_legacy_and_explicit_flow_share_the_workflow_journal(self):
        templates = self.repo.config()['workflow_templates']
        next(row for row in templates[0]['statuses']['todo'] if row['id'] == self.selection['status_id'])['name'] = '待验收'
        with self.assertRaises(AgentError) as error:
            self.repo.save_workflow_templates(templates, require_preview=True)
        self.assertEqual(error.exception.code, 'workflow_preview_required')
        review = self.repo.preview_workflow_change({'operation':'compat_catalogue','selection':{'templates':templates}})
        request = {'ticket':review['ticket']}
        receipt = self.repo.approve_workflow_change(request)
        self.assertEqual(self.repo.approve_workflow_change(request), receipt)
        self.assertEqual(self.repo.get_record(self.item['id'])[0]['status'], '待验收')
        self.assertTrue(self.store._load(receipt['proposal_id'])['local_workflow_origin'])

    def test_create_permission_consumed_and_retired_template_id_not_reused(self):
        self.grant({'operation':'create','name':'原空缺名'})
        key = self.client['client_id']
        catalogue = self.repo.config()['workflow_templates']
        added = {'id':'legacy-added','name':'原空缺名','statuses':catalogue[0]['statuses']}
        self.repo.save_workflow_templates([*catalogue, added])
        self.repo.save_workflow_templates(catalogue)
        self.client = self.security.clients()[key]
        self.assertEqual(self.client['workflow_write_grants']['grants'], [])
        with self.assertRaises(AgentError):
            self.prepare('create', {'name':'原空缺名'})
        with self.assertRaisesRegex(ValueError, '退役'):
            self.repo.save_workflow_templates([*catalogue, {**added,'name':'另一个名字'}])

    def test_project_switch_requires_project_bound_grant_and_consumes_it(self):
        catalogue = self.repo.config()['workflow_templates']
        target = {'id':'secondary','name':'第二模板','statuses':catalogue[0]['statuses']}
        self.repo.save_workflow_templates([*catalogue, target])
        choice = {'project_id':self.project['id'],'target_template_id':target['id']}
        self.grant({'operation':'switch', **choice})
        proposal = self.prepare('switch', choice)
        _, approval = self.approval(proposal)
        applied = self.proposals.approve(proposal['proposal_id'], approval)
        current = self.security.clients()[self.client['client_id']]
        self.assertFalse(current['workflow_write_grants']['grants'])
        self.assertEqual(self.service.get_proposal(current, proposal['proposal_id'])['receipt'], applied['receipt'])
        self.assertEqual(self.repo.project(self.project['id'])['workflow_template'], target['id'])
        self.assertEqual(self.repo.get_record(self.item['id'])[0]['status'], '进行中')

    def test_real_exit_after_history_and_publication_recovers_original_receipt(self):
        from server import Repository
        script = """
import os, sys
from pathlib import Path
from server import Repository
from workbench.agent_runtime import AgentRuntime
root, private = map(Path, sys.argv[1:3])
point, status_id, name = sys.argv[3:]
repo = Repository(root)
repo.agent_runtime = AgentRuntime(repo, base=private)
review = repo.preview_workflow_change({'operation':'rename_status','selection':{
    'template_id':'standard','record_type':'todo','status_id':status_id,'name':name}})
print(review['ticket'], flush=True)
repo.agent_proposals.checkpoint = lambda stage: os._exit(73) if stage == point else None
repo.approve_workflow_change({'ticket':review['ticket']})
"""
        for index, stage in enumerate(('workflow_manifest','workflow_history','workflow_write','workflow_verified','receipt')):
            with self.subTest(stage=stage):
                destination = f'恢复后状态{index}'
                child = subprocess.run([sys.executable,'-X','utf8','-c',script,str(self.repo.root),
                                        str(self.base / 'credentials'), stage, self.selection['status_id'], destination],
                                       capture_output=True,text=True,encoding='utf-8',timeout=30,
                                       cwd=Path(__file__).resolve().parent)
                self.assertEqual(child.returncode, 73, child.stderr)
                reopened = Repository(self.repo.root)
                reopened.agent_runtime = AgentRuntime(reopened, base=self.base / 'credentials')
                request = {'ticket':child.stdout.strip()}
                receipt = reopened.approve_workflow_change(request)
                self.assertEqual(reopened.approve_workflow_change(request), receipt)
                self.assertEqual(reopened.get_record(self.item['id'])[0]['status'], destination)
                self.assertFalse(list((self.security.config_dir / 'workflow-plans').glob('*.json')))

    def test_third_party_edit_after_history_is_preserved_and_blocks_recovery(self):
        review = self.repo.preview_workflow_change({'operation':'rename_status',
            'selection':{**self.selection,'name':'原待应用'}})
        request = {'ticket':review['ticket']}

        def interrupted(stage):
            if stage == 'workflow_history':
                raise OSError('synthetic interruption')

        with patch.object(self.store,'checkpoint',side_effect=interrupted), self.assertRaises(AgentError):
            self.repo.approve_workflow_change(request)
        path = Path(self.item['file_path'])
        external = path.read_bytes() + b'\nthird party\n'
        path.write_bytes(external)
        self.assertTrue(self.store.recover()['blocked'])
        self.assertEqual(path.read_bytes(), external)
        self.assertNotIn('原待应用', str(self.repo.config()['workflow_templates']))
