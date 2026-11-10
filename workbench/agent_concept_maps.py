"""Strict Agent graph candidates; ordinary legacy graph normalization stays tolerant."""

import json
import math
import re
from collections import Counter
from pathlib import Path

from .agent_security import AgentError
from .concept_maps import ConceptMapRepository


GRAPH_FIELDS = {'version', 'title', 'project_id', 'category', 'focus_question', 'theme', 'viewport', 'nodes', 'edges'}
NODE_FIELDS = {'id', 'type', 'text', 'note', 'x', 'y', 'width', 'height', 'color', 'border_color', 'text_color', 'font_size', 'font_weight', 'shape'}
EDGE_FIELDS = {'id', 'from', 'to', 'label', 'color', 'dashed', 'arrowhead'}
GRAPH_BYTES = 256 * 1024
RAW_BASE_BYTES = 1024 * 1024
PREVIEW_BYTES = 2 * 1024 * 1024


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def controlled_graph_path(root, relative, *, required=False):
    from .document_attachments import safe_local_path
    try:
        return safe_local_path(Path(root), relative, (Path(root),), required=required, decode=False)
    except (ValueError, OSError):
        raise AgentError('unsafe_concept_map_path', '图资源路径不可安全读取，保留文件并停止操作', 503) from None


def read_graph(root, map_id):
    from .write_coordinator import content_revision
    if not isinstance(map_id, str) or not re.fullmatch(r'CMAP-[0-9]+', map_id):
        raise AgentError('not_found', '概念图不存在或不可访问', 404)
    path = controlled_graph_path(root, f'concept-maps/{map_id}.json')
    if not path.is_file():
        raise AgentError('not_found', '概念图不存在或不可访问', 404)
    try:
        with path.open('rb') as source:
            raw = source.read(RAW_BASE_BYTES + 1)
        if len(raw) > RAW_BASE_BYTES:
            raise AgentError('content_too_large', '图原始文件超过1MiB，不能完整读取或预览', 413)
        item = json.loads(raw.decode('utf-8'))
        if not isinstance(item, dict) or item.get('id') != map_id or type(item.get('version', 1)) is not int or item.get('version', 1) not in (1, 2) or not isinstance(item.get('nodes', []), list) or not isinstance(item.get('edges', []), list):
            raise ValueError()
        json_bytes(item)
    except (OSError, ValueError, TypeError, UnicodeError):
        raise AgentError('invalid_base_concept_map', '图格式或身份不受支持，保留文件并停止操作', 503) from None
    return {**item, 'revision': content_revision(raw)}, path, raw


def graph_catalog(root):
    directory = controlled_graph_path(root, 'concept-maps')
    result = []
    for path in sorted(directory.glob('CMAP-*.json')):
        item, _, _ = read_graph(root, path.stem)
        result.append({key: item.get(key) for key in ('id', 'title', 'project_id', 'created', 'updated', 'revision')} | {'category':item.get('category', '未分类')})
    return result


def _invalid(message, code='invalid_concept_map'):
    raise AgentError(code, message)


def _object(value, fields, label):
    if not isinstance(value, dict) or set(value) != fields:
        _invalid(f'{label}必须包含全部已声明字段，不接受未知字段')


def _text(value, maximum, label, *, nonempty=False, trimmed=False):
    if not isinstance(value, str) or len(value) > maximum or any((ord(c) < 32 and c not in '\r\n\t') or 0xd800 <= ord(c) <= 0xdfff for c in value):
        _invalid(f'{label}文本或长度无效')
    if nonempty and not value.strip() or trimmed and value != value.strip():
        _invalid(f'{label}须为有效且无首尾空白的文本')


def _number(value, minimum, maximum, label, *, integer=False):
    if type(value) not in (int, float) or not minimum <= value <= maximum or not math.isfinite(value) or integer and type(value) is not int:
        _invalid(f'{label}数值超出支持范围')


def _identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value):
        _invalid(f'{label}标识无效')


def _color(value):
    if not isinstance(value, str) or not re.fullmatch(r'#[a-fA-F0-9]{6}', value):
        _invalid('图颜色必须为六位十六进制颜色')


def _without_id(value, node_mapping=None):
    value = {key: item for key, item in value.items() if key != 'id'}
    if node_mapping:
        value = {**value, 'from': node_mapping.get(value['from'], value['from']), 'to': node_mapping.get(value['to'], value['to'])}
    return json_bytes(value)


def check_stable_ids(base, candidate):
    """Prove only unique, fully equal non-ID structures; never infer semantics."""
    mapping = {}
    changed = []
    for collection in ('nodes', 'edges'):
        old, new = base.get(collection, []), candidate[collection]
        if not isinstance(old, list) or any(not isinstance(item, dict) or not isinstance(item.get('id'), str) for item in old):
            _invalid('旧图身份字段无法安全表达，请先在本机检查并保存', 'legacy_identity_invalid')
        old_ids, new_ids = {item['id'] for item in old}, {item['id'] for item in new}
        if len(old_ids) != len(old) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value) for value in old_ids):
            _invalid('旧图包含重复或无效身份，请先在本机检查并保存', 'legacy_identity_invalid')
        # Only complete structures can prove a pure renumbering. Missing legacy
        # fields and duplicate equal structures provide no such proof.
        fields = NODE_FIELDS if collection == 'nodes' else EDGE_FIELDS
        old_complete = [item for item in old if set(item) == fields]
        new_complete = [item for item in new if set(item) == fields]
        old_keys = Counter(_without_id(item) for item in old_complete)
        new_keys = Counter(_without_id(item, mapping if collection == 'edges' else None) for item in new_complete)
        removed = {_without_id(item): item for item in old_complete if item['id'] not in new_ids}
        for item in new_complete:
            if item['id'] in old_ids:
                continue
            key = _without_id(item, mapping if collection == 'edges' else None)
            if old_keys[key] == new_keys[key] == 1 and key in removed:
                original = removed[key]['id']
                changed.append({'collection': collection, 'before': original, 'after': item['id']})
                if collection == 'nodes':
                    mapping[item['id']] = original
    if changed:
        raise AgentError('unstable_element_id', '请保留完整相同元素的既有ID，不能仅重新编号', details={'changes': changed})


