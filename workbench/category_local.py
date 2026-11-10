"""Local category review using the same prepared plan and execution engine."""

import hashlib
import re
import secrets
import time
import uuid
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

from .agent_category_service import candidate, security_for
from .agent_delete_service import checked_preview
from .agent_execution import fingerprint
from .agent_management import credential_lock
from .agent_proposals import stamp
from .agent_security import AgentError, read_json
from .category_prepared import apply_category_files
from .markdown_io import now_iso
from .persistence import atomic_write_bytes, atomic_write_json
from .project_identity import controlled
from .write_coordinator import RevisionConflict


def _security(repository):
    security = security_for(repository)
    if (repository.root / '.agent' / 'workspace.json').exists() and security is None:
        raise AgentError('authorization_unavailable', '已初始化工作空间需要匹配的私人配置才能迁移分类', 503)
    return security


def _bundle(repository, security, operation, selection, epoch, managed_time):
    if security:
        with credential_lock(security.config_dir):
            if security.manager().blocked_clients():
                raise AgentError('management_recovery_required', '先核查未完成的授权操作', 503)
            return candidate(repository, security, selection, operation, epoch, managed_time)
    return candidate(repository, None, selection, operation, epoch, managed_time)


def preview(repository, payload):
    if not isinstance(payload, dict) or set(payload) != {'operation', 'selection'}:
        raise ValueError('分类预览只接受具体选择和操作')
    security = _security(repository)
    epoch = str(uuid.uuid5(uuid.NAMESPACE_URL, security.workspace_id)) if security else str(uuid.uuid4())
    managed_time = now_iso()
    bundle = _bundle(repository, security, payload['operation'], payload['selection'], epoch, managed_time)
    _, impact, dependencies, local, _, _ = bundle
    token, now = secrets.token_hex(32), time.monotonic()
    tickets = repository.category_preview_tickets
    for key, ticket in list(tickets.items()):
        if ticket['expires'] <= now:
            del tickets[key]
    if len(tickets) >= 100:
        raise AgentError('preview_limit', '分类预览过多，请稍后再试', 429)
    value = checked_preview({'ticket':token, 'impact':impact, 'local':local})
    tickets[token] = {'expires':now + 600, 'workspace':security.workspace_id if security else None,
                      'impact':impact, 'dependencies':dependencies}
    return value


def _commit_origin(repository, security, bundle, token):
    store = repository.agent_proposals
    _, impact, dependencies, local, _, _ = bundle
    origin = {'client_id':store.workspace_id, 'local_category_origin':True}
    request = {'request_id':token, 'kind':'category', 'operation':impact['operation']}
    created = store.create(origin, request, impact, {}, 'local_web', dependencies=dependencies,
                           category_local_details=local, local_category_origin=True)
    proposal = store._load(created['proposal_id'], expire=False)
    store.preview(proposal)
    action_id = hashlib.sha256(token.encode()).hexdigest()
    input_digest = fingerprint([token, proposal['proposal_id'], proposal['preview_digest']])
    approval = {'mode':'local_web', 'version':1, 'preview_digest':proposal['preview_digest'],
                'operation_id':action_id, 'input_digest':input_digest, 'approved_at':stamp(),
                'plan_digest':proposal['plan_digest'], 'authorization_revision':proposal['authorization_revision'],
                'dependencies_digest':fingerprint(dependencies)}
    action = {'schema_version':3, 'workspace_id':store.workspace_id, 'request_id':token, 'operation':'approve',
              'proposal_id':proposal['proposal_id'], 'version':1, 'input_digest':input_digest, 'approval':approval,
              'business_operation_id':f"{proposal['proposal_id']}-1", 'state':'approved',
              'proposal_schema_version':3, 'plan_digest':proposal['plan_digest']}
    path = controlled(repository.root, store.root / 'proposal-actions' / (action_id + '.json'))
    atomic_write_json(path, action)
    proposal['approval'] = approval
    store._save(proposal)
    receipt = store.commit(proposal, 1, proposal['preview_digest'], {'mode':'local_web'}, bundle, local_approval=approval)
    atomic_write_json(path, {**action, 'state':'completed', 'result':receipt})
    return receipt


