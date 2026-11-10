"""Explicit fresh single-item deletion grants; dormant intents never activate."""

import re
import json
import hashlib
import secrets
import time
from pathlib import Path

from .agent_security import AgentError, normalize_capability_grants


EMPTY_DELETE_GRANTS = {'schema_version': 1, 'grants': []}
DELETE_KINDS = {'issue', 'todo', 'info', 'document', 'concept_map'}


def normalize_delete_grants(value):
    normalized = normalize_capability_grants(value)
    for grant in normalized['grants']:
        if grant['capability'] != 'items.delete' or grant['operations'] != ['delete'] or grant['minimum_confirmation_mode'] != 'local_web':
            raise ValueError('删除授权仅接受items.delete/delete/local_web')
        for resource in grant['resources']:
            if resource['type'] == 'concept_map' and not re.fullmatch(r'CMAP-[0-9]+', resource['id']):
                raise ValueError('指定图身份无效')
            if resource['type'] == 'item' and resource['kind'] not in {'issue', 'todo', 'info', 'document'}:
                raise ValueError('只支持四种Markdown条目删除')
    return normalized


def client_delete_grants(client):
    if client.get('authorization_schema_version', 1) not in (6, 7):
        if 'delete_grants' in client:
            raise AgentError('invalid_configuration', '旧授权不能包含已生效删除授权', 503)
        return {'schema_version': 1, 'grants': []}
    try:
        return normalize_delete_grants(client['delete_grants'])
    except (ValueError, TypeError, KeyError):
        raise AgentError('invalid_configuration', '删除授权格式无效，停止使用', 503) from None


def resource_matches(resource, item):
    kind = item.get('type')
    if kind not in DELETE_KINDS:
        return False
    if resource['type'] == 'item':
        return kind == resource['kind'] and item.get('id') == resource['id']
    if resource['type'] == 'project':
        return kind != 'document' and item.get('project_id') == resource['id']
    if resource['type'] == 'document_category':
        return kind == 'document' and item.get('category', '未分类') == resource['name']
    if resource['type'] == 'concept_map':
        return kind == 'concept_map' and item.get('id') == resource['id']
    return resource['type'] == 'concept_map_category' and kind == 'concept_map' and item.get('project_id') is None and item.get('category', '未分类') == resource['name']


def delete_allows(client, item):
    from .agent_security import allows
    from .deletion_prepared import supported
    if not supported() or client.get('enabled') is not True or not {'read', 'propose', 'commit'} <= set(client.get('scopes', [])):
        return False
    grants = client_delete_grants(client)['grants']
    return bool(grants) and allows(client, item) and any(resource_matches(resource, item) for grant in grants for resource in grant['resources'])


def deletion_confirmation_mode(requested=None):
    if requested not in (None, 'local_web'):
        raise AgentError('confirmation_required', '删除只接受本机管理页面完整预览后的独立批准', 409)
    return 'local_web'


def effective_kinds(repository, client):
    from .deletion_prepared import supported
    if not supported() or not client_delete_grants(client)['grants']:
        return []
    from .deletion_inventory import active_inventory
    try:
        entries, _ = active_inventory(repository.root)
        from .agent_file_handles import LocalFileHandle
        kinds = set()
        for entry in entries:
            if delete_allows(client, entry['item']):
                try:
                    with LocalFileHandle(str(repository.root / entry['relative_path'])):
                        kinds.add(entry['kind'])
                except AgentError:
                    continue
        return sorted(kinds)
    except (ValueError, OSError, TypeError, AgentError):
        return []  # Read/old business capabilities remain available; deletion fails closed.


def validate_narrowing(before, after):
    old = normalize_delete_grants(before)['grants']
    new = normalize_delete_grants(after)
    for grant in new['grants']:
        if not any(all(grant[key] == original[key] for key in ('capability', 'operations', 'minimum_confirmation_mode'))
                   and all(resource in original['resources'] for resource in grant['resources']) for original in old):
            raise ValueError('收窄不能增加删除资源或降低确认方式')
    return new


