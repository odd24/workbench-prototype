"""Long attachment execution entry points; outer handlers never hold IO locks."""

import uuid
from urllib.parse import urlparse

from .agent_security import AgentError, require_scope, read_json
from .agent_management import credential_lock, client_version
from .agent_attachments import AttachmentService
from .agent_attachment_execution import AttachmentExecution


def dispatch_agent(handler):
    path, _query = handler._route()
    parts = path.removeprefix('/api/agent/v1/').split('/')
    target_route = len(parts) == 3 and parts[0] == 'attachment-targets' and handler.command == 'GET'
    proposal_route = len(parts) in (2, 3) and parts[0] == 'proposals' and (handler.command == 'GET' and len(parts) == 2 or handler.command == 'POST' and len(parts) == 3 and parts[2] == 'commit')
    if not path.startswith('/api/agent/v1/') or not (target_route or proposal_route):
        return False
    request_id = str(uuid.uuid4())
    try:
        with handler.repository_switch_lock:
            repository = handler.repository
            service = getattr(repository, 'agent_service', None)
            if service is None:
                return False
            with repository.write_lock, credential_lock(service.security.config_dir):
                client = service.security.authenticate(handler.headers.get('Authorization'), handler.headers.get('X-Workbench-Workspace'))
                if proposal_route:
                    proposal = service.store.owned(client, parts[1])
                    if proposal['kind'] != 'attachment':
                        return False
                version = client_version(client)
                service.accept_request(client)
        if urlparse(handler.path).query:
            raise AgentError('unknown_parameter', '附件接口不接受查询参数')

        def guard(action):
            with handler.repository_switch_lock:
                if handler.repository is not repository or getattr(repository, 'agent_service', None) is not service:
                    raise AgentError('workspace_changed', '空间或接入状态已变化，原事务保留待查询', 409)
                with repository.write_lock, credential_lock(service.security.config_dir):
                    current = service.security.authenticate(handler.headers.get('Authorization'), handler.headers.get('X-Workbench-Workspace'))
                    if client_version(current) != version:
                        raise AgentError('authorization_changed', '授权已变化，停止发布附件', 409)
                    return action()

        require_scope(client, 'read')
        if target_route:
            result = guard(lambda:AttachmentService(service).target(client, parts[1], parts[2]))
        elif handler.command == 'POST':
            require_scope(client, 'commit')
            from .agent_http import agent_body
            payload = agent_body(handler)
            result = AttachmentExecution(service).commit(client, parts[1], payload, guard)
        else:
            result = AttachmentService(service).get_proposal(client, parts[1], guard)
        guard(lambda:None)
        handler.connection.settimeout(5)
        handler._json(result)
    except AgentError as error:
        handler._json(error.payload(request_id), error.status)
    except (ValueError, KeyError, TypeError):
        handler._json(AgentError('invalid_request', '附件请求参数或证据无效').payload(request_id), 400)
    except Exception:
        handler._json(AgentError('attachment_interrupted', '附件操作未能确认完成，请查询原提案').payload(request_id), 503)
    return True


def dispatch_management(handler, parts, origin):
    approval = len(parts) == 3 and parts[0] == 'proposals' and parts[2] == 'approve' and handler.command == 'POST'
    query = len(parts) == 2 and parts[0] == 'proposal-actions' and handler.command == 'GET'
    if not (approval or query):
        return False
    with handler.repository_switch_lock:
        repository = handler.repository
        runtime = getattr(repository, 'agent_runtime', None)
        if runtime is None or not runtime.status()['workspace_id']:
            return False
        runtime.authorize(handler.headers.get('X-Workbench-Management-Token'))
        from .agent_proposal_management import ProposalManagement
        management = ProposalManagement(runtime)
        if approval:
            proposal = management._require_store()._load(parts[1], expire=False)
        else:
            action_path = management._action_path(parts[1])
            if not action_path.exists():
                return False
            action = read_json(action_path)
            if action.get('operation') != 'approve':
                return False
            proposal = management._require_store()._load(action['proposal_id'], expire=False)
        if proposal['kind'] != 'attachment':
            return False
        active_service = getattr(repository, 'agent_service', None)
        generation = runtime._generation

    def guard(action):
        with handler.repository_switch_lock:
            if handler.repository is not repository or getattr(repository, 'agent_runtime', None) is not runtime or runtime._generation != generation or getattr(repository, 'agent_service', None) is not active_service:
                raise AgentError('workspace_changed', '空间或接入状态变化，原附件提案保留', 409)
            runtime.authorize(handler.headers.get('X-Workbench-Management-Token'))
            with repository.write_lock, credential_lock(runtime.security().config_dir):
                return action()

    if approval:
        if handler.headers.get('Origin') != origin or handler._content_length() > 65536 or handler.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            raise AgentError('forbidden', '附件批准需要同源有界JSON', 403)
        result = management.approve_attachment(parts[1], handler._body(), guard)
    else:
        result = management.attachment_action(parts[1], guard)
    guard(lambda:None)
    handler.connection.settimeout(5)
    handler._json(result)
    return True
