"""Transport-independent, scoped workbench operations for AI Agents."""

from __future__ import annotations

import time
import re
from collections import deque
from functools import wraps

from .agent_security import AgentError, allows, require_scope, client_kinds
from .records import matches_query


LIMITS = {"body_bytes": 256 * 1024, "title_characters": 200, "request_bytes": 1024 * 1024,
          "page_default": 20, "page_max": 100, "active_proposals": 100}


def page(items, params):
    try:
        limit, cursor = int(params.get("limit", 20)), int(params.get("cursor", 0))
    except (ValueError, TypeError):
        raise AgentError("invalid_pagination", "分页参数无效")
    if not 1 <= limit <= 100 or cursor < 0:
        raise AgentError("invalid_pagination", "分页范围无效")
    return {"items": items[cursor:cursor + limit], "next_cursor": str(cursor + limit) if cursor + limit < len(items) else None}


def clean_item(item, body=False):
    keys = {"id", "type", "title", "project_id", "category", "status", "priority", "tags", "created", "updated", "revision"}
    result = {key: value for key, value in item.items() if key in keys}
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
        kinds = [kind for kind in ("issue", "document") if kind in client_kinds(client)]
        fields = {"issue": {"create": ["title", "body", "tags", "project_id", "status", "priority"], "update": ["title", "body", "tags", "status", "priority"], "append": ["title", "body", "tags", "project_id", "status", "priority"]},
                  "document": {"create": ["title", "body", "tags", "category"], "update": ["title", "body", "tags", "category"], "append": ["title", "body", "tags", "category"]}}
        return {"kind_operations": {kind: ["create", "append", "update"] for kind in kinds},
                "kind_fields": {kind: fields[kind] for kind in kinds}, "authorized_kinds": client_kinds(client),
                "confirmation_modes": ["agent_attested"], "default_confirmation_mode": "agent_attested",
                "proposal_schema_versions": [1, 2], "api_version": "1", "workspace_id": self.security.workspace_id, "kinds": kinds,
                "operations": ["create", "append", "update"], "limits": LIMITS, "scopes": client["scopes"],
                "project_ids": client["project_ids"], "categories": client["categories"], "confirmation_mode": "agent_attested"}

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
        if kind not in {"issue", "document"}:
            raise AgentError("invalid_kind", "不支持的条目类型")
        if kind not in client_kinds(client) and project_id:
            raise AgentError("not_found", "项目不存在或不可访问", 404)
        result = {"tags": self.repository.list_tags(), "document_categories": [category for category in self.repository.document_categories()
                                         if allows(client, {"type": "document", "category": category})]}
        if project_id:
            project = self.repository.project(project_id)
            if not project or not allows(client, {"project_id": project_id}):
                raise AgentError("not_found", "项目不存在或不可访问", 404)
            config = self.repository.config()
            workflow = next((item for item in config["workflow_templates"] if item["id"] == project.get("workflow_template", "standard")), None)
            result.update({"project_id": project_id, "statuses": workflow["statuses"]["issue"] if workflow else config["status_templates"]["issue"],
                           "priorities": ["低", "普通", "高", "紧急"], "tags": self.repository.list_tags()})
        return result

    @service_operation
    def get_item(self, client, kind, item_id):
        require_scope(client, "read")
        if kind not in {"issue", "document"}:
            raise AgentError("invalid_kind", "不支持的条目类型")
        item, path = (self.repository.get_document(item_id) if kind == "document" else self.repository.get_record(item_id))
        if not item or item.get("type") != kind or not allows(client, item):
            raise AgentError("not_found", "条目不存在或不可访问", 404)
        if kind == "issue":
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
        if kind and kind not in {"issue", "document"}:
            raise AgentError("invalid_kind", "不支持的条目类型")
        items = self.repository.list_records(record_type="issue") + self.repository.list_documents()
        selected = [clean_item(item) for item in items if allows(client, item)
                    and (not kind or item["type"] == kind)
                    and (not params.get("project_id") or item.get("project_id") == params["project_id"])
                    and (not params.get("category") or item.get("category") == params["category"])
                    and matches_query(item, query)]
        return page(sorted(selected, key=lambda item: (item.get("updated", ""), item["id"]), reverse=True), params)

    @service_operation
    def normalize_content(self, client, kind, operation, content, target_id=None, base_revision=None):
        require_scope(client, "read")
        if kind not in {"issue", "document"} or operation not in {"create", "append", "update"}:
            raise AgentError("invalid_operation", "不支持的类型或操作")
        if kind not in client_kinds(client):
            raise AgentError("forbidden", "此客户端未获授权访问该类型", 403)
        if not isinstance(content, dict):
            raise AgentError("invalid_content", "内容必须是对象")
        fields = {"title", "body", "tags"} | ({"project_id", "status", "priority"} if kind == "issue" else {"category"})
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
            if kind == "issue" and "project_id" in content and content["project_id"] != base["project_id"]:
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
        if kind == "issue":
            project_id = result.get("project_id")
            if not isinstance(project_id, str) or not self.repository.project(project_id) or not allows(client, {"project_id": project_id}):
                raise AgentError("not_found", "项目不存在或不可访问", 404)
            catalog = self.catalog(client, {"project_id": project_id})
            statuses = catalog["statuses"]
            status = result.get("status", statuses[0]["name"])
            selected = next((item for item in statuses if item["name"] == status), None)
            if not selected or result.get("priority", "普通") not in catalog["priorities"]:
                raise AgentError("invalid_status", "状态或优先级不在当前配置中")
            result.update(status=status, priority=result.get("priority", "普通"), completed=bool(selected.get("completed")))
        else:
            category = result.get("category", "未分类")
            if not isinstance(category, str) or category not in self.repository.document_categories() or not allows(client, {"type": "document", "category": category}):
                raise AgentError("not_found", "文档分类不存在或不可访问", 404)
            result["category"] = category
        for referenced_id in re.findall(r"\[\[([A-Za-z]+-\d+)(?:#[^\]]*)?\]\]", result["body"]):
            item = (self.repository.get_document(referenced_id) if referenced_id.startswith("DOC-") else self.repository.get_record(referenced_id))[0]
            if not item or not allows(client, item):
                raise AgentError("invalid_reference", "正文引用的条目不存在或不在授权范围内")
        return result, {key: value for key, value in base.items() if key in fields}

    @service_operation
    def prepare_proposal(self, client, payload):
        require_scope(client, "propose")
        allowed = {"request_id", "operation", "kind", "target_id", "base_revision", "content", "source_note"}
        if set(payload) - allowed or not isinstance(payload.get("request_id"), str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", payload["request_id"]):
            raise AgentError("invalid_request", "参数或 request_id 无效")
        if not isinstance(payload.get("source_note", ""), str) or len(payload.get("source_note", "")) > 1000:
            raise AgentError("invalid_source", "来源说明无效")
        existing = self.store.find_request(client, payload)
        if existing:
            return existing
        self.store.guard_writes()
        content, base = self.normalize_content(client, payload.get("kind"), payload.get("operation"), payload.get("content"), payload.get("target_id"), payload.get("base_revision"))
        return self.store.create(client, payload, content, base)

    @service_operation
    def revise_proposal(self, client, proposal_id, payload):
        require_scope(client, "propose")
        if set(payload) - {"expected_version", "content", "base_revision"}:
            raise AgentError("unknown_field", "修改提案包含不支持的字段")
        proposal = self.store.owned(client, proposal_id)
        self.store.editable(proposal, payload.get("expected_version"))
        revision = payload.get("base_revision", proposal["base_revision"])
        # Revisions supply the complete desired candidate, including for append.
        operation = "create" if proposal["operation"] == "create" else "update"
        content, base = self.normalize_content(client, proposal["kind"], operation, payload.get("content"), proposal["target_id"], revision)
        return self.store.revise(proposal, payload["expected_version"], content, revision, base)

    @service_operation
    def preview_proposal(self, client, proposal_id):
        require_scope(client, "read")
        return self.store.preview(self.store.owned(client, proposal_id))

    @service_operation
    def get_proposal(self, client, proposal_id):
        require_scope(client, "read")
        self.store.recover()
        proposal = self.store.owned(client, proposal_id)
        result = self.store.public(proposal)
        if proposal["state"] == "committed":
            try:
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
        return self.store.cancel(self.store.owned(client, proposal_id), payload.get("expected_version"))

    @service_operation
    def commit_proposal(self, client, proposal_id, payload):
        require_scope(client, "commit")
        require_scope(client, "read")
        if set(payload) - {"version", "preview_digest", "confirmation"}:
            raise AgentError("unknown_field", "提交只能引用已预览版本，不能携带新正文")
        self.store.recover()
        proposal = self.store.owned(client, proposal_id)
        if proposal["state"] == "committed":
            return self.store.commit(proposal, payload.get("version"), payload.get("preview_digest"), payload.get("confirmation"), None)
        self.store.editable(proposal, payload.get("version"))
        saved = proposal["normalized_content"]
        try:
            content, _ = self.normalize_content(client, proposal["kind"], "create" if proposal["operation"] == "create" else "update", {key: value for key, value in saved.items() if key != "completed"}, proposal["target_id"], proposal["base_revision"])
        except AgentError as error:
            proposal["state"] = "conflicted"
            self.store._save(proposal)
            raise AgentError("proposal_conflict", "目标、权限或配置已变化，请重新整理并预览", 409, False, {"reason": error.code})
        if content != saved:
            raise AgentError("configuration_conflict", "当前配置会改变预览内容，请重新整理并预览", 409)
        prepared = self.repository.prepare_markdown_write(proposal["kind"], saved, proposal["target_id"], proposal["base_revision"])
        return self.store.commit(proposal, payload.get("version"), payload.get("preview_digest"), payload.get("confirmation"), prepared)
