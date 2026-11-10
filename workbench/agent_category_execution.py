"""Static category_mutation@1 execution in the existing ProposalStore."""

import base64
import re
from datetime import datetime
from pathlib import PurePosixPath

from .agent_execution import fingerprint
from .agent_management import client_version, credential_lock
from .agent_security import AgentError, private_directory, private_write, read_json
from .category_changes import OPERATIONS, PROJECT_ASSETS
from .category_identity import FENCE_PATH, IDENTITY_PATH, namespace_key
from .category_prepared import (DOCUMENT, GRAPH, FileChange, apply_category_files, catalogue_path,
                                read_file, revision, verify_category_files, verify_members)
from .persistence import atomic_write_json
from .project_identity import controlled


STEPS = ['narrow', 'business', 'restore', 'receipt']


def logical_plan(proposal):
    content = proposal.get('normalized_content')
    return {'handler':'category_mutation@1', 'kind':'category', 'operation':proposal['operation'],
            'target':proposal['access_target'], 'steps':STEPS, 'source_bindings':[],
            'candidate_digest':fingerprint(content) if content else proposal['execution_plan']['candidate_digest']}


def validate_context(proposal):
    if proposal['operation'] not in OPERATIONS or proposal['confirmation_mode'] != 'local_web':
        raise ValueError('分类提案操作或批准方式无效')
    deps = proposal['dependencies']
    if set(deps) != {'schema_version', 'files_digest', 'authorization_digest', 'local_digest'} or type(deps['schema_version']) is not int or deps['schema_version'] != 1 or any(not re.fullmatch(r'[0-9a-f]{64}', deps[key]) for key in deps if key != 'schema_version'):
        raise ValueError('分类计划证据格式无效')
    target = proposal['access_target']
    if set(target) != {'type', 'family', 'project_id', 'name'} or target['type'] != 'category':
        raise ValueError('分类提案范围无效')
    namespace_key(target['family'], target['project_id'])
    if not proposal.get('content_cleaned'):
        content = proposal['normalized_content']
        selection = content['selection']
        if target != {'type':'category', 'family':selection['family'], 'project_id':selection.get('project_id'), 'name':selection['name']} or proposal['base_revision'] != content['revision'] or proposal['operation'] != content['operation']:
            raise ValueError('分类提案与原预览不一致')
        if fingerprint(proposal.get('category_local_details')) != deps['local_digest']:
            raise ValueError('本机分类预览与原摘要不一致')
    if proposal['execution_plan'] != logical_plan(proposal) or proposal['plan_digest'] != fingerprint(proposal['execution_plan']):
        raise ValueError('分类执行计划不一致')


def concrete_plan(manifest, proposal):
    return {'handler':'category_mutation@1', 'steps':STEPS, 'proposal_plan_digest':proposal['plan_digest'],
            'files_digest':proposal['dependencies']['files_digest'], 'history_version':manifest['history_version']}


def _directory(store, operation):
    return controlled(store.repository.root, store.operations / operation)


def _private_plan(security, operation):
    folder = security.config_dir / 'category-plans'
    if folder.resolve() != folder.absolute():
        raise ValueError('分类授权计划路径无效')
    path = folder / f'{operation}.json'
    if path.resolve() != path.absolute():
        raise ValueError('分类授权计划不能使用别名')
    return path


def discard_committed_private_plan(store, manifest):
    from .agent_category_service import security_for
    if manifest['state'] != 'committed' or manifest['step_states'] != ['completed'] * 4:
        return
    try:
        security = security_for(store.repository)
        if security and security.workspace_id == store.workspace_id:
            _private_plan(security, manifest['operation_id']).unlink(missing_ok=True)
    except (ValueError, OSError, AgentError):
        # The durable receipt is already settled. Startup can retry cleanup.
        pass


