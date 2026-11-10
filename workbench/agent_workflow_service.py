"""Build workflow candidates with separate Agent and local disclosure."""

from dataclasses import replace

from .agent_category_service import security_for
from .agent_delete_service import checked_preview
from .agent_execution import authorization_revision, fingerprint
from .agent_management import client_version
from .agent_security import AgentError, allows, client_kinds
from .agent_workflow_authorization import matching_grant, narrowing_plan, operation_selection, selection
from .workflow_changes import validate_catalogue
from .workflow_identity import FENCE, LEDGER, load_identities
from .workflow_prepared import digest, prepare_workflow
from .write_coordinator import RevisionConflict


def target(operation, command):
    if operation in {'compat_catalogue', 'compat_status'}:
        return {'type':'workflow','operation':operation}
    return {'type':'workflow', **operation_selection(operation, command)}


def visible_impact(client, impact):
    for row in impact['projects']:
        if not allows(client, {'project_id':row['id']}):
            return False
        for prefix, kinds in (('issue',('issue',)), ('todo',('todo',)), ('idea',('idea',)), ('mixed',('issue','todo'))):
            keys = (f'{prefix}_status_order', f'{prefix}_status_record_sorts')
            if any(row['before'].get(key) != row['after'].get(key) for key in keys) and any(
                    not allows(client, {'type':kind,'project_id':row['id']}) for kind in kinds):
                return False
    return all(row['before']['type'] != 'idea' and allows(client, row['before']) for row in impact['records'])


def _visible_template(template, kinds):
    if template is None:
        return None
    return {'id':template['id'], 'name':template['name'],
            'statuses':{kind:template['statuses'][kind] for kind in ('issue','todo') if kind in kinds}}


def _visible_project(row, kinds):
    fields = {'id','name','status','workflow_template'}
    for prefix in ('issue','todo','mixed'):
        for suffix in ('status_order','status_record_sorts'):
            key = f'{prefix}_{suffix}'
            if row['before'].get(key) != row['after'].get(key):
                fields.add(key)
    return {**row, **{side:{key:value for key,value in row[side].items() if key in fields}
                      for side in ('before','after')},
            'mapping':[entry for entry in row['mapping'] if entry['type'] in kinds],
            'template_before':_visible_template(row['template_before'], kinds),
            'template_after':_visible_template(row['template_after'], kinds)}


def proposal_access(client, proposal):
    from .agent_workflow_authorization import SCOPES, client_grants
    if proposal.get('local_workflow_origin') or not client.get('enabled') or not SCOPES <= set(client.get('scopes', ())):
        return False
    if proposal['state'] == 'committed':
        return True
    access = {key:value for key,value in proposal['access_target'].items() if key != 'type'}
    return any(selection(grant) == access for grant in client_grants(client)['grants'])


def _templates(prepared, command, allocated_id):
    before, after = (validate_catalogue(value) for value in (prepared.catalogue_before, prepared.catalogue_after))
    if prepared.operation in {'create', 'copy'}:
        source = before.get(command.get('template_id')) or before.get('standard') or next(iter(before.values()))
        return {'source':source, 'before':None, 'after':after[allocated_id]}
    key = command.get('template_id')
    return {'before':before.get(key), 'after':after.get(key)}


def candidate(repository, security, operation, command, epoch, managed_time, *, allocated_id=None,
              client=None, legacy=None, project_patch=None):
    try:
        prepared = prepare_workflow(repository.root, operation, command, allocated_id=allocated_id,
                                    stamp=managed_time, agent=client is not None, legacy=legacy,
                                    project_patch=project_patch)
        identities = load_identities(repository.root, prepared.catalogue_before)
        identity_files = identities.plan(prepared.catalogue_after, epoch) if prepared.files else ()
        prepared = replace(prepared, files=prepared.files + identity_files,
                           watch={**prepared.watch, FENCE:digest(identities.fence), LEDGER:digest(identities.ledger)})
        grant = matching_grant(repository.root, client, operation, prepared.selection) if client is not None else None
    except (ValueError, OSError) as error:
        if client is None:
            raise
        raise AgentError('workflow_unavailable', '工作流不存在或无法核验完整影响', 404) from error
    impact = {
        'selection':prepared.selection, 'operation':operation, 'allocated_id':allocated_id,
        'epoch':epoch, 'managed_time':managed_time,
        'templates':_templates(prepared, prepared.selection, allocated_id),
        'projects':list(prepared.projects), 'records':list(prepared.records),
        'unmapped':list(prepared.unmapped), 'ordering_conflicts':list(prepared.ordering_conflicts),
        'warnings':['待办完成状态按目标定义推导，原记录及 README 保留原始历史。',
                    '首页按名称关注状态是浏览器偏好，可能包含其它模板的同名状态。'],
    }
    if client is not None and (grant is None or not visible_impact(client, impact)):
        raise AgentError('workflow_unavailable', '工作流不存在或无法核验完整影响', 404)
    clients = security.clients() if security else {}
    registry = {key:client_version(value) for key,value in clients.items()}
    narrowed = narrowing_plan(clients, prepared)
    local_fields = ('name','enabled','workflow_write_grants','capability_grants')
    local = {
        'catalogue':{'before':prepared.catalogue_before, 'after':prepared.catalogue_after},
        'fallback':{'before':prepared.fallback_before, 'after':prepared.fallback_after},
        'authorization':[{'client_id':key, 'before':{field:clients[key][field] for field in local_fields if field in clients[key]},
                          'after':{field:after[field] for field in local_fields if field in after}}
                         for key,after in narrowed.items()],
    }
    if client is not None:
        from .agent_service import clean_item
        kinds = client_kinds(client)
        if prepared.selection.get('record_type') not in (None, *kinds):
            raise AgentError('workflow_unavailable', '工作流不存在或无法核验完整影响', 404)
        local.update(project_files=impact['projects'], record_files=impact['records'])
        impact['templates'] = {key:_visible_template(value, kinds) for key,value in impact['templates'].items()}
        impact['projects'] = [_visible_project(row, kinds) for row in impact['projects']]
        impact['records'] = [{**row,'before':clean_item(row['before'], body=True),
                              'after':clean_item(row['after'], body=True)} for row in impact['records']]
    revision = fingerprint(prepared.evidence())
    impact['revision'] = revision
    dependencies = {'schema_version':1, 'files_digest':revision, 'local_digest':fingerprint(local),
                    'authorization_digest':fingerprint([registry, narrowed])}
    checked_preview({**impact,'local':local})
    return prepared, impact, dependencies, local, registry, narrowed


def prepare_submission(repository, security, client, proposal):
    if authorization_revision(client) != proposal['authorization_revision']:
        raise AgentError('authorization_changed', '工作流授权变化，请重新预览', 409)
    content = proposal['normalized_content']
    bundle = candidate(repository, security, proposal['operation'], content['selection'], content['epoch'],
                       content['managed_time'], allocated_id=content['allocated_id'], client=client)
    if bundle[1] != content or bundle[2] != proposal['dependencies']:
        raise RevisionConflict('工作流、活动集合或授权变化，请重新预览')
    if bundle[0].unmapped:
        raise AgentError('mapping_required', '请为全部使用中状态选择同类型目标后重新预览', 409)
    return bundle
