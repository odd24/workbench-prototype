"""Fresh, exact workflow permissions and fail-closed narrowing."""

import re
import uuid

from .agent_security import AgentError, allows
from .workflow_changes import BOARD_TYPES, COMMANDS, STANDARD, _identifier, _label, effective_template, validate_catalogue
from .workflow_identity import load_identities
from .workflow_prepared import CATALOGUE, FALLBACK, digest, read_raw
from .markdown_io import load_markdown_text
from .project_identity import load_unique_json, valid_new_id


FIELD = 'workflow_write_grants'
SCOPES = {'read', 'propose', 'commit'}
HASH = re.compile(r'[a-f0-9]{64}')
NAME_OPS = {'create', 'copy'}
STATUS_OPS = {'add_status', 'rename_status', 'delete_status', 'reorder'}


def empty_grants():
    return {'schema_version':1, 'grants':[]}


def selection_keys(operation):
    if operation == 'create':
        return {'operation','name'}
    if operation == 'copy':
        return {'operation','template_id','name'}
    if operation == 'switch':
        return {'operation','project_id','target_template_id'}
    if operation in STATUS_OPS:
        return {'operation','template_id','record_type'}
    if operation == 'rename':
        return {'operation','template_id'}
    raise ValueError('工作流授权操作无效')


def _validate_selection(value):
    if not isinstance(value, dict) or not isinstance(value.get('operation'), str):
        raise ValueError('工作流授权需要具体操作')
    operation = value['operation']
    if operation not in COMMANDS or value.keys() != selection_keys(operation):
        raise ValueError('工作流授权需要精确资源范围')
    for key in value:
        if key.endswith('template_id'):
            _identifier(value[key])
    if 'name' in value:
        _label(value['name'])
    if operation in STATUS_OPS and value['record_type'] not in BOARD_TYPES:
        raise ValueError('工作流状态许可仅支持问题或待办')
    if operation == 'switch':
        valid_new_id(value['project_id'])
    if operation == 'rename' and value['template_id'] == STANDARD:
        raise ValueError('系统工作流不能改名')
    return value


def selection(grant):
    return {key:grant[key] for key in selection_keys(grant['operation'])}


def normalize_grants(value):
    if (not isinstance(value, dict) or value.keys() != {'schema_version', 'grants'} or type(value['schema_version']) is not int
            or value['schema_version'] != 1 or not isinstance(value['grants'], list) or len(value['grants']) > 100):
        raise ValueError('工作流授权格式无效')
    grants, seen = [], set()
    for grant in value['grants']:
        if not isinstance(grant, dict) or grant.get('capability') != 'workflows.write' or grant.get('minimum_confirmation_mode') != 'local_web':
            raise ValueError('工作流授权必须使用本机独立批准')
        selected = _validate_selection(selection(grant))
        operation = selected['operation']
        evidence = {'capability','minimum_confirmation_mode'}
        identities = ()
        if operation in NAME_OPS:
            evidence.update(('generation','catalogue_revision'))
            if (type(grant.get('generation')) is not int or grant['generation'] < 0
                    or not isinstance(grant.get('catalogue_revision'), str) or not HASH.fullmatch(grant['catalogue_revision'])):
                raise ValueError('新名称授权必须绑定空缺代次和目录版本')
        if operation == 'switch':
            evidence.update(('source_template_id', 'source_identity','target_identity'))
            _identifier(grant.get('source_template_id'))
            identities = ('source_identity','target_identity')
        elif operation != 'create':
            evidence.add('identity')
            identities = ('identity',)
        if grant.keys() != selected.keys() | evidence or any(not isinstance(grant[key], str) or str(uuid.UUID(grant[key])) != grant[key] for key in identities):
            raise ValueError('工作流授权身份格式无效')
        unique = tuple(sorted(selected.items()))
        if unique in seen:
            raise ValueError('工作流授权范围重复')
        seen.add(unique)
        grants.append((unique, grant.copy()))
    return {'schema_version':1, 'grants':[item for _,item in sorted(grants)]}


