"""Prepare one complete, authorized project trash candidate from disk evidence."""

from dataclasses import dataclass

from .agent_delete_authorization import delete_allows
from .agent_delete_service import checked_preview
from .agent_execution import authorization_revision
from .agent_project_delete_authorization import asset_evidence, project_delete_grant
from .agent_security import AgentError
from .deletion_prepared import read_trash_index, require_platform
from .project_delete_impact import active_project_impacts
from .project_delete_tree import ProjectTree, classify_tree, read_tree
from .project_identity import controlled, read_bounded, valid_new_id
from .write_coordinator import content_revision


WARNINGS = [
    '移入回收站的是原项目整目录及全部明细中的成员。本机可恢复或永久删除，默认保留30天。',
    '项目外关联图保留原项目ID、内容和历史；项目暂不可用，恢复同一ID后可重新定位。其他正文、全局共享附件、历史及原排序保留。',
    '文本链接按既有语法识别，代码示例也可能命中。完整活动集合绑定为保守依赖，无关来源变化也可能要求重预览。',
    '仅支持本机固定NTFS。目录移动前后验证完整树；外部进程仍可修改子文件。证据不一致时保留现场，查询原操作。',
]


@dataclass(frozen=True)
class PreparedProjectDelete:
    relative_path: str
    project_id: str
    tree: ProjectTree
    index_raw: bytes
    sort_raw: bytes | None

    @property
    def before(self):
        return self.tree.raw_text['README.md']


def prepare_project_delete(repository, client, project_id, base_revision, *, held_tree=None):
    require_platform()
    try:
        valid_new_id(project_id)
    except ValueError:
        raise AgentError('not_found', '项目不存在或不可级联删除', 404) from None
    grant = project_delete_grant(client, project_id)
    if grant is None:
        raise AgentError('not_found', '项目不存在或不可级联删除', 404)
    try:
        root = repository.root
        relative = f'projects/{project_id}'
        tree = read_tree(root, root / relative) if held_tree is None else held_tree
        prepared = PreparedProjectDelete(relative, project_id, tree, *project_delete_configuration(root))
        if content_revision(prepared.before) != base_revision:
            raise AgentError('revision_conflict', '项目原始版本已变化，请重新预览', 409)
        project, records, assets, binaries = classify_tree(root, project_id, tree)
        if not all(delete_allows(client, record['item']) for record in records) or asset_evidence(assets) != grant['assets']:
            raise ValueError('项目实际子资源缺少独立授权')
        impacts, activity_digest = active_project_impacts(repository, client, project_id, records, assets, binaries, base_revision)
        sorting = {'relative_path':'config/project-sort.json', 'policy':'preserve',
                   'revision':content_revision(prepared.sort_raw) if prepared.sort_raw is not None else None}
        content = {'title':project['title'], 'project_id':project_id, 'category':None,
                   'target':{'item':project, 'raw_source':prepared.before.decode('utf-8'), 'revision':base_revision},
                   'children':records, 'standalone_assets':assets, 'tree':tree.portable_members, 'impacts':impacts,
                   'warnings':WARNINGS.copy(), 'retention':{'default_days':30, 'local_early_purge':True,
                       'attachments':'move_owned', 'history':'retain', 'ordering':'preserve'}}
        binding = {'schema_version':2, 'relative_path':relative, 'source_identity':tree.identity,
                   'source_digest':base_revision, 'tree_digest':tree.physical_digest,
                   'portable_digest':tree.portable_digest, 'child_ids':sorted(record['item']['id'] for record in records),
                   'sorting':sorting, 'trash_index_digest':content_revision(prepared.index_raw)}
        dependencies = {'schema_version':1, 'activity_digest':activity_digest, 'tree_digest':tree.physical_digest,
                        'sorting_revision':sorting['revision'], 'trash_index_digest':binding['trash_index_digest']}
        return checked_preview(content), dependencies, binding, prepared
    except AgentError as error:
        if error.code in {'revision_conflict', 'preview_too_large'}:
            raise
        raise AgentError('impact_unavailable', '无法完整授权或建立可信项目删除影响预览，请在本机核查', 409) from None
    except (KeyError, ValueError, OSError, TypeError):
        raise AgentError('impact_unavailable', '无法完整授权或建立可信项目删除影响预览，请在本机核查', 409) from None


def project_delete_configuration(root):
    index_raw, _ = read_trash_index(root)
    path = controlled(root, root / 'config/project-sort.json')
    return index_raw, read_bounded(path) if path.exists() else None


def prepare_submission(repository, client, proposal, *, held_tree=None):
    if authorization_revision(client) != proposal['authorization_revision']:
        raise AgentError('authorization_changed', '项目级联删除授权已变化，请重新预览', 409)
    content, dependencies, binding, prepared = prepare_project_delete(repository, client, proposal['target_id'],
                                                                      proposal['base_revision'], held_tree=held_tree)
    if content != proposal['normalized_content'] or dependencies != proposal['dependencies'] or binding != proposal['delete_binding']:
        raise AgentError('dependency_changed', '原项目树或完整影响集合变化，请重新预览', 409)
    return prepared
