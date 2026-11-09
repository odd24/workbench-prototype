"""Durable ordinary web upload operations, independent of Agent authorization.

Only operation evidence lives here; attachment metadata stays in Markdown.
Both web and Agent publication use the same PreparedAttachment domain candidate.
"""

import hashlib
import json
import os
import re
import time
import uuid
from contextlib import contextmanager

from .agent_file_handles import LocalFileHandle, SUPPORTED
from .attachment_prepared import PreparedAttachment
from .document_attachments import safe_local_path, attachment_items
from .history import history_path
from .persistence import atomic_write_json, atomic_write_bytes
from .write_coordinator import DataDirectoryLock, PreparedMarkdownWrite, RevisionConflict, content_revision
from .agent_security import AgentError


class UploadRecoveryError(AgentError):
    def __init__(self, key):
        super().__init__('document_upload_recovery_required', '文档上传日志需要核查，未执行恢复写入', 503, details={'operation_id':key})


class DocumentUploads:
    def __init__(self, repository):
        self.repository = repository
        self.directory = repository.root / '.workbench-document-uploads'
        self.executing = None

    def checkpoint(self, stage):
        """Fault-injection seam; no user supplied code is executed."""

    def folder(self, key):
        if not isinstance(key, str) or str(uuid.UUID(key)) != key:
            raise ValueError('上传操作标识无效')
        return safe_local_path(self.repository.root, '.workbench-document-uploads/' + key, (self.directory,), decode=False)

    def load(self, key):
        try:
            return self._load(key)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError):
            raise UploadRecoveryError(key) from None

    def _load(self, key):
        folder = self.folder(key)
        log = safe_local_path(folder, 'operation.json', (folder,), required=True)
        if log.stat().st_size > 8 * 1048576:
            raise ValueError('上传日志超过完整预检上限')
        value = json.loads(log.read_text(encoding='utf-8'))
        fields = {'schema_version', 'operation_id', 'document_id', 'filename', 'size', 'base_revision', 'state', 'view', 'sha256', 'identity', 'history_version', 'receipt', 'after_revision', 'removed', 'compacted', 'stream_identity', 'partial'}
        if not isinstance(value, dict) or set(value) != fields or type(value['schema_version']) is not int or value['schema_version'] != 1 or value['operation_id'] != key or value['state'] not in {'receiving', 'failed', 'prepared', 'applying', 'completed', 'abandoned'} or not re.fullmatch(r'DOC-\d+', value['document_id']) or type(value['size']) is not int or not 0 <= value['size'] <= 104857600 or not re.fullmatch('[a-f0-9]{64}', value['base_revision']) or type(value['removed']) is not bool or type(value['compacted']) is not bool:
            raise ValueError('上传日志未知或损坏，保留现场')
        from .security import validate_portable_filename
        if not isinstance(value['filename'], str):
            raise ValueError('上传名称无效')
        validate_portable_filename(value['filename'])
        if value['stream_identity'] is not None and (not isinstance(value['stream_identity'], dict) or set(value['stream_identity']) != {'device', 'inode'} or any(type(v) is not int for v in value['stream_identity'].values())):
            raise ValueError('流文件身份无效')
        for field in ('sha256', 'after_revision'):
            if value[field] is not None and (not isinstance(value[field], str) or not re.fullmatch('[a-f0-9]{64}', value[field])):
                raise ValueError('上传摘要无效')
        if value['identity'] is not None and (not isinstance(value['identity'], dict) or set(value['identity']) != {'volume', 'index', 'size', 'created', 'written', 'changed'} or any(type(v) is not int for v in value['identity'].values())):
            raise ValueError('发布文件身份无效')
        if value['partial'] is not None and (not isinstance(value['partial'], dict) or set(value['partial']) != {'size', 'sha256', 'identity', 'file_identity'} or type(value['partial']['size']) is not int or not 0 <= value['partial']['size'] <= value['size'] or not re.fullmatch('[a-f0-9]{64}', value['partial']['sha256']) or value['partial']['identity'] != value['stream_identity'] or not isinstance(value['partial']['file_identity'], dict) or set(value['partial']['file_identity']) != {'volume', 'index', 'size', 'created', 'written', 'changed'} or any(type(v) is not int for v in value['partial']['file_identity'].values())):
            raise ValueError('失败暂存证据无效')
        if value['compacted'] and value['state'] != 'completed' or value['removed'] and value['state'] not in {'failed', 'abandoned', 'completed'}:
            raise ValueError('上传终结状态无效')
        if value['view'] is not None:
            view = value['view']
            expected_view = {'owner_kind', 'owner_id', 'project_id', 'title', 'attachment', 'binary_relative', 'metadata_relative', 'metadata_before', 'metadata_after', 'body', 'insert_link', 'category_revision', 'unparsed_binary'}
            if not isinstance(view, dict) or set(view) != expected_view or view['insert_link'] is not True or view['unparsed_binary'] is not True or not isinstance(view['body'], str) or not isinstance(view['category_revision'], str) or not re.fullmatch('[a-f0-9]{64}', view['category_revision']):
                raise ValueError('上传候选结构未知')
            asset = view['attachment']
            import mimetypes
            if not isinstance(asset, dict) or set(asset) != {'name', 'path', 'size', 'mime', 'category', 'id', 'sha256'} or not isinstance(asset['name'], str) or not isinstance(asset['category'], str) or type(asset['size']) is not int or asset['mime'] != (mimetypes.guess_type(asset['name'])[0] or 'application/octet-stream'):
                raise ValueError('上传候选附件不是领域元数据')
            from .agent_attachments import relative_paths
            relative_paths(view)
            if view['owner_kind'] != 'document' or view['owner_id'] != value['document_id'] or view['attachment']['id'] != 'ASSET-' + uuid.UUID(key).hex or view['attachment']['size'] != value['size'] or view['attachment']['sha256'] != value['sha256']:
                raise ValueError('上传日志归属不一致')
            before = safe_local_path(folder, 'before.md', (folder,), required=True).read_bytes()
            after = safe_local_path(folder, 'after.md', (folder,), required=True).read_bytes()
            from .attachment_prepared import serialize_attachment_candidate, raw_markdown_body
            from .markdown_io import load_markdown_text
            from .assets import AttachmentRepository
            original, _ = load_markdown_text(before.decode('utf-8'))
            updated = view['metadata_after']
            previous_items = original.get('attachments', [])
            next_items = updated.get('attachments', [])
            if view['metadata_before'] != original or asset['category'] != original.get('category', '未分类') or updated.get('id') != value['document_id'] or updated.get('type') != 'document' or view['body'] != AttachmentRepository.append_attachment_link(raw_markdown_body(before), view['attachment']) or {k:v for k,v in updated.items() if k not in {'updated', 'attachments'}} != {k:v for k,v in original.items() if k not in {'updated', 'attachments'}} or attachment_items(next_items[:-1]) != attachment_items(previous_items) or (json.loads(next_items[-1]) if isinstance(next_items[-1], str) else next_items[-1]) != view['attachment']:
                raise ValueError('上传候选不是原文档的附件追加')
            if content_revision(before) != value['base_revision'] or after != serialize_attachment_candidate(view) or content_revision(after) != value['after_revision']:
                raise ValueError('上传快照不匹配')
            history_path(self.repository.history_dir, value['document_id'], value['history_version'])
        elif value['state'] not in {'receiving', 'failed', 'abandoned'} and not value['compacted']:
            raise ValueError('上传计划缺失')
        receipt = value['receipt']
        if value['state'] == 'completed':
            if not isinstance(receipt, dict) or set(receipt) != {'attachment', 'revision', 'base_revision', 'document_id'} or receipt['revision'] != value['after_revision'] or receipt['base_revision'] != value['base_revision'] or receipt['document_id'] != value['document_id'] or value['after_revision'] is None or value['sha256'] is None:
                raise ValueError('上传回执不匹配')
            asset = receipt['attachment']
            if not isinstance(asset, dict) or set(asset) != {'id', 'name', 'path', 'size', 'sha256', 'mime', 'category'} or asset['id'] != 'ASSET-' + uuid.UUID(key).hex or asset['size'] != value['size'] or asset['sha256'] != value['sha256'] or type(asset['size']) is not int or not isinstance(asset['category'], str):
                raise ValueError('上传回执附件无效')
            import mimetypes
            validate_portable_filename(asset['name'])
            if asset['mime'] != (mimetypes.guess_type(asset['name'])[0] or 'application/octet-stream') or asset['path'] != '../assets/' + ('images/' if asset['mime'].startswith('image/') else 'files/') + asset['name'] or value['view'] is not None and asset != value['view']['attachment']:
                raise ValueError('上传回执目标无效')
        elif receipt is not None:
            raise ValueError('未完成上传不能有正式回执')
        allowed = {'operation.json', '.workbench-service.lock', 'before.md', 'after.md', 'binary.part'}
        part = folder / 'binary.part'
        if (value['removed'] or value['state'] == 'completed') and part.exists():
            raise ValueError('已终结上传出现未知源字节，保留现场')
        for child in folder.iterdir():
            if child.name not in allowed:
                raise ValueError('上传目录含未知对象')
            safe_local_path(folder, child.name, (folder,), required=True)
        return value

    def save(self, value, stage):
        atomic_write_json(self.folder(value['operation_id']) / 'operation.json', value)
        self.checkpoint(stage)

    def guard(self):
        if not self.directory.exists():
            return
        if self.directory.resolve() != self.directory.absolute():
            raise ValueError('上传目录包含链接')
        for value in self.preflight():
            if value['operation_id'] != self.executing and value['state'] in {'prepared', 'applying'}:
                raise AgentError('document_upload_pending', '文档附件正在提交或需要恢复，请查询原上传操作', 503, details={'operation_id':value['operation_id']})

    def pending(self):
        try:
            return self.directory.exists() and any(self.load(p.name)['state'] in {'prepared', 'applying'} for p in self.directory.iterdir())
        except (OSError, ValueError, KeyError, TypeError, AgentError):
            return True

    def preflight(self):
        if not self.directory.exists():
            return []
        inventory = []
        for path in self.directory.iterdir():
            value = self.load(path.name)
            inventory.append({key:value[key] for key in ('operation_id', 'document_id', 'state', 'size', 'removed')} | {'binary_relative':value['view']['binary_relative'] if value['view'] else None})
        return inventory

    def report(self):
        items, errors = [], []
        for folder in self.directory.glob('*'):
            try:
                items.append(self.public(self.load(folder.name)))
            except (AgentError, ValueError):
                try:
                    key = str(uuid.UUID(folder.name))
                except ValueError:
                    key = '(未知条目)'
                errors.append({'operation_id':key, 'code':'document_upload_recovery_required', 'message':'未知或不完整操作，保留现场；请按维护说明核查'})
        return {'items':items, 'errors':errors}

    def maintain(self, short, cleanup=False):
        values = self.preflight()  # Entire format/path inventory before ANY write.
        results = []
        for value in values:
            try:
                with self.operation_lock(value['operation_id']):
                    current = self.load(value['operation_id'])
                    result = self._query_locked(current, short)
                    if cleanup:
                        self.retire(self.load(value['operation_id']))
                    results.append(result)
            except FileExistsError:
                continue  # A live receiver owns this operation; never wait on it.
        return results

    def abandon(self, document_id, key, short):
        self.preflight()
        with self.operation_lock(key):
            value = self.load(key)
            if value['document_id'] != document_id or value['state'] == 'completed':
                raise RevisionConflict('不能放弃其他文档或已完成的操作')
            def mark():
                value['state'] = 'abandoned'
                self.save(value, 'abandoned')
                return self.public(value)
            return short(mark)  # No file rollback; any published bytes stay protected.

    def abandon_empty(self, key, short):
        folder = self.folder(key)
        if not folder.is_dir() or any(p.name != '.workbench-service.lock' for p in folder.iterdir()):
            raise UploadRecoveryError(key)
        for other in self.directory.iterdir():
            if other != folder:
                self.load(other.name)
        with self.operation_lock(key):
            if any(p.name != '.workbench-service.lock' for p in folder.iterdir()):
                raise UploadRecoveryError(key)
            value = {'schema_version':1, 'operation_id':key, 'document_id':'DOC-0000', 'filename':'uninitialized',
                     'size':0, 'base_revision':content_revision(b''), 'state':'abandoned', 'view':None, 'sha256':None,
                     'identity':None, 'history_version':None, 'receipt':None, 'after_revision':None,
                     'removed':True, 'compacted':False, 'stream_identity':None, 'partial':None}
            return short(lambda:(self.save(value, 'empty_abandoned'), self.public(value))[1])

    def guard_relocation(self):
        if self.directory.exists():
            for folder in self.directory.iterdir():
                value = self.load(folder.name)
                if value['state'] in {'receiving', 'prepared', 'applying'} or value['state'] != 'completed' and not value['removed']:
                    raise RevisionConflict('文档上传尚未结束，请查询原操作后再切换目录')

    @contextmanager
    def operation_lock(self, key):
        folder = self.folder(key)
        safe_local_path(folder, '.workbench-service.lock', (folder,), decode=False)
        with DataDirectoryLock(folder):
            safe_local_path(folder, '.workbench-service.lock', (folder,), required=True, decode=False)
            yield

    def public(self, value):
        return {key:value[key] for key in ('operation_id', 'document_id', 'state', 'base_revision', 'receipt')}

    def receive(self, document_id, key, filename, size, revision, stream, short):
        from .security import validate_portable_filename
        if not SUPPORTED:
            raise AgentError('unsupported_platform', '文档附件上传仅支持可验证的Windows本机固定NTFS', 503)
        validate_portable_filename(filename, label='附件文件名')
        if type(size) is not int or not 0 <= size <= 104857600 or not isinstance(revision, str) or not re.fullmatch('[a-f0-9]{64}', revision):
            raise ValueError('上传大小或文档版本无效')
        folder = self.folder(key)
        def begin():
            self.guard()
            if folder.exists():
                old = self.load(key)
                if any(old[k] != v for k,v in {'document_id':document_id, 'filename':filename, 'size':size, 'base_revision':revision}.items()):
                    raise RevisionConflict('上传操作标识已用于不同内容')
                return old
            if self.repository.write_guard:
                self.repository.write_guard()
            owner, _path, before, _items = self.repository.attachment_target('document', document_id)
            if content_revision(before) != revision:
                raise RevisionConflict('文档已变化，请处理冲突后再上传')
            probe = self.repository.prepare_attachment_create('document', document_id, filename, size, '0' * 64, owner.get('category', '未分类'), True, revision, 'ASSET-' + uuid.UUID(key).hex)
            safe_local_path(self.repository.root, probe.view['binary_relative'], (self.repository.global_assets_dir / 'images', self.repository.global_assets_dir / 'files'), decode=False)
            try:
                with LocalFileHandle(str(_path), read=False):
                    pass  # Verify local fixed NTFS and every ancestor before receiving bytes.
            except AgentError:
                raise AgentError('unsupported_platform', '目标文件系统或路径无法通过本机安全验证，未接收上传', 503) from None
            import shutil
            values = self.preflight()
            if sum(v['state'] in {'receiving', 'prepared', 'applying'} for v in values) >= 1000:
                raise ValueError('上传操作日志达到上限，请先按维护说明核查')
            reserved = sum(v['size'] for v in values if not v['removed'] and v['state'] != 'completed')
            if reserved + size > 1024 * 1048576 or shutil.disk_usage(self.repository.root).free < size + 16 * 1048576:
                raise ValueError('附件暂存预算或可用磁盘不足')
            folder.mkdir(parents=True)
            self.checkpoint('folder_created')
            return None
        old = short(begin)
        if old is not None:
            return self.query(document_id, key, short)
        with self.operation_lock(key):
            if (folder / 'operation.json').exists():
                raise UploadRecoveryError(key)
            value = {'schema_version':1, 'operation_id':key, 'document_id':document_id, 'filename':filename,
                     'size':size, 'base_revision':revision, 'state':'receiving', 'view':None, 'sha256':None,
                     'identity':None, 'history_version':None, 'receipt':None, 'after_revision':None,
                     'removed':False, 'compacted':False, 'stream_identity':None, 'partial':None}
            self.save(value, 'receiving')
            count, checksum, deadline = 0, hashlib.sha256(), time.monotonic() + 60
            try:
                with (folder / 'binary.part').open('xb') as output:
                    info = os.fstat(output.fileno())
                    value['stream_identity'] = {'device':info.st_dev, 'inode':info.st_ino}
                    self.save(value, 'stream_identity')
                    while count < size:
                        if time.monotonic() > deadline:
                            raise ValueError('上传超时')
                        chunk = stream.read(min(65536, size - count))
                        if not chunk or len(chunk) > size - count:
                            raise ValueError('附件上传不完整')
                        count += len(chunk); checksum.update(chunk); output.write(chunk)
                    output.flush(); os.fsync(output.fileno())
                self.checkpoint('stream_fsynced')
                def prepare():
                    self.guard()
                    if self.repository.write_guard:
                        self.repository.write_guard()
                    owner, _path = self.repository.get_document(document_id)
                    if not owner:
                        raise FileNotFoundError(document_id)
                    draft = self.repository.prepare_attachment_create('document', document_id, filename, size, checksum.hexdigest(), owner.get('category', '未分类'), True, revision, 'ASSET-' + uuid.UUID(key).hex)
                    atomic_write_bytes(folder / 'before.md', draft.before)
                    atomic_write_bytes(folder / 'after.md', draft.after)
                    from datetime import datetime
                    value.update(state='prepared', view=draft.view, sha256=checksum.hexdigest(), after_revision=content_revision(draft.after), history_version=datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + uuid.uuid4().hex[:8])
                    self.save(value, 'prepared')
                short(prepare)
            except Exception:
                if value['state'] == 'receiving':
                    value['state'] = 'failed'
                    self.seal_failure(value)
                    self.save(value, 'failed')
                raise
            return self.run(self.load(key), short)

    def query(self, document_id, key, short):
        if not self.folder(key).exists():
            raise AgentError('document_upload_not_found', '原操作尚未被服务接收', 404)
        if not (self.folder(key) / 'operation.json').is_file():
            raise UploadRecoveryError(key)
        self.preflight()
        with self.operation_lock(key):
            value = self.load(key)
            if value['document_id'] != document_id:
                raise FileNotFoundError('上传操作不属于此文档')
            return self._query_locked(value, short)

    def _query_locked(self, value, short):
        if value['state'] == 'receiving':
            value['state'] = 'failed'  # An unlocked incomplete stream is never promoted.
            self.seal_failure(value)
            self.save(value, 'failed')
        if value['state'] in {'prepared', 'applying'}:
            return self.run(value, short)
        return self.public(value)

    def seal_failure(self, value):
        part = self.folder(value['operation_id']) / 'binary.part'
        if not part.exists():
            value['removed'] = True
            return
        if value['stream_identity'] is None:
            raise UploadRecoveryError(value['operation_id'])
        info = part.stat()
        if {'device':info.st_dev, 'inode':info.st_ino} != value['stream_identity'] or info.st_size > value['size']:
            raise UploadRecoveryError(value['operation_id'])
        checksum, size = hashlib.sha256(), 0
        with LocalFileHandle(str(part), read=True) as handle:
            locked = part.stat()
            if {'device':locked.st_dev, 'inode':locked.st_ino} != value['stream_identity']:
                raise UploadRecoveryError(value['operation_id'])
            for chunk in handle.chunks(time.monotonic() + 60):
                checksum.update(chunk); size += len(chunk)
            if handle.identity() != handle.initial:
                raise UploadRecoveryError(value['operation_id'])
        value['partial'] = {'identity':value['stream_identity'], 'size':size, 'sha256':checksum.hexdigest(), 'file_identity':handle.initial}

    def retire(self, value):
        folder = self.folder(value['operation_id'])
        if value['state'] == 'completed':
            # Persist the complete idempotent result before pruning snapshots.
            value.update(compacted=True, view=None)
            self.save(value, 'compacted')
            for name, expected in (('before.md', value['base_revision']), ('after.md', value['after_revision'])):
                path = folder / name
                if not path.exists():
                    continue
                with LocalFileHandle(str(path), read=True, delete=True) as handle:
                    checksum = hashlib.sha256()
                    for chunk in handle.chunks(time.monotonic() + 60): checksum.update(chunk)
                    if handle.identity() != handle.initial or checksum.hexdigest() != expected:
                        raise UploadRecoveryError(value['operation_id'])
                    handle.delete_verified()
            return
        if value['state'] not in {'failed', 'abandoned'} or value['view'] is not None:
            return
        part = folder / 'binary.part'
        if part.exists():
            evidence = value['partial']
            if evidence is None or value['stream_identity'] is None:
                raise UploadRecoveryError(value['operation_id'])
            info = part.stat()
            if {'device':info.st_dev, 'inode':info.st_ino} != evidence['identity']:
                raise UploadRecoveryError(value['operation_id'])
            with LocalFileHandle(str(part), read=True, delete=True) as handle:
                locked = part.stat()
                if handle.initial != evidence['file_identity'] or {'device':locked.st_dev, 'inode':locked.st_ino} != evidence['identity']:
                    raise UploadRecoveryError(value['operation_id'])
                checksum, size = hashlib.sha256(), 0
                for chunk in handle.chunks(time.monotonic() + 60): checksum.update(chunk); size += len(chunk)
                if handle.identity() != handle.initial or size != evidence['size'] or checksum.hexdigest() != evidence['sha256']:
                    raise UploadRecoveryError(value['operation_id'])
                handle.delete_verified()
            self.checkpoint('failed_deleted')
        value['removed'] = True
        self.save(value, 'failed_retired')

    def run(self, value, short):
        from .agent_attachment_execution import AttachmentExecution
        from .attachment_prepared import serialize_attachment_candidate
        folder = self.folder(value['operation_id'])
        view = value['view']
        binary = safe_local_path(self.repository.root, view['binary_relative'], (self.repository.global_assets_dir / 'images', self.repository.global_assets_dir / 'files'), decode=False)
        metadata = safe_local_path(self.repository.root, view['metadata_relative'], (self.repository.documents_dir,), required=True, decode=False)
        part = folder / 'binary.part'
        source = part if part.exists() else binary
        if not SUPPORTED:
            raise AgentError('unsupported_platform', '当前文档附件安全发布仅支持本机Windows固定NTFS', 503)
        with LocalFileHandle(str(source), read=True, delete=source == part) as handle:
            if source == part:
                locked = part.stat()
                if {'device':locked.st_dev, 'inode':locked.st_ino} != value['stream_identity']:
                    raise UploadRecoveryError(value['operation_id'])
            # Reuse exactly the Agent stream/SHA/identity verification algorithm.
            AttachmentExecution.verified(self, handle, view['attachment'])
            if value['identity'] is None:
                if source != part:
                    raise ValueError('缺少原上传身份，保留现场')
                value['identity'] = handle.initial
                self.save(value, 'identity')
            elif any(value['identity'][key] != handle.initial[key] for key in ('volume', 'index', 'size', 'created', 'written')):
                raise ValueError('上传文件身份变化，保留现场')
            def publish():
                self.executing = value['operation_id']
                try:
                    self.guard()
                    if self.repository.write_guard:
                        self.repository.write_guard()
                    before = (folder / 'before.md').read_bytes()
                    after = (folder / 'after.md').read_bytes()
                    current = metadata.read_bytes()
                    if current == after:
                        if source != binary:
                            raise ValueError('正文已写但附件未发布')
                    else:
                        if current != before:
                            raise RevisionConflict('文档已发生外部修改，保留原上传供核查')
                        owner, owner_path = self.repository.get_document(value['document_id'])
                        if not owner or owner_path != metadata or owner.get('category', '未分类') != view['attachment']['category']:
                            raise RevisionConflict('原文档归属或分类变化')
                        if source == part:
                            binary.parent.mkdir(parents=True, exist_ok=True)
                            safe_local_path(self.repository.root, view['binary_relative'], (self.repository.global_assets_dir / 'images', self.repository.global_assets_dir / 'files'), decode=False)
                            value['state'] = 'applying'; self.save(value, 'applying')
                            handle.rename_verified(binary)
                            self.checkpoint('binary')
                        write = PreparedMarkdownWrite(metadata, value['document_id'], after.decode('utf-8'), before, value['history_version'])
                        draft = PreparedAttachment(binary, metadata, before, after, view, write)
                        self.repository.apply_attachment_metadata(draft, self.checkpoint)
                    history = history_path(self.repository.history_dir, value['document_id'], value['history_version'])
                    if not history.exists() or history.read_bytes() != before:
                        raise ValueError('上传历史证据缺失')
                    if after != serialize_attachment_candidate(view):
                        raise ValueError('上传正文与领域计划不一致')
                    value.update(state='completed', receipt={'attachment':view['attachment'], 'revision':content_revision(after), 'base_revision':value['base_revision'], 'document_id':value['document_id']})
                    self.save(value, 'completed')
                    return self.public(value)
                finally:
                    self.executing = None
            return short(publish)
