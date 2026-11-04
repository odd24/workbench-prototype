"""Versioned proposals and recoverable single-Markdown Agent transactions."""

from __future__ import annotations

import difflib
import hashlib
import json
import uuid
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from .agent_security import AgentError, allows, read_json
from .markdown_io import load_markdown_text
from .persistence import atomic_write_bytes, atomic_write_json
from .security import validate_archive_member
from .write_coordinator import PreparedMarkdownWrite


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def byte_digest(value):
    return hashlib.sha256(value).hexdigest() if value is not None else None


class ProposalStore:
    def __init__(self, repository):
        self.repository = repository
        self.root = repository.root / ".agent"
        workspace = read_json(self.root / "workspace.json")
        if workspace.get("schema_version") != 1:
            raise AgentError("unsupported_schema", "Agent 工作空间格式不受支持", 503)
        self.workspace_id = workspace["workspace_id"]
        self.proposals = self.root / "proposals"
        self.operations = self.root / "operations"
        self.receipts = self.root / "receipts"
        for directory in (self.proposals, self.operations, self.receipts):
            if directory.is_symlink() or not directory.resolve().is_relative_to(repository.root):
                raise AgentError("unsafe_state_path", "Agent 状态目录路径无效", 503)
            directory.mkdir(parents=True, exist_ok=True)
        self.blocked = False
        self.recovery_errors = []
        self.executing = False

    def checkpoint(self, _stage):
        """Fault-injection seam; production has no callback or remote commands."""

    def guard_writes(self):
        if self.blocked and not self.executing:
            raise AgentError("recovery_required", "存在未解决的 Agent 写入，请先检查恢复日志", 503, False)

    def _save(self, proposal):
        atomic_write_json(self.proposals / f"{proposal['proposal_id']}.json", proposal)

    def _load(self, proposal_id):
        try:
            if str(uuid.UUID(proposal_id)) != proposal_id:
                raise ValueError()
            path = self.proposals / f"{proposal_id}.json"
            if path.resolve() != path.absolute():
                raise AgentError("unsafe_state_path", "提案路径无效", 503)
            value = read_json(path)
        except (ValueError, FileNotFoundError, TypeError):
            raise AgentError("not_found", "提案不存在或不可访问", 404)
        if value.get("schema_version") != 1 or value.get("workspace_id") != self.workspace_id:
            raise AgentError("unsupported_schema", "提案格式或工作空间不受支持", 503)
        if value["state"] in {"draft", "previewed", "conflicted"} and value["expires_at"] <= stamp():
            value.update(state="expired", finished_at=value["expires_at"])
            self._save(value)
        return value

    def owned(self, client, proposal_id):
        proposal = self._load(proposal_id)
        if proposal["client_id"] != client["client_id"] or not allows(client, proposal["access_target"]):
            raise AgentError("not_found", "提案不存在或不可访问", 404)
        return proposal

    def public(self, proposal):
        return {key: value for key, value in proposal.items() if key not in {"request_hash", "base_content"}}

    def find_request(self, client, request):
        for path in self.proposals.glob("*.json"):
            old = self._load(path.stem)
            if old["client_id"] == client["client_id"] and old["request_id"] == request["request_id"]:
                if old["request_hash"] != digest(request):
                    raise AgentError("idempotency_conflict", "相同 request_id 不能用于不同内容", 409)
                return self.public(self.owned(client, old["proposal_id"]))
        return None

    def create(self, client, request, content, base_content):
        request_hash = digest(request)
        active = 0
        for path in self.proposals.glob("*.json"):
            old = self._load(path.stem)
            if old["client_id"] != client["client_id"]:
                continue
            if old["request_id"] == request["request_id"]:
                if old["request_hash"] != request_hash:
                    raise AgentError("idempotency_conflict", "相同 request_id 不能用于不同内容", 409)
                return self.public(self.owned(client, old["proposal_id"]))
            active += old["state"] in {"draft", "previewed", "conflicted", "committing", "recovery_required"}
        if active >= 100:
            raise AgentError("proposal_limit", "活动提案数量已达到上限", 429)
        proposal = {"schema_version": 1, "workspace_id": self.workspace_id, "proposal_id": str(uuid.uuid4()),
                    "client_id": client["client_id"], "request_id": request["request_id"], "request_hash": request_hash,
                    "version": 1, "state": "draft", "operation": request["operation"], "kind": request["kind"],
                    "target_id": request.get("target_id"), "base_revision": request.get("base_revision"),
                    "base_content": base_content, "normalized_content": content, "source_note": request.get("source_note", ""),
                    "created_at": stamp(), "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                    "previewed_version": None, "preview_digest": None,
                    "access_target": {"type": request["kind"], "project_id": content.get("project_id"), "category": content.get("category")}}
        self._save(proposal)
        return self.public(proposal)

    def revise(self, proposal, expected_version, content, base_revision, base_content):
        self.editable(proposal, expected_version)
        proposal.update(version=proposal["version"] + 1, state="draft", normalized_content=content,
                        base_revision=base_revision, base_content=base_content, previewed_version=None, preview_digest=None,
                        expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                        access_target={"type": proposal["kind"], "project_id": content.get("project_id"), "category": content.get("category")})
        self._save(proposal)
        return self.public(proposal)

    def editable(self, proposal, expected_version):
        if type(expected_version) is not int or proposal["version"] != expected_version:
            raise AgentError("version_conflict", "提案版本已变化，请重新预览", 409)
        if proposal["state"] == "expired":
            raise AgentError("expired", "提案已过期，请重新整理和预览", 410)
        if proposal["state"] not in {"draft", "previewed", "conflicted"}:
            raise AgentError("invalid_state", "当前提案状态不允许此操作", 409)

    def preview_payload(self, proposal):
        warnings = ["新 ID 和创建/修改时间由服务端生成；用户可见字段以此预览为准。", "请展示完整内容，等待用户明确确认当前版本后再提交。"]
        preview = {key: proposal[key] for key in ("workspace_id", "proposal_id", "version", "operation", "kind", "target_id", "base_revision", "source_note")}
        return {**preview, "content": proposal["normalized_content"], "warnings": warnings}

    def preview(self, proposal):
        self.editable(proposal, proposal["version"])
        content = proposal["normalized_content"]
        preview = self.preview_payload(proposal)
        preview_digest = digest(preview)
        changes = {key: {"before": proposal["base_content"].get(key), "after": value}
                   for key, value in content.items() if proposal["base_content"].get(key) != value}
        diff = "\n".join(difflib.unified_diff(proposal["base_content"].get("body", "").splitlines(), content.get("body", "").splitlines(), fromfile="当前正文", tofile="拟保存正文", lineterm=""))
        proposal.update(state="previewed", previewed_version=proposal["version"], preview_digest=preview_digest)
        self._save(proposal)
        return {**preview, "preview_digest": preview_digest, "expires_at": proposal["expires_at"], "changes": changes, "body_diff": diff}

    def cancel(self, proposal, version):
        if proposal["state"] == "cancelled" and proposal["version"] == version:
            return self.public(proposal)
        self.editable(proposal, version)
        proposal.update(state="cancelled", finished_at=stamp())
        self._save(proposal)
        return self.public(proposal)

    def _target(self, manifest):
        relative = validate_archive_member(manifest["relative_path"])
        target = self.repository.root / relative
        if target.resolve() != target.absolute() or not target.resolve().is_relative_to(self.repository.root):
            raise ValueError("事务目标路径无效")
        parts = Path(relative).parts
        kind = manifest["kind"]
        if kind == "document":
            valid = len(parts) == 2 and parts[0] == "documents"
        else:
            valid = kind == "issue" and len(parts) == 4 and parts[0] == "projects" and parts[2] == "issues"
        if not valid or not target.name.startswith(manifest["item_id"] + "-") or target.suffix != ".md":
            raise ValueError("事务目标类型无效")
        return target

    def _finish(self, manifest, proposal):
        receipt = manifest["receipt"]
        atomic_write_json(self.receipts / f"{proposal['proposal_id']}.json", receipt)
        self.checkpoint("receipt")
        proposal.update(state="committed", receipt=receipt, finished_at=receipt["committed_at"])
        self._save(proposal)
        self.checkpoint("proposal")
        manifest["state"] = "committed"
        atomic_write_json(self.operations / manifest["operation_id"] / "manifest.json", manifest)

    def commit(self, proposal, version, preview_digest, confirmation, prepared):
        if proposal["state"] == "committed":
            if type(version) is not int or version != proposal["version"] or preview_digest != proposal["preview_digest"]:
                raise AgentError("version_conflict", "提交版本与原回执不一致", 409)
            return proposal["receipt"]
        self.editable(proposal, version)
        if proposal["state"] != "previewed" or proposal["previewed_version"] != version or not preview_digest or proposal["preview_digest"] != preview_digest or digest(self.preview_payload(proposal)) != preview_digest:
            raise AgentError("preview_required", "请完整预览当前版本后再提交", 409)
        if not isinstance(confirmation, dict) or set(confirmation) - {"mode", "user_confirmed", "note"} or confirmation.get("mode") != "agent_attested" or confirmation.get("user_confirmed") is not True:
            raise AgentError("confirmation_required", "需要用户在预览后明确确认当前版本")
        if not isinstance(confirmation.get("note", ""), str) or len(confirmation.get("note", "")) > 1000:
            raise AgentError("invalid_confirmation", "确认说明无效")
        self.guard_writes()
        operation_id = f"{proposal['proposal_id']}-{version}"
        directory = self.operations / operation_id
        directory.mkdir(parents=True, exist_ok=True)
        prepared.history_version = datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8]
        receipt = {"proposal_id": proposal["proposal_id"], "version": version, "kind": proposal["kind"],
                   "item_id": prepared.item_id, "revision": byte_digest(prepared.after), "committed_at": stamp(),
                   "title": proposal["normalized_content"]["title"], "project_id": proposal["normalized_content"].get("project_id"),
                   "category": proposal["normalized_content"].get("category"),
                   "web_path": "/?" + urlencode({"item": proposal["kind"], "itemId": prepared.item_id})}
        manifest = {"schema_version": 1, "workspace_id": self.workspace_id, "operation_id": operation_id,
                    "proposal_id": proposal["proposal_id"], "version": version, "kind": proposal["kind"],
                    "item_id": prepared.item_id, "relative_path": prepared.path.relative_to(self.repository.root).as_posix(),
                    "before_digest": byte_digest(prepared.before), "after_digest": byte_digest(prepared.after), "history_version": prepared.history_version,
                    "state": "prepared", "receipt": receipt, "confirmation": confirmation}
        self._target(manifest)
        try:
            atomic_write_bytes(directory / "after.md", prepared.after)
            if prepared.before is not None:
                atomic_write_bytes(directory / "before.md", prepared.before)
            self.checkpoint("snapshots")
            atomic_write_json(directory / "manifest.json", manifest)
            self.blocked = True
            self.checkpoint("manifest")
            proposal["state"] = "committing"
            self._save(proposal)
            self.checkpoint("committing")
            manifest["state"] = "applying"
            atomic_write_json(directory / "manifest.json", manifest)
            self.checkpoint("applying")
            self.executing = True
            self.repository.apply_markdown_write(proposal["kind"], prepared, self.checkpoint)
            self._finish(manifest, proposal)
            self.blocked = False
            return receipt
        except Exception:
            self.blocked = (directory / "manifest.json").exists()
            raise AgentError("commit_interrupted", "提交未能确认完成，请查询提案状态，勿重新创建", 503, True)
        finally:
            self.executing = False

    def recover(self):
        self.blocked = False
        self.recovery_errors = []
        for manifest_path in sorted(self.operations.glob("*/manifest.json")):
            try:
                if manifest_path.resolve() != manifest_path.absolute():
                    raise ValueError("事务路径无效")
                manifest = read_json(manifest_path)
                if manifest.get("schema_version") != 1 or manifest.get("workspace_id") != self.workspace_id or manifest.get("operation_id") != manifest_path.parent.name or manifest.get("state") not in {"prepared", "applying", "committed", "abandoned", "recovery_required"}:
                    raise ValueError("不受支持的事务格式")
                proposal = self._load(manifest["proposal_id"])
                if proposal["version"] != manifest["version"]:
                    raise ValueError("事务提案版本不一致")
                if manifest["state"] == "abandoned":
                    if proposal["state"] != "cancelled":
                        proposal.update(state="cancelled", finished_at=manifest["abandoned_at"], outcome="accepted_disk")
                        self._save(proposal)
                    continue
                receipt_path = self.receipts / f"{proposal['proposal_id']}.json"
                if receipt_path.exists():
                    if read_json(receipt_path) != manifest["receipt"]:
                        raise ValueError("事务回执不一致")
                    if manifest["state"] != "committed" or proposal["state"] != "committed":
                        self._finish(manifest, proposal)
                    continue
                if manifest["state"] == "committed":
                    # Later ordinary edits/deletion never replay an already completed operation.
                    if not (self.receipts / f"{proposal['proposal_id']}.json").exists() or proposal["state"] != "committed":
                        self._finish(manifest, proposal)
                    continue
                target = self._target(manifest)
                current = target.read_bytes() if target.exists() else None
                if byte_digest(current) == manifest["after_digest"]:
                    self.repository._forget_record(target)
                    self._finish(manifest, proposal)
                    continue
                if (current is None and manifest["before_digest"] is None and manifest["state"] == "applying") or manifest["state"] == "recovery_required" or byte_digest(current) != manifest["before_digest"]:
                    raise ValueError("磁盘内容与事务前后版本均不匹配")
                after = (manifest_path.parent / "after.md").read_bytes()
                before = (manifest_path.parent / "before.md").read_bytes() if manifest["before_digest"] is not None else None
                if byte_digest(after) != manifest["after_digest"] or byte_digest(before) != manifest["before_digest"]:
                    raise ValueError("事务快照校验失败")
                meta, _ = load_markdown_text(after.decode("utf-8"))
                if meta.get("id") != manifest["item_id"] or meta.get("type") != manifest["kind"]:
                    raise ValueError("事务快照身份无效")
                # Parent removal (e.g. project moved externally) cannot resurrect a project.
                if manifest["kind"] == "issue" and not self.repository.project(meta.get("project_id")):
                    raise ValueError("事务所属项目不存在")
                manifest["state"] = "applying"
                atomic_write_json(manifest_path, manifest)
                self.executing = True
                self.repository.apply_markdown_write(manifest["kind"], PreparedMarkdownWrite(target, manifest["item_id"], after.decode("utf-8"), before, manifest.get("history_version")))
                self._finish(manifest, proposal)
            except Exception:
                self.blocked = True
                self.recovery_errors.append(manifest_path.parent.name)
                try:
                    proposal = self._load(manifest_path.parent.name.rsplit("-", 1)[0])
                    proposal["state"] = "recovery_required"
                    self._save(proposal)
                except Exception:
                    pass
            finally:
                self.executing = False
        return {"blocked": self.blocked, "operations": self.recovery_errors}

    def recovery_report(self):
        result = self.recover()
        details = []
        for operation_id in result["operations"]:
            path = self.operations / operation_id / "manifest.json"
            try:
                manifest = read_json(path)
                target = self._target(manifest)
                current = target.read_bytes() if target.exists() else None
                details.append({"operation_id": operation_id, "kind": manifest.get("kind"),
                                "relative_path": manifest.get("relative_path"), "current_digest": byte_digest(current),
                                "before_digest": manifest.get("before_digest"), "after_digest": manifest.get("after_digest")})
            except Exception:
                details.append({"operation_id": operation_id, "error": "事务格式或路径损坏；保留原文件并使用匹配版本核查"})
        return {**result, "details": details}

    def abandon(self, operation_id):
        """Local operator accepts disk state; never exposed as an Agent tool."""
        if not isinstance(operation_id, str) or not re.fullmatch(r"[a-f0-9-]{36}-[1-9]\d*", operation_id):
            raise AgentError("invalid_operation_id", "操作标识无效")
        self.recover()
        if operation_id not in self.recovery_errors:
            raise AgentError("not_unresolved", "该操作已恢复或不存在，无需放弃", 409)
        path = self.operations / operation_id / "manifest.json"
        manifest = read_json(path)
        if manifest.get("schema_version") != 1 or manifest.get("workspace_id") != self.workspace_id:
            raise AgentError("unsupported_schema", "不能放弃未知格式的事务，请使用匹配版本核查", 503)
        proposal = self._load(manifest["proposal_id"])
        if manifest["operation_id"] != operation_id or manifest["version"] != proposal["version"]:
            raise AgentError("invalid_manifest", "事务身份不一致，拒绝修改", 503)
        manifest.update(state="abandoned", abandoned_at=stamp())
        atomic_write_json(path, manifest)
        proposal.update(state="cancelled", finished_at=manifest["abandoned_at"], outcome="accepted_disk")
        self._save(proposal)
        return self.recovery_report()

    def cleanup(self):
        now = datetime.now(timezone.utc)
        for path in self.proposals.glob("*.json"):
            proposal = self._load(path.stem)
            if proposal["state"] not in {"committed", "cancelled", "expired"}:
                continue
            finished = datetime.fromisoformat(proposal.get("finished_at", proposal["created_at"]))
            if now - finished <= timedelta(days=30):
                continue
            proposal.pop("normalized_content", None)
            proposal.pop("base_content", None)
            proposal["source_note"] = ""
            proposal["content_cleaned"] = True
            self._save(proposal)
            for directory in self.operations.glob(f"{proposal['proposal_id']}-*"):
                if directory.resolve() != directory.absolute():
                    raise AgentError("unsafe_state_path", "事务清理路径无效", 503)
                manifest_path = directory / "manifest.json"
                if not manifest_path.exists() or read_json(manifest_path).get("state") in {"committed", "abandoned"}:
                    for filename in ("before.md", "after.md"):
                        (directory / filename).unlink(missing_ok=True)
