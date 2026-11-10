"""Bounded, original-byte workflow inventories and pure migration plans."""

import json
import re
from collections import defaultdict
from dataclasses import dataclass

from .attachment_prepared import raw_markdown_body
from .markdown_io import dump_markdown, load_markdown_text
from .persistence import atomic_write_bytes
from .project_identity import controlled, identity_key, load_unique_json, read_bounded
from .records import TYPE_DIRS
from .workflow_changes import (
    STANDARD, STATE_TYPES, change_catalogue, effective_template, map_states, project_order_after,
    record_after, target_state, validate_catalogue, validate_command, validate_statuses,
)
from .write_coordinator import RevisionConflict, content_revision


CATALOGUE = 'config/workflow-templates.json'
FALLBACK = 'config/status-templates.json'
FILE_LIMIT = 4096
BYTE_LIMIT = 32 * 1048576


def digest(raw):
    return None if raw is None else content_revision(raw)


def read_raw(root, relative):
    path = controlled(root, root / relative)
    return read_bounded(path) if path.exists() else None


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')


def active_paths(root):
    projects = controlled(root, root / 'projects')
    ideas = controlled(root, root / 'ideas')
    if not projects.is_dir() or not ideas.is_dir():
        raise ValueError('缺少活动项目或历史想法目录')
    paths = [(path, 'idea', None) for path in ideas.glob('*.md')]
    for folder in projects.iterdir():
        folder = controlled(root, folder)
        if not folder.is_dir():
            continue
        identity_key(folder.name)
        children = []
        for kind, subdir in TYPE_DIRS.items():
            directory = controlled(root, folder / subdir)
            children.extend((path, kind, folder.name) for path in directory.glob('*.md'))
        readme = controlled(root, folder / 'README.md')
        if readme.exists():
            paths.append((readme, 'project', folder.name))
        elif children:
            raise ValueError('活动记录缺少可核验项目')
        paths.extend(children)
        if len(paths) > FILE_LIMIT:
            raise ValueError('工作流活动集合超过完整扫描上限')
    if len(paths) > FILE_LIMIT:
        raise ValueError('工作流活动集合超过完整扫描上限')
    return [(path.relative_to(root).as_posix(), kind, project) for path, kind, project in sorted(paths)]


@dataclass(frozen=True)
class WorkflowFile:
    path: str
    before: bytes | None
    after: bytes
    record_id: str | None = None

    def evidence(self):
        return {'path':self.path, 'before':digest(self.before), 'after':digest(self.after), 'record_id':self.record_id}


@dataclass(frozen=True)
class WorkflowInventory:
    catalogue: list
    fallback: dict
    raw: dict
    projects: dict
    records: dict
    watch: dict


@dataclass(frozen=True)
class PreparedWorkflow:
    operation: str
    selection: dict
    catalogue_before: list
    catalogue_after: list
    fallback_before: dict
    fallback_after: dict
    watch: dict
    files: tuple
    projects: tuple
    records: tuple
    unmapped: tuple
    ordering_conflicts: tuple
    substantive: bool

    def evidence(self):
        return {'watch':self.watch, 'files':[file.evidence() for file in self.files]}


