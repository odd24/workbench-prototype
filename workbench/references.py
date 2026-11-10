"""Read existing internal reference syntax without maintaining a second index."""

import html
import re
from urllib.parse import parse_qs, unquote, urlsplit


REFERENCE = re.compile(r'\[\[([A-Za-z]+-[0-9]+)(?:#([^\]]+))?\]\]')
ITEM_URL = re.compile(r'(?<![A-Za-z0-9_./:-])(?:https?://(?:127\.0\.0\.1|localhost)(?::[0-9]+)?)?/\?[^\s<>"\x27)\]]+')


def text_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if key == 'links':
                for token in item if isinstance(item, list) else [item]:
                    if isinstance(token, str) and re.fullmatch(r'[A-Za-z]+-[0-9]+(?:#[^\]]+)?', token):
                        yield '[[' + token + ']]'
            yield from text_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from text_values(item)
    elif value is not None and type(value) not in (int, float, bool):
        raise ValueError('未知用户文本结构，不能完整识别引用')


def references(value, *, strict=False):
    """Potential textual links, including code samples; never execute text."""
    found = []
    for text in text_values(value):
        for match in REFERENCE.finditer(text):
            suffix = match[2] or ''
            if suffix and suffix != 'body' and not suffix.startswith('attachment:'):
                if strict:
                    raise ValueError('未知内部引用形式，不能建立完整影响计划')
                continue
            found.append({'id':match[1].upper(), 'syntax':'token', 'token':match[0],
                          'attachment':unquote(suffix[len('attachment:'):]) if suffix.startswith('attachment:') else None})
        for match in ITEM_URL.finditer(html.unescape(text)):
            url = urlsplit(match[0])
            query = parse_qs(url.query, keep_blank_values=True)
            if 'item' not in query and 'itemId' not in query:
                continue
            kind, key = query.get('item', []), query.get('itemId', [])
            if kind == ['trash'] and len(key) == 1 and set(query) == {'item', 'itemId'} and re.fullmatch(r'(?:record|document|concept-map)-agent-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}-[1-9][0-9]*', key[0]):
                continue  # A receipt link addresses retained trash, not a formal item.
            if kind == ['project'] and len(key) == 1 and set(query) == {'item', 'itemId'}:
                from .project_identity import valid_new_id
                try:
                    valid_new_id(key[0])
                except ValueError:
                    pass
                else:
                    continue  # Project results are outside the single-item deletion surface.
            valid = len(kind) == len(key) == 1 and kind[0] in {'issue', 'todo', 'info', 'document', 'concept_map'} and re.fullmatch(r'(?:ISSUE|TODO|INFO|IDEA|DOC|CMAP)-[0-9]+', key[0])
            if valid and kind[0] in {'document', 'todo', 'info', 'concept_map'}:
                valid = key[0].startswith({'document':'DOC-', 'todo':'TODO-', 'info':'INFO-', 'concept_map':'CMAP-'}[kind[0]])
            if valid and kind[0] == 'concept_map':
                valid = set(query) == {'item', 'itemId'}
            if not valid:
                if strict:
                    raise ValueError('内部结果链接无效，不能建立完整影响计划')
                continue
            found.append({'id':key[0], 'syntax':'item_link', 'token':match[0], 'attachment':None})
    return found
