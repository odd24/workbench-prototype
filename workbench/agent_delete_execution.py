"""Static trash_delete@1 contracts and domain steps for the single ProposalStore."""

import json
import re
from datetime import datetime
from pathlib import Path

from .agent_execution import fingerprint
from .agent_security import AgentError
from .deletion_prepared import PreparedDelete, DELETE_KINDS, deletion_token, source_metadata, controlled
from .security import validate_archive_member
from .write_coordinator import content_revision


STEPS = ['trash_move', 'trash_index', 'preserve_sort_and_cache', 'receipt']


def token(proposal):
    return deletion_token(proposal['kind'], proposal['proposal_id'], proposal['version'])


def logical_plan(proposal):
    content = proposal.get('normalized_content')
    return {'handler':'trash_delete@1', 'kind':proposal['kind'], 'operation':'delete',
            'target':proposal['access_target'], 'trash_token':token(proposal),
            'candidate_digest':fingerprint(content) if content is not None else proposal['execution_plan']['candidate_digest'],
            'binding_digest':fingerprint(proposal['delete_binding']), 'steps':STEPS.copy(), 'source_bindings':[]}


def validate_context(proposal):
    if proposal['operation'] != 'delete' or proposal['kind'] not in DELETE_KINDS or proposal['confirmation_mode'] != 'local_web':
        raise ValueError('删除仅支持固定类型与本机网页批准')
    target = proposal.get('access_target')
    if not isinstance(target, dict) or set(target) != {'type', 'id', 'project_id', 'category'} or target['type'] != proposal['kind'] or target['id'] != proposal['target_id'] or not isinstance(target['id'], str) or not re.fullmatch(r'(?:ISSUE|TODO|INFO|DOC|CMAP)-[0-9]+', target['id']):
        raise ValueError('删除目标身份无效')
    binding = proposal.get('delete_binding')
    if not isinstance(binding, dict) or set(binding) != {'schema_version', 'relative_path', 'source_identity', 'source_digest', 'sorting', 'trash_index_digest'} or type(binding['schema_version']) is not int or binding['schema_version'] != 1:
        raise ValueError('删除来源绑定无效')
    relative = validate_archive_member(binding['relative_path'])
    parts = Path(relative).parts
    kind = proposal['kind']
    valid = (len(parts) == 2 and parts[0] == 'documents' and Path(relative).suffix == '.md') if kind == 'document' else relative == f"concept-maps/{target['id']}.json" if kind == 'concept_map' else len(parts) == 4 and parts[0] == 'projects' and parts[1] == target['project_id'] and parts[2] == kind + 's' and Path(relative).suffix == '.md'
    if not valid:
        raise ValueError('删除固定来源不在目标领域目录')
    identity = binding['source_identity']
    if not isinstance(identity, dict) or set(identity) != {'volume', 'index', 'created'} or any(type(x) is not int or x < 0 for x in identity.values()):
        raise ValueError('删除对象身份不完整')
    if not isinstance(proposal.get('base_revision'), str) or not re.fullmatch(r'[a-f0-9]{64}', proposal['base_revision']) or binding['source_digest'] != proposal['base_revision']:
        raise ValueError('删除原始版本不一致')
    sorting = binding['sorting']
    expected_sort = 'config/document-sort.json' if kind == 'document' else f"projects/{target['project_id']}/README.md" if kind in {'issue', 'todo', 'info'} else None
    if not isinstance(sorting, dict) or set(sorting) != {'relative_path', 'revision', 'exists', 'policy'} or sorting['relative_path'] != expected_sort or type(sorting['exists']) is not bool or sorting['policy'] != 'preserve' or (not sorting['exists'] and sorting['revision'] is not None) or sorting['exists'] and (not isinstance(sorting['revision'], str) or not re.fullmatch(r'[a-f0-9]{64}', sorting['revision'])):
        raise ValueError('删除排序保留计划无效')
    deps = proposal['dependencies']
    if not isinstance(deps, dict) or set(deps) != {'schema_version', 'activity_digest', 'sorting_digest', 'trash_index_digest'} or type(deps['schema_version']) is not int or deps['schema_version'] != 1 or not isinstance(deps['activity_digest'], str) or not re.fullmatch(r'[a-f0-9]{64}', deps['activity_digest']) or deps['sorting_digest'] != fingerprint(sorting) or deps['trash_index_digest'] != binding['trash_index_digest'] or not isinstance(binding['trash_index_digest'], str) or not re.fullmatch(r'[a-f0-9]{64}', binding['trash_index_digest']):
        raise ValueError('删除完整集合依赖无效')
    if not proposal.get('content_cleaned'):
        content = proposal['normalized_content']
        if set(content) != {'title', 'project_id', 'category', 'target', 'impacts', 'warnings', 'retention'} or not isinstance(content['impacts'], list) or not isinstance(content['warnings'], list) or any(not isinstance(warning, str) for warning in content['warnings']):
            raise ValueError('删除完整影响格式无效')
        source = content['target']
        raw = source['raw_source'].encode('utf-8')
        item = source_metadata(raw, target['id'], kind)
        if kind == 'concept_map':
            item = {**item, 'type':'concept_map'}
        if source['item'] != item or content['title'] != item.get('title', target['id']) or source['revision'] != proposal['base_revision'] or content_revision(raw) != binding['source_digest']:
            raise ValueError('删除全文/身份与绑定版本不一致')
        from .agent_delete_service import access_target, WARNINGS
        if access_target(kind, item) != target or content['project_id'] != target['project_id'] or content['category'] != target['category'] or content['warnings'] != WARNINGS or content['retention'] != {'default_days':30, 'local_early_purge':True, 'attachments':'retain', 'history':'retain', 'ordering':'preserve'}:
            raise ValueError('删除影响或保留规则与固定目标不一致')
    if proposal.get('execution_plan') != logical_plan(proposal) or proposal.get('plan_digest') != fingerprint(proposal['execution_plan']):
        raise ValueError('删除逻辑执行计划不一致')


