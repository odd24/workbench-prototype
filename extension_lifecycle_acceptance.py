"""Explicit disposable extension backup/restore and Agent-off acceptance.

No real user data, credentials or client configuration is used. Remote and
non-Codex interoperability remain separate external gates.
"""
from __future__ import annotations

import io
import hashlib
import json
import shutil
import socket
import tempfile
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import quote, unquote

from codex_agent_acceptance import LocalWorkbench
from server import Repository
from workbench.agent_proposal_management import ProposalManagement
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentError, AgentSecurity, read_json
from workbench.agent_file_handles import LocalFileHandle
from workbench.agent_management import client_version
from workbench.document_attachments import attachment_items, local_links
from workbench.markdown_io import load_markdown_text
from workbench.persistence import atomic_write_json
from workbench.agent_delete_authorization import DeleteGrantManagement
from workbench.agent_service import AgentService


def tree_bytes(root):
    """Compare durable files, excluding only the OS-held service lock."""
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob('*')
            if path.is_file() and path.name != '.workbench-service.lock'}


def verify_stopped_mixed_copies(base, repo, security, receipts, transport, file_id,
                               source, secret, foreign_security):
    """Reuse the stopped mixed fixture; never manufacture approval evidence."""
    original_data, original_private = tree_bytes(repo.root), tree_bytes(security.config_dir.parent)
    outcomes = {}
    for mode in ('matching', 'missing', 'mismatched'):
        backup = base / ('stopped-' + mode)
        data, private = backup / 'data', backup / 'private'
        shutil.copytree(repo.root, data)
        if mode == 'matching':
            shutil.copytree(security.config_dir.parent, private)
        elif mode == 'mismatched':
            # A real foreign registry, placed where the old workspace expects its own.
            shutil.copytree(foreign_security.config_dir, private / security.workspace_id)
        before_data, before_private = tree_bytes(data), tree_bytes(private)
        restored = Repository(data)
        # Repository initialization always updates the machine-local location preference.
        assert read_json(data / 'config/settings.json') == {'version': 1, 'data_dir': str(data.resolve())}
        before_data['config/settings.json'] = (data / 'config/settings.json').read_bytes()
        assert {k: v for k, v in before_data.items() if k != 'config/settings.json'} == {
            k: v for k, v in original_data.items() if k != 'config/settings.json'}
        runtime = restored.agent_runtime = AgentRuntime(restored, base=private)
        assert runtime.status()['workspace_id'] == security.workspace_id
        if mode == 'mismatched':
            try:
                runtime.set_enabled(True)
            except AgentError as error:
                assert error.code == 'management_recovery_required', error.code
            else:
                raise AssertionError('Foreign private registry accepted')
            try:
                runtime.security().authenticate('Bearer ' + transport['token'], security.workspace_id)
            except AgentError as error:
                assert error.code == 'management_recovery_required', error.code
            else:
                raise AssertionError('Foreign registry authenticated the old client')
            assert tree_bytes(private) == before_private
        else:
            runtime.set_enabled(True)
            restored_security = runtime.security()
            if mode == 'missing':
                assert restored_security.clients() == {}
                try:
                    restored_security.authenticate('Bearer ' + transport['token'], security.workspace_id)
                except AgentError as error:
                    assert error.code == 'unauthenticated', error.code
                else:
                    raise AssertionError('Missing private root accepted an old credential')
            else:
                client = restored_security.authenticate('Bearer ' + transport['token'], security.workspace_id)
                assert restored_security.clients() == security.clients()
                info = restored.agent_service.get_file_info(client, file_id)
                params = {'source_revision': info['source_revision'], 'offset': 0, 'length': 65536}
                assert restored.agent_service.read_file(client, file_id, params)['body'] == secret.decode()
                # Replacing an authorized source with identical bytes must still fail identity validation.
                replacement = base / 'replacement-source.txt'
                replacement.write_bytes(secret)
                replacement.replace(source)
                evidence = tree_bytes(data), tree_bytes(private)
                try:
                    restored.agent_service.read_file(client, file_id, params)
                except AgentError as error:
                    assert error.code == 'source_changed', error.code
                else:
                    raise AssertionError('Copied source identity was trusted')
                assert (tree_bytes(data), tree_bytes(private)) == evidence
                assert tree_bytes(private) == before_private
            # Completed approvals are historical receipts, including when credentials are missing.
            management = ProposalManagement(runtime)
            for receipt in receipts:
                assert read_json(restored.agent_proposals.receipts / (receipt['proposal_id'] + '.json')) == receipt
                if 'approval' in receipt:
                    action = read_json(management.directory / (receipt['approval']['operation_id'] + '.json'))
                    result = management.action(action['request_id'])
                    assert result['state'] == 'completed' and result['receipt'] == receipt
        # Whole-tree equality includes attachments, configuration, ordering, graph/history,
        # trash, proposal actions and receipts, rather than only visible current Markdown.
        after_data = tree_bytes(data)
        assert after_data == before_data, (mode, [
            name for name in before_data.keys() | after_data.keys()
            if before_data.get(name) != after_data.get(name)])
        outcomes[mode] = True
    outcomes['pending_copied_identity_retained'] = verify_copied_pending_delete(
        base, repo.root, security, transport, receipts)
    assert tree_bytes(repo.root) == original_data and tree_bytes(security.config_dir.parent) == original_private
    return outcomes


