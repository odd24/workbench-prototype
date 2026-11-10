"""Graph candidates use the existing concept-map domain and explicit grants."""

import re

from .agent_security import AgentError, require_scope
from .agent_concept_maps import validate_graph, read_graph, GRAPH_FIELDS, NODE_FIELDS, EDGE_FIELDS, controlled_graph_path, graph_catalog, json_bytes, GRAPH_BYTES
from .agent_concept_authorization import graph_allows, matching_graph_grants, normalize_graph_grants, grant_dependencies


SERVICE_TIME = '（服务端受理本次确认时生成）'


def graph_target(graph, map_id=None):
    return {'type': 'concept_map', 'id': map_id, 'project_id': graph.get('project_id'), 'category': graph.get('category', '未分类')}


def ownership(graph):
    return (graph.get('project_id'), graph.get('category', '未分类') if graph.get('project_id') is None else None)


def authorized_graph(repository, client, key):
    from .agent_concept_authorization import client_graph_grants
    if not any(grant['capability'] == 'concept_maps.read' for grant in client_graph_grants(client)['grants']):
        raise AgentError('not_found', '概念图不存在或不可访问', 404)
    try:
        item, path, raw = read_graph(repository.root, key)
    except AgentError:
        if graph_allows(client, {'type': 'concept_map', 'id': key, 'project_id': None, 'category': None}):
            raise
        raise AgentError('not_found', '概念图不存在或不可访问', 404) from None
    if not graph_allows(client, graph_target(item, key)):
        raise AgentError('not_found', '概念图不存在或不可访问', 404)
    return item, path, raw


