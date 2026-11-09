"""Portable knowledge ZIP copies with controlled, deduplicated resources."""

import hashlib
import io
import json
import time
import zipfile
from pathlib import Path
from urllib.parse import quote, unquote

from .agent_file_handles import LocalFileHandle, SUPPORTED
from .assets import AttachmentRepository
from .document_attachments import attachment_items, safe_local_path, local_links, INTERNAL_ATTACHMENT
from .markdown_io import load_markdown, dump_markdown
from .security import validate_archive_member, validate_zip_bytes


def export_documents(domain, selected):
    root = domain.documents_dir.parent
    roots = (root / 'assets' / 'images', root / 'assets' / 'files', domain.documents_dir)
    assets, copies = {}, []

    def include(path):
        path = Path(path)
        # The owner resolver has already restricted metadata, but validate the
        # final path again and never allow arbitrary members or alias fallback.
        allowed = (*roots, *root.glob('projects/*/assets'))
        path = safe_local_path(root, path.relative_to(root).as_posix(), allowed, required=True, decode=False)
        if path not in assets:
            name = 'assets/' + hashlib.sha256(path.relative_to(root).as_posix().encode('utf-8')).hexdigest()[:24] + '-' + path.name
            assets[path] = validate_archive_member(name)
        return assets[path]

    for path in sorted(domain.documents_dir.glob('*.md')):
        if path.resolve() != path.absolute():
            raise ValueError('文档导出不接受链接文件')
        meta, body = load_markdown(path)
        if meta.get('type') != 'document' or selected and str(meta.get('id', '')) not in selected:
            continue
        meta.pop('document_type', None)
        if 'attachments' in meta:
            values = []
            for item in attachment_items(meta['attachments']):
                source = safe_local_path(path.parent, item['path'], roots[:2], required=True, decode=False)
                values.append(json.dumps({**item, 'path':include(source)}, ensure_ascii=False, separators=(',', ':')))
            meta['attachments'] = values
        replacements = []
        for match, source in local_links(body):
            local = safe_local_path(path.parent, source, roots, required=True)
            target = quote(include(local), safe='/.-_')
            fragment = match.group(1).split('#', 1)
            if len(fragment) == 2:
                target += '#' + fragment[1]
            replacements.append((match.start(1), match.end(1), target))
        for match in INTERNAL_ATTACHMENT.finditer(body):
            item_id, name = match[1].upper(), unquote(match[2], errors='strict')
            source = domain.resolve_attachment(item_id, name)
            if source is None:
                raise ValueError('引用附件缺失，不能导出不完整归档')
            item = AttachmentRepository.attachment_metadata(Path(name), include(source), Path(source).stat().st_size)
            replacements.append((match.start(), match.end(), AttachmentRepository.attachment_link(item)))
        # Unknown local HTML/reference-style targets cannot silently produce an
        # incomplete archive. Ordinary web URLs and inline formatting remain.
        import re
        if re.search(r'(?:src|href)=["\'](?!https?://|mailto:|#|data:)', body, re.I) or re.search(r'^\s*\[[^\]]+\]:\s*(?!https?://)', body, re.M):
            raise ValueError('文档含未支持的本地HTML或定义式引用，请改用正文相对链接后导出')
        for start, end, replacement in sorted(replacements, reverse=True):
            body = body[:start] + replacement + body[end:]
        copies.append((validate_archive_member(path.name), dump_markdown(meta, body)))
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, text in copies:
            archive.writestr(name, text)
        for source, name in assets.items():
            if not SUPPORTED:
                raise ValueError('当前附件归档安全读取仅支持本机Windows固定NTFS')
            with LocalFileHandle(str(source), read=True) as handle, archive.open(name, 'w', force_zip64=True) as output:
                for chunk in handle.chunks(time.monotonic() + 60):
                    output.write(chunk)
                if handle.identity() != handle.initial:
                    raise ValueError('导出时附件变化，请重新导出')
    return validate_zip_bytes(memory.getvalue())
