"""Same-origin local administration, never exposed through Agent tools."""

import uuid
import hashlib
from urllib.parse import urlparse

from .agent_security import AgentError
from .agent_runtime import AgentRuntime, LOOPBACK


PREFIX = "/api/local/agent-management/"


def dispatch(handler):
    path, query = handler._route()
    if not path.startswith(PREFIX):
        return False
    request_id = str(uuid.uuid4())
    try:
        if handler.server.server_address[0] not in LOOPBACK or handler.client_address[0] not in LOOPBACK:
            raise AgentError("forbidden", "管理接口只允许本机访问", 403)
        if handler.headers.get("Authorization") or handler.headers.get("X-Workbench-Management") != "1":
            raise AgentError("forbidden", "需要工作台管理页面请求", 403)
        origin = "http://" + handler.headers["Host"]
        if handler.headers.get("Origin", origin) != origin or handler.headers.get("Sec-Fetch-Site", "same-origin") not in {"same-origin", "none"}:
            raise AgentError("forbidden", "管理接口只允许同源访问", 403)
        if query or urlparse(handler.path).query:
            raise AgentError("invalid_request", "管理接口不接受查询参数")
        with handler.repository_switch_lock, handler.repository.write_lock:
            runtime = getattr(handler.repository, "agent_runtime", None)
            if runtime is None:
                service = getattr(handler.repository, "agent_service", None)
                runtime = AgentRuntime(handler.repository, handler.server.server_address[0], handler.server.server_address[1], service.security.config_dir.parent if service else None)
                handler.repository.agent_runtime = runtime
            route = path[len(PREFIX):]
            if handler.command == "GET" and route == "status":
                result = runtime.status(session=True)
            else:
                runtime.authorize(handler.headers.get("X-Workbench-Management-Token"))
                if handler.command != "GET" and handler.headers.get("Origin") != origin:
                    raise AgentError("forbidden", "管理写入需要同源 Origin", 403)
                payload = None
                if handler.command != "GET":
                    if handler._content_length() > 65536:
                        raise AgentError("request_too_large", "管理请求过大", 413)
                    if handler.headers.get("Content-Type", "").split(";")[0] != "application/json":
                        raise AgentError("invalid_request", "管理请求需要 JSON")
                    payload = handler._body()
                from .agent_management import AgentManagement
                management = AgentManagement(runtime)
                parts = route.split("/")
                if handler.command == "PATCH" and route == "runtime":
                    result = runtime.update(payload)
                elif handler.command == "GET" and route == "clients":
                    result = management.list_clients()
                elif handler.command == "POST" and route == "clients":
                    result = management.mutate("create", payload)
                elif len(parts) == 2 and parts[0] == "clients" and handler.command == "PATCH":
                    result = management.mutate("edit", payload, parts[1])
                elif len(parts) == 3 and parts[0] == "clients" and parts[2] == "setup" and handler.command in {"GET", "POST"}:
                    from .agent_setup import setup_instructions, registration_command
                    if handler.command == "POST" and (set(payload) != {"workspace_id", "name"} or payload["workspace_id"] != runtime.status()["workspace_id"]):
                        raise AgentError("invalid_request", "接入向导参数或工作空间无效")
                    result = setup_instructions(management._security(), parts[1], runtime.origin)
                    if handler.command == "POST":
                        result["powershell_command"] = registration_command(result, payload["name"])
                elif len(parts) == 3 and parts[0] == "clients" and parts[2] in {"rotate", "revoke", "repair"} and handler.command == "POST":
                    result = management.mutate(parts[2], payload, parts[1])
                elif handler.command == "GET" and route.startswith("operations/"):
                    key = route[len("operations/"):]
                    operation = runtime.operations.get(key)
                    if operation:
                        result = operation[1]
                    else:
                        if not runtime.status()["workspace_id"]:
                            raise AgentError("not_found", "管理操作不存在", 404)
                        manager = management._security().manager()
                        operation_id = key if len(key) == 64 else hashlib.sha256(key.encode()).hexdigest()
                        result = manager.operation(operation_id)
                else:
                    raise AgentError("not_found", "管理接口不存在", 404)
            handler._json(result)
    except AgentError as error:
        handler._json(error.payload(request_id), error.status)
    except (ValueError, TypeError, KeyError):
        handler._json(AgentError("invalid_request", "管理参数无效").payload(request_id), 400)
    except Exception:
        handler._json(AgentError("management_failed", "接入管理失败，请检查配置后重试", 500).payload(request_id), 500)
    return True
