"""Fresh, explicit graph grants; dormant configuration is never activated."""

import re
import hashlib
import json
import secrets
import time
from pathlib import Path

from .agent_security import AgentError, normalize_capability_grants


EMPTY_GRAPH_GRANTS = {'schema_version': 1, 'grants': []}


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def normalize_graph_grants(value):
    normalized = normalize_capability_grants(value)
    for grant in normalized['grants']:
        if grant['capability'] not in {'concept_maps.read', 'concept_maps.write'}:
            raise ValueError('图授权仅接受concept_maps.read/write')
        if grant['capability'] == 'concept_maps.read' and grant['minimum_confirmation_mode'] != 'agent_attested':
            raise ValueError('图读取不设置逐次确认策略；新授予仍须完整管理预览批准')
        for resource in grant['resources']:
            if resource['type'] == 'concept_map':
                if not re.fullmatch(r'CMAP-[0-9]+', resource['id']):
                    raise ValueError('指定图身份无效')
                if 'create' in grant['operations']:
                    raise ValueError('指定已有图不能授予创建新图')
    return normalized


def client_graph_grants(client):
    if client.get('authorization_schema_version', 1) != 5:
        if 'concept_map_grants' in client:
            raise AgentError('invalid_configuration', '旧授权不能包含已生效图授权', 503)
        return {'schema_version': 1, 'grants': []}
    try:
        return normalize_graph_grants(client['concept_map_grants'])
    except (KeyError, ValueError, TypeError):
        raise AgentError('invalid_configuration', '图授权格式无效，停止使用', 503) from None


def validate_narrowing(before, after):
    original = normalize_graph_grants(before)['grants']
    narrowed = normalize_graph_grants(after)
    for grant in narrowed['grants']:
        if not any(all(grant[key] == old[key] for key in ('capability', 'operations', 'minimum_confirmation_mode'))
                   and all(resource in old['resources'] for resource in grant['resources']) for old in original):
            raise ValueError('收窄不得增加图权限、资源或降低确认策略')
    return narrowed


def resource_matches(resource, item):
    if resource['type'] == 'concept_map':
        return resource['id'] == item.get('id')
    if resource['type'] == 'project':
        return item.get('project_id') is not None and resource['id'] == item.get('project_id')
    return resource['type'] == 'concept_map_category' and item.get('project_id') is None and resource['name'] == item.get('category')


def matching_graph_grants(client, item, operation='read', *, destination=False):
    if item.get('type') != 'concept_map' or client.get('authorization_schema_version') != 5 or client.get('enabled') is not True or 'concept_map' not in client.get('kinds', []):
        return []
    needed = {'read'} if operation == 'read' else {'read', 'propose', 'commit'}
    if not needed <= set(client.get('scopes', [])):
        return []
    capability = 'concept_maps.read' if operation == 'read' else 'concept_maps.write'
    return [grant for grant in client_graph_grants(client)['grants']
            if grant['capability'] == capability and operation in grant['operations']
            and any(resource_matches(resource, item) and not (destination and resource['type'] == 'concept_map') for resource in grant['resources'])]


def graph_allows(client, item, operation='read', *, destination=False):
    if operation != 'read' and not matching_graph_grants(client, item, 'read'):
        return False
    return bool(matching_graph_grants(client, item, operation, destination=destination))


def graph_confirmation_mode(client, item, operation, requested):
    if requested not in {'agent_attested', 'local_web'}:
        raise AgentError('invalid_confirmation', '确认策略无效')
    if not graph_allows(client, item, operation):
        raise AgentError('not_found', '概念图不存在或不可访问', 404)
    grants = matching_graph_grants(client, item, operation)
    if not grants:
        raise AgentError('not_found', '概念图不存在或不可访问', 404)
    modes = {requested, client.get('minimum_confirmation_mode', 'agent_attested'), *(grant['minimum_confirmation_mode'] for grant in grants)}
    return 'local_web' if 'local_web' in modes else 'agent_attested'


