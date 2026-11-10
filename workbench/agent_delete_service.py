"""Server-derived, complete deletion impact; never accepts replacement content."""

import html
import json

from .agent_security import AgentError, allows
from .agent_delete_authorization import delete_allows
from .agent_execution import authorization_revision
from .deletion_inventory import active_inventory, fingerprint
from .deletion_prepared import DELETE_KINDS, require_platform, source_metadata, read_trash_index
from .document_attachments import attachment_items, safe_local_path, local_links
from .write_coordinator import content_revision


WARNINGS = [
    '此操作移入回收站；默认保留30天，本机用户可以提前永久删除。Agent不具备恢复、永久删除或清空回收站能力。',
    '附件文件、共享资源和历史原样保留，不自动删除附件或改写其他正文。历史/回收站可能仍含旧引用，不计入当前活动断链来源。',
    '以下为既有语法的潜在文本引用；代码示例也可能命中，不能证明或排除任意自然语言关联。',
    '完整活动集合绑定为保守依赖；无关正式来源增删或修改也会要求重新预览。',
    '现有排序序列保留原ID和位置，不额外修改项目或分类配置；恢复位置仍受之后的用户排序操作影响。',
    '仅支持Windows本机固定NTFS普通文件；跨文件步骤不是事务，未知盘态保留现场并查询原操作，不能重建删除请求。',
]


def checked_preview(result):
    if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')) > 2097152:
        raise AgentError('preview_too_large', '完整删除预览超过2MiB，不能省略或截断内容', 413)
    return result


def access_target(kind, item):
    return {'type':kind, 'id':item['id'], 'project_id':item['id'] if kind == 'project' else item.get('project_id'), 'category':item.get('category', '未分类') if kind in {'document', 'concept_map'} else None}


def source_view(repository, entry, *, url_references=()):
    item = entry['item']
    if not isinstance(item.get('title', ''), str):
        raise ValueError('目标标题无法完整预览')
    raw = entry['raw']
    original = repository.root / entry['relative_path']
    assets = []
    roots = (repository.global_assets_dir, *repository.projects_dir.glob('*/assets'))
    for attachment in attachment_items(item.get('attachments', [])):
        path = safe_local_path(original.parent, attachment['path'], roots, decode=False)
        assets.append({'metadata':attachment, 'exists':path.is_file(), 'retained':True})
    for match, source in local_links(item.get('body', '')):
        if url_references and html.unescape(match.group(1).strip('<>')) in url_references:
            continue  # Already represented as an app URL in the impact list.
        if source:
            path = safe_local_path(original.parent, source, (*roots, repository.documents_dir))
            assets.append({'body_reference':source, 'exists':path.is_file(), 'retained':True})
    view = {'item':item, 'raw_source':raw.decode('utf-8'), 'revision':entry['revision'], 'attachments':assets}
    if entry['kind'] == 'concept_map':
        from .agent_concept_maps import validate_graph_view
        # Rendering uses a validated view only; it never writes/normalizes the source.
        graph, warnings = validate_graph_view(repository._concept_map_repository.normalize(item), base=item)
        from .agent_concept_maps import GRAPH_FIELDS
        if any(item.get(key) != graph[key] for key in GRAPH_FIELDS):
            warnings.append('只读画布采用明确兼容显示值；上方完整原始文件及全部字段为事实，本次不写回这些显示值。')
        view.update(graph=graph, graph_warnings=warnings)
    return view


