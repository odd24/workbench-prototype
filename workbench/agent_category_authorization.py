"""Exact, generation-bound category authority and conservative migrations."""

import re
import uuid

from .agent_security import AgentError, allows
from .category_changes import DEFAULT_NAME, OPERATIONS, PROJECT_ASSETS, category_name
from .category_identity import load_category_identities, namespace_key
from .category_prepared import DOCUMENT, GRAPH, _category, category_inventory, revision


FIELD = 'category_write_grants'
REQUIRED = {'read', 'propose', 'commit'}
HASH = re.compile(r'[a-f0-9]{64}')


def empty_grants():
    return {'schema_version':1, 'grants':[]}


def normalize_grants(value):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'grants'} or type(value['schema_version']) is not int or value['schema_version'] != 1 or not isinstance(value['grants'], list) or len(value['grants']) > 100:
        raise ValueError('分类授权格式无效')
    result, seen = [], set()
    for grant in value['grants']:
        fields = {'capability', 'minimum_confirmation_mode', 'family', 'project_id', 'name', 'operation', 'identity', 'generation', 'configuration_revision'}
        if not isinstance(grant, dict) or set(grant) != fields or grant['capability'] != 'categories.write' or grant['minimum_confirmation_mode'] != 'local_web' or grant['operation'] not in OPERATIONS:
            raise ValueError('分类授权必须指定具体操作和本机确认')
        family, project, name = (grant[key] for key in ('family', 'project_id', 'name'))
        key = (namespace_key(family, project), name, grant['operation'])
        category_name(family, name, destination=grant['operation'] == 'create')
        if key in seen or type(grant['generation']) is not int or grant['generation'] < 0:
            raise ValueError('分类授权代次或范围无效')
        if grant['operation'] == 'create':
            if grant['identity'] is not None or not isinstance(grant['configuration_revision'], str) or not HASH.fullmatch(grant['configuration_revision']):
                raise ValueError('创建授权必须绑定空缺名称和配置版本')
        elif not isinstance(grant['identity'], str) or str(uuid.UUID(grant['identity'])) != grant['identity'] or not grant['generation'] or grant['configuration_revision'] is not None:
            raise ValueError('分类授权缺少原分类身份')
        seen.add(key)
        result.append((key, grant.copy()))
    return {'schema_version':1, 'grants':[grant for _, grant in sorted(result, key=lambda pair:pair[0])]}


def client_grants(client):
    if client.get('authorization_schema_version', 1) not in (9, 10):
        if FIELD in client:
            raise AgentError('invalid_configuration', '分类授权格式门槛缺失', 503)
        return empty_grants()
    try:
        return normalize_grants(client[FIELD])
    except (ValueError, TypeError, KeyError):
        raise AgentError('invalid_configuration', '分类授权格式无效', 503) from None


def upgraded_client(before, grants):
    from .agent_project_authorization import grant_value as create_grant
    from .agent_project_delete_authorization import grant_value as delete_grant
    after = {**before, 'authorization_schema_version':max(9, before.get('authorization_schema_version', 1)), FIELD:normalize_grants(grants),
             'management_revision':before.get('management_revision', 0) + 1}
    for key in ('concept_map_grants', 'delete_grants'):
        after.setdefault(key, empty_grants())
    after.setdefault('project_create_grant', create_grant(False))
    after.setdefault('project_delete_grants', delete_grant())
    return after


def grant_matches(client, prepared, revision):
    change = prepared.change
    return bool(client.get('enabled') and REQUIRED <= set(client.get('scopes', ())) and any(
        grant['family'] == change.family and grant['project_id'] == prepared.project_id
        and grant['name'] == change.name and grant['operation'] == change.operation
        and grant['identity'] == prepared.scope['active'].get(change.name)
        and grant['generation'] == prepared.scope['generations'].get(change.name, 0)
        and (change.operation != 'create' or grant['configuration_revision'] == revision)
        for grant in client_grants(client)['grants']))


def grant_from_selection(repository, selection, *, inventory_cache=None):
    from .agent_execution import fingerprint
    if not isinstance(selection, dict) or set(selection) != {'family', 'project_id', 'name', 'operation'} or selection['operation'] not in OPERATIONS:
        raise ValueError('分类授权必须选择具体分类与操作')
    family, project, name, operation = (selection[key] for key in ('family', 'project_id', 'name', 'operation'))
    key = namespace_key(family, project)
    category_name(family, name, destination=operation == 'create')
    if name == DEFAULT_NAME and family != PROJECT_ASSETS:
        raise ValueError('系统默认分类不能授权变更')
    if inventory_cache is not None and key in inventory_cache:
        raw, names, scope = inventory_cache[key]
    else:
        config, raw, members, _ = category_inventory(repository, family, project)
        names = list(dict.fromkeys(entry['name'] if family == PROJECT_ASSETS else entry for entry in config))
        observed = dict.fromkeys(_category(family, member['item']) for member in members)
        names.extend(category for category in observed if category and category not in names)
        scope = load_category_identities(repository.root).scope(key, names)
        if inventory_cache is not None:
            inventory_cache[key] = raw, names, scope
    identity = scope['active'].get(name)
    if (operation == 'create') != (identity is None):
        raise AgentError('category_resource_changed', '分类存在状态已变化，请重新预览', 409)
    grant = {**selection, 'capability':'categories.write', 'minimum_confirmation_mode':'local_web', 'identity':identity,
             'generation':scope['generations'].get(name, 0),
             'configuration_revision':fingerprint([revision(raw), names, scope]) if operation == 'create' else None}
    return normalize_grants({'schema_version':1, 'grants':[grant]})['grants'][0]


