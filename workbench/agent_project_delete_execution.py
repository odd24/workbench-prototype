"""Static project_trash@1 evidence and steps within the existing proposal store."""

import json
import re

from .agent_execution import fingerprint
from .deletion_prepared import controlled, read_trash_index
from .persistence import atomic_write_json
from .project_delete_tree import move_tree, project_metadata, read_tree
from .project_identity import valid_new_id
from .write_coordinator import content_revision


HANDLER = 'project_trash@1'


def validate_context(proposal):
    from .agent_delete_execution import logical_plan
    target_id = proposal['target_id']
    valid_new_id(target_id)
    target = {'type':'project', 'id':target_id, 'project_id':target_id, 'category':None}
    if proposal['operation'] != 'delete' or proposal['kind'] != 'project' or proposal['confirmation_mode'] != 'local_web' or proposal['access_target'] != target:
        raise ValueError('项目级联删除目标或确认无效')
    binding = proposal['delete_binding']
    if set(binding) != {'schema_version', 'relative_path', 'source_identity', 'source_digest', 'tree_digest', 'portable_digest', 'child_ids', 'sorting', 'trash_index_digest'} or type(binding['schema_version']) is not int or binding['schema_version'] != 2 or binding['relative_path'] != f'projects/{target_id}':
        raise ValueError('项目级联来源绑定无效')
    identity = binding['source_identity']
    if set(identity) != {'volume', 'index', 'created'} or any(type(value) is not int or value < 0 for value in identity.values()):
        raise ValueError('项目根目录物理身份无效')
    sha = re.compile(r'[0-9a-f]{64}')
    if any(not sha.fullmatch(binding[key]) for key in ('source_digest', 'tree_digest', 'portable_digest', 'trash_index_digest')) or binding['source_digest'] != proposal['base_revision']:
        raise ValueError('项目级联证据摘要无效')
    ids = binding['child_ids']
    if not isinstance(ids, list) or len(ids) > 4096 or ids != sorted(set(ids)) or any(not re.fullmatch(r'(?:ISSUE|TODO|INFO)-[0-9]+', item) for item in ids):
        raise ValueError('项目子资源身份集合无效')
    sorting = binding['sorting']
    if set(sorting) != {'relative_path', 'policy', 'revision'} or sorting['relative_path'] != 'config/project-sort.json' or sorting['policy'] != 'preserve' or sorting['revision'] is not None and not sha.fullmatch(sorting['revision']):
        raise ValueError('项目排序证据无效')
    deps = proposal['dependencies']
    if deps != {'schema_version':1, 'activity_digest':deps['activity_digest'], 'tree_digest':binding['tree_digest'], 'sorting_revision':sorting['revision'], 'trash_index_digest':binding['trash_index_digest']} or type(deps['schema_version']) is not int or not sha.fullmatch(deps['activity_digest']):
        raise ValueError('项目影响依赖证据无效')
    if not proposal.get('content_cleaned'):
        from .agent_project_delete_service import WARNINGS
        content = proposal['normalized_content']
        if set(content) != {'title', 'project_id', 'category', 'target', 'children', 'standalone_assets', 'tree', 'impacts', 'warnings', 'retention'}:
            raise ValueError('项目级联预览字段不完整')
        source = content['target']
        raw = source['raw_source'].encode('utf-8')
        item = project_metadata(raw, target_id)
        if content_revision(raw) != binding['source_digest'] or source != {'item':item, 'raw_source':source['raw_source'], 'revision':proposal['base_revision']} or content['project_id'] != target_id or content['category'] is not None or content['title'] != item['title'] or content['warnings'] != WARNINGS or content['retention'] != {'default_days':30, 'local_early_purge':True, 'attachments':'move_owned', 'history':'retain', 'ordering':'preserve'}:
            raise ValueError('项目预览与原始身份或保留规则不一致')
        if fingerprint(content['tree']) != binding['portable_digest'] or sorted(child['item']['id'] for child in content['children']) != ids:
            raise ValueError('项目预览目录或子资源证据不一致')
    if proposal['execution_plan'] != logical_plan(proposal) or proposal['plan_digest'] != fingerprint(proposal['execution_plan']):
        raise ValueError('项目级联删除逻辑计划不一致')


def validate_snapshots(store, manifest, proposal):
    directory = store.operations / manifest['operation_id']
    root = store.repository.root
    binding = proposal['delete_binding']
    tree_path = controlled(root, (directory / 'tree-before.json').relative_to(root).as_posix())
    with tree_path.open('rb') as stream:
        raw = stream.read(2 * 1048576 + 1)
    if len(raw) > 2 * 1048576:
        raise ValueError('项目树快照超出核验上限')
    from .project_identity import load_unique_json
    tree = load_unique_json(raw)
    if set(tree) != {'identity', 'members'} or tree['identity'] != binding['source_identity'] or fingerprint([tree['identity'], tree['members']]) != binding['tree_digest']:
        raise ValueError('项目树快照与持久计划不一致')
    from .project_delete_tree import ProjectTree
    if ProjectTree(tree['identity'], tree['members'], {}).portable_digest != binding['portable_digest']:
        raise ValueError('项目树可移植快照不一致')
    sort_path = controlled(root, (directory / 'sort-before.json').relative_to(root).as_posix(), required=False)
    from .project_identity import read_bounded
    sort_revision = content_revision(read_bounded(sort_path)) if sort_path.exists() else None
    if sort_revision != binding['sorting']['revision']:
        raise ValueError('项目排序原始快照不一致')


