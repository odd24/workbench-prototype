"""attachment@1 phases within ProposalStore; no independent business state machine."""

import hashlib
import os
import re
import time
import shutil
import uuid
from datetime import datetime, timezone
from dataclasses import replace
from urllib.parse import urlencode

from .agent_security import AgentError, read_json, require_scope
from .agent_management import credential_lock
from .agent_execution import fingerprint, validate_context
from .agent_attachments import AttachmentService, consumption_id, serialized, STEPS, relative_paths
from .agent_file_handles import LocalFileHandle
from .attachment_prepared import PreparedAttachment, raw_markdown_body
from .persistence import atomic_write_bytes, atomic_write_json
from .write_coordinator import content_revision, PreparedMarkdownWrite, DataDirectoryLock
from .history import history_path


def digest(value):
    return None if value is None else hashlib.sha256(value).hexdigest()


def concrete_plan(manifest, proposal):
    return {'handler':'attachment@1', 'proposal_plan_digest':proposal['plan_digest'], 'steps':STEPS.copy(),
            **{key:manifest[key] for key in ('kind', 'operation', 'item_id', 'relative_path', 'binary_relative',
                                            'before_digest', 'after_digest', 'history_version', 'metadata_time', 'upload_id', 'consumption_id')},
            'source_bindings':proposal['execution_plan']['source_bindings']}


def targets(repository, proposal):
    view = proposal['normalized_content']
    relative_paths(view)
    result = tuple(repository.root / relative for relative in (view['binary_relative'], view['metadata_relative']))
    for path in result:
        if path.resolve() != path.absolute() or not path.absolute().is_relative_to(repository.root):
            raise ValueError('附件目标包含链接或超出空间')
    return result


