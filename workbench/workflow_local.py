"""Ordinary local workflow previews and legacy API adapters."""

import re
import secrets
import time
import uuid
from contextlib import nullcontext
from datetime import datetime

from .agent_category_service import security_for
from .agent_delete_service import checked_preview
from .agent_management import credential_lock
from .agent_security import AgentError
from .agent_workflow_service import candidate
from .category_local import commit_local_origin
from .markdown_io import now_iso
from .workflow_prepared import apply_workflow_files
from .write_coordinator import RevisionConflict


def _security(repository):
    security = security_for(repository)
    if security is None and (repository.root / '.agent' / 'workspace.json').exists():
        raise AgentError('authorization_unavailable','已初始化空间需要匹配的私人配置',503)
    return security


def _lock(security):
    return credential_lock(security.config_dir) if security else nullcontext()


def _legacy(operation, command):
    if operation not in {'compat_catalogue','compat_status'}:
        return None
    if not isinstance(command, dict) or command.keys() != {'templates'}:
        raise ValueError('兼容工作流变更需要完整原格式候选')
    if operation == 'compat_catalogue':
        return command['templates'], None
    return None, command['templates']


def _bundle(repository, security, operation, command, epoch, stamp, allocated_id, project_patch):
    if security and security.manager().blocked_clients():
        raise AgentError('management_recovery_required','请先核查未完成的授权操作',503)
    return candidate(repository, security, operation, command, epoch, stamp, allocated_id=allocated_id,
                     legacy=_legacy(operation, command), project_patch=project_patch)


def preview(repository, payload):
    if (not isinstance(payload, dict) or not {'operation','selection'} <= payload.keys()
            or payload.keys() - {'operation','selection','project_patch'} or not isinstance(payload['operation'], str)):
        raise ValueError('工作流预览需要受控操作与选择')
    operation, command = payload['operation'], payload['selection']
    patch = payload.get('project_patch', {})
    if not isinstance(patch, dict) or patch.keys() - {'name','description'} or (patch and operation != 'switch'):
        raise ValueError('项目切换只能同时修改名称和说明')
    security = _security(repository)
    epoch = str(uuid.uuid5(uuid.NAMESPACE_URL, security.workspace_id)) if security else str(uuid.uuid4())
    allocated = ('state-' if operation == 'add_status' else 'workflow-') + uuid.uuid4().hex if operation in {'create','copy','add_status'} else None
    managed_time = now_iso()
    with _lock(security):
        plan, impact, dependencies, local, _, _ = _bundle(repository, security, operation, command, epoch, managed_time, allocated, patch)
    now, token = time.monotonic(), secrets.token_hex(32)
    tickets = repository.workflow_preview_tickets
    for key, ticket in list(tickets.items()):
        if ticket['expires'] <= now:
            del tickets[key]
    if len(tickets) >= 100:
        raise AgentError('preview_limit','工作流预览过多，请稍后再试',429)
    result = checked_preview({'ticket':token, 'impact':impact, 'local':local, 'approvable':not plan.unmapped})
    tickets[token] = {'expires':now + 600, 'workspace':security.workspace_id if security else None,
                      'impact':impact, 'dependencies':dependencies, 'operation':operation,
                      'selection':command, 'epoch':epoch, 'stamp':managed_time, 'allocated':allocated, 'patch':patch}
    return result


def _publish(repository, security, bundle, token):
    plan = bundle[0]
    if plan.unmapped:
        raise AgentError('mapping_required','使用中状态需要显式映射，请重新预览',409)
    if security:
        return commit_local_origin(repository, bundle, token, kind='workflow')
    version = datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + token[:8]
    apply_workflow_files(repository.root, plan.files, plan.watch, history_version=version,
                         invalidate=repository._forget_record)
    return {'kind':'workflow','operation':plan.operation,'scope':bundle[1]['selection']}


def _replay(repository, token):
    runtime = getattr(repository, 'agent_runtime', None)
    store = getattr(repository, 'agent_proposals', None)
    if runtime and store:
        from .agent_proposal_management import ProposalManagement
        management = ProposalManagement(runtime)
        path = management._action_path(token)
        if path.exists():
            action = management._load_approval(path)
            proposal = store._load(action['proposal_id'], expire=False)
            if not proposal.get('local_workflow_origin'):
                raise AgentError('preview_expired','工作流预览已失效',409)
            result = management.action(token)
            if result['state'] == 'completed':
                return result['receipt']
            raise AgentError('workflow_action_' + result['state'],'请在提案管理中核查原工作流操作',409)
    return None