def inventory(root):
    raw = {relative:read_raw(root, relative) for relative in (CATALOGUE, FALLBACK)}
    if None in raw.values():
        raise ValueError('缺少原工作流或全局状态配置')
    catalogue, fallback = [load_unique_json(raw[path]) for path in (CATALOGUE, FALLBACK)]
    validate_catalogue(catalogue)
    validate_statuses(fallback)
    projects, records, ids = {}, defaultdict(list), set()
    total = sum(map(len, raw.values()))
    for relative, kind, project in active_paths(root):
        data = read_raw(root, relative)
        if data is None:
            raise RevisionConflict('活动工作流成员在读取时变化')
        raw[relative] = data
        total += len(data)
        if total > BYTE_LIMIT:
            raise ValueError('工作流活动集合超过完整字节上限')
        meta, _ = load_markdown_text(data.decode('utf-8'))
        if kind == 'idea' and project is None and not meta:
            continue  # Unmanaged legacy Markdown has no workbench status.
        key = meta.get('id')
        if kind == 'project':
            if key != project or meta.get('type') != 'project' or (
                    'workflow_template' in meta and not isinstance(meta['workflow_template'], str)):
                raise ValueError('项目身份或模板绑定无法核验')
            projects[project] = (relative, meta)
        elif (meta.get('type') != kind or not isinstance(key, str)
              or not re.fullmatch((r'(?:ISSUE|TODO)' if kind in {'issue','todo'} else kind.upper()) + r'-[0-9]+', key)
              or key in ids or (meta.get('project_id') or None) != project):
            raise ValueError('活动记录身份、路径或项目归属无法核验')
        elif kind in STATE_TYPES:
            if not isinstance(meta.get('status'), str) or not meta['status']:
                raise ValueError('活动记录状态无法核验')
            records[project].append((relative, meta))
            ids.add(key)
        else:
            ids.add(key)
    return WorkflowInventory(catalogue, fallback, raw, projects, dict(records),
                             {relative:digest(data) for relative,data in raw.items()})


def _markdown_after(meta, body):
    header = dump_markdown(meta, '').split('\n---\n', 1)[0] + '\n---\n'
    rendered = header + body
    if load_markdown_text(rendered)[0] != meta:
        raise ValueError('原 Markdown 元数据不能安全往返，请先核查原文件')
    return rendered.encode('utf-8')


def _item(relative, meta, source):
    return {**meta, 'body':raw_markdown_body(source.raw[relative])}


def _switch_map(command):
    result = {kind:{} for kind in STATE_TYPES}
    for row in command.get('mapping', []):
        result[row['record_type']][row['source_status']] = row['target_status_id']
    return result


def _binding(meta, templates, fallback):
    return effective_template(meta, templates, fallback)


def _changed_types(original, target):
    return {kind for kind in STATE_TYPES if original[kind] != target[kind]}


def _migrate_project(source, project_id, original, target, changed, command, operation, stamp, project_patch=None):
    project_path, project = source.projects.get(project_id, (None, {}))
    switching = operation == 'switch'
    explicit = _switch_map(command)
    if operation == 'delete_status' and 'target_status_id' in command:
        kind = command['record_type']
        name = next(status['name'] for status in original[kind] if status['id'] == command['status_id'])
        explicit[kind][name] = command['target_status_id']
    maps = {kind:map_states(original[kind], target[kind], switch=switching, explicit=explicit[kind]) for kind in STATE_TYPES}
    files, record_views, missing = [], [], []
    board = {kind:{name:[state['name']] if state else [] for name,state in maps[kind].items()} for kind in STATE_TYPES}
    prior = {kind:{status['name']:status for status in original[kind]} for kind in STATE_TYPES}
    for relative, meta in source.records.get(project_id, ()):
        kind, name = meta['type'], meta['status']
        if kind not in changed and not switching:
            board[kind].setdefault(name, [name])
            continue
        state = target_state(name, maps[kind], target[kind], switching=switching)
        if state is None:
            # An already-unconfigured state is preserved during an unrelated
            # template edit. A deleted or switched state requires a choice.
            if name in maps[kind] or switching:
                missing.append({'project_id':project_id, 'record_type':kind, 'record_id':meta['id'], 'source_status':name})
            board[kind][name] = [name]
            result = meta
        else:
            previous = prior[kind].get(name)
            if switching or name != state['name'] or bool((previous or {}).get('completed')) != bool(state.get('completed')):
                result = record_after(meta, state, previous)
            else:
                result = meta
            board[kind][name] = [state['name']]
        if result != meta:
            result['updated'] = stamp
            files.append(WorkflowFile(relative, source.raw[relative],
                                      _markdown_after(result, raw_markdown_body(source.raw[relative])), meta['id']))
        record_views.append({'id':meta['id'], 'revision':source.watch[relative], 'before':_item(relative, meta, source),
                             'after':_item(relative, result, source)})
    project_view, conflicts = None, []
    if project_path:
        from .projects import project_metadata_patch
        ordering, conflicts = project_order_after(project, board)
        project_patch = project_patch or {}
        result = {**project, **project_metadata_patch(project_patch), **ordering}
        original_body = raw_markdown_body(source.raw[project_path])
        body = original_body
        if 'description' in project_patch or result.get('name') != project.get('name'):
            original_description = original_body.strip().removeprefix(f"# {project.get('name', '')}").strip()
            description = str(project_patch.get('description', original_description)).strip()
            if description != original_description or result.get('name') != project.get('name'):
                body = f"\n# {result['name']}\n\n{description}\n"
        if switching:
            result['workflow_template'] = command['target_template_id']
        if result != project or body != original_body:
            result['updated'] = stamp
            files.append(WorkflowFile(project_path, source.raw[project_path], _markdown_after(result, body)))
        project_view = {'id':project_id, 'revision':source.watch[project_path], 'before':_item(project_path, project, source),
                        'after':{**result, 'body':body}}
    mapping = [{'project_id':project_id, 'type':kind, 'before':name, 'after':state['name'] if state else None,
                'terminal':bool(state.get('completed')) if state else None}
               for kind in STATE_TYPES if switching or kind in changed for name,state in maps[kind].items()]
    if project_view is not None:
        project_view['mapping'] = mapping
    return files, record_views, missing, project_view, conflicts


