"""AG-129 static Markdown execution contracts, not a dynamic command engine."""

import hashlib
import json
import re

from .agent_management import client_version
from .agent_security import AgentError


HANDLERS = {(kind, operation): "markdown@1" for kind in ("issue", "document", "todo", "info") for operation in ("create", "append", "update")}
STEP_TYPES = ["history_snapshot", "markdown_write"]


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def authorization_revision(client):
    revision = client.get("management_revision", 0)
    if type(revision) is not int or revision < 0:
        raise AgentError("invalid_configuration", "客户端管理版本无效", 503)
    return {"management_revision": revision, "client_version": client_version(client)}


def logical_plan(proposal):
    if proposal['kind'] == 'project' and proposal['operation'] == 'create':
        from .agent_project_execution import logical_plan as project_plan
        return project_plan(proposal)
    if proposal['operation'] == 'delete':
        from .agent_delete_execution import logical_plan as delete_plan
        return delete_plan(proposal)
    if proposal['kind'] == 'concept_map':
        from .agent_concept_execution import logical_plan as graph_plan
        return graph_plan(proposal)
    if proposal['kind'] == 'attachment':
        from .agent_attachments import logical_plan as attachment_plan
        return attachment_plan(proposal)
    handler = HANDLERS.get((proposal["kind"], proposal["operation"]))
    if handler is None:
        raise AgentError("unsupported_handler", "执行处理器不受支持", 503)
    content = proposal.get("normalized_content")
    candidate = fingerprint(content) if content is not None else proposal["execution_plan"]["candidate_digest"]
    return {"handler": handler, "kind": proposal["kind"], "operation": proposal["operation"],
            "target": {"id": proposal["target_id"], **proposal["access_target"]}, "candidate_digest": candidate,
            "steps": STEP_TYPES.copy(), "source_bindings": []}


def bind_context(proposal, client, dependencies):
    proposal.update(authorization_revision=authorization_revision(client), dependencies=dependencies)
    proposal["execution_plan"] = logical_plan(proposal)
    proposal["plan_digest"] = fingerprint(proposal["execution_plan"])


def validate_context(proposal):
    if type(proposal.get("version")) is not int or proposal["version"] < 1 or proposal.get("state") not in {"draft", "previewed", "conflicted", "committing", "committed", "recovery_required", "cancelled", "expired"}:
        raise ValueError("提案版本或状态无效")
    if proposal.get("content_cleaned"):
        if proposal["state"] not in {"committed", "cancelled", "expired"}:
            raise ValueError("在途提案不能清理内容")
    elif not isinstance(proposal.get("normalized_content"), dict):
        raise ValueError("未清理提案缺少完整候选")
    if proposal.get("digest_algorithm") != "sha256-json-v3" or proposal.get("confirmation_mode") not in {"agent_attested", "local_web"}:
        raise ValueError("提案摘要或确认版本无效")
    binding = proposal.get("authorization_revision")
    if not isinstance(binding, dict) or set(binding) != {"management_revision", "client_version"} or type(binding["management_revision"]) is not int or binding["management_revision"] < 0 or not re.fullmatch(r"[a-f0-9]{64}", str(binding["client_version"])):
        raise ValueError("提案授权版本无效")
    if proposal['kind'] == 'project' and proposal['operation'] == 'create':
        from .agent_project_execution import validate_context as project_context
        return project_context(proposal)
    if proposal['operation'] == 'delete':
        from .agent_delete_execution import validate_context as delete_context
        delete_context(proposal)
        return
    if proposal['kind'] == 'concept_map':
        from .agent_concept_execution import validate_context as graph_context
        graph_context(proposal)
        return
    if proposal['kind'] == 'attachment':
        from .agent_attachments import validate_dependencies
        validate_dependencies(proposal)
        return
    dependencies = proposal.get("dependencies")
    if not isinstance(dependencies, dict) or set(dependencies) != {"schema_version", "owner", "statuses", "tags", "references"} or type(dependencies["schema_version"]) is not int or dependencies["schema_version"] != 1:
        raise ValueError("提案依赖格式无效")
    owner = dependencies["owner"]
    if not isinstance(owner, dict) or owner.get("type") not in {"project", "document_category"} or type(owner.get("exists")) is not bool:
        raise ValueError("归属依赖无效")
    fields = {"type", "id", "exists"} if owner["type"] == "project" else {"type", "name", "exists"}
    if "workflow_template" in owner:
        fields.add("workflow_template")
    if set(owner) != fields or any(not isinstance(value, str) for key, value in owner.items() if key != "exists"):
        raise ValueError("归属依赖字段无效")
    for key, expected in (("statuses", {"name", "completed"}), ("tags", {"name", "exists"}), ("references", {"kind", "id", "revision"})):
        if not isinstance(dependencies[key], list):
            raise ValueError("依赖集合无效")
        for member in dependencies[key]:
            if not isinstance(member, dict) or set(member) != expected:
                raise ValueError("依赖集合成员无效")
            if key == "references":
                if member["kind"] not in {"issue", "document", "todo", "info"} or not isinstance(member["id"], str) or not re.fullmatch(r"[a-f0-9]{64}", str(member["revision"])):
                    raise ValueError("引用依赖无效")
            elif not isinstance(member["name"], str) or type(member.get("completed" if key == "statuses" else "exists")) is not bool:
                raise ValueError("配置依赖无效")
    if proposal.get("execution_plan") != logical_plan(proposal) or proposal.get("plan_digest") != fingerprint(proposal["execution_plan"]):
        raise ValueError("提案执行计划不一致")


