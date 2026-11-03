import hashlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from server import Repository
from workbench.write_coordinator import DataDirectoryLock, RevisionConflict


class WriteCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = Repository(self.root)
        self.project = self.repo.create_project({"name": "并发验证"})

    def tearDown(self):
        self.temp.cleanup()

    def test_conditional_update_only_one_writer_wins_and_reload_preserves_it(self):
        for kind in ("record", "document"):
            create = getattr(self.repo, f"create_{kind}")
            update = getattr(self.repo, f"update_{kind}")
            item = create({"title": kind, "type": "issue", "project_id": self.project["id"], "body": "最初"})
            def write(value):
                try:
                    return update(item["id"], {"body": value, "expected_revision": item["revision"]})["body"]
                except RevisionConflict:
                    return "conflict"
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(write, ["first", "second"]))
            self.assertEqual(results.count("conflict"), 1)
            reloaded = getattr(Repository(self.root), f"get_{kind}")(item["id"])[0]
            self.assertIn(reloaded["body"], results)
            self.assertNotIn("revision:", Path(reloaded["file_path"]).read_text(encoding="utf-8"))
            self.assertEqual(reloaded["revision"], hashlib.sha256(Path(reloaded["file_path"]).read_bytes()).hexdigest())

    def test_document_ids_are_unique_and_history_restore_is_conditional(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            items = list(pool.map(lambda n: self.repo.create_document({"title": str(n), "body": f"正文 {n}"}), range(20)))
        self.assertEqual(len({item["id"] for item in items}), 20)
        item = items[0]
        updated = self.repo.update_document(item["id"], {"body": "修改", "expected_revision": item["revision"]})
        versions = self.repo.list_document_history(item["id"])
        self.assertEqual(self.repo.read_history(item["id"], versions[0]["version"])["body"], item["body"])
        with self.assertRaises(RevisionConflict):
            self.repo.restore_document_history(item["id"], versions[0]["version"], item["revision"])
        self.repo.restore_document_history(item["id"], versions[0]["version"], updated["revision"])
        self.assertEqual(Repository(self.root).get_document(item["id"])[0]["body"], item["body"])
        with self.assertRaises(ValueError):
            self.repo.read_history(item["id"], "../../escape")
        bad = self.root / "history" / item["id"] / "20000101-000000-000000.md"
        bad.write_text("broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.repo.restore_document_history(item["id"], bad.stem)

    def test_parser_race_never_pairs_old_body_with_new_revision(self):
        from workbench.markdown_io import load_markdown, dump_markdown
        from workbench.persistence import atomic_write_text
        item = self.repo.create_record({"type": "issue", "title": "读取竞态", "body": "旧正文", "project_id": self.project["id"]})
        path = Path(item["file_path"])
        self.repo._forget_record(path)
        original = self.repo._record_repository.load_markdown
        changed = False
        def racing_parser(source):
            nonlocal changed
            meta, body = original(source)
            if source == path and not changed:
                changed = True
                atomic_write_text(source, dump_markdown(meta, "新正文"))
            return meta, body
        self.repo._record_repository.load_markdown = racing_parser
        read, _ = self.repo.get_record(item["id"])
        self.assertEqual(read["body"], "新正文")
        self.assertEqual(read["revision"], hashlib.sha256(path.read_bytes()).hexdigest())
        with self.assertRaises(RevisionConflict):
            self.repo.update_record(item["id"], {"body": "旧页面保存", "expected_revision": item["revision"]})

    def test_change_after_initial_version_check_is_not_overwritten(self):
        from workbench.markdown_io import load_markdown, dump_markdown
        from workbench.persistence import atomic_write_text
        from workbench.write_coordinator import check_revision
        item = self.repo.create_record({"type": "issue", "title": "条件检查竞态", "body": "原文", "project_id": self.project["id"]})
        path = Path(item["file_path"])
        def check_then_change(source, payload):
            check_revision(source, payload)
            meta, _ = load_markdown(source)
            atomic_write_text(source, dump_markdown(meta, "外部刚刚保存"))
        with patch("workbench.records.check_revision", side_effect=check_then_change):
            with self.assertRaises(RevisionConflict):
                self.repo.update_record(item["id"], {"body": "不能覆盖", "expected_revision": item["revision"]})
        self.assertEqual(load_markdown(path)[1], "外部刚刚保存")

    def test_category_migration_keeps_revision_out_of_metadata_and_saves_history(self):
        doc = self.repo.create_document({"title": "分类迁移", "category": "旧分类"})
        self.repo.rename_document_category("旧分类", "新分类")
        self.repo.delete_document_category("新分类")
        reloaded = Repository(self.root).get_document(doc["id"])[0]
        self.assertEqual(reloaded["category"], "未分类")
        self.assertNotIn("revision:", Path(reloaded["file_path"]).read_text(encoding="utf-8"))
        self.assertEqual(len(self.repo.list_document_history(doc["id"])), 2)

    def test_posix_lock_branch_uses_nonblocking_flock_and_releases(self):
        fake = SimpleNamespace(flock=Mock(), LOCK_EX=2, LOCK_NB=4, LOCK_UN=8)
        with patch("workbench.write_coordinator.os", SimpleNamespace(name="posix")), patch.dict(sys.modules, {"fcntl": fake}):
            lock = DataDirectoryLock(self.root)
            lock.close()
        self.assertEqual([call.args[1] for call in fake.flock.call_args_list], [6, 8])

    def test_service_directory_lock_excludes_other_processes_and_releases(self):
        script = "from pathlib import Path; from workbench.write_coordinator import DataDirectoryLock; import sys; lock=DataDirectoryLock(Path(sys.argv[1])); lock.close()"
        lock = DataDirectoryLock(self.root)
        try:
            result = subprocess.run([sys.executable, "-c", script, str(self.root)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
        finally:
            lock.close()
        result = subprocess.run([sys.executable, "-c", script, str(self.root)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