def prepare_workflow(root, operation, content, *, allocated_id=None, stamp, agent=False, legacy=None, project_patch=None):
    source = inventory(root)
    if legacy is None:
        selection = validate_command(operation, content, agent=agent)
        catalogue = change_catalogue(source.catalogue, operation, selection, allocated_id)
        fallback = source.fallback
    else:
        selection = {}
        catalogue = source.catalogue if operation == 'compat_status' else legacy[0]
        fallback = source.fallback if operation == 'compat_catalogue' else legacy[1]
        current = validate_catalogue(source.catalogue)
        new = validate_catalogue(catalogue)
        if STANDARD in current and (STANDARD not in new or new[STANDARD]['name'] != current[STANDARD]['name']):
            raise ValueError('系统工作流不能改名或删除')
        validate_statuses(fallback)
    before, after = validate_catalogue(source.catalogue), validate_catalogue(catalogue)
    files, project_views, record_views, missing, collisions = [], [], [], [], []
    project_rows = [(key, row[1]) for key,row in source.projects.items()]
    if operation == 'switch':
        project_rows = [(key, project) for key,project in project_rows if key == selection['project_id']]
        if not project_rows:
            raise FileNotFoundError('项目不存在')
    elif None in source.records:
        project_rows.append((None, {}))
    substantive = False
    for project_id, project in project_rows:
        original = _binding(project, before, source.fallback)
        if operation == 'switch':
            target = after[selection['target_template_id']]
            if original is None:
                # The operator supplied a specific new binding. Every current
                # legacy name must be explicitly mapped without a trusted old template.
                original = {'id':None, 'name':None, 'statuses':{kind:[] for kind in STATE_TYPES}}
        else:
            if original is None:
                if catalogue != source.catalogue or fallback != source.fallback:
                    raise ValueError('活动项目的旧工作流绑定存在歧义，请先在本机修复')
                continue
            target = _binding(project, after, fallback)
            if original['id'] not in after:
                raise ValueError('不能删除仍被使用的工作流')
            if target is None or original['id'] != target['id']:
                raise ValueError('工作流修改会隐式改变现有项目绑定')
        changed = _changed_types(original['statuses'], target['statuses'])
        if not changed and original['name'] == target['name'] and operation != 'switch':
            continue
        substantive = True
        rows, records, unmapped, project_view, conflicts = _migrate_project(
            source, project_id, original['statuses'], target['statuses'], changed, selection, operation, stamp, project_patch)
        files.extend(rows)
        record_views.extend(records)
        missing.extend(unmapped)
        collisions.extend({'project_id':project_id, **conflict} for conflict in conflicts)
        if project_view is not None:
            project_view['template_before'] = {'id':original['id'], 'name':original['name'], 'statuses':original['statuses']}
            project_view['template_after'] = {'id':target['id'], 'name':target['name'], 'statuses':target['statuses']}
            project_views.append(project_view)
    if catalogue != source.catalogue:
        files.append(WorkflowFile(CATALOGUE, source.raw[CATALOGUE], encoded(catalogue)))
    if fallback != source.fallback:
        files.append(WorkflowFile(FALLBACK, source.raw[FALLBACK], encoded(fallback)))
    if any(len(file.after) > 1048576 for file in files):
        raise ValueError('工作流候选文件超过完整核验上限')
    return PreparedWorkflow(operation, selection, source.catalogue, catalogue, source.fallback, fallback,
                            source.watch, tuple(files), tuple(project_views), tuple(record_views), tuple(missing),
                            tuple(collisions), substantive)


