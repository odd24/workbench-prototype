"""Disposable Codex pilot for one in-use workflow status migration."""

import json
import time
from urllib.error import HTTPError

from attachment_pilot import await_value
from concept_map_pilot import WINDOW_SECONDS, emit
from issue_delete_pilot import ProposalCase, check_local_approval, main
from server import Repository
from workbench.agent_security import AgentError, read_json
from workbench.agent_workflow_authorization import client_grants, selection
from workbench.agent_workflow_service import candidate
from workbench.workflow_identity import FENCE, LEDGER
from workbench.workflow_prepared import inventory, read_raw, verify_workflow_files, verify_workflow_history
from workbuddy_agent_acceptance import CONFIGURATION_PILOT_TOOLS, WORKFLOW_PILOT_CASE


TEMPLATE = 'ag142-workflow'
SOURCE_STATUS = '进行中'
TARGET_STATUS = '已完成'
OPERATION = 'delete_status'


def seed_template(repo):
    catalogue = repo.config()['workflow_templates']
    standard = next(template for template in catalogue if template['id'] == 'standard')
    custom = {**standard, 'id':TEMPLATE, 'name':'AG142 合成工作流'}
    repo.save_workflow_templates([*catalogue, custom])


class WorkflowCase(ProposalCase):
    server = 'workbench_ag142_workflow'
    tools = CONFIGURATION_PILOT_TOOLS
    relay_flag = '--relay-workflow-pilot'
    directory_prefix = 'workbench-ag142-workflow-'
    request_prefix = 'ag142-workflow'
    client_name = 'AG142 工作流状态迁移'
    kinds = ['todo']
    case_file = WORKFLOW_PILOT_CASE
    target = None

    def __init__(self, repo):
        self.repo = repo
        self.service = repo.agent_service
        self.security = self.service.security
        self.store = self.service.store
        self.project = repo.create_project({'name':'AG142 工作流迁移项目', 'description':'保留项目 README 正文',
                                            'workflow_template':TEMPLATE})['id']
        self.record = repo.create_record({'type':'todo', 'project_id':self.project, 'title':'AG142 活动待办',
                                         'status':SOURCE_STATUS, 'body':'完整待办正文\n\n保留第二段和引号 "甲"。'})['id']
        repo.update_project(self.project, {'todo_status_order':[SOURCE_STATUS, TARGET_STATUS],
                                         'todo_status_record_sorts':{SOURCE_STATUS:'title', TARGET_STATUS:'manual'},
                                         'todo_record_order':[self.record]})
        other = repo.create_project({'name':'AG142 工作流对照项目', 'workflow_template':'standard'})['id']
        repo.create_record({'type':'todo', 'project_id':other, 'title':'AG142 同名状态对照', 'status':SOURCE_STATUS})
        self.project_ids = [self.project]
        self.grant_selection = {'operation':OPERATION, 'template_id':TEMPLATE, 'record_type':'todo'}
        self.command = {'template_id':TEMPLATE, 'record_type':'todo', 'status_id':'doing', 'target_status_id':'done'}
        self.request = {'request_id':'ag142-exact-workflow-status', 'kind':'workflow', 'operation':OPERATION,
                        'confirmation_mode':'local_web', 'content':self.command, 'source_note':'仅本轮合成工作流验收'}
        self.original = inventory(repo.root).raw
        self.original.update({path:read_raw(repo.root, path) for path in (FENCE, LEDGER)})
        self.history = self.history_paths()
        self.check_original()

    def authorize(self, grant):
        return grant('workflow-writes', 'WORKFLOW_STATUS', selection=self.grant_selection)

    def binding_revision(self, proposal):
        return proposal['normalized_content']['revision']

    def final_state(self):
        return {'receipt_count':len(list(self.store.receipts.glob('*.json')))}

    def history_paths(self):
        return set((self.repo.root / 'history').rglob('*.md'))

    def check_original(self):
        if (any(read_raw(self.repo.root, path) != raw for path, raw in self.original.items())
                or self.history_paths() != self.history or self.final_state()['receipt_count']):
            raise ValueError('Workflow, project, record or history changed before approval')

    def check_grant(self, client):
        [grant] = client_grants(client)['grants']
        if (selection(grant) != self.grant_selection or grant['minimum_confirmation_mode'] != 'local_web'
                or client['project_ids'] != [self.project] or client['kinds'] != ['todo']):
            raise ValueError('Workflow grant or content-read scope differs from the fixed fixture')

    def check_preview(self, proposal):
        client = self.security.clients()[proposal['client_id']]
        self.check_grant(client)
        content = proposal['normalized_content']
        self.prepared, impact, dependencies, self.local_plan, _, _ = candidate(
            self.repo, self.security, OPERATION, self.command, content['epoch'], content['managed_time'], client=client)
        if content != impact or proposal['dependencies'] != dependencies or content['unmapped']:
            raise ValueError('Workflow preview differs from the fixed mapped proposal')
        [project], [record] = self.prepared.projects, self.prepared.records
        mapping = {'project_id':self.project, 'type':'todo', 'before':SOURCE_STATUS, 'after':TARGET_STATUS, 'terminal':True}
        if (project['id'] != self.project or mapping not in project['mapping']
                or project['before']['todo_status_order'] != [SOURCE_STATUS, TARGET_STATUS]
                or project['after']['todo_status_order'] != [TARGET_STATUS]
                or project['after']['todo_status_record_sorts'] != {TARGET_STATUS:'manual'}
                or project['after']['todo_record_order'] != [self.record]
                or not any(row['board'] == 'todo' and row['target'] == TARGET_STATUS and row['kept'] == TARGET_STATUS
                           for row in self.prepared.ordering_conflicts)
                or record['id'] != self.record or record['before']['status'] != SOURCE_STATUS
                or record['after']['status'] != TARGET_STATUS or record['after']['completed'] is not True
                or record['after']['body'] != record['before']['body']):
            raise ValueError('Workflow preview omitted full project order, record or explicit terminal mapping')
        before, after = content['templates']['before'], content['templates']['after']
        untouched_templates = [row for row in self.prepared.catalogue_before if row['id'] != TEMPLATE]
        if (before['id'] != TEMPLATE or after['id'] != TEMPLATE
                or [row for row in before['statuses']['todo'] if row['id'] != 'doing'] != after['statuses']['todo']
                or [row for row in self.prepared.catalogue_after if row['id'] != TEMPLATE] != untouched_templates
                or self.prepared.fallback_before != self.prepared.fallback_after):
            raise ValueError('Template preview did not remove exactly the fixed status')

    def check_local_preview(self, review, binding):
        super().check_local_preview(review, binding)
        if review['local_workflow_plan'] != self.local_plan:
            raise ValueError('Local workflow preview omitted full template, project, record or authorization evidence')

    def check_tool_access(self, call, rejected, invoke):
        client = next(iter(self.security.clients().values()))
        self.check_grant(client)
        wrong_scope = (
            {**self.command, 'template_id':'standard'},
            {**self.command, 'record_type':'issue', 'status_id':'in_progress', 'target_status_id':'resolved'},
        )
        for command in wrong_scope:
            request = {**self.request, 'content':command}
            rejected('prepare_proposal', request, 'outside the workflow pilot scope')
            try:
                self.service.prepare_proposal(client, request)
            except AgentError as error:
                assert error.code == 'workflow_unavailable' and error.status == 404 and not error.details, error
            else:
                raise AssertionError('Service disclosed or accepted an unauthorized workflow')
        rejected('prepare_proposal', {**self.request, 'content':self.unmapped_command()}, 'outside the workflow pilot scope')
        self.check_original()
        return {'other_template_and_record_type_denied':True}

    def unmapped_command(self):
        return {key:value for key,value in self.command.items() if key != 'target_status_id'}

    def check_rejections(self, proposal_id, client_id, workspace, local):
        client = self.security.clients()[client_id]
        route = 'proposals/' + proposal_id
        review = local(route + '/preview')
        stale = {'workspace_id':workspace, 'version':review['version'], 'preview_digest':review['preview_digest'],
                 'preview_ticket':review['preview_ticket'], 'request_id':self.request_prefix + '-stale'}
        revised = self.service.revise_proposal(client, proposal_id, {
            'expected_version':review['version'], 'content':self.unmapped_command()})
        current = local(route + '/preview')
        assert 'preview_ticket' not in current
        [missing] = current['preview']['content']['unmapped']
        assert missing['record_id'] == self.record and missing['source_status'] == SOURCE_STATUS
        try:
            local(route + '/approve', {**stale, 'version':current['version'],
                'preview_digest':current['preview']['preview_digest'], 'request_id':self.request_prefix + '-unmapped'})
        except HTTPError as error:
            with error:
                assert error.code == 409 and json.load(error)['code'] == 'preview_expired'
        else:
            raise AssertionError('A preview without a mapping was approved')
        stored = read_json(self.store.proposals / f'{proposal_id}.json')
        try:
            self.service.prepare_submission(client, stored)
        except AgentError as error:
            assert error.code == 'mapping_required', error
        else:
            raise AssertionError('Submission without the in-use status mapping was accepted')
        self.service.revise_proposal(client, proposal_id, {'expected_version':revised['version'], 'content':self.command})
        try:
            local(route + '/approve', stale)
        except HTTPError as error:
            with error:
                assert error.code == 409 and json.load(error)['code'] == 'version_conflict'
        else:
            raise AssertionError('Original approval was accepted after the proposal was revised')
        self.check_original()
        return {'missing_mapping_denied':True, 'older_preview_denied':True}

    def check(self, invoke, client_id, workspace, local):
        return check_local_approval(invoke, self, client_id, workspace, local, check_rejections=self.check_rejections)

    def after_approval(self, binding):
        key = binding['proposal_id']
        proposal = read_json(self.store.proposals / f'{key}.json')
        if proposal['state'] != 'committed':
            return None
        receipt = read_json(self.store.receipts / f'{key}.json')
        manifest = read_json(self.store.operations / f'{key}-{binding["version"]}' / 'manifest.json')
        reopened = Repository(self.repo.root)
        item, _ = reopened.get_record(self.record)
        project = reopened.project(self.project)
        verify_workflow_files(reopened.root, self.prepared.files, self.prepared.watch, final=True)
        verify_workflow_history(reopened.root, self.prepared.files, manifest['history_version'])
        if (receipt != proposal['receipt'] or receipt != manifest['receipt'] or manifest['state'] != 'committed'
                or receipt['version'] != binding['version'] or receipt['operation'] != OPERATION
                or receipt['scope'] != {'type':'workflow', **self.grant_selection}
                or receipt['approval']['mode'] != 'local_web' or receipt['approval']['preview_digest'] != binding['preview_digest']
                or self.final_state()['receipt_count'] != 1 or item['status'] != TARGET_STATUS or item['completed'] is not True
                or project['workflow_template'] != TEMPLATE or project['todo_status_order'] != [TARGET_STATUS]):
            raise ValueError('Workflow result, actual migration or unique original receipt could not be verified')
        return {'receipt':receipt, 'record_migrated':True, 'original_history_matches':True, 'other_template_unchanged':True}

    def run_window(self, client_id, workspace, stop, audit, local):
        deadline = time.monotonic() + WINDOW_SECONDS
        expires_at = int(time.time() + WINDOW_SECONDS)
        prompt = (f'只用 {self.server}。capabilities 核对空间 {workspace}。用以下固定请求调用 prepare_proposal '
                  '和 preview_proposal，完整展示模板和受影响项目、待办、排序和冲突、明确状态映射、终态和执行依据。'
                  '请用户在隔离工作台核对完整本机原始内容、版本和摘要，再独立批准。展示后停止。\n'
                  + json.dumps(self.request, ensure_ascii=False, indent=2))
        emit({'mode':'ready_preview', 'prompt':prompt, 'execution_expires_at':expires_at})
        binding = await_value(lambda: self.before_approval(client_id), stop, deadline)
        if not binding:
            return
        self.check_local_preview(local('proposals/' + binding['proposal_id'] + '/preview'), binding)
        emit({'mode':'await_web_approval', **binding, **self.final_state(), 'execution_expires_at':expires_at})
        evidence = await_value(lambda: self.after_approval(binding), stop, deadline)
        if evidence:
            audit.update(evidence)
            emit({'mode':'committed', **evidence})
            await_value(lambda: None, stop, deadline)


if __name__ == '__main__':
    main(WorkflowCase, __doc__, seed=seed_template)
