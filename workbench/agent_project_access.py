"""Separate, exact project-scope approval tied to the original creation receipt."""

import hashlib
import re
import secrets
import time
import uuid
from contextlib import contextmanager

from .agent_execution import fingerprint, validate_action, validate_context
from .agent_project_authorization import can_create_project
from .agent_project_execution import validate_execution
from .agent_security import AgentError
from .deletion_prepared import read_handle
from .agent_file_handles import LocalFileHandle
from .markdown_io import load_markdown_text
from .project_directory import _ProjectDirectoryHandle, physical_identity
from .project_identity import controlled, load_unique_json, read_bounded, valid_new_id
from .write_coordinator import content_revision


def _read(root, path):
    return load_unique_json(read_bounded(controlled(root, root / path), limit=4194304))


@contextmanager
def project_access_evidence(security, proposal_id, client_id):
    """Pin the original directory and current README until scope publication."""
    root = security.root
    try:
        if str(uuid.UUID(proposal_id)) != proposal_id:
            raise ValueError()
        proposal = _read(root, f'.agent/proposals/{proposal_id}.json')
        if proposal['proposal_id'] != proposal_id or proposal['state'] != 'committed' or proposal['kind'] != 'project' or proposal['client_id'] != client_id or proposal['workspace_id'] != security.workspace_id:
            raise ValueError()
        validate_context(proposal)
        operation_id = f"{proposal_id}-{proposal['version']}"
        manifest = _read(root, f'.agent/operations/{operation_id}/manifest.json')
        validate_execution(None, manifest, proposal)
        receipt = _read(root, f'.agent/receipts/{proposal_id}.json')
        if manifest['schema_version'] != 3 or manifest['state'] != 'committed' or manifest['workspace_id'] != security.workspace_id or manifest['operation_id'] != operation_id or manifest['proposal_id'] != proposal_id or manifest['version'] != proposal['version'] or manifest['receipt'] != receipt or proposal['receipt'] != receipt:
            raise ValueError()
        approval = manifest['approval']['operation_id']
        if not re.fullmatch(r'[a-f0-9]{64}', approval):
            raise ValueError()
        action = _read(root, f'.agent/proposal-actions/{approval}.json')
        validate_action(action, approval)
        if action['schema_version'] != 3 or action['workspace_id'] != security.workspace_id or action['approval'] != manifest['approval'] or action['state'] not in {'approved','completed'} or action['business_operation_id'] != operation_id or action['state'] == 'completed' and action['result'] != receipt:
            raise ValueError()
        project_id = manifest['item_id']
        folder = controlled(root, root / 'projects' / project_id)
        readme_path = controlled(root, folder / 'README.md')
        with _ProjectDirectoryHandle(str(folder)) as directory, LocalFileHandle(str(readme_path), read=True) as readme:
            if physical_identity(directory) != manifest['stage_identity']:
                raise ValueError()
            raw = read_handle(readme)
            meta, _ = load_markdown_text(raw.decode('utf-8'))
            if meta.get('type') != 'project' or meta.get('id') != project_id:
                raise ValueError()
            yield {'proposal_id':proposal_id, 'project_id':project_id, 'receipt_digest':fingerprint(receipt),
                   'project_revision':content_revision(raw), 'identity':manifest['stage_identity']}
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        raise AgentError('project_access_unavailable', '原已创建项目无法核验，不能授予访问范围', 409) from None


def access_client_after(before, evidence):
    key = evidence['project_id']
    if not can_create_project(before) or '*' in before['project_ids'] or key in before['project_ids']:
        raise ValueError('当前客户端不能追加或已具备该项目范围')
    return {**before, 'project_ids':[*before['project_ids'],key],
            'management_revision':before.get('management_revision',0) + 1}


def validate_access_intent(value):
    if value.get('operation_family') != 'project_access':
        return
    try:
        evidence = value['project_access_evidence']
        if value['schema_version'] != 7 or set(evidence) != {'proposal_id','project_id','receipt_digest','project_revision','identity'} or str(uuid.UUID(evidence['proposal_id'])) != evidence['proposal_id'] or any(not re.fullmatch(r'[a-f0-9]{64}', evidence[name]) for name in ('receipt_digest','project_revision')):
            raise ValueError()
        if valid_new_id(evidence['project_id']) != evidence['project_id'].casefold() or set(evidence['identity']) != {'volume','index','created'} or any(type(v) is not int or v < 0 for v in evidence['identity'].values()):
            raise ValueError()
        if value['state'] in {'prepared','recovery_required'}:
            from .agent_management import client_version
            before = value['before_client']
            if value['before_config'] != value['after_config'] or before['client_id'] != value['client_id'] or value['after_client'] != access_client_after(before,evidence):
                raise ValueError()
            if value['result']['version'] != client_version(value['after_client']) or value['result']['client_id'] != value['client_id']:
                raise ValueError()
        if value['state'] != 'abandoned' and (value['result']['project_id'] != evidence['project_id'] or value['result']['proposal_id'] != evidence['proposal_id']):
            raise ValueError()
    except (KeyError, ValueError, TypeError, AttributeError, AgentError):
        raise AgentError('management_recovery_required', '项目范围授权意图与原项目或客户端证据不一致', 503) from None