def grant_dependencies(repository, grants):
    from .deletion_inventory import active_inventory, fingerprint
    from .deletion_prepared import controlled
    from .write_coordinator import content_revision
    root = repository.root if hasattr(repository, '_record_repository') else Path(repository).resolve()
    entries, catalog_digest = active_inventory(root)
    configs = {}
    for name in ('document-categories', 'concept-map-categories'):
        path = controlled(root, f'config/{name}.json', required=False)
        raw = path.read_bytes() if path.exists() else b''
        value = json.loads(raw.decode('utf-8')) if raw else []
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError('删除资源分类配置损坏')
        configs[name] = (value, content_revision(raw))
    resources = {json.dumps(resource, sort_keys=True):resource for grant in normalize_delete_grants(grants)['grants'] for resource in grant['resources']}
    result = []
    for _, resource in sorted(resources.items()):
        kind = resource['type']
        if kind in {'project', 'item', 'concept_map'}:
            expected = resource.get('kind') if kind == 'item' else kind
            entry = next((item for item in entries if item['id'] == resource['id'] and item['kind'] == expected), None)
            if entry is None:
                raise AgentError('resource_changed', '删除授权资源不存在或不受支持，请重新预览', 409)
            revision = entry['revision']
        else:
            config = configs['document-categories' if kind == 'document_category' else 'concept-map-categories']
            names = set(config[0]) | {'未分类'}
            names.update(item['item'].get('category', '未分类') for item in entries if item['kind'] == ('document' if kind == 'document_category' else 'concept_map'))
            if resource['name'] not in names:
                raise AgentError('resource_changed', '删除授权分类不存在，请重新预览', 409)
            revision = config[1]
        members = sorted((item['kind'], item['id'], item['revision']) for item in entries if resource_matches(resource, item['item']))
        result.append({'resource':resource, 'revision':revision, 'members_digest':fingerprint(members), 'count':len(members)})
    return {'schema_version':1, 'catalog_digest':fingerprint([catalog_digest, configs]), 'resources':result}


def validate_grant_dependencies(value, grants):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'catalog_digest', 'resources'} or type(value['schema_version']) is not int or value['schema_version'] != 1 or not isinstance(value['catalog_digest'], str) or not re.fullmatch(r'[a-f0-9]{64}', value['catalog_digest']) or not isinstance(value['resources'], list):
        raise ValueError('删除授权依赖格式无效')
    expected = {json.dumps(resource, sort_keys=True) for grant in normalize_delete_grants(grants)['grants'] for resource in grant['resources']}
    seen = set()
    for item in value['resources']:
        if not isinstance(item, dict) or set(item) != {'resource', 'revision', 'members_digest', 'count'} or type(item['count']) is not int or item['count'] < 0:
            raise ValueError('删除授权资源依赖无效')
        for key in ('revision', 'members_digest'):
            if not isinstance(item[key], str) or not re.fullmatch(r'[a-f0-9]{64}', item[key]):
                raise ValueError('删除授权资源摘要无效')
        key = json.dumps(item['resource'], sort_keys=True)
        if key not in expected or key in seen:
            raise ValueError('删除授权资源集合不一致')
        seen.add(key)
    if seen != expected:
        raise ValueError('删除授权资源集合不完整')


def restrict_delete_categories(repository, names, resource_type):
    """Remove named scopes before a category can disappear or be reused."""
    if resource_type not in {'document_category', 'concept_map_category'}:
        raise ValueError('删除授权分类类型无效')
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
        grants = client_delete_grants(client)
        narrowed = []
        for grant in grants['grants']:
            resources = [resource for resource in grant['resources'] if not (resource['type'] == resource_type and resource['name'] in names)]
            if resources:
                narrowed.append({**grant, 'resources':resources})
        if narrowed != grants['grants']:
            manager.run('delete_grants_narrow', {'grants':{'schema_version':1, 'grants':narrowed}}, client['client_id'], client_version(client))