class GraphCandidateService:
    def __init__(self, repository):
        self.repository = repository
        self.domain = repository._concept_map_repository

    def list(self, client, params):
        from .agent_service import page
        require_scope(client, 'read')
        if set(params) - {'limit', 'cursor', 'project_id', 'category', 'query'}:
            raise AgentError('unknown_parameter', '图查询包含不支持字段')
        query = params.get('query', '')
        if not isinstance(query, str) or len(query) > 500:
            raise AgentError('invalid_query', '图查询文字无效')
        items = [item for item in graph_catalog(self.repository.root)
                 if graph_allows(client, {**item, 'type': 'concept_map'})
                 and (not params.get('project_id') or item['project_id'] == params['project_id'])
                 and (not params.get('category') or item['category'] == params['category'])
                 and query.casefold() in str(item['title']).casefold()]
        return page(items, params)

    def get(self, client, key):
        require_scope(client, 'read')
        item, _, _ = authorized_graph(self.repository, client, key)
        stored = {name: value for name, value in item.items() if name != 'revision'}
        if len(json_bytes(stored)) > GRAPH_BYTES:
            raise AgentError('content_too_large', '完整图JSON数据超过256KiB，不能截断读取或更新', 413)
        warnings, editable = [], None
        try:
            editable, warnings = validate_graph(self.domain.normalize(stored), base=stored)
            if any(stored.get(field) != editable[field] for field in GRAPH_FIELDS):
                warnings.append('兼容归一化编辑候选与原始图不同；原始图完整保留在graph，保存前须核对全部差异。')
        except (ValueError, AgentError, TypeError):
            warnings.append('原图无法安全转换为完整编辑候选，请先在本机检查修复；不自动截断或重新编号。')
        return {'id': key, 'revision': item['revision'], 'graph': stored, 'editable_graph': editable, 'warnings': warnings}

    def normalize(self, client, operation, content, target_id=None, base_revision=None):
        require_scope(client, 'read')
        require_scope(client, 'propose')
        if operation not in {'create', 'update'}:
            raise AgentError('invalid_operation', '概念图仅支持完整create/update候选')
        if not isinstance(content, dict) or set(content) != {'graph'}:
            raise AgentError('invalid_content', '概念图需要完整content.graph，不接受服务器身份、时间或局部patch')
        base = {}
        if operation == 'create':
            if target_id is not None or base_revision is not None:
                raise AgentError('invalid_request', '新图身份由提案持久预留，不接受外部指定')
        else:
            if not isinstance(target_id, str) or not re.fullmatch(r'CMAP-[0-9]+', target_id):
                raise AgentError('invalid_request', '更新图必须指定已有稳定ID')
            item, _, _ = authorized_graph(self.repository, client, target_id)
            base = {key: value for key, value in item.items() if key != 'revision'}
            source = graph_target(base, target_id)
            if (source['project_id'] is not None and (not isinstance(source['project_id'], str) or not source['project_id'] or len(source['project_id']) > 80)) or not isinstance(source['category'], str) or not source['category'] or len(source['category']) > 200:
                raise AgentError('legacy_metadata_invalid', '原图归属字段不能安全表达，请先在本机检查修复')
            if not graph_allows(client, graph_target(base, target_id), 'update'):
                raise AgentError('not_found', '概念图不存在或不可访问', 404)
            if not isinstance(base_revision, str) or not re.fullmatch(r'[a-f0-9]{64}', base_revision):
                raise AgentError('invalid_revision', '更新图必须指定完整原始字节revision')
            if item['revision'] != base_revision:
                raise AgentError('revision_conflict', '概念图已变化，请重新完整读取并预览', 409)
        graph, warnings = validate_graph(content['graph'], base=base if base else None, create=operation == 'create')
        target = graph_target(graph, target_id)
        destination = bool(base and ownership(base) != ownership(graph))
        if not graph_allows(client, target, operation, destination=destination):
            raise AgentError('not_found', '图候选的目标范围不存在或不可访问', 404)
        # Existing categories/projects only: creating configuration is AG-139.
        if graph['category'] not in self.domain.categories():
            raise AgentError('invalid_category', '图分类不存在，请先在本机建立分类')
        if graph['project_id'] is not None:
            from .markdown_io import load_markdown_text
            path = controlled_graph_path(self.repository.root, f"projects/{graph['project_id']}/README.md")
            if not path.is_file():
                raise AgentError('not_found', '图所属项目不存在或不可访问', 404)
            metadata, _ = load_markdown_text(path.read_text(encoding='utf-8'))
            if metadata.get('id') != graph['project_id'] or metadata.get('type') != 'project':
                raise AgentError('resource_changed', '图所属项目身份变化，请重新预览', 409)
        for collection, fields in (('nodes', NODE_FIELDS), ('edges', EDGE_FIELDS)):
            for item in base.get(collection, []):
                unknown = sorted(set(item) - fields)
                if unknown:
                    warnings.append(f"原图{collection}/{item['id']}的额外字段将在完整替换后移除：{'、'.join(unknown)}。请核对完整原图及差异。")
        return {'graph': graph}, base, warnings

    def dependencies(self, client, operation, content, base, target_id=None):
        targets = [graph_target(content['graph'], target_id)]
        if base:
            targets.append(graph_target(base, target_id))
        selected = []
        for target in targets:
            for action in ('read', operation):
                for grant in matching_graph_grants(client, target, action):
                    if grant not in selected:
                        selected.append(grant)
        grants = normalize_graph_grants({'schema_version': 1, 'grants': selected})
        return {'schema_version': 1, 'resource_grants': grants, 'resources': grant_dependencies(self.repository, grants)}

    def prepare(self, operation, content, target_id, base_revision, *, managed_time=SERVICE_TIME):
        graph = content['graph']
        controlled_graph_path(self.repository.root, f'concept-maps/{target_id}.json')
        try:
            if operation == 'create':
                return self.domain.prepare_create(graph, target_id, managed_time=managed_time, default_node=False)
            return self.domain.prepare_update(target_id, {**graph, 'expected_revision': base_revision}, managed_time=managed_time)
        except (FileExistsError, FileNotFoundError):
            raise AgentError('revision_conflict', '图固定身份或原始版本变化，请重新读取并预览；不能改名或覆盖', 409) from None
