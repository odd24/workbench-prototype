"""Static workflow_mutation@1 handler in the shared ProposalStore."""

import base64
import json
import re
from datetime import datetime
from pathlib import PurePosixPath

from .agent_category_service import security_for
from .agent_execution import fingerprint
from .agent_management import client_version, credential_lock
from .agent_security import AgentError, private_directory, private_write, read_json
from .persistence import atomic_write_json
from .project_identity import controlled
from .records import TYPE_DIRS
from .workflow_changes import COMMANDS
from .workflow_identity import FENCE, LEDGER
from .workflow_prepared import CATALOGUE, FALLBACK, WorkflowFile, apply_workflow_files, verify_workflow_files


STEPS = ['narrow', 'files', 'verified', 'receipt']
LOCAL = {'compat_catalogue','compat_status'}


def logical_plan(proposal):
    content = proposal.get('normalized_content')
    candidate = fingerprint(content) if content else proposal['execution_plan']['candidate_digest']
    return {'handler':'workflow_mutation@1', 'kind':'workflow', 'operation':proposal['operation'],
            'target':proposal['access_target'], 'steps':STEPS, 'source_bindings':[], 'candidate_digest':candidate}


def validate_context(proposal):
    from .agent_workflow_service import target
    operation = proposal['operation']
    local = proposal.get('local_workflow_origin', False)
    if (operation not in COMMANDS.keys() | LOCAL or proposal['confirmation_mode'] != 'local_web'
            or (operation in LOCAL and local is not True) or type(local) is not bool
            or (local and proposal['client_id'] != proposal['workspace_id'])):
        raise ValueError('工作流提案操作或起源无效')
    deps = proposal['dependencies']
    if (deps.keys() != {'schema_version','files_digest','local_digest','authorization_digest'}
            or type(deps['schema_version']) is not int or deps['schema_version'] != 1
            or any(not re.fullmatch(r'[a-f0-9]{64}', deps[key]) for key in deps if key != 'schema_version')):
        raise ValueError('工作流依赖格式无效')
    if not proposal.get('content_cleaned'):
        content = proposal['normalized_content']
        if (proposal['access_target'] != target(operation, content['selection']) or content['operation'] != operation
                or proposal['base_revision'] != content['revision'] or content['revision'] != deps['files_digest']
                or fingerprint(proposal['workflow_local_details']) != deps['local_digest']):
            raise ValueError('工作流计划与原预览不一致')
    if proposal['execution_plan'] != logical_plan(proposal) or proposal['plan_digest'] != fingerprint(proposal['execution_plan']):
        raise ValueError('工作流执行计划摘要不一致')


def concrete_plan(manifest, proposal):
    return {'handler':'workflow_mutation@1','steps':STEPS, 'proposal_plan_digest':proposal['plan_digest'],
            'files_digest':proposal['dependencies']['files_digest'], 'history_version':manifest['history_version']}


def _directory(store, operation):
    return controlled(store.repository.root, store.operations / operation)


def _private(security, operation):
    path = security.config_dir / 'workflow-plans' / f'{operation}.json'
    if path.resolve() != path.absolute():
        raise ValueError('工作流授权计划路径不能使用别名')
    return path


def _allowed_path(relative):
    if relative in {CATALOGUE,FALLBACK,FENCE,LEDGER}:
        return True
    path = PurePosixPath(relative)
    if relative != path.as_posix() or any(part in {'..','.'} for part in path.parts):
        return False
    if len(path.parts) == 2:
        return path.parts[0] == 'ideas' and path.suffix == '.md'
    if not path.parts or path.parts[0] != 'projects':
        return False
    return (len(path.parts) == 3 and path.name == 'README.md'
            or len(path.parts) == 4 and path.parts[2] in TYPE_DIRS.values() and path.suffix == '.md')