def _read_files(store, manifest, proposal):
    path = controlled(store.repository.root, _directory(store, manifest['operation_id']) / 'category-files.json')
    with path.open('rb') as stream:
        data = stream.read(96 * 1048576 + 1)
    if len(data) > 96 * 1048576:
        raise ValueError('分类原字节计划超出限制')
    import json
    value = json.loads(data.decode('utf-8'))
    if set(value) != {'files', 'watch', 'names', 'scope'} or not isinstance(value['files'], list) or not isinstance(value['watch'], dict):
        raise ValueError('分类原字节计划格式无效')
    files = []
    for row in value['files']:
        if set(row) != {'path', 'before', 'after', 'item_id'}:
            raise ValueError('分类候选文件格式无效')
        before = None if row['before'] is None else base64.b64decode(row['before'], validate=True)
        after = base64.b64decode(row['after'], validate=True)
        files.append(FileChange(row['path'], before, after, row['item_id']))
    evidence = {**value, 'files':[file.descriptor() for file in files]}
    if fingerprint(evidence) != proposal['dependencies']['files_digest']:
        raise ValueError('分类原字节计划摘要不一致')
    scope = proposal['access_target']
    family, project_id = scope['family'], scope['project_id']
    config_paths = {catalogue_path(family, project_id), FENCE_PATH, IDENTITY_PATH}
    if family == PROJECT_ASSETS:
        config_paths.update({f'projects/{project_id}/assets/index.json', f'projects/{project_id}/README.md'})
    if family == DOCUMENT:
        config_paths.add('config/document-sort.json')
    paths = {file.path for file in files}
    if len(paths) != len(files) or len(paths) > 4102 or len(value['watch']) > 4102:
        raise ValueError('分类计划文件重复或超限')
    for relative in paths | value['watch'].keys():
        path = PurePosixPath(relative)
        if relative in config_paths:
            continue
        if len(path.parts) != 2 or not (family == DOCUMENT and path.parts[0] == 'documents' and path.suffix == '.md' or family == GRAPH and path.parts[0] == 'concept-maps' and re.fullmatch(r'CMAP-[0-9]+\.json', path.name)):
            raise ValueError('分类计划文件不属于原领域')
    return files, value['watch']


def validate_execution(store, manifest, proposal, snapshots=False):
    validate_context(proposal)
    if type(manifest.get('execution_schema_version')) is not int or manifest['execution_schema_version'] != 7:
        raise ValueError('分类执行格式不受支持')
    for key in ('workspace_id', 'proposal_id', 'version', 'kind', 'operation', 'client_id', 'preview_digest', 'approval', 'confirmation_mode', 'digest_algorithm', 'access_target'):
        if manifest.get(key) != proposal.get(key):
            raise ValueError('分类执行证据和提案不符')
    operation = f"{proposal['proposal_id']}-{proposal['version']}"
    if manifest['operation_id'] != operation or not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[0-9]{6}-[a-f0-9]{8}', manifest['history_version']):
        raise ValueError('分类执行标识无效')
    if manifest['execution_plan'] != concrete_plan(manifest, proposal) or manifest['execution_plan_digest'] != fingerprint(manifest['execution_plan']):
        raise ValueError('分类执行摘要不一致')
    if manifest['step_states'] not in ([0, 0, 0, 0], [1, 0, 0, 0], [2, 1, 0, 0], [2, 2, 1, 0], [2, 2, 2, 1], ['completed'] * 4):
        raise ValueError('分类执行阶段未知')
    expected = {'proposal_id':proposal['proposal_id'], 'version':proposal['version'], 'kind':'category',
                'operation':proposal['operation'], 'family':proposal['access_target']['family'], 'name':proposal['access_target']['name'],
                'project_id':proposal['access_target']['project_id'], 'committed_at':manifest['receipt']['committed_at'],
                'execution_plan_digest':manifest['execution_plan_digest'], 'plan_digest':proposal['plan_digest'], 'approval':proposal['approval']}
    if manifest['receipt'] != expected:
        raise ValueError('分类回执身份不一致')
    if store and snapshots:
        _read_files(store, manifest, proposal)