def concrete_plan(manifest, proposal):
    return {'handler':'trash_delete@1', 'proposal_plan_digest':proposal['plan_digest'], 'steps':STEPS.copy(),
            **{key:manifest[key] for key in ('kind', 'operation', 'item_id', 'relative_path', 'before_digest', 'trash_token', 'deleted_at')},
            'binding_digest':fingerprint(proposal['delete_binding'])}


def validate_execution(store, manifest, proposal, snapshots):
    validate_context(proposal)
    if manifest.get('execution_schema_version') != 4 or type(manifest['execution_schema_version']) is not int or manifest.get('operation') != 'delete' or manifest.get('kind') != proposal['kind'] or manifest.get('client_id') != proposal['client_id'] or manifest.get('item_id') != proposal['target_id'] or manifest.get('relative_path') != proposal['delete_binding']['relative_path'] or manifest.get('before_digest') != proposal['base_revision'] or manifest.get('trash_token') != token(proposal):
        raise ValueError('删除执行身份/来源/版本不一致')
    if store is not None:
        controlled(store.repository.root, manifest['relative_path'], required=False)
        controlled(store.repository.root, '.trash/' + manifest['trash_token'], required=False)
    datetime.fromisoformat(manifest['deleted_at'])
    if manifest.get('execution_plan') != concrete_plan(manifest, proposal) or manifest.get('execution_plan_digest') != fingerprint(manifest['execution_plan']):
        raise ValueError('删除执行计划摘要不一致')
    for key in ('authorization_revision', 'dependencies', 'preview_digest', 'confirmation_mode', 'digest_algorithm', 'approval', 'access_target'):
        if manifest.get(key) != proposal.get(key):
            raise ValueError('删除执行批准/授权/影响依据不一致')
    if manifest.get('confirmation') != {'mode':'local_web'} or not manifest.get('approval'):
        raise ValueError('删除缺少持久本机批准')
    states = manifest.get('step_states')
    allowed = [['pending'] * 4] + [['completed'] * count + ['applying'] + ['pending'] * (3 - count) for count in range(4)] + [['completed'] * 4]
    if states not in allowed or manifest['state'] == 'prepared' and states != ['pending'] * 4 or manifest['state'] == 'committed' and states != ['completed'] * 4:
        raise ValueError('删除步骤阶段无效')
    if manifest['state'] in {'applying', 'recovery_required'} and states in (['pending'] * 4, ['completed'] * 4):
        raise ValueError('删除移动阶段不能使用未开始或已终结步骤')
    if manifest['state'] == 'abandoned' and manifest.get('manual_review_required') is not True:
        raise ValueError('放弃删除必须明确记录接受盘态与人工核查')
    expected = {'proposal_id':proposal['proposal_id'], 'version':proposal['version'], 'kind':proposal['kind'], 'item_id':proposal['target_id'],
                'revision':proposal['base_revision'], 'deleted':True, 'trash_token':token(proposal), 'committed_at':manifest['deleted_at'],
                'web_path':'/?item=trash&itemId=' + token(proposal),
                'plan_digest':proposal['plan_digest'], 'execution_plan_digest':manifest['execution_plan_digest'], 'approval':manifest['approval']}
    receipt = manifest['receipt']
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('删除回执不属于原操作')
    if not proposal.get('content_cleaned'):
        from .agent_proposals import digest
        if digest(store.preview_payload(proposal)) != manifest['preview_digest']:
            raise ValueError('删除预览摘要不一致')
    if snapshots and not proposal.get('content_cleaned'):
        path = store.operations / manifest['operation_id'] / ('before.json' if proposal['kind'] == 'concept_map' else 'before.md')
        path = controlled(store.repository.root, path.relative_to(store.repository.root).as_posix())
        raw = path.read_bytes()
        if content_revision(raw) != manifest['before_digest'] or raw.decode('utf-8') != proposal['normalized_content']['target']['raw_source']:
            raise ValueError('删除原始字节快照不一致')
        index_path = store.operations / manifest['operation_id'] / 'index-before.json'
        raw_index = controlled(store.repository.root, index_path.relative_to(store.repository.root).as_posix()).read_bytes()
        if content_revision(raw_index) != proposal['delete_binding']['trash_index_digest'] or manifest['trash_token'] in json.loads(raw_index.decode('utf-8')):
            raise ValueError('删除原索引快照不一致或token已存在')