def validate_graph(graph, *, base=None, create=False):
    _object(graph, GRAPH_FIELDS, '完整图候选')
    if type(graph['version']) is not int or graph['version'] != 2:
        _invalid('Agent图候选仅支持version=2')
    _text(graph['title'], 120, '图标题', nonempty=True, trimmed=True)
    _text(graph['category'], 200, '图分类', nonempty=True, trimmed=True)
    _text(graph['focus_question'], 500, '焦点问题', trimmed=True)
    if graph['project_id'] is not None:
        _text(graph['project_id'], 80, '所属项目', nonempty=True, trimmed=True)
        if any(c in graph['project_id'] for c in '/\\:*\r\n\t') or graph['project_id'] in {'.', '..'}:
            _invalid('所属项目必须为已有稳定标识，不接受路径')
    if not isinstance(graph['theme'], str) or graph['theme'] not in {'light', 'paper', 'dots'}:
        _invalid('图主题无效')
    _object(graph['viewport'], {'x', 'y', 'zoom'}, '视口')
    for key in ('x', 'y'):
        _number(graph['viewport'][key], -100000, 100000, '视口坐标')
    _number(graph['viewport']['zoom'], .2, 3, '视口缩放')
    if not isinstance(graph['nodes'], list) or not (1 if create else 0) <= len(graph['nodes']) <= 500:
        _invalid('节点数量无效；Agent新建须显式提供至少一个节点')
    if not isinstance(graph['edges'], list) or len(graph['edges']) > 1000:
        _invalid('关系数量无效')
    types = {}
    for node in graph['nodes']:
        _object(node, NODE_FIELDS, '节点')
        _identifier(node['id'], '节点')
        if node['id'] in types:
            _invalid('节点ID重复')
        if not isinstance(node['type'], str) or node['type'] not in {'concept', 'linking_phrase'}:
            _invalid('节点类型无效')
        types[node['id']] = node['type']
        _text(node['text'], 500, '节点文字', nonempty=True, trimmed=True)
        _text(node['note'], 5000, '节点说明')
        for key in ('x', 'y'):
            _number(node[key], -100000, 100000, '节点坐标')
        _number(node['width'], 30 if node['type'] == 'linking_phrase' else 72, 420, '节点宽度')
        _number(node['height'], 22 if node['type'] == 'linking_phrase' else 30, 260, '节点高度')
        _number(node['font_size'], 10, 32, '字体大小', integer=True)
        if type(node['font_weight']) is not int or node['font_weight'] not in (400, 600, 700):
            _invalid('字体粗细无效')
        if not isinstance(node['shape'], str) or node['shape'] not in {'rounded', 'rectangle', 'pill', 'ellipse'}:
            _invalid('节点形状无效')
        for key in ('color', 'border_color', 'text_color'):
            _color(node[key])
    seen = set()
    for edge in graph['edges']:
        _object(edge, EDGE_FIELDS, '关系')
        _identifier(edge['id'], '关系')
        if edge['id'] in seen:
            _invalid('关系ID重复')
        seen.add(edge['id'])
        if not isinstance(edge['from'], str) or not isinstance(edge['to'], str) or edge['from'] not in types or edge['to'] not in types or edge['from'] == edge['to']:
            _invalid('关系必须引用本候选中的两个不同节点')
        _text(edge['label'], 120, '关系文字', trimmed=True)
        _color(edge['color'])
        if type(edge['dashed']) is not bool or not isinstance(edge['arrowhead'], str) or edge['arrowhead'] not in {'none', 'from', 'to', 'both'}:
            _invalid('关系样式或箭头无效')
        if types[edge['to']] == 'linking_phrase' and edge['arrowhead'] not in {'none', 'from'} or types[edge['from']] == 'linking_phrase' and types[edge['to']] == 'concept' and edge['arrowhead'] != 'to':
            _invalid('关系箭头与连词节点方向不兼容')
    if base is not None and not isinstance(base, dict):
        _invalid('原图数据格式无效', 'invalid_base_concept_map')
    try:
        too_large = len(json_bytes(graph)) > GRAPH_BYTES or base is not None and len(json_bytes(base)) > GRAPH_BYTES
    except (ValueError, TypeError, OverflowError, UnicodeError):
        _invalid('原图含不可完整表达的JSON数据，请先在本机核查', 'invalid_base_concept_map')
    if too_large:
        raise AgentError('content_too_large', '图候选或原图JSON数据超过256KiB，不能完整预览', 413)
    try:
        normalized = ConceptMapRepository.normalize(graph)
    except (ValueError, TypeError, OverflowError):
        _invalid('图字段不能按现有领域规则保存')
    warnings = []
    if normalized != graph:
        # Validation above excludes truncation, re-ID, range coercion and trim.
        if json_bytes(normalized).lower() != json_bytes(graph).lower():
            _invalid('图归一化会改变候选，请按规范重新整理')
        warnings.append('颜色字母统一为小写；完整规范化结果以本预览为准。')
    if base is not None:
        check_stable_ids(base, normalized)
    return normalized, warnings
