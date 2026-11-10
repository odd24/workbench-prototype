"""Original-byte category plans shared by local and Agent category writes."""

import json
import re
from dataclasses import dataclass
from datetime import datetime

from .category_changes import DEFAULT_NAME, PROJECT_ASSETS, plan_categories
from .category_identity import FENCE_PATH, IDENTITY_PATH, load_category_identities, namespace_key
from .document_attachments import attachment_items, metadata_for_write, safe_local_path
from .markdown_io import dump_markdown, load_markdown_text
from .persistence import atomic_write_bytes
from .project_identity import controlled, load_unique_json, read_bounded
from .write_coordinator import RevisionConflict, content_revision


DOCUMENT = 'document_category'
GRAPH = 'concept_map_category'
MEMBER_LIMIT = 4096
BYTE_LIMIT = 32 * 1048576


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')


def revision(raw):
    return None if raw is None else content_revision(raw)


def read_file(root, relative):
    path = controlled(root, root / relative)
    return read_bounded(path) if path.exists() else None


def catalogue_path(family, project_id):
    namespace_key(family, project_id)
    if family == PROJECT_ASSETS:
        return f'projects/{project_id}/assets/categories.json'
    return 'config/document-categories.json' if family == DOCUMENT else 'config/concept-map-categories.json'


def member_paths(root, family):
    directory, pattern = ('documents', '*.md') if family == DOCUMENT else ('concept-maps', '*.json')
    folder = controlled(root, root / directory)
    paths = []
    for path in folder.glob(pattern):
        paths.append(path.relative_to(root).as_posix())
        if len(paths) > MEMBER_LIMIT:
            raise ValueError('分类成员超过完整核验上限')
    return sorted(paths)


@dataclass(frozen=True)
class FileChange:
    path: str
    before: bytes | None
    after: bytes
    item_id: str | None = None

    def descriptor(self):
        return {'path':self.path, 'before':revision(self.before), 'after':revision(self.after), 'item_id':self.item_id}


@dataclass(frozen=True)
class PreparedCategory:
    change: object
    project_id: str | None
    files: tuple[FileChange, ...]
    watch: dict
    members: tuple[dict, ...]
    names: tuple[str, ...]
    scope: dict
    config_before: object
    config_after: object
    sort_before: dict | None
    sort_after: dict | None

    def evidence(self):
        return {'files':[file.descriptor() for file in self.files], 'watch':self.watch, 'names':list(self.names),
                'scope':self.scope}


def _catalogue(raw, family):
    result = [] if raw is None else load_unique_json(raw)
    if not isinstance(result, list):
        raise ValueError('分类配置不是有序列表')
    if family == PROJECT_ASSETS:
        if any(not isinstance(entry, dict) or set(entry) != {'name', 'tag'} or not isinstance(entry['tag'], str) for entry in result):
            raise ValueError('项目附件分类配置无法完整核验')
    elif any(not isinstance(name, str) for name in result):
        raise ValueError('分类名称格式无效')
    return result


def category_inventory(repository, family, project_id=None):
    root = repository.root
    path = catalogue_path(family, project_id)
    catalogue_raw = read_file(root, path)
    config = _catalogue(catalogue_raw, family)
    watch = {path:revision(catalogue_raw)}
    members, ids = [], set()
    if family == PROJECT_ASSETS:
        folder = root / 'projects' / project_id
        readme_path = f'projects/{project_id}/README.md'
        readme = read_file(root, readme_path)
        if readme is None:
            raise FileNotFoundError(project_id)
        meta, _ = load_markdown_text(readme.decode('utf-8'))
        if meta.get('id') != project_id or meta.get('type') != 'project':
            raise ValueError('项目归属身份无效')
        index_path = f'projects/{project_id}/assets/index.json'
        index_raw = read_file(root, index_path)
        watch.update({readme_path:revision(readme), index_path:revision(index_raw)})
        index = [] if index_raw is None else load_unique_json(index_raw)
        if not isinstance(index, list) or len(index) > MEMBER_LIMIT:
            raise ValueError('独立附件索引无法完整核验')
        for item in index:
            item_id = item.get('id') if isinstance(item, dict) else None
            if not isinstance(item_id, str) or not re.fullmatch(r'ASSET-(?:[0-9]+(?:-[0-9]+)?|[0-9a-f]{32})', item_id) or item_id in ids:
                raise ValueError('独立附件标识无效')
            file = safe_local_path(folder, item.get('path'), (folder / 'assets/library',), required=True, decode=False)
            if file.name != item.get('name'):
                raise ValueError('独立附件名称与文件不符')
            ids.add(item_id)
            members.append({'item':item, 'raw':index_raw, 'path':index_path})
    else:
        total = 0
        for relative in member_paths(root, family):
            raw = read_file(root, relative)
            if raw is None:
                raise RevisionConflict('分类成员在读取期间变化')
            total += len(raw)
            if total > BYTE_LIMIT:
                raise ValueError('分类成员超出完整核验字节上限')
            watch[relative] = revision(raw)
            if family == DOCUMENT:
                meta, body = load_markdown_text(raw.decode('utf-8'))
                if meta.get('type') != 'document':
                    continue  # Legacy loose Markdown is not a workbench document.
                item = {**meta, 'body':body}
            else:
                item = load_unique_json(raw)
                if not isinstance(item, dict) or type(item.get('version', 1)) is not int or item.get('version', 1) not in (1, 2):
                    raise ValueError('概念图版本无法完整核验')
            item_id = item.get('id')
            prefix = 'DOC-' if family == DOCUMENT else 'CMAP-'
            if not isinstance(item_id, str) or not re.fullmatch(prefix + r'[0-9]+', item_id) or item_id in ids or family == GRAPH and relative != f'concept-maps/{item_id}.json':
                raise ValueError('分类成员标识无效或重复')
            ids.add(item_id)
            members.append({'item':item, 'raw':raw, 'path':relative})
    return config, catalogue_raw, members, watch


