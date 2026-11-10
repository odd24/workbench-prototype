"""Static concept_map@1 contract inside the existing ProposalStore journal."""

import json
import re
import uuid

from .agent_security import AgentError
from .agent_concept_maps import validate_graph, json_bytes, PREVIEW_BYTES
from .agent_concept_service import graph_target, SERVICE_TIME
from .agent_concept_authorization import normalize_graph_grants, validate_grant_dependencies


STEPS = ['history_snapshot', 'json_write']


def identity(proposal):
    return {'schema_version': 1, 'kind': 'concept_map', 'id': proposal['target_id'],
            **{key: proposal[key] for key in ('proposal_id', 'client_id', 'workspace_id')}}


def logical_plan(proposal):
    from .agent_execution import fingerprint
    content = proposal.get('normalized_content')
    candidate = fingerprint(content) if content is not None else proposal['execution_plan']['candidate_digest']
    return {'handler': 'concept_map@1', 'kind': 'concept_map', 'operation': proposal['operation'],
            'target': proposal['access_target'], 'source_target': proposal['source_target'],
            'identity': proposal['identity'], 'candidate_digest': candidate, 'steps': STEPS.copy(), 'source_bindings': []}


def validate_context(proposal):
    from .agent_execution import fingerprint
    if proposal['operation'] not in {'create', 'update'} or not isinstance(proposal['target_id'], str) or not re.fullmatch(r'CMAP-[0-9]+', proposal['target_id']) or not isinstance(proposal.get('identity'), dict) or type(proposal['identity'].get('schema_version')) is not int or proposal.get('identity') != identity(proposal) or str(uuid.UUID(proposal['client_id'])) != proposal['client_id']:
        raise ValueError('图提案身份契约无效')
    for name in ('access_target', 'source_target'):
        target = proposal.get(name)
        if name == 'source_target' and target is None and proposal['operation'] == 'create':
            continue
        if not isinstance(target, dict) or set(target) != {'type', 'id', 'project_id', 'category'} or target['type'] != 'concept_map' or target['id'] != proposal['target_id'] or target['project_id'] is not None and not isinstance(target['project_id'], str) or not isinstance(target['category'], str):
            raise ValueError('图提案持久归属字段无效')
    dependencies = proposal.get('dependencies')
    if not isinstance(dependencies, dict) or set(dependencies) != {'schema_version', 'resource_grants', 'resources'} or type(dependencies['schema_version']) is not int or dependencies['schema_version'] != 1:
        raise ValueError('图提案依赖契约无效')
    grants = normalize_graph_grants(dependencies['resource_grants'])
    if grants != dependencies['resource_grants'] or not grants['grants']:
        raise ValueError('图提案具体资源依赖无效')
    validate_grant_dependencies(dependencies['resources'], grants)
    warnings = proposal.get('graph_warnings')
    if not isinstance(warnings, list) or any(not isinstance(value, str) for value in warnings):
        raise ValueError('图提案警告证据无效')
    if proposal['operation'] == 'create':
        if proposal['base_revision'] is not None or proposal['source_target'] is not None:
            raise ValueError('图创建不能指定旧版本或来源')
    elif not isinstance(proposal['base_revision'], str) or not re.fullmatch(r'[a-f0-9]{64}', proposal['base_revision']):
        raise ValueError('图更新基础版本无效')
    if not proposal.get('content_cleaned'):
        content, base = proposal['normalized_content'], proposal['base_content']
        if set(content) != {'graph'} or not isinstance(base, dict):
            raise ValueError('图提案缺少完整候选与原图')
        try:
            graph, _ = validate_graph(content['graph'], base=base if proposal['operation'] == 'update' else None, create=proposal['operation'] == 'create')
        except AgentError as error:
            raise ValueError('持久图候选损坏或不受支持') from error
        if graph != content['graph'] or proposal['access_target'] != graph_target(graph, proposal['target_id']):
            raise ValueError('图提案授权目标与候选不一致')
        if proposal['source_target'] != (graph_target(base, proposal['target_id']) if proposal['operation'] == 'update' else None) or proposal['operation'] == 'create' and base:
            raise ValueError('图提案来源与原图不一致')
    if proposal.get('execution_plan') != logical_plan(proposal) or proposal.get('plan_digest') != fingerprint(proposal['execution_plan']):
        raise ValueError('图提案执行计划不一致')