def client_grants(client):
    try:
        if client.get('authorization_schema_version', 1) == 10:
            return normalize_grants(client[FIELD])
        if FIELD in client:
            raise ValueError()
        return empty_grants()
    except (KeyError, TypeError, ValueError):
        raise AgentError('invalid_configuration', '工作流授权格式或门槛无效', 503) from None


def upgraded_client(before, grants):
    from .agent_category_authorization import empty_grants as empty_categories, upgraded_client as with_categories
    after = with_categories(before, before.get('category_write_grants', empty_categories()))
    after.update(authorization_schema_version=10, workflow_write_grants=normalize_grants(grants))
    return after


def grant_from_selection(root, selected, *, client=None):
    selected = _validate_selection(selected)
    operation = selected['operation']
    raw = read_raw(root, CATALOGUE)
    if raw is None:
        raise ValueError('工作流配置不存在')
    catalogue = load_unique_json(raw)
    indexed = validate_catalogue(catalogue)
    identities = load_identities(root, catalogue)
    grant = {**selected, 'capability':'workflows.write', 'minimum_confirmation_mode':'local_web'}
    if operation in NAME_OPS:
        name = selected['name']
        if name in identities.names.values():
            raise ValueError('目标模板名称已被占用')
        grant.update(generation=identities.generations.get(name, 0), catalogue_revision=digest(raw))
    if operation == 'switch':
        project_id = selected['project_id']
        if client is not None and (project_id not in client['project_ids'] or not allows(client, {'project_id':project_id})):
            raise AgentError('forbidden', '切换授权需要现有精确项目读取权限', 403)
        original = read_raw(root, f'projects/{project_id}/README.md')
        fallback = read_raw(root, FALLBACK)
        entry, _ = load_markdown_text(original.decode('utf-8')) if original is not None else ({}, '')
        source = effective_template(entry, indexed, load_unique_json(fallback)) if fallback and entry.get('id') == project_id and entry.get('type') == 'project' else None
        target = selected['target_template_id']
        if source is None or target not in indexed or source['id'] == target:
            raise ValueError('切换需要可核验的不同原/目标模板')
        grant.update(source_template_id=source['id'], source_identity=identities.active[source['id']],
                     target_identity=identities.active[target])
    elif operation != 'create':
        key = selected['template_id']
        if key not in indexed:
            raise ValueError('工作流不存在')
        grant['identity'] = identities.active[key]
    return normalize_grants({'schema_version':1, 'grants':[grant]})['grants'][0]


def operation_selection(operation, content):
    return {'operation':operation, **{key:content[key] for key in selection_keys(operation) if key != 'operation'}}


def matching_grant(root, client, operation, content):
    if not client.get('enabled') or not SCOPES <= set(client.get('scopes', ())):
        return None
    selected = operation_selection(operation, content)
    eligible = [grant for grant in client_grants(client)['grants'] if selection(grant) == selected]
    if not eligible:
        return None
    current = grant_from_selection(root, selected, client=client)
    return current if current in eligible else None


def narrowing_plan(clients, prepared):
    old, new = (validate_catalogue(rows) for rows in (prepared.catalogue_before, prepared.catalogue_after))
    deleted = old.keys() - new.keys()
    previous_names = {row['name']:key for key,row in old.items()}
    activated = {row['name'] for key,row in new.items() if previous_names.get(row['name']) != key}
    switched = prepared.selection.get('project_id') if prepared.operation == 'switch' else None
    rows = {}
    for key, client in sorted(clients.items()):
        grants = client_grants(client)['grants']
        kept = [grant for grant in grants
                if not (grant.get('template_id') in deleted or grant.get('source_template_id') in deleted
                        or grant.get('target_template_id') in deleted or grant.get('name') in activated
                        or (switched is not None and grant.get('project_id') == switched))]
        after = client.copy()
        if len(kept) != len(grants):
            after[FIELD] = normalize_grants({'schema_version':1, 'grants':kept})
        if deleted and 'capability_grants' in client:
            dormant = client['capability_grants']
            entries = []
            for grant in dormant['grants']:
                resources = [resource for resource in grant['resources']
                             if resource['type'] != 'workflow_template' or resource['id'] not in deleted]
                if resources:
                    entries.append({**grant, 'resources':resources})
            after['capability_grants'] = {**dormant,'grants':entries}
        if after != client:
            after['management_revision'] = client.get('management_revision', 0) + 1
            rows[key] = after
    return rows


