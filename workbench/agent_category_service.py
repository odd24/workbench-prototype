"""Scoped category candidates and the shared local/Agent preparation boundary."""

from .agent_category_authorization import grant_matches, migration_plan, prepared_revision, resource_view
from .agent_delete_service import checked_preview
from .agent_execution import authorization_revision, fingerprint
from .agent_management import client_version
from .agent_security import AgentError, allows
from .category_changes import PROJECT_ASSETS
from .category_prepared import prepare_category
from .write_coordinator import RevisionConflict


def security_for(repository):
    runtime = getattr(repository, 'agent_runtime', None)
    if runtime:
        workspace = runtime.status()['workspace_id']
        if workspace:
            folder = runtime.base / workspace
            if folder.is_dir() and not folder.is_symlink():
                return runtime.security()
            return None
    return getattr(getattr(repository, 'agent_proposals', None), 'security', None)


def validate_selection(selection):
    if not isinstance(selection, dict) or not {'family', 'name'} <= selection.keys() or selection.keys() - {'family', 'name', 'project_id', 'new_name', 'anchor', 'position'}:
        raise AgentError('invalid_category_selection', '仅接受分类体系、具体名称和受控目标字段')
    if any(not isinstance(value, str) for value in selection.values()):
        raise AgentError('invalid_category_selection', '分类选择字段必须为字符串')
    return selection


def visible_members(repository, security, client, family, project_id, members):
    if not client.get('enabled') or 'read' not in client.get('scopes', ()):
        return False
    if family == PROJECT_ASSETS:
        if project_id not in client.get('project_ids', ()):
            return False
        from .agent_attachments import AttachmentService
        from types import SimpleNamespace
        try:
            target = AttachmentService(SimpleNamespace(repository=repository, security=security, store=None, uploads=None)).target(client, 'project', project_id)
        except AgentError:
            return False
        listed = {item['id'] for item in target['attachments']}
        return all(member['id'] in listed for member in members)
    return all(allows(client, resource_view(family, member['before'])) for member in members)


def visible_impact(repository, security, client, family, project_id, impact):
    if not visible_members(repository, security, client, family, project_id, impact['members']):
        return False
    order = impact.get('category_order')
    if order and family != PROJECT_ASSETS:
        return all(allows(client, resource_view(family, {'category':name}))
                   for name in set(order['before']) | set(order['after']))
    return True


def candidate(repository, security, selection, operation, epoch, managed_time, *, client=None):
    selection = validate_selection(selection)
    try:
        prepared = prepare_category(repository, operation=operation, **selection, epoch=epoch, managed_time=managed_time)
    except (ValueError, OSError) as error:
        if client is None:
            raise
        raise AgentError('category_unavailable', '分类或完整影响无法核验', 409) from error
    version = prepared_revision(prepared)
    change = prepared.change
    if client is not None:
        if not grant_matches(client, prepared, version) or not visible_members(repository, security, client, change.family, prepared.project_id, prepared.members):
            raise AgentError('category_unavailable', '分类不存在或当前授权不足以核验完整影响', 404)
        if change.operation == 'reorder' and change.family != PROJECT_ASSETS:
            for name in set(change.before) | set(change.after):
                if not allows(client, resource_view(change.family, {'category':name})):
                    raise AgentError('category_unavailable', '无法在当前权限内展示完整分类位置', 404)
    clients = security.clients() if security else {}
    migrations = migration_plan(clients, prepared)
    registry = {client_id:client_version(value) for client_id, value in clients.items()}
    impact = {'selection':selection, 'operation':operation, 'members':list(prepared.members),
              'revision':version, 'managed_time':managed_time, 'epoch':epoch,
              'warnings':['分类变更保留原条目身份和附件文件。独立附件变更保留记录附件分类。',
                          '先收窄旧范围，再迁移已核验文件。改名仅按原证据补发等价授权。']}
    if change.operation == 'reorder':
        impact['category_order'] = {'before':list(change.before), 'after':list(change.after)}
    private_fields = ('name', 'enabled', 'categories', 'capability_grants', 'delete_grants', 'concept_map_grants', 'category_write_grants')
    local = {'configuration':{'before':prepared.config_before, 'after':prepared.config_after},
             'ordering':{'before':prepared.sort_before, 'after':prepared.sort_after},
             'authorization':[{'client_id':key, **{phase:{field:row[phase][field] for field in private_fields if field in row[phase]}
                                                      for phase in ('before', 'narrow', 'after')}} for key, row in migrations.items()]}
    dependencies = {'schema_version':1, 'files_digest':fingerprint(prepared.evidence()),
                    'authorization_digest':fingerprint([registry, migrations]), 'local_digest':fingerprint(local)}
    checked_preview({**impact, 'local':local})
    return prepared, impact, dependencies, local, registry, migrations


def prepare_submission(repository, security, client, proposal):
    if authorization_revision(client) != proposal['authorization_revision']:
        raise AgentError('authorization_changed', '分类授权已变化，请重新生成完整预览', 409)
    content = proposal['normalized_content']
    result = candidate(repository, security, content['selection'], proposal['operation'], content['epoch'], content['managed_time'], client=client)
    if result[1] != content or result[2] != proposal['dependencies']:
        raise RevisionConflict('分类、成员或授权已经变化，请重新预览')
    return result