def prepared_from_manifest(store, manifest, proposal):
    filename = 'before.json' if proposal['kind'] == 'concept_map' else 'before.md'
    raw = (store.operations / manifest['operation_id'] / filename).read_bytes()
    return PreparedDelete(store.repository.root, manifest['relative_path'], manifest['item_id'], manifest['kind'], raw, proposal['delete_binding']['source_identity'])


def index_entry(store, manifest):
    return {'token':manifest['trash_token'], 'id':manifest['item_id'],
            'kind':'concept-map' if manifest['kind'] == 'concept_map' else 'document' if manifest['kind'] == 'document' else 'record',
            'title':manifest['receipt']['title'], 'deleted_at':manifest['deleted_at'],
            'original_path':str(store.repository.root / manifest['relative_path']),
            'trash_path':str(store.repository.trash_dir / manifest['trash_token']),
            'delete_schema_version':1, 'original_relative_path':manifest['relative_path'], 'agent_operation_id':manifest['operation_id']}


def apply_steps(store, manifest, proposal, prepared, *, recovery=False):
    """Apply known domain steps; the caller is ProposalStore's sole state loop."""
    from .persistence import atomic_write_json
    path = store.operations / manifest['operation_id'] / 'manifest.json'
    destination = prepared.trash_path(manifest['trash_token'])
    if not destination.exists():
        if recovery and (manifest['state'] != 'prepared' or manifest['step_states'] != ['pending'] * 4):
            raise ValueError('移动中且回收原对象缺失，不能再次删除可能已恢复的来源')
        store._current_authorization(proposal)
        manifest.update(state='applying', step_states=['applying', 'pending', 'pending', 'pending'])
        atomic_write_json(path, manifest)
        store.checkpoint('delete_move_applying')
        prepared.move(manifest['trash_token'], permit=lambda held:store._current_authorization(proposal, held_source=held), checkpoint=store.checkpoint)
    else:
        prepared.verify_trash(manifest['trash_token'])
    # Proof of the original moved object is sufficient; never touch a source
    # that appeared again, and never require current permission to finish it.
    manifest.update(state='applying', step_states=['completed', 'applying', 'pending', 'pending'])
    atomic_write_json(path, manifest)
    store.checkpoint('delete_move_logged')
    from .deletion_prepared import read_trash_index
    _, index = read_trash_index(store.repository.root)
    expected = index_entry(store, manifest)
    existing = index.get(manifest['trash_token'])
    if existing is not None and existing != expected:
        raise ValueError('原回收token存在异物索引，不能覆盖')
    if existing is None:
        index[manifest['trash_token']] = expected
        store.repository._write_trash_index(index)
    store.checkpoint('delete_index')
    manifest['step_states'] = ['completed', 'completed', 'applying', 'pending']
    atomic_write_json(path, manifest)
    store.checkpoint('delete_index_logged')
    store.repository._forget_record(prepared.path)
    store.checkpoint('delete_cache')
    manifest['step_states'] = ['completed', 'completed', 'completed', 'applying']
    atomic_write_json(path, manifest)
    store.checkpoint('delete_cache_logged')


def validated_trash_paths(repository, item):
    """Resolve a completed Agent entry under the current root, including migration."""
    if 'delete_schema_version' not in item:
        return None
    if type(item['delete_schema_version']) is not int or item['delete_schema_version'] != 1:
        raise AgentError('unsupported_schema', '回收站删除证据版本未知，请使用匹配版本核查', 503)
    store = getattr(repository, 'agent_proposals', None)
    operation = item.get('agent_operation_id')
    if store is None or not isinstance(operation, str) or not re.fullmatch(r'[a-f0-9-]{36}-[1-9][0-9]*', operation):
        raise AgentError('recovery_required', '缺少匹配的删除操作证据，保留回收文件', 503)
    path = store.operations / operation / 'manifest.json'
    from .agent_security import read_json
    manifest = read_json(path)
    proposal = store._load(manifest['proposal_id'], expire=False)
    store._validate_execution(manifest, proposal)
    if manifest.get('operation') != 'delete' or manifest['state'] != 'committed':
        raise AgentError('recovery_required', '该删除尚未完成或已接受盘态，需人工核查', 503)
    expected = index_entry(store, manifest)
    if {key:value for key, value in item.items() if key not in {'original_path', 'trash_path'}} != {key:value for key, value in expected.items() if key not in {'original_path', 'trash_path'}}:
        raise AgentError('recovery_required', '回收索引不是原操作的同一成员，停止恢复或清理', 503)
    source = controlled(repository.root, '.trash/' + manifest['trash_token'])
    with source.open('rb') as stream:
        raw = stream.read(1048577)
    if len(raw) > 1048576 or content_revision(raw) != manifest['before_digest']:
        raise AgentError('recovery_required', '回收内容变化，不能作为原删除结果恢复或清理', 503)
    source_metadata(raw, manifest['item_id'], manifest['kind'])
    destination = controlled(repository.root, manifest['relative_path'], required=False)
    return source, destination
