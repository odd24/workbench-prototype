"""Dedicated loopback staging transport. No socket IO inside business locks."""

import hashlib
import re
import socket
import time
import uuid
from contextlib import nullcontext
from urllib.parse import urlparse

from .agent_security import AgentError
from .agent_management import credential_lock, client_version
from .agent_runtime import LOOPBACK
from .agent_uploads import LIMITS


def dispatch(handler):
    request_id = str(uuid.uuid4())
    try:
        from .agent_file_handles import SUPPORTED
        if not SUPPORTED:
            raise AgentError("unsupported_platform", "暂存校验在当前平台不可用", 503)
        if handler.server.server_address[0] not in LOOPBACK or handler.client_address[0] not in LOOPBACK:
            raise AgentError("forbidden", "暂存仅支持loopback", 403)
        if len(handler.headers.get_all("Host", [])) != 1 or len(handler.headers.get_all("Origin", [])) > 1 or len(handler.headers.get_all("Authorization", [])) != 1 or len(handler.headers.get_all("X-Workbench-Workspace", [])) != 1:
            raise AgentError("invalid_headers", "暂存身份、来源或主机头重复/缺失")
        path, _query = handler._route()
        parts = path.removeprefix("/api/agent/v1/").split("/")
        if urlparse(handler.path).query:
            raise AgentError("unknown_parameter", "暂存接口不接受查询参数")
        lengths = handler.headers.get_all("Content-Length", [])
        if handler.headers.get_all("Transfer-Encoding") or len(lengths) > 1 or lengths and not re.fullmatch(r"[0-9]+", lengths[0]):
            raise AgentError("invalid_length", "拒绝传输编码和重复或非法长度")
        with handler.repository_switch_lock:
            repository = handler.repository
            service = getattr(repository, "agent_service", None)
            if not service:
                raise AgentError("disabled", "Agent接入未启用", 404)
            with repository.write_lock, credential_lock(service.security.config_dir):
                client = service.security.authenticate(handler.headers.get("Authorization"), handler.headers.get("X-Workbench-Workspace"))
                version = client_version(client)
                service.accept_request(client)
        store = service.uploads

        def checked(action):
            with handler.repository_switch_lock:
                if handler.repository is not repository or getattr(repository, "agent_service", None) is not service:
                    raise AgentError("workspace_changed", "空间或接入状态已变化，暂存未发布", 409)
                with repository.write_lock, credential_lock(service.security.config_dir):
                    current = service.security.authenticate(handler.headers.get("Authorization"), handler.headers.get("X-Workbench-Workspace"))
                    if client_version(current) != version:
                        raise AgentError("authorization_changed", "授权变化，暂存未发布", 409)
                    return action(current)

        def permit(value, publish):
            def validate(current):
                source = store.authorize(current, value)
                if publish:
                    store.publish_ready(value)
                return source
            return checked(validate)

        if parts == ["uploads"] and handler.command == "POST":
            from .agent_http import agent_body
            payload = agent_body(handler)
            result = checked(lambda current: store.create(current, payload))
        elif len(parts) == 2 and parts[0] == "uploads" and handler.command == "GET":
            result = store.get(parts[1], client, permit)
        elif len(parts) == 3 and parts[0] == "uploads" and parts[2] in {"complete", "cancel"} and handler.command == "POST":
            from .agent_http import agent_body
            if agent_body(handler) != {}:
                raise AgentError("unknown_parameter", "完成/取消只接受空JSON对象")
            result = store.complete(parts[1], permit) if parts[2] == "complete" else checked(lambda current: store.cancel(parts[1], current))
        elif len(parts) == 3 and parts[0] == "uploads" and parts[2] == "content" and handler.command == "PUT":
            handler.close_connection = True  # Extra bytes are never a next request.
            if len(lengths) != 1:
                raise AgentError("length_required", "原始流需要一个Content-Length", 411)
            length = int(lengths[0])
            if length > LIMITS["file_bytes"]:
                raise AgentError("upload_overflow", "原始流超过100MiB", 413)
            if handler.headers.get("Content-Type", "").strip().lower() != "application/octet-stream":
                raise AgentError("invalid_content_type", "仅接受application/octet-stream")
            value = store.load(parts[1])
            checked(lambda current: store.authorize(current, value))
            if value["source"] != {"mode": "stream"} or length != value["declared_bytes"]:
                raise AgentError("invalid_length", "传输来源或长度不符合会话声明")
            deadline = time.monotonic() + LIMITS["total_seconds"]
            def chunks():
                remaining = length
                while remaining:
                    budget = deadline - time.monotonic()
                    if budget <= 0:
                        raise AgentError("upload_timeout", "上传超过总时限", 408)
                    handler.connection.settimeout(min(LIMITS["socket_idle_seconds"], budget))
                    chunk = handler.rfile.read1(min(remaining, LIMITS["chunk_bytes"]))
                    if not chunk:
                        raise AgentError("upload_incomplete", "上传字节不足", 409)
                    remaining -= len(chunk)
                    yield chunk
                # Best-effort detection of already-buffered surplus. Any late
                # surplus is discarded by mandatory connection close.
                handler.connection.setblocking(False)
                try:
                    if handler.rfile.peek(1):
                        raise AgentError("upload_overflow", "上传含多余字节", 413)
                except BlockingIOError:
                    pass
                finally:
                    handler.connection.settimeout(LIMITS["socket_idle_seconds"])
            result = store.receive(parts[1], chunks(), permit)
        else:
            raise AgentError("not_found", "暂存接口不存在", 404)
        checked(lambda current: None)
        handler.connection.settimeout(5)
        handler._json(result)
    except AgentError as error:
        handler.close_connection = True
        handler._json(error.payload(request_id), error.status)
    except (TimeoutError, socket.timeout):
        handler.close_connection = True
        handler._json(AgentError("upload_timeout", "上传连接等待超时", 408).payload(request_id), 408)
    except (ValueError, TypeError, KeyError):
        handler.close_connection = True
        handler._json(AgentError("invalid_request", "暂存参数无效").payload(request_id), 400)
    except Exception:
        handler.close_connection = True
        handler._json(AgentError("upload_failed", "暂存操作失败，请查询原会话，保留恢复证据", 500).payload(request_id), 500)