def concrete_plan(manifest, proposal):
    if proposal['kind'] == 'project' and proposal['operation'] == 'create':
        from .agent_project_execution import concrete_plan as project_plan
        return project_plan(manifest, proposal)
    if proposal['operation'] == 'delete':
        from .agent_delete_execution import concrete_plan as delete_plan
        return delete_plan(manifest, proposal)
    if proposal['kind'] == 'concept_map':
        from .agent_concept_execution import concrete_plan as graph_plan
        return graph_plan(manifest, proposal)
    if proposal['kind'] == 'attachment':
        from .agent_attachment_execution import concrete_plan as attachment_plan
        return attachment_plan(manifest, proposal)
    return {"handler": "markdown@1", "proposal_plan_digest": proposal["plan_digest"], "steps": STEP_TYPES.copy(),
            "kind": manifest["kind"], "operation": manifest["operation"], "item_id": manifest["item_id"], "relative_path": manifest["relative_path"],
            "before_digest": manifest["before_digest"], "after_digest": manifest["after_digest"], "history_version": manifest["history_version"]}


def validate_manifest(manifest, proposal):
    if proposal['kind'] == 'project' and proposal['operation'] == 'create':
        from .agent_project_execution import validate_execution
        return validate_execution(None, manifest, proposal)
    if proposal['operation'] == 'delete':
        from .agent_delete_execution import validate_execution
        return validate_execution(None, manifest, proposal, False)
    if proposal['kind'] == 'attachment':
        from .agent_attachment_execution import validate_manifest as attachment_manifest
        return attachment_manifest(manifest, proposal)
    validate_context(proposal)
    if proposal.get("content_cleaned") and manifest.get("state") not in {"committed", "abandoned"}:
        raise ValueError("在途执行证据不能标为已清理")
    if manifest.get("kind") != proposal["kind"] or manifest.get("operation") != proposal["operation"] or manifest.get("access_target") != proposal["access_target"]:
        raise ValueError("执行资源类型不一致")
    for key in ("before_digest", "after_digest", "preview_digest"):
        if key == "before_digest" and manifest.get(key) is None:
            continue
        if not isinstance(manifest.get(key), str) or not re.fullmatch(r"[a-f0-9]{64}", manifest[key]):
            raise ValueError("执行内容摘要格式无效")
    if type(manifest.get("execution_schema_version")) is not int or manifest["execution_schema_version"] != (3 if proposal['kind'] == 'concept_map' else 1):
        raise ValueError("执行日志版本无效")
    if manifest.get("execution_plan") != concrete_plan(manifest, proposal) or manifest.get("execution_plan_digest") != fingerprint(manifest["execution_plan"]):
        raise ValueError("执行计划摘要无效")
    for key in ("authorization_revision", "dependencies", "preview_digest", "confirmation_mode", "digest_algorithm"):
        if manifest.get(key) != proposal.get(key):
            raise ValueError("执行日志与提案不一致")
    confirmation = manifest.get("confirmation")
    if proposal["confirmation_mode"] == "local_web":
        if confirmation != {"mode": "local_web"} or not manifest.get("approval") or manifest["approval"] != proposal.get("approval"):
            raise ValueError("执行日志网页确认不一致")
    elif not isinstance(confirmation, dict) or set(confirmation) - {"mode", "user_confirmed", "note"} or confirmation.get("mode") != "agent_attested" or confirmation.get("user_confirmed") is not True or not isinstance(confirmation.get("note", ""), str) or len(confirmation.get("note", "")) > 1000 or manifest.get("approval") is not None:
        raise ValueError("执行日志缺少有效对话确认")
    if manifest.get("client_id") != proposal["client_id"] or manifest.get("step_states") not in (["pending", "pending"], ["completed", "applying"], ["completed", "completed"]):
        raise ValueError("执行步骤身份或状态无效")
    receipt = manifest["receipt"]
    expected = {"proposal_id": proposal["proposal_id"], "version": proposal["version"], "kind": proposal["kind"],
                "item_id": manifest["item_id"], "revision": manifest["after_digest"], "plan_digest": proposal["plan_digest"],
                "execution_plan_digest": manifest["execution_plan_digest"]}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("执行回执绑定无效")
    if receipt.get("approval") != manifest.get("approval"):
        raise ValueError("执行回执批准绑定无效")