def verify_copied_pending_delete(base, original, security, transport, receipts):
    """Derive a pending operation from the same mixed data, then copy its NTFS evidence."""
    pending = base / 'pending-origin'
    shutil.copytree(original, pending / 'data')
    shutil.copytree(security.config_dir.parent, pending / 'private')
    repo = Repository(pending / 'data')
    runtime = repo.agent_runtime = AgentRuntime(repo, base=pending / 'private')
    runtime.set_enabled(True)
    runtime.status(session=True)
    restored_security = runtime.security()
    client = restored_security.authenticate('Bearer ' + transport['token'], security.workspace_id)
    [item] = [item for item in repo.list_records() if item['type'] == 'info']
    grants = DeleteGrantManagement(runtime)
    review = grants.preview(client['client_id'], {
        'workspace_id': security.workspace_id, 'expected_version': client_version(client),
        'grants': {'schema_version': 1, 'grants': [{
            'capability': 'items.delete', 'operations': ['delete'],
            'resources': [{'type': 'project', 'id': item['project_id']}],
            'minimum_confirmation_mode': 'local_web'}]}})
    grants.approve(client['client_id'], {
        **{k: review[k] for k in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')},
        'approved': True, 'request_id': uuid.uuid4().hex})
    client = restored_security.clients()[client['client_id']]
    service = repo.agent_service
    _, path = repo.get_record(item['id'])
    proposal = service.prepare_proposal(client, {
        'request_id': uuid.uuid4().hex, 'kind': 'info', 'operation': 'delete',
        'target_id': item['id'], 'base_revision': hashlib.sha256(path.read_bytes()).hexdigest()})
    management = ProposalManagement(runtime)
    preview = management.preview(proposal['proposal_id'])

    def stop(stage):
        if stage == 'trash_moved':
            raise OSError('synthetic interruption after original handle move')

    with patch.object(service.store, 'checkpoint', side_effect=stop):
        try:
            management.approve(proposal['proposal_id'], {
                **{k: preview[k] for k in ('workspace_id', 'version', 'preview_digest', 'preview_ticket')},
                'request_id': uuid.uuid4().hex})
        except AgentError:
            pass
        else:
            raise AssertionError('Pending delete interruption was not reached')
    assert not path.exists()
    operation_id = proposal['proposal_id'] + '-1'
    manifest_path = service.store.operations / operation_id / 'manifest.json'
    manifest = read_json(manifest_path)
    trash = repo.trash_dir / manifest['trash_token']
    assert trash.is_file() and not (service.store.receipts / (proposal['proposal_id'] + '.json')).exists()
    copied = base / 'pending-copy'
    shutil.copytree(repo.root, copied / 'data')
    shutil.copytree(pending / 'private', copied / 'private')
    with LocalFileHandle(str(trash), read=True) as old_handle:
        with LocalFileHandle(str(copied / 'data' / '.trash' / manifest['trash_token']), read=True) as new_handle:
            assert old_handle.initial['index'] != new_handle.initial['index']
    before = tree_bytes(copied / 'data'), tree_bytes(copied / 'private')
    reopened = Repository(copied / 'data')
    copied_security = AgentSecurity(reopened.root, copied / 'private')
    copied_service = AgentService(reopened, copied_security)
    result = copied_service.store.recover()
    assert result['blocked'] and operation_id in result['operations']
    assert not (reopened.root / path.relative_to(repo.root)).exists()
    assert tree_bytes(copied / 'private') == before[1]
    after = tree_bytes(reopened.root)
    changed = {name for name in before[0].keys() | after.keys() if before[0].get(name) != after.get(name)}
    # Startup can normalize the local path and mark this proposal recovery_required.
    assert changed <= {'config/settings.json', '.agent/proposals/' + proposal['proposal_id'] + '.json'}, changed
    proposal_name = '.agent/proposals/' + proposal['proposal_id'] + '.json'
    expected_proposal = json.loads(before[0][proposal_name])
    expected_proposal['state'] = 'recovery_required'
    assert copied_service.store._load(proposal['proposal_id'], expire=False) == expected_proposal
    assert read_json(reopened.root / 'config/settings.json') == {'version': 1, 'data_dir': str(reopened.root)}
    for receipt in receipts:
        assert read_json(copied_service.store.receipts / (receipt['proposal_id'] + '.json')) == receipt
    stable = tree_bytes(reopened.root)
    assert copied_service.store.recover()['blocked'] and tree_bytes(reopened.root) == stable
    return True


def run_acceptance():
    with tempfile.TemporaryDirectory(prefix="workbench-extension-lifecycle-") as temporary:
        base = Path(temporary)
        data, credentials = base / "data", base / "private"
        workbench = LocalWorkbench(data, credentials)
        try:
            repo = workbench.repository
            runtime = AgentRuntime(repo, port=workbench.server.server_address[1], base=credentials)
            repo.agent_runtime = runtime
            repo.ensure_document_category("未分类")
            project = repo.create_project({"name": "隔离备份验收"})
            security = workbench.security
            provisioned = security.add_client("临时生命周期验收", ["read", "propose", "commit"], [project["id"]], ["未分类"], workbench.base_url, kinds=["issue", "document", "todo", "info"])
            client = security.clients()[provisioned["client_id"]]
            service = repo.agent_service
            management = ProposalManagement(runtime)
            fields = [{"name": "命令", "value": "  echo 'one'\n  echo two  ", "note": "  首尾与换行\n说明  "}]
            receipts = []
            for kind in ("issue", "todo", "info", "document"):
                for mode in ("agent_attested", "local_web"):
                    content = {"title": kind + " " + mode, "body": "# 备份验收\n\n临时内容", **({"category": "未分类"} if kind == "document" else {"project_id": project["id"]})}
                    if kind == "info": content["info_fields"] = fields
                    if kind == "todo": content["due"] = "2028-02-29"
                    proposal = service.prepare_proposal(client, {"request_id": kind + mode, "kind": kind, "operation": "create", "confirmation_mode": mode, "content": content})
                    if mode == "local_web":
                        detail = management.preview(proposal["proposal_id"])
                        result = management.approve(proposal["proposal_id"], {"workspace_id": security.workspace_id, "version": detail["version"], "preview_digest": detail["preview"]["preview_digest"], "preview_ticket": detail["preview_ticket"], "request_id": kind + "-approved"})
                        receipt = result["receipt"]
                    else:
                        preview = service.preview_proposal(client, proposal["proposal_id"])
                        receipt = service.commit_proposal(client, proposal["proposal_id"], {"version": preview["version"], "preview_digest": preview["preview_digest"], "confirmation": {"mode": mode, "user_confirmed": True, "note": "程序化隔离验收夹具"}})
                    receipts.append(receipt)
            expected = {(receipt["kind"], receipt["item_id"]): service.get_item(client, receipt["kind"], receipt["item_id"]) for receipt in receipts}
            archive = repo.export_zip()
            workspace = security.workspace_id
            config = read_json(Path(provisioned["config_file"]))
            runtime.set_enabled(False)
            request = Request(workbench.base_url + "/api/agent/v1/capabilities", headers={"Authorization": "Bearer " + config["token"], "X-Workbench-Workspace": workspace})
            try:
                urlopen(request, timeout=5)
                raise AssertionError("Disabled Agent route unexpectedly succeeded")
            except HTTPError as error:
                assert error.code == 404
                error.close()
            with urlopen(workbench.base_url + "/api/records", timeout=5) as response:
                assert len(json.load(response)) == 6
            with urlopen(workbench.base_url + "/api/documents", timeout=5) as response:
                assert len(json.load(response)) == 2
        finally:
            workbench.close()
        # Full stopped-service backup includes private state and approval evidence.
        backup = base / "offline-backup"
        shutil.copytree(data, backup / "data")
        shutil.copytree(credentials, backup / "private")
        original_markdown = {path.relative_to(data).as_posix(): path.read_bytes() for path in data.rglob("*.md")}
        restored = Repository(backup / "data")
        restored_runtime = AgentRuntime(restored, base=backup / "private")
        restored.agent_runtime = restored_runtime
        restored_runtime.set_enabled(True)
        restored_security = AgentSecurity(restored.root, backup / "private")
        restored_client = restored_security.clients()[client["client_id"]]
        assert restored_security.workspace_id == workspace
        for key, item in expected.items():
            actual = restored.agent_service.get_item(restored_client, *key)
            assert actual == item, key
            if key[0] == "info": assert actual["info_fields"] == fields
        assert original_markdown == {path.relative_to(restored.root).as_posix(): path.read_bytes() for path in restored.root.rglob("*.md")}
        restored_management = ProposalManagement(restored_runtime)
        for receipt in receipts:
            if "approval" in receipt:
                result = restored_management.action(receipt["kind"] + "-approved")
                assert result["state"] == "completed" and result["receipt"] == receipt
        # Portable export contains business facts but no workspace or approvals.
        portable = base / "portable"
        portable.mkdir()
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            assert package.testzip() is None
            assert all(".agent" not in Path(name).parts and "management-operations" not in Path(name).parts for name in package.namelist())
            package.extractall(portable)
        candidates = [portable, *portable.iterdir()]
        portable_root = next(path for path in candidates if path.is_dir() and (path / "projects").is_dir())
        portable_repo = Repository(portable_root)
        portable_runtime = AgentRuntime(portable_repo, base=base / "portable-private")
        assert portable_runtime.status()["workspace_id"] is None
        assert len(portable_repo.list_records()) == 6 and len(portable_repo.list_documents()) == 2
        portable_runtime.set_enabled(True)
        assert portable_runtime.status()["workspace_id"] != workspace
        assert portable_runtime.security().clients() == {}
        for record in portable_repo.list_records(record_type="info"):
            assert record["info_fields"] == fields
        return {"passed": True, "types": ["issue", "todo", "info", "document"], "confirmation_modes": ["agent_attested", "local_web"],
                "persisted_items": 8, "agent_off_ui_available": True, "stopped_full_backup_receipts_restored": True,
                "portable_zip_crc_and_secret_exclusion": True, "portable_restores_new_identity": True,
                "real_user_data_changed": False, "non_codex_and_remote": "not_run_external_environment_missing"}


def run_mixed_portable_acceptance():
    """Verify portable copies of one mixed, isolated business and private state."""
    with tempfile.TemporaryDirectory(prefix="wb-mixed-") as temporary:
        base = Path(temporary)
        workbench = LocalWorkbench(base / "data", base / "private")
        try:
            repo = workbench.repository
            runtime = repo.agent_runtime = AgentRuntime(
                repo, port=workbench.server.server_address[1], base=base / "private")
            security = workbench.security
            service = repo.agent_service
            management = ProposalManagement(runtime)
            project = repo.create_project({"name": "混合备份项目"})
            source_category, destination = "原知识分类", "可移植知识"
            repo.ensure_document_category(source_category)
            repo.ensure_document_category("保留空分类")
            provisioned = security.add_client(
                "混合备份临时身份", ["read", "propose", "commit"],
                [project["id"]], [source_category], workbench.base_url,
                kinds=["issue", "todo", "info", "document"])
            client_id = provisioned["client_id"]
            workspace = security.workspace_id
            original_transport = read_json(Path(provisioned["config_file"]))
            receipts, items = [], {}
            headers = {"Origin": workbench.base_url, "X-Workbench-Management": "1", "Content-Type": "application/json"}

            def local(route, payload=None):
                with urlopen(Request(
                    workbench.base_url + "/api/local/agent-management/" + route, headers=headers,
                    data=None if payload is None else json.dumps(payload).encode()), timeout=10) as response:
                    return json.load(response)

            headers["X-Workbench-Management-Token"] = local("status")["management_token"]

            def grant(route, selection):
                review = local(f"clients/{client_id}/{route}/preview", {
                    "workspace_id": workspace, "expected_version": client_version(security.clients()[client_id]),
                    **selection})
                approval = {key: review[key] for key in (
                    "workspace_id", "expected_version", "preview_id", "preview_digest")}
                return local(f"clients/{client_id}/{route}/confirm", {
                    **approval, "approved": True, "request_id": uuid.uuid4().hex})

            def approve_proposal(request):
                client = security.clients()[client_id]
                proposal = service.prepare_proposal(client, {
                    "request_id": uuid.uuid4().hex, "confirmation_mode": "local_web", **request})
                review = management.preview(proposal["proposal_id"])
                preview = review["preview"]
                result = management.approve(proposal["proposal_id"], {
                    "workspace_id": workspace, "version": preview["version"],
                    "preview_digest": preview["preview_digest"],
                    "preview_ticket": review["preview_ticket"], "request_id": uuid.uuid4().hex})
                receipts.append(result["receipt"])
                return result["receipt"]

            for kind in ("issue", "todo", "info", "document"):
                content = {"title": "混合 " + kind, "body": "完整正文\n\n保留引用和附件。"}
                content.update({"category": source_category} if kind == "document"
                               else {"project_id": project["id"]})
                if kind == "info":
                    content["info_fields"] = [{"name": "多行值", "value": "  原值\n第二行  ", "note": "保留"}]
                if kind == "todo":
                    content["status"] = "进行中"
                items[kind] = approve_proposal({"kind": kind, "operation": "create", "content": content})["item_id"]

            binary = b"AG143 formal bytes\x00\xff\n"
            record_asset = repo.add_record_attachment_stream(
                items["issue"], "记录 #%.bin", io.BytesIO(binary), len(binary))
            repo.ensure_project_asset_category(project["id"], "独立原分类")
            project_asset = repo.add_project_asset_stream(
                project["id"], "独立 #%.bin", io.BytesIO(binary), len(binary), category="独立原分类")
            document, _ = repo.get_document(items["document"])

            def short(action):
                with repo.write_lock:
                    return action()

            uploaded = repo.document_uploads.receive(
                document["id"], str(uuid.uuid4()), "文档 #%.bin", len(binary),
                document["revision"], io.BytesIO(binary), short)
            assert uploaded["state"] == "completed"
            document_asset = uploaded["receipt"]["attachment"]
            document, _ = repo.get_document(document["id"])
            record_reference = f'[[{items["issue"]}#attachment:{quote(record_asset["name"], safe="")}]]'
            repo.update_document(document["id"], {
                "body": document["body"] + "\n\n" + record_reference,
                "expected_revision": document["revision"]})
            assert all(repo.attachment_path(owner, name).read_bytes() == binary for owner, name in (
                (items["issue"], record_asset["name"]), (document["id"], document_asset["name"])))
            assert repo.project_asset_path(project["id"], project_asset["id"]).read_bytes() == binary

            issue, _ = repo.get_record(items["issue"])
            repo.update_record(issue["id"], {"body": issue["body"] + "\n\n[[" + items["document"] + "]]"})
            repo.update_project(project["id"], {
                "todo_status_order": ["进行中", "已完成"],
                "todo_status_record_sorts": {"已完成": "manual"},
                "todo_record_order": [items["todo"]]})
            repo.save_project_sort({"mode": "custom", "order": [project["id"]]})
            repo.save_document_sort({
                "category_mode": "manual", "category_order": ["保留空分类", source_category],
                "file_modes": {source_category: "manual"}, "file_orders": {source_category: [document["id"]]}})
            review = repo.preview_category_change({
                "operation": "rename", "selection": {
                    "family": "document_category", "name": source_category, "new_name": destination}})
            receipts.append(repo.approve_category_change({"ticket": review["ticket"]}))
            review = repo.preview_category_change({
                "operation": "rename", "selection": {
                    "family": "project_attachment_category", "project_id": project["id"],
                    "name": "独立原分类", "new_name": "独立新分类"}})
            receipts.append(repo.approve_category_change({"ticket": review["ticket"]}))
            review = repo.preview_workflow_change({
                "operation": "delete_status", "selection": {
                    "template_id": "standard", "record_type": "todo",
                    "status_id": "doing", "target_status_id": "done"}})
            assert review["approvable"]
            receipts.append(repo.approve_workflow_change({"ticket": review["ticket"]}))
            assert repo.get_record(items["todo"])[0]["completed"] is True

            graph = repo.create_concept_map({
                "title": "混合图原版", "category": "图原分类", "project_id": project["id"],
                "nodes": [{"id": "a", "text": "甲"}, {"id": "b", "text": "乙"}],
                "edges": [{"id": "edge", "from": "a", "to": "b", "label": "引用"}]})
            original_graph = repo.get_concept_map(graph["id"])[1].read_bytes()
            resource = {"type": "concept_map", "id": graph["id"]}
            grant("concept-maps", {"grants": {"schema_version": 1, "grants": [
                {"capability": "concept_maps.read", "operations": ["read"],
                 "resources": [resource], "minimum_confirmation_mode": "agent_attested"},
                {"capability": "concept_maps.write", "operations": ["update"],
                 "resources": [resource], "minimum_confirmation_mode": "local_web"}]}})
            current = service.get_concept_map(security.clients()[client_id], graph["id"])
            approve_proposal({
                "kind": "concept_map", "operation": "update", "target_id": graph["id"],
                "base_revision": current["revision"],
                "content": {"graph": {**current["editable_graph"], "title": "混合图新版本"}}})
            review = repo.preview_category_change({
                "operation": "rename", "selection": {
                    "family": "concept_map_category", "name": "图原分类", "new_name": "图新分类"}})
            receipts.append(repo.approve_category_change({"ticket": review["ticket"]}))
            assert original_graph in [path.read_bytes() for path in (repo.history_dir / graph["id"]).glob("*.json")]
            trashed = repo.create_record({"type": "issue", "project_id": project["id"], "title": "仅回收对象"})
            repo.delete_record(trashed["id"])

            secret = b"AG143_PRIVATE_SOURCE_MARKER_72ea"
            source = base / "private-source.txt"
            source.write_bytes(secret)
            # The native handle validates fixed NTFS and ordinary-file identity.
            with LocalFileHandle(str(source), read=True) as handle:
                assert handle.initial["size"] == len(secret)
            file_grant = grant("files", {
                "path": str(source), "purposes": ["text_read"], "encoding": "utf-8",
                "max_bytes": len(secret), "duration_seconds": 600})
            policy = grant("upload-policy", {
                "owner_kind": "project", "owner_id": project["id"], "stream": True, "files": [],
                "max_bytes": len(secret), "duration_seconds": 600})
            upload = service.uploads.create(security.clients()[client_id], {
                "request_id": uuid.uuid4().hex, "policy_id": policy["policy_id"], "source": {"mode": "stream"},
                "owner_kind": "project", "owner_id": project["id"], "filename": "private-stage.txt",
                "bytes": len(secret), "sha256": hashlib.sha256(secret).hexdigest()})
            with urlopen(Request(
                workbench.base_url + f'/api/agent/v1/uploads/{upload["upload_id"]}/content',
                method="PUT", data=secret, headers={
                    "Authorization": "Bearer " + original_transport["token"], "X-Workbench-Workspace": workspace,
                    "Content-Type": "application/octet-stream"}), timeout=10) as response:
                assert response.status == 200
            assert list(service.uploads.directory.rglob("blob.bin"))
            file_id = file_grant["file_id"]
            assert service.get_file_info(security.clients()[client_id], file_id)["file_id"] == file_id
            [authorized_source] = local(f"clients/{client_id}/files")["items"]
            approved_path = authorized_source["path"]
            assert Path(approved_path).samefile(source)
            atomic_write_json(repo.config_dir / "settings.json", {"data_dir": str(repo.root)})
            atomic_write_json(repo.root / ".workbench-export.json", {"directory": str(base)})

            def snapshot():
                return tree_bytes(repo.root)

            before = snapshot()
            assert any(name.startswith(".agent/receipts/") for name in before)
            assert any(name.startswith(".trash/") for name in before)
            assert any(name.startswith(".workbench-document-uploads/") for name in before)
            assert str(repo.root).replace("\\", "\\\\").encode() in before["config/settings.json"]
            private_files = [path.read_bytes() for path in security.config_dir.rglob("*")
                             if path.is_file() and path.name != ".workbench-service.lock"]
            for marker in (file_id, upload["upload_id"], policy["policy_id"]):
                assert any(marker.encode() in raw for raw in private_files)
            assert any(original_transport["token"].encode() in raw for raw in private_files)
            assert any(secret == raw for raw in private_files)
            assert any(approved_path.replace("\\", "\\\\").encode() in raw for raw in private_files)
            archive = repo.export_zip()
            assert before == snapshot()
            excluded = (".agent/", ".trash/", ".workbench-document-uploads/")
            expected_files = {name: raw for name, raw in before.items()
                              if not name.startswith(excluded) and name != "config/settings.json"
                              and not Path(name).name.startswith(".workbench-")}
            assert any(name.startswith("history/") and name.endswith(".json") for name in expected_files)
            assert any(name.startswith("history/") and name.endswith(".md") for name in expected_files)
            for receipt in receipts:
                stored = read_json(service.store.receipts / (receipt["proposal_id"] + ".json"))
                assert stored == receipt
                assert service.store._load(receipt["proposal_id"], expire=False)["receipt"] == stored
            portable = base / "portable"
            portable.mkdir()
            with zipfile.ZipFile(io.BytesIO(archive)) as package:
                assert package.testzip() is None
                assert len(package.namelist()) == len(set(package.namelist()))
                exported = {name: package.read(name) for name in package.namelist()}
                assert exported == expected_files
                assert not any(name.split("/")[0] in {
                    ".agent", ".trash", ".workbench-document-uploads", "private",
                    "file-grants", "uploads", "management-operations"} for name in exported)
                assert "config/settings.json" not in exported and ".workbench-export.json" not in exported
                history_files = {name: raw for name, raw in before.items() if name.startswith("history/")}
                assert history_files and {name: exported[name] for name in history_files} == history_files
                private_markers = [
                    secret, original_transport["token"].encode(), str(base).encode(),
                    str(base).replace("\\", "\\\\").encode(), file_id.encode(),
                    upload["upload_id"].encode(), policy["policy_id"].encode(),
                    approved_path.encode(), approved_path.replace("\\", "\\\\").encode()]
                assert all(marker not in raw for raw in exported.values() for marker in private_markers)
                package.extractall(portable)
            reopened = Repository(portable)
            assert len(reopened.list_records()) == 3 and len(reopened.list_documents()) == 1
            assert reopened.list_trash() == []
            assert reopened.project_sort()["order"] == [project["id"]]
            assert reopened.document_sort()["file_orders"][destination] == [document["id"]]
            assert reopened.config()["workflow_templates"] == repo.config()["workflow_templates"]
            assert reopened.get_record(items["todo"])[0]["completed"] is True
            assert reopened.project(project["id"])["todo_record_order"] == [items["todo"]]
            assert "独立新分类" in [item["name"] for item in reopened.project_asset_categories(project["id"])]
            assert "图新分类" in reopened.concept_map_categories()
            assert reopened.get_concept_map(graph["id"])[1].read_bytes() == repo.get_concept_map(graph["id"])[1].read_bytes()
            assert reopened.get_record(items["info"])[0]["info_fields"] == repo.get_record(items["info"])[0]["info_fields"]
            for owner, name in ((items["issue"], record_asset["name"]), (document["id"], document_asset["name"])):
                assert reopened.attachment_path(owner, name).read_bytes() == binary
            assert reopened.project_asset_path(project["id"], project_asset["id"]).read_bytes() == binary
            restored_document, _ = reopened.get_document(document["id"])
            assert "[[" + document["id"] + "]]" in reopened.get_record(items["issue"])[0]["body"]
            assert record_reference in restored_document["body"]
            for metadata in attachment_items(restored_document["attachments"]):
                assert (portable / "documents" / metadata["path"]).resolve().read_bytes() == binary
            for _, link in local_links(restored_document["body"]):
                assert (portable / "documents" / unquote(link)).resolve().read_bytes() == binary

            # Knowledge-only export rewrites its copies; full export preserves original bytes and history.
            document_zip = repo.export_documents_zip([document["id"]])
            with zipfile.ZipFile(io.BytesIO(document_zip)) as package:
                assert package.testzip() is None
                [markdown] = [name for name in package.namelist() if name.endswith(".md")]
                meta, body = load_markdown_text(package.read(markdown).decode())
                for metadata in attachment_items(meta["attachments"]):
                    assert metadata["path"].startswith("assets/") and package.read(metadata["path"]) == binary
                for _, link in local_links(body):
                    assert package.read(unquote(link)) == binary
            assert before == snapshot()
            portable_runtime = AgentRuntime(reopened, base=base / "new-private")
            reopened.agent_runtime = portable_runtime
            assert portable_runtime.status()["workspace_id"] is None
            portable_runtime.set_enabled(True)
            new_security = portable_runtime.security()
            assert new_security.workspace_id != workspace and new_security.clients() == {}
            for identity in (workspace, new_security.workspace_id):
                try:
                    new_security.authenticate("Bearer " + original_transport["token"], identity)
                except AgentError as error:
                    assert error.code in {"workspace_mismatch", "unauthenticated"}
                else:
                    raise AssertionError("Portable copy accepted an old credential")
            fresh = new_security.add_client(
                "新空间只读身份", ["read"], [project["id"]], [destination],
                "http://127.0.0.1:4173", kinds=["issue", "document"])
            new_client = new_security.clients()[fresh["client_id"]]
            assert reopened.agent_service.list_file_grants(new_client)["items"] == []
            try:
                reopened.agent_service.get_file_info(new_client, file_id)
            except AgentError as error:
                assert error.code == "not_found"
            else:
                raise AssertionError("New portable client inherited an old file grant")
            workbench.close()
            stopped_port = workbench.server.server_address[1]
            workbench = None
            with socket.socket() as probe:
                assert probe.connect_ex(('127.0.0.1', stopped_port)) != 0
            stopped = verify_stopped_mixed_copies(
                base, repo, security, receipts, original_transport, file_id, source, secret, new_security)
            return {
                "passed": True, "business_types": ["project", "issue", "todo", "info", "document"],
                "attachment_owners": ["project", "issue", "document"],
                "raw_zip_files": len(expected_files), "original_receipts": len(receipts),
                "graph_and_markdown_history": True, "configuration_order_and_references": True,
                "portable_exact_bytes": True, "knowledge_copy_paths_rewritten": True,
                "private_grants_uploads_and_secret_excluded": True,
                "new_identity_empty_clients_old_credential_denied": True,
                "stopped_private_roots": stopped,
                "real_user_data_changed": False,
            }
        finally:
            if workbench is not None:
                port = workbench.server.server_address[1]
                workbench.close()
                with socket.socket() as probe:
                    assert probe.connect_ex(("127.0.0.1", port)) != 0


if __name__ == "__main__":
    print(json.dumps({**run_acceptance(), "mixed_portable": run_mixed_portable_acceptance()},
                     ensure_ascii=False, indent=2))