def validate_manifest(manifest, proposal):
    validate_context(proposal)
    required = {'schema_version', 'execution_schema_version', 'workspace_id', 'operation_id', 'proposal_id', 'version',
                'kind', 'operation', 'client_id', 'access_target', 'item_id', 'relative_path', 'binary_relative',
                'before_digest', 'after_digest', 'history_version', 'metadata_time', 'upload_id', 'consumption_id', 'state', 'receipt',
                'confirmation', 'digest_algorithm', 'preview_digest', 'confirmation_mode', 'approval',
                'authorization_revision', 'dependencies', 'step_states', 'execution_plan', 'execution_plan_digest', 'copy_evidence'}
    if set(manifest) - {'abandoned_at'} != required or manifest['schema_version'] != 3 or manifest['execution_schema_version'] != 2 or manifest['kind'] != 'attachment' or manifest['operation'] != 'create':
        raise ValueError('附件执行格式不受支持')
    operation_id = proposal['proposal_id'] + '-' + str(proposal['version'])
    if manifest['operation_id'] != operation_id or manifest['consumption_id'] != consumption_id(operation_id) or manifest['version'] != proposal['version'] or manifest['proposal_id'] != proposal['proposal_id']:
        raise ValueError('附件执行身份无效')
    for key in ('workspace_id', 'client_id', 'access_target', 'authorization_revision', 'dependencies', 'preview_digest', 'confirmation_mode', 'digest_algorithm', 'approval'):
        if manifest[key] != proposal[key]:
            raise ValueError('附件执行与提案不一致')
    if manifest['execution_plan'] != concrete_plan(manifest, proposal) or manifest['execution_plan_digest'] != fingerprint(manifest['execution_plan']):
        raise ValueError('附件具体计划摘要无效')
    if set(manifest['step_states']) != set(STEPS) or any(value not in {'pending', 'completed'} for value in manifest['step_states'].values()):
        raise ValueError('附件执行阶段无效')
    confirmation = manifest['confirmation']
    if proposal['confirmation_mode'] == 'local_web':
        if confirmation != {'mode':'local_web'} or proposal['approval'] is None:
            raise ValueError('附件缺少网页确认')
    elif not isinstance(confirmation, dict) or set(confirmation) - {'mode', 'user_confirmed', 'note'} or confirmation.get('mode') != 'agent_attested' or confirmation.get('user_confirmed') is not True or not isinstance(confirmation.get('note', ''), str) or len(confirmation.get('note', '')) > 1000:
        raise ValueError('附件缺少对话确认')
    receipt = manifest['receipt']
    receipt_fields = {'proposal_id', 'version', 'kind', 'item_id', 'revision', 'upload_id', 'consumption_id', 'committed_at', 'title', 'project_id', 'owner_kind', 'owner_id', 'attachment', 'web_path', 'plan_digest', 'execution_plan_digest'} | ({'approval'} if manifest['approval'] is not None else set())
    if not isinstance(receipt, dict) or set(receipt) != receipt_fields or receipt['owner_id'] != proposal['target_id'] or receipt['owner_kind'] != proposal['access_target'].get('type', 'project') or receipt['project_id'] != proposal['access_target'].get('project_id'):
        raise ValueError('附件回执字段或归属无效')
    for key, expected in {'proposal_id':proposal['proposal_id'], 'version':proposal['version'], 'kind':'attachment',
                          'item_id':manifest['item_id'], 'revision':manifest['after_digest'], 'upload_id':manifest['upload_id'],
                          'consumption_id':manifest['consumption_id'], 'plan_digest':proposal['plan_digest'], 'execution_plan_digest':manifest['execution_plan_digest']}.items():
        if receipt.get(key) != expected:
            raise ValueError('附件回执身份不一致')
    source = proposal['execution_plan']['source_bindings'][0]
    if receipt.get('attachment', {}).get('size') != source['bytes'] or receipt.get('attachment', {}).get('sha256') != source['sha256']:
        raise ValueError('附件回执与来源证据不一致')
    if receipt.get('approval') != manifest['approval']:
        raise ValueError('附件回执确认不一致')
    accepted = datetime.fromisoformat(receipt['committed_at'])
    metadata_time = datetime.fromisoformat(manifest['metadata_time'])
    if accepted.tzinfo is None or metadata_time.tzinfo is None or accepted.astimezone(timezone.utc).replace(microsecond=0) != metadata_time.astimezone(timezone.utc):
        raise ValueError('附件提交时间不一致')
    if manifest['history_version'] is not None and not manifest['history_version'].startswith(metadata_time.strftime('%Y%m%d-%H%M%S-') + f'{accepted.microsecond:06d}-'):
        raise ValueError('附件历史时间未绑定接受时刻')
    evidence = manifest['copy_evidence']
    if evidence is not None:
        if set(evidence) != {'bytes', 'sha256', 'identity'} or set(evidence['identity']) != {'volume', 'index', 'size', 'created', 'written', 'changed'} or any(type(value) is not int for value in evidence['identity'].values()):
            raise ValueError('附件复制证据无效')
    if not proposal.get('content_cleaned'):
        view = proposal['normalized_content']
        expected_attachment = dict(view['attachment'])
        if view['owner_kind'] == 'project':
            expected_attachment['created'] = manifest['metadata_time']
        if receipt['attachment'] != expected_attachment or receipt['title'] != view['title']:
            raise ValueError('附件回执元数据不属于候选')
        if manifest['item_id'] != view['attachment']['id'] or manifest['upload_id'] != view['upload_id'] or manifest['binary_relative'] != view['binary_relative'] or manifest['relative_path'] != view['metadata_relative'] or manifest['after_digest'] != digest(serialized(view, manifest['metadata_time'])):
            raise ValueError('附件具体计划不属于候选')
        if evidence is not None and (evidence['bytes'] != view['attachment']['size'] or evidence['sha256'] != view['attachment']['sha256'] or evidence['identity']['size'] != evidence['bytes']):
            raise ValueError('附件复制证据不属于候选')