def _read_files(store, manifest, proposal):
    path = controlled(store.repository.root, _directory(store, manifest['operation_id']) / 'workflow-files.json')
    with path.open('rb') as stream:
        raw = stream.read(96 * 1048576 + 1)
    if len(raw) > 96 * 1048576:
        raise ValueError('工作流原字节计划超出上限')
    value = json.loads(raw.decode('utf-8'))
    if (value.keys() != {'files','watch'} or not isinstance(value['files'], list) or not isinstance(value['watch'], dict)
            or len(value['files']) > 4100 or len(value['watch']) > 4100):
        raise ValueError('工作流原字节计划格式无效')
    watch = value['watch']
    files = []
    for row in value['files']:
        if row.keys() != {'path','before','after','record_id'}:
            raise ValueError('工作流候选文件格式无效')
        before = None if row['before'] is None else base64.b64decode(row['before'], validate=True)
        after = base64.b64decode(row['after'], validate=True)
        files.append(WorkflowFile(row['path'], before, after, row['record_id']))
    if fingerprint({'files':[file.evidence() for file in files], 'watch':watch}) != proposal['dependencies']['files_digest']:
        raise ValueError('工作流原字节计划摘要不一致')
    if any(not _allowed_path(relative) for relative in watch.keys() | {file.path for file in files}):
        raise ValueError('工作流候选文件超出领域路径')
    return files, watch


def _receipt(manifest, proposal):
    return {'proposal_id':proposal['proposal_id'], 'version':proposal['version'], 'kind':'workflow',
            'operation':proposal['operation'], 'scope':proposal['access_target'], 'committed_at':manifest['receipt']['committed_at'],
            'execution_plan_digest':manifest['execution_plan_digest'], 'plan_digest':proposal['plan_digest'],
            'approval':proposal['approval']}


def validate_execution(store, manifest, proposal, snapshots=False):
    validate_context(proposal)
    if type(manifest.get('execution_schema_version')) is not int or manifest['execution_schema_version'] != 8:
        raise ValueError('工作流执行格式不受支持')
    for key in ('workspace_id','proposal_id','version','kind','operation','client_id','preview_digest','approval','confirmation_mode','digest_algorithm','access_target'):
        if manifest[key] != proposal[key]:
            raise ValueError('工作流事务证据不一致')
    if (manifest['operation_id'] != f"{proposal['proposal_id']}-{proposal['version']}"
            or not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[0-9]{6}-[a-f0-9]{8}', manifest['history_version'])
            or manifest['execution_plan'] != concrete_plan(manifest, proposal)
            or manifest['execution_plan_digest'] != fingerprint(manifest['execution_plan'])
            or manifest['receipt'] != _receipt(manifest, proposal)
            or manifest['step_states'] not in ([0,0,0,0],[1,0,0,0],[2,1,0,0],[2,2,1,0],[2,2,2,1],['completed'] * 4)):
        raise ValueError('工作流执行身份、阶段或回执无效')
    if store and snapshots:
        _read_files(store, manifest, proposal)


def _security(store):
    security = security_for(store.repository)
    if security is None or security.workspace_id != store.workspace_id:
        raise AgentError('authorization_unavailable','工作流恢复需要匹配的私人配置',503)
    return security


def discard_private(store, manifest):
    if manifest['state'] == 'committed':
        try:
            _private(_security(store), manifest['operation_id']).unlink(missing_ok=True)
        except (OSError, ValueError, AgentError):
            pass


