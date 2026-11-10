"""Transport-independent, scoped workbench operations for AI Agents."""

from __future__ import annotations

import time
import re
from datetime import date
from collections import deque
from functools import wraps

from .agent_security import AgentError, allows, require_scope, client_kinds, client_confirmation_mode, client_capability_grants
from .records import matches_query
from .markdown_io import normalize_info_fields
from .agent_execution import authorization_revision


LIMITS = {"body_bytes": 256 * 1024, "title_characters": 200, "request_bytes": 1024 * 1024,
          "page_default": 20, "page_max": 100, "active_proposals": 100, "info_fields": 200, "field_name_characters": 200, "field_value_bytes": 65536, "field_note_bytes": 65536, "content_bytes": 262144}


def page(items, params):
    try:
        limit, cursor = int(params.get("limit", 20)), int(params.get("cursor", 0))
    except (ValueError, TypeError):
        raise AgentError("invalid_pagination", "分页参数无效")
    if not 1 <= limit <= 100 or cursor < 0:
        raise AgentError("invalid_pagination", "分页范围无效")
    return {"items": items[cursor:cursor + limit], "next_cursor": str(cursor + limit) if cursor + limit < len(items) else None}


def clean_item(item, body=False):
    keys = {"id", "type", "title", "project_id", "category", "status", "priority", "tags", "created", "updated", "revision", "due", "completed"}
    result = {key: value for key, value in item.items() if key in keys}
    if item.get("type") == "info":
        for key in ("status", "priority", "due", "completed"):
            result.pop(key, None)
        if body:
            result["info_fields"] = normalize_info_fields(item.get("info_fields", []), limit=None)
    if body:
        result["body"] = item.get("body", "")
    else:
        result["excerpt"] = item.get("body", "")[:300]
    return result