def _category(family, item):
    name = item.get('category')
    if name is not None and not isinstance(name, str):
        raise ValueError('原分类成员的分类值无效')
    return name or ('' if family == PROJECT_ASSETS else DEFAULT_NAME)


def _document_sort(repository, members, change):
    before = repository.document_sort()
    modes = before['file_modes'].copy()
    orders = {name:items.copy() for name, items in before['file_orders'].items()}
    legacy_order = before.get('legacy_order', [])
    if change.operation in {'rename', 'delete'}:
        source_order = orders.pop(change.name, legacy_order)
        source_mode = modes.pop(change.name, None)
        if change.operation == 'rename':
            modes[change.destination] = source_mode or before['file_mode']
            orders[change.destination] = source_order
        else:
            orders[DEFAULT_NAME] = [*orders.get(DEFAULT_NAME, legacy_order), *source_order]
    category_order = [name for name in before['category_order'] if name in change.before]
    category_order.extend(name for name in change.before if name not in category_order)
    reordered = (change.after if change.operation == 'reorder' else
                 tuple(dict.fromkeys(change.member_category(name) for name in category_order)))
    category_order = [name for name in reordered if name in change.after]
    category_order.extend(name for name in change.after if name not in category_order)
    if DEFAULT_NAME in category_order:
        category_order.remove(DEFAULT_NAME)
        category_order.append(DEFAULT_NAME)
    known = {name:[] for name in change.after}
    for member in sorted(members, key=lambda member:member['item'].get('updated', ''), reverse=True):
        item = member['item']
        known[change.member_category(_category(DOCUMENT, item))].append(item['id'])
    for name, current in known.items():
        listed = orders.get(name, legacy_order)
        orders[name] = list(dict.fromkeys([*(item for item in listed if item in current), *current]))
    after = {'category_mode':'manual' if change.operation == 'reorder' else before['category_mode'],
             'category_order':category_order, 'file_mode':before['file_mode'],
             'file_modes':{name:modes.get(name, before['file_mode']) for name in change.after},
             'file_orders':{name:orders[name] for name in change.after}}
    return before, after


