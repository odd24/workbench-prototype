"""Workflow command and status mapping contracts."""

import tempfile
import unittest
from pathlib import Path

from workbench.workflow_changes import (
    change_catalogue, effective_template, map_states, project_order_after,
    record_after, target_state, validate_catalogue, validate_command,
)
from workbench.workflow_prepared import apply_workflow_files, prepare_workflow
from workbench.write_coordinator import RevisionConflict
from workbench.agent_security import AgentError


def template(key='standard', name='系统原名称'):
    return {'id':key, 'name':name, 'statuses':{
        kind:[{'id':'open', 'name':'进行中', 'color':'#334455', 'completed':False},
              {'id':'done', 'name':'完成', 'color':'#336655', 'completed':True}]
        for kind in ('issue', 'todo', 'idea')
    }}


class WorkflowChangeTests(unittest.TestCase):
    def test_template_create_copy_rename_and_system_protection(self):
        original = template()
        created = change_catalogue([original], 'create', validate_command('create', {'name':'新模板'}), 'fresh-id')
        self.assertEqual(created[1]['statuses'], original['statuses'])
        copied = change_catalogue(created, 'copy', {'template_id':'fresh-id', 'name':'副本'}, 'copy-id')
        renamed = change_catalogue(copied, 'rename', {'template_id':'fresh-id', 'name':'新显示名'})
        self.assertEqual((renamed[0]['name'], renamed[1]['id'], renamed[1]['name']), ('系统原名称', 'fresh-id', '新显示名'))
        self.assertEqual(copied[1]['name'], '新模板')
        with self.assertRaisesRegex(ValueError, '系统工作流'):
            change_catalogue(copied, 'rename', {'template_id':'standard', 'name':'尝试更名'})

    def test_type_scoped_status_add_reorder_rename_and_delete(self):
        context = {'template_id':'standard', 'record_type':'todo'}
        existing = [template()]
        command = validate_command('add_status', {**context,'name':'稍后验证','color':'#123ABC','terminal':False}, agent=True)
        added = change_catalogue(existing, 'add_status', command, 'verify-id')
        ordered = change_catalogue(added, 'reorder', {**context,'status_id':'verify-id','anchor_status_id':'open','position':'before'})
        self.assertEqual([item['id'] for item in ordered[0]['statuses']['todo']], ['verify-id','open','done'])
        renamed = change_catalogue(ordered, 'rename_status', {**context,'status_id':'verify-id','name':'现在验证'})
        removed = change_catalogue(renamed, 'delete_status', {**context,'status_id':'open','target_status_id':'verify-id'})
        self.assertEqual(removed[0]['statuses']['todo'][0]['name'], '现在验证')
        self.assertEqual(removed[0]['statuses']['issue'], existing[0]['statuses']['issue'])
        with self.assertRaises(ValueError):
            validate_command('rename_status', {**context,'record_type':'idea','status_id':'open','name':'旧想法'}, agent=True)
        with self.assertRaises(ValueError):
            validate_command('switch', {'project_id':'p','target_template_id':'x','completed':True})

    def test_switch_natural_and_explicit_mappings_use_target_completion(self):
        old = template()['statuses']['todo']
        target = [{'id':'new-open','name':'进行中','completed':True}, {'id':'review','name':'待验收'}]
        mapped = map_states(old, target, switch=True, explicit={'模板外':'review'})
        self.assertTrue(record_after({'type':'todo','completed':False}, mapped['进行中'])['completed'])
        self.assertEqual(record_after({'type':'todo'}, mapped['模板外']), {'type':'todo','status':'待验收','completed':False})
        self.assertIsNone(target_state('完成', mapped, target, switching=True))
        self.assertIsNone(target_state('未知', mapped, target, switching=True))
        self.assertNotIn('completed', record_after({'type':'idea'}, target[0]))

    def test_board_expands_shared_column_and_prefers_existing_destination_sort(self):
        changes, conflicts = project_order_after({
            'mixed_status_order':['进行中','目标','原外列'],
            'mixed_status_record_sorts':{'进行中':'updated','目标':'manual'},
            'todo_status_order':['进行中','目标'],
            'todo_status_record_sorts':{'进行中':'title','目标':'due'},
            'mixed_record_order':['TODO-0001','ISSUE-0002'],
        }, {'issue':{'进行中':['保留列']}, 'todo':{'进行中':['目标'], '目标':['目标']}, 'idea':{}})
        self.assertEqual(changes['mixed_status_order'], ['保留列','目标','原外列'])
        self.assertEqual(changes['mixed_status_record_sorts'], {'保留列':'updated','目标':'manual'})
        self.assertEqual(changes['todo_status_order'], ['目标'])
        self.assertEqual(changes['todo_status_record_sorts'], {'目标':'due'})
        self.assertNotIn('mixed_record_order', changes)
        self.assertEqual([item['kept'] for item in conflicts], ['目标','目标'])

    def test_legacy_fallback_requires_existing_meanings_to_agree(self):
        existing = template('old','旧模板')
        templates = validate_catalogue([existing])
        self.assertEqual(effective_template({}, templates, existing['statuses']), existing)
        self.assertIsNone(effective_template({'workflow_template':'missing'}, templates, {'todo':[]}))
        current = template()
        self.assertEqual(effective_template({}, validate_catalogue([existing,current]), {}), current)


