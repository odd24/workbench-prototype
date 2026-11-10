"""Pure single-item deletion plans and verified, non-replacing trash moves.

Publication evidence and index/receipt recovery belong to ProposalStore. These
domain primitives never infer permission to repeat a move from missing bytes.
"""

import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from .agent_file_handles import LocalFileHandle, SUPPORTED
from .agent_security import AgentError
from .document_attachments import safe_local_path
from .markdown_io import load_markdown_text
from .write_coordinator import content_revision, RevisionConflict


DELETE_KINDS = {'issue', 'todo', 'info', 'document', 'concept_map'}
RAW_LIMIT = 1048576
IDENTITY_FIELDS = ('volume', 'index', 'created')
_HELD_SOURCE_SEAL = object()


class HeldDeleteSource:
    """In-process capability valid only during this exact verified move handle."""
    def __init__(self, prepared, handle, seal):
        if seal is not _HELD_SOURCE_SEAL:
            raise ValueError('不能自行构造持有的删除来源')
        self._prepared, self._handle, self._active = prepared, handle, True

    def validate(self):
        if not self._active or self._handle.identity() != self._handle.initial:
            raise ValueError('删除来源句柄已失效或变化')

    def __getattr__(self, name):
        self.validate()
        return getattr(self._prepared, name)


def validate_held_source(value):
    if not isinstance(value, HeldDeleteSource):
        raise ValueError('未提供内部有效删除句柄')
    value.validate()


def require_platform():
    if not supported():
        raise AgentError('unsupported_platform', 'Agent删除仅支持已验证的Windows本机固定NTFS普通文件', 503)


def supported():
    from . import agent_file_handles
    return SUPPORTED and agent_file_handles.SUPPORTED


def stable_identity(identity):
    return {key: identity[key] for key in IDENTITY_FIELDS}


def read_handle(handle):
    if handle.initial['size'] > RAW_LIMIT:
        raise ValueError('删除对象超过1MiB，不能完整预览')
    raw = bytearray()
    for chunk in handle.chunks(time.monotonic() + 5):
        raw.extend(chunk)
        if len(raw) > RAW_LIMIT:
            raise ValueError('删除对象超过1MiB，不能完整预览')
    if handle.identity() != handle.initial or len(raw) != handle.initial['size']:
        raise RevisionConflict('删除对象在读取期间变化，请重新预览')
    return bytes(raw)


def deletion_token(kind, proposal_id, version):
    if kind not in DELETE_KINDS or str(uuid.UUID(proposal_id)) != proposal_id or type(version) is not int or version < 1:
        raise ValueError('删除操作身份无效')
    prefix = 'concept-map' if kind == 'concept_map' else 'document' if kind == 'document' else 'record'
    return f'{prefix}-agent-{proposal_id}-{version}'


def validate_token(token, kind):
    prefix = 'concept-map' if kind == 'concept_map' else 'document' if kind == 'document' else 'record'
    match = re.fullmatch(re.escape(prefix) + r'-agent-([a-f0-9-]{36})-([1-9][0-9]*)', token) if isinstance(token, str) else None
    if not match or deletion_token(kind, match[1], int(match[2])) != token:
        raise ValueError('回收站操作身份无效')
    return token


def controlled(root, relative, *, required=True):
    return safe_local_path(root, relative, (root,), decode=False, required=required)


def read_trash_index(root):
    """Validate complete index metadata before moving any Agent source."""
    path = controlled(root, '.trash/index.json')
    with path.open('rb') as stream:
        raw = stream.read(RAW_LIMIT + 1)
    if len(raw) > RAW_LIMIT:
        raise ValueError('回收索引超过完整核验上限')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('回收索引存在重复字段')
            result[key] = value
        return result
    index = json.loads(raw.decode('utf-8'), object_pairs_hook=unique)
    if not isinstance(index, dict):
        raise ValueError('回收索引不是对象')
    required = {'token', 'id', 'kind', 'title', 'deleted_at', 'original_path', 'trash_path'}
    for key, value in index.items():
        if not isinstance(value, dict) or not required <= value.keys() or value['token'] != key or not isinstance(key, str) or '/' in key or '\\' in key or key in {'.', '..'} or value['kind'] not in {'project', 'record', 'document', 'concept-map'} or any(not isinstance(value[name], str) for name in required):
            raise ValueError('回收索引成员未知或损坏')
        datetime.fromisoformat(value['deleted_at'])
        if 'delete_schema_version' in value and (type(value['delete_schema_version']) is not int or value['delete_schema_version'] != 1 or set(value) != required | {'delete_schema_version', 'original_relative_path', 'agent_operation_id'}):
            raise ValueError('回收索引删除版本未知')
    return raw, index


