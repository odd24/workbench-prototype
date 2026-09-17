import io
import json
import tempfile
import unittest
from pathlib import Path

from server import Repository
from workbench.assets import AttachmentRepository


class AttachmentRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.temp.name))
        self.project = self.repo.create_project({"name": "附件仓储边界"})
        self.record = self.repo.create_record({"type": "issue", "title": "记录附件", "project_id": self.project["id"]})

    def tearDown(self):
        self.temp.cleanup()

    def test_repository_facade_uses_extracted_attachment_repository(self):
        self.assertIsInstance(self.repo._attachment_repository, AttachmentRepository)

        record_asset = self.repo.add_record_attachment_stream(self.record["id"], "record.txt", io.BytesIO(b"record"), 6)
        project_asset = self.repo.add_project_asset_stream(self.project["id"], "project.txt", io.BytesIO(b"project"), 7)

        self.assertEqual([item["name"] for item in self.repo.project_assets(self.project["id"])], ["project.txt"])
        self.assertEqual(self.repo.get_record(self.record["id"])[0]["attachments"][0]["name"], record_asset["name"])
        self.assertNotEqual(project_asset["id"], record_asset.get("id"))
        orphan_paths = {Path(item["path"]).resolve() for item in self.repo.orphan_assets()}
        self.assertNotIn(self.repo.project_asset_path(self.project["id"], project_asset["id"]).resolve(), orphan_paths)
        self.assertNotIn(self.repo.attachment_path(self.record["id"], record_asset["name"]).resolve(), orphan_paths)

    def test_duplicate_names_are_renamed_inside_expected_roots(self):
        first = self.repo.add_record_attachment_stream(self.record["id"], "same.txt", io.BytesIO(b"one"), 3)
        second = self.repo.add_record_attachment_stream(self.record["id"], "same.txt", io.BytesIO(b"two"), 3)
        project_first = self.repo.add_project_asset_stream(self.project["id"], "same.txt", io.BytesIO(b"one"), 3)
        project_second = self.repo.add_project_asset_stream(self.project["id"], "same.txt", io.BytesIO(b"two"), 3)

        self.assertEqual([first["name"], second["name"]], ["same.txt", "same-2.txt"])
        self.assertEqual([project_first["name"], project_second["name"]], ["same.txt", "same-2.txt"])
        for name in (first["name"], second["name"]):
            self.assertTrue(self.repo.attachment_path(self.record["id"], name).is_relative_to(self.repo.root))
        for asset in (project_first, project_second):
            self.assertTrue(self.repo.project_asset_path(self.project["id"], asset["id"]).is_relative_to(self.repo.projects_dir / self.project["id"]))

    def test_unportable_attachment_names_are_rejected(self):
        for name in ("../same.txt", "..\\same.txt", "CON.txt", "bad\x00name.txt", " trailing.txt "):
            with self.subTest(name=repr(name)):
                with self.assertRaisesRegex(ValueError, "文件名"):
                    self.repo.add_record_attachment_stream(self.record["id"], name, io.BytesIO(b"x"), 1)
                with self.assertRaisesRegex(ValueError, "文件名"):
                    self.repo.add_project_asset_stream(self.project["id"], name, io.BytesIO(b"x"), 1)

    def test_tampered_attachment_indexes_cannot_escape_asset_roots(self):
        project_readme = self.repo.projects_dir / self.project["id"] / "README.md"
        malicious = {"name": "README.md", "path": "../README.md", "size": project_readme.stat().st_size}
        self.repo.update_record(self.record["id"], {"attachments": [json.dumps(malicious)]})

        self.assertIsNone(self.repo.attachment_path(self.record["id"], "README.md"))
        self.repo.delete_record_attachment(self.record["id"], "README.md")
        self.assertTrue(project_readme.exists())

        asset_index = self.repo.projects_dir / self.project["id"] / "assets" / "index.json"
        asset_index.parent.mkdir(parents=True, exist_ok=True)
        asset_index.write_text(json.dumps([{"id": "ASSET-BAD", "name": "README.md", "path": "README.md"}]), encoding="utf-8")
        self.assertEqual(self.repo.project_assets(self.project["id"]), [])
        self.assertIsNone(self.repo.project_asset_path(self.project["id"], "ASSET-BAD"))

        unindexed = asset_index.parent / "library" / "unindexed.txt"
        unindexed.parent.mkdir(parents=True, exist_ok=True)
        unindexed.write_text("orphan", encoding="utf-8")
        self.repo.update_record(self.record["id"], {
            "attachments": [json.dumps({"name": "unindexed.txt", "path": "../assets/library/unindexed.txt"})],
        })
        orphan_paths = {Path(item["path"]).resolve() for item in self.repo.orphan_assets()}
        self.assertIn(unindexed.resolve(), orphan_paths)

    def test_incomplete_stream_upload_removes_partial_files(self):
        with self.assertRaisesRegex(ValueError, "上传不完整"):
            self.repo.add_record_attachment_stream(self.record["id"], "partial-record.bin", io.BytesIO(b"short"), 10)
        with self.assertRaisesRegex(ValueError, "上传不完整"):
            self.repo.add_project_asset_stream(self.project["id"], "partial-project.bin", io.BytesIO(b"short"), 10)

        self.assertEqual(list(self.repo.root.rglob("partial-record.bin")), [])
        self.assertEqual(list(self.repo.root.rglob("partial-project.bin")), [])


if __name__ == "__main__":
    unittest.main()