def dispatch_policy(handler, parts, runtime, payload):
    from .agent_upload_policy import UploadPolicyManagement
    management = UploadPolicyManagement(runtime)
    client_id = parts[1]
    if len(parts) == 3 and handler.command == "GET":
        return management.list(client_id)
    if len(parts) == 4 and parts[3] == "preview" and handler.command == "POST":
        return management.preview(client_id, payload)
    if len(parts) == 4 and parts[3] == "confirm" and handler.command == "POST":
        if not isinstance(payload, dict) or set(payload) != {"workspace_id", "preview_id", "preview_digest", "expected_version", "request_id", "approved"} or not isinstance(payload.get("request_id"), str) or not 1 <= len(payload["request_id"]) <= 100 or payload.get("approved") is not True or payload.get("workspace_id") != management.security.workspace_id:
            raise AgentError("approval_required", "需要明确批准当前预览")
        manager = management.security.manager()
        operation_id = hashlib.sha256(payload["request_id"].encode()).hexdigest()
        if (manager.directory / (operation_id + ".json")).exists():
            return manager.run(manager._load(manager.directory / (operation_id + ".json"))["operation_family"], {"policy": None, "approval_digest": payload["preview_digest"]}, client_id, payload["expected_version"], payload["request_id"])
        return management.approve(client_id, payload)
    if len(parts) == 3 and handler.command == "DELETE":
        if not isinstance(payload, dict) or set(payload) != {"workspace_id", "expected_version", "request_id"} or payload["workspace_id"] != management.security.workspace_id:
            raise AgentError("invalid_request", "撤销策略参数无效")
        return management.security.manager().run("upload_policy_revoke", {}, client_id, payload["expected_version"], payload["request_id"])
    raise AgentError("not_found", "暂存授权管理接口不存在", 404)


def dispatch_maintenance(handler, origin):
    from .agent_uploads import UploadStore
    with handler.repository_switch_lock:
        repository = handler.repository
        runtime = getattr(repository, "agent_runtime", None)
        if not runtime or not runtime.status()["workspace_id"]:
            raise AgentError("not_initialized", "当前空间未初始化接入", 409)
        runtime.authorize(handler.headers.get("X-Workbench-Management-Token"))
        security = runtime.security()
        service = getattr(repository, "agent_service", None)
        store = UploadStore(repository, security)
    if handler.command == "GET":
        with store.quota_lock() if store.directory.exists() else nullcontext():
            from .agent_uploads import public_session
            result = {"items": [public_session(value) for value in store.catalog()]}
    elif handler.command == "POST":
        if handler.headers.get("Origin") != origin or handler._content_length() > 65536 or handler.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise AgentError("forbidden", "暂存维护需要同源有界JSON", 403)
        payload = handler._body()
        if not isinstance(payload, dict) or set(payload) != {"workspace_id", "cleanup"} or payload["workspace_id"] != security.workspace_id or type(payload["cleanup"]) is not bool:
            raise AgentError("invalid_request", "暂存维护参数无效")
        def permit(value, publish):
            with handler.repository_switch_lock:
                if handler.repository is not repository or getattr(repository, "agent_runtime", None) is not runtime or getattr(repository, "agent_service", None) is not service or service is None:
                    raise AgentError("workspace_changed", "空间或接入状态变化，不能发布ready", 409)
                runtime.authorize(handler.headers.get("X-Workbench-Management-Token"))
                with repository.write_lock, credential_lock(security.config_dir):
                    client = security.clients().get(value["client_id"])
                    if not client or not client.get("enabled") or client["client_id"] in security.manager().blocked_clients():
                        raise AgentError("forbidden", "客户端已撤销", 403)
                    grant = store.authorize(client, value)
                    if publish:
                        store.publish_ready(value)
                    return grant
        result = {"items": store.recover_and_cleanup(permit, payload["cleanup"])}
    else:
        raise AgentError("not_found", "暂存维护接口不存在", 404)
    with handler.repository_switch_lock:
        if handler.repository is not repository or getattr(repository, "agent_runtime", None) is not runtime:
            raise AgentError("workspace_changed", "空间已变化，维护结果未发布", 409)
        runtime.authorize(handler.headers.get("X-Workbench-Management-Token"))
    handler.connection.settimeout(5)
    handler._json(result)