def approve(repository, payload):
    if (not isinstance(payload, dict) or payload.keys() != {'ticket'} or not isinstance(payload['ticket'], str)
            or not re.fullmatch(r'[0-9a-f]{64}', payload['ticket'])):
        raise ValueError('工作流批准需要当前完整预览票据')
    token = payload['ticket']
    replay = _replay(repository, token)
    if replay is not None:
        return replay
    ticket = repository.workflow_preview_tickets.get(token)
    if not ticket or ticket['expires'] <= time.monotonic():
        raise AgentError('preview_expired','工作流预览已失效，请重新核对',409)
    if 'receipt' in ticket:
        return ticket['receipt']
    repository.document_uploads.guard()
    if repository.write_guard:
        repository.write_guard()
    security = _security(repository)
    if ticket['workspace'] != (security.workspace_id if security else None):
        raise RevisionConflict('工作空间授权在预览后变化')
    with _lock(security):
        bundle = _bundle(repository, security, ticket['operation'], ticket['selection'], ticket['epoch'],
                         ticket['stamp'], ticket['allocated'], ticket['patch'])
        if bundle[1] != ticket['impact'] or bundle[2] != ticket['dependencies']:
            raise RevisionConflict('工作流、活动集合或授权在预览后变化')
        receipt = _publish(repository, security, bundle, token)
        repository.workflow_preview_tickets[token] = {'expires':ticket['expires'],'receipt':receipt}
        return receipt


def legacy_write(repository, operation, command, *, require_preview=False, project_patch=None):
    security = _security(repository)
    epoch = str(uuid.uuid5(uuid.NAMESPACE_URL, security.workspace_id)) if security else str(uuid.uuid4())
    with _lock(security):
        bundle = _bundle(repository, security, operation, command, epoch, now_iso(), None, project_patch)
        plan = bundle[0]
        if plan.unmapped:
            name = plan.unmapped[0]['source_status']
            if operation == 'compat_catalogue' and not require_preview:
                raise ValueError(f'状态「{name}」正在被使用，请为记录显式选择同类型目标')
            raise AgentError('mapping_required','使用中状态需要显式映射，请打开工作流迁移预览',409)
        if require_preview and plan.substantive:
            raise AgentError('workflow_preview_required','此工作流变更影响活动项目或记录，请先完整预览并本机批准',409)
        if plan.files:
            _publish(repository, security, bundle, secrets.token_hex(32))
        if operation == 'switch':
            return repository.project(command['project_id'])
        return plan.catalogue_after if operation == 'compat_catalogue' else plan.fallback_after


def history_state(repository, record_id, payload, resolution):
    from .workflow_changes import STATE_TYPES, effective_template, find_status, record_after, validate_catalogue
    record, _ = repository.get_record(record_id)
    if record is None:
        raise FileNotFoundError(record_id)
    kind = record['type']
    if kind not in STATE_TYPES:
        if resolution is not None:
            raise ValueError('无状态记录不能选择恢复状态')
        return payload
    config = repository.config()
    project = repository.project(record.get('project_id')) if record.get('project_id') else {}
    current = effective_template(project or {}, validate_catalogue(config['workflow_templates']), config['status_templates'])
    statuses = current['statuses'][kind] if current is not None else []
    old = payload.get('status')
    chosen = next((status for status in statuses if status['name'] == old), None)
    if resolution is not None:
        if not isinstance(resolution, dict):
            raise ValueError('历史状态恢复选择无效')
        if resolution == {'mode':'keep_current'}:
            return {key:value for key,value in payload.items() if key not in {'status','completed'}}
        if resolution.keys() != {'mode','status_id'} or resolution['mode'] != 'replace':
            raise ValueError('历史状态恢复选择无效')
        chosen = find_status(statuses, resolution['status_id'])
    if chosen is None:
        raise AgentError('history_workflow_resolution_required','原历史状态不适用于当前工作流，请明确选择有效状态或保留当前状态',409,
                         details={'historical_status':old,'current_status':record.get('status'),
                                  'statuses':[{'id':status['id'],'name':status['name'],'terminal':bool(status.get('completed'))}
                                              for status in statuses]})
    resolved = record_after({'type':kind, **({'completed':record['completed']} if 'completed' in record else {})}, chosen)
    payload = {key:value for key,value in payload.items() if key not in {'status','completed'}}
    return {**payload, **{key:value for key,value in resolved.items() if key != 'type'}}