def prepared_revision(prepared):
    from .agent_execution import fingerprint
    from .category_prepared import catalogue_path
    relative = catalogue_path(prepared.change.family, prepared.project_id)
    return fingerprint([prepared.watch[relative], list(prepared.names), prepared.scope])


def management_candidate(security, action, params, before, expected_version):
    from .agent_management import digest
    if not expected_version:
        raise ValueError('分类管理需要客户端版本')
    if action == 'category_migration':
        if set(params) != {'after', 'phase', 'proof'}:
            raise ValueError('分类迁移授权证据不全')
        after = params['after']
        intent = {'operation_family':'category_migration', 'category_action':params['phase'],
                  'category_proof':params['proof'], 'category_digest':digest(after)}
        _validate_transition(before, after, intent)
        check_management_evidence(security, {**intent, 'client_id':before['client_id'],
                                             'before_client':before, 'after_client':after})
        return after, intent
    if action == 'category_grant_revoke':
        if params or before.get('authorization_schema_version') not in (9, 10):
            raise ValueError('当前没有可撤销的分类授权')
        grant = None
        after = upgraded_client(before, empty_grants())
    else:
        from types import SimpleNamespace
        if set(params) != {'approval_digest', 'grant'} or not HASH.fullmatch(params['approval_digest']) or not REQUIRED <= set(before['scopes']):
            raise ValueError('分类授权必须绑定完整预览和基本权限')
        grant = params['grant']
        selected = {key:grant[key] for key in ('family', 'project_id', 'name', 'operation')}
        if grant_from_selection(SimpleNamespace(root=security.root), selected) != grant:
            raise AgentError('category_resource_changed', '分类身份或配置已变化，请重新预览', 409)
        grants = [item for item in client_grants(before)['grants'] if any(item[key] != selected[key] for key in selected)]
        after = upgraded_client(before, {'schema_version':1, 'grants':grants + [grant]})
    return after, {'operation_family':'category_grant', 'category_action':'approve' if grant else 'revoke',
                   'category_proof':grant, 'category_digest':digest(after)}


def _validate_transition(before, after, intent):
    fields = {'categories', 'capability_grants', 'delete_grants', 'concept_map_grants', FIELD, 'management_revision'}
    if any(before.get(key) != after.get(key) for key in (before.keys() | after.keys()) - fields) or after.get('management_revision') != before.get('management_revision', 0) + 1:
        raise ValueError('分类迁移修改了无关客户端字段')
    action, proof = intent['category_action'], intent['category_proof']
    if action == 'narrow':
        if proof != {} or not set(after['categories']) <= set(before['categories']):
            raise ValueError('分类收窄授权不得扩大')
        for key in ('capability_grants', 'delete_grants', 'concept_map_grants'):
            for grant in after.get(key, empty_grants())['grants']:
                if not any(all(grant[field] == old[field] for field in ('capability', 'operations', 'minimum_confirmation_mode'))
                           and all(resource in old['resources'] for resource in grant['resources'])
                           for old in before.get(key, empty_grants())['grants']):
                    raise ValueError('分类收窄改变了原许可')
        if any(grant not in client_grants(before)['grants'] for grant in client_grants(after)['grants']):
            raise ValueError('分类收窄改变了类别许可')
    elif action != 'restore' or not before.get('enabled') or not isinstance(proof, dict) or not proof:
        raise ValueError('分类补发证据缺失')


def validate_management_intent(value):
    from .agent_management import digest
    family = value.get('operation_family')
    if family not in {'category_grant', 'category_migration'}:
        return
    try:
        action, proof = value['category_action'], value['category_proof']
        if value['schema_version'] not in (9, 10) or not HASH.fullmatch(value['category_digest']):
            raise ValueError()
        if family == 'category_grant':
            if action == 'approve':
                normalize_grants({'schema_version':1, 'grants':[proof]})
            elif action != 'revoke' or proof is not None:
                raise ValueError()
        elif action not in {'narrow', 'restore'} or not isinstance(proof, dict):
            raise ValueError()
        if value['state'] not in {'prepared', 'recovery_required'}:
            return
        before, after = value['before_client'], value['after_client']
        if before['client_id'] != value['client_id'] or after['client_id'] != value['client_id'] or value['before_config'] != value['after_config'] or digest(after) != value['category_digest']:
            raise ValueError()
        if family == 'category_grant':
            keep = [item for item in client_grants(before)['grants'] if proof and any(item[key] != proof[key] for key in ('family', 'project_id', 'name', 'operation'))]
            expected = upgraded_client(before, {'schema_version':1, 'grants':keep + ([proof] if proof else [])})
            if after != expected:
                raise ValueError()
        else:
            _validate_transition(before, after, value)
    except (ValueError, TypeError, KeyError, AgentError) as error:
        raise AgentError('management_recovery_required', '分类授权日志与原操作证据不一致', 503) from error


