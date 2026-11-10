"""Local-only workflow grant preview and approval."""

import secrets
import time

from .agent_category_management import CategoryGrantManagement
from .agent_delete_service import checked_preview
from .agent_execution import fingerprint
from .agent_management import client_version, credential_lock
from .agent_security import AgentError
from .agent_workflow_authorization import SCOPES, STATUS_OPS, client_grants, grant_from_selection


class WorkflowGrantManagement(CategoryGrantManagement):
    ticket_key = 'workflow_preview'
    approve_action = 'workflow_grant'
    revoke_action = 'workflow_grant_revoke'

    def list(self, key):
        client = self.management.client(key, enabled=False)
        return {'workspace_id':self.security.workspace_id, 'client_id':key, 'expected_version':client_version(client),
                'grants':client_grants(client),
                'templates':[{'id':item['id'], 'name':item['name']} for item in self.repository.config()['workflow_templates']],
                'projects':[{'id':item['id'], 'name':item['name']} for item in self.repository.list_projects()]}

    def preview(self, key, payload):
        self._check(payload, ('selection',))
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            client = self.management.client(key, payload['expected_version'])
            if not SCOPES <= set(client['scopes']):
                raise AgentError('forbidden', '工作流授权需要读取、提案及提交权限', 403)
            grant = grant_from_selection(self.repository.root, payload['selection'], client=client)
            disclosure = '授权仅覆盖所示模板和操作。实际内容仍受已有读取权限限制，每次都须本机独立批准。'
            if grant['operation'] in STATUS_OPS:
                disclosure += '此许可覆盖该模板中所选记录类型的当前和以后合法状态；每案仍核对具体状态。'
            if grant['operation'] in {'create','copy','switch'}:
                disclosure += '许可在对应名称激活或项目切换时消费。'
            preview = {**self.list(key), 'client_name':client['name'], 'grant':grant, 'disclosure':disclosure}
            token, signature, now = secrets.token_hex(32), fingerprint(preview), time.monotonic()
            tickets = self.runtime.preview_tickets
            for old, ticket in list(tickets.items()):
                if ticket.get('expires', ticket.get('file_expiry', float('inf'))) <= now:
                    del tickets[old]
            if len(tickets) >= 1000:
                raise AgentError('preview_limit', '管理预览过多，请稍后重试', 429)
            result = checked_preview({**preview, 'preview_id':token, 'preview_digest':signature})
            tickets[token] = {self.ticket_key:preview, 'digest':signature, 'session':self.runtime._token,
                              'runtime_version':self.runtime.status()['version'], 'expires':now + 600}
            return result
