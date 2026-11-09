"""Domain attachment candidates: pure preview preparation, bounded metadata writes."""

import json
import copy
import re
import os
from dataclasses import dataclass
from pathlib import Path

from .markdown_io import load_markdown_text, now_iso, dump_markdown
from .security import validate_portable_filename
from .write_coordinator import RevisionConflict, content_revision


@dataclass
class PreparedAttachment:
    binary_path: Path
    metadata_path: Path
    before: bytes | None
    after: bytes
    view: dict
    record_write: object = None


COMMIT_TIME = '提交确认时由服务端生成'


def raw_markdown_body(content):
    text = content.decode('utf-8')
    match = re.match(r'^---\r?\n.*?\r?\n---\r?\n', text, re.S)
    if not match:
        raise ValueError('记录缺少有效元数据边界')
    return text[match.end():]


def serialize_record_metadata(meta, body):
    from .document_attachments import metadata_for_write
    meta = metadata_for_write(meta)
    header = dump_markdown(meta, '').split('\n---\n', 1)[0] + '\n---\n'
    return (header + body).encode('utf-8')


def attachment_target(domain, kind, owner_id):
    if kind == 'project':
        project = domain.project(owner_id)
        if not project:
            raise FileNotFoundError(owner_id)
        path = domain.projects_dir / owner_id / 'assets' / 'index.json'
        before = path.read_bytes() if path.exists() else None
        if before is not None and len(before) > 1048576:
            raise ValueError('附件索引过大，无法完整预览')
        items = json.loads(before) if before is not None else []
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ValueError('附件索引损坏，保留现场')
        return project, path, before, items
    if kind == 'document' and (not isinstance(owner_id, str) or not re.fullmatch(r'DOC-\d+', owner_id)):
        raise FileNotFoundError(owner_id)
    record, path = domain.get_document(owner_id) if kind == 'document' else domain.get_record(owner_id)
    if not record or record['type'] != kind or kind not in {'issue', 'todo', 'info', 'document'}:
        raise FileNotFoundError(owner_id)
    before = path.read_bytes()
    if len(before) > 1048576:
        raise ValueError('目标内容过大，无法完整预览')
    items = list(record.get('attachments') or [])
    for item in items:
        parsed = json.loads(item) if isinstance(item, str) else item
        if not isinstance(parsed, dict):
            raise ValueError('已有记录附件元数据无法完整预览')
    return record, path, before, items


def categories(domain, project_id, items):
    path = domain.projects_dir / project_id / 'assets' / 'categories.json'
    raw = path.read_bytes() if path.exists() else None
    if raw is not None and len(raw) > 1048576:
        raise ValueError('附件分类过大')
    configured = json.loads(raw) if raw is not None else []
    if not isinstance(configured, list):
        raise ValueError('附件分类损坏')
    names = {item.get('name') for item in configured if isinstance(item, dict)}
    for item in items:
        if isinstance(item, str):
            item = json.loads(item)
        if isinstance(item, dict):
            names.add(item.get('category'))
    names = sorted(name for name in names if isinstance(name, str) and name)
    revision = content_revision(json.dumps({'configured_digest':content_revision(raw or b''), 'names':names}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))
    return names, revision