def prepare_category(repository, family, operation, name, *, project_id=None, new_name=None, anchor=None, position=None, epoch, managed_time):
    root = repository.root
    config, raw, members, watch = category_inventory(repository, family, project_id)
    names = list(dict.fromkeys(entry['name'] if family == PROJECT_ASSETS else entry for entry in config))
    for member in members:
        category = _category(family, member['item'])
        if category and category not in names:
            names.append(category)
    sort_path = 'config/document-sort.json'
    sort_raw = sort_record = None
    if family == DOCUMENT:
        sort_raw = read_file(root, sort_path)
        sort_record = load_unique_json(sort_raw) if sort_raw is not None else {}
        if not isinstance(sort_record, dict) or sort_record.keys() - {'mode', 'order', 'category_mode', 'category_order', 'file_mode', 'file_modes', 'file_orders'}:
            raise ValueError('文档排序包含无法完整核验的字段')
        if operation == 'reorder':
            order = repository.document_sort()['category_order']
            names = list(dict.fromkeys([*(category for category in order if category in names), *names]))
    change = plan_categories(family, operation, names, name, new_name=new_name, anchor=anchor, position=position)
    identities = load_category_identities(root)
    scope = identities.scope(namespace_key(family, project_id), change.before)
    _, fence, ledger = identities.plan(change, project_id, epoch)
    tags = {entry['name']:entry['tag'] for entry in config} if family == PROJECT_ASSETS else {}
    if operation == 'rename' and name in tags:
        tags[change.destination] = tags[name]
    config_after = ([{'name':category, 'tag':tags.get(category, '')} for category in change.after]
                    if family == PROJECT_ASSETS else list(change.after))
    files, affected = [], []
    if family == PROJECT_ASSETS:
        index_after = []
    for member in members:
        item, before = member['item'], member['raw']
        current = _category(family, item)
        category = change.member_category(current)
        candidate = item if current == category else {**item, 'category':category}
        if current != category:
            if family == DOCUMENT:
                candidate = {**candidate, 'updated':managed_time}
                if candidate.get('attachments'):
                    candidate['attachments'] = [{**attachment, 'category':category} for attachment in attachment_items(candidate['attachments'])]
                body = candidate['body']
                meta = {key:value for key,value in candidate.items() if key != 'body'}
                after = dump_markdown(metadata_for_write(meta), body).encode('utf-8')
            elif family == GRAPH:
                candidate = {**candidate, 'updated':managed_time}
                after = encoded(candidate)
            if family != PROJECT_ASSETS:
                files.append(FileChange(member['path'], before, after, item['id']))
        if current == name or current != category:
            affected.append({'id':item['id'], 'revision':revision(before), 'before':item, 'after':candidate})
        if family == PROJECT_ASSETS:
            index_after.append(candidate)
    if family == PROJECT_ASSETS and any(member['before'] != member['after'] for member in affected):
        relative = f'projects/{project_id}/assets/index.json'
        files.append(FileChange(relative, members[0]['raw'], encoded(index_after)))
    files.append(FileChange(catalogue_path(family, project_id), raw, encoded(config_after)))
    sorting_before = sorting_after = None
    if family == DOCUMENT:
        _, sorting_after = _document_sort(repository, members, change)
        sorting_before = sort_record
        if read_file(root, sort_path) != sort_raw:
            raise RevisionConflict('文档排序在准备期间发生变化')
        files.append(FileChange(sort_path, sort_raw, encoded(sorting_after)))
    if identities.fence_before != fence:
        files.append(FileChange(FENCE_PATH, identities.fence_before, fence))
    files.append(FileChange(IDENTITY_PATH, identities.ledger_before, ledger))
    if any(len(file.after) > 1048576 for file in files):
        raise ValueError('分类候选文件超过完整核验上限')
    return PreparedCategory(change, project_id, tuple(files), watch, tuple(affected), tuple(names), scope,
                            config, config_after, sorting_before, sorting_after)


def verify_members(root, family, watch, project_id=None):
    if family == PROJECT_ASSETS:
        from types import SimpleNamespace
        category_inventory(SimpleNamespace(root=root), family, project_id)
        return
    expected = {path for path in watch if path.startswith(('documents/', 'concept-maps/'))}
    if set(member_paths(root, family)) != expected:
        raise RevisionConflict('分类成员集合已经变化')


def verify_category_files(root, family, files, watch, *, allow_applied, project_id=None):
    verify_members(root, family, watch, project_id)
    changed = {file.path:file for file in files}
    for relative in set(watch) | changed.keys():
        current = revision(read_file(root, relative))
        if relative in changed:
            allowed = {revision(changed[relative].before)}
            if allow_applied:
                allowed.add(revision(changed[relative].after))
        else:
            allowed = {watch[relative]}
        if current not in allowed:
            raise RevisionConflict('分类配置或成员在准备后变化')


def apply_category_files(root, family, files, watch, *, project_id=None, history_version=None, allow_applied=False, checkpoint=lambda *_:None):
    from .history import concept_map_history_path, history_path, save_concept_map_snapshot, save_snapshot_bytes
    verify_category_files(root, family, files, watch, allow_applied=allow_applied, project_id=project_id)
    changed = {file.path:file for file in files}
    version = history_version or datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for index, file in enumerate(files):
        current = read_file(root, file.path)
        if file.before == file.after:
            continue
        if current != file.before and (not allow_applied or current != file.after):
            raise RevisionConflict('分类写入期间检测到第三方修改')
        if file.item_id:
            history = root / 'history'
            target = (history_path if family == DOCUMENT else concept_map_history_path)(history, file.item_id, version)
            controlled(root, target)
            if current == file.after:
                if read_file(root, target.relative_to(root).as_posix()) != file.before:
                    raise RevisionConflict('已发布分类成员缺少原历史证据')
            else:
                save = save_snapshot_bytes if family == DOCUMENT else save_concept_map_snapshot
                save(history, file.item_id, file.before, version)
                checkpoint('category_history', index)
        if current == file.before:
            if read_file(root, file.path) != file.before:
                raise RevisionConflict('分类成员在正式发布前变化')
            atomic_write_bytes(controlled(root, root / file.path), file.after)
            checkpoint('category_write', index)
    verify_members(root, family, watch, project_id)
    for relative in set(watch) | changed.keys():
        expected = revision(changed[relative].after) if relative in changed else watch[relative]
        if revision(read_file(root, relative)) != expected:
            raise RevisionConflict('分类最终文件证据不一致')