def _validate_narrow(before, after):
    if (any(before.get(key) != after.get(key) for key in (before.keys() | after.keys()) - {FIELD, 'capability_grants', 'management_revision'})
            or after.get('management_revision') != before.get('management_revision', 0) + 1
            or any(grant not in client_grants(before)['grants'] for grant in client_grants(after)['grants'])):
        raise ValueError('工作流收窄不能改变其它授权或扩大许可')
    old, new = (client.get('capability_grants', empty_grants()) for client in (before, after))
    if old.keys() != new.keys() or old['schema_version'] != new['schema_version']:
        raise ValueError('休眠授权格式不能变更')
    for grant in new['grants']:
        if not any(all(grant[field] == prior[field] for field in ('capability','operations','minimum_confirmation_mode'))
                   and all(resource in prior['resources'] for resource in grant['resources']) for prior in old['grants']):
            raise ValueError('休眠授权只能收窄')


def _approve_client(before, grant):
    keep = [old for old in client_grants(before)['grants'] if selection(old) != selection(grant)]
    return upgraded_client(before, {'schema_version':1,'grants':keep + [grant]})


def management_candidate(security, action, params, before, expected_version):
    from .agent_management import digest as value_digest
    if not expected_version:
        raise ValueError('工作流管理需要绑定客户端版本')
    grant = None
    if action == 'workflow_grant':
        if (params.keys() != {'approval_digest','grant'} or not isinstance(params['approval_digest'], str)
                or not HASH.fullmatch(params['approval_digest']) or not SCOPES <= set(before['scopes'])):
            raise ValueError('工作流授权需要完整预览与基本权限')
        grant = params['grant']
        if grant_from_selection(security.root, selection(grant), client=before) != grant:
            raise AgentError('resource_changed', '工作流身份或绑定已变化，请重新预览', 409)
        after, kind = _approve_client(before, grant), 'approve'
    elif action == 'workflow_grant_revoke':
        if params or before.get('authorization_schema_version') != 10:
            raise ValueError('没有可撤销的工作流授权')
        after, kind = upgraded_client(before, empty_grants()), 'revoke'
    else:
        if params.keys() != {'after'}:
            raise ValueError('工作流收窄缺少完整授权证据')
        after, kind = params['after'], 'narrow'
        _validate_narrow(before, after)
    return after, {'operation_family':'workflow', 'workflow_action':kind, 'workflow_grant':grant,
                   'workflow_digest':value_digest(after)}


def validate_management_intent(value):
    from .agent_management import digest as value_digest
    if value.get('operation_family') != 'workflow':
        return
    try:
        action, grant = value['workflow_action'], value['workflow_grant']
        if value['schema_version'] != 10 or not HASH.fullmatch(value['workflow_digest']):
            raise ValueError()
        if action == 'approve':
            normalize_grants({'schema_version':1, 'grants':[grant]})
        elif action not in {'revoke','narrow'} or grant is not None:
            raise ValueError()
        if value['state'] not in {'prepared','recovery_required'}:
            return
        before, after = value['before_client'], value['after_client']
        if (before['client_id'] != value['client_id'] or after['client_id'] != value['client_id']
                or value['before_config'] != value['after_config'] or value_digest(after) != value['workflow_digest']):
            raise ValueError()
        if action == 'narrow':
            _validate_narrow(before, after)
        elif after != (_approve_client(before, grant) if action == 'approve' else upgraded_client(before, empty_grants())):
            raise ValueError()
    except (ValueError, TypeError, KeyError, AgentError) as error:
        raise AgentError('management_recovery_required', '工作流管理日志与原授权证据不一致', 503) from error


def check_management_evidence(security, value):
    if value['workflow_action'] == 'approve':
        grant = value['workflow_grant']
        if grant_from_selection(security.root, selection(grant), client=value['before_client']) != grant:
            raise ValueError('待发布工作流授权的资源已经变化')
