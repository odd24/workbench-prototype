"""Select complete active sources affected by one proposed project trash move."""

import html
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .agent_delete_service import access_target, source_view
from .agent_security import allows
from .deletion_inventory import active_inventory
from .deletion_prepared import DELETE_KINDS
from .document_attachments import attachment_items, local_links
from .references import references, text_values


ASSET_RESOURCE = re.compile(
    r'(?<![A-Za-z0-9_./:-])(?:https?://(?:127\.0\.0\.1|localhost)(?::[0-9]+)?)?'
    r'/api/(?:project-assets|attachments|markdown-images)/[^\s<>"\x27)\]]+', re.I)
HTML_LINK = re.compile(r'\b(?:src|href)\s*=\s*["\x27]([^"\x27]+)["\x27]', re.I)
LINK_DEFINITION = re.compile(r'^\s*\[[^\]]+\]:\s*(<[^>\n]+>|\S+)', re.M)


def _file_links(text):
    yield from (target for _, target in local_links(text))
    for pattern in (HTML_LINK, LINK_DEFINITION):
        for match in pattern.finditer(text):
            yield match[1].strip('<>').split('#', 1)[0].split('?', 1)[0]


def _points_into_tree(root, owner, source, binaries, *, decode):
    if not source:
        return False
    value = unquote(source, errors='strict') if decode else source
    if not value or value.startswith(('/', '\\')) or ':' in value or '\x00' in value:
        return False
    # Only resolve existing local relative paths. The app does not resolve remote
    # content, and an alias to a moved binary must not evade the check.
    candidate = Path(os.path.abspath(owner.parent / value))
    if not candidate.is_relative_to(root):
        return False
    if candidate in binaries:
        return True
    return candidate.is_file() and candidate.resolve() in binaries


def active_project_impacts(repository, client, project_id, records, assets, binaries, readme_revision):
    """Return full authorized matches and a digest of the whole active catalogue."""
    root = repository.root
    folder = root / 'projects' / project_id
    binaries = {folder / name for name in binaries}
    children = {record['item']['id']: record['item']['type'] for record in records}
    child_paths = {record['item']['id']: folder / record['relative_path'] for record in records}
    asset_ids = {asset['id'] for asset in assets}
    child_attachments = {record['item']['id']: {entry['name'] for entry in record['attachments']
                                              if entry['action'] == 'move'} for record in records}

    def select(relative, kind, item, links):
        owner = root / relative
        if owner.is_relative_to(folder):
            return None
        matched = []
        for link in links:
            key, name = link['id'], link['attachment']
            if link.get('kind') == 'project' and key == project_id:
                if name is not None and name in asset_ids:
                    raise ValueError('活动来源仍引用将移动的附件')
                matched.append(link)
            elif key in children and link.get('kind', children[key]) == children[key]:
                if name is not None and name in child_attachments[key]:
                    raise ValueError('活动来源仍引用将移动的附件')
                matched.append(link)
        if binaries:
            for attachment in attachment_items(item.get('attachments', [])):
                if _points_into_tree(root, owner, attachment['path'], binaries, decode=False):
                    raise ValueError('活动来源仍引用将移动的附件')
            for text in text_values(item):
                unescaped = html.unescape(text)
                if any(_points_into_tree(root, owner, source, binaries, decode=True) for source in _file_links(unescaped)):
                    raise ValueError('活动来源仍引用将移动的附件')
                for match in ASSET_RESOURCE.finditer(unescaped):
                    url = urlsplit(match[0])
                    parts = url.path.split('/')
                    if len(parts) == 4 and parts[2] == 'markdown-images':
                        resource = child_paths.get(unquote(parts[3], errors='strict'))
                        if resource and any(_points_into_tree(root, resource, name, binaries, decode=decode)
                                            for name in parse_qs(url.query).get('path', ()) for decode in (False, True)):
                            raise ValueError('活动来源仍引用将移动的附件')
                        continue
                    if len(parts) != 5:
                        continue
                    key, name = (unquote(part, errors='strict') for part in parts[3:])
                    if (parts[2] == 'project-assets' and key == project_id and name in asset_ids
                            or parts[2] == 'attachments' and name in child_attachments.get(key, ())):
                        raise ValueError('活动来源仍引用将移动的附件')
        if matched or kind == 'concept_map' and item.get('project_id') == project_id:
            return matched
        return None

    entries, digest = active_inventory(root, select_impact=select)
    expected = {f'projects/{project_id}/README.md':readme_revision,
                **{f"projects/{project_id}/{record['relative_path']}":record['revision'] for record in records}}
    observed = {entry['relative_path']:entry['revision'] for entry in entries
                if (root / entry['relative_path']).is_relative_to(folder)}
    if observed != expected:
        raise ValueError('原项目在活动来源核验期间变化')
    impacts = []
    for entry in entries:
        if 'raw' not in entry:
            continue
        kind, item = entry['kind'], entry['item']
        if kind not in DELETE_KINDS or not allows(client, access_target(kind, item)):
            raise ValueError('无法完整授权活动影响')
        urls = {link['token'] for link in references(item.get('body', ''), project_links=True)
                if link['syntax'] == 'item_link'}
        impacts.append({'source':source_view(repository, entry, url_references=urls), 'references':entry['references'],
                        'associated_graph':kind == 'concept_map' and item.get('project_id') == project_id})
    return impacts, digest