def effective_operations(repository, client):
    """Report only operations with an intersecting read/write resource scope."""
    grants = client_graph_grants(client)['grants']
    if not {'read', 'propose', 'commit'} <= set(client.get('scopes', [])):
        return []
    probes = []
    for grant in grants:
        if grant['capability'] != 'concept_maps.write':
            continue
        for resource in grant['resources']:
            if resource['type'] != 'concept_map':
                probes.append({'type':'concept_map', 'id':None,
                               'project_id':resource.get('id') if resource['type'] == 'project' else None,
                               'category':resource.get('name') if resource['type'] == 'concept_map_category' else None})
    operations = {operation for operation in ('create', 'update') if any(graph_allows(client, probe, operation) for probe in probes)}
    if 'update' not in operations and any(resource['type'] == 'concept_map' for grant in grants for resource in grant['resources']):
        from .agent_concept_maps import graph_catalog
        if any(graph_allows(client, {**item, 'type':'concept_map'}, 'update') for item in graph_catalog(repository.root)):
            operations.add('update')
    return sorted(operations)


def grant_dependencies(repository, grants):
    """Read the exact resource snapshot for approval/publication, never create it."""
    from .markdown_io import load_markdown_text
    from .write_coordinator import content_revision
    from .concept_maps import ConceptMapRepository
    from .agent_concept_maps import controlled_graph_path, graph_catalog, read_graph
    if hasattr(repository, '_concept_map_repository'):
        root, domain = repository.root, repository._concept_map_repository
    else:
        # CLI credential recovery reads the same domain implementation without
        # opening/initializing another business Repository or taking its lock.
        root = Path(repository)
        domain = ConceptMapRepository(root / 'concept-maps', root / 'config', None, None)
    grants = normalize_graph_grants(grants)
    resources = {json.dumps(resource, sort_keys=True): resource for grant in grants['grants'] for resource in grant['resources']}
    catalog = graph_catalog(root)
    config_path = controlled_graph_path(root, 'config/concept-map-categories.json')
    config = config_path.read_bytes() if config_path.exists() else b''
    if config:
        try:
            configured = json.loads(config.decode('utf-8'))
            if not isinstance(configured, list) or any(not isinstance(item, str) for item in configured):
                raise ValueError()
        except (ValueError, UnicodeError):
            raise AgentError('invalid_configuration', '图分类配置不可完整读取，停止授权', 503) from None
    categories = domain.categories()
    result = []
    for _, resource in sorted(resources.items()):
        kind = resource['type']
        if kind == 'project':
            path = controlled_graph_path(root, f"projects/{resource['id']}/README.md")
            if not path.is_file():
                raise AgentError('resource_changed', '授权项目已不存在，请重新预览', 409)
            raw = path.read_bytes()
            metadata, _ = load_markdown_text(raw.decode('utf-8'))
            if metadata.get('id') != resource['id'] or metadata.get('type') != 'project':
                raise AgentError('resource_changed', '项目身份已变化，请重新预览', 409)
            revision = content_revision(raw)
        elif kind == 'concept_map':
            item, _, _ = read_graph(root, resource['id'])
            if not item or item.get('id') != resource['id'] or type(item.get('version', 1)) is not int or item.get('version', 1) not in (1, 2):
                raise AgentError('resource_changed', '授权图已不存在或格式不受支持', 409)
            revision = item['revision']
        else:
            if resource['name'] not in categories:
                raise AgentError('resource_changed', '授权图分类已不存在，请重新预览', 409)
            revision = content_revision(config)
        members = sorted((item['id'], item['revision']) for item in catalog if resource_matches(resource, item))
        result.append({'resource': resource, 'revision': revision, 'members_digest': _digest(members), 'count': len(members)})
    return {'schema_version': 1, 'catalog_digest': _digest([content_revision(config), categories]), 'resources': result}


def validate_grant_dependencies(value, grants):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'catalog_digest', 'resources'} or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('图授权依赖格式无效')
    if not isinstance(value['catalog_digest'], str) or not re.fullmatch(r'[a-f0-9]{64}', value['catalog_digest']) or not isinstance(value['resources'], list):
        raise ValueError('图授权依赖摘要无效')
    expected = {json.dumps(resource, sort_keys=True) for grant in normalize_graph_grants(grants)['grants'] for resource in grant['resources']}
    seen = set()
    for item in value['resources']:
        if not isinstance(item, dict) or set(item) != {'resource', 'revision', 'members_digest', 'count'} or type(item['count']) is not int or item['count'] < 0:
            raise ValueError('图授权资源依赖无效')
        for key in ('revision', 'members_digest'):
            if not isinstance(item[key], str) or not re.fullmatch(r'[a-f0-9]{64}', item[key]):
                raise ValueError('图授权资源摘要无效')
        key = json.dumps(item['resource'], sort_keys=True)
        if key not in expected or key in seen:
            raise ValueError('图授权资源集合不一致')
        seen.add(key)
    if seen != expected:
        raise ValueError('图授权资源集合不完整')


