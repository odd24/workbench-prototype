"""Local management tickets for exact category operations."""

import hashlib
import re
import secrets
import time

from .agent_category_authorization import HASH, REQUIRED, client_grants, grant_from_selection
from .agent_delete_service import checked_preview
from .agent_execution import fingerprint
from .agent_management import client_version, credential_lock
from .agent_project_delete_authorization import ProjectDeleteGrantManagement
from .agent_security import AgentError


class CategoryGrantManagement(ProjectDeleteGrantManagement):
    def list(self, key):
        client = self.management.client(key, enabled=False)
        return {'workspace_id':self.security.workspace_id, 'client_id':key, 'expected_version':client_version(client),
                'grants':client_grants(client), 'projects':[{'id':item['id'], 'name':item['name']} for item in self.repository.list_projects()]}

    def preview(self, key, payload):
        self._check(payload, ('selection',))
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            client = self.management.client(key, payload['expected_version'])
            if not REQUIRED <= set(client['scopes']):
                raise AgentError('forbidden', '分类授权需要读取、提案及提交基本权限', 403)
            grant = grant_from_selection(self.repository, payload['selection'])
            preview = {**self.list(key), 'client_name':client['name'], 'grant':grant,
                       'disclosure':'只授予所示分类操作。每次变更仍需完整影响预览和本机独立批准。实际内容仍按已有权限读取。'}
            token, signature, now = secrets.token_hex(32), fingerprint(preview), time.monotonic()
            tickets = self.runtime.preview_tickets
            for old, ticket in list(tickets.items()):
                if ticket.get('expires', ticket.get('file_expiry', float('inf'))) <= now:
                    del tickets[old]
            if len(tickets) >= 1000:
                raise AgentError('preview_limit', '管理预览过多，请稍后重试', 429)
            result = checked_preview({**preview, 'preview_id':token, 'preview_digest':signature})
            tickets[token] = {'category_preview':preview, 'digest':signature, 'session':self.runtime._token,
                              'runtime_version':self.runtime.status()['version'], 'expires':now + 600}
            return result

    def approve(self, key, payload):
        self._check(payload, ('preview_id', 'preview_digest', 'request_id', 'approved'))
        if payload['approved'] is not True or any(not isinstance(payload[field], str) or not HASH.fullmatch(payload[field]) for field in ('preview_id', 'preview_digest')) or not isinstance(payload['request_id'], str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', payload['request_id']):
            raise AgentError('invalid_request', '必须批准当前完整分类授权预览')
        params = {'approval_digest':payload['preview_digest']}
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            manager = self.security.manager()
            operation_id = hashlib.sha256(payload['request_id'].encode()).hexdigest()
            if not (manager.directory / f'{operation_id}.json').exists():
                ticket = self.runtime.preview_tickets.get(payload['preview_id'], {})
                preview = ticket.get('category_preview', {})
                if ticket.get('expires', 0) <= time.monotonic() or ticket.get('session') != self.runtime._token or ticket.get('runtime_version') != self.runtime.status()['version'] or ticket.get('digest') != payload['preview_digest'] or fingerprint(preview) != payload['preview_digest'] or preview.get('client_id') != key or preview.get('expected_version') != payload['expected_version']:
                    raise AgentError('preview_expired', '分类授权预览已变化，请重新核对', 409)
                self.management.client(key, payload['expected_version'])
                params['grant'] = preview['grant']
            return manager.run('category_grant', params, key, payload['expected_version'], payload['request_id'])

    def revoke(self, key, payload):
        self._check(payload, ('request_id',))
        with self.repository.write_lock:
            return self.security.manager().run('category_grant_revoke', {}, key, payload['expected_version'], payload['request_id'])
