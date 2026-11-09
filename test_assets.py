import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        # Unknown/malicious metadata no longer proves lack of references.
        self.assertNotIn(unindexed.resolve(), orphan_paths)
        self.assertTrue(self.repo.orphan_asset_report()['warnings'])
        self.assertEqual(self.repo.cleanup_orphan_assets()['removed'], 0)
        self.assertTrue(unindexed.exists())

    def test_incomplete_stream_upload_removes_partial_files(self):
        with self.assertRaisesRegex(ValueError, "上传不完整"):
            self.repo.add_record_attachment_stream(self.record["id"], "partial-record.bin", io.BytesIO(b"short"), 10)
        with self.assertRaisesRegex(ValueError, "上传不完整"):
            self.repo.add_project_asset_stream(self.project["id"], "partial-project.bin", io.BytesIO(b"short"), 10)

        self.assertEqual(list(self.repo.root.rglob("partial-record.bin")), [])
        self.assertEqual(list(self.repo.root.rglob("partial-project.bin")), [])

    def test_indexed_attachments_open_with_external_applications(self):
        record_asset = self.repo.add_record_attachment_stream(self.record["id"], "说明.md", io.BytesIO(b"markdown"), 8)
        project_asset = self.repo.add_project_asset_stream(self.project["id"], "调试工具.exe", io.BytesIO(b"binary"), 6)

        with patch("server.open_file_external", side_effect=["Typora", "系统默认应用"]) as opener:
            record_result = self.repo.open_record_attachment_external(self.record["id"], record_asset["name"])
            project_result = self.repo.open_project_asset_external(self.project["id"], project_asset["id"])

        self.assertEqual(record_result["application"], "Typora")
        self.assertEqual(project_result["application"], "系统默认应用")
        self.assertEqual(opener.call_args_list[0].args[0], self.repo.attachment_path(self.record["id"], record_asset["name"]))
        self.assertEqual(opener.call_args_list[1].args[0], self.repo.project_asset_path(self.project["id"], project_asset["id"]))

    def test_unindexed_attachments_cannot_be_opened_externally(self):
        with patch("server.open_file_external") as opener:
            with self.assertRaises(FileNotFoundError):
                self.repo.open_record_attachment_external(self.record["id"], "missing.txt")
            with self.assertRaises(FileNotFoundError):
                self.repo.open_project_asset_external(self.project["id"], "ASSET-MISSING")
        opener.assert_not_called()


    def test_prepared_attachment_preview_is_read_only_and_preserves_info_metadata(self):
        from workbench.write_coordinator import content_revision
        info = self.repo.create_record({'type':'info', 'title':'信息', 'project_id':self.project['id'],
                                        'info_fields':[{'name':'说明', 'value':'  a\n"b"  ', 'note':'末尾 '}]})
        path = Path(info['file_path'])
        original = path.read_bytes()
        original_paths = sorted(str(item) for item in self.repo.root.rglob("*"))
        draft = self.repo.prepare_attachment_create('info', info['id'], '说明[方](圆)%#&.txt', 1, 'a' * 64, '', True,
                                                     content_revision(original), 'ASSET-fixed')
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(sorted(str(item) for item in self.repo.root.rglob("*")), original_paths)
        self.assertEqual(draft.view['metadata_after']['info_fields'], draft.view['metadata_before']['info_fields'])
        self.assertEqual(draft.view['attachment']['name'], '说明[方](圆)%#&.txt')
        self.assertIn('%28', draft.view['body'])
        self.assertIn('%25%23', draft.view['body'])
        draft.binary_path.parent.mkdir(parents=True, exist_ok=True)
        draft.binary_path.write_bytes(b'x')
        draft.record_write.history_version = '20261109-000000-000000-12345678'
        self.repo.apply_attachment_metadata(draft)
        reopened = Repository(self.repo.root)
        self.assertEqual(reopened.get_record(info['id'])[0]['info_fields'], info['info_fields'])
        self.assertEqual(reopened.attachment_path(info['id'], '说明[方](圆)%#&.txt').read_bytes(), b'x')

    def test_prepared_project_index_has_revision_and_does_not_create_asset_directories(self):
        from workbench.write_coordinator import content_revision, RevisionConflict
        draft = self.repo.prepare_attachment_create('project', self.project['id'], '索引.txt', 1, 'a' * 64, '', False,
                                                     content_revision(b''), 'ASSET-fixed')
        self.assertFalse(draft.metadata_path.exists())
        self.assertFalse(draft.binary_path.parent.exists())
        with self.assertRaises(ValueError):
            self.repo.prepare_attachment_create('project', self.project['id'], '索引.txt', 1, 'a' * 64, '', True,
                                                content_revision(b''), 'ASSET-fixed')
        draft.binary_path.parent.mkdir(parents=True)
        draft.binary_path.write_bytes(b'x')
        self.repo.apply_attachment_metadata(draft)
        self.assertEqual(Repository(self.repo.root).project_assets(self.project['id'])[0]['id'], 'ASSET-fixed')
        with self.assertRaises(RevisionConflict):
            self.repo.apply_attachment_metadata(draft)


if __name__ == "__main__":
    unittest.main()
