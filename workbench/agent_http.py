"""Versioned Agent HTTP routing; all business behavior lives in the service."""

import uuid
from urllib.parse import parse_qs, urlparse

from .agent_security import AgentError
from .agent_service import LIMITS


def dispatch(handler):
    path, _ = handler._route()
    raw_query = parse_qs(urlparse(handler.path).query, keep_blank_values=True)
    request_id = str(uuid.uuid4())
    try:
        service = getattr(handler.repository, "agent_service", None)
        if not service:
            raise AgentError("disabled", "工作台 Agent 接入未启用", 404)
        client = service.security.authenticate(handler.headers.get("Authorization"), handler.headers.get("X-Workbench-Workspace"))
        query = {key: values[0] for key, values in raw_query.items()}
        prefix = "/api/agent/v1/"
        if not path.startswith(prefix):
            raise AgentError("unsupported_version", "不支持的 Agent API 版本", 404)
        route = path[len(prefix):]
        routes = {"capabilities": (set(), lambda: service.capabilities(client)),
                  "projects": ({"limit", "cursor"}, lambda: service.projects(client, query)),
                  "catalog": ({"project_id"}, lambda: service.catalog(client, query)),
                  "search": ({"query", "kind", "project_id", "category", "limit", "cursor"}, lambda: service.search(client, query))}
        parts = route.split("/")
        if route == "proposals" and handler.command == "GET":
            allowed, action = {"limit", "cursor"}, lambda: service.list_proposals(client, query)
        elif route == "proposals" and handler.command == "POST":
            allowed, action = set(), lambda: service.prepare_proposal(client, agent_body(handler))
        elif len(parts) == 2 and parts[0] == "proposals" and handler.command == "GET":
            allowed, action = set(), lambda: service.get_proposal(client, parts[1])
        elif len(parts) == 2 and parts[0] == "proposals" and handler.command == "PATCH":
            allowed, action = set(), lambda: service.revise_proposal(client, parts[1], agent_body(handler))
        elif len(parts) == 3 and parts[0] == "proposals" and (parts[2], handler.command) in {("preview", "GET"), ("commit", "POST"), ("cancel", "POST")}:
            allowed = set()
            if parts[2] == "preview":
                action = lambda: service.preview_proposal(client, parts[1])
            elif parts[2] == "commit":
                action = lambda: service.commit_proposal(client, parts[1], agent_body(handler))
            else:
                action = lambda: service.cancel_proposal(client, parts[1], agent_body(handler))
        elif len(parts) == 3 and parts[0] == "items" and handler.command == "GET":
            allowed = {"offset", "length"}
            action = lambda: service.read_item(client, parts[1], parts[2], query)
        elif route in routes and handler.command == "GET":
            allowed, action = routes[route]
        else:
            raise AgentError("not_found", "接口不存在", 404)
        if set(query) - allowed or any(len(values) != 1 for values in raw_query.values()):
            raise AgentError("unknown_parameter", "查询参数无效或重复")
        with handler.repository.write_lock:
            service.accept_request(client)
            result = action()
        handler._json(result)
    except AgentError as error:
        handler._json(error.payload(request_id), error.status)
    except (ValueError, TypeError):
        handler._json(AgentError("invalid_request", "请求参数无效").payload(request_id), 400)
    except Exception:
        handler._json(AgentError("internal_error", "Agent 服务处理失败", 500).payload(request_id), 500)


def agent_body(handler):
    try:
        length = handler._content_length()
        if length > LIMITS["request_bytes"]:
            handler.close_connection = True
            raise AgentError("request_too_large", "请求超过 1 MiB 限制", 413)
        if handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise AgentError("invalid_content_type", "请求必须使用 application/json")
        raw = handler.rfile.read(length)
        if len(raw) != length:
            raise AgentError("incomplete_body", "请求内容不完整")
        import json
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise AgentError("invalid_body", "请求内容必须是 JSON 对象")
        return payload
    except (ValueError, UnicodeError):
        raise AgentError("invalid_json", "JSON 请求无效")