def check_management_evidence(security, intent):
    from types import SimpleNamespace
    action, proof = intent['category_action'], intent['category_proof']
    if action == 'approve':
        selection = {key:proof[key] for key in ('family', 'project_id', 'name', 'operation')}
        if grant_from_selection(SimpleNamespace(root=security.root), selection) != proof:
            raise ValueError('分类授权资源变化')
    if action == 'restore':
        from .agent_category_execution import verify_restore_evidence
        verify_restore_evidence(security, intent)


def resource_view(family, item):
    return {**item, 'type':'document' if family == DOCUMENT else 'concept_map'}


def _capabilities(client, family, item):
    from .agent_concept_authorization import graph_allows
    from .agent_delete_authorization import delete_allows
    view = resource_view(family, item)
    read = client.get('enabled') is True and 'read' in client.get('scopes', ()) and allows(client, view)
    write = read and (graph_allows(client, view, 'update') if family == GRAPH else REQUIRED <= set(client.get('scopes', ())))
    return {key for key, active in [('read', read), ('write', write), ('delete', read and delete_allows(client, view))] if active}


def migration_plan(clients, prepared):
    """Return original, narrowed and equivalent values for a private journal."""
    change = prepared.change
    if change.operation == 'reorder':
        return {}
    family, source, target = change.family, change.name, change.destination
    names = {source} if change.operation == 'delete' else {source, target}
    migrations = {}
    for client_id, before in sorted(clients.items()):
        narrow, finish = before.copy(), before.copy()
        if family == DOCUMENT and '*' not in before['categories']:
            narrow['categories'] = [value for value in before['categories'] if value not in names]
            finish['categories'] = list(dict.fromkeys(target if value == source and change.operation == 'rename' else value
                                                     for value in before['categories'] if value not in names or value == source and change.operation == 'rename'))
        for key in ('capability_grants', 'delete_grants', 'concept_map_grants'):
            if key not in before:
                continue
            existing = before[key]['grants']
            stripped, transferred = [], []
            for grant in existing:
                def affected(resource):
                    return (resource['type'] == family and resource.get('name') in names
                            and (family != PROJECT_ASSETS or resource['project_id'] == prepared.project_id))
                resources = [resource for resource in grant['resources'] if not affected(resource)]
                if resources:
                    stripped.append({**grant, 'resources':resources})
                equivalent = [{**resource, 'name':target} for resource in grant['resources']
                              if affected(resource) and resource['name'] == source and key != 'capability_grants' and change.operation == 'rename']
                if resources or equivalent:
                    transferred.append({**grant, 'resources':resources + equivalent})
            narrow[key] = {**before[key], 'grants':stripped}
            finish[key] = {**before[key], 'grants':transferred}
        if FIELD in before:
            def affected_grant(grant):
                return grant['family'] == family and grant['project_id'] == prepared.project_id and grant['name'] in names
            stripped = [grant for grant in client_grants(before)['grants'] if not affected_grant(grant)]
            equivalent = [{**grant, 'name':target, 'generation':prepared.scope['generations'].get(target, 0) + 1}
                          for grant in client_grants(before)['grants'] if change.operation == 'rename' and affected_grant(grant)
                          and grant['name'] == source and grant['identity'] == prepared.scope['active'].get(source)
                          and grant['generation'] == prepared.scope['generations'].get(source)
                          and grant['operation'] != 'create']
            narrow[FIELD] = normalize_grants({'schema_version':1, 'grants':stripped})
            finish[FIELD] = normalize_grants({'schema_version':1, 'grants':stripped + equivalent})
        if not before.get('enabled'):
            finish = narrow.copy()
        if family != PROJECT_ASSETS:
            for member in prepared.members:
                if _capabilities(finish, family, member['after']) - _capabilities(before, family, member['before']):
                    raise AgentError('category_access_expansion', '迁移会扩大对现有内容的授权，请先核对范围并重新预览', 409)
        if narrow != before:
            narrow['management_revision'] = before.get('management_revision', 0) + 1
            finish['management_revision'] = narrow['management_revision']
            if finish != narrow:
                finish['management_revision'] += 1
            migrations[client_id] = {'before':before, 'narrow':narrow, 'after':finish}
    return migrations