def _security(store):
    from .agent_category_service import security_for
    security = security_for(store.repository)
    if not security or security.workspace_id != store.workspace_id:
        raise AgentError('authorization_unavailable', '分类恢复需要匹配的私人授权配置', 503)
    return security


def verify_restore_evidence(security, intent):
    from types import SimpleNamespace
    from .history import concept_map_history_path, history_path
    proof = intent['category_proof']
    operation = proof.get('operation_id')
    if set(proof) != {'operation_id'} or not isinstance(operation, str) or not re.fullmatch(r'[a-f0-9-]{36}-[1-9][0-9]*', operation):
        raise ValueError('分类补发缺少有效的原事务')
    root = security.root
    store = SimpleNamespace(repository=SimpleNamespace(root=root), operations=root / '.agent' / 'operations')
    manifest = read_json(controlled(root, _directory(store, operation) / 'manifest.json'))
    proposal_id, _, _ = operation.rpartition('-')
    proposal = read_json(controlled(root, root / '.agent' / 'proposals' / f'{proposal_id}.json'))
    validate_execution(store, manifest, proposal)
    if (manifest['operation_id'] != operation or manifest['workspace_id'] != security.workspace_id
            or manifest['state'] != 'applying' or manifest['step_states'] != [2, 2, 1, 0]):
        raise ValueError('原分类事务尚未进入补发阶段')
    private = read_json(_private_plan(security, operation))
    migrations = private['migrations']
    if (private['operation_id'] != operation
            or fingerprint([private['registry'], migrations]) != proposal['dependencies']['authorization_digest']):
        raise ValueError('分类补发缺少匹配的私人计划')
    row = migrations[intent['client_id']]
    if row['narrow'] != intent['before_client'] or row['after'] != intent['after_client']:
        raise ValueError('分类补发与原范围不一致')
    files, watch = _read_files(store, manifest, proposal)
    scope = proposal['access_target']
    family = scope['family']
    verify_members(root, family, watch, scope['project_id'])
    for file in files:
        watch[file.path] = revision(file.after)
        if file.item_id and file.before != file.after:
            history = (history_path if family == DOCUMENT else concept_map_history_path)(
                root / 'history', file.item_id, manifest['history_version'])
            if read_file(root, history.relative_to(root).as_posix()) != file.before:
                raise ValueError('分类补发前原始历史证据不一致')
    if any(revision(read_file(root, path)) != expected for path, expected in watch.items()):
        raise ValueError('分类补发前业务文件证据不一致')