def approve(repository, payload):
    if not isinstance(payload, dict) or set(payload) != {'ticket'} or not isinstance(payload['ticket'], str) or not re.fullmatch(r'[0-9a-f]{64}', payload['ticket']):
        raise ValueError('确认需要本机分类预览票据')
    token = payload['ticket']
    ticket = repository.category_preview_tickets.get(token)
    runtime = getattr(repository, 'agent_runtime', None)
    store = getattr(repository, 'agent_proposals', None)
    if runtime and store:
        from .agent_proposal_management import ProposalManagement
        management = ProposalManagement(runtime)
        path = management._action_path(token)
        if path.exists():
            action = management._load_approval(path)
            proposal = store._load(action['proposal_id'], expire=False)
            if not proposal.get('local_category_origin'):
                raise AgentError('preview_expired', '分类预览已失效，请重新核对', 409)
            result = management.action(token)
            if result['state'] == 'completed':
                return result['receipt']
            raise AgentError('category_action_' + result['state'], '请在提案管理中核查原分类操作状态', 409)
    if not ticket or ticket['expires'] <= time.monotonic():
        raise AgentError('preview_expired', '分类预览已失效，请重新核对', 409)
    if 'receipt' in ticket:
        return ticket['receipt']
    if getattr(repository, 'document_uploads', None):
        repository.document_uploads.guard()
    if repository.write_guard:
        repository.write_guard()
    security = _security(repository)
    if ticket['workspace'] != (security.workspace_id if security else None):
        raise RevisionConflict('分类预览后工作空间授权状态发生变化')
    with credential_lock(security.config_dir) if security else nullcontext():
        impact = ticket['impact']
        bundle = _bundle(repository, security, impact['operation'], impact['selection'], impact['epoch'], impact['managed_time'])
        prepared, current, dependencies, _, _, _ = bundle
        if current != impact or dependencies != ticket['dependencies']:
            raise RevisionConflict('分类、成员或授权已经变化，请重新预览')
        if security:
            del repository.category_preview_tickets[token]
            return _commit_origin(repository, security, bundle, token)
        apply_category_files(repository.root, prepared.change.family, prepared.files, prepared.watch,
                             project_id=prepared.project_id)
        receipt = {'kind':'category', 'operation':prepared.change.operation, 'family':prepared.change.family,
                   'name':prepared.change.name, 'project_id':prepared.project_id}
        repository.category_preview_tickets[token] = {'expires':ticket['expires'], 'receipt':receipt}
        return receipt


def execute_legacy_command(repository, family, operation, name, *, new_name=None):
    selection = {'family':family, 'name':name, **({'new_name':new_name} if new_name is not None else {})}
    review = preview(repository, {'operation':operation, 'selection':selection})
    approve(repository, {'ticket':review['ticket']})
    return review


def active_identity(repository):
    from .category_identity import FENCE_PATH, IDENTITY_PATH
    return any((repository.root / path).exists() for path in (FENCE_PATH, IDENTITY_PATH, '.agent/workspace.json'))


@contextmanager
def legacy_catalogue(repository, family, project_id, before, after):
    """Preserve the old PUT data semantics while fencing name activation."""
    from .agent_category_authorization import migration_plan
    from .category_identity import FENCE_PATH, IDENTITY_PATH, load_category_identities, namespace_key
    from .category_prepared import catalogue_path, read_file
    old, new = set(before), set(after)
    identities = load_category_identities(repository.root)
    key = namespace_key(family, project_id)
    scope = identities.scope(key, before)
    if old == new:
        yield
        return
    security = _security(repository)
    config = catalogue_path(family, project_id)
    original_config = read_file(repository.root, config)
    with credential_lock(security.config_dir) if security else nullcontext():
        clients = security.clients() if security else {}
        operations = [(name, 'delete') for name in sorted(old - new)] + [(name, 'create') for name in sorted(new - old)]
        staged = []
        for name, operation in operations:
            shadow = SimpleNamespace(change=SimpleNamespace(family=family, name=name, destination=name if operation == 'create' else None, operation=operation),
                                     project_id=project_id, members=(), scope=scope)
            rows = migration_plan(clients, shadow)
            staged.append(rows)
            clients = {key:rows[key]['narrow'] if key in rows else value for key, value in clients.items()}
        tracked = identities.epoch or security and security.registry_version() >= 8 or any(staged)
        if not tracked:
            yield
            return
        epoch = identities.epoch or str(uuid.uuid4())
        fence, ledger = identities.replace(family, project_id, before, after, epoch)
        if security:
            manager = security.manager()
            for rows in staged:
                for key, row in rows.items():
                    from .agent_management import client_version
                    manager.run('category_migration', {'after':row['narrow'], 'phase':'narrow', 'proof':{}},
                                key, client_version(row['before']), uuid.uuid4().hex)
        if (load_category_identities(repository.root) != identities
                or read_file(repository.root, config) != original_config):
            raise RevisionConflict('分类目录或身份在授权收窄期间变化')
        if identities.fence_before is None:
            atomic_write_bytes(controlled(repository.root, repository.root / FENCE_PATH), fence)
        yield
        if (read_file(repository.root, FENCE_PATH) != fence
                or read_file(repository.root, IDENTITY_PATH) != identities.ledger_before):
            raise RevisionConflict('分类身份在业务写入期间变化')
        atomic_write_bytes(controlled(repository.root, repository.root / IDENTITY_PATH), ledger)