def run(store, manifest, proposal):
    from .agent_workflow_service import prepare_submission
    security = _security(store)
    operation = manifest['operation_id']
    private = read_json(_private(security, operation))
    registry, narrowed = private['registry'], private['narrowed']
    if private['operation_id'] != operation or fingerprint([registry, narrowed]) != proposal['dependencies']['authorization_digest']:
        raise ValueError('工作流私人授权证据与原计划不匹配')
    current = security.clients()
    if current.keys() != registry.keys():
        raise ValueError('工作流客户端集合变化')
    files, watch = _read_files(store, manifest, proposal)
    stage = manifest['step_states']
    initial = stage in ([0,0,0,0],[1,0,0,0])

    def phase(states, checkpoint):
        manifest.update(state='applying', step_states=states)
        atomic_write_json(_directory(store, operation) / 'manifest.json', manifest)
        store.checkpoint(checkpoint)

    if stage == [0,0,0,0]:
        if any(client_version(current[key]) != expected for key,expected in registry.items()):
            raise ValueError('工作流原批准授权已经变化')
        if not proposal.get('local_workflow_origin'):
            prepare_submission(store.repository, security, current[proposal['client_id']], proposal)
    if initial:
        verify_workflow_files(store.repository.root, files, watch)
        phase([1,0,0,0], 'workflow_narrow_applying')
        for key, after in narrowed.items():
            security.manager().run('workflow_narrow', {'after':after}, key, registry[key], f'{operation}:n:{key}')
            store.checkpoint('workflow_client_narrowed')
        phase([2,1,0,0], 'workflow_files_applying')
    current = security.clients()
    if current.keys() != registry.keys() or any(client_version(client) != (client_version(narrowed[key]) if key in narrowed else registry[key])
                                                for key,client in current.items()):
        raise ValueError('工作流执行中授权已经变化')
    apply_workflow_files(store.repository.root, files, watch, history_version=manifest['history_version'],
                         allow_applied=not initial, invalidate=store.repository._forget_record,
                         checkpoint=lambda name, _:store.checkpoint(name))
    phase([2,2,1,0], 'workflow_verified')
    phase([2,2,2,1], 'workflow_receipt_applying')
    store._finish(manifest, proposal)


def commit(store, proposal, bundle, approval):
    from .agent_proposals import stamp
    prepared, _, _, _, registry, narrowed = bundle
    if prepared.unmapped:
        raise AgentError('mapping_required','请先完整映射所有使用中状态',409)
    operation = f"{proposal['proposal_id']}-{proposal['version']}"
    security = _security(store)
    with credential_lock(security.config_dir):
        directory = _directory(store, operation)
        directory.mkdir(parents=True, exist_ok=True)
        files = [{**file.evidence(),
                  'before':None if file.before is None else base64.b64encode(file.before).decode('ascii'),
                  'after':base64.b64encode(file.after).decode('ascii')} for file in prepared.files]
        atomic_write_json(directory / 'workflow-files.json', {'files':files,'watch':prepared.watch})
        path = _private(security, operation)
        private_directory(path.parent)
        private_write(path, {'operation_id':operation,'registry':registry,'narrowed':narrowed})
        store.checkpoint('workflow_snapshots')
        manifest = {key:proposal[key] for key in ('workspace_id','proposal_id','version','kind','operation','client_id',
                                                  'preview_digest','confirmation_mode','digest_algorithm','access_target')}
        manifest.update(schema_version=3, execution_schema_version=8, operation_id=operation, approval=approval,
                        state='prepared', step_states=[0,0,0,0],
                        history_version=datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + operation[:8],
                        receipt={'committed_at':stamp()})
        manifest['execution_plan'] = concrete_plan(manifest, proposal)
        manifest['execution_plan_digest'] = fingerprint(manifest['execution_plan'])
        manifest['receipt'] = _receipt(manifest, proposal)
        validate_execution(store, manifest, proposal, snapshots=True)
        atomic_write_json(directory / 'manifest.json', manifest)
        store.blocked = True
        store.checkpoint('workflow_manifest')
        proposal['state'] = 'committing'
        store._save(proposal)
        store.executing = True
        try:
            run(store, manifest, proposal)
        except (ValueError, OSError, AgentError) as error:
            raise AgentError('recovery_required','工作流操作未完成，请查询原操作',503) from error
        finally:
            store.executing = False
        store.blocked = False
        return manifest['receipt']