def validate_execution(store, manifest, proposal, snapshots=False):
    validate_manifest(manifest, proposal)
    if proposal.get('content_cleaned'):
        if manifest['state'] not in {'committed', 'abandoned'}:
            raise ValueError('不能清理在途附件执行证据')
        return
    _binary, _metadata = targets(store.repository, proposal)
    if manifest['before_digest'] is not None and manifest['before_digest'] != proposal['base_revision']:
        raise ValueError('附件基础版本不一致')
    if manifest['before_digest'] is None and proposal['base_revision'] != content_revision(b''):
        raise ValueError('附件缺失索引的基础版本无效')
    if manifest['history_version'] is not None:
        history_path(store.repository.history_dir, proposal['target_id'], manifest['history_version'])
    if manifest['preview_digest'] != fingerprint(store.preview_payload(proposal)):
        raise ValueError('附件执行预览不一致')
    if snapshots:
        directory = store.operations / manifest['operation_id']
        for name, expected in (('before.md', manifest['before_digest']), ('after.md', manifest['after_digest'])):
            path = directory / name
            if path.resolve() != path.absolute() or digest(path.read_bytes() if expected is not None else None) != expected:
                raise ValueError('附件元数据快照不匹配')
        before = (directory / 'before.md').read_bytes() if manifest['before_digest'] is not None else None
        view = proposal['normalized_content']
        if view['owner_kind'] != 'project':
            from .markdown_io import load_markdown_text
            if before is None or load_markdown_text(before.decode('utf-8'))[0] != view['metadata_before'] or raw_markdown_body(before) != proposal['base_content']['body']:
                raise ValueError('附件原正文/元数据与版本快照不一致')
        else:
            import json
            if (json.loads(before) if before is not None else []) != view['metadata_before']:
                raise ValueError('附件原项目索引与版本快照不一致')