def _run(store, manifest, proposal):
    from .agent_category_service import prepare_submission
    from .agent_execution import authorization_revision
    security = _security(store)
    manager = security.manager()
    operation = manifest['operation_id']
    directory = _directory(store, operation)
    private = _private_plan(security, operation)
    files, watch = _read_files(store, manifest, proposal)
    evidence = read_json(private)
    registry, migrations = evidence['registry'], evidence['migrations']
    if evidence.get('operation_id') != operation or fingerprint([registry, migrations]) != proposal['dependencies']['authorization_digest']:
        raise ValueError('分类私人迁移证据不匹配')
    current = security.clients()
    if current.keys() != registry.keys():
        raise ValueError('客户端集合变化，停止迁移')
    stage = manifest['step_states']
    scope = proposal['access_target']
    family = scope['family']
    before_business = stage in ([0, 0, 0, 0], [1, 0, 0, 0])
    if stage == [0, 0, 0, 0]:
        if {key:client_version(client) for key,client in current.items()} != registry:
            raise ValueError('分类执行前授权已变化')
        if not proposal.get('local_category_origin'):
            actor = current[proposal['client_id']]
            if authorization_revision(actor) != proposal['authorization_revision']:
                raise ValueError('分类执行前原客户端授权已变化')
            prepare_submission(store.repository, security, actor, proposal)

    def phase(states, checkpoint):
        manifest.update(state='applying', step_states=states)
        atomic_write_json(directory / 'manifest.json', manifest)
        store.checkpoint(checkpoint)

    if before_business:
        verify_category_files(store.repository.root, family, files, watch,
                              allow_applied=False, project_id=scope['project_id'])
        phase([1, 0, 0, 0], 'category_narrow_applying')
        for key, row in migrations.items():
            manager.run('category_migration', {'after':row['narrow'], 'phase':'narrow', 'proof':{}},
                        key, registry[key], f'{operation}:n:{key}')
            store.checkpoint('category_client_narrowed')
        phase([2, 1, 0, 0], 'category_business_applying')
    for key, client in security.clients().items():
        allowed = {registry[key]} if key not in migrations else {client_version(migrations[key]['narrow'])}
        if manifest['step_states'] in ([2, 2, 1, 0], [2, 2, 2, 1]) and key in migrations:
            allowed.add(client_version(migrations[key]['after']))
        if client_version(client) not in allowed:
            raise ValueError('分类迁移中的客户端权限已变化')
    apply_category_files(store.repository.root, family, files, watch, history_version=manifest['history_version'],
                         allow_applied=not before_business, project_id=scope['project_id'],
                         checkpoint=lambda name, _:store.checkpoint(name))
    phase([2, 2, 1, 0], 'category_restore_applying')
    for key, row in migrations.items():
        if row['after'] == row['narrow']:
            continue
        manager.run('category_migration', {'after':row['after'], 'phase':'restore', 'proof':{'operation_id':operation}},
                    key, client_version(row['narrow']), f'{operation}:r:{key}')
        store.checkpoint('category_client_restored')
    phase([2, 2, 2, 1], 'category_receipt_applying')
    store._finish(manifest, proposal)


def commit(store, proposal, bundle, approval):
    from .agent_proposals import stamp
    prepared, _, _, _, registry, migrations = bundle
    operation = f"{proposal['proposal_id']}-{proposal['version']}"
    security = _security(store)
    with credential_lock(security.config_dir):
        directory = _directory(store, operation)
        directory.mkdir(parents=True, exist_ok=True)
        value = prepared.evidence()
        value['files'] = [{**file.descriptor(), 'before':None if file.before is None else base64.b64encode(file.before).decode('ascii'),
                           'after':base64.b64encode(file.after).decode('ascii')} for file in prepared.files]
        atomic_write_json(directory / 'category-files.json', value)
        private = _private_plan(security, operation)
        private_directory(private.parent)
        private_write(private, {'operation_id':operation, 'registry':registry, 'migrations':migrations})
        store.checkpoint('category_snapshots')
        manifest = {key:proposal[key] for key in ('workspace_id', 'proposal_id', 'version', 'kind', 'operation', 'client_id', 'preview_digest', 'confirmation_mode', 'digest_algorithm', 'access_target')}
        manifest.update(schema_version=3, execution_schema_version=7, operation_id=operation, approval=approval,
                        state='prepared', step_states=[0, 0, 0, 0], history_version=datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + operation[:8])
        manifest['execution_plan'] = concrete_plan(manifest, proposal)
        manifest['execution_plan_digest'] = fingerprint(manifest['execution_plan'])
        target = proposal['access_target']
        manifest['receipt'] = {**{key:proposal[key] for key in ('proposal_id', 'version', 'kind', 'operation')},
                               **{key:target[key] for key in ('family', 'name', 'project_id')}, 'committed_at':stamp(),
                               'execution_plan_digest':manifest['execution_plan_digest'], 'plan_digest':proposal['plan_digest'], 'approval':approval}
        validate_execution(store, manifest, proposal, snapshots=True)
        atomic_write_json(directory / 'manifest.json', manifest)
        store.blocked = True
        store.checkpoint('category_manifest')
        proposal['state'] = 'committing'
        store._save(proposal)
        store.executing = True
        try:
            _run(store, manifest, proposal)
        except (ValueError, OSError, AgentError) as error:
            raise AgentError('recovery_required', '分类操作未全部完成，请查询原操作', 503) from error
        finally:
            store.executing = False
        store.blocked = False
        return manifest['receipt']
