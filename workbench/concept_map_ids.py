"""Monotonic graph allocation; proposals remain the sole Agent reservation."""

import json
import re

from .document_attachments import safe_local_path
from .persistence import atomic_write_json


class ConceptMapIdentityError(ValueError):
    """Allocation evidence is unknown: preserve every source and stop writes."""


def controlled(root, relative):
    return safe_local_path(root, relative, (root,), decode=False)


def read_json(root, path):
    path = controlled(root, path.relative_to(root).as_posix())
    return json.loads(path.read_text(encoding='utf-8'))


def graph_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'CMAP-[0-9]+', value):
        raise ValueError('占用身份无效')
    return value


def graph_evidence(root, path, expected=None):
    value = read_json(root, path)
    key = graph_id(value['id'])
    if expected is not None and key != expected or type(value.get('version', 1)) is not int or value.get('version', 1) not in (1, 2):
        raise ValueError('占用图格式或身份不受支持')
    return key


def occupied_ids(repository):
    """Read all known sources without expiry, cleanup, adoption or repair."""
    root = repository.root
    try:
        used = set()
        formal = controlled(root, 'concept-maps')
        for path in formal.glob('CMAP-*'):
            if path.suffix != '.json':
                raise ValueError('未知正式图占用')
            used.add(graph_evidence(root, path, graph_id(path.stem)))
        history = controlled(root, 'history')
        for directory in history.glob('CMAP-*'):
            key = graph_id(directory.name)
            controlled(root, directory.relative_to(root).as_posix())
            if not directory.is_dir():
                raise ValueError('图历史占用不是目录')
            used.add(key)
            for path in directory.iterdir():
                if not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[0-9]{6}(?:-[a-f0-9]{8})?\.json', path.name):
                    raise ValueError('未知图历史占用')
                graph_evidence(root, path, key)
        trash = controlled(root, '.trash')
        index = read_json(root, trash / 'index.json')
        if not isinstance(index, dict):
            raise ValueError('回收站索引格式无效')
        for token, item in index.items():
            if not isinstance(item, dict) or item.get('token') != token or not isinstance(item.get('id'), str) or item.get('kind') not in {'project', 'document', 'record', 'concept-map'}:
                raise ValueError('回收站占用不受支持')
            if item['kind'] == 'concept-map':
                key = graph_id(item['id'])
                # Derive the destination from the index token, never trust its
                # absolute machine path as a source to read.
                if not isinstance(token, str) or '/' in token or '\\' in token or token in {'.', '..'}:
                    raise ValueError('回收站占用路径无效')
                used.add(graph_evidence(root, trash / token, key))
        for path in trash.glob('concept-map-*'):
            if path.name not in index:
                used.add(graph_evidence(root, path))  # Crash after move, before index.
        agent = controlled(root, '.agent')
        store = getattr(repository, 'agent_proposals', None)
        sources = any((agent / name).exists() for name in ('proposals', 'operations', 'receipts'))
        if sources and store is None:
            raise ValueError('缺少匹配的提案格式读取器')
        if store:
            store.preflight()
            for path in store.proposals.glob('*.json'):
                controlled(root, path.relative_to(root).as_posix())
                proposal = store._load(path.stem, expire=False)
                if proposal['kind'] == 'concept_map':
                    used.add(graph_id(proposal['target_id']))
            for path in store.operations.glob('*/manifest.json'):
                manifest = read_json(root, path)
                if manifest['kind'] == 'concept_map':
                    used.add(graph_id(manifest['item_id']))
            for path in store.receipts.glob('*.json'):
                receipt = read_json(root, path)
                proposal = store._load(path.stem, expire=False)
                manifest_path = store.operations / f"{path.stem}-{receipt['version']}" / 'manifest.json'
                manifest = read_json(root, manifest_path)
                if manifest['receipt'] != receipt or receipt['proposal_id'] != path.stem or receipt['kind'] != proposal['kind']:
                    raise ValueError('孤立或不一致回执占用')
                if receipt['kind'] == 'concept_map':
                    used.add(graph_id(receipt['item_id']))
        return used
    except Exception as error:
        raise ConceptMapIdentityError('概念图编号占用证据损坏或版本未知；保留文件并停止分配') from error


def advance(root, occupied, *, allocate):
    """Caller holds the shared Repository/ID lock. Persist before publication."""
    try:
        path = controlled(root, 'config/concept-map-ids.json')
        exists = path.exists()
        before = read_json(root, path) if exists else None
        if exists and (not isinstance(before, dict) or set(before) != {'schema_version', 'high_water'} or type(before['schema_version']) is not int or before['schema_version'] != 1 or type(before['high_water']) is not int or before['high_water'] < 0):
            raise ValueError('未知或损坏游标')
        highest = max((int(graph_id(key)[5:]) for key in occupied()), default=0)
        highest = max(highest, before['high_water'] if before is not None else 0) + int(allocate)
        after = {'schema_version': 1, 'high_water': highest}
        if after != before:
            atomic_write_json(path, after)
        return f'CMAP-{highest:04d}'
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        raise ConceptMapIdentityError('概念图编号游标不可用；保留配置并停止分配') from error