class AttachmentExecution:
    def __init__(self, service):
        self.service, self.repository, self.store = service, service.repository, service.store
        self.security, self.uploads = service.security, service.uploads
        self.attachments = AttachmentService(service)

    def client(self, proposal):
        client = self.security.clients().get(proposal['client_id'])
        if not client or not client.get('enabled') or client['client_id'] in self.security.manager().blocked_clients():
            raise AgentError('authorization_revoked', '附件原客户端已撤销', 409)
        for scope in ('read', 'propose', 'commit'):
            require_scope(client, scope)
        return client

    def short(self, action, guard=None):
        def run():
            with self.repository.write_lock, credential_lock(self.security.config_dir):
                return action()
        return guard(run) if guard else run()

    def accept(self, proposal, payload, local_approval=None):
        previous = self.store.check_commit(proposal, payload.get('version'), payload.get('preview_digest'), payload.get('confirmation'), local_approval=local_approval)
        if previous is not None:
            return None, previous
        draft = self.attachments.prepare_submission(self.client(proposal), proposal)
        operation_id = proposal['proposal_id'] + '-' + str(proposal['version'])
        directory = self.store.operations / operation_id
        accepted = datetime.now(timezone.utc)
        metadata_time = accepted.astimezone().isoformat(timespec='seconds')
        history_version = accepted.astimezone().strftime('%Y%m%d-%H%M%S-%f') + '-' + uuid.uuid4().hex[:8] if draft.record_write else None
        draft = replace(draft, after=serialized(draft.view, metadata_time))
        if shutil.disk_usage(self.repository.root).free < draft.view['attachment']['size'] + 16 * 1048576:
            raise AgentError('insufficient_storage', '正式附件复制所需磁盘空间不足', 507)
        attachment = dict(draft.view['attachment'])
        if draft.view['owner_kind'] == 'project':
            attachment['created'] = metadata_time
        receipt = {'proposal_id':proposal['proposal_id'], 'version':proposal['version'], 'kind':'attachment',
                   'item_id':draft.view['attachment']['id'], 'revision':digest(draft.after), 'upload_id':draft.view['upload_id'],
                   'consumption_id':consumption_id(operation_id), 'committed_at':accepted.isoformat(),
                   'title':draft.view['title'], 'project_id':draft.view['project_id'], 'owner_kind':draft.view['owner_kind'],
                   'owner_id':draft.view['owner_id'], 'attachment':attachment,
                   'web_path':'/?' + urlencode({'item':'project', 'itemId':draft.view['project_id'], 'assetId':draft.view['attachment']['id']}) if draft.view['owner_kind'] == 'project' else '/?' + urlencode({'item':draft.view['owner_kind'], 'itemId':draft.view['owner_id']})}
        if draft.view['owner_kind'] == 'todo' and not draft.view['owner_id'].startswith('TODO-'):
            receipt['web_path'] = None  # Preserve the legacy converted-ID link contract.
        manifest = {'schema_version':3, 'execution_schema_version':2, 'workspace_id':self.store.workspace_id,
                    'operation_id':operation_id, 'proposal_id':proposal['proposal_id'], 'version':proposal['version'],
                    'kind':'attachment', 'operation':'create', 'client_id':proposal['client_id'], 'access_target':proposal['access_target'],
                    'item_id':receipt['item_id'], 'relative_path':draft.view['metadata_relative'], 'binary_relative':draft.view['binary_relative'],
                    'before_digest':digest(draft.before), 'after_digest':digest(draft.after), 'history_version':history_version, 'metadata_time':metadata_time,
                    'upload_id':draft.view['upload_id'], 'consumption_id':receipt['consumption_id'], 'state':'prepared', 'receipt':receipt,
                    'confirmation':payload.get('confirmation'), 'digest_algorithm':proposal['digest_algorithm'], 'preview_digest':proposal['preview_digest'],
                    'confirmation_mode':proposal['confirmation_mode'], 'approval':proposal['approval'],
                    'authorization_revision':proposal['authorization_revision'], 'dependencies':proposal['dependencies'],
                    'step_states':dict.fromkeys(STEPS, 'pending'), 'copy_evidence':None}
        manifest['execution_plan'] = concrete_plan(manifest, proposal)
        manifest['execution_plan_digest'] = fingerprint(manifest['execution_plan'])
        receipt.update(plan_digest=proposal['plan_digest'], execution_plan_digest=manifest['execution_plan_digest'])
        if local_approval:
            receipt['approval'] = local_approval
        atomic_write_bytes(directory / 'after.md', draft.after)
        if draft.before is not None:
            atomic_write_bytes(directory / 'before.md', draft.before)
        self.store.checkpoint('attachment_snapshots')
        validate_execution(self.store, manifest, proposal, snapshots=True)
        atomic_write_json(directory / 'manifest.json', manifest)
        self.store.blocked = True
        self.store.checkpoint('attachment_manifest')
        proposal['state'] = 'committing'
        self.store._save(proposal)
        self.store.checkpoint('attachment_committing')
        return manifest, None

    def save(self, manifest, stage=None):
        if stage:
            self.store.checkpoint('attachment_' + stage)
        atomic_write_json(self.store.operations / manifest['operation_id'] / 'manifest.json', manifest)
        if stage:
            self.store.checkpoint('attachment_' + stage + '_logged')

    def verified(self, handle, asset):
        checksum, count = hashlib.sha256(), 0
        for chunk in handle.chunks(time.monotonic() + 60):
            checksum.update(chunk)
            count += len(chunk)
        if handle.identity() != handle.initial or count != asset['size'] or checksum.hexdigest() != asset['sha256']:
            raise AgentError('attachment_evidence_changed', '附件磁盘证据不匹配，保留现场', 503)

    def copy(self, proposal, manifest, part):
        if part.exists():
            return
        value = self.uploads.load(manifest['upload_id'])
        self.short(lambda:self.attachments.prepare_submission(self.client(proposal), proposal))
        checksum, count = hashlib.sha256(), 0
        with LocalFileHandle(str(self.uploads.path(value['upload_id'], 'blob.bin')), read=True) as source:
            with part.open('xb') as output:
                for chunk in source.chunks(time.monotonic() + 60):
                    output.write(chunk)
                    checksum.update(chunk); count += len(chunk)
                    if count == len(chunk):
                        output.flush(); os.fsync(output.fileno())
                        self.store.checkpoint('attachment_copy_partial')
                output.flush(); os.fsync(output.fileno())
            if source.identity() != source.initial or count != value['declared_bytes'] or checksum.hexdigest() != value['declared_sha256']:
                raise AgentError('upload_changed', '暂存来源字节或身份已变化', 409)
        self.store.checkpoint('attachment_copy_fsynced')

    def run(self, proposal, manifest, guard=None):
        directory = self.store.operations / manifest['operation_id']
        part = directory / 'binary.part'
        binary, metadata = targets(self.repository, proposal)
        receipt_path = self.store.receipts / (proposal['proposal_id'] + '.json')
        if receipt_path.exists():
            self.short(lambda:self.store._finish(manifest, proposal))
            return manifest['receipt']
        asset = proposal['normalized_content']['attachment']
        if binary.exists():
            if manifest['copy_evidence'] is None:
                raise AgentError('attachment_name_conflict', '最终名称由外部对象占用，不能收编', 409)
            source_path = binary
        else:
            self.copy(proposal, manifest, part)
            source_path = part
        # Keep this exact verified handle open across the short publication.
        with LocalFileHandle(str(source_path), read=True, delete=source_path == part) as handle:
            self.verified(handle, asset)
            evidence = manifest['copy_evidence']
            if evidence is not None:
                if any(handle.initial[key] != evidence['identity'][key] for key in ('volume', 'index', 'size', 'created', 'written')):
                    raise AgentError('attachment_identity_changed', '同名文件不属于本操作，保留现场', 503)
            elif source_path == part:
                manifest['copy_evidence'] = {'bytes':asset['size'], 'sha256':asset['sha256'], 'identity':handle.initial}
                manifest['step_states']['binary_copy'] = 'completed'
                self.short(lambda:self.save(manifest, 'copy_evidence'))
            else:
                raise AgentError('attachment_identity_changed', '缺少本操作发布证据', 503)

            def publish():
                current = metadata.read_bytes() if metadata.exists() else None
                if digest(current) == manifest['after_digest']:
                    if source_path != binary:
                        raise AgentError('attachment_evidence_changed', '元数据已写但正式字节缺失', 503)
                    self.finish_metadata(proposal, manifest)
                    return
                if digest(current) != manifest['before_digest']:
                    raise AgentError('revision_conflict', '目标已发生第三方修改，保留现场', 409)
                self.attachments.prepare_submission(self.client(proposal), proposal, allow_published=source_path == binary)
                if proposal['confirmation_mode'] == 'local_web':
                    self.store._verify_approval(manifest, proposal, check_authorization=True)
                if source_path == part:
                    if binary.exists():
                        raise AgentError('attachment_name_conflict', '最终名称被占用，请重新核查', 409)
                    binary.parent.mkdir(parents=True, exist_ok=True)
                    if targets(self.repository, proposal) != (binary, metadata):
                        raise AgentError('attachment_path_changed', '附件目标路径变化', 409)
                    manifest['state'] = 'applying'
                    self.save(manifest, 'applying')
                    handle.rename_verified(binary)
                    self.store.checkpoint('attachment_binary')
                manifest['step_states']['binary_publish'] = 'completed'
                self.save(manifest, 'binary')
                after = (directory / 'after.md').read_bytes()
                before = (directory / 'before.md').read_bytes() if manifest['before_digest'] is not None else None
                record_write = None if proposal['normalized_content']['owner_kind'] == 'project' else PreparedMarkdownWrite(metadata, proposal['target_id'], after.decode('utf-8'), before, manifest['history_version'])
                draft = PreparedAttachment(binary, metadata, before, after, proposal['normalized_content'], record_write)
                def progress(stage):
                    self.store.checkpoint('attachment_' + stage)
                    manifest['step_states']['history_snapshot' if stage == 'history' else 'metadata_write'] = 'completed'
                    self.save(manifest)
                self.store.executing = True
                try:
                    self.repository.apply_attachment_metadata(draft, progress)
                finally:
                    self.store.executing = False
                self.finish_metadata(proposal, manifest)
            self.short(publish, guard)
        self.store.recover()  # Metadata-only pass; never performs attachment hash.
        return manifest['receipt']

    def finish_metadata(self, proposal, manifest):
        if manifest['history_version']:
            path = history_path(self.repository.history_dir, proposal['target_id'], manifest['history_version'])
            if not path.exists() or digest(path.read_bytes()) != manifest['before_digest']:
                raise AgentError('attachment_history_missing', '附件更新历史证据缺失', 503)
        value = self.uploads.load(manifest['upload_id'])
        expected_binding = {'schema_version':1, 'proposal_id':proposal['proposal_id'], 'version':proposal['version'], 'owner_revision':proposal['base_revision']}
        if value['client_id'] != proposal['client_id'] or value['binding'] != expected_binding or value['consumption'] not in (None, {'schema_version':1, 'operation_id':manifest['consumption_id']}):
            raise AgentError('attachment_consumption_conflict', '暂存消费身份不一致，保留现场', 503)
        value.update(state='consumed', consumption={'schema_version':1, 'operation_id':manifest['consumption_id']})
        self.uploads.write(value)
        self.store.checkpoint('attachment_consumed')
        manifest['step_states'] = dict.fromkeys(STEPS, 'completed')
        self.save(manifest)
        self.store._finish(manifest, proposal)

    def commit(self, client, proposal_id, payload, guard=None, local_approval=None):
        if not isinstance(payload, dict) or set(payload) - {'version', 'preview_digest', 'confirmation'}:
            raise AgentError('unknown_field', '提交只能引用已预览版本')
        self.short(self.store.preflight)
        proposal = self.short(lambda:self.store.owned(client, proposal_id))
        if payload.get('version') != proposal['version'] or payload.get('preview_digest') != proposal.get('preview_digest'):
            raise AgentError('version_conflict', '提交版本与原预览不一致', 409)
        if proposal['kind'] != 'attachment':
            raise AgentError('invalid_kind', '不是附件提案')
        if proposal['state'] == 'committed':
            return self.short(lambda:self.store.check_commit(proposal, payload.get('version'), payload.get('preview_digest'), payload.get('confirmation')))
        upload_id = proposal['normalized_content']['upload_id']
        directory = self.store.operations / (proposal_id + '-' + str(proposal['version']))
        self.uploads._safe(directory)
        self.uploads._safe(directory / '.workbench-service.lock')
        with self.uploads.session_lock(upload_id), DataDirectoryLock(directory):
            path = directory / 'manifest.json'
            if path.exists():
                manifest = read_json(path)
                self.short(lambda:validate_execution(self.store, manifest, proposal, snapshots=True))
            else:
                manifest, receipt = self.short(lambda:self.accept(proposal, payload, local_approval), guard)
                if receipt is not None:
                    return receipt
            try:
                return self.run(proposal, manifest, guard)
            except Exception:
                self.store.blocked = True
                raise


    def recover(self, proposal_id=None, guard=None):
        self.short(self.store.preflight)
        for path in sorted(self.store.operations.glob('*/manifest.json')):
            manifest = read_json(path)
            if manifest['kind'] != 'attachment' or manifest['state'] in {'committed', 'abandoned'} or proposal_id is not None and manifest['proposal_id'] != proposal_id:
                continue
            proposal = self.short(lambda:self.store._load(manifest['proposal_id'], expire=False))
            directory = path.parent
            self.uploads._safe(directory)
            self.uploads._safe(directory / '.workbench-service.lock')
            try:
                with self.uploads.session_lock(manifest['upload_id']), DataDirectoryLock(directory):
                    self.short(lambda:validate_execution(self.store, manifest, proposal, snapshots=True))
                    self.uploads.protected(self.uploads.load(manifest['upload_id']))
                    self.run(proposal, manifest, guard)
            except (AgentError, OSError, ValueError):
                self.store.blocked = True
                continue
        return self.store.recover()


def recover_attachments(repository):
    store = getattr(repository, 'agent_proposals', None)
    if store is None:
        return {'blocked':False, 'operations':[]}
    runtime = getattr(repository, 'agent_runtime', None)
    security = runtime.security() if runtime and runtime.status()['workspace_id'] else getattr(store, 'security', None)
    if security is None:
        return store.recover()
    from .agent_service import AgentService
    service = AgentService(repository, security)
    return AttachmentExecution(service).recover()
