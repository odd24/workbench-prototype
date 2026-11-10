"""Project allocation occupancy shared by ordinary creation and Agent plans."""

import json
import re

from .document_attachments import safe_local_path
from .markdown_io import load_markdown_text, slugify


_DEVICE = re.compile(r'(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', re.I)
_BAD_COMPONENT = re.compile(r'[\x00-\x1f<>:"/\\|?*]')


def identity_key(value):
    if not isinstance(value, str) or not value or _BAD_COMPONENT.search(value) or value in {'.', '..'}:
        raise ValueError('项目占用身份无效')
    key = value.rstrip(' .').casefold()
    if not key:
        raise ValueError('项目占用身份无效')
    return key


def valid_new_id(value):
    key = identity_key(value)
    if len(value) > 110 or key != value.casefold() or _DEVICE.fullmatch(value):
        raise ValueError('新项目目录名无效')
    return key


def next_project_id(name, occupied):
    base = slugify(_BAD_COMPONENT.sub('-', name)).rstrip(' .') or 'untitled'
    if _DEVICE.fullmatch(base):
        base = 'project-' + base
    key, index = base, 2
    while identity_key(key) in occupied:
        key, index = f'{base}-{index}', index + 1
    return key


def controlled(root, path):
    return safe_local_path(root, path.relative_to(root).as_posix(), (root,), decode=False)


def read_bounded(path, *, limit=1048576):
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('项目身份或配置证据超出核验上限')
    return raw


def load_unique_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('项目身份或配置证据含重复字段')
            result[key] = value
        return result

    def reject_constant(_):
        raise ValueError('配置含非有限数')

    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=reject_constant)


def disk_occupied(root):
    """Count even incomplete entries; never follow a reparse point."""
    projects = controlled(root, root / 'projects')
    trash = controlled(root, root / '.trash')
    used = set()
    for path in projects.iterdir():
        used.add(identity_key(path.name))
        # An existing alias can never be used as the new destination.
        checked = controlled(root, path)
        if checked.is_dir():
            readme = controlled(root, checked / 'README.md')
            if readme.exists():
                meta, _ = load_markdown_text(read_bounded(readme).decode('utf-8'))
                if meta.get('type') == 'project':
                    used.add(identity_key(meta['id']))
    index = load_unique_json(read_bounded(controlled(root, trash / 'index.json')))
    if not isinstance(index, dict):
        raise ValueError('回收站占用格式不受支持')
    for token, entry in index.items():
        if not isinstance(entry, dict) or entry.get('token') != token or entry.get('kind') not in {'project', 'record', 'document', 'concept-map'}:
            raise ValueError('回收站占用格式不受支持')
        if entry['kind'] == 'project':
            used.add(identity_key(entry['id']))
    for path in trash.glob('project-*'):
        if path.name not in index:
            readme = controlled(root, path / 'README.md')
            meta, _ = load_markdown_text(read_bounded(readme).decode('utf-8'))
            if meta.get('type') != 'project':
                raise ValueError('无法核验无索引回收项目')
            used.add(identity_key(meta['id']))
    return used


def reserved_projects(repository, *, exclude_proposal=None):
    """Read validated permanent Agent reservations without expiry or repair."""
    root = repository.root
    agent = controlled(root, root / '.agent')
    store = getattr(repository, 'agent_proposals', None)
    if store is None:
        if any((agent / name).exists() for name in ('proposals', 'operations', 'receipts')):
            raise ValueError('缺少项目身份所需的提案读取器')
        return set()
    store.preflight()
    used = set()
    for path in store.proposals.glob('*.json'):
        proposal = store._load(path.stem, expire=False)
        if proposal.get('kind') == 'project' and path.stem != exclude_proposal:
            used.add(identity_key(proposal['target_id']))
    for path in store.receipts.glob('*.json'):
        receipt = load_unique_json(read_bounded(controlled(root, path)))
        proposal = store._load(path.stem, expire=False)
        if receipt.get('kind') != proposal['kind'] or receipt.get('proposal_id') != path.stem:
            raise ValueError('项目回执占用证据不一致')
        if receipt['kind'] == 'project':
            if receipt['item_id'] != proposal['target_id'] or proposal.get('receipt') != receipt:
                raise ValueError('项目回执没有原项目身份证据')
            if path.stem != exclude_proposal:
                used.add(identity_key(receipt['item_id']))
    return used


def scoped_project_ids(security):
    """Exclude still configured exact scopes, even for disabled clients."""
    from .agent_concept_authorization import client_graph_grants
    from .agent_delete_authorization import client_delete_grants
    from .agent_project_delete_authorization import client_project_delete_grants
    from .agent_security import client_kinds

    if security.manager().blocked_clients():
        raise ValueError('存在未决授权，无法核对项目占用')
    used = set()
    for client in security.clients().values():
        client_kinds(client)
        if not isinstance(client['project_ids'], list):
            raise ValueError('现有项目范围格式未知，不能确认编号占用')
        used.update(identity_key(key) for key in client['project_ids'] if key != '*')
        used.update(identity_key(grant['project_id']) for grant in client_project_delete_grants(client)['grants'])
        for policy in (client_graph_grants(client), client_delete_grants(client)):
            for grant in policy['grants']:
                used.update(identity_key(resource['id']) for resource in grant['resources'] if resource['type'] == 'project')
    from .agent_upload_policy import load_policies
    used.update(identity_key(policy['owner_id']) for policy in load_policies(security)['policies'].values()
                if policy['enabled'] and policy['owner_kind'] == 'project')
    return used
