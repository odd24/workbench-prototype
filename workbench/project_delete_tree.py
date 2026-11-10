"""Bounded original-tree evidence and verified whole-directory trash moves."""

import ctypes
import hashlib
import os
import re
import stat
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from .agent_file_handles import lexical_path
from .agent_security import AgentError
from .deletion_inventory import fingerprint
from .document_attachments import attachment_items, safe_local_path
from .markdown_io import load_markdown_text
from .project_directory import _ProjectDirectoryHandle, physical_identity
from .project_identity import controlled, load_unique_json, valid_new_id
from .projects import PROJECT_DIRECTORIES
from .write_coordinator import RevisionConflict


TREE_MEMBERS = 4096
TREE_BYTES = 64 * 1048576
TEXT_BYTES = 1048576
RETAINED_TEXT_BYTES = 2097152
DIRECTORIES = frozenset((*PROJECT_DIRECTORIES, 'assets', 'assets/library'))
CONTROL_FILES = frozenset(('README.md', 'assets/index.json', 'assets/categories.json'))
RECORDS = {'issues':'issue', 'todos':'todo', 'infos':'info'}
ASSET_DIRS = {'assets/images', 'assets/files', 'assets/library'}
SPECIAL = 0x400 | 0x40 | 0x1000 | 0x40000 | 0x400000


class _StreamInfo(ctypes.Structure):
    _fields_ = [('size', ctypes.c_longlong), ('name', wintypes.WCHAR * 296)]


def _stream_checker(library):
    # NTFS named streams would be carried by rename but are not members of
    # scandir or the ordinary file byte stream. Refuse rather than omit them.
    first, following, close = library.FindFirstStreamW, library.FindNextStreamW, library.FindClose
    first.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(_StreamInfo), wintypes.DWORD]
    first.restype = wintypes.HANDLE
    following.argtypes = [wintypes.HANDLE, ctypes.POINTER(_StreamInfo)]
    following.restype = wintypes.BOOL
    close.argtypes, close.restype = [wintypes.HANDLE], wintypes.BOOL

    def check(path, directory):
        info = _StreamInfo()
        search = first(str(path), 0, ctypes.byref(info), 0)
        if search == ctypes.c_void_p(-1).value:
            if directory and ctypes.get_last_error() == 38:
                return
            raise ValueError('无法完整核验目录数据流')
        try:
            if directory or info.name != '::$DATA' or following(search, ctypes.byref(info)) or ctypes.get_last_error() != 38:
                raise ValueError('项目包含不受支持的数据流')
        finally:
            close(search)
    return check


def _identity(info):
    if not info.st_ino:
        raise ValueError('不能确认树成员的物理身份')
    return {'device':info.st_dev, 'inode':info.st_ino,
            'created':getattr(info, 'st_birthtime_ns', info.st_ctime_ns)}


