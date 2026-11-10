"""Conservative, bounded-root attachment reference inventory.

Snapshots are interpreted relative to the original owner, never history/.trash.
An unreadable or unknown inventory prevents deletion instead of guessing.
"""

import json
import re
from pathlib import Path

from .document_attachments import attachment_items, local_links, safe_local_path, INTERNAL_ATTACHMENT
from .markdown_io import load_markdown
from .agent_security import AgentError


def orphan_report(domain):
    root = domain.root
    referenced, warnings = set(), []
    roots = [domain.global_assets_dir, *domain.projects_dir.glob('*/assets')]
    owners, snapshots = {}, []

    def warn():
        # Reports never leak arbitrary local paths or source body content.
        message = '存在无法确认的附件引用或损坏元数据，已保守保留全部候选文件'
        if message not in warnings:
            warnings.append(message)

    def add_snapshot(path, original=None):
        try:
            if path.resolve() != path.absolute():
                raise ValueError()
            meta, body = load_markdown(path)
            if meta.get('type') not in {'issue', 'todo', 'info', 'idea', 'document', 'project'} or not meta.get('id'):
                raise ValueError()
            if original is None:
                if meta['type'] == 'document':
                    original = root / 'documents' / (meta['id'] + '.md')
                elif meta.get('project_id') and meta['type'] in {'issue', 'todo', 'info', 'idea'}:
                    original = root / 'projects' / meta['project_id'] / (meta['type'] + 's') / (meta['id'] + '.md')
                elif meta['type'] == 'idea':
                    original = root / 'ideas' / (meta['id'] + '.md')
                else:
                    raise ValueError()
            original = Path(original).absolute()
            if not original.is_relative_to(root) or original.is_relative_to(root / '.trash') or original.is_relative_to(root / 'history'):
                raise ValueError()
            snapshots.append((meta, body, original))
            owners[meta['id']] = original
        except (ValueError, OSError, TypeError, KeyError):
            warn()

    current = list((root / 'documents').glob('*.md')) + list((root / 'ideas').glob('*.md'))
    current += list(domain.projects_dir.glob('*/README.md'))
    for category in ('issues', 'todos', 'infos', 'ideas'):
        current += list(domain.projects_dir.glob('*/' + category + '/*.md'))
    for path in current:
        add_snapshot(path, path)
    for path in (root / 'history').glob('*/*.md'):
        add_snapshot(path, owners.get(path.parent.name))
    try:
        trash = json.loads((root / '.trash' / 'index.json').read_text(encoding='utf-8'))
        if not isinstance(trash, dict):
            raise ValueError()
        for value in trash.values():
            if value.get('delete_schema_version') == 2:
                from .agent_delete_execution import validated_trash_paths
                path, original, _, _ = validated_trash_paths(domain, value)
                roots.append(original / 'assets')
                add_snapshot(path / 'README.md', original / 'README.md')
            else:
                original, path = Path(value['original_path']), Path(value['trash_path'])
            if not path.absolute().is_relative_to(root / '.trash') or path.resolve() != path.absolute():
                raise ValueError()
            if path.is_file():
                # Binary trash entries cannot be parsed as Markdown; only known
                # owner kinds participate. Unknown kinds still prevent deletion.
                if value.get('kind') in {'issue', 'todo', 'info', 'idea', 'document'}:
                    add_snapshot(path, original)
                elif value.get('kind') not in {'attachment', 'project_asset', 'concept_map'}:
                    warn()
            elif path.is_dir() and value.get('kind') == 'project':
                for part in ('issues', 'todos', 'infos', 'ideas'):
                    for child in (path / part).glob('*.md'):
                        add_snapshot(child, original / part / child.name)
            elif not path.exists():
                warn()
    except (ValueError, OSError, KeyError, TypeError, AgentError):
        warn()

    all_asset_roots = tuple(roots)
    # Legacy external-editor document images can also live under documents/.
    body_roots = (*all_asset_roots, root / 'documents')
    known_attachments = set()
    for meta, body, original in snapshots:
        try:
            for item in attachment_items(meta.get('attachments', [])):
                referenced.add(safe_local_path(original.parent, item['path'], all_asset_roots, decode=False))
                known_attachments.add((meta['id'].upper(), item['name']))
            for _match, source in local_links(body):
                if source:
                    referenced.add(safe_local_path(original.parent, source, body_roots))
            for source in re.findall(r'(?:src|href)=["\']([^"\']+)["\']', body, re.I):
                if not re.match(r'^(?:https?://|mailto:|#|data:)', source, re.I):
                    referenced.add(safe_local_path(original.parent, source, body_roots))
            for source in re.findall(r'^\s*\[[^\]]+\]:\s*(\S+)', body, re.M):
                if not source.startswith(('http://', 'https://')):
                    referenced.add(safe_local_path(original.parent, source.strip('<>'), body_roots))
            if len(re.findall(r'(?<!\\)\]\(', body)) > sum(1 for _ in local_links(body)) + len(re.findall(r'\]\((?:https?://|mailto:|#|data:)', body)):
                warn()
        except (ValueError, OSError, TypeError):
            warn()
    from urllib.parse import unquote
    for _meta, body, _original in snapshots:
        for match in INTERNAL_ATTACHMENT.finditer(body):
            if (match[1].upper(), unquote(match[2])) not in known_attachments:
                warn()
    for project in domain.projects_dir.iterdir():
        if not project.is_dir():
            continue
        for name in ('index.json', 'categories.json'):
            path = project / 'assets' / name
            referenced.add(path.absolute())
            if name == 'index.json' and path.exists():
                try:
                    values = json.loads(path.read_text(encoding='utf-8'))
                    if not isinstance(values, list):
                        raise ValueError()
                    for item in values:
                        referenced.add(safe_local_path(project, item['path'], (project / 'assets',), decode=False))
                except (ValueError, OSError, TypeError, KeyError):
                    warn()
    # Reuse each operation store's strict preflight; do not maintain a weaker
    # second parser here. Inventory summaries retain no editor body snapshots.
    try:
        for value in domain.agent_operation_inventory():
            if value.get('operation') == 'delete' and value.get('state') != 'committed':
                # Even abandon accepts disk state rather than undoing deletion.
                # Unindexed or uncertain moved sources may still own attachments.
                warn()
            if value.get('kind') == 'attachment' and value.get('state') != 'committed':
                referenced.add(safe_local_path(root, value['binary_relative'], all_asset_roots, decode=False))
        for value in domain.document_upload_inventory():
            if value['binary_relative'] and value['state'] in {'prepared', 'applying', 'abandoned'}:
                referenced.add(safe_local_path(root, value['binary_relative'], all_asset_roots, decode=False))
    except (AgentError, ValueError, OSError, TypeError, KeyError, AttributeError):
        warn()
    orphaned = []
    if not warnings:
        for asset_root in roots:
            if asset_root.resolve() != asset_root.absolute():
                warn(); break
            for path in asset_root.rglob('*'):
                try:
                    candidate = safe_local_path(asset_root, path.relative_to(asset_root).as_posix(), (asset_root,), decode=False)
                    if candidate.is_file() and candidate not in referenced:
                        orphaned.append({'path':str(candidate), 'name':candidate.name, 'size':candidate.stat().st_size})
                except (ValueError, OSError):
                    warn(); break
    return {'orphans':[] if warnings else orphaned, 'warnings':warnings}
