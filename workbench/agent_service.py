"""Transport-independent, scoped workbench operations for AI Agents."""

from __future__ import annotations

import time
from collections import deque

from .agent_security import AgentError, allows, require_scope
from .write_coordinator import file_revision


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


class AgentService:
    def __init__(self, repository, security):
        self.repository, self.security = repository, security
        self.request_windows = {}

    def accept_request(self, client):
        now = time.monotonic()
        window = self.request_windows.setdefault(client["client_id"], deque())
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= 120:
            raise AgentError("rate_limited", "请求过于频繁，请稍后重试", 429, True)
        window.append(now)

    def capabilities(self, client):
        require_scope(client, "read")
        return {"api_version": "1", "workspace_id": self.security.workspace_id, "kinds": ["issue", "document"],
                "operations": [], "limits": LIMITS, "scopes": client["scopes"],
                "project_ids": client["project_ids"], "categories": client["categories"], "confirmation_mode": "agent_attested"}

    def projects(self, client, params):
        require_scope(client, "read")
        items = [{key: item[key] for key in ("id", "name", "status", "workflow_template") if key in item}
                 for item in self.repository.list_projects() if allows(client, {"project_id": item["id"]})]
        return page(items, params)

    def catalog(self, client, params):
        require_scope(client, "read")
        project_id = params.get("project_id")
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
        return {**clean_item(item, True), "revision": file_revision(path)}

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
                    and (not query or query in " ".join(str(item.get(key, "")) for key in ("title", "body", "tags", "status")).casefold())]
        return page(sorted(selected, key=lambda item: (item.get("updated", ""), item["id"]), reverse=True), params)
