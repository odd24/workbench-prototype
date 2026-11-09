"""Document attachment metadata and controlled resource resolution.

Markdown is the only attachment catalogue. No secondary business index exists.
"""

import json
import mimetypes
import os
import re
import stat
from pathlib import Path
from urllib.parse import unquote

from .security import validate_portable_filename


def metadata_for_write(meta):
    """Keep document attachment entries as ordered JSON strings on disk."""
    if meta.get('type') != 'document' or not isinstance(meta.get('attachments'), list):
        return meta
    return {**meta, 'attachments':[json.dumps(item, ensure_ascii=False, separators=(',', ':')) if isinstance(item, dict) else item for item in meta['attachments']]}


def attachment_items(value):
    if not isinstance(value, list):
        raise ValueError('附件元数据必须是有序列表')
    result = []
    for raw in value:
        item = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(item, dict) or not isinstance(item.get('path'), str):
            raise ValueError('附件元数据损坏，保留文件')
        validate_portable_filename(item.get('name', ''), label='附件文件名')
        result.append(item)
    return result


def safe_local_path(base, source, roots, *, required=False, decode=True):
    """Raw metadata stays literal; Markdown URLs decode exactly once."""
    if not isinstance(source, str) or not source or '\x00' in source or '\\' in source:
        raise ValueError('附件相对路径无效')
    decoded = unquote(source, errors='strict') if decode else source
    roots = tuple(Path(root).absolute() for root in roots)
    for value in (decoded,):
        if value.startswith('/') or ':' in value or '\x00' in value or '\\' in value:
            raise ValueError('附件路径必须是受控相对路径')
        candidate = Path(os.path.abspath(base / value))
        if not any(candidate.is_relative_to(root) for root in roots):
            raise ValueError('附件路径超出受控目录')
        probe = candidate
        while True:
            try:
                info = probe.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400 or stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                    raise ValueError('附件路径包含重解析对象')
            except FileNotFoundError:
                pass
            if probe == probe.parent:
                break
            probe = probe.parent
        if candidate.resolve() != candidate.absolute():
            raise ValueError('附件路径包含别名')
        if candidate.is_file():
            return candidate
    if required:
        raise FileNotFoundError('引用的本地附件缺失')
    return candidate


def document_attachment_path(repository, document_id, name):
    if not re.fullmatch(r'DOC-\d+', document_id):
        return None
    document, path = repository.get_document(document_id)
    if not document or document.get('type') != 'document' or document.get('id') != document_id:
        return None
    try:
        for item in attachment_items(document.get('attachments', [])):
            if item['name'] == name:
                result = safe_local_path(path.parent, item['path'], (repository.global_assets_dir / 'images', repository.global_assets_dir / 'files'), decode=False)
                return result if result.is_file() else None
    except (OSError, ValueError, TypeError):
        return None
    return None


# The app emits URL-encoded parentheses/space; legacy angle targets are supported.
MARKDOWN_LINK = re.compile(r'!?\[(?:\\.|[^\]\\])*\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"\n]*")?\)')
INTERNAL_ATTACHMENT = re.compile(r'\[\[([A-Za-z]+-\d+)#attachment:([^\]]+)\]\]')


def local_links(body):
    for match in MARKDOWN_LINK.finditer(body):
        source = match.group(1)
        if source.startswith('<'):
            source = source[1:-1]
        if re.match(r'^(?:https?://|mailto:|#|data:)', source, re.I):
            continue
        # A literal percent/hash filename is resolved before decoding. Fragment
        # removal is deliberately limited to unencoded URL punctuation.
        yield match, source.split('#', 1)[0].split('?', 1)[0]


def reference_attachment(repository, item_id, name):
    if item_id.startswith('DOC-'):
        return document_attachment_path(repository, item_id, name)
    return repository.attachment_path(item_id, name)


def reference_summary(document, documents_dir):
    try:
        if document.get('type') != 'document' or not re.fullmatch(r'DOC-\d+', document.get('id', '')):
            return []
        path = safe_local_path(documents_dir, Path(document['file_path']).name, (documents_dir,), required=True, decode=False)
        roots = (documents_dir.parent / 'assets' / 'images', documents_dir.parent / 'assets' / 'files')
        return [{'name':item['name'], 'size':int(item.get('size', 0) or 0),
                 'mime':mimetypes.guess_type(item['name'])[0] or 'application/octet-stream'}
                for item in attachment_items(document.get('attachments', [])) if safe_local_path(path.parent, item['path'], roots, decode=False).is_file()]
    except (ValueError, TypeError, OSError, KeyError):
        return []