def verify_workflow_files(root, files, watch, *, allow_applied=False, final=False):
    expected_paths = {path for path in watch if path.startswith(('projects/', 'ideas/'))}
    if {row[0] for row in active_paths(root)} != expected_paths:
        raise RevisionConflict('活动项目或记录集合已经变化')
    changed = {file.path:file for file in files}
    if len(changed) != len(files):
        raise ValueError('工作流候选含重复文件')
    for path in watch.keys() | changed.keys():
        current = digest(read_raw(root, path))
        if path not in changed:
            acceptable = {watch[path]}
        elif final:
            acceptable = {digest(changed[path].after)}
        else:
            acceptable = {digest(changed[path].before)}
            if allow_applied:
                acceptable.add(digest(changed[path].after))
        if current not in acceptable:
            raise RevisionConflict('工作流、项目或记录原字节已经变化')


def snapshot_path(root, file, version):
    if not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[0-9]{6}(?:-[a-f0-9]{8})?', version):
        raise ValueError('工作流历史版本无效')
    if file.record_id:
        from .history import history_path
        path = history_path(root / 'history', file.record_id, version)
    elif file.path.startswith('projects/') and file.path.endswith('/README.md'):
        project = file.path.split('/')[1]
        identity_key(project)
        path = root / 'history' / 'workflow-projects' / project / f'{version}.md'
    else:
        return None
    return controlled(root, path)


def verify_workflow_history(root, files, version):
    for file in files:
        history = snapshot_path(root, file, version)
        if history and file.before != file.after and read_raw(root, history.relative_to(root).as_posix()) != file.before:
            raise RevisionConflict('缺少匹配的工作流原历史')


def apply_workflow_files(root, files, watch, *, history_version, allow_applied=False,
                         invalidate=lambda _:None, checkpoint=lambda *_:None):
    verify_workflow_files(root, files, watch, allow_applied=allow_applied)
    for file in files:
        before = read_raw(root, file.path)
        if file.before == file.after:
            continue
        if before != file.before and (not allow_applied or before != file.after):
            raise RevisionConflict('工作流写入前检测到第三方修改')
        history = snapshot_path(root, file, history_version)
        if history:
            old = read_raw(root, history.relative_to(root).as_posix())
            if old not in (None, file.before) or (before == file.after and old != file.before):
                raise RevisionConflict('已发布文件缺少匹配的原历史')
            if old is None:
                atomic_write_bytes(history, file.before)
                checkpoint('workflow_history', file.path)
        if before == file.before:
            if read_raw(root, file.path) != file.before:
                raise RevisionConflict('工作流发布期间检测到第三方修改')
            target = controlled(root, root / file.path)
            atomic_write_bytes(target, file.after)
            if file.record_id:
                invalidate(target)
            checkpoint('workflow_write', file.path)
        elif file.record_id:
            invalidate(controlled(root, root / file.path))
    verify_workflow_files(root, files, watch, final=True)
    verify_workflow_history(root, files, history_version)