def apply_steps(store, manifest, proposal):
    from .agent_delete_execution import index_entry
    root = store.repository.root
    directory = store.operations / manifest['operation_id']
    path = directory / 'manifest.json'
    source = controlled(root, manifest['relative_path'], required=False)
    destination = controlled(root, '.trash/' + manifest['trash_token'], required=False)
    binding = proposal['delete_binding']
    if manifest['state'] == 'prepared':
        if destination.exists():
            raise ValueError('项目回收目标在移动前已存在')
        store._current_authorization(proposal)
        manifest.update(state='applying', step_states=['applying', 'pending', 'pending', 'pending'])
        atomic_write_json(path, manifest)
        store.checkpoint('delete_move_applying')
        move_tree(root, source, destination, binding['tree_digest'],
                  lambda tree:store._current_authorization(proposal, held_source=tree),
                  before_rename=lambda:store.checkpoint('delete_before_rename'), moved=lambda:store.checkpoint('delete_move'))
    elif not destination.exists():
        raise ValueError('移动中但缺少原回收项目，不再移动可能已恢复的来源')
    elif read_tree(root, destination, keep_text=False).physical_digest != binding['tree_digest']:
        raise ValueError('回收目录与原始项目树证据不一致')

    manifest.update(state='applying', step_states=['completed', 'applying', 'pending', 'pending'])
    atomic_write_json(path, manifest)
    store.checkpoint('delete_move_logged')
    raw, index = read_trash_index(root)
    original = json.loads((directory / 'index-before.json').read_bytes().decode('utf-8'))
    expected = {**original, manifest['trash_token']:index_entry(store, manifest)}
    if content_revision(raw) == binding['trash_index_digest']:
        store.repository._write_trash_index(expected)
    elif index != expected:
        raise ValueError('回收索引与原始或已应用计划不一致')
    store.checkpoint('delete_index')
    manifest['step_states'] = ['completed', 'completed', 'applying', 'pending']
    atomic_write_json(path, manifest)
    store.checkpoint('delete_index_logged')
    for child in proposal['normalized_content']['children']:
        store.repository._forget_record(source / child['relative_path'])
    store.checkpoint('delete_cache')
    manifest['step_states'] = ['completed', 'completed', 'completed', 'applying']
    atomic_write_json(path, manifest)
    store.checkpoint('delete_cache_logged')


def validated_project_trash(repository, item):
    from .agent_delete_execution import index_entry, token
    from .agent_security import AgentError, read_json
    try:
        root = repository.root
        store = repository.agent_proposals
        operation_id = item['agent_operation_id']
        if not re.fullmatch(r'[a-f0-9-]{36}-[1-9][0-9]*', operation_id):
            raise ValueError('项目回收操作身份无效')
        path = controlled(root, (store.operations / operation_id / 'manifest.json').relative_to(root).as_posix())
        manifest = read_json(path)
        proposal = store._load(manifest['proposal_id'], expire=False)
        store._validate_execution(manifest, proposal)
        if manifest['kind'] != 'project' or manifest['operation'] != 'delete' or manifest['state'] != 'committed' or manifest['workspace_id'] != store.workspace_id or manifest['operation_id'] != operation_id or token(proposal) != 'project-agent-' + operation_id or item != index_entry(store, manifest):
            raise ValueError('项目回收项与原索引不一致')
        receipt_path = controlled(root, (store.receipts / (proposal['proposal_id'] + '.json')).relative_to(root).as_posix())
        if proposal.get('receipt') != manifest['receipt'] or read_json(receipt_path) != manifest['receipt']:
            raise ValueError('项目缺少原提交回执')
        store._verify_approval(manifest, proposal, check_authorization=False)
        source = controlled(root, item['trash_path'], required=False)
        destination = controlled(root, manifest['relative_path'], required=False)
        tree = read_tree(root, source, keep_text=False)
        binding = proposal['delete_binding']
        if tree.portable_digest != binding['portable_digest']:
            raise ValueError('项目回收树内容已变化')
        return source, destination, tree.physical_digest, frozenset(binding['child_ids'])
    except (AgentError, ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        raise AgentError('recovery_required', '回收项目与原提交或完整树证据不一致，保留现场', 503) from error


def verify_restore_destination(repository, planned):
    from .write_coordinator import RevisionConflict
    _, destination, _, child_ids = planned
    if destination.exists():
        raise RevisionConflict('原项目身份已存在，不能改名恢复或覆盖')
    if child_ids and any(record['id'] in child_ids for record in repository.list_records()):
        raise RevisionConflict('正式空间存在同一子记录身份，不能恢复原项目')


def recovery_evidence(store, manifest, proposal):
    from .agent_security import AgentError
    root = store.repository.root
    binding = proposal['delete_binding']
    evidence = {'operation_id':manifest['operation_id'], 'kind':'project', 'operation':'delete',
                'state':manifest['state'], 'steps':manifest['step_states'], 'trash_token':manifest['trash_token'],
                'tree_digest':binding['tree_digest']}
    for key, relative in [('source', manifest['relative_path']), ('trash', '.trash/' + manifest['trash_token'])]:
        try:
            path = controlled(root, relative, required=False)
            if not path.exists():
                evidence[key] = 'absent'
            else:
                evidence[key] = 'original' if read_tree(root, path, keep_text=False).physical_digest == binding['tree_digest'] else 'changed'
        except (OSError, ValueError, AgentError):
            evidence[key] = 'unverified'
    return evidence