class DeleteCandidateService:
    def __init__(self, repository):
        self.repository = repository

    def normalize(self, client, kind, target_id, revision, *, held_source=None):
        require_platform()
        if kind not in DELETE_KINDS or not isinstance(target_id, str):
            raise AgentError('invalid_operation', '删除仅支持四种Markdown条目及概念图')
        try:
            if held_source is not None:
                from .deletion_prepared import validate_held_source
                validate_held_source(held_source)
                if held_source.root != self.repository.root:
                    raise ValueError('删除句柄不属于当前工作空间')
            domain = self.repository
            item = source_metadata(held_source.before, target_id, kind) if held_source is not None else (domain.get_concept_map(target_id) if kind == 'concept_map' else domain.get_document(target_id) if kind == 'document' else domain.get_record(target_id))[0]
            if not item or item.get('type', 'concept_map' if kind == 'concept_map' else None) != kind:
                raise FileNotFoundError()
            target = access_target(kind, item)
            if not delete_allows(client, target):
                raise AgentError('not_found', '目标不存在或不可删除', 404)
            prepared = held_source if held_source is not None else domain.prepare_delete(kind, target_id, revision)
            if prepared.kind != kind or prepared.item_id != target_id or content_revision(prepared.before) != revision:
                raise ValueError('持有的删除对象不属于此原始版本')
            entries, inventory_digest = active_inventory(domain.root, target_id=target_id, held_source=held_source)
            source = next(entry for entry in entries if entry['id'] == target_id and entry['kind'] == kind)
            if source['relative_path'] != prepared.relative_path or source['raw'] != prepared.before:
                raise ValueError('源在准备期间变化')
            impacts = []
            for entry in entries:
                if entry['id'] == target_id or not entry['references']:
                    continue
                if entry['kind'] not in DELETE_KINDS or not allows(client, access_target(entry['kind'], entry['item'])):
                    raise ValueError('无法完整授权活动影响')
                impacts.append({'source':source_view(domain, entry), 'references':entry['references']})
            sorting_path = 'config/document-sort.json' if kind == 'document' else f"projects/{source['item']['project_id']}/README.md" if kind in {'issue', 'todo', 'info'} else None
            from .deletion_prepared import controlled
            path = controlled(domain.root, sorting_path, required=False) if sorting_path else None
            sort_raw = path.read_bytes() if path and path.exists() else None
            sorting = {'relative_path':sorting_path, 'revision':content_revision(sort_raw) if sort_raw is not None else None, 'exists':sort_raw is not None, 'policy':'preserve'}
            if sort_raw is not None and len(sort_raw) > 1048576:
                raise ValueError('排序依据超过可完整核验大小')
            content = {'title':source['item'].get('title', target_id), 'project_id':target['project_id'], 'category':target['category'],
                       'target':source_view(domain, source), 'impacts':impacts, 'warnings':WARNINGS.copy(),
                       'retention':{'default_days':30, 'local_early_purge':True, 'attachments':'retain', 'history':'retain', 'ordering':'preserve'}}
            checked_preview(content)
            index_raw, _ = read_trash_index(domain.root)
            dependencies = {'schema_version':1, 'activity_digest':inventory_digest, 'sorting_digest':fingerprint(sorting), 'trash_index_digest':content_revision(index_raw)}
            binding = {'schema_version':1, 'relative_path':prepared.relative_path, 'source_identity':prepared.source_identity,
                       'source_digest':content_revision(prepared.before), 'sorting':sorting, 'trash_index_digest':content_revision(index_raw)}
            return content, dependencies, binding, prepared
        except AgentError:
            raise
        except FileNotFoundError:
            raise AgentError('not_found', '目标不存在或不可删除', 404) from None
        except (ValueError, TypeError, KeyError, UnicodeError, OSError, StopIteration):
            raise AgentError('impact_unavailable', '无法完整授权或建立可信删除影响预览，请在本机核查后重试', 409) from None

    def prepare_submission(self, client, proposal, *, held_source=None):
        if authorization_revision(client) != proposal['authorization_revision']:
            raise AgentError('authorization_changed', '删除授权已变化，请重新完整预览', 409)
        content, dependencies, binding, prepared = self.normalize(client, proposal['kind'], proposal['target_id'], proposal['base_revision'], held_source=held_source)
        if content != proposal['normalized_content'] or dependencies != proposal['dependencies'] or binding != proposal['delete_binding']:
            raise AgentError('dependency_changed', '目标或完整影响集合变化，请修订并重新预览', 409)
        return prepared