class DeleteGrantManagement:
    """Local management previews use the existing runtime tickets and journal."""

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
        from .deletion_inventory import active_inventory
        client = self.client(key, enabled=False)
        entries, _ = active_inventory(self.repository.root)
        items = [{key:entry['item'].get(key) for key in ('id', 'type', 'title', 'project_id', 'category')}
                 for entry in entries if entry['kind'] in DELETE_KINDS]
        return {'workspace_id':self.security.workspace_id, 'client_id':key, 'expected_version':client_version(client),
                'grants':client_delete_grants(client), 'items':items,
                'projects':[{'id':item['id'], 'name':item['name']} for item in self.repository.list_projects()],
                'document_categories':self.repository.document_categories(), 'concept_map_categories':self.repository.concept_map_categories()}

    def preview(self, key, payload):
        from .agent_management import credential_lock, client_version, digest
        from .deletion_inventory import active_inventory
        from .deletion_prepared import require_platform
        require_platform()
        if not isinstance(payload, dict) or set(payload) != {'workspace_id', 'expected_version', 'grants'} or payload['workspace_id'] != self.security.workspace_id or not isinstance(payload['expected_version'], str) or not re.fullmatch(r'[a-f0-9]{64}', payload['expected_version']):
            raise AgentError('invalid_request', '删除授权预览字段无效')
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            client = self.client(key, payload['expected_version'])
            grants = normalize_delete_grants(payload['grants'])
            if not grants['grants'] or not {'read', 'propose', 'commit'} <= set(client['scopes']):
                raise AgentError('forbidden', '请选择具体删除范围并核对完整基本权限', 403)
            dependencies = grant_dependencies(self.repository, grants)
            entries, _ = active_inventory(self.repository.root)
            resources = []
            for dependency in dependencies['resources']:
                members = [{**{name:entry['item'].get(name) for name in ('id', 'type', 'title', 'project_id', 'category')}, 'revision':entry['revision']}
                           for entry in entries if resource_matches(dependency['resource'], entry['item'])]
                resources.append({**dependency, 'items':members})
            preview = {'workspace_id':self.security.workspace_id, 'client_id':key, 'client_name':client['name'],
                       'expected_version':client_version(client), 'grants':grants, 'resources':resources,
                       'resource_dependencies':dependencies, 'scopes':client['scopes'], 'kinds':client['kinds'],
                       'minimum_confirmation_mode':'local_web',
                       'disclosure':'替代全部删除授权；不会启用旧休眠items.delete，不增加类型或读取权限。仅四种Markdown条目与概念图，需原完整读取及read/propose/commit与具体范围交集，图仍需单独读取授权。每次删除必须完整影响预览后由本机网页独立批准，不能用对话自报确认替代。删除只移入回收站，默认30天保留，本机可提前永久删除；附件/历史/其他正文保留。无项目级联/恢复/永久删除/清空回收站/孤儿清理Agent能力。仅支持Windows本机固定NTFS。授权变更使当前client_version绑定的上传/附件策略需重新批准。'}
            if len(json.dumps(preview, ensure_ascii=False, allow_nan=False).encode('utf-8')) > 2097152:
                raise AgentError('preview_too_large', '完整删除授权预览超过2MiB，请缩小范围')
            for ticket_id, value in list(self.runtime.preview_tickets.items()):
                if 'delete_grant_preview' in value and value.get('expires', 0) < time.monotonic():
                    del self.runtime.preview_tickets[ticket_id]
            if len(self.runtime.preview_tickets) >= 100:
                raise AgentError('management_limit', '预览过多，请稍后或重启服务重试', 429)
            ticket = secrets.token_hex(32)
            response = {**preview, 'preview_id':ticket, 'preview_digest':digest(preview)}
            if len(json.dumps(response, ensure_ascii=False, allow_nan=False).encode('utf-8')) > 2097152:
                raise AgentError('preview_too_large', '完整删除授权预览超过2MiB，请缩小范围')
            self.runtime.preview_tickets[ticket] = {'delete_grant_preview':json.loads(json.dumps(preview)), 'digest':digest(preview),
                                                  'session':digest(self.runtime._token), 'expires':time.monotonic() + 600,
                                                  'runtime_version':self.runtime.status()['version']}
            return response

    def approve(self, key, payload):
        from .agent_management import credential_lock, digest
        from .deletion_prepared import require_platform
        require_platform()
        if not isinstance(payload, dict) or set(payload) != {'workspace_id', 'preview_id', 'preview_digest', 'expected_version', 'request_id', 'approved'} or payload['approved'] is not True or payload['workspace_id'] != self.security.workspace_id or not isinstance(payload['request_id'], str) or not 1 <= len(payload['request_id']) <= 100 or not isinstance(payload['preview_id'], str) or not isinstance(payload['preview_digest'], str) or not re.fullmatch(r'[a-f0-9]{64}', payload['preview_digest']):
            raise AgentError('approval_required', '需要明确批准当前完整删除授权预览')
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            manager = self.security.manager()
            operation_id = hashlib.sha256(payload['request_id'].encode()).hexdigest()
            if (manager.directory / f'{operation_id}.json').exists():
                return manager.run('delete_grants', {'approval_digest':payload['preview_digest']}, key, payload['expected_version'], payload['request_id'])
            ticket = self.runtime.preview_tickets.get(payload['preview_id'], {})
            preview = ticket.get('delete_grant_preview', {})
            if ticket.get('expires', 0) < time.monotonic() or self.runtime._expires < time.monotonic() or ticket.get('session') != digest(self.runtime._token) or ticket.get('runtime_version') != self.runtime.status()['version'] or ticket.get('digest') != payload['preview_digest'] or digest(preview) != payload['preview_digest'] or preview.get('client_id') != key or preview.get('expected_version') != payload['expected_version']:
                raise AgentError('preview_expired', '删除授权预览失效，请重新完整预览', 409)
            self.client(key, payload['expected_version'])
            if grant_dependencies(self.repository, preview['grants']) != preview['resource_dependencies']:
                raise AgentError('resource_changed', '删除授权资源变化，请重新完整预览', 409)
            return manager.run('delete_grants', {'grants':preview['grants'], 'approval_digest':payload['preview_digest'],
                                               'resource_dependencies':preview['resource_dependencies']}, key, payload['expected_version'], payload['request_id'])

    def revoke(self, key, payload):
        if not isinstance(payload, dict) or set(payload) != {'workspace_id', 'expected_version', 'request_id'} or payload['workspace_id'] != self.security.workspace_id:
            raise AgentError('invalid_request', '撤销删除授权参数无效')
        with self.repository.write_lock:
            return self.security.manager().run('delete_grants_revoke', {}, key, payload['expected_version'], payload['request_id'])
