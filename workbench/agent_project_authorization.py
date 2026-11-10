"""Fresh creation capability, separate from access to existing projects."""

import hashlib
import re
import secrets
import time

from .agent_security import AgentError


def grant_value(enabled):
    return {'schema_version':1, 'capability':'projects.create', 'operations':['create'],
            'minimum_confirmation_mode':'local_web', 'enabled':enabled}


def normalize_project_create_grant(value):
    if not isinstance(value, dict) or type(value.get('schema_version')) is not int or type(value.get('enabled')) is not bool or value != grant_value(value['enabled']):
        raise ValueError('项目创建授权格式无效')
    return grant_value(value['enabled'])


def client_project_create_grant(client):
    if client.get('authorization_schema_version', 1) != 7:
        if 'project_create_grant' in client:
            raise AgentError('invalid_configuration', '旧授权不能包含已生效项目创建授权', 503)
        return grant_value(False)
    try:
        return normalize_project_create_grant(client['project_create_grant'])
    except (KeyError, ValueError, TypeError):
        raise AgentError('invalid_configuration', '项目创建授权无效，停止使用', 503) from None


def can_create_project(client):
    from . import agent_file_handles
    return bool(agent_file_handles.SUPPORTED and client.get('enabled') is True and
                {'read', 'propose', 'commit'} <= set(client.get('scopes', [])) and
                client_project_create_grant(client)['enabled'])


def creation_confirmation_mode(requested=None):
    if requested not in (None, 'local_web'):
        raise AgentError('confirmation_required', '项目创建只接受本机管理页面完整预览后的独立批准', 409)
    return 'local_web'


def upgraded_project_client(before, grant):
    result = {**before, 'authorization_schema_version':7,
              'project_create_grant':normalize_project_create_grant(grant),
              'management_revision':before.get('management_revision', 0) + 1}
    for field in ('concept_map_grants', 'delete_grants'):
        result.setdefault(field, {'schema_version':1, 'grants':[]})
    return result


def validate_project_grant_intent(value):
    if value.get('operation_family') != 'project_create':
        return
    from .agent_management import digest
    try:
        action = value['project_grant_action']
        if value['schema_version'] != 7 or action not in {'approve', 'revoke'} or not re.fullmatch(r'[0-9a-f]{64}', value['project_grant_digest']):
            raise ValueError()
        if value['state'] in {'prepared', 'recovery_required'}:
            before, after = value['before_client'], value['after_client']
            grant = grant_value(action == 'approve')
            if value['before_config'] != value['after_config'] or before['client_id'] != value['client_id'] or after != upgraded_project_client(before, grant) or digest(grant) != value['project_grant_digest']:
                raise ValueError()
            if action == 'approve' and (before['enabled'] is not True or not {'read', 'propose', 'commit'} <= set(before['scopes'])):
                raise ValueError()
            if action == 'revoke' and before.get('authorization_schema_version') != 7:
                raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise AgentError('management_recovery_required', '项目创建授权意图与客户端证据不一致', 503) from None


class ProjectCreateGrantManagement:
    def __init__(self, runtime):
        from .agent_delete_authorization import DeleteGrantManagement
        self.runtime = runtime
        self.client_management = DeleteGrantManagement(runtime)
        self.security = self.client_management.security
        self.repository = runtime.repository

    def list(self, key):
        from .agent_management import client_version
        client = self.client_management.client(key, enabled=False)
        return {'workspace_id':self.security.workspace_id, 'client_id':key,
                'expected_version':client_version(client), 'grant':client_project_create_grant(client)}

    def preview(self, key, payload):
        from .agent_management import credential_lock, digest
        from .project_directory import workspace_supported
        if not workspace_supported(self.repository.root):
            raise AgentError('unsupported_platform', '项目创建仅支持Windows固定NTFS卷', 503)
        self._check(payload, {'workspace_id', 'expected_version'})
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            client = self.client_management.client(key, payload['expected_version'])
            if not {'read', 'propose', 'commit'} <= set(client['scopes']):
                raise AgentError('forbidden', '项目创建需要完整基本权限', 403)
            preview = {**self.list(key), 'client_name':client['name'],
                       'after':grant_value(True), 'unchanged_project_ids':client['project_ids'],
                       'disclosure':'每次只创建一个新项目，必须由本机网页独立批准。该许可不扩大既有项目访问范围；既有通配权限原本可能覆盖新项目。授权版本改变，原版本绑定的暂存/附件策略需要重新批准。'}
            token = secrets.token_hex(32)
            now = time.monotonic()
            tickets = self.runtime.preview_tickets
            for old, ticket in list(tickets.items()):
                if ticket.get('expires', ticket.get('file_expiry', float('inf'))) <= now:
                    del tickets[old]
            if len(tickets) >= 1000:
                raise AgentError('preview_limit', '管理预览过多，请稍后重试', 429)
            value = digest(preview)
            tickets[token] = {'project_create_grant':True, 'client_id':key, 'version':payload['expected_version'],
                              'digest':value, 'session':self.runtime._token, 'runtime_version':self.runtime.status()['version'],
                              'expires':now + 600}
            return {**preview, 'preview_id':token, 'preview_digest':value}

    def approve(self, key, payload):
        from .agent_management import credential_lock
        self._check(payload, {'workspace_id', 'expected_version', 'preview_id', 'preview_digest', 'request_id', 'approved'})
        if payload['approved'] is not True or any(not isinstance(payload[field], str) or not re.fullmatch(r'[0-9a-f]{64}', payload[field]) for field in ('preview_id','preview_digest')):
            raise AgentError('invalid_request', '必须明确批准当前项目创建授权预览')
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            manager = self.security.manager()
            operation_id = hashlib.sha256(payload['request_id'].encode()).hexdigest()
            if not (manager.directory / f'{operation_id}.json').exists():
                ticket = self.runtime.preview_tickets.get(payload['preview_id'], {})
                if not ticket.get('project_create_grant') or ticket.get('expires', 0) <= time.monotonic() or ticket.get('client_id') != key or ticket.get('version') != payload['expected_version'] or ticket.get('digest') != payload['preview_digest'] or ticket.get('session') != self.runtime._token or ticket.get('runtime_version') != self.runtime.status()['version']:
                    raise AgentError('preview_expired', '项目创建授权预览失效，请重新核对', 409)
                self.client_management.client(key, payload['expected_version'])
            return manager.run('project_create_grant', {'approval_digest':payload['preview_digest']},
                               key, payload['expected_version'], payload['request_id'])

    def revoke(self, key, payload):
        self._check(payload, {'workspace_id', 'expected_version', 'request_id'})
        with self.repository.write_lock:
            return self.security.manager().run('project_create_grant_revoke', {}, key, payload['expected_version'], payload['request_id'])

    def _check(self, payload, keys):
        self.runtime.authorize(self.runtime._token)
        if not isinstance(payload, dict) or set(payload) != keys or payload['workspace_id'] != self.security.workspace_id or not isinstance(payload['expected_version'], str) or not re.fullmatch(r'[0-9a-f]{64}', payload['expected_version']) or 'request_id' in keys and (not isinstance(payload['request_id'], str) or not 1 <= len(payload['request_id']) <= 100):
            raise AgentError('invalid_request', '项目创建授权管理参数无效')