def candidate_graph(proposal, managed_time=SERVICE_TIME):
    graph = {**proposal['base_content'], **proposal['normalized_content']['graph'], 'id': proposal['target_id'], 'updated': managed_time}
    if proposal['operation'] == 'create':
        graph['created'] = managed_time
    graph.pop('revision', None)
    graph.pop('expected_revision', None)
    return graph


def graph_diff(base, after):
    result = {'metadata': {key: {'before': base.get(key), 'after': after.get(key), 'before_present':key in base, 'after_present':key in after} for key in sorted(set(base) | set(after))
                           if key not in {'nodes', 'edges'} and (key not in base or key not in after or base.get(key) != after.get(key))}}
    for collection in ('nodes', 'edges'):
        old, new = base.get(collection, []), after[collection]
        before_ids, after_ids = [item['id'] for item in old], [item['id'] for item in new]
        old = {item['id']: item for item in old}
        new = {item['id']: item for item in new}
        result[collection] = {'order_before': before_ids, 'order_after': after_ids,
                              'changes': [{'id': key, 'before': old.get(key), 'after': new.get(key)} for key in sorted(set(old) | set(new)) if old.get(key) != new.get(key)]}
    return result


def preview_fields(proposal):
    after = candidate_graph(proposal)
    warnings = ['图ID由本提案持久预留，取消或过期不复用；正式结果以入库状态和回执为准。',
                '创建/修改时间为明确占位；服务端受理本次确认后固定实际时间并记录执行计划。',
                '必须展示完整画布、全部节点/关系字段、原图、稳定ID差异与警告后再确认当前版本。',
                '授权绑定完整派生资源集合；同范围其他图增减或相关配置变化也可能要求修订并重新预览。',
                *proposal['graph_warnings']]
    return {'base_graph': proposal['base_content'], 'prepared_graph': after,
            'graph_diff': graph_diff(proposal['base_content'], after), 'identity': proposal['identity'], 'warnings': warnings}


def checked_preview(result):
    if len(json_bytes(result)) > PREVIEW_BYTES:
        raise AgentError('preview_too_large', '完整图预览超过2MiB，拒绝截断或省略字段', 413)
    return result


def concrete_plan(manifest, proposal):
    return {'handler': 'concept_map@1', 'proposal_plan_digest': proposal['plan_digest'], 'steps': STEPS.copy(),
            **{key: manifest[key] for key in ('kind', 'operation', 'item_id', 'relative_path', 'before_digest', 'after_digest', 'history_version', 'managed_time')},
            'identity': proposal['identity']}


def validate_snapshots(store, manifest, proposal, snapshots):
    from .agent_proposals import byte_digest, digest
    from .agent_execution import validate_manifest
    from .agent_concept_maps import controlled_graph_path
    validate_manifest(manifest, proposal)
    if manifest['state'] == 'committed' and manifest['step_states'] != ['completed', 'completed'] or manifest['state'] == 'prepared' and manifest['step_states'] != ['pending', 'pending']:
        raise ValueError('图执行阶段与步骤状态不一致')
    store._target(manifest)
    store._history_path(manifest)
    if manifest['item_id'] != proposal['target_id'] or manifest['before_digest'] != (proposal['base_revision'] if proposal['operation'] == 'update' else None):
        raise ValueError('图执行目标或基础版本无效')
    from datetime import datetime
    if not isinstance(manifest.get('managed_time'), str) or datetime.fromisoformat(manifest['managed_time']) is None:
        raise ValueError('图受理时间无效')
    if not proposal.get('content_cleaned') and manifest['preview_digest'] != digest(store.preview_payload(proposal)):
        raise ValueError('图完整预览摘要不一致')
    if snapshots and not proposal.get('content_cleaned'):
        directory = store.operations / manifest['operation_id']
        values = {}
        for name, expected in (('before.json', manifest['before_digest']), ('after.json', manifest['after_digest'])):
            path = controlled_graph_path(store.repository.root, (directory / name).relative_to(store.repository.root).as_posix())
            value = path.read_bytes() if expected is not None else None
            if byte_digest(value) != expected:
                raise ValueError('图执行原始字节快照摘要无效')
            values[name] = json.loads(value.decode('utf-8')) if value is not None else {}
        if values['before.json'] != proposal['base_content'] or values['after.json'] != candidate_graph(proposal, manifest['managed_time']):
            raise ValueError('图执行原始字节快照与完整候选不一致')