def document_categories(domain, owner):
    path = domain.root / 'config' / 'document-categories.json'
    raw = path.read_bytes() if path.exists() else b''
    value = {'category':owner.get('category', '未分类'), 'configured_digest':content_revision(raw)}
    return [value['category']], content_revision(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8'))


def prepare_attachment_create(domain, kind, owner_id, name, size, sha256, category, insert_link,
                              base_revision, asset_id, prepare_record_update, reserved=(), managed_time=None):
    managed_time = managed_time or now_iso()
    name = validate_portable_filename(name, label='附件文件名')
    owner, metadata_path, before, items = attachment_target(domain, kind, owner_id)
    if content_revision(before or b'') != base_revision:
        raise RevisionConflict('附件目标已变化，请重新预览')
    project_id = owner['id'] if kind == 'project' else None if kind == 'document' else owner.get('project_id')
    project_root = domain.projects_dir / project_id if project_id else domain.root
    if kind == 'document':
        category_names, category_revision = document_categories(domain, owner)
        if not isinstance(category, str) or category != owner.get('category', '未分类'):
            raise ValueError('文档附件分类必须等于文档原分类')
    else:
        project_items = attachment_target(domain, 'project', project_id)[3]
        category_names, category_revision = categories(domain, project_id, project_items + ([] if kind == 'project' else items))
        if not isinstance(category, str) or category != domain._asset_category(category, allow_empty=True) or category and category not in category_names:
            raise ValueError('只能使用已有附件分类或空分类')
    if kind == 'project' and insert_link:
        raise ValueError('项目独立附件不支持插入记录正文')
    image = (domain.attachment_metadata(Path(name), '', size)['mime']).startswith('image/')
    root = project_root / 'assets' / ('library' if kind == 'project' else 'images' if image else 'files')
    candidate, counter = root / name, 2
    while candidate.exists() or candidate.relative_to(domain.root).as_posix() in reserved:
        candidate = root / f'{Path(name).stem}-{counter}{Path(name).suffix}'
        counter += 1
    if len(str(candidate)) > 240 or candidate.resolve() != candidate.absolute():
        raise ValueError('附件目标路径包含链接')
    relative = candidate.relative_to(project_root).as_posix() if kind == 'project' else Path(os.path.relpath(candidate, metadata_path.parent)).as_posix()
    attachment = domain.attachment_metadata(candidate, relative, size, category)
    attachment.update(id=asset_id, sha256=sha256)
    record_write = None
    if kind == 'project':
        attachment['created'] = managed_time
        after_items = items + [attachment]
        after = (json.dumps(after_items, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        metadata_before, metadata_after, body = items, after_items, ''
    else:
        changes = {'attachments': items + [json.dumps(attachment, ensure_ascii=False, separators=(',', ':'))]}
        raw_body = raw_markdown_body(before)
        body = domain.append_attachment_link(raw_body, attachment) if insert_link else raw_body
        if insert_link:
            changes['body'] = body
        if kind == 'document':
            from .write_coordinator import PreparedMarkdownWrite
            metadata, _ = load_markdown_text(before.decode('utf-8'))
            record_write = PreparedMarkdownWrite(metadata_path, owner_id, serialize_record_metadata({**metadata, 'attachments':changes['attachments']}, body).decode('utf-8'), before)
        else:
            record_write = prepare_record_update(owner_id, {**changes, 'expected_revision': base_revision})
        after = record_write.after
        metadata_before, before_body = load_markdown_text(before.decode('utf-8'))
        metadata_after, _body = load_markdown_text(after.decode('utf-8'))
        metadata_after['updated'] = managed_time
        after = serialize_record_metadata(metadata_after, body)
        record_write.text = after.decode('utf-8')
    view = {'owner_kind': kind, 'owner_id': owner_id, 'project_id': project_id,
            'title': owner.get('title', owner.get('name')), 'attachment': attachment,
            'binary_relative': candidate.relative_to(domain.root).as_posix(),
            'metadata_relative': metadata_path.relative_to(domain.root).as_posix(),
            'metadata_before': metadata_before, 'metadata_after': metadata_after,
            'body': body, 'insert_link': insert_link, 'category_revision': category_revision,
            'unparsed_binary': True}
    return PreparedAttachment(candidate, metadata_path, before, after, view, record_write)


def serialize_attachment_candidate(view, commit_time=None):
    metadata = copy.deepcopy(view['metadata_after'])
    if view['owner_kind'] == 'project':
        if commit_time is not None:
            metadata[-1]['created'] = commit_time
        return (json.dumps(metadata, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if commit_time is not None:
        metadata['updated'] = commit_time
    return serialize_record_metadata(metadata, view['body'])
