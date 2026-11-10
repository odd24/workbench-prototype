"""Bounded, strict inventory of current business sources for deletion impact.

History and trash are retained evidence, not active backlink sources. Callers
must keep nonmatching inventory entries private and authorize every match.
"""

import hashlib
import json
import re
from pathlib import Path

from .deletion_prepared import controlled, RAW_LIMIT
from .markdown_io import load_markdown_text
from .references import references
from .write_coordinator import content_revision


INVENTORY_BYTES = 32 * 1048576
INVENTORY_FILES = 4096


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def active_inventory(root, target_id=None, *, held_source=None, select_impact=None):
    if held_source is not None:
        from .deletion_prepared import validate_held_source
        validate_held_source(held_source)
    root = Path(root).resolve()
    paths = []
    for directory in ('documents', 'ideas', 'concept-maps', 'projects'):
        if not controlled(root, directory, required=False).is_dir():
            raise ValueError('活动来源目录不存在')
    paths.extend((path, 'document', None) for path in (root / 'documents').glob('*.md'))
    paths.extend((path, 'idea', None) for path in (root / 'ideas').glob('*.md'))
    paths.extend((path, 'concept_map', None) for path in (root / 'concept-maps').glob('*.json'))
    for project in (root / 'projects').iterdir():
        controlled(root, project.relative_to(root).as_posix(), required=False)
        if not project.is_dir():
            continue
        readme = project / 'README.md'
        if not readme.exists():
            if any(project.glob('*/*.md')):
                raise ValueError('正式记录缺少可信项目归属')
            continue
        paths.append((readme, 'project', project.name))
        for kind in ('issue', 'todo', 'info', 'idea'):
            paths.extend((path, kind, project.name) for path in (project / (kind + 's')).glob('*.md'))
    if len(paths) > INVENTORY_FILES:
        raise ValueError('活动集合超过完整扫描上限，无法提供可信删除预览')
    total, retained_bytes, entries, identities = 0, 0, [], set()
    for path, kind, project_id in sorted(paths, key=lambda item:item[0].as_posix()):
        relative = path.relative_to(root).as_posix()
        path = controlled(root, relative)
        if held_source is not None and relative == held_source.relative_path:
            # The caller verified these bytes on the exact DELETE handle and
            # keeps it open, excluding writes/replacement throughout this pass.
            raw = held_source.before
        else:
            with path.open('rb') as stream:
                raw = stream.read(RAW_LIMIT + 1)
        if len(raw) > RAW_LIMIT:
            raise ValueError('活动来源超过1MiB，无法建立完整删除影响')
        total += len(raw)
        if total > INVENTORY_BYTES:
            raise ValueError('活动集合超过完整扫描字节上限')
        if kind == 'concept_map':
            def reject_constant(value):
                raise ValueError('活动图包含非有限数')
            def unique_fields(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('活动图包含重复字段，不能完整确定引用')
                    result[key] = value
                return result
            item = json.loads(raw.decode('utf-8'), parse_constant=reject_constant, object_pairs_hook=unique_fields)
            if not isinstance(item, dict) or item.get('id') != path.stem or not re.fullmatch(r'CMAP-[0-9]+', path.stem) or type(item.get('version', 1)) is not int or item.get('version', 1) not in (1, 2):
                raise ValueError('活动图身份或版本不受支持')
            item = {**item, 'type':'concept_map'}
        else:
            meta, body = load_markdown_text(raw.decode('utf-8'))
            item = {**meta, 'body':body}
            if meta.get('type') != kind or not isinstance(meta.get('id'), str) or not meta['id']:
                raise ValueError('活动Markdown身份或类型无效')
            if kind == 'project' and meta['id'] != project_id or kind in {'issue', 'todo', 'info', 'idea'} and project_id is not None and meta.get('project_id') != project_id:
                raise ValueError('活动条目归属不一致')
        identity = item['id']
        if identity in identities:
            raise ValueError('存在重复正式身份，不能确定删除影响')
        identities.add(identity)
        links = references(item, strict=True, project_links=select_impact is not None)
        if select_impact is None:
            matches = [ref for ref in links if ref['id'] == target_id] if target_id is not None else []
            selected = target_id is not None and (identity == target_id or matches)
        else:
            matches = select_impact(relative, kind, item, links)
            selected = matches is not None
        entry = {'id':identity, 'kind':kind, 'relative_path':relative, 'revision':content_revision(raw),
                 'item':{key:item.get(key) for key in ('id', 'type', 'title', 'project_id', 'category')},
                 'references':matches or []}
        if selected:
            retained_bytes += len(raw)
            if retained_bytes > 2097152:
                raise ValueError('完整删除影响超过预览预算')
            entry.update(raw=raw, item=item)
        entries.append(entry)
    bindings = [{key:item[key] for key in ('id', 'kind', 'relative_path', 'revision')} for item in entries]
    return entries, fingerprint(bindings)