def validate_action(action, operation_id):
    """Approval schema 3 binds the reviewed logical plan, not an unallocated file ID."""
    fields = {"schema_version", "workspace_id", "request_id", "operation", "proposal_id", "version", "input_digest", "approval", "business_operation_id", "state", "proposal_schema_version", "plan_digest"}
    if set(action) - {"result"} != fields or action.get("proposal_schema_version") != 3 or action.get("operation") != "approve" or action.get("state") not in {"approved", "completed", "not_applied"}:
        raise ValueError("批准日志字段无效")
    approval = action.get("approval")
    expected = {"mode", "version", "preview_digest", "operation_id", "input_digest", "approved_at", "plan_digest", "authorization_revision", "dependencies_digest"}
    if not isinstance(approval, dict) or set(approval) != expected or approval["mode"] != "local_web" or approval["operation_id"] != operation_id:
        raise ValueError("批准记录字段无效")
    if approval["plan_digest"] != action["plan_digest"] or approval["version"] != action["version"] or approval["input_digest"] != action["input_digest"]:
        raise ValueError("批准记录版本绑定无效")
    if type(action["version"]) is not int or action["version"] < 1 or not isinstance(action["request_id"], str) or hashlib.sha256(action["request_id"].encode()).hexdigest() != operation_id or action["business_operation_id"] != f"{action['proposal_id']}-{action['version']}":
        raise ValueError("批准操作身份无效")
    binding = approval["authorization_revision"]
    if not isinstance(binding, dict) or set(binding) != {"management_revision", "client_version"} or type(binding["management_revision"]) is not int or binding["management_revision"] < 0:
        raise ValueError("批准授权版本无效")
    for value in (approval["plan_digest"], approval["dependencies_digest"], approval["preview_digest"], approval["input_digest"], binding["client_version"]):
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("批准摘要格式无效")
    if action["state"] == "completed":
        result = action.get("result")
        if not isinstance(result, dict) or any(result.get(key) != action[key] for key in ("proposal_id", "version", "plan_digest")) or result.get("approval") != approval:
            raise ValueError("批准完成回执不一致")
    elif action["state"] == "not_applied":
        if "result" not in action or action["result"] is not None:
            raise ValueError("未应用批准不能返回回执")
    elif "result" in action:
        raise ValueError("批准在途结果字段无效")
