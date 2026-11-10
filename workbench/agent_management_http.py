"""Same-origin local administration, never exposed through Agent tools."""

import uuid
import hashlib
from urllib.parse import urlparse, parse_qs

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
        route = path[len(PREFIX):]
        params = {}
        if query or urlparse(handler.path).query:
            if handler.command != "GET" or route != "proposals":
                raise AgentError("invalid_request", "此管理接口不接受查询参数")
            raw = parse_qs(urlparse(handler.path).query, keep_blank_values=True)
            if any(len(values) != 1 for values in raw.values()):
                raise AgentError("invalid_request", "筛选参数不能重复")
            params = {key: values[0] for key, values in raw.items()}
        parts = route.split("/")
        from .agent_attachment_http import dispatch_management as dispatch_attachments
        if dispatch_attachments(handler, parts, origin):
            return True
        if route == "uploads/maintenance":
            from .agent_upload_http import dispatch_maintenance
            dispatch_maintenance(handler, origin)
            return True
        if len(parts) in (3, 4) and parts[0] == "clients" and parts[2] == "files":
            dispatch_files(handler, parts, origin)
            return True
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
                if len(parts) in (3, 4) and parts[0] == "clients" and parts[2] == "upload-policy":
                    from .agent_upload_http import dispatch_policy
                    result = dispatch_policy(handler, parts, runtime, payload)
                elif len(parts) in (3, 4) and parts[0] == 'clients' and parts[2] in {'concept-maps', 'deletions', 'project-creation', 'project-deletions', 'category-writes', 'workflow-writes'}:
                    from .agent_concept_authorization import GraphGrantManagement
                    from .agent_delete_authorization import DeleteGrantManagement
                    from .agent_project_authorization import ProjectCreateGrantManagement
                    from .agent_project_delete_authorization import ProjectDeleteGrantManagement
                    from .agent_category_management import CategoryGrantManagement
                    from .agent_workflow_management import WorkflowGrantManagement
                    grants = {'concept-maps':GraphGrantManagement, 'deletions':DeleteGrantManagement,
                              'project-creation':ProjectCreateGrantManagement, 'project-deletions':ProjectDeleteGrantManagement,
                              'category-writes':CategoryGrantManagement, 'workflow-writes':WorkflowGrantManagement}[parts[2]](runtime)
                    if len(parts) == 3 and handler.command == 'GET':
                        result = grants.list(parts[1])
                    elif len(parts) == 4 and parts[3] == 'preview' and handler.command == 'POST':
                        result = grants.preview(parts[1], payload)
                    elif len(parts) == 4 and parts[3] == 'confirm' and handler.command == 'POST':
                        result = grants.approve(parts[1], payload)
                    elif len(parts) == 3 and handler.command == 'DELETE':
                        result = grants.revoke(parts[1], payload)
                    else:
                        raise AgentError('not_found', '图授权管理接口不存在', 404)
                elif len(parts) == 4 and parts[0] == 'proposals' and parts[2] == 'project-access':
                    from .agent_project_access import ProjectAccessManagement
                    access = ProjectAccessManagement(runtime)
                    if handler.command == 'GET' and parts[3] == 'preview':
                        result = access.preview(parts[1])
                    elif handler.command == 'POST' and parts[3] == 'confirm':
                        result = access.approve(parts[1], payload)
                    else:
                        raise AgentError('not_found', '项目访问授权接口不存在', 404)
                elif parts[0] in {"proposals", "proposal-actions"}:
                    from .agent_proposal_management import ProposalManagement
                    proposals = ProposalManagement(runtime)
                    if handler.command == "GET" and len(parts) == 2 and parts[0] == "proposal-actions":
                        result = proposals.action(parts[1])
                    elif parts[0] == "proposals" and handler.command == "GET" and len(parts) == 1:
                        result = proposals.list(params)
                    elif parts[0] == "proposals" and handler.command == "GET" and len(parts) == 2:
                        result = proposals.detail(parts[1])
                    elif parts[0] == "proposals" and handler.command == "GET" and len(parts) == 3 and parts[2] == "preview":
                        result = proposals.preview(parts[1])
                    elif parts[0] == "proposals" and handler.command == "POST" and len(parts) == 3 and parts[2] == "approve":
                        result = proposals.approve(parts[1], payload)
                    elif parts[0] == "proposals" and handler.command == "POST" and len(parts) == 3 and parts[2] == "cancel":
                        result = proposals.cancel(parts[1], payload)
                    else:
                        raise AgentError("not_found", "提案管理接口不存在", 404)
                elif handler.command == "PATCH" and route == "runtime":
                    result = runtime.update(payload)
                elif handler.command == "POST" and route == "diagnostics":
                    if set(payload) != {"workspace_id", "client_id", "request_id"} or payload["workspace_id"] != runtime.status()["workspace_id"]:
                        raise AgentError("invalid_request", "诊断参数或工作空间无效")
                    result = runtime.diagnostics.start(payload["client_id"], payload["request_id"])
                elif handler.command == "GET" and len(parts) == 2 and parts[0] == "diagnostics":
                    result = runtime.diagnostics.get(parts[1])
                elif len(parts) == 3 and parts[0] == "clients" and parts[2] in {"registration-preview", "registration"} and handler.command == "POST":
                    from .agent_registration import CodexRegistration
                    registration = CodexRegistration(runtime, management._security())
                    result = registration.preview(parts[1], payload) if parts[2] == "registration-preview" else registration.register(parts[1], payload)
                elif len(parts) == 2 and parts[0] == "registrations" and handler.command == "GET":
                    from .agent_registration import CodexRegistration
                    result = CodexRegistration(runtime, management._security()).get(parts[1])
                elif handler.command == "GET" and route == "clients":
                    result = management.list_clients()
                elif handler.command == "POST" and route == "clients":
                    result = management.mutate("create", payload)
                elif len(parts) == 2 and parts[0] == "clients" and handler.command == "PATCH":
                    result = management.mutate("edit", payload, parts[1])
                elif len(parts) == 3 and parts[0] == "clients" and parts[2] == "setup" and handler.command in {"GET", "POST"}:
                    from .agent_setup import setup_instructions, registration_command, command_variants
                    if handler.command == "POST" and (not {"workspace_id", "name"} <= payload.keys() or set(payload) - {"workspace_id", "name", "terminal"} or payload["workspace_id"] != runtime.status()["workspace_id"]):
                        raise AgentError("invalid_request", "接入向导参数或工作空间无效")
                    result = setup_instructions(management._security(), parts[1], runtime.origin)
                    if handler.command == "POST":
                        terminal = payload.get("terminal", "powershell")
                        result["registration_command"] = registration_command(result, payload["name"], terminal)
                        result["terminal"] = terminal
                        command_variants(result, payload["name"])
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


