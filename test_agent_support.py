"""Isolated fixtures shared by Agent domain and recovery tests."""

import tempfile
import uuid
from pathlib import Path

from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService


class AgentFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = Repository(self.base / "data")
        self.project = self.repo.create_project({"name": "Agent 验收"})
        self.repo.ensure_document_category("允许")
        self.security = AgentSecurity(self.repo.root, self.base / "credentials")
        info = self.security.add_client("验收", ["read", "propose", "commit"], ["*"], ["*"], "http://127.0.0.1:4174")
        self.client = self.security.clients()[info["client_id"]]
        self.service = AgentService(self.repo, self.security)
        self.store = self.service.store

    def tearDown(self):
        self.temp.cleanup()

    def spec(self, kind="issue", operation="create", **overrides):
        content = {"title": "问题或知识总结", "body": "原始正文\n\n```sh\necho 'hello'\n```", "tags": []}
        content.update({"project_id": self.project["id"]} if kind == "issue" else {"category": "允许"})
        return {"request_id": uuid.uuid4().hex, "kind": kind, "operation": operation, "content": content, **overrides}

    def confirmation(self, preview):
        return {"version": preview["version"], "preview_digest": preview["preview_digest"],
                "confirmation": {"mode": "agent_attested", "user_confirmed": True, "note": "用户已确认预览"}}

    def prepare_preview(self, spec=None):
        proposal = self.service.prepare_proposal(self.client, spec or self.spec())
        return self.service.preview_proposal(self.client, proposal["proposal_id"])

    def commit(self, preview):
        return self.service.commit_proposal(self.client, preview["proposal_id"], self.confirmation(preview))

    def reload(self):
        self.repo = Repository(self.repo.root)
        self.service = AgentService(self.repo, self.security)
        self.store = self.service.store
