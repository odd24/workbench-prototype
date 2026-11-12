"""Disposable Codex pilot for one exact category rename in a selected domain."""

import argparse
import io
import json
import time
import uuid
from pathlib import Path

from attachment_pilot import await_value
from concept_map_pilot import WINDOW_SECONDS, emit
from issue_delete_pilot import ProposalCase, check_local_approval, run
from server import Repository
from workbench.agent_category_authorization import client_grants, prepared_revision
from workbench.agent_security import AgentError, read_json
from workbench.category_identity import FENCE_PATH, IDENTITY_PATH, load_category_identities, namespace_key
from workbench.category_prepared import DOCUMENT, GRAPH, PROJECT_ASSETS, category_inventory, prepare_category, read_file
from workbench.markdown_io import now_iso
from workbuddy_agent_acceptance import CATEGORY_PILOT_CASE, CATEGORY_PILOT_TOOLS


DOMAINS = {'document':DOCUMENT, 'concept-map':GRAPH, 'project-attachment':PROJECT_ASSETS}
SOURCE = 'AG142 原分类'
DESTINATION = 'AG142 新分类'
NEIGHBOR = 'AG142 空分类'
BINARY = b'AG142 SYNTHETIC ATTACHMENT\n'


class CategoryCase(ProposalCase):
    server = 'workbench_ag142_category'
    tools = CATEGORY_PILOT_TOOLS
    relay_flag = '--relay-category-pilot'
    directory_prefix = 'workbench-ag142-category-'
    request_prefix = 'ag142-category'
    client_name = 'AG142 分类改名'
    case_file = CATEGORY_PILOT_CASE
    target = None

    def __init__(self, repo, family):
        self.repo = repo
        self.security = repo.agent_service.security
        self.store = repo.agent_service.store
        self.family = family
        project = repo.create_project({'name':'AG142 分类验收项目'})['id']
        document = repo.create_document({'title':'AG142 原文档', 'category':SOURCE, 'body':'原文档完整正文\n\n第二段'})
        repo.ensure_document_category(NEIGHBOR)
        repo.save_document_sort({'category_mode':'manual', 'category_order':[NEIGHBOR, SOURCE],
                                 'file_modes':{SOURCE:'manual'}, 'file_orders':{SOURCE:[document['id']]}})
        graph = repo.create_concept_map({'title':'AG142 原图', 'category':SOURCE, 'nodes':[{'id':'n1','text':'原节点'}]})
        repo.ensure_concept_map_category(NEIGHBOR)
        repo.save_project_asset_categories(project, [{'name':NEIGHBOR,'tag':'空类标签'}, {'name':SOURCE,'tag':'原标签'}])
        asset = repo.add_project_asset_stream(project, 'ag142-category.txt', io.BytesIO(BINARY), len(BINARY), category=SOURCE)
        record = repo.create_record({'type':'issue', 'title':'AG142 记录附件对照', 'project_id':project})
        repo.add_record_attachment_stream(record['id'], 'ag142-record.txt', io.BytesIO(BINARY), len(BINARY), append_to_body=False)
        repo.update_record_attachment_category(record['id'], 'ag142-record.txt', SOURCE)

        self.members = {DOCUMENT:document['id'], GRAPH:graph['id'], PROJECT_ASSETS:asset['id']}
        self.owners = {DOCUMENT:None, GRAPH:None, PROJECT_ASSETS:project}
        self.project_ids = [project] if family == PROJECT_ASSETS else []
        self.client_categories = [SOURCE] if family == DOCUMENT else []
        self.kinds = ['document'] if family == DOCUMENT else ['issue']
        self.selection = self.selection_for(family)
        self.request = {'request_id':'ag142-exact-category-rename', 'kind':'category', 'operation':'rename',
                        'confirmation_mode':'local_web', 'content':self.selection, 'source_note':'仅本轮合成分类改名验收'}
        epoch = str(uuid.uuid5(uuid.NAMESPACE_URL, self.security.workspace_id))
        self.prepared = self.plan(epoch, now_iso())
        self.original_revision = prepared_revision(self.prepared)
        self.domain_snapshots = {domain:self.snapshot(domain) for domain in DOMAINS.values()}
        self.retained = {path:path.read_bytes() for path in (
            repo.get_record(record['id'])[1], repo.attachment_path(record['id'], 'ag142-record.txt'),
            repo.project_asset_path(project, asset['id']),
        )}
        self.identity_bytes = {path:read_file(repo.root, path) for path in (FENCE_PATH, IDENTITY_PATH)}
        self.client_id = None
        self.check_original()

    def selection_for(self, family):
        selection = {'family':family, 'name':SOURCE, 'new_name':DESTINATION}
        if self.owners[family]:
            selection['project_id'] = self.owners[family]
        return selection

    def plan(self, epoch, managed_time):
        return prepare_category(self.repo, operation='rename', **self.selection, epoch=epoch, managed_time=managed_time)

    def snapshot(self, family):
        owner = self.owners[family]
        config, _, _, watch = category_inventory(self.repo, family, owner)
        names = [entry['name'] if family == PROJECT_ASSETS else entry for entry in config]
        scope = load_category_identities(self.repo.root).scope(namespace_key(family, owner), names)
        files = dict(watch)
        if family == DOCUMENT:
            files['config/document-sort.json'] = read_file(self.repo.root, 'config/document-sort.json')
        return files, scope

    def authorize(self, grant):
        if self.family == GRAPH:
            read = {'capability':'concept_maps.read', 'operations':['read'], 'minimum_confirmation_mode':'agent_attested',
                    'resources':[{'type':'concept_map','id':self.members[GRAPH]}]}
            if not grant('concept-maps', 'GRAPH_READ', grants={'schema_version':1, 'grants':[read]}):
                return False
        selection = {'family':self.family, 'project_id':self.owners[self.family], 'name':SOURCE, 'operation':'rename'}
        if not grant('category-writes', 'CATEGORY_RENAME', selection=selection):
            return False
        if self.family == PROJECT_ASSETS:
            return grant('upload-policy', 'ATTACHMENT_VISIBILITY', owner_kind='project', owner_id=self.owners[self.family],
                         stream=True, files=[], max_bytes=1, duration_seconds=3600, attachment_write=True,
                         minimum_confirmation_mode='local_web')
        return True

    def binding_revision(self):
        return self.original_revision

    def final_state(self):
        return {'family':self.family, 'receipt_count':len(list(self.store.receipts.glob('*.json')))}

    def check_retained(self):
        if any(path.read_bytes() != raw for path, raw in self.retained.items()):
            raise ValueError('Attachment bytes or record attachment metadata changed')

    def check_original(self):
        if (any(self.snapshot(family) != snapshot for family, snapshot in self.domain_snapshots.items())
                or any(read_file(self.repo.root, path) != raw for path, raw in self.identity_bytes.items())
                or self.final_state()['receipt_count']):
            raise ValueError('Category files or receipt changed before approval')
        self.check_retained()

    def check_grant(self, grants, name):
        [grant] = grants['grants']
        expected = {'family':self.family, 'project_id':self.owners[self.family], 'name':name, 'operation':'rename',
                    'capability':'categories.write', 'minimum_confirmation_mode':'local_web',
                    'identity':self.prepared.scope['active'][SOURCE]}
        if any(grant.get(key) != value for key, value in expected.items()):
            raise ValueError('Category grant is outside the exact fixed scope')

    def check_preview(self, proposal):
        content = proposal['normalized_content']
        self.client_id = proposal['client_id']
        self.check_grant(client_grants(self.security.clients()[self.client_id]), SOURCE)
        self.prepared = self.plan(content['epoch'], content['managed_time'])
        [member] = self.prepared.members
        if (content['selection'] != self.selection or content['operation'] != 'rename'
                or content['members'] != [member] or member['id'] != self.members[self.family]
                or member['before']['category'] != SOURCE or member['after']['category'] != DESTINATION
                or not content['warnings']):
            raise ValueError('Category preview omitted the exact original member or migration')

    def check_local_preview(self, review, binding):
        super().check_local_preview(review, binding)
        local = review['local_category_plan']
        [migration] = local['authorization']
        before = self.prepared.config_before
        after = ([{**entry, 'name':DESTINATION} if entry['name'] == SOURCE else entry for entry in before]
                 if self.family == PROJECT_ASSETS else [DESTINATION if name == SOURCE else name for name in before])
        if (local['configuration'] != {'before':self.prepared.config_before, 'after':self.prepared.config_after}
                or local['configuration']['after'] != after
                or local['ordering'] != {'before':self.prepared.sort_before, 'after':self.prepared.sort_after}
                or migration['client_id'] != self.client_id
                or migration['narrow']['category_write_grants']['grants']):
            raise ValueError('Local category preview omitted complete configuration, sorting or authorization changes')
        if self.family == DOCUMENT:
            sorting = local['ordering']['after']
            if (sorting['category_order'][:2] != [NEIGHBOR, DESTINATION]
                    or sorting['file_modes'][DESTINATION] != 'manual'
                    or sorting['file_orders'][DESTINATION] != [self.members[DOCUMENT]]
                    or migration['before']['categories'] != [SOURCE] or migration['narrow']['categories']
                    or migration['after']['categories'] != [DESTINATION]):
                raise ValueError('Document category order, member order or exact read scope did not migrate')
        self.check_grant(migration['before']['category_write_grants'], SOURCE)
        self.check_grant(migration['after']['category_write_grants'], DESTINATION)

    def check_tool_access(self, call, rejected, invoke):
        client = next(iter(self.security.clients().values()))
        self.check_grant(client_grants(client), SOURCE)
        alternatives = [{**self.request, 'content':self.selection_for(family)}
                        for family in DOMAINS.values() if family != self.family]
        alternatives.append({**self.request, 'operation':'delete', 'content':{
            key:value for key,value in self.selection.items() if key != 'new_name'}})
        for proposal in alternatives:
            rejected('prepare_proposal', proposal, 'outside the category pilot scope')
            try:
                self.repo.agent_service.prepare_proposal(client, proposal)
            except AgentError as error:
                assert error.code == 'category_unavailable', error
            else:
                raise AssertionError('Service accepted an unapproved category domain or operation')
        self.check_original()
        assert not list(self.store.proposals.glob('*.json'))
        return {'cross_domain_denied':True, 'other_operation_denied':True}

    def check(self, invoke, client_id, workspace, local):
        return check_local_approval(invoke, self, client_id, workspace, local)

    def after_approval(self, binding):
        key = binding['proposal_id']
        proposal = read_json(self.store.proposals / f'{key}.json')
        if proposal['state'] != 'committed':
            return None
        receipt = read_json(self.store.receipts / f'{key}.json')
        reopened = Repository(self.repo.root)
        _, _, members, _ = category_inventory(reopened, self.family, self.owners[self.family])
        [member] = members
        if (receipt != proposal['receipt'] or receipt['family'] != self.family or receipt['name'] != SOURCE
                or receipt['project_id'] != self.owners[self.family] or receipt['operation'] != 'rename'
                or receipt['version'] != binding['version'] or receipt['approval']['mode'] != 'local_web'
                or receipt['approval']['preview_digest'] != binding['preview_digest']
                or self.final_state()['receipt_count'] != 1 or member['item'] != self.prepared.members[0]['after']
                or any(read_file(reopened.root, file.path) != file.after for file in self.prepared.files)
                or any(self.snapshot(family) != snapshot for family, snapshot in self.domain_snapshots.items()
                       if family != self.family)):
            raise ValueError('Category receipt, original-domain persistence or other-domain evidence did not match')
        self.check_grant(client_grants(self.security.clients()[self.client_id]), DESTINATION)
        self.check_retained()
        return {'receipt':receipt, 'other_domains_unchanged':True, 'attachment_bytes_unchanged':True}

    def run_window(self, client_id, workspace, stop, audit, local):
        deadline = time.monotonic() + WINDOW_SECONDS
        expires_at = int(time.time() + WINDOW_SECONDS)
        prompt = (f'只用 {self.server}。capabilities 核对空间 {workspace}。用以下固定请求调用 prepare_proposal '
                  '与 preview_proposal。展示精确分类域与项目、全部影响成员改名前后原内容、警告、版本、摘要和执行依据。'
                  '请用户在隔离工作台核对本机预览中的完整目录顺序、文件排序和授权迁移，再独立批准。展示后停止。\n'
                  + json.dumps(self.request, ensure_ascii=False, indent=2))
        emit({'mode':'ready_preview', 'prompt':prompt, 'family':self.family, 'execution_expires_at':expires_at})
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', required=True, choices=DOMAINS)
    parser.add_argument('--check', action='store_true', help='Run the isolated App Server preflight without a model')
    parser.add_argument('--anchor', type=Path, help='Use an initialized Codex pilot directory')
    args = parser.parse_args()
    family = DOMAINS[args.domain]
    run(args.check, args.anchor, CategoryCase, family=family)
