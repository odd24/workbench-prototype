import json
import tempfile
import unittest
from pathlib import Path

from server import Repository
from workbench.projects import ProjectRepository
from workbench.records import RecordRepository


class ProjectRecordRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.repo = Repository(self.data_dir)

    def tearDown(self):
        self.temp.cleanup()

    def test_facade_uses_extracted_project_and_record_repositories(self):
        self.assertIsInstance(self.repo._project_repository, ProjectRepository)
        self.assertIsInstance(self.repo._record_repository, RecordRepository)
        self.assertIs(self.repo._record_cache, self.repo._record_repository._record_cache)

        project = self.repo.create_project({"name": "仓储边界"})
        record = self.repo.create_record({
            "type": "info",
            "title": "环境信息",
            "project_id": project["id"],
            "info_fields": [{"name": "命令", "value": "echo one\necho two"}],
        })
        updated = self.repo.update_record(record["id"], {"body": "# 环境信息\n\n已更新"})

        self.assertEqual(self.repo._project_repository.project(project["id"])["name"], "仓储边界")
        self.assertEqual(self.repo._record_repository.get_record(record["id"])[0]["body"], updated["body"])
        self.assertEqual(len(self.repo.list_history(record["id"])), 1)

        reloaded = Repository(self.data_dir)
        self.assertEqual(reloaded.get_record(record["id"])[0]["info_fields"][0]["value"], "echo one\necho two")
        self.assertEqual(len(reloaded.list_history(record["id"])), 1)

    def test_extracted_repositories_share_recoverable_trash_boundary(self):
        project = self.repo.create_project({"name": "回收站边界"})
        record = self.repo.create_record({"type": "todo", "title": "可恢复记录", "project_id": project["id"]})

        record_trash = self.repo.delete_record(record["id"])
        self.assertIsNone(self.repo.get_record(record["id"])[0])
        self.repo.restore_trash(record_trash["token"])
        self.assertEqual(self.repo.get_record(record["id"])[0]["title"], "可恢复记录")

        project_trash = self.repo.delete_project(project["id"])
        self.assertIsNone(self.repo.project(project["id"]))
        self.repo.restore_trash(project_trash["token"])
        self.assertEqual(self.repo.project(project["id"])["name"], "回收站边界")

    def test_tampered_trash_index_cannot_restore_outside_repository(self):
        project = self.repo.create_project({"name": "回收站路径保护"})
        record = self.repo.create_record({"type": "issue", "title": "不可越界恢复", "project_id": project["id"]})
        trashed = self.repo.delete_record(record["id"])
        outside = self.data_dir.parent / "outside-restored.md"
        index_path = self.repo.trash_dir / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index[trashed["token"]]["original_path"] = str(outside)
        index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "恢复路径无效"):
            self.repo.restore_trash(trashed["token"])
        self.assertFalse(outside.exists())
        self.assertTrue(Path(trashed["trash_path"]).exists())

    def test_tampered_trash_index_cannot_purge_trash_root(self):
        project = self.repo.create_project({"name": "回收站删除保护"})
        record = self.repo.create_record({"type": "todo", "title": "不可越界删除", "project_id": project["id"]})
        trashed = self.repo.delete_record(record["id"])
        index_path = self.repo.trash_dir / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index[trashed["token"]]["trash_path"] = str(self.repo.trash_dir)
        index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "回收站路径无效"):
            self.repo.purge_trash(trashed["token"])
        self.assertTrue(self.repo.trash_dir.exists())
        self.assertTrue(index_path.exists())


if __name__ == "__main__":
    unittest.main()
