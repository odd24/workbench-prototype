"""Disposable Codex pilot for one synthetic project cascade. No model is started."""

import hashlib
import io
from urllib.parse import quote

from issue_delete_pilot import DeletionCase, main
from server import Repository
from workbench.agent_project_delete_service import project_delete_configuration
from workbench.agent_security import read_json
from workbench.project_delete_tree import classify_tree, read_tree
from workbuddy_agent_acceptance import PROJECT_PILOT_TOOLS


ASSET = b'AG142 SYNTHETIC PROJECT ASSET\n'


class ProjectDeleteCase(DeletionCase):
    server = 'workbench_ag142_project_delete'
    tools = PROJECT_PILOT_TOOLS
    relay_flag = '--relay-project-delete-pilot'
    directory_prefix = 'workbench-ag142-project-delete-'
    request_prefix = 'ag142-project-delete'
    client_name = 'AG142 项目级联删除'
    kinds = ['todo']

    def __init__(self, repo):
        self.repo = repo
        self.project = self.target = repo.create_project({'name':'AG142 合成级联项目',
                                                          'description':'项目原文仅供隔离预演。'})['id']
        self.child = repo.create_record({'type':'todo', 'project_id':self.project, 'title':'AG142 合成子记录',
                                         'body':'第一段\n\n保留空格与引号 "甲"  \n第二段'})['id']
        self.asset = repo.add_project_asset_stream(self.project, 'ag142-cascade.txt', io.BytesIO(ASSET), len(ASSET))['id']
        graph = repo.create_concept_map({'title':'AG142 保留关联图', 'project_id':self.project})
        self.graph = graph['id']
        self.graph_path = repo.get_concept_map(self.graph)[1]
        self.graph_raw = self.graph_path.read_bytes()
        self.path = repo.projects_dir / self.project
        self.tree = read_tree(repo.root, self.path)
        self.project_view, self.children, self.assets, _ = classify_tree(repo.root, self.project, self.tree)
        [child] = self.children
        [asset] = self.assets
        if (child['item']['id'] != self.child or asset['id'] != self.asset
                or asset['sha256'] != hashlib.sha256(ASSET).hexdigest()):
            raise ValueError('Synthetic project tree does not match the fixed fixture')
        self.revision = hashlib.sha256(self.tree.raw_text['README.md']).hexdigest()
        self.sort_raw = project_delete_configuration(repo.root)[1]
        self.store = repo.agent_service.store
        self.request = {'request_id':'ag142-exact-project-delete', 'kind':'project', 'operation':'delete',
                        'target_id':self.target, 'base_revision':self.revision, 'confirmation_mode':'local_web',
                        'source_note':'仅本轮合成项目级联删除验收'}

    def authorize(self, grant):
        return (grant('concept-maps', 'GRAPH_READ', grants={'schema_version':1, 'grants':[
            {'capability':'concept_maps.read', 'operations':['read'], 'minimum_confirmation_mode':'agent_attested',
             'resources':[{'type':'concept_map', 'id':self.graph}]}]})
            and grant('deletions', 'CHILD_DELETE', grants={'schema_version':1, 'grants':[
                {'capability':'items.delete', 'operations':['delete'], 'minimum_confirmation_mode':'local_web',
                 'resources':[{'type':'item', 'kind':'todo', 'id':self.child}]}]})
            and grant('project-deletions', 'PROJECT_DELETE', project_id=self.project, asset_ids=[self.asset]))

    def check_tool_access(self, call, rejected, invoke):
        [project] = call('list_projects')['items']
        assert project['id'] == self.target and project['revision'] == self.revision
        rejected('prepare_proposal', {**self.request, 'target_id':'ag142-unapproved-project'},
                 'outside the project deletion pilot scope')
        rejected('get_item', {'kind':'todo', 'item_id':self.child})
        document = self.repo.create_document({
            'title':'AG142 项目外合成引用',
            'body':f'[附件](/api/project-assets/{quote(self.project, safe="")}/{self.asset})',
        })
        result = invoke('workbench_prepare_proposal', self.request)
        assert result['isError'] and result['structuredContent']['code'] == 'impact_unavailable', result
        self.check_original()
        assert not list(self.store.proposals.glob('*.json'))
        self.repo.update_document(document['id'], {'body':'AG142 合成引用已移除。'})
        return {'external_attachment_reference_denied':True}

    def check_retained(self):
        if (self.graph_path.read_bytes() != self.graph_raw
                or project_delete_configuration(self.repo.root)[1] != self.sort_raw):
            raise ValueError('Associated graph or project sorting changed')

    def check_original(self):
        if (read_tree(self.repo.root, self.path).physical_digest != self.tree.physical_digest
                or self.repo.list_trash() or list(self.store.receipts.glob('*.json'))):
            raise ValueError('Original tree, trash or receipt changed before approval')
        self.check_retained()

    def check_preview(self, proposal):
        content = proposal['normalized_content']
        [impact] = content['impacts']
        graph = impact['source']
        binding = proposal['delete_binding']
        retention = {'default_days':30, 'local_early_purge':True, 'attachments':'move_owned',
                     'history':'retain', 'ordering':'preserve'}
        if (content['target'] != {'item':self.project_view, 'revision':self.revision,
                                  'raw_source':self.tree.raw_text['README.md'].decode()}
                or content['children'] != self.children or content['standalone_assets'] != self.assets
                or content['tree'] != self.tree.portable_members
                or not impact['associated_graph'] or graph['item']['id'] != self.graph
                or graph['graph']['project_id'] != self.project or graph['raw_source'].encode() != self.graph_raw
                or not content['warnings'] or content['retention'] != retention
                or binding['sorting']['policy'] != 'preserve'
                or binding['child_ids'] != [self.child] or binding['portable_digest'] != self.tree.portable_digest):
            raise ValueError('Project cascade preview is missing fixed source, impact or execution evidence')

    def after_approval(self, binding):
        key = binding['proposal_id']
        proposal = read_json(self.store.proposals / f'{key}.json')
        if proposal['state'] != 'committed':
            return None
        receipt = read_json(self.store.receipts / f'{key}.json')
        token = receipt['trash_token']
        reopened = Repository(self.repo.root)
        index = reopened._trash_index()
        if (receipt != proposal['receipt'] or proposal['preview_digest'] != binding['preview_digest']
                or receipt['version'] != binding['version'] or receipt['revision'] != self.revision
                or not receipt['deleted'] or receipt['item_id'] != self.target or self.path.exists()
                or not token.startswith('project-agent-') or set(index) != {token}
                or index[token]['delete_schema_version'] != 2
                or index[token]['agent_operation_id'] != f'{key}-{binding["version"]}'
                or index[token]['original_relative_path'] != f'projects/{self.project}'
                or self.child not in reopened.reserved_resource_ids()
                or len(list(self.store.receipts.glob('*.json'))) != 1):
            raise ValueError('Project cascade trash index or receipt failed verification')
        archived = read_tree(reopened.root, reopened.trash_dir / token)
        if archived.physical_digest != self.tree.physical_digest:
            raise ValueError('Trash does not contain the original project tree and bytes')
        self.check_retained()
        return {'receipt':receipt, 'trash_tree_digest':archived.portable_digest,
                'retained_graph_sha256':hashlib.sha256(self.graph_raw).hexdigest(), 'retained_bytes_match':True}

    def prompt(self, workspace):
        return (f'只用 {self.server}。capabilities 核对空间 {workspace}。调用 list_projects，'
                '确认唯一项目 ID 与 revision 匹配以下固定请求后才调用 prepare_proposal。'
                '调用 preview_proposal，完整展示项目及所有子记录的原文、全部目录和附件、活动影响、'
                '保留关联图的完整内容和原归属、排序与历史保留、回收期限、警告、提案 ID、版本、摘要和执行依据。'
                '随后停止，等待用户在隔离网页独立批准。禁止自行提交、恢复或永久删除。'
                '授权、引用或版本异常时报告并停止。')


if __name__ == '__main__':
    main(ProjectDeleteCase, __doc__)
