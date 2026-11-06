"""Local-session proposal review; never part of the MCP tool surface."""
from __future__ import annotations

import hashlib
import re
import secrets
import time

from .agent_proposals import ProposalStore, digest, stamp
from .agent_management import client_version, credential_lock
from .agent_security import AgentError, allows, read_json
from .agent_service import page, service_operation, AgentService
from .persistence import atomic_write_json

STATES = {"draft", "previewed", "committing", "committed", "conflicted", "cancelled", "expired", "recovery_required"}


class ProposalManagement:
    def __init__(self, runtime):
        self.runtime = runtime
        self.repository = runtime.repository
        self.workspace_id = runtime.status()["workspace_id"]
        self.store = getattr(self.repository, "agent_proposals", None)
        if self.workspace_id and self.store is None:
            self.store = ProposalStore(self.repository)
            self.repository.agent_proposals = self.store
        self.directory = self.repository.root / ".agent" / "proposal-actions"
        if self.directory.is_symlink() or not self.directory.resolve().is_relative_to(self.repository.root):
            raise AgentError("unsafe_state_path", "提案操作目录无效", 503)

    def _require_store(self):
        if not self.store:
            raise AgentError("not_found", "当前空间暂无提案", 404)
        return self.store

    def _clients(self):
        if not self.workspace_id:
            return {}
        return self.runtime.security().clients()

    def _summary(self, proposal, clients):
        result = {key: proposal.get(key) for key in ("proposal_id", "client_id", "version", "state", "kind", "operation", "target_id", "created_at", "expires_at", "finished_at", "content_cleaned")}
        result.update(client_name=clients.get(proposal["client_id"], {}).get("name", "已移除客户端"),
                      title=proposal.get("normalized_content", {}).get("title", proposal.get("receipt", {}).get("title", "正文已清理")),
                      access_target=proposal["access_target"], receipt=proposal.get("receipt"))
        return result

    @service_operation
    def list(self, params):
        if set(params) - {"limit", "cursor", "client_id", "kind", "state", "operation"}:
            raise AgentError("unknown_parameter", "提案筛选参数无效")
        if params.get("kind") and params["kind"] not in {"issue", "todo", "info", "document"} or params.get("state") and params["state"] not in STATES or params.get("operation") and params["operation"] not in {"create", "append", "update"}:
            raise AgentError("invalid_filter", "提案筛选值无效")
        clients = self._clients()
        items = []
        if self.store:
            for path in self.store.proposals.glob("*.json"):
                proposal = self.store._load(path.stem)
                if all(not params.get(key) or proposal.get(key) == params[key] for key in ("client_id", "kind", "state", "operation")):
                    items.append(self._summary(proposal, clients))
        return {**page(sorted(items, key=lambda item: (item["created_at"], item["proposal_id"]), reverse=True), params),
                "workspace_id": self.workspace_id, "clients": [{"client_id": key, "name": value["name"]} for key, value in clients.items()]}

    @service_operation
    def detail(self, proposal_id):
        proposal = self._require_store()._load(proposal_id)
        clients = self._clients()
        client = clients.get(proposal["client_id"])
        authorized = bool(client and client.get("enabled") and {"read", "propose", "commit"} <= set(client.get("scopes", [])) and allows(client, proposal["access_target"]))
        if authorized:
            authorized = client["client_id"] not in self.runtime.security().manager().blocked_clients()
        return {**self._summary(proposal, clients), "authorization_available": authorized,
                "confirmation_mode": proposal.get("confirmation_mode", "agent_attested"),
                "preview_digest": proposal.get("preview_digest"), "source_note": proposal.get("source_note", ""),
                "recovery_in_progress": proposal["state"] in {"committing", "recovery_required"},
                "workspace_id": self.workspace_id}

    @service_operation
    def preview(self, proposal_id):
        proposal = self._require_store()._load(proposal_id)
        detail = self.detail(proposal_id)
        if proposal.get("content_cleaned") or "normalized_content" not in proposal:
            return {**detail, "content_cleaned": True, "preview": None}
        # Review is read-only: no automatic submission, cancellation or recovery.
        security = self.runtime.security()
        client = security.clients().get(proposal["client_id"])
        if client:
            service = AgentService(self.repository, security)
            service._enforce_confirmation_policy(client, proposal)
            detail = self.detail(proposal_id)
        preview = self.store.preview_result(proposal)
        result = {**detail, "preview": preview}
        if client and detail["authorization_available"] and proposal.get("confirmation_mode") == "local_web" and proposal["state"] in {"draft", "previewed", "conflicted"}:
            self.store.preview(proposal)
            ticket = secrets.token_urlsafe(32)
            now = time.monotonic()
            self.runtime.preview_tickets = {key: value for key, value in self.runtime.preview_tickets.items() if value["expires"] > now}
            if len(self.runtime.preview_tickets) >= 1000:
                raise AgentError("preview_limit", "管理预览过多，请稍后重试", 429)
            self.runtime.preview_tickets[ticket] = {"workspace_id": self.workspace_id, "proposal_id": proposal_id, "version": proposal["version"],
                "digest": preview["preview_digest"], "confirmation_mode": proposal["confirmation_mode"], "client_version": client_version(client),
                "session": self.runtime._token, "expires": now + 600}
            result.update(preview_ticket=ticket, preview_ticket_seconds=600, state="previewed")
        return result

    @staticmethod
    def request_key(request_id):
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", request_id):
            raise AgentError("invalid_request", "提案管理请求标识无效")
        return hashlib.sha256(request_id.encode()).hexdigest()

    def _action_path(self, request_id):
        path = self.directory / (self.request_key(request_id) + ".json")
        if path.is_symlink() or path.resolve() != path.absolute():
            raise AgentError("unsafe_state_path", "提案操作路径无效", 503)
        return path

    def checkpoint(self, stage):
        """Durable action fault-injection seam."""

    @service_operation
    def cancel(self, proposal_id, payload):
        if not isinstance(payload, dict) or set(payload) != {"expected_version", "request_id", "workspace_id"} or payload["workspace_id"] != self.workspace_id:
            raise AgentError("invalid_request", "取消参数或工作空间无效")
        store = self._require_store()
        proposal = store._load(proposal_id)
        path = self._action_path(payload["request_id"])
        signature = digest(["cancel", proposal_id, payload])
        action = None
        if path.exists():
            action = read_json(path)
            if action.get("schema_version") in (1, 2) and action.get("input_digest") != signature:
                raise AgentError("request_conflict", "请求编号已用于其他提案操作", 409)
            if action.get("schema_version") != 1 or action.get("workspace_id") != self.workspace_id or action.get("operation") != "cancel" or action.get("proposal_id") != proposal_id or action.get("version") != payload["expected_version"] or action.get("state") not in {"prepared", "completed"}:
                raise AgentError("unsupported_schema", "提案操作格式不受支持", 503)
            if action.get("input_digest") != signature:
                raise AgentError("request_conflict", "请求编号已用于其他提案操作", 409)
            if action["state"] == "completed":
                return action["result"]
        if not action:
            store.editable(proposal, payload["expected_version"])
            action = {"schema_version": 1, "workspace_id": self.workspace_id, "request_id": payload["request_id"],
                      "operation": "cancel", "proposal_id": proposal_id, "version": payload["expected_version"],
                      "input_digest": signature, "state": "prepared", "created_at": stamp()}
            atomic_write_json(path, action)
            self.checkpoint("cancel_prepared")
        store.cancel(proposal, payload["expected_version"])
        self.checkpoint("cancel_applied")
        result = {"proposal_id": proposal_id, "version": proposal["version"], "state": "cancelled", "request_id": payload["request_id"]}
        action.update(state="completed", result=result)
        atomic_write_json(path, action)
        self.checkpoint("cancel_completed")
        return result

    @service_operation
    def approve(self, proposal_id, payload):
        fields = {"workspace_id", "version", "preview_digest", "preview_ticket", "request_id"}
        if not isinstance(payload, dict) or set(payload) != fields or payload["workspace_id"] != self.workspace_id or type(payload["version"]) is not int or not isinstance(payload["preview_ticket"], str):
            raise AgentError("invalid_request", "网页批准参数无效")
        self.runtime.authorize(self.runtime._token)
        path = self._action_path(payload["request_id"])
        signature = digest(["approve", proposal_id, payload])
        if path.exists():
            previous = read_json(path)
            if previous.get("schema_version") in (1, 2) and previous.get("input_digest") != signature:
                raise AgentError("request_conflict", "请求编号已用于其他提案操作", 409)
            action = self._load_approval(path)
            if action["input_digest"] != signature:
                raise AgentError("request_conflict", "请求编号已用于其他批准内容", 409)
            return self.action(payload["request_id"])
        store = self._require_store()
        proposal = store._load(proposal_id)
        ticket = self.runtime.preview_tickets.get(payload["preview_ticket"])
        security = self.runtime.security()
        with credential_lock(security.config_dir):
            client = security.clients().get(proposal["client_id"])
            expected = {"workspace_id": self.workspace_id, "proposal_id": proposal_id, "version": payload["version"], "digest": payload["preview_digest"],
                        "confirmation_mode": "local_web", "client_version": client_version(client), "session": self.runtime._token}
            if not ticket or ticket["expires"] <= time.monotonic() or any(ticket.get(key) != value for key, value in expected.items()):
                raise AgentError("preview_expired", "管理预览已失效，请重新完整预览", 409)
            store.editable(proposal, payload["version"])
            if proposal.get("confirmation_mode") != "local_web" or digest(store.preview_payload(proposal)) != payload["preview_digest"] or not self.detail(proposal_id)["authorization_available"]:
                raise AgentError("approval_conflict", "提案或授权已变化，请重新预览", 409)
            service = AgentService(self.repository, security)
            store.guard_writes()
            prepared = service.prepare_submission(client, proposal)
            approval = {"mode": "local_web", "version": proposal["version"], "preview_digest": payload["preview_digest"],
                        "operation_id": path.stem, "input_digest": signature, "approved_at": stamp()}
            action = {"schema_version": 2, "workspace_id": self.workspace_id, "request_id": payload["request_id"], "operation": "approve",
                      "proposal_id": proposal_id, "version": proposal["version"], "input_digest": signature, "approval": approval,
                      "business_operation_id": f"{proposal_id}-{proposal['version']}", "state": "approved"}
            atomic_write_json(path, action)
            self.checkpoint("approval_record")
            proposal["approval"] = approval
            store._save(proposal)
            self.checkpoint("approval_proposal")
            receipt = store.commit(proposal, payload["version"], payload["preview_digest"], {"mode": "local_web"}, prepared, local_approval=approval)
            self.checkpoint("approval_committed")
            action.update(state="completed", result=receipt)
            atomic_write_json(path, action)
            self.runtime.preview_tickets.pop(payload["preview_ticket"], None)
            return {"request_id": action["request_id"], "state": "completed", "receipt": receipt, "proposal_id": proposal_id}

    def _load_approval(self, path):
        action = read_json(path)
        if action.get("schema_version") != 2 or action.get("workspace_id") != self.workspace_id or action.get("operation") != "approve" or action.get("state") not in {"approved", "completed", "not_applied"} or self.request_key(action.get("request_id")) != path.stem:
            raise AgentError("unsupported_schema", "网页批准日志格式无效，保留证据核查", 503)
        if action.get("business_operation_id") != f"{action.get('proposal_id')}-{action.get('version')}" or action.get("approval", {}).get("operation_id") != path.stem:
            raise AgentError("unsupported_schema", "网页批准事务关联无效", 503)
        return action

    @service_operation
    def action(self, request_id):
        path = self._action_path(request_id)
        if not path.exists():
            raise AgentError("not_found", "提案操作不存在", 404)
        raw = read_json(path)
        if raw.get("operation") == "cancel":
            if raw.get("schema_version") != 1 or raw.get("workspace_id") != self.workspace_id:
                raise AgentError("unsupported_schema", "取消日志格式无效", 503)
            return {"request_id": request_id, "state": raw["state"], "result": raw.get("result"), "proposal_id": raw["proposal_id"]}
        action = self._load_approval(path)
        if action["state"] == "approved":
            manifest_path = self.store.operations / action["business_operation_id"] / "manifest.json"
            if not manifest_path.exists():
                action.update(state="not_applied", result=None)
            else:
                self.store.security = self.runtime.security()
                self.store.recover()
                proposal = self.store._load(action["proposal_id"])
                if proposal["state"] == "committed" and proposal.get("approval") == action["approval"]:
                    action.update(state="completed", result=proposal["receipt"])
                else:
                    return {"request_id": request_id, "state": "recovery_required", "proposal_id": action["proposal_id"]}
            atomic_write_json(path, action)
        return {"request_id": request_id, "state": action["state"], "receipt": action.get("result"), "proposal_id": action["proposal_id"]}