def _stat(path, directory):
    info = path.lstat()
    if getattr(info, 'st_file_attributes', 0) & SPECIAL or (not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise ValueError('项目包含重解析、硬链接或特殊对象')
    return info


def _file_version(info):
    return _identity(info), info.st_size, info.st_mtime_ns, info.st_nlink


@dataclass(frozen=True)
class ProjectTree:
    identity: dict
    members: list
    raw_text: dict

    @property
    def portable_members(self):
        return [{key:value for key,value in entry.items() if key != 'identity'} for entry in self.members]

    @property
    def portable_digest(self):
        return fingerprint(self.portable_members)

    @property
    def physical_digest(self):
        return fingerprint([self.identity, self.members])


def _scan(folder, handle, *, keep_text=True):
    initial = physical_identity(handle)
    check_streams = _stream_checker(handle.library)
    check_streams(folder, True)
    members, raw_text, seen = [], {}, set()
    total = retained_text = 0
    deadline = time.monotonic() + 25
    base_dev = _stat(folder, True).st_dev

    def visit(directory, prefix=''):
        nonlocal total, retained_text
        old_dir = _stat(directory, True)
        with os.scandir(directory) as entries:
            for entry in entries:
                if len(members) >= TREE_MEMBERS or time.monotonic() > deadline:
                    raise ValueError('项目树超出完整盘点上限')
                relative = f'{prefix}/{entry.name}' if prefix else entry.name
                path = Path(entry.path)
                lexical_path(str(path))
                key = relative.casefold()
                if key in seen:
                    raise ValueError('项目树包含大小写别名')
                seen.add(key)
                is_dir = entry.is_dir(follow_symlinks=False)
                text_file = relative in CONTROL_FILES or prefix in RECORDS and path.suffix == '.md'
                if is_dir and relative not in DIRECTORIES or not is_dir and not text_file and prefix not in ASSET_DIRS:
                    raise ValueError('项目包含未授权或未知树成员')
                old = _stat(path, is_dir)
                if old.st_dev != base_dev:
                    raise ValueError('项目树跨越受控卷')
                check_streams(path, is_dir)
                member = {'path':relative,'type':'directory' if is_dir else 'file','identity':_identity(old)}
                members.append(member)
                if is_dir:
                    visit(path, relative)
                else:
                    if total + old.st_size > TREE_BYTES or text_file and old.st_size > TEXT_BYTES:
                        raise ValueError('项目文件或总字节超出盘点上限')
                    sha, actual = hashlib.sha256(), 0
                    content = bytearray() if text_file and keep_text else None
                    with path.open('rb') as stream:
                        opened = os.fstat(stream.fileno())
                        if _file_version(opened) != _file_version(old):
                            raise RevisionConflict('项目文件在打开期间变化')
                        for chunk in iter(lambda:stream.read(65536), b''):
                            actual += len(chunk)
                            total += len(chunk)
                            if total > TREE_BYTES or text_file and actual > TEXT_BYTES or time.monotonic() > deadline:
                                raise ValueError('项目实际读取超出盘点上限')
                            sha.update(chunk)
                            if content is not None:
                                retained_text += len(chunk)
                                if retained_text > RETAINED_TEXT_BYTES:
                                    raise ValueError('项目完整文本超过预览预算')
                                content.extend(chunk)
                        if _file_version(os.fstat(stream.fileno())) != _file_version(opened):
                            raise RevisionConflict('项目文件在读取期间变化')
                    member.update(size=actual, sha256=sha.hexdigest())
                    if actual != old.st_size or _file_version(_stat(path, False)) != _file_version(opened):
                        raise RevisionConflict('项目文件在读取期间变化')
                    if content is not None:
                        raw_text[relative] = bytes(content)
                check_streams(path, is_dir)
        final = _stat(directory, True)
        if _identity(old_dir) != _identity(final) or old_dir.st_mtime_ns != final.st_mtime_ns:
            raise RevisionConflict('项目目录成员在读取期间变化')

    visit(folder)
    check_streams(folder, True)
    if initial != physical_identity(handle):
        raise RevisionConflict('项目根身份变化')
    return ProjectTree(initial, sorted(members,key=lambda item:item['path']), raw_text)


def read_tree(root, folder, *, keep_text=True):
    path = controlled(root, folder)
    with _ProjectDirectoryHandle(str(path)) as handle:
        return _scan(path, handle, keep_text=keep_text)


def validate_tree_destination(folder, members):
    for path in (folder, *(folder / entry['path'] for entry in members)):
        value = lexical_path(str(path))
        if len(value.encode('utf-16-le')) > 480:
            raise ValueError('项目目标路径超出原生移动上限')


def move_tree(root, source, target, expected, permit, *, before_rename=lambda:None, moved=lambda:None):
    """One no-replacement rename; a post-move failure never moves it back."""
    source, target = controlled(root, source), controlled(root, target)
    with _ProjectDirectoryHandle(str(source), read=True, delete=True) as handle:
        observed = _scan(source, handle)
        if observed.physical_digest != expected:
            raise RevisionConflict('项目完整树已变化')
        validate_tree_destination(target, observed.members)
        permit(observed)
        if _scan(source, handle, keep_text=False).physical_digest != expected:
            raise RevisionConflict('项目最后复核时已变化')
        before_rename()
        try:
            handle.rename_verified(target)
        except AgentError as error:
            if error.code == 'attachment_publish_conflict':
                raise RevisionConflict('项目回收目标已占用或原目录被外部占用') from None
            raise
        moved()
    if read_tree(root,target,keep_text=False).physical_digest != expected:
        raise RevisionConflict('移动后树证据不匹配，保留现场核查')


def classify_tree(root, project_id, tree):
    """Describe all approved owners, leaving no unclassified binary in the tree."""
    valid_new_id(project_id)
    folder = root / 'projects' / project_id
    members = {entry['path']:entry for entry in tree.members}
    project = project_metadata(tree.raw_text['README.md'], project_id)
    records, assets, owned, child_ids = [], [], set(), set()

    def check_attachment(owner, attachment, expected_dirs, *, independent=False):
        path = safe_local_path(owner.parent, attachment['path'], (folder/'assets', root/'assets'), decode=False)
        if not path.is_file() or path.name != attachment['name']:
            raise ValueError('项目附件事实源不一致')
        if path.is_relative_to(folder):
            relative = path.relative_to(folder).as_posix()
            entry = members.get(relative)
            if not entry or path.parent.relative_to(folder).as_posix() not in expected_dirs or entry['type'] != 'file' or type(attachment.get('size')) is not int or entry['size'] != attachment['size']:
                raise ValueError('项目内附件路径、大小或归属无效')
            if independent and relative in owned:
                raise ValueError('独立附件索引重复占用文件')
            owned.add(relative)
            return {**attachment,'relative_path':relative,'sha256':entry['sha256'],'action':'move'}
        if independent:
            raise ValueError('独立附件必须位于原项目目录')
        return {**attachment,'action':'retain'}

    for name, raw in tree.raw_text.items():
        parent = Path(name).parent.as_posix()
        if parent not in RECORDS:
            continue
        item, body = load_markdown_text(raw.decode('utf-8'))
        kind = RECORDS[parent]
        prefix = {'issue':'ISSUE','todo':'(?:TODO|ISSUE)','info':'INFO'}[kind]
        key = item.get('id')
        if item.get('type') != kind or item.get('project_id') != project_id or not isinstance(key,str) or not re.fullmatch(prefix+'-[0-9]+',key) or key in child_ids or not isinstance(item.get('title'),str):
            raise ValueError('子记录身份、类型或归属无效')
        child_ids.add(key)
        attachments = [check_attachment(folder/name, a, {'assets/images','assets/files'}) for a in attachment_items(item.get('attachments',[]))]
        records.append({'relative_path':name,'item':{**item,'body':body},'raw_source':raw.decode('utf-8'),
                        'revision':members[name]['sha256'],'attachments':attachments})
    ids = set()
    if 'assets/index.json' in tree.raw_text:
        entries = load_unique_json(tree.raw_text['assets/index.json'])
        for item in attachment_items(entries):
            key = item.get('id')
            if not isinstance(key,str) or not re.fullmatch(r'ASSET-(?:[0-9a-f]{32}|[0-9]+(?:-[0-9]+)?)',key) or key in ids:
                raise ValueError('独立附件身份无效')
            ids.add(key)
            assets.append(check_attachment(folder/'README.md',item,{'assets/library'},independent=True))
    if 'assets/categories.json' in tree.raw_text:
        entries = load_unique_json(tree.raw_text['assets/categories.json'])
        if not isinstance(entries,list) or any(not isinstance(item,dict) or not isinstance(item.get('name'),str) for item in entries):
            raise ValueError('独立附件分类证据无效')
    binaries = {name for name, item in members.items() if item['type'] == 'file' and name not in tree.raw_text}
    if binaries != owned:
        raise ValueError('项目存在未归属附件或其它未授权文件')
    return project, records, assets, binaries


def project_metadata(raw, project_id):
    meta, body = load_markdown_text(raw.decode('utf-8'))
    if meta.get('id') != project_id or meta.get('type') != 'project' or not isinstance(meta.get('name'), str):
        raise ValueError('项目 README 身份无效')
    return {**meta, 'title':meta['name'], 'body':body}