def restrict_graph_categories(repository, names):
    """Persist narrowing before business changes; never restore implicitly."""
    runtime = getattr(repository, 'agent_runtime', None)
    service = getattr(repository, 'agent_service', None)
    if runtime:
        if not runtime.status()['workspace_id']:
            return
        security = runtime.security()
    elif service:
        security = service.security
    else:
        return
    from .agent_management import client_version
    manager = security.manager()
    manager.recover()
    for client in security.clients().values():
        grants = client_graph_grants(client)
        narrowed = []
        for grant in grants['grants']:
            resources = [resource for resource in grant['resources'] if not (resource['type'] == 'concept_map_category' and resource['name'] in names)]
            if resources:
                narrowed.append({**grant, 'resources': resources})
        if narrowed != grants['grants']:
            manager.run('concept_map_grants_narrow', {'grants': {'schema_version': 1, 'grants': narrowed}},
                        client['client_id'], client_version(client))


class GraphGrantManagement:
    """Loopback management only. Agent callers cannot mint approval tickets."""
    def __init__(self, runtime):
        from .agent_management import AgentManagement
        self.runtime = runtime
        self.repository = runtime.repository
        self.security = AgentManagement(runtime)._security()

    def client(self, key, expected=None, *, enabled=True):
        from .agent_files import file_id
        from .agent_management import client_version
        client = self.security.clients().get(file_id(key))
        if not client or enabled and not client.get('enabled') or key in self.security.manager().blocked_clients():
            raise AgentError('not_found', '客户端不存在或需要恢复', 404)
        if expected is not None and client_version(client) != expected:
            raise AgentError('configuration_conflict', '客户端授权变化，请重新完整预览', 409)
        return client

    def list(self, key):
        from .agent_management import client_version
        from .agent_concept_maps import graph_catalog
        client = self.client(key, enabled=False)
        return {'workspace_id': self.security.workspace_id, 'client_id': key, 'expected_version': client_version(client),
                'grants': client_graph_grants(client),
                'projects': [{'id': item['id'], 'name': item['name']} for item in self.repository.list_projects()],
                'categories': self.repository.concept_map_categories(), 'maps': graph_catalog(self.repository.root)}

    def preview(self, key, payload):
        from .agent_management import credential_lock, client_version, digest
        from .agent_concept_maps import graph_catalog
        if not isinstance(payload, dict) or set(payload) != {'workspace_id', 'expected_version', 'grants'} or payload['workspace_id'] != self.security.workspace_id or not isinstance(payload['expected_version'], str) or not re.fullmatch(r'[a-f0-9]{64}', payload['expected_version']):
            raise AgentError('invalid_request', '图授权预览字段无效')
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            client = self.client(key, payload['expected_version'])
            grants = normalize_graph_grants(payload['grants'])
            if not grants['grants']:
                raise AgentError('invalid_request', '请选择具体图权限与资源；清空请使用撤销')
            required = {'read', 'propose', 'commit'} if any(grant['capability'] == 'concept_maps.write' for grant in grants['grants']) else {'read'}
            if not required <= set(client['scopes']):
                raise AgentError('forbidden', '客户端操作权限不足，请先编辑基本授权', 403)
            dependencies = grant_dependencies(self.repository, grants)
            maps = graph_catalog(self.repository.root)
            projects = {item['id']: item['name'] for item in self.repository.list_projects()}
            resources = []
            for dependency in dependencies['resources']:
                resource = dependency['resource']
                label = projects.get(resource.get('id'), resource.get('name', resource.get('id')))
                resources.append({**dependency, 'label': label, 'maps': [item for item in maps if resource_matches(resource, item)]})
            preview = {'workspace_id': self.security.workspace_id, 'client_id': key, 'client_name': client['name'],
                       'expected_version': client_version(client), 'grants': grants, 'resources': resources,
                       'resource_dependencies': dependencies, 'scopes': client['scopes'],
                       'minimum_confirmation_mode': client.get('minimum_confirmation_mode', 'agent_attested'),
                       'disclosure': '替代本客户端全部现有图授权；旧休眠配置不会激活。本次变更更新客户端版本，现有上传暂存及附件共同策略需要重新批准。项目范围仅含关联项目的图，分类范围仅含独立图，并适用于以后加入该范围的图；指定图仅限已有ID，不能新建或变更归属。读写同时受基本权限及资源交集限制，写入仍须完整提案预览与最严格确认方式。分类移除或重命名先撤去原分类授权，失败不恢复或扩大到未分类。项目正文、删除、分类与项目创建不在授权内。'}
            for ticket_id, value in list(self.runtime.preview_tickets.items()):
                if 'graph_grant_preview' in value and value.get('expires', 0) < time.monotonic():
                    del self.runtime.preview_tickets[ticket_id]
            if len(self.runtime.preview_tickets) >= 100:
                raise AgentError('management_limit', '预览过多，请稍后或重启服务重试', 429)
            ticket = secrets.token_hex(32)
            self.runtime.preview_tickets[ticket] = {'graph_grant_preview': json.loads(json.dumps(preview)), 'digest': digest(preview),
                                                  'session': digest(self.runtime._token), 'expires': time.monotonic() + 600,
                                                  'runtime_version': self.runtime.status()['version']}
            return {**preview, 'preview_id': ticket, 'preview_digest': digest(preview)}

    def approve(self, key, payload):
        from .agent_management import credential_lock, digest
        if not isinstance(payload, dict) or set(payload) != {'workspace_id', 'preview_id', 'preview_digest', 'expected_version', 'request_id', 'approved'} or payload['approved'] is not True or payload['workspace_id'] != self.security.workspace_id or not isinstance(payload['request_id'], str) or not 1 <= len(payload['request_id']) <= 100 or not isinstance(payload['preview_id'], str) or not isinstance(payload['preview_digest'], str) or not re.fullmatch(r'[a-f0-9]{64}', payload['preview_digest']):
            raise AgentError('approval_required', '需要明确批准当前完整图授权预览')
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            manager = self.security.manager()
            operation_id = hashlib.sha256(payload['request_id'].encode()).hexdigest()
            # The persistent signature binds the original approval digest, client
            # and version. A lost response must work after ticket/session expiry.
            if (manager.directory / f'{operation_id}.json').exists():
                return manager.run('concept_map_grants', {'approval_digest': payload['preview_digest']}, key, payload['expected_version'], payload['request_id'])
            ticket = self.runtime.preview_tickets.get(payload['preview_id'], {})
            preview = ticket.get('graph_grant_preview', {})
            if ticket.get('expires', 0) < time.monotonic() or self.runtime._expires < time.monotonic() or ticket.get('session') != digest(self.runtime._token) or ticket.get('runtime_version') != self.runtime.status()['version'] or ticket.get('digest') != payload['preview_digest'] or digest(preview) != payload['preview_digest'] or preview.get('client_id') != key or preview.get('expected_version') != payload['expected_version']:
                raise AgentError('preview_expired', '图授权预览失效，请重新完整预览', 409)
            self.client(key, payload['expected_version'])
            if grant_dependencies(self.repository, preview['grants']) != preview['resource_dependencies']:
                raise AgentError('resource_changed', '图授权资源变化，请重新完整预览', 409)
            return manager.run('concept_map_grants', {'grants': preview['grants'], 'approval_digest': payload['preview_digest'],
                                                    'resource_dependencies': preview['resource_dependencies']},
                               key, payload['expected_version'], payload['request_id'])

    def revoke(self, key, payload):
        if not isinstance(payload, dict) or set(payload) != {'workspace_id', 'expected_version', 'request_id'} or payload['workspace_id'] != self.security.workspace_id:
            raise AgentError('invalid_request', '撤销图授权参数无效')
        with self.repository.write_lock:
            return self.security.manager().run('concept_map_grants_revoke', {}, key, payload['expected_version'], payload['request_id'])