def dispatch_files(handler, parts, origin):
    from .agent_files import FileManagement
    from .agent_management import credential_lock
    with handler.repository_switch_lock:
        repository = handler.repository
        runtime = getattr(repository, "agent_runtime", None)
        if not runtime or not runtime.status()["workspace_id"]:
            raise AgentError("not_initialized", "请先开启接入", 409)
        runtime.authorize(handler.headers.get("X-Workbench-Management-Token"))
        generation = runtime._generation
        if handler.command != "GET" and handler.headers.get("Origin") != origin:
            raise AgentError("forbidden", "管理写入需要同源Origin", 403)
        management = FileManagement(runtime)
    payload = None
    if handler.command != "GET":
        if handler._content_length() > 65536 or handler.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise AgentError("invalid_request", "文件管理请求需要有界JSON")
        payload = handler._body()
    client_id = parts[1]
    if len(parts) == 3 and handler.command == "GET":
        with repository.write_lock, credential_lock(management.security.config_dir):
            result = management.list(client_id)
    elif len(parts) == 4 and parts[3] == "preview" and handler.command == "POST":
        result = management.preview(client_id, payload)
    elif len(parts) == 4 and parts[3] == "confirm" and handler.command == "POST":
        if not isinstance(payload, dict) or set(payload) != {"workspace_id", "preview_id", "preview_digest", "expected_version", "request_id", "approved"} or payload["approved"] is not True or payload["workspace_id"] != management.security.workspace_id or not isinstance(payload["request_id"], str) or not 1 <= len(payload["request_id"]) <= 100:
            raise AgentError("approval_required", "需要明确批准当前完整预览")
        manager = management.security.manager()
        operation_id = hashlib.sha256(payload["request_id"].encode()).hexdigest()
        with credential_lock(management.security.config_dir):
            replay = (manager.directory / f"{operation_id}.json").exists()
            if replay:
                result = manager.run("file_grant_create", {"record": None, "approval_digest": payload["preview_digest"]}, client_id, payload["expected_version"], payload["request_id"])
        if not replay:
            record = management.approved_record(client_id, payload)  # Hash only after approval, unlocked.
            with handler.repository_switch_lock:
                if handler.repository is not repository or getattr(repository, "agent_runtime", None) is not runtime or runtime._generation != generation:
                    raise AgentError("workspace_changed", "工作空间已变化，授权未发布", 409)
                runtime.authorize(handler.headers.get("X-Workbench-Management-Token"))
                with repository.write_lock:
                    result = management.commit(client_id, payload, record)
    elif len(parts) == 4 and handler.command == "DELETE":
        if not isinstance(payload, dict) or set(payload) != {"workspace_id", "expected_version", "request_id"} or payload["workspace_id"] != management.security.workspace_id:
            raise AgentError("invalid_request", "撤销文件授权参数无效")
        with handler.repository_switch_lock:
            if handler.repository is not repository:
                raise AgentError("workspace_changed", "工作空间已变化", 409)
            with repository.write_lock:
                result = management.security.manager().run("file_grant_revoke", {"file_id": parts[3]}, client_id, payload["expected_version"], payload["request_id"])
    else:
        raise AgentError("not_found", "文件管理接口不存在", 404)
    with handler.repository_switch_lock:
        if handler.repository is not repository or getattr(repository, "agent_runtime", None) is not runtime or runtime._generation != generation:
            raise AgentError("workspace_changed", "工作空间已变化，管理结果未发布", 409)
        runtime.authorize(handler.headers.get("X-Workbench-Management-Token"))
    handler.connection.settimeout(5)
    handler._json(result)