class PreparedWorkflowTests(unittest.TestCase):
    def setUp(self):
        from server import Repository
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Repository(Path(self.temp.name))
        self.project = self.repo.create_project({'name':'状态迁移项目'})['id']
        self.todo = self.repo.create_record({'type':'todo', 'project_id':self.project, 'title':'要迁移',
                                            'status':'进行中', 'body':'保留正文'})
        self.stamp = '2026-11-10T09:00:00+08:00'

    def test_explicit_delete_migrates_raw_markdown_and_board_keys(self):
        path = Path(self.todo['file_path'])
        raw = path.read_bytes() + b'\r\n\r\n'
        path.write_bytes(raw)
        self.repo.update_project(self.project, {'mixed_status_order':['进行中','已完成'],
            'mixed_status_record_sorts':{'进行中':'title','已完成':'manual'}, 'todo_record_order':[self.todo['id']]})
        active = next(state for state in self.repo.config()['workflow_templates'][0]['statuses']['todo'] if state['name'] == '进行中')
        command = {'template_id':'standard','record_type':'todo','status_id':active['id']}
        draft = prepare_workflow(self.repo.root, 'delete_status', command, stamp=self.stamp)
        self.assertEqual(draft.unmapped[0]['record_id'], self.todo['id'])
        self.assertEqual(path.read_bytes(), raw)
        plan = prepare_workflow(self.repo.root, 'delete_status', {**command,'target_status_id':'done'}, stamp=self.stamp)
        self.assertFalse(plan.unmapped)
        self.assertTrue(plan.records[0]['after']['completed'])
        version = '20261110-090000-000000'
        apply_workflow_files(self.repo.root, plan.files, plan.watch, history_version=version)
        from server import Repository
        reopened = Repository(self.repo.root)
        self.assertEqual(reopened.get_record(self.todo['id'])[0]['status'], '已完成')
        self.assertEqual(reopened.project(self.project)['mixed_status_order'], ['已完成'])
        self.assertEqual(reopened.project(self.project)['mixed_status_record_sorts'], {'已完成':'manual'})
        self.assertEqual(reopened.project(self.project)['todo_record_order'], [self.todo['id']])
        self.assertEqual((reopened.history_dir / self.todo['id'] / (version + '.md')).read_bytes(), raw)
        self.assertTrue(path.read_bytes().endswith(b'\r\n\r\n'))
        self.assertTrue((reopened.history_dir / 'workflow-projects' / self.project / (version + '.md')).is_file())

    def test_after_membership_change_refuses_all_publication(self):
        statuses = self.repo.config()['workflow_templates'][0]['statuses']['todo']
        active = next(state for state in statuses if state['name'] == '进行中')
        plan = prepare_workflow(self.repo.root, 'rename_status', {'template_id':'standard','record_type':'todo',
                                'status_id':active['id'], 'name':'新名'}, stamp=self.stamp)
        self.repo.create_record({'type':'todo', 'project_id':self.project, 'title':'迟到的成员', 'status':'进行中'})
        with self.assertRaises(RevisionConflict):
            apply_workflow_files(self.repo.root, plan.files, plan.watch, history_version='20261110-090000-000000')
        self.assertEqual(self.repo.get_record(self.todo['id'])[0]['status'], '进行中')

    def test_history_old_state_requires_explicit_replacement_or_preserve_current(self):
        key = self.todo['id']
        self.repo.update_record(key, {'body':'当前内容'})
        catalogue = self.repo.config()['workflow_templates']
        active = next(row for row in catalogue[0]['statuses']['todo'] if row['name'] == '进行中')
        active['name'] = '等待复验'
        self.repo.save_workflow_templates(catalogue)
        older = self.repo.list_history(key)[-1]['version']
        current = self.repo.get_record(key)[0]
        with self.assertRaises(AgentError) as error:
            self.repo.restore_history(key, older, current['revision'])
        self.assertEqual(error.exception.code, 'history_workflow_resolution_required')
        self.assertEqual(self.repo.read_history(key, older)['status'], '进行中')
        kept = self.repo.restore_history(key, older, current['revision'], {'mode':'keep_current'})
        self.assertEqual((kept['status'], kept['body']), ('等待复验', '保留正文'))
        with self.assertRaises(RevisionConflict):
            self.repo.restore_history(key, older, current['revision'], {'mode':'replace','status_id':'done'})
        restored = self.repo.restore_history(key, older, kept['revision'], {'mode':'replace','status_id':'done'})
        self.assertEqual((restored['status'], restored['completed']), ('已完成', True))