class ProjectAccessManagement:
    def __init__(self, runtime):
        from .agent_proposal_management import ProposalManagement
        self.runtime = runtime
        self.proposals = ProposalManagement(runtime)
        self.proposals._require_store()
        self.security = runtime.security()

    def preview(self, proposal_id):
        from .agent_management import client_version, clean_client, credential_lock, digest
        self.runtime.authorize(self.runtime._token)
        proposal = self.proposals._require_store()._load(proposal_id, expire=False)
        key = proposal['client_id']
        with self.runtime.repository.write_lock, credential_lock(self.security.config_dir):
            current = self.security.clients().get(key)
            if not current or not can_create_project(current) or key in self.security.manager().blocked_clients():
                raise AgentError('forbidden', '原客户端授权不可用，项目仍保留', 403)
            with project_access_evidence(self.security, proposal_id, key) as evidence:
                already = evidence['project_id'] in current['project_ids'] or '*' in current['project_ids']
                preview = {'workspace_id':self.security.workspace_id, 'proposal_id':proposal_id, 'client_id':key,
                           'project_id':evidence['project_id'], 'already_covered':already,
                           'expected_version':client_version(current), 'before':clean_client(current),
                           'after':clean_client(current if already else access_client_after(current,evidence)),
                           'disclosure':'仅追加此项目的精确范围。客户端已有类型、读取、提案及提交权限将按各能力规则在此范围内适用；不增加类型或基本权限。原版本绑定的暂存/附件策略需要重新批准。项目创建结果独立保留。'}
                if already:
                    return preview
                token = secrets.token_hex(32)
                value = digest([preview, evidence])
                now = time.monotonic()
                tickets = self.runtime.preview_tickets
                for old, ticket in list(tickets.items()):
                    if ticket.get('expires', float('inf')) <= now:
                        del tickets[old]
                if len(tickets) >= 1000:
                    raise AgentError('preview_limit', '管理预览过多，请稍后重试', 429)
                tickets[token] = {'project_access':True, 'client_id':key, 'version':preview['expected_version'],
                                  'proposal_id':proposal_id, 'digest':value, 'session':self.runtime._token,
                                  'evidence':evidence, 'runtime_version':self.runtime.status()['version'], 'expires':now + 600}
                return {**preview, 'preview_id':token, 'preview_digest':value}

    def approve(self, proposal_id, payload):
        from .agent_management import credential_lock
        from .agent_proposal_management import ProposalManagement
        self.runtime.authorize(self.runtime._token)
        if not isinstance(payload, dict) or set(payload) != {'workspace_id','expected_version','preview_id','preview_digest','request_id','approved'} or payload['workspace_id'] != self.security.workspace_id or payload['approved'] is not True or any(not isinstance(payload[f],str) or not re.fullmatch(r'[a-f0-9]{64}', payload[f]) for f in ('expected_version','preview_id','preview_digest')):
            raise AgentError('invalid_request', '必须明确批准当前项目范围预览')
        operation_id = ProposalManagement.request_key(payload['request_id'])
        proposal = self.proposals._require_store()._load(proposal_id, expire=False)
        key = proposal['client_id']
        with self.runtime.repository.write_lock, credential_lock(self.security.config_dir):
            manager = self.security.manager()
            path = manager.directory / f'{operation_id}.json'
            if path.exists():
                evidence = manager._load(path).get('project_access_evidence')
                if not evidence or evidence['proposal_id'] != proposal_id:
                    raise AgentError('request_conflict', '请求编号已用于其他管理操作', 409)
            else:
                ticket = self.runtime.preview_tickets.get(payload['preview_id'], {})
                if not ticket.get('project_access') or ticket.get('client_id') != key or ticket.get('proposal_id') != proposal_id or ticket.get('version') != payload['expected_version'] or ticket.get('digest') != payload['preview_digest'] or ticket.get('session') != self.runtime._token or ticket.get('expires', 0) <= time.monotonic() or ticket.get('runtime_version') != self.runtime.status()['version']:
                    raise AgentError('preview_expired', '项目访问授权预览已失效', 409)
                evidence = ticket['evidence']
            return manager.run('project_access_grant', {'approval_digest':payload['preview_digest'], 'evidence':evidence},
                               key, payload['expected_version'], payload['request_id'])