def source_metadata(raw, item_id, kind):
    if kind == 'concept_map':
        item = json.loads(raw.decode('utf-8'))
        if not isinstance(item, dict) or item.get('id') != item_id or type(item.get('version', 1)) is not int or item.get('version', 1) not in (1, 2):
            raise ValueError('删除图身份或格式不受支持')
        return item
    meta, body = load_markdown_text(raw.decode('utf-8'))
    if meta.get('id') != item_id or meta.get('type') != kind:
        raise ValueError('删除条目身份不匹配')
    return {**meta, 'body': body}


@dataclass(frozen=True)
class PreparedDelete:
    root: Path
    relative_path: str
    item_id: str
    kind: str
    before: bytes
    source_identity: dict

    @classmethod
    def from_path(cls, root, path, item_id, kind, revision):
        require_platform()
        if kind not in DELETE_KINDS or not isinstance(revision, str) or not re.fullmatch(r'[a-f0-9]{64}', revision):
            raise ValueError('删除必须使用支持的类型和原始字节版本')
        root, path = Path(root).absolute(), Path(path).absolute()
        relative = path.relative_to(root).as_posix()
        parts = Path(relative).parts
        if kind == 'concept_map':
            allowed = len(parts) == 2 and parts[0] == 'concept-maps' and parts[1] == item_id + '.json' and re.fullmatch(r'CMAP-[0-9]+', item_id)
        elif kind == 'document':
            allowed = len(parts) == 2 and parts[0] == 'documents' and path.suffix == '.md'
        else:
            allowed = len(parts) == 4 and parts[0] == 'projects' and parts[2] == kind + 's' and path.suffix == '.md'
        if not allowed:
            raise ValueError('删除来源不属于该类型的受控目录')
        source = controlled(root, relative)
        with LocalFileHandle(str(source), read=True) as handle:
            raw = read_handle(handle)
            identity = stable_identity(handle.initial)
        if content_revision(raw) != revision:
            raise RevisionConflict('删除对象已变化，请重新完整预览')
        item = source_metadata(raw, item_id, kind)
        if kind in {'issue', 'todo', 'info'} and item.get('project_id') != parts[1]:
            raise ValueError('删除条目归属与来源目录不一致')
        return cls(root, relative, item_id, kind, raw, identity)

    @property
    def path(self):
        return self.root / self.relative_path

    @property
    def trash_kind(self):
        return 'concept-map' if self.kind == 'concept_map' else 'document' if self.kind == 'document' else 'record'

    def trash_path(self, token):
        validate_token(token, self.kind)
        return controlled(self.root, '.trash/' + token, required=False)

    def verify_trash(self, token):
        require_platform()
        destination = self.trash_path(token)
        with LocalFileHandle(str(destination), read=True) as handle:
            raw = read_handle(handle)
            if stable_identity(handle.initial) != self.source_identity or raw != self.before:
                raise RevisionConflict('回收对象不是原删除计划中的同一文件，保留现场')
        source_metadata(raw, self.item_id, self.kind)
        return destination

    def move(self, token, *, permit=None, checkpoint=None):
        """Move the verified original handle once; never copy or replace."""
        require_platform()
        destination = self.trash_path(token)
        if destination.exists():
            raise RevisionConflict('回收名称已被占用，未覆盖任何文件')
        source = controlled(self.root, self.relative_path)
        with LocalFileHandle(str(source), read=True, delete=True) as handle:
            if stable_identity(handle.initial) != self.source_identity or read_handle(handle) != self.before:
                raise RevisionConflict('删除对象身份或内容已变化，请重新预览')
            held = HeldDeleteSource(self, handle, _HELD_SOURCE_SEAL)
            try:
                if permit:
                    permit(held)
                handle.rename_verified(destination)
            finally:
                held._active = False
        if checkpoint:
            checkpoint('trash_moved')
        self.verify_trash(token)
        return destination
