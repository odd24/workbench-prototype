"""Disposable Codex pilot for one project creation and separate access approval."""

import hashlib
import json
import time
from urllib.error import HTTPError

from attachment_pilot import await_value
from concept_map_pilot import WINDOW_SECONDS, emit
from issue_delete_pilot import ProposalCase, main
from server import Repository
from workbench.agent_management import clean_client
from workbench.agent_security import read_json
from workbench.project_prepared import prepare_project
from workbuddy_agent_acceptance import PROJECT_CREATE_PILOT_CASE, PROJECT_PILOT_TOOLS


class ProjectCreateCase(ProposalCase):
    server = 'workbench_ag142_project_create'
    tools = PROJECT_PILOT_TOOLS
    relay_flag = '--relay-project-create-pilot'
    directory_prefix = 'workbench-ag142-project-create-'
    request_prefix = 'ag142-project-create'
    client_name = 'AG142 项目创建'
    kinds = ['todo']
    project_ids = []
    case_file = PROJECT_CREATE_PILOT_CASE

    def __init__(self, repo):
        self.repo = repo
        self.store = repo.agent_service.store
        self.security = repo.agent_service.security
        self.sort_path = repo.root / 'config/project-sort.json'
        repo.save_project_sort({'mode':'custom', 'order':[]})
        fields = {'name':'AG142 合成新项目', 'description':'第一行\n第二行带引号 "甲"',
                  'status':'paused', 'color':'#4d78e8', 'workflow_template':'standard'}
        self.prepared = prepare_project(repo, fields)
        self.target = self.prepared.project_id
        self.path = repo.projects_dir / self.target
        self.request = {'request_id':'ag142-exact-project-create', 'kind':'project', 'operation':'create',
                        'confirmation_mode':'local_web', 'content':fields, 'source_note':'仅本轮合成项目创建验收'}
        self.check_original()

    def authorize(self, grant):
        return grant('project-creation', 'PROJECT_CREATE')

    def final_state(self):
        return {'project_count':len(list(self.repo.projects_dir.iterdir())),
                'receipt_count':len(list(self.store.receipts.glob('*.json')))}

    def check_original(self):
        if (self.final_state() != {'project_count':0, 'receipt_count':0}
                or self.sort_path.read_bytes() != self.prepared.sort_before):
            raise ValueError('Project directory, sorting or receipt changed before creation approval')

    def check_preview(self, proposal):
        content = proposal['normalized_content']
        metadata, readme = self.prepared.readme()
        if (content['project_id'] != self.target or content['fields'] != self.request['content']
                or content['metadata'] != metadata or content['readme'] != readme
                or content['workflow'] != self.prepared.workflow or content['directories'] != list(self.prepared.directories)
                or content['sorting']['mode'] != 'custom' or content['sorting']['position'] != '末尾'
                or not content['warnings']):
            raise ValueError('Creation preview is missing fixed project, README, template or sorting evidence')

    def check_local_preview(self, review, binding):
        order = {'mode':'custom', 'raw_before':self.prepared.sort_before.decode(),
                 'raw_after':self.prepared.sort_after.decode(), 'visible_before':[], 'visible_after':[self.target]}
        if (review['local_project_plan'] != order or review['version'] != binding['version']
                or review['preview_digest'] != binding['preview_digest']):
            raise ValueError('Local project sort preview does not match the fixed approval')

    def created(self, binding):
        key = binding['proposal_id']
        proposal = read_json(self.store.proposals / f'{key}.json')
        if proposal['state'] != 'committed':
            return None
        receipt = read_json(self.store.receipts / f'{key}.json')
        reopened = Repository(self.repo.root)
        raw = (self.path / 'README.md').read_bytes()
        _, expected = self.prepared.readme(receipt['committed_at'])
        expected_dirs = set(self.prepared.directories) | {'assets'}
        dirs = {path.relative_to(self.path).as_posix() for path in self.path.rglob('*') if path.is_dir()}
        files = {path.relative_to(self.path).as_posix() for path in self.path.rglob('*') if path.is_file()}
        if (receipt != proposal['receipt'] or receipt['item_id'] != self.target or receipt['project_id'] != self.target
                or receipt['version'] != binding['version'] or receipt['approval']['mode'] != 'local_web'
                or receipt['approval']['preview_digest'] != binding['preview_digest']
                or receipt['revision'] != hashlib.sha256(raw).hexdigest() or raw != expected.encode()
                or dirs != expected_dirs or files != {'README.md'}
                or self.final_state() != {'project_count':1, 'receipt_count':1}
                or [project['id'] for project in reopened.list_projects()] != [self.target]
                or self.sort_path.read_bytes() != self.prepared.sort_after):
            raise ValueError('Created project, published sorting or original receipt could not be verified')
        return receipt

    def without_access(self, client_id):
        client = self.security.clients()[client_id]
        if client['project_ids'] or self.visible(client):
            raise ValueError('Project became visible before the separate access approval')
        return client

    def visible(self, client):
        return [project['id'] for project in self.repo.agent_service.projects(client, {})['items']]

    def client_with_access(self, before):
        return {**before, 'project_ids':[self.target], 'management_revision':before['management_revision'] + 1}

    def check_access_preview(self, review, before, binding):
        if (review['proposal_id'] != binding['proposal_id'] or review['project_id'] != self.target
                or review['already_covered'] or review['before'] != clean_client(before)
                or review['after'] != clean_client(self.client_with_access(before))):
            raise ValueError('Access preview changes more than the fixed project scope')

    def access_applied(self, before):
        current = self.security.clients()[before['client_id']]
        if current == before:
            return None
        if current != self.client_with_access(before) or self.visible(current) != [self.target]:
            raise ValueError('Access approval changed more than the fixed project scope')
        return True

    def check(self, invoke, client_id, workspace, local):
        def call(name, args=None):
            result = invoke('workbench_' + name, args or {})
            assert not result['isError'], result
            return result['structuredContent']

        def rejected(name, args, reason):
            try:
                invoke('workbench_' + name, args)
            except RuntimeError as error:
                assert reason in str(error), error
            else:
                raise AssertionError('Project pilot forwarded a call outside the fixed scope')

        assert call('capabilities')['workspace_id'] == workspace
        assert call('list_projects')['items'] == []
        changed = {**self.request, 'content':{**self.request['content'], 'name':'另一个项目'}}
        rejected('prepare_proposal', changed, 'outside the project creation pilot scope')
        proposal = call('prepare_proposal', self.request)
        query = {'proposal_id':proposal['proposal_id']}
        preview = call('preview_proposal', query)
        binding = self.before_approval(client_id)
        assert binding and preview['preview_digest'] == binding['preview_digest'] and 'local_project_plan' not in preview
        rejected('commit_proposal', {**binding, 'confirmation':{'mode':'agent_attested','user_confirmed':True}},
                 'is disabled for MCP server')
        route = 'proposals/' + binding['proposal_id']
        review = local(route + '/preview')
        self.check_local_preview(review, binding)
        assert review['preview']['content'] == preview['content']
        approval = {'workspace_id':workspace, 'version':binding['version'], 'preview_digest':binding['preview_digest'],
                    'preview_ticket':review['preview_ticket'], 'request_id':self.request_prefix + '-approve'}
        result = local(route + '/approve', approval)
        assert result['state'] == 'completed' and local(route + '/approve', approval) == result
        receipt = self.created(binding)
        assert receipt == result['receipt']
        before = self.without_access(client_id)
        assert call('list_projects')['items'] == []
        access = route + '/project-access'
        review = local(access + '/preview')
        self.check_access_preview(review, before, binding)
        approval = {key:review[key] for key in ('workspace_id','expected_version','preview_id','preview_digest')}
        approval.update(approved=True, request_id=self.request_prefix + '-access')
        try:
            local(access + '/confirm', {**approval, 'preview_digest':'0' * 64})
        except HTTPError as error:
            with error:
                assert error.code == 409 and json.load(error)['code'] == 'preview_expired'
        else:
            raise AssertionError('Stale access confirmation was accepted')
        assert self.without_access(client_id) == before and call('list_projects')['items'] == []
        observed = call('get_proposal', query)['receipt']
        assert all(observed[key] == value for key, value in receipt.items())
        scope_receipt = local(access + '/confirm', approval)
        assert scope_receipt['project_id'] == self.target and scope_receipt['proposal_id'] == binding['proposal_id']
        assert scope_receipt['operation_id'] != receipt['approval']['operation_id']
        assert local(access + '/confirm', approval) == scope_receipt
        operation = local('operations/' + approval['request_id'])
        assert operation['state'] == 'completed' and operation['result'] == scope_receipt
        assert self.access_applied(before)
        assert [project['id'] for project in call('list_projects')['items']] == [self.target]
        assert self.created(binding) == receipt and call('get_proposal', query)['receipt'] == observed
        return {'receipt':receipt, 'access_receipt':scope_receipt, 'tool_count':len(self.tools),
                'hidden_after_creation':True, 'access_failure_preserved_original_receipt':True,
                'only_new_project_visible':True, 'approval_replay_matches':True}

    def run_window(self, client_id, workspace, stop, audit, local):
        deadline = time.monotonic() + WINDOW_SECONDS
        expires_at = int(time.time() + WINDOW_SECONDS)
        prompt = (f'只用 {self.server}。capabilities 核对空间 {workspace}，list_projects 确认项目列表为空。'
                  '使用以下固定请求调用 prepare_proposal 和 preview_proposal，展示完整项目字段、README、'
                  '既有工作流模板、全部空目录、排序规则、新项目位置、警告、版本、摘要和执行依据。'
                  '提示用户在隔离工作台提案管理查看完整排序前后，再决定是否批准创建。'
                  '展示后停止。创建批准与项目访问批准在本机分别进行。\n'
                  + json.dumps(self.request, ensure_ascii=False, indent=2))
        emit({'mode':'ready_preview', 'prompt':prompt, 'execution_expires_at':expires_at})
        binding = await_value(lambda: self.before_approval(client_id), stop, deadline)
        if not binding:
            return
        route = 'proposals/' + binding['proposal_id']
        self.check_local_preview(local(route + '/preview'), binding)
        emit({'mode':'await_web_approval', **binding, **self.final_state(), 'execution_expires_at':expires_at})
        receipt = await_value(lambda: self.created(binding), stop, deadline)
        if not receipt:
            return
        before = self.without_access(client_id)
        self.check_access_preview(local(route + '/project-access/preview'), before, binding)
        audit.update(receipt=receipt, hidden_after_creation=True)
        emit({'mode':'await_project_access_approval', **audit, 'project_id':self.target,
              'execution_expires_at':expires_at})
        if await_value(lambda: self.access_applied(before), stop, deadline):
            if self.created(binding) != receipt:
                raise ValueError('Original receipt changed after access approval')
            audit['only_new_project_visible'] = True
            emit({'mode':'access_granted', **audit})
            await_value(lambda: None, stop, deadline)


if __name__ == '__main__':
    main(ProjectCreateCase, __doc__)
