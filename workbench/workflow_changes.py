"""Pure workflow command validation and migration rules."""

import re
from copy import deepcopy


STANDARD = 'standard'
STATE_TYPES = ('issue', 'todo', 'idea')
BOARD_TYPES = ('issue', 'todo')
SORT_MODES = {'manual', 'updated', 'priority', 'due', 'title', 'created'}
COMMANDS = {
    'create': (('name',), ()),
    'copy': (('template_id', 'name'), ()),
    'rename': (('template_id', 'name'), ()),
    'add_status': (('template_id', 'record_type', 'name', 'color'), ('terminal',)),
    'rename_status': (('template_id', 'record_type', 'status_id', 'name'), ()),
    'delete_status': (('template_id', 'record_type', 'status_id'), ('target_status_id',)),
    'reorder': (('template_id', 'record_type', 'status_id', 'anchor_status_id', 'position'), ()),
    'switch': (('project_id', 'target_template_id'), ('mapping',)),
}


def _label(value):
    if (not isinstance(value, str) or not value or len(value) > 80 or value != value.strip()
            or value == '*' or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError('模板或状态名称无效')
    return value


def _identifier(value):
    if not isinstance(value, str) or not value or len(value) > 160 or value != value.strip() or re.search(r'[\x00-\x1f\x7f/\\]', value):
        raise ValueError('工作流或状态标识无效')
    return value


def validate_command(operation, content, *, agent=False):
    if not isinstance(operation, str) or operation not in COMMANDS or not isinstance(content, dict):
        raise ValueError('工作流操作或字段无效')
    required, optional = map(set, COMMANDS[operation])
    if not required <= content.keys() or content.keys() - required - optional:
        raise ValueError('工作流操作包含未知字段或缺少必填字段')
    value = deepcopy(content)
    for field in required | optional.intersection(content):
        if field.endswith('_id'):
            _identifier(content[field])
    if 'name' in value:
        _label(value['name'])
    if 'record_type' in value and value['record_type'] not in (BOARD_TYPES if agent else STATE_TYPES):
        raise ValueError('此记录类型不能进行状态操作')
    if 'color' in value and (not isinstance(value['color'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value['color'])):
        raise ValueError('状态颜色需为六位十六进制')
    if 'terminal' in value and type(value['terminal']) is not bool:
        raise ValueError('终态语义必须是布尔值')
    if 'position' in value and value['position'] not in ('before', 'after'):
        raise ValueError('状态排序需指定相对位置')
    if operation == 'switch':
        mapping = value.setdefault('mapping', [])
        if not isinstance(mapping, list) or len(mapping) > 200:
            raise ValueError('工作流映射必须是有界的显式列表')
        seen = set()
        for row in mapping:
            if not isinstance(row, dict) or row.keys() != {'record_type', 'source_status', 'target_status_id'}:
                raise ValueError('映射需指定记录类型、源状态和同类目标状态 ID')
            kind, source = row['record_type'], _label(row['source_status'])
            if kind not in STATE_TYPES or (kind, source) in seen:
                raise ValueError('状态映射类型错误或源状态重复')
            seen.add((kind, source))
            _identifier(row['target_status_id'])
    return value


def validate_statuses(statuses):
    if not isinstance(statuses, dict) or not set(STATE_TYPES) <= statuses.keys():
        raise ValueError('状态定义需包含问题、待办和兼容想法')
    for kind in STATE_TYPES:
        values = statuses[kind]
        if not isinstance(values, list) or not values:
            raise ValueError('每种记录至少需要一个状态')
        ids, names = set(), set()
        for status in values:
            if not isinstance(status, dict):
                raise ValueError('状态格式无效')
            key, name = _identifier(status.get('id')), _label(status.get('name'))
            if key in ids or name in names:
                raise ValueError('同一类型的状态 ID 和名称不能重复')
            if 'completed' in status and type(status['completed']) is not bool:
                raise ValueError('状态终态语义无法核验')
            ids.add(key)
            names.add(name)
    return statuses


def validate_catalogue(templates):
    if not isinstance(templates, list) or not templates:
        raise ValueError('至少需要一套工作流模板')
    indexed, names = {}, set()
    for template in templates:
        if not isinstance(template, dict):
            raise ValueError('工作流模板格式无效')
        key, name = _identifier(template.get('id')), _label(template.get('name'))
        if key in indexed or name in names:
            raise ValueError('工作流 ID 和显示名称不能重复')
        validate_statuses(template.get('statuses'))
        indexed[key] = template
        names.add(name)
    return indexed


def effective_template(project, templates, fallback):
    """Resolve only bindings for which the existing browser and Agent agree."""
    binding = project.get('workflow_template')
    if binding in templates:
        return templates[binding]
    if 'workflow_template' not in project and STANDARD in templates:
        return templates[STANDARD]
    first = templates.get(STANDARD) if not binding else None
    first = first or next(iter(templates.values()))
    return first if first['statuses'] == fallback else None


def find_status(statuses, key):
    status = next((item for item in statuses if item['id'] == key), None)
    if status is None:
        raise ValueError('目标状态不在同类型工作流中')
    return status


def change_catalogue(templates, operation, command, allocated_id=None):
    candidate = deepcopy(templates)
    indexed = validate_catalogue(candidate)
    if operation == 'switch':
        if command['target_template_id'] not in indexed:
            raise FileNotFoundError('目标工作流不存在')
        return candidate
    template = indexed.get(command.get('template_id'))
    if operation != 'create' and template is None:
        raise FileNotFoundError('工作流不存在')
    if operation in {'create', 'copy'}:
        source = template or indexed.get(STANDARD) or candidate[0]
        candidate.append({'id':_identifier(allocated_id), 'name':command['name'], 'statuses':deepcopy(source['statuses'])})
    elif operation == 'rename':
        if template['id'] == STANDARD and template['name'] != command['name']:
            raise ValueError('系统工作流不能改名')
        template['name'] = command['name']
    else:
        statuses = template['statuses'][command['record_type']]
        if operation == 'add_status':
            statuses.append({'id':_identifier(allocated_id), 'name':command['name'],
                             'color':command['color'], 'completed':command.get('terminal', False)})
        else:
            status = find_status(statuses, command['status_id'])
            if operation == 'rename_status':
                status['name'] = command['name']
            else:
                statuses.remove(status)
                if operation == 'reorder':
                    anchor = find_status(statuses, command['anchor_status_id'])
                    statuses.insert(statuses.index(anchor) + (command['position'] == 'after'), status)
                elif 'target_status_id' in command:
                    find_status(statuses, command['target_status_id'])
    validate_catalogue(candidate)
    return candidate


def map_states(before, after, *, switch=False, explicit=None):
    """Return the destination definition for each old name, or None if unmapped."""
    explicit = explicit or {}
    by_id = {status['id']:status for status in after}
    by_name = {status['name']:status for status in after}
    lookup = by_name if switch else by_id
    field = 'name' if switch else 'id'
    result = {status['name']:lookup.get(status[field]) for status in before}
    for name, target_id in explicit.items():
        result[name] = find_status(after, target_id)
    return result


def target_state(name, mapping, target_statuses, *, switching):
    if name in mapping:
        return mapping[name]
    if switching:
        return None
    # Retain template-external legacy statuses during unrelated template edits.
    return next((item for item in target_statuses if item['name'] == name), None)


def record_after(record, status, prior=None):
    updated = {**record, 'status':status['name']}
    if record['type'] == 'todo' or ('completed' in record and ('completed' in status or 'completed' in (prior or {}))):
        updated['completed'] = bool(status.get('completed'))
    return updated


def project_order_after(project, mappings):
    """Migrate name-keyed orders; ID orders remain stable."""
    changes = {}
    conflicts = []
    mixed = {}
    for kind in STATE_TYPES:
        mapping = mappings[kind]
        if kind in BOARD_TYPES:
            for name, destinations in mapping.items():
                mixed.setdefault(name, [])
                mixed[name].extend(target for target in destinations if target not in mixed[name])
        _remap_board(project, kind, mapping, changes, conflicts)
    _remap_board(project, 'mixed', mixed, changes, conflicts)
    return changes, conflicts


def _remap_board(project, prefix, mapping, changes, conflicts):
    order_key = f'{prefix}_status_order'
    sorts_key = f'{prefix}_status_record_sorts'
    order = project.get(order_key, [])
    sorts = project.get(sorts_key, {})
    if (not isinstance(order, list) or any(not isinstance(name, str) for name in order)
            or not isinstance(sorts, dict) or any(not isinstance(name, str) or mode not in SORT_MODES for name, mode in sorts.items())):
        raise ValueError('项目状态排序格式无法核验')
    mapped_order = list(dict.fromkeys(target for name in order for target in mapping.get(name, (name,))))
    slots = list(dict.fromkeys([*order, *sorts]))
    mapped_sorts, source = {}, {}
    for name in slots:
        if name not in sorts:
            continue
        for target in mapping.get(name, (name,)):
            if target in mapped_sorts and mapped_sorts[target] != sorts[name]:
                keep = name if name == target else source[target]
                conflicts.append({'board':prefix, 'target':target, 'sources':[source[target], name], 'kept':keep})
            if target not in mapped_sorts or name == target:
                mapped_sorts[target], source[target] = sorts[name], name
    if order_key in project and mapped_order != order:
        changes[order_key] = mapped_order
    if sorts_key in project and mapped_sorts != sorts:
        changes[sorts_key] = mapped_sorts
