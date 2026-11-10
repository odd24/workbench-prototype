"""Derive complete project proposals without creating business directories."""

import json

from .agent_execution import authorization_revision, fingerprint
from .agent_project_authorization import can_create_project
from .agent_project_execution import sort_summary
from .agent_security import AgentError
from .project_identity import reserved_projects, scoped_project_ids
from .project_prepared import prepare_project
from .write_coordinator import content_revision


def checked_preview(value):
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')) > 2097152:
        raise AgentError('preview_too_large', '完整项目预览超出2MiB，不能截断', 413)
    return value


class ProjectCandidateService:
    def __init__(self, repository, security):
        self.repository = repository
        self.security = security

    def normalize(self, client, content, *, proposal=None):
        from .project_directory import workspace_supported
        if not can_create_project(client):
            raise AgentError('forbidden', '需要独立项目创建授权及基本权限；只支持Windows固定NTFS', 403)
        if not workspace_supported(self.repository.root):
            raise AgentError('unsupported_volume', '当前工作空间无法验证同卷固定NTFS目录发布', 503)
        try:
            occupied = reserved_projects(self.repository, exclude_proposal=proposal['proposal_id'] if proposal else None) | scoped_project_ids(self.security)
            prepared = prepare_project(self.repository, content, occupied=occupied, project_id=proposal['target_id'] if proposal else None)
        except FileExistsError:
            raise AgentError('identity_conflict', '固定项目身份已占用，请新建提案并完整预览', 409) from None
        except (ValueError, OSError, KeyError, TypeError, AttributeError):
            raise AgentError('project_plan_unavailable', '项目字段无效或现有模板、排序、身份无法完整核验，请在本机核查', 400) from None
        meta, readme = prepared.readme()
        details = {'mode':prepared.sort_mode, 'raw_before':prepared.sort_before.decode('utf-8'), 'raw_after':prepared.sort_after.decode('utf-8'),
                   'visible_before':prepared.visible_before, 'visible_after':prepared.visible_after}
        public = {'project_id':prepared.project_id, 'title':prepared.fields['name'], 'fields':prepared.fields,
                  'metadata':meta, 'readme':readme, 'directories':list(prepared.directories),
                  'workflow':prepared.workflow, 'sorting':sort_summary(prepared.sort_mode),
                  'warnings':['批准前不创建正式项目或目录；创建和修改时间在受理本次批准时固定。',
                              'Agent 预览仅含排序规则与新项目位置；本机批准会显示完整排序前后依据。',
                              '创建不授予新项目访问权限。既有通配本身可能覆盖新项目；追加精确范围须另行在本机批准。',
                              '项目目录、排序和回执分阶段保存；中断先查询原操作，不能用新请求重建。']}
        dependencies = {'schema_version':1, 'workflow_digest':prepared.workflow_digest,
                        'collection_digest':fingerprint(sorted(prepared.projects, key=lambda item:item['id'])),
                        'sort_plan_digest':fingerprint(details), 'sort_before_digest':content_revision(prepared.sort_before),
                        'sort_after_digest':content_revision(prepared.sort_after)}
        checked_preview({'content':public, 'local_project_plan':details})
        return public, dependencies, details, prepared

    def prepare_submission(self, client, proposal):
        if authorization_revision(client) != proposal['authorization_revision']:
            raise AgentError('authorization_changed', '项目创建授权版本已改变，请重新预览', 409)
        content, deps, details, prepared = self.normalize(client, proposal['normalized_content']['fields'], proposal=proposal)
        if content != proposal['normalized_content'] or deps != proposal['dependencies'] or details != proposal['project_sort_details']:
            raise AgentError('dependency_changed', '项目模板、集合或排序已变化，请修订并重新预览', 409)
        return prepared
