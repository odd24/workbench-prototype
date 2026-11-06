"""Explicit disposable extension backup/restore and Agent-off acceptance.

No real user data, credentials or client configuration is used. Remote and
non-Codex interoperability remain separate external gates.
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from codex_agent_acceptance import LocalWorkbench
from server import Repository
from workbench.agent_proposal_management import ProposalManagement
from workbench.agent_runtime import AgentRuntime
from workbench.agent_security import AgentSecurity, read_json


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


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2))
