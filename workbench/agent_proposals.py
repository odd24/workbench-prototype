"""Versioned proposals and recoverable Markdown execution journals."""

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
from .agent_execution import bind_context, validate_context, concrete_plan, validate_manifest, fingerprint, authorization_revision, validate_action
from .history import history_path


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
        uploads = getattr(self.repository, "document_uploads", None)
        if uploads:
            uploads.guard()
        if self.blocked and not self.executing:
            raise AgentError("recovery_required", "存在未解决的 Agent 写入，请先检查恢复日志", 503, False)

    def trash_protection(self, index):
        """Read-only protection inventory; never starts recovery or expires drafts."""
        self.preflight()
        protected = {}
        active = self.blocked
        for path in self.operations.glob('*/manifest.json'):
            manifest = read_json(path)
            if manifest['state'] not in {'committed', 'abandoned'}:
                active = True
            if manifest.get('operation') == 'delete' and manifest['state'] != 'committed':
                key = manifest['trash_token']
                if manifest['state'] != 'abandoned' or key in index or (self.repository.trash_dir / key).exists():
                    protected[key] = '删除计划尚在处理或放弃后仍需人工核查，保留回收证据'
        if active:
            for key in index:
                protected.setdefault(key, '存在未解决的Agent操作，请先核查恢复日志')
        return protected

    def _save(self, proposal):
        atomic_write_json(self.proposals / f"{proposal['proposal_id']}.json", proposal)

    def _load(self, proposal_id, *, expire=True):
        try:
            if str(uuid.UUID(proposal_id)) != proposal_id:
                raise ValueError()
            path = self.proposals / f"{proposal_id}.json"
            if path.resolve() != path.absolute():
                raise AgentError("unsafe_state_path", "提案路径无效", 503)
            value = read_json(path)
        except (ValueError, FileNotFoundError, TypeError):
            raise AgentError("not_found", "提案不存在或不可访问", 404)
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") not in (1, 2, 3) or value.get("workspace_id") != self.workspace_id:
            raise AgentError("unsupported_schema", "提案格式或工作空间不受支持", 503)
        if value.get("proposal_id") != proposal_id:
            raise AgentError("invalid_manifest", "提案文件与内部身份不一致", 503)
        if value["schema_version"] == 2 and (value.get("digest_algorithm") != "sha256-json-v2" or value.get("confirmation_mode") not in {"agent_attested", "local_web"}):
            raise AgentError("unsupported_schema", "提案摘要或确认策略不受支持", 503)
        if value["schema_version"] == 1 and value.get("kind") not in {"issue", "document"}:
            raise AgentError("unsupported_schema", "旧格式提案类型不受支持", 503)
        if value["schema_version"] == 3:
            try:
                validate_context(value)
            except (ValueError, KeyError, TypeError):
                raise AgentError("unsupported_schema", "提案执行契约损坏或不受支持", 503) from None
        expiring = expire and value["state"] in {"draft", "previewed", "conflicted"} and value["expires_at"] <= stamp()
        in_flight = expiring and any(self.operations.glob(f"{proposal_id}-*/manifest.json"))
        if expiring and not in_flight:
            self.preflight()
            value.update(state="expired", finished_at=value["expires_at"])
            self._save(value)
        return value

    def owned(self, client, proposal_id):
        proposal = self._load(proposal_id)
        if proposal["client_id"] != client["client_id"] or not allows(client, proposal["access_target"]) or proposal.get('source_target') is not None and not allows(client, proposal['source_target']):
            raise AgentError("not_found", "提案不存在或不可访问", 404)
        if proposal['operation'] == 'delete' and not proposal.get('content_cleaned'):
            from .agent_delete_service import access_target
            for impact in proposal['normalized_content']['impacts']:
                item = impact['source']['item']
                if not allows(client, access_target(item['type'], item)):
                    raise AgentError('not_found', '提案不存在或不可访问', 404)
        return proposal

    def public(self, proposal):
        return {key: value for key, value in proposal.items() if key not in {"request_hash", "base_content", "delete_binding"}}

    def find_request(self, client, request):
        for path in self.proposals.glob("*.json"):
            old = self._load(path.stem)
            if old["client_id"] == client["client_id"] and old["request_id"] == request["request_id"]:
                if old["request_hash"] != digest(request):
                    raise AgentError("idempotency_conflict", "相同 request_id 不能用于不同内容", 409)
                return self.public(self.owned(client, old["proposal_id"]))
        return None

    def create(self, client, request, content, base_content, confirmation_mode="agent_attested", *, dependencies=None, graph_warnings=None, delete_binding=None):
        self.preflight()
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
        proposal = {"schema_version": 3, "digest_algorithm": "sha256-json-v3", "confirmation_mode": confirmation_mode, "approval": None, "workspace_id": self.workspace_id, "proposal_id": str(uuid.uuid4()),
                    "client_id": client["client_id"], "request_id": request["request_id"], "request_hash": request_hash,
                    "version": 1, "state": "draft", "operation": request["operation"], "kind": request["kind"],
                    "target_id": request.get("target_id"), "base_revision": request.get("base_revision"),
                    "base_content": base_content, "normalized_content": content, "source_note": request.get("source_note", ""),
                    "created_at": stamp(), "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                    "previewed_version": None, "preview_digest": None,
                    "access_target": {"type": request["kind"], "project_id": content.get("project_id"), "category": content.get("category")}}
        if proposal['operation'] == 'delete':
            from .agent_delete_service import access_target
            proposal.update(delete_binding=delete_binding, access_target=access_target(proposal['kind'], content['target']['item']))
            bind_context(proposal, client, dependencies)
            validate_context(proposal)
            self.preview_result(proposal)
            self._save(proposal)
            return self.public(proposal)
        if proposal['kind'] == 'attachment':
            proposal['access_target'] = {'project_id':content['project_id']} if content['owner_kind'] == 'project' else {'type':'document', 'category':content['metadata_before'].get('category', '未分类')} if content['owner_kind'] == 'document' else {'type':content['owner_kind'], 'project_id':content['project_id']}
        if proposal['kind'] == 'concept_map':
            from .agent_concept_execution import identity
            from .agent_concept_service import graph_target
            # The cursor may consume an ID before this atomic proposal save.
            # Only the saved proposal binds it to the request/client/workspace.
            with self.repository.write_lock, self.repository._record_id_lock:
                if proposal['operation'] == 'create':
                    proposal['target_id'] = self.repository._concept_map_repository.next_id()
                    self.checkpoint('concept_map_id_claimed')
                proposal.update(identity=identity(proposal), graph_warnings=graph_warnings or [],
                                access_target=graph_target(content['graph'], proposal['target_id']),
                                source_target=graph_target(base_content, proposal['target_id']) if proposal['operation'] == 'update' else None)
                bind_context(proposal, client, dependencies)
                validate_context(proposal)
                self._save(proposal)
                self.checkpoint('concept_map_reserved')
                return self.public(proposal)
        bind_context(proposal, client, dependencies)
        self._save(proposal)
        return self.public(proposal)

    def revise(self, proposal, expected_version, content, base_revision, base_content, *, client=None, dependencies=None, graph_warnings=None, delete_binding=None):
        self.preflight()
        self.editable(proposal, expected_version)
        proposal.update(approval=None, version=proposal["version"] + 1, state="draft", normalized_content=content,
                        base_revision=base_revision, base_content=base_content, previewed_version=None, preview_digest=None,
                        expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                        access_target={"type": proposal["kind"], "project_id": content.get("project_id"), "category": content.get("category")})
        if proposal['operation'] == 'delete':
            from .agent_delete_service import access_target
            proposal.update(delete_binding=delete_binding, access_target=access_target(proposal['kind'], content['target']['item']))
            bind_context(proposal, client, dependencies)
            validate_context(proposal)
            self.preview_result(proposal)
            self._save(proposal)
            return self.public(proposal)
        if proposal['kind'] == 'attachment':
            proposal['access_target'] = {'project_id':content['project_id']} if content['owner_kind'] == 'project' else {'type':'document', 'category':content['metadata_before'].get('category', '未分类')} if content['owner_kind'] == 'document' else {'type':content['owner_kind'], 'project_id':content['project_id']}
        if proposal['kind'] == 'concept_map':
            from .agent_concept_service import graph_target
            proposal.update(access_target=graph_target(content['graph'], proposal['target_id']), graph_warnings=graph_warnings or [],
                            source_target=graph_target(base_content, proposal['target_id']) if proposal['operation'] == 'update' else None)
        if proposal["schema_version"] == 3:
            bind_context(proposal, client, dependencies)
            if proposal['kind'] == 'concept_map':
                validate_context(proposal)
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
        if proposal.get("schema_version") in (2, 3):
            preview.update(confirmation_mode=proposal["confirmation_mode"], digest_algorithm=proposal["digest_algorithm"])
        if proposal.get("schema_version") == 3:
            preview.update(**{key: proposal[key] for key in ("authorization_revision", "dependencies", "execution_plan", "plan_digest")})
        if proposal['operation'] == 'delete':
            from .agent_delete_execution import token
            return {**preview, 'content':proposal['normalized_content'], 'trash_token':token(proposal), 'warnings':proposal['normalized_content']['warnings']}
        if proposal['kind'] == 'attachment':
            warnings = ['二进制仅按名称、大小、MIME及SHA-256预览，未解析内容；不执行或解压。', '创建/修改时间显示占位；服务端在接受本次确认时生成实际时间并持久记入执行计划，不使用草稿时间。', '最终名称和相对链接已固定；同名占位必须重新预览。', '请展示完整正文、元数据差异及来源，等待当前版本明确确认。']
        if proposal['kind'] == 'concept_map':
            from .agent_concept_execution import preview_fields
            return {**preview, 'content': proposal['normalized_content'], **preview_fields(proposal)}
        return {**preview, "content": proposal["normalized_content"], "warnings": warnings}

    def preview_result(self, proposal):
        content = proposal["normalized_content"]
        preview = self.preview_payload(proposal)
        preview_digest = digest(preview)
        if proposal['operation'] == 'delete':
            from .agent_delete_service import checked_preview
            return checked_preview({**preview, 'preview_digest':preview_digest, 'expires_at':proposal['expires_at'], 'changes':{'operation':{'before':'正式条目', 'after':'回收站'}}, 'body_diff':''})
        if proposal['kind'] == 'concept_map':
            from .agent_concept_execution import checked_preview
            return checked_preview({**preview, 'preview_digest': preview_digest, 'expires_at': proposal['expires_at'], 'changes': preview['graph_diff'], 'body_diff': ''})
        changes = {key: {"before": proposal["base_content"].get(key), "after": value}
                   for key, value in content.items() if proposal["base_content"].get(key) != value}
        diff = "\n".join(difflib.unified_diff(proposal["base_content"].get("body", "").splitlines(), content.get("body", "").splitlines(), fromfile="当前正文", tofile="拟保存正文", lineterm=""))
        return {**preview, "preview_digest": preview_digest, "expires_at": proposal["expires_at"], "changes": changes, "body_diff": diff}

    def preview(self, proposal):
        self.preflight()
        self.editable(proposal, proposal["version"])
        result = self.preview_result(proposal)
        proposal.update(state="previewed", previewed_version=proposal["version"], preview_digest=result["preview_digest"])
        self._save(proposal)
        return result

    def cancel(self, proposal, version):
        self.preflight()
        if proposal["state"] == "cancelled" and proposal["version"] == version:
            return self.public(proposal)
        self.editable(proposal, version)
        proposal.update(state="cancelled", finished_at=stamp())
        self._save(proposal)
        return self.public(proposal)

    def _target(self, manifest):
        if manifest['kind'] == 'concept_map':
            from .agent_concept_maps import controlled_graph_path
            if not re.fullmatch(r'CMAP-[0-9]+', str(manifest['item_id'])) or manifest['relative_path'] != f"concept-maps/{manifest['item_id']}.json":
                raise ValueError('图执行固定目标无效')
            return controlled_graph_path(self.repository.root, manifest['relative_path'])
        if manifest['kind'] == 'attachment':
            from .agent_attachment_execution import targets
            return targets(self.repository, self._load(manifest['proposal_id'], expire=False))[1]
        relative = validate_archive_member(manifest["relative_path"])
        target = self.repository.root / relative
        if target.resolve() != target.absolute() or not target.resolve().is_relative_to(self.repository.root):
            raise ValueError("事务目标路径无效")
        parts = Path(relative).parts
        kind = manifest["kind"]
        if kind == "document":
            valid = len(parts) == 2 and parts[0] == "documents"
        else:
            valid = kind in {"issue", "todo", "info"} and len(parts) == 4 and parts[0] == "projects" and parts[2] == {"issue": "issues", "todo": "todos", "info": "infos"}[kind]
            if kind == "info" and not re.fullmatch(r"INFO-\d+", manifest["item_id"]):
                valid = False
            if kind == "todo" and not re.fullmatch(r"(?:TODO|ISSUE)-\d+" if manifest.get("before_digest") else r"TODO-\d+", manifest["item_id"]):
                valid = False
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
        if manifest["schema_version"] == 3:
            manifest["step_states"] = ['completed'] * 4 if proposal['operation'] == 'delete' else dict.fromkeys(manifest["step_states"], "completed") if proposal["kind"] == "attachment" else ["completed", "completed"]
        atomic_write_json(self.operations / manifest["operation_id"] / "manifest.json", manifest)

    def check_commit(self, proposal, version, preview_digest, confirmation, *, local_approval=None):
        if proposal["state"] == "committed":
            if type(version) is not int or version != proposal["version"] or preview_digest != proposal["preview_digest"]:
                raise AgentError("version_conflict", "提交版本与原回执不一致", 409)
            return proposal["receipt"]
        self.preflight()
        self.editable(proposal, version)
        if proposal["state"] != "previewed" or proposal["previewed_version"] != version or not preview_digest or proposal["preview_digest"] != preview_digest or digest(self.preview_payload(proposal)) != preview_digest:
            raise AgentError("preview_required", "请完整预览当前版本后再提交", 409)
        if proposal.get("confirmation_mode", "agent_attested") == "local_web":
            if not local_approval or proposal.get("approval") != local_approval or confirmation != {"mode": "local_web"}:
                raise AgentError("confirmation_required", "需要本机管理页面独立批准", 409)
            self._verify_approval({"proposal_id": proposal["proposal_id"], "version": version, "preview_digest": preview_digest,
                                   "approval": local_approval, "state": "prepared"}, proposal, check_authorization=True)
        else:
            if not isinstance(confirmation, dict) or set(confirmation) - {"mode", "user_confirmed", "note"} or confirmation.get("mode") != "agent_attested" or confirmation.get("user_confirmed") is not True:
                raise AgentError("confirmation_required", "需要用户在预览后明确确认当前版本")
            if not isinstance(confirmation.get("note", ""), str) or len(confirmation.get("note", "")) > 1000:
                raise AgentError("invalid_confirmation", "确认说明无效")
        self.guard_writes()
        return None

    def commit(self, proposal, version, preview_digest, confirmation, prepared, *, local_approval=None):
        previous = self.check_commit(proposal, version, preview_digest, confirmation, local_approval=local_approval)
        if previous is not None:
            return previous
        if proposal['operation'] == 'delete':
            return self._commit_delete(proposal, version, preview_digest, prepared, local_approval)
        operation_id = f"{proposal['proposal_id']}-{version}"
        directory = self.operations / operation_id
        directory.mkdir(parents=True, exist_ok=True)
        prepared.history_version = datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8]
        receipt_content = proposal['normalized_content']['graph'] if proposal['kind'] == 'concept_map' else proposal['normalized_content']
        receipt = {"proposal_id": proposal["proposal_id"], "version": version, "kind": proposal["kind"],
                   "item_id": prepared.item_id, "revision": byte_digest(prepared.after), "committed_at": stamp(),
                   "title": receipt_content["title"], "project_id": receipt_content.get("project_id"),
                   "category": receipt_content.get("category"),
                   "web_path": "/?" + urlencode({"item": proposal["kind"], "itemId": prepared.item_id})}
        if proposal['kind'] == 'concept_map':
            graph = proposal['normalized_content']['graph']
            receipt.update(title=graph['title'], project_id=graph['project_id'], category=graph['category'])
        if proposal["kind"] == "todo" and not prepared.item_id.startswith("TODO-"):
            receipt["web_path"] = None  # Converted legacy IDs remain readable via the record UI.
        manifest = {"schema_version": proposal["schema_version"], "workspace_id": self.workspace_id, "operation_id": operation_id,
                    "proposal_id": proposal["proposal_id"], "version": version, "kind": proposal["kind"],
                    "item_id": prepared.item_id, "relative_path": prepared.path.relative_to(self.repository.root).as_posix(),
                    "before_digest": byte_digest(prepared.before), "after_digest": byte_digest(prepared.after), "history_version": prepared.history_version,
                    "state": "prepared", "receipt": receipt, "confirmation": confirmation}
        if local_approval:
            receipt.update(approval=local_approval)
        if proposal["schema_version"] in (2, 3):
            manifest.update(digest_algorithm=proposal["digest_algorithm"], preview_digest=preview_digest,
                            confirmation_mode=proposal["confirmation_mode"], approval=proposal["approval"])
        if proposal["schema_version"] == 3:
            manifest.update(execution_schema_version=1, client_id=proposal["client_id"],
                            operation=proposal["operation"], access_target=proposal["access_target"],
                            authorization_revision=proposal["authorization_revision"], dependencies=proposal["dependencies"],
                            step_states=["pending", "pending"])
            if proposal['kind'] == 'concept_map':
                manifest.update(execution_schema_version=3, managed_time=json.loads(prepared.after.decode('utf-8'))['updated'])
            manifest["execution_plan"] = concrete_plan(manifest, proposal)
            manifest["execution_plan_digest"] = fingerprint(manifest["execution_plan"])
            receipt.update(plan_digest=proposal["plan_digest"], execution_plan_digest=manifest["execution_plan_digest"])
            self._validate_execution(manifest, proposal)
        self._target(manifest)
        suffix = 'json' if proposal['kind'] == 'concept_map' else 'md'
        try:
            atomic_write_bytes(directory / f'after.{suffix}', prepared.after)
            if prepared.before is not None:
                atomic_write_bytes(directory / f'before.{suffix}', prepared.before)
            self.checkpoint("snapshots")
            if manifest["schema_version"] == 3:
                self._validate_execution(manifest, proposal, snapshots=True)
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
            if proposal['kind'] == 'concept_map':
                self._current_authorization(proposal)
                self.repository.apply_concept_map_write(prepared, self._progress(manifest, directory / 'manifest.json'))
            else:
                self.repository.apply_markdown_write(proposal["kind"], prepared, self._progress(manifest, directory / "manifest.json"))
            self._finish(manifest, proposal)
            self.blocked = False
            return receipt
        except Exception:
            self.blocked = (directory / "manifest.json").exists()
            raise AgentError("commit_interrupted", "提交未能确认完成，请查询提案状态，勿重新创建", 503, True)
        finally:
            self.executing = False

    def _commit_delete(self, proposal, version, preview_digest, prepared, approval):
        from .agent_delete_execution import token, concrete_plan as delete_plan, apply_steps
        operation_id = f"{proposal['proposal_id']}-{version}"
        directory = self.operations / operation_id
        directory.mkdir(parents=True, exist_ok=True)
        accepted = stamp()
        content = proposal['normalized_content']
        receipt = {'proposal_id':proposal['proposal_id'], 'version':version, 'kind':proposal['kind'],
                   'item_id':prepared.item_id, 'revision':proposal['base_revision'], 'committed_at':accepted,
                   'title':content['title'], 'project_id':content['project_id'], 'category':content['category'],
                   'deleted':True, 'trash_token':token(proposal), 'web_path':'/?item=trash&itemId=' + token(proposal), 'approval':approval,
                   'plan_digest':proposal['plan_digest']}
        manifest = {'schema_version':3, 'execution_schema_version':4, 'workspace_id':self.workspace_id,
                    'operation_id':operation_id, 'proposal_id':proposal['proposal_id'], 'version':version,
                    'client_id':proposal['client_id'], 'kind':proposal['kind'], 'operation':'delete',
                    'item_id':prepared.item_id, 'relative_path':prepared.relative_path, 'before_digest':proposal['base_revision'],
                    'trash_token':token(proposal), 'deleted_at':accepted, 'state':'prepared', 'step_states':['pending'] * 4,
                    'receipt':receipt, 'confirmation':{'mode':'local_web'}, 'approval':approval,
                    **{key:proposal[key] for key in ('authorization_revision', 'dependencies', 'preview_digest', 'confirmation_mode', 'digest_algorithm', 'access_target')}}
        manifest['execution_plan'] = delete_plan(manifest, proposal)
        manifest['execution_plan_digest'] = fingerprint(manifest['execution_plan'])
        receipt['execution_plan_digest'] = manifest['execution_plan_digest']
        self._validate_execution(manifest, proposal)
        try:
            atomic_write_bytes(directory / ('before.json' if proposal['kind'] == 'concept_map' else 'before.md'), prepared.before)
            from .deletion_prepared import read_trash_index
            index_raw, index = read_trash_index(self.repository.root)
            if byte_digest(index_raw) != proposal['delete_binding']['trash_index_digest'] or manifest['trash_token'] in index:
                raise ValueError('回收站索引变化或token被占用，请重新完整预览')
            atomic_write_bytes(directory / 'index-before.json', index_raw)
            self.checkpoint('snapshots')
            self._validate_execution(manifest, proposal, snapshots=True)
            atomic_write_json(directory / 'manifest.json', manifest)
            self.blocked = True
            self.checkpoint('manifest')
            proposal['state'] = 'committing'
            self._save(proposal)
            self.checkpoint('committing')
            self.executing = True
            apply_steps(self, manifest, proposal, prepared)
            self._finish(manifest, proposal)
            self.blocked = False
            return receipt
        except Exception:
            self.blocked = (directory / 'manifest.json').exists()
            raise AgentError('commit_interrupted', '删除结果尚未确认，请查询原提案，不要重新创建或生成回收token', 503, True) from None
        finally:
            self.executing = False

    def _progress(self, manifest, path):
        def checkpoint(stage):
            self.checkpoint(stage)  # An exit here occurs AFTER disk write, BEFORE progress log.
            if manifest["schema_version"] == 3 and stage in {"history", "target"}:
                manifest["step_states"] = ["completed", "applying" if stage == "history" else "completed"]
                atomic_write_json(path, manifest)
                self.checkpoint(stage + "_logged")
            if manifest.get('kind') == 'concept_map' and stage == 'history':
                # History is already durable, but the graph has not published.
                # Revocation/dependency changes still prevent the JSON write.
                self._current_authorization(self._load(manifest['proposal_id'], expire=False))
        return checkpoint

    def _history_path(self, manifest):
        if manifest['kind'] == 'concept_map':
            from .history import concept_map_history_path
            from .agent_concept_maps import controlled_graph_path
            path = concept_map_history_path(self.repository.history_dir, manifest['item_id'], manifest['history_version'])
            return controlled_graph_path(self.repository.root, path.relative_to(self.repository.root).as_posix())
        path = history_path(self.repository.history_dir, manifest["item_id"], manifest["history_version"])
        if path.resolve() != path.absolute():
            raise ValueError("历史步骤路径无效")
        return path

    def _validate_execution(self, manifest, proposal, *, snapshots=False):
        if proposal['operation'] == 'delete':
            from .agent_delete_execution import validate_execution
            return validate_execution(self, manifest, proposal, snapshots)
        if proposal['kind'] == 'concept_map':
            from .agent_concept_execution import validate_snapshots
            return validate_snapshots(self, manifest, proposal, snapshots)
        if proposal['kind'] == 'attachment':
            from .agent_attachment_execution import validate_execution
            return validate_execution(self, manifest, proposal, snapshots)
        validate_manifest(manifest, proposal)
        self._target(manifest)
        self._history_path(manifest)
        if manifest["before_digest"] != (None if proposal["operation"] == "create" else proposal["base_revision"]):
            raise ValueError("执行基础版本无效")
        if proposal["target_id"] is not None and manifest["item_id"] != proposal["target_id"]:
            raise ValueError("执行目标身份无效")
        if manifest["kind"] != "document" and Path(manifest["relative_path"]).parts[1] != proposal["access_target"]["project_id"]:
            raise ValueError("执行目标项目无效")
        if not proposal.get("content_cleaned") and manifest["preview_digest"] != digest(self.preview_payload(proposal)):
            raise ValueError("执行预览摘要不一致")
        if snapshots and not proposal.get("content_cleaned"):
            directory = self.operations / manifest["operation_id"]
            values = {}
            for name, expected in (("after.md", manifest["after_digest"]), ("before.md", manifest["before_digest"])):
                path = directory / name
                if path.resolve() != path.absolute():
                    raise ValueError("执行快照路径无效")
                value = path.read_bytes() if expected is not None else None
                if byte_digest(value) != expected:
                    raise ValueError("执行快照摘要不一致")
                values[name] = value
            meta, body = load_markdown_text(values["after.md"].decode("utf-8"))
            if meta.get("id") != manifest["item_id"] or meta.get("type") != proposal["kind"] or any(({**meta, "body": body}).get(key) != value for key, value in proposal["normalized_content"].items()):
                raise ValueError("执行快照不属于当前已预览候选")

    def preflight(self):
        try:
            self._preflight()
        except AgentError:
            raise
        except (ValueError, KeyError, TypeError, OSError):
            raise AgentError("recovery_required", "执行证据损坏或不受支持，停止写入并保留现场", 503) from None

    def _preflight(self):
        """Read/validate EVERY format before expiry, recovery, cleanup or acceptance writes."""
        for path in self.proposals.glob("*.json"):
            self._load(path.stem, expire=False)
        for path in self.operations.glob("*/manifest.json"):
            if path.resolve() != path.absolute():
                raise AgentError("unsafe_state_path", "事务路径无效", 503)
            manifest = read_json(path)
            if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest["schema_version"] not in (1, 2, 3):
                raise AgentError("unsupported_schema", "事务版本不受支持，保留原现场", 503)
            proposal = self._load(manifest["proposal_id"], expire=False)
            if manifest["workspace_id"] != self.workspace_id or manifest["operation_id"] != path.parent.name or manifest["version"] != proposal["version"] or manifest["schema_version"] != proposal["schema_version"]:
                raise AgentError("invalid_manifest", "事务身份与提案不一致", 503)
            if manifest.get("state") not in {"prepared", "applying", "committed", "abandoned", "recovery_required"}:
                raise AgentError("invalid_manifest", "事务状态无效", 503)
            if manifest["schema_version"] in (2, 3) and (manifest.get("digest_algorithm") != f"sha256-json-v{manifest['schema_version']}" or manifest.get("confirmation_mode") not in {"agent_attested", "local_web"} or manifest.get("preview_digest") != proposal.get("preview_digest")):
                raise AgentError("invalid_manifest", "事务摘要或确认格式无效", 503)
            if manifest["schema_version"] == 3:
                receipt_path = self.receipts / f"{proposal['proposal_id']}.json"
                receipt_proven = receipt_path.exists()
                if receipt_proven:
                    receipt = read_json(receipt_path)
                    if receipt != manifest["receipt"] or proposal["state"] == "committed" and proposal.get("receipt") != receipt:
                        raise AgentError("invalid_manifest", "原回执与执行记录不一致", 503)
                self._validate_execution(manifest, proposal, snapshots=manifest["state"] != "abandoned" and not receipt_proven)
            if manifest.get("confirmation_mode") == "local_web":
                self._verify_approval(manifest, proposal, check_authorization=False)
        actions = self.root / "proposal-actions"
        for path in actions.glob("*.json"):
            if path.resolve() != path.absolute():
                raise AgentError("unsafe_state_path", "批准日志路径无效", 503)
            action = read_json(path)
            expected = {"cancel": (1,), "approve": (2, 3)}.get(action.get("operation"), ()) if isinstance(action, dict) else ()
            if not isinstance(action, dict) or type(action.get("schema_version")) is not int or action["schema_version"] not in expected or action.get("workspace_id") != self.workspace_id:
                raise AgentError("unsupported_schema", "批准或取消日志格式不受支持", 503)
            if action["schema_version"] == 3:
                validate_action(action, path.stem)

    def _current_authorization(self, proposal, *, held_source=None):
        runtime = getattr(self.repository, "agent_runtime", None)
        security = runtime.security() if runtime and runtime.status()["workspace_id"] else getattr(self, "security", None)
        if not security:
            raise AgentError("authorization_unavailable", "需要匹配私人授权核查未应用事务", 503)
        client = security.clients().get(proposal["client_id"])
        if not client or not client.get("enabled") or not {"read", "propose", "commit"} <= set(client.get("scopes", [])) or not allows(client, proposal["access_target"]) or client["client_id"] in security.manager().blocked_clients():
            raise AgentError("authorization_revoked", "原客户端权限已失效，停止发布正文", 409)
        if authorization_revision(client) != proposal["authorization_revision"]:
            raise AgentError("authorization_changed", "原客户端授权版本已变化", 409)
        from .agent_service import AgentService
        service = AgentService(self.repository, security)
        if proposal['operation'] == 'delete' or proposal['kind'] == 'concept_map':
            service.prepare_submission(client, proposal, held_source=held_source)
            return client
        if service.execution_dependencies(client, proposal["kind"], proposal["normalized_content"]) != proposal["dependencies"]:
            raise AgentError("dependency_changed", "提案依赖或集合已变化", 409)
        return client

    def _verify_approval(self, manifest, proposal, *, check_authorization):
        approval = manifest.get("approval")
        if not isinstance(approval, dict) or approval != proposal.get("approval") or approval.get("mode") != "local_web" or approval.get("version") != manifest["version"] or approval.get("preview_digest") != manifest["preview_digest"]:
            raise AgentError("invalid_approval", "网页批准与事务版本不一致", 503)
        operation_id = approval.get("operation_id", "")
        if not re.fullmatch(r"[a-f0-9]{64}", operation_id):
            raise AgentError("invalid_approval", "网页批准标识无效", 503)
        path = self.root / "proposal-actions" / (operation_id + ".json")
        if path.resolve() != path.absolute():
            raise AgentError("invalid_approval", "网页批准日志路径无效", 503)
        action = read_json(path)
        if action.get("schema_version") != (3 if proposal["schema_version"] == 3 else 2) or action.get("workspace_id") != self.workspace_id or action.get("proposal_id") != proposal["proposal_id"] or action.get("operation") != "approve" or action.get("approval") != approval or action.get("input_digest") != approval.get("input_digest") or action.get("state") not in {"approved", "completed"}:
            raise AgentError("invalid_approval", "缺少持久网页批准证据", 503)
        if proposal["schema_version"] == 3 and (approval.get("plan_digest") != proposal["plan_digest"] or approval.get("authorization_revision") != proposal["authorization_revision"] or approval.get("dependencies_digest") != fingerprint(proposal["dependencies"]) or action.get("plan_digest") != proposal["plan_digest"]):
            raise AgentError("invalid_approval", "网页批准未绑定当前执行计划及授权", 503)
        if check_authorization:
            runtime = getattr(self.repository, "agent_runtime", None)
            security = runtime.security() if runtime else getattr(self, "security", None)
            if not security:
                raise AgentError("authorization_unavailable", "需要匹配私人授权后核查未应用的网页批准事务", 503)
            client = security.clients().get(proposal["client_id"])
            if not client or not client.get("enabled") or not {"read", "propose", "commit"} <= set(client.get("scopes", [])) or not allows(client, proposal["access_target"]) or client["client_id"] in security.manager().blocked_clients():
                raise AgentError("authorization_revoked", "未应用事务的原客户端授权已失效，停止写入", 409)

    def recover(self):
        with self.repository.write_lock:
            runtime = getattr(self.repository, "agent_runtime", None)
            security = runtime.security() if runtime and runtime.status()["workspace_id"] else getattr(self, "security", None)
            if security:
                from .agent_management import credential_lock
                with credential_lock(security.config_dir):
                    return self._recover()
            return self._recover()

    def _recover(self):
        self.blocked = False
        self.recovery_errors = []
        try:
            self.preflight()
        except Exception as error:
            self.blocked = True
            self.recovery_errors = [path.parent.name for path in sorted(self.operations.glob("*/manifest.json"))]
            return {"blocked": True, "operations": self.recovery_errors, "format_error": getattr(error, "code", "invalid_manifest")}
        for manifest_path in sorted(self.operations.glob("*/manifest.json")):
            try:
                if manifest_path.resolve() != manifest_path.absolute():
                    raise ValueError("事务路径无效")
                manifest = read_json(manifest_path)
                if manifest.get("schema_version") not in (1, 2, 3) or manifest.get("workspace_id") != self.workspace_id or manifest.get("operation_id") != manifest_path.parent.name or manifest.get("state") not in {"prepared", "applying", "committed", "abandoned", "recovery_required"}:
                    raise ValueError("不受支持的事务格式")
                proposal = self._load(manifest["proposal_id"], expire=False)
                if manifest["schema_version"] == 2 and (manifest.get("digest_algorithm") != "sha256-json-v2" or manifest.get("confirmation_mode") not in {"agent_attested", "local_web"} or manifest.get("preview_digest") != proposal.get("preview_digest")):
                    raise ValueError("事务确认策略或摘要不一致")
                if proposal["version"] != manifest["version"] or proposal["schema_version"] != manifest["schema_version"]:
                    raise ValueError("事务提案版本不一致")
                if manifest.get("confirmation_mode") == "local_web":
                    self._verify_approval(manifest, proposal, check_authorization=manifest["schema_version"] < 3 and manifest["state"] == "prepared")
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
                if proposal['operation'] == 'delete':
                    from .agent_delete_execution import prepared_from_manifest, apply_steps
                    prepared = prepared_from_manifest(self, manifest, proposal)
                    self.executing = True
                    apply_steps(self, manifest, proposal, prepared, recovery=True)
                    self._finish(manifest, proposal)
                    continue
                if proposal['kind'] == 'attachment':
                    # Dedicated entry points recover binary evidence outside all
                    # caller-owned business/credential/workspace locks.
                    self.blocked = True
                    self.recovery_errors.append(manifest['operation_id'])
                    continue
                target = self._target(manifest)
                current = target.read_bytes() if target.exists() else None
                if manifest["schema_version"] == 3:
                    history = self._history_path(manifest)
                    if manifest["before_digest"] is not None and manifest["step_states"][0] == "completed" and not history.exists():
                        raise ValueError("已记录完成的历史步骤证据缺失")
                    if history.exists() and byte_digest(history.read_bytes()) != manifest["before_digest"]:
                        raise ValueError("历史步骤实际内容与计划不一致")
                if byte_digest(current) == manifest["after_digest"]:
                    if manifest["schema_version"] == 3 and manifest["before_digest"] is not None and not history.exists():
                        raise ValueError("正文已写但历史步骤证据缺失")
                    self.repository._forget_record(target)
                    self._finish(manifest, proposal)
                    continue
                if (current is None and manifest["before_digest"] is None and manifest["state"] == "applying") or manifest["state"] == "recovery_required" or byte_digest(current) != manifest["before_digest"]:
                    raise ValueError("磁盘内容与事务前后版本均不匹配")
                if manifest["schema_version"] == 3:
                    self._current_authorization(proposal)
                if proposal['kind'] == 'concept_map':
                    from .concept_maps import PreparedConceptMapWrite
                    after = (manifest_path.parent / 'after.json').read_bytes()
                    before = (manifest_path.parent / 'before.json').read_bytes() if manifest['before_digest'] is not None else None
                    manifest['state'] = 'applying'
                    atomic_write_json(manifest_path, manifest)
                    self.executing = True
                    self.repository.apply_concept_map_write(PreparedConceptMapWrite(target, manifest['item_id'], before, after, manifest['history_version']), self._progress(manifest, manifest_path))
                    self._finish(manifest, proposal)
                    continue
                after = (manifest_path.parent / "after.md").read_bytes()
                before = (manifest_path.parent / "before.md").read_bytes() if manifest["before_digest"] is not None else None
                if byte_digest(after) != manifest["after_digest"] or byte_digest(before) != manifest["before_digest"]:
                    raise ValueError("事务快照校验失败")
                meta, _ = load_markdown_text(after.decode("utf-8"))
                if meta.get("id") != manifest["item_id"] or meta.get("type") != manifest["kind"]:
                    raise ValueError("事务快照身份无效")
                if manifest["schema_version"] == 3:
                    _, body = load_markdown_text(after.decode("utf-8"))
                    if any(({**meta, "body": body}).get(key) != value for key, value in proposal["normalized_content"].items()):
                        raise ValueError("事务快照与已预览候选不一致")
                # Parent removal (e.g. project moved externally) cannot resurrect a project.
                if manifest["kind"] != "document" and not self.repository.project(meta.get("project_id")):
                    raise ValueError("事务所属项目不存在")
                manifest["state"] = "applying"
                atomic_write_json(manifest_path, manifest)
                self.executing = True
                self.repository.apply_markdown_write(manifest["kind"], PreparedMarkdownWrite(target, manifest["item_id"], after.decode("utf-8"), before, manifest.get("history_version")), self._progress(manifest, manifest_path))
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
        if manifest.get("schema_version") not in (1, 2, 3) or manifest.get("workspace_id") != self.workspace_id:
            raise AgentError("unsupported_schema", "不能放弃未知格式的事务，请使用匹配版本核查", 503)
        proposal = self._load(manifest["proposal_id"])
        if manifest["operation_id"] != operation_id or manifest["version"] != proposal["version"]:
            raise AgentError("invalid_manifest", "事务身份不一致，拒绝修改", 503)
        if manifest["schema_version"] == 3:
            try:
                if proposal['operation'] == 'delete':
                    self.preflight()
                self._validate_execution(manifest, proposal, snapshots=proposal['operation'] == 'delete')
            except (ValueError, KeyError, TypeError):
                raise AgentError("invalid_manifest", "不能放弃不受支持或身份不一致的执行计划", 503) from None
        manifest.update(state="abandoned", abandoned_at=stamp())
        if proposal['operation'] == 'delete':
            manifest['manual_review_required'] = True
        atomic_write_json(path, manifest)
        proposal.update(state="cancelled", finished_at=manifest["abandoned_at"], outcome="accepted_disk")
        self._save(proposal)
        return self.recovery_report()

    def cleanup(self):
        self.preflight()
        now = datetime.now(timezone.utc)
        for path in self.proposals.glob("*.json"):
            proposal = self._load(path.stem)
            manifests = [read_json(item) for item in self.operations.glob(f"{proposal['proposal_id']}-*/manifest.json")]
            if any(item["state"] not in {"committed", "abandoned"} for item in manifests):
                continue
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
                if manifest_path.exists():
                    manifest = read_json(manifest_path)
                    if manifest.get("schema_version") not in (1, 2, 3):
                        raise AgentError("unsupported_schema", "不能清理未知格式的事务", 503)
                if not manifest_path.exists() or manifest.get("state") in {"committed", "abandoned"}:
                    if proposal['operation'] == 'delete':
                        (directory / 'index-before.json').unlink(missing_ok=True)
                    for filename in (("before.json", "after.json") if proposal['kind'] == 'concept_map' else ("before.md", "after.md")):
                        (directory / filename).unlink(missing_ok=True)