def service_operation(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.repository.write_lock:
            return method(self, *args, **kwargs)
    return call


class AgentService:
    def __init__(self, repository, security):
        self.repository, self.security = repository, security
        self.request_windows = {}
        self.last_cleanup_at = 0
        from .agent_proposals import ProposalStore
        if not getattr(repository, "agent_proposals", None):
            repository.agent_proposals = ProposalStore(repository)
            repository.agent_proposals.recover()
            repository.write_guard = repository.agent_proposals.guard_writes
        self.store = repository.agent_proposals
        self.store.security = security
        from .agent_uploads import UploadStore
        self.uploads = UploadStore(repository, security)

    def list_file_grants(self, client):
        from .agent_files import authorized_files, public_info
        from .agent_file_handles import SUPPORTED
        if not SUPPORTED:
            raise AgentError("unsupported_platform", "本机文件能力在当前平台不可用", 503)
        return {"items": [public_info(item) for item in authorized_files(self.security, client).values()]}

    @service_operation
    def list_concept_maps(self, client, params):
        from .agent_concept_service import GraphCandidateService
        return GraphCandidateService(self.repository).list(client, params)

    @service_operation
    def get_concept_map(self, client, key):
        from .agent_concept_service import GraphCandidateService
        return GraphCandidateService(self.repository).get(client, key)

    def get_file_info(self, client, key):
        from .agent_files import get_authorized, public_info
        return public_info(get_authorized(self.security, client, key))

    def read_file(self, client, key, params):
        from .agent_files import get_authorized, read_segment
        return read_segment(self.security, get_authorized(self.security, client, key, "text_read"), params)

    @service_operation
    def accept_request(self, client):
        now = time.monotonic()
        window = self.request_windows.setdefault(client["client_id"], deque())
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= 120:
            raise AgentError("rate_limited", "请求过于频繁，请稍后重试", 429, True)
        window.append(now)
        if now - self.last_cleanup_at >= 3600 and not self.store.blocked:
            self.store.cleanup()
            self.last_cleanup_at = now

    @service_operation
    def capabilities(self, client):
        require_scope(client, "read")
        kinds = [kind for kind in ("issue", "document", "todo", "info") if kind in client_kinds(client)]
        fields = {"issue": {"create": ["title", "body", "tags", "project_id", "status", "priority"], "update": ["title", "body", "tags", "status", "priority"], "append": ["title", "body", "tags", "project_id", "status", "priority"]},
                  "document": {"create": ["title", "body", "tags", "category"], "update": ["title", "body", "tags", "category"], "append": ["title", "body", "tags", "category"]}}
        fields["todo"] = {"create": ["title", "project_id", "body", "tags", "status", "priority", "due"],
                          "update": ["title", "body", "tags", "status", "priority", "due"], "append": ["body"]}
        fields["info"] = {"create": ["title", "project_id", "body", "tags", "info_fields"],
                          "update": ["title", "body", "tags", "info_fields"], "append": ["body"]}
        from .agent_files import authorized_files
        from .agent_file_handles import SUPPORTED
        file_grants = list(authorized_files(self.security, client).values()) if SUPPORTED else []
        from .agent_upload_policy import active_policies
        from .agent_uploads import LIMITS as UPLOAD_LIMITS
        upload_policies = active_policies(self.repository, self.security, client) if SUPPORTED else []
        attachment_policies = [policy for policy in upload_policies if policy.get('attachment_write')]
        from .agent_concept_authorization import client_graph_grants, effective_operations
        graph_grants = client_graph_grants(client)
        graph_read = 'concept_map' in client_kinds(client) and any(grant['capability'] == 'concept_maps.read' for grant in graph_grants['grants'])
        graph_operations = effective_operations(self.repository, client) if graph_read else []
        graph_write = bool(graph_operations)
        from .agent_delete_authorization import client_delete_grants, effective_kinds
        from .deletion_prepared import supported as deletion_supported
        delete_supported = deletion_supported()
        delete_grants = client_delete_grants(client)
        delete_kinds = effective_kinds(self.repository, client)
        kind_operations = {**{kind:['create', 'append', 'update'] for kind in kinds}, **({'attachment':['create']} if attachment_policies else {}), **({'concept_map':graph_operations} if graph_write else {})}
        kind_fields = {**{kind:fields[kind] for kind in kinds}, **({'concept_map':{operation:['graph'] for operation in graph_operations}} if graph_write else {})}
        for kind in delete_kinds:
            kind_operations.setdefault(kind, []).append('delete')
            kind_fields.setdefault(kind, {})['delete'] = []
        from .agent_project_authorization import can_create_project, client_project_create_grant
        from .project_prepared import PROJECT_FIELDS
        from .project_directory import workspace_supported
        project_grant = client_project_create_grant(client)
        project_create = can_create_project(client) and workspace_supported(self.repository.root)
        if project_create:
            kind_operations['project'] = ['create']
            kind_fields['project'] = {'create':list(PROJECT_FIELDS)}
        return {"kind_operations":kind_operations,
                "kind_fields":kind_fields, "authorized_kinds": client_kinds(client),
                "confirmation_modes": ["agent_attested", "local_web"], "default_confirmation_mode": client_confirmation_mode(client),
                "proposal_schema_versions": [1, 2, 3], "execution_schema_versions": [1, 2, 3, 4, 5], "api_version": "1", "workspace_id": self.security.workspace_id, "kinds": kinds + (['concept_map'] if graph_read else []),
                "operations": ["create", "append", "update"] + (['delete'] if delete_supported else []), "limits": LIMITS, "scopes": client["scopes"],
                "project_ids": client["project_ids"], "categories": client["categories"], "confirmation_mode": client_confirmation_mode(client),
                "capability_authorization": {"configured": client_capability_grants(client),
                                             "implemented": (["files.read", "uploads.stage", "attachments.write"] if SUPPORTED else []) + ['concept_maps.read', 'concept_maps.write'] + (['items.delete'] if delete_supported else []) + (['projects.create'] if SUPPORTED else []), "effective": (["files.read"] if file_grants else []) + (["uploads.stage"] if upload_policies else []) + (["attachments.write"] if attachment_policies else []) + (['concept_maps.read'] if graph_read else []) + (['concept_maps.write'] if graph_write else []) + (['items.delete'] if delete_kinds else []) + (['projects.create'] if project_create else []), "activation": "requires_reauthorization"},
                'project_creation':{'grant':project_grant, 'effective':project_create, 'confirmation_mode':'local_web', 'platform':'Windows fixed NTFS only', 'fields':list(PROJECT_FIELDS), 'grants_access':False, 'preview_bytes':2097152},
                'deletion':{'grants':delete_grants, 'effective_kinds':delete_kinds, 'confirmation_mode':'local_web', 'platform':'Windows fixed NTFS only', 'raw_file_bytes':1048576, 'preview_bytes':2097152, 'inventory_files':4096, 'inventory_bytes':33554432, 'default_retention_days':30, 'local_early_purge':True, 'agent_restore':False, 'agent_purge':False, 'attachments':'retain', 'history':'retain', 'ordering':'preserve', 'source_note':'operation delete accepts target_id/base_revision/source_note; content/path/body forbidden; full impact or generic refusal'},
                'concept_maps': {'grants':graph_grants, 'operations':graph_operations, 'graph_json_bytes':262144, 'raw_base_bytes':1048576, 'preview_bytes':2097152, 'partial_update':False, 'delete':'concept_map' in delete_kinds, 'identity':'server-reserved stable CMAP ID; canceled/expired proposals retain it; timestamps fixed at confirmation acceptance', 'authorization':'fresh explicit grants; exact read/write/resource/operation intersection; existing projects/categories only; delete requires independent delete_grants/local_web'},
                "upload_staging": {"policies": upload_policies, "limits": UPLOAD_LIMITS, "formal_attachment_write": bool(attachment_policies),
                                   "transports": ["approved_file_id", "dedicated_loopback_octet_stream"], "mcp_binary_payload": False,
                                   "authorization": "read scope, existing owner access and fresh staging policy; any client authorization or token change requires reapproval"},
                "attachment_write": {"policies":attachment_policies, "operations":["create"], "owner_kinds":["project", "issue", "todo", "info", "document"], "confirmation_required":True, "binary_download":False, "document_attachments":True},
                "file_access": {"grant_required": True, "operations": ["list_file_grants"] + (["get_file_info"] if file_grants else []) + (["read_file"] if any("text_read" in item["purposes"] for item in file_grants) else []),
                                "raw_chunk_bytes": 65536, "default_max_bytes": 10485760, "max_bytes": 104857600, "default_duration_seconds": 3600, "max_duration_seconds": 86400,
                                "verification": "each segment rehashes the full approved file; raw byte offsets; use next_offset; attachment_source grants do not permit text reads or uploads",
                                "revocation": "checked at response permit; already permitted responses may arrive after revocation", "timeout": "5 seconds checked between local synchronous reads; OS waits may exceed this"},
                "authorization_schema_versions": [1, 2, 3, 4, 5, 6, 7], "management_log_schema_versions": [1, 2, 3, 4, 5, 6, 7]}

    @service_operation
    def projects(self, client, params):
        require_scope(client, "read")
        items = [{key: item[key] for key in ("id", "name", "status", "workflow_template") if key in item}
                 for item in self.repository.list_projects() if allows(client, {"project_id": item["id"]})]
        return page(items, params)

    @service_operation
    def catalog(self, client, params):
        require_scope(client, "read")
        project_id = params.get("project_id")
        kind = params.get("kind", "issue")
        if kind not in {"issue", "document", "todo", "info"}:
            raise AgentError("invalid_kind", "不支持的条目类型")
        if kind == "document" and project_id:
            raise AgentError("invalid_request", "文档分类查询不接受项目工作流")
        if kind not in client_kinds(client) and project_id:
            raise AgentError("not_found", "项目不存在或不可访问", 404)
        tags = self.repository.list_tags()
        if client.get("authorization_schema_version") in (3, 4, 5):
            visible = [item for item in self.repository.list_records() if allows(client, item)] + [item for item in self.repository.list_documents() if allows(client, item)]
            names = {name for item in visible for name in item.get("tags", [])}
            tags = [tag for tag in tags if tag["name"] in names]
        result = {"tags": tags, "document_categories": [category for category in self.repository.document_categories()
                                         if allows(client, {"type": "document", "category": category})]}
        if project_id:
            project = self.repository.project(project_id)
            if not project or not allows(client, {"project_id": project_id}):
                raise AgentError("not_found", "项目不存在或不可访问", 404)
            if kind == "info":
                result["project_id"] = project_id
                return result
            config = self.repository.config()
            workflow = next((item for item in config["workflow_templates"] if item["id"] == project.get("workflow_template", "standard")), None)
            result.update({"project_id": project_id, "statuses": workflow["statuses"][kind] if workflow else config["status_templates"][kind],
                            "priorities": ["低", "普通", "高", "紧急"], "tags": tags})
        return result

    @service_operation
    def get_item(self, client, kind, item_id):
        require_scope(client, "read")
        if kind not in {"issue", "document", "todo", "info"}:
            raise AgentError("invalid_kind", "不支持的条目类型")
        item, path = (self.repository.get_document(item_id) if kind == "document" else self.repository.get_record(item_id))
        if not item or item.get("type") != kind or not allows(client, item):
            raise AgentError("not_found", "条目不存在或不可访问", 404)
        if kind != "document":
            self.repository._forget_record(path)
            item, path = self.repository.get_record(item_id)
        if not item or item.get("type") != kind or not allows(client, item):
            raise AgentError("not_found", "条目不存在或不可访问", 404)
        return clean_item(item, True)

    @service_operation
    def read_item(self, client, kind, item_id, params):
        item = self.get_item(client, kind, item_id)
        try:
            offset, length = int(params.get("offset", 0)), int(params.get("length", 65536))
        except (TypeError, ValueError):
            raise AgentError("invalid_range", "正文读取范围无效")
        if offset < 0 or not 1 <= length <= 65536:
            raise AgentError("invalid_range", "正文读取范围无效")
        body = item["body"]
        return {**item, "body": body[offset:offset + length], "body_offset": offset,
                "body_characters": len(body), "next_offset": offset + length if offset + length < len(body) else None}

    @service_operation
    def search(self, client, params):
        require_scope(client, "read")
        query = params.get("query", "").strip().casefold()
        if len(query) > 500:
            raise AgentError("invalid_query", "搜索词过长")
        kind = params.get("kind")
        if kind and kind not in {"issue", "document", "todo", "info"}:
            raise AgentError("invalid_kind", "不支持的条目类型")
        items = [item for item in self.repository.list_records() if item.get("type") in {"issue", "todo", "info"}] + self.repository.list_documents()
        selected = [clean_item(item) for item in items if allows(client, item)
                    and (not kind or item["type"] == kind)
                    and (not params.get("project_id") or item.get("project_id") == params["project_id"])
                    and (not params.get("category") or item.get("category") == params["category"])
                    and matches_query(item, query)]
        return page(sorted(selected, key=lambda item: (item.get("updated", ""), item["id"]), reverse=True), params)

    @service_operation
    def normalize_content(self, client, kind, operation, content, target_id=None, base_revision=None):
        require_scope(client, "read")
        if kind not in {"issue", "document", "todo", "info"} or operation not in {"create", "append", "update"}:
            raise AgentError("invalid_operation", "不支持的类型或操作")
        if kind not in client_kinds(client):
            raise AgentError("forbidden", "此客户端未获授权访问该类型", 403)
        if not isinstance(content, dict):
            raise AgentError("invalid_content", "内容必须是对象")
        fields = {"title", "body", "tags"} | ({"category"} if kind == "document" else {"project_id", "status", "priority"})
        if kind == "info":
            fields -= {"status", "priority"}
            fields.add("info_fields")
            if operation == "append" and set(content) != {"body"}:
                raise AgentError("unknown_field", "信息追加仅接受正文")
        if kind == "todo":
            fields.add("due")
            if operation == "append" and set(content) != {"body"}:
                raise AgentError("unknown_field", "待办追加仅接受正文")
        if set(content) - fields:
            raise AgentError("unknown_field", "内容包含不支持的字段")
        if operation == "create":
            if target_id is not None or base_revision is not None:
                raise AgentError("invalid_target", "新建不能指定目标 ID 或基础版本")
            base = {}
        else:
            if not isinstance(target_id, str) or not isinstance(base_revision, str):
                raise AgentError("revision_required", "更新必须指定目标和基础版本")
            base = self.get_item(client, kind, target_id)
            if base["revision"] != base_revision:
                raise AgentError("revision_conflict", "目标已变化，请读取最新版本并重新预览", 409)
            if kind != "document" and "project_id" in content and content["project_id"] != base["project_id"]:
                raise AgentError("invalid_target", "此接口不支持迁移所属项目")
        result = {key: base[key] for key in fields if key in base}
        result.update(content)
        title = result.get("title")
        body = result.get("body", "")
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > LIMITS["title_characters"] or any(ord(char) < 32 for char in title):
            raise AgentError("invalid_title", "标题不能为空、含控制字符或超过 200 字符")
        if not isinstance(body, str) or "\x00" in body:
            raise AgentError("invalid_body", "正文必须是不含空字符的文本")
        if operation == "append":
            if "body" not in content or not content["body"].strip():
                raise AgentError("invalid_body", "追加正文不能为空")
            body = base.get("body", "").rstrip() + "\n\n" + content["body"]
        if operation == "create" and not body.strip():
            body = "# " + title.strip()
        result.update(title=title.strip(), body=body.replace("\r\n", "\n").replace("\r", "\n").strip())
        if len(body.encode("utf-8")) > LIMITS["body_bytes"] or len(base.get("body", "").encode("utf-8")) > LIMITS["body_bytes"]:
            raise AgentError("content_too_large", "正文过长，无法完整预览；请缩小整理范围", 413)
        tags = result.get("tags", [])
        known_tags = {tag["name"] for tag in self.repository.list_tags()}
        if not isinstance(tags, list) or len(tags) > 100 or any(not isinstance(tag, str) or tag not in known_tags for tag in tags):
            raise AgentError("invalid_tags", "只能使用现有标签")
        result["tags"] = list(dict.fromkeys(tags))
        if kind != "document":
            project_id = result.get("project_id")
            if not isinstance(project_id, str) or not self.repository.project(project_id) or not allows(client, {"project_id": project_id}):
                raise AgentError("not_found", "项目不存在或不可访问", 404)
            if kind == "info":
                result["info_fields"] = self.validate_info_fields(result.get("info_fields", []))
            else:
                self._normalize_workflow(client, kind, result, base, operation)
        else:
            category = result.get("category", "未分类")
            if not isinstance(category, str) or category not in self.repository.document_categories() or not allows(client, {"type": "document", "category": category}):
                raise AgentError("not_found", "文档分类不存在或不可访问", 404)
            result["category"] = category
        self._validate_content_size(result, base)
        reference_text = result["body"] + "\n" + "\n".join(value for field in result.get("info_fields", []) for value in field.values())
        for referenced_id in re.findall(r"\[\[([A-Za-z]+-\d+)(?:#[^\]]*)?\]\]", reference_text):
            item = (self.repository.get_document(referenced_id) if referenced_id.startswith("DOC-") else self.repository.get_record(referenced_id))[0]
            if not item or not allows(client, item):
                raise AgentError("invalid_reference", "正文引用的条目不存在或不在授权范围内")
        return result, {key: value for key, value in base.items() if key in fields}

    def _normalize_workflow(self, client, kind, result, base, operation):
        project_id = result["project_id"]
        catalog = self.catalog(client, {"project_id": project_id, "kind": kind})
        statuses = catalog["statuses"]
        status = result.get("status", statuses[0]["name"])
        selected = next((item for item in statuses if item["name"] == status), None)
        if not selected or result.get("priority", "普通") not in catalog["priorities"]:
            raise AgentError("invalid_status", "状态或优先级不在当前配置中")
        result.update(status=status, priority=result.get("priority", "普通"), completed=bool(selected.get("completed")))
        if kind == "todo":
            due = result.get("due")
            if operation == "create" or due != base.get("due"):
                try:
                    if due is not None and (not isinstance(due, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due) or date.fromisoformat(due).isoformat() != due):
                        raise ValueError()
                except ValueError:
                    raise AgentError("invalid_due", "截止日期须为有效 YYYY-MM-DD 或 null") from None
            result["due"] = due

    @staticmethod
    def validate_info_fields(fields):
        if not isinstance(fields, list) or len(fields) > LIMITS["info_fields"]:
            raise AgentError("invalid_info_fields", "信息字段须为最多200项的有序列表")
        for field in fields:
            if not isinstance(field, dict) or not {"name", "value"} <= field.keys() or set(field) - {"name", "value", "note"}:
                raise AgentError("invalid_info_fields", "信息字段仅接受 name/value/可选 note")
            if any(not isinstance(value, str) or "\x00" in value for value in field.values()):
                raise AgentError("invalid_info_fields", "信息字段必须是不含空字符的文本")
            if not field["name"].strip() or len(field["name"]) > LIMITS["field_name_characters"] or any(ord(c) < 32 for c in field["name"]):
                raise AgentError("invalid_info_fields", "字段名称不能为空、含控制字符或超过200字符")
            if any(len(field.get(key, "").encode("utf-8")) > LIMITS["field_" + key + "_bytes"] for key in ("value", "note")):
                raise AgentError("content_too_large", "单项字段内容或说明不能超过64KiB", 413)
        return normalize_info_fields(fields)

    @staticmethod
    def _validate_content_size(content, base):
        for candidate in (content, base):
            size = len(candidate.get("body", "").encode("utf-8"))
            size += sum(len(value.encode("utf-8")) for field in candidate.get("info_fields", []) for value in field.values())
            if size > LIMITS["content_bytes"]:
                raise AgentError("content_too_large", "正文和结构字段合计过长，无法完整预览", 413)

    @service_operation
    def prepare_proposal(self, client, payload):
        require_scope(client, "propose")
        allowed = {"request_id", "operation", "kind", "target_id", "base_revision", "content", "source_note", "confirmation_mode"}
        if set(payload) - allowed or not isinstance(payload.get("request_id"), str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", payload["request_id"]):
            raise AgentError("invalid_request", "参数或 request_id 无效")
        if not isinstance(payload.get("source_note", ""), str) or len(payload.get("source_note", "")) > 1000:
            raise AgentError("invalid_source", "来源说明无效")
        if payload.get('kind') == 'project':
            from .agent_project_authorization import creation_confirmation_mode
            creation_confirmation_mode(payload.get('confirmation_mode'))
            if payload.get('operation') != 'create' or {'target_id','base_revision'} & payload.keys():
                raise AgentError('invalid_operation', '项目仅允许创建；身份由服务端固定')
        if payload.get('operation') == 'delete':
            from .agent_delete_authorization import deletion_confirmation_mode
            deletion_confirmation_mode(payload.get('confirmation_mode'))
        requested_mode = payload.get("confirmation_mode", 'local_web' if payload.get('operation') == 'delete' else client_confirmation_mode(client))
        if requested_mode not in {"agent_attested", "local_web"}:
            raise AgentError("invalid_confirmation", "确认策略无效")
        mode = "local_web" if "local_web" in {requested_mode, client_confirmation_mode(client)} else "agent_attested"
        existing = self.store.find_request(client, payload)
        if existing:
            return existing
        self.store.guard_writes()
        if payload.get('kind') == 'project':
            from .agent_project_service import ProjectCandidateService
            content, dependencies, details, _ = ProjectCandidateService(self.repository, self.security).normalize(client, payload.get('content'))
            return self.store.create(client, payload, content, {}, 'local_web', dependencies=dependencies, project_sort_details=details)
        if payload.get('operation') == 'delete':
            from .agent_delete_service import DeleteCandidateService
            if 'content' in payload:
                raise AgentError('unknown_field', '删除不接受content、替换正文或路径')
            content, dependencies, binding, _ = DeleteCandidateService(self.repository).normalize(client, payload.get('kind'), payload.get('target_id'), payload.get('base_revision'))
            return self.store.create(client, payload, content, {}, 'local_web', dependencies=dependencies, delete_binding=binding)
        if payload.get('kind') == 'concept_map':
            from .agent_concept_service import GraphCandidateService, graph_target
            from .agent_concept_authorization import graph_confirmation_mode
            from .concept_map_ids import ConceptMapIdentityError
            graphs = GraphCandidateService(self.repository)
            content, base, warnings = graphs.normalize(client, payload.get('operation'), payload.get('content'), payload.get('target_id'), payload.get('base_revision'))
            targets = [graph_target(content['graph'], payload.get('target_id'))] + ([graph_target(base, payload.get('target_id'))] if base else [])
            for target in targets:
                mode = graph_confirmation_mode(client, target, payload['operation'], mode)
            try:
                return self.store.create(client, payload, content, base, mode,
                                         dependencies=graphs.dependencies(client, payload['operation'], content, base, payload.get('target_id')), graph_warnings=warnings)
            except ConceptMapIdentityError as error:
                raise AgentError('identity_unavailable', str(error), 503) from None
        if payload.get('kind') == 'attachment':
            from .agent_attachments import AttachmentService
            attachments = AttachmentService(self)
            if payload.get('operation') != 'create':
                raise AgentError('invalid_operation', '附件只支持create')
            content = payload.get('content')
            if not isinstance(content, dict) or not isinstance(content.get('upload_id'), str):
                raise AgentError('invalid_content', '附件需要受控暂存ID')
            with self.uploads.session_lock(content['upload_id']):
                normalized, base = attachments.normalize(client, content, payload.get('target_id'), payload.get('base_revision'))
                policy = attachments.policy(client, content['owner_kind'], content['owner_id'], normalized['policy_id'])
                if policy['attachment_write']['minimum_confirmation_mode'] == 'local_web':
                    mode = 'local_web'
                result = self.store.create(client, payload, normalized, base, mode, dependencies=attachments.dependencies(client, normalized, payload['base_revision']))
                self.store.checkpoint('attachment_proposal_created')
                attachments.synchronize_binding(content['upload_id'])
                return result
        content, base = self.normalize_content(client, payload.get("kind"), payload.get("operation"), payload.get("content"), payload.get("target_id"), payload.get("base_revision"))
        return self.store.create(client, payload, content, base, mode, dependencies=self.execution_dependencies(client, payload["kind"], content))

    def execution_dependencies(self, client, kind, content):
        """Only dependencies that decide this candidate; never private config paths."""
        statuses = []
        if kind == "document":
            category = content["category"]
            owner = {"type": "document_category", "name": category, "exists": category in self.repository.document_categories()}
        else:
            project = self.repository.project(content["project_id"])
            owner = {"type": "project", "id": content["project_id"], "exists": project is not None}
            if kind != "info" and project:
                owner["workflow_template"] = project.get("workflow_template", "standard")
                catalog = self.catalog(client, {"kind": kind, "project_id": content["project_id"]})
                statuses = [{"name": value["name"], "completed": bool(value.get("completed"))} for value in catalog["statuses"]]
        known_tags = {tag["name"] for tag in self.repository.list_tags()}
        tags = [{"name": name, "exists": name in known_tags} for name in sorted(content.get("tags", []))]
        text = content["body"] + "\n" + "\n".join(value for field in content.get("info_fields", []) for value in field.values())
        references = []
        for item_id in sorted(set(re.findall(r"\[\[([A-Za-z]+-\d+)(?:#[^\]]*)?\]\]", text))):
            item = (self.repository.get_document(item_id) if item_id.startswith("DOC-") else self.repository.get_record(item_id))[0]
            if not item or not allows(client, item):
                raise AgentError("invalid_reference", "引用不存在或不可访问")
            item = self.get_item(client, item["type"], item_id)
            references.append({"kind": item["type"], "id": item_id, "revision": item["revision"]})
        return {"schema_version": 1, "owner": owner, "statuses": statuses, "tags": tags, "references": references}

    @service_operation
    def revise_proposal(self, client, proposal_id, payload):
        require_scope(client, "propose")
        if set(payload) - {"expected_version", "content", "base_revision"}:
            raise AgentError("unknown_field", "修改提案包含不支持的字段")
        proposal = self.store.owned(client, proposal_id)
        self._enforce_confirmation_policy(client, proposal)
        self.store.editable(proposal, payload.get("expected_version"))
        revision = payload.get("base_revision", proposal["base_revision"])
        if proposal['kind'] == 'project':
            from .agent_project_service import ProjectCandidateService
            if 'base_revision' in payload:
                raise AgentError('invalid_operation', '创建项目不接受基础版本')
            content, dependencies, details, _ = ProjectCandidateService(self.repository, self.security).normalize(client, payload.get('content'), proposal=proposal)
            return self.store.revise(proposal, payload['expected_version'], content, None, {}, client=client,
                                     dependencies=dependencies, project_sort_details=details)
        if proposal['operation'] == 'delete':
            from .agent_delete_service import DeleteCandidateService
            if 'content' in payload:
                raise AgentError('unknown_field', '删除修订不接受替换正文')
            content, dependencies, binding, _ = DeleteCandidateService(self.repository).normalize(client, proposal['kind'], proposal['target_id'], revision)
            return self.store.revise(proposal, payload['expected_version'], content, revision, {}, client=client, dependencies=dependencies, delete_binding=binding)
        if proposal['kind'] == 'concept_map':
            from .agent_concept_service import GraphCandidateService, graph_target
            from .agent_concept_authorization import graph_confirmation_mode
            graphs = GraphCandidateService(self.repository)
            content, base, warnings = graphs.normalize(client, proposal['operation'], payload.get('content'),
                                                      proposal['target_id'] if proposal['operation'] == 'update' else None, revision)
            mode = proposal['confirmation_mode']
            for target in [graph_target(content['graph'], proposal['target_id'])] + ([graph_target(base, proposal['target_id'])] if base else []):
                mode = graph_confirmation_mode(client, target, proposal['operation'], mode)
            proposal['confirmation_mode'] = mode
            return self.store.revise(proposal, payload['expected_version'], content, revision, base, client=client,
                                     dependencies=graphs.dependencies(client, proposal['operation'], content, base, proposal['target_id']), graph_warnings=warnings)
        if proposal['kind'] == 'attachment':
            from contextlib import ExitStack
            from .agent_attachments import AttachmentService
            attachments = AttachmentService(self)
            content = payload.get('content')
            if not isinstance(content, dict) or not isinstance(content.get('upload_id'), str):
                raise AgentError('invalid_content', '附件需要完整候选')
            old_id = proposal['normalized_content']['upload_id']
            with ExitStack() as locks:
                for key in sorted({old_id, content['upload_id']}):
                    locks.enter_context(self.uploads.session_lock(key))
                normalized, base = attachments.normalize(client, content, proposal['target_id'], revision, proposal)
                policy = attachments.policy(client, content['owner_kind'], content['owner_id'], normalized['policy_id'])
                if policy['attachment_write']['minimum_confirmation_mode'] == 'local_web':
                    proposal['confirmation_mode'] = 'local_web'
                result = self.store.revise(proposal, payload['expected_version'], normalized, revision, base, client=client, dependencies=attachments.dependencies(client, normalized, revision))
                self.store.checkpoint('attachment_proposal_revised')
                for key in {old_id, content['upload_id']}:
                    attachments.synchronize_binding(key)
                return result
        # Revisions supply the complete desired candidate, including for append.
        operation = "create" if proposal["operation"] == "create" else "update"
        content, base = self.normalize_content(client, proposal["kind"], operation, payload.get("content"), proposal["target_id"], revision)
        return self.store.revise(proposal, payload["expected_version"], content, revision, base, client=client,
                                 dependencies=self.execution_dependencies(client, proposal["kind"], content))

    @service_operation
    def preview_proposal(self, client, proposal_id):
        require_scope(client, "read")
        proposal = self.store.owned(client, proposal_id)
        self._enforce_confirmation_policy(client, proposal)
        return self.store.preview(proposal)

    def get_proposal(self, client, proposal_id):
        require_scope(client, "read")
        with self.repository.write_lock:
            proposal = self.store.owned(client, proposal_id)
        if proposal['kind'] == 'attachment':
            from .agent_attachments import AttachmentService
            return AttachmentService(self).get_proposal(client, proposal_id)
        return self._get_markdown_proposal(client, proposal_id)

    @service_operation
    def _get_markdown_proposal(self, client, proposal_id):
        require_scope(client, "read")
        self.store.recover()
        proposal = self.store.owned(client, proposal_id)
        self._enforce_confirmation_policy(client, proposal)
        result = self.store.public(proposal)
        if proposal["state"] == "committed" and proposal["kind"] != "project":
            try:
                if proposal['kind'] == 'concept_map':
                    from .agent_concept_service import authorized_graph
                    current, _, _ = authorized_graph(self.repository, client, proposal['receipt']['item_id'])
                else:
                    current = self.get_item(client, proposal["kind"], proposal["receipt"]["item_id"])
                result["current_item"] = {"exists": True, "revision": current["revision"], "changed_since_commit": current["revision"] != proposal["receipt"]["revision"]}
            except AgentError:
                result["current_item"] = {"exists": False}
        return result

    @service_operation
    def list_proposals(self, client, params):
        require_scope(client, "read")
        items = []
        for path in self.store.proposals.glob("*.json"):
            try:
                proposal = self.store.owned(client, path.stem)
            except AgentError as error:
                if error.status == 404:
                    continue
                raise
            items.append({key: proposal[key] for key in ("proposal_id", "version", "state", "kind", "operation", "target_id", "created_at", "expires_at")})
        return page(sorted(items, key=lambda item: item["created_at"], reverse=True), params)

    @service_operation
    def cancel_proposal(self, client, proposal_id, payload):
        require_scope(client, "propose")
        if set(payload) - {"expected_version"}:
            raise AgentError("unknown_field", "取消提案包含不支持的字段")
        proposal = self.store.owned(client, proposal_id)
        if proposal['kind'] == 'attachment':
            from .agent_attachments import AttachmentService
            upload_id = proposal['execution_plan']['source_bindings'][0]['upload_id']
            with self.uploads.session_lock(upload_id):
                result = self.store.cancel(proposal, payload.get('expected_version'))
                self.store.checkpoint('attachment_proposal_cancelled')
                AttachmentService(self).synchronize_binding(upload_id)
                return result
        return self.store.cancel(proposal, payload.get("expected_version"))

    def _enforce_confirmation_policy(self, client, proposal):
        if client_confirmation_mode(client) == "local_web" and proposal.get("confirmation_mode", "agent_attested") != "local_web" and proposal["state"] in {"draft", "previewed", "conflicted"}:
            schema = 3 if proposal["schema_version"] == 3 else 2
            proposal.update(schema_version=schema, digest_algorithm=f"sha256-json-v{schema}", confirmation_mode="local_web", approval=None,
                            version=proposal["version"] + 1, state="draft", previewed_version=None, preview_digest=None)
            if schema == 3:
                proposal["authorization_revision"] = authorization_revision(client)
            self.store._save(proposal)

    def commit_proposal(self, client, proposal_id, payload):
        require_scope(client, "read")
        require_scope(client, "commit")
        with self.repository.write_lock:
            proposal = self.store.owned(client, proposal_id)
        if proposal['kind'] == 'attachment':
            from .agent_attachment_execution import AttachmentExecution
            return AttachmentExecution(self).commit(client, proposal_id, payload)
        return self._commit_markdown_proposal(client, proposal_id, payload)

    @service_operation
    def _commit_markdown_proposal(self, client, proposal_id, payload):
        require_scope(client, "commit")
        require_scope(client, "read")
        if set(payload) - {"version", "preview_digest", "confirmation"}:
            raise AgentError("unknown_field", "提交只能引用已预览版本，不能携带新正文")
        self.store.recover()
        proposal = self.store.owned(client, proposal_id)
        self._enforce_confirmation_policy(client, proposal)
        if proposal.get("confirmation_mode", "agent_attested") == "local_web" and proposal["state"] != "committed":
            raise AgentError("confirmation_required", "此提案需要在本机提案管理中独立批准", 409, False, {"management_path": "/"})
        if proposal["state"] == "committed":
            return self.store.commit(proposal, payload.get("version"), payload.get("preview_digest"), payload.get("confirmation"), None)
        self.store.editable(proposal, payload.get("version"))
        prepared = self.prepare_submission(client, proposal)
        return self.store.commit(proposal, payload.get("version"), payload.get("preview_digest"), payload.get("confirmation"), prepared)

    def prepare_submission(self, client, proposal, *, held_source=None):
        require_scope(client, "read")
        require_scope(client, "propose")
        require_scope(client, "commit")
        if proposal['kind'] == 'project':
            from .agent_project_service import ProjectCandidateService
            return ProjectCandidateService(self.repository, self.security).prepare_submission(client, proposal)
        if proposal['operation'] == 'delete':
            from .agent_delete_service import DeleteCandidateService
            return DeleteCandidateService(self.repository).prepare_submission(client, proposal, held_source=held_source)
        if proposal['kind'] == 'concept_map':
            from .agent_concept_service import GraphCandidateService
            from .markdown_io import now_iso
            graphs = GraphCandidateService(self.repository)
            if authorization_revision(client) != proposal['authorization_revision']:
                raise AgentError('authorization_changed', '图授权版本变化，请修订并重新完整预览', 409)
            content, base, _ = graphs.normalize(client, proposal['operation'], proposal['normalized_content'],
                                               proposal['target_id'] if proposal['operation'] == 'update' else None, proposal['base_revision'])
            if content != proposal['normalized_content'] or base != proposal['base_content']:
                raise AgentError('proposal_conflict', '图候选或原图变化，请重新完整预览', 409)
            if graphs.dependencies(client, proposal['operation'], content, base, proposal['target_id']) != proposal['dependencies']:
                raise AgentError('dependency_changed', '图相关资源或派生集合变化，请修订并重新预览', 409)
            return graphs.prepare(proposal['operation'], content, proposal['target_id'], proposal['base_revision'], managed_time=now_iso())
        if proposal['kind'] == 'attachment':
            from .agent_attachments import AttachmentService
            return AttachmentService(self).prepare_submission(client, proposal)
        saved = proposal["normalized_content"]
        if proposal["schema_version"] == 3:
            if authorization_revision(client) != proposal["authorization_revision"]:
                raise AgentError("authorization_changed", "授权版本已变化，请修订并重新完整预览", 409)
            if self.execution_dependencies(client, proposal["kind"], saved) != proposal["dependencies"]:
                raise AgentError("dependency_changed", "相关依赖或集合已变化，请修订并重新预览", 409)
        try:
            content, _ = self.normalize_content(client, proposal["kind"], "create" if proposal["operation"] == "create" else "update", {key: value for key, value in saved.items() if key != "completed"}, proposal["target_id"], proposal["base_revision"])
        except AgentError as error:
            proposal["state"] = "conflicted"
            self.store._save(proposal)
            raise AgentError("proposal_conflict", "目标、权限或配置已变化，请重新整理并预览", 409, False, {"reason": error.code})
        if content != saved:
            raise AgentError("configuration_conflict", "当前配置会改变预览内容，请重新整理并预览", 409)
        prepared = self.repository.prepare_markdown_write(proposal["kind"], saved, proposal["target_id"], proposal["base_revision"])
        return prepared
