import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from server import Repository
from workbench.persistence import atomic_write_bytes, atomic_write_json, atomic_write_text


class AtomicPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_text_bytes_and_json_replace_with_exact_content(self):
        text_path = self.root / "nested" / "record.md"
        atomic_write_text(text_path, "中文正文\n")
        self.assertEqual(text_path.read_bytes(), "中文正文\n".encode("utf-8"))

        binary_path = self.root / "payload.bin"
        atomic_write_bytes(binary_path, b"\x00atomic\xff")
        self.assertEqual(binary_path.read_bytes(), b"\x00atomic\xff")

        json_path = self.root / "config.json"
        atomic_write_json(json_path, {"名称": "工作台", "items": [1, 2]})
        self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), {"名称": "工作台", "items": [1, 2]})

    def test_replace_failure_keeps_old_file_and_cleans_temporary_file(self):
        destination = self.root / "settings.json"
        destination.write_text("old", encoding="utf-8")

        with patch("workbench.persistence.os.replace", side_effect=OSError("模拟替换中断")):
            with self.assertRaisesRegex(OSError, "模拟替换中断"):
                atomic_write_text(destination, "new")

        self.assertEqual(destination.read_text(encoding="utf-8"), "old")
        self.assertEqual(list(self.root.glob(".settings.json.*.tmp")), [])

    def test_fsync_failure_keeps_old_file_and_cleans_temporary_file(self):
        destination = self.root / "index.json"
        destination.write_text("old-index", encoding="utf-8")

        with patch("workbench.persistence.os.fsync", side_effect=OSError("模拟写入中断")):
            with self.assertRaisesRegex(OSError, "模拟写入中断"):
                atomic_write_json(destination, {"new": True})

        self.assertEqual(destination.read_text(encoding="utf-8"), "old-index")
        self.assertEqual(list(self.root.glob(".index.json.*.tmp")), [])

    def test_concurrent_writers_leave_one_complete_value_without_temporary_files(self):
        destination = self.root / "shared.json"
        payloads = [{"writer": index, "content": "值" * 200} for index in range(12)]

        with ThreadPoolExecutor(max_workers=6) as executor:
            list(executor.map(lambda payload: atomic_write_json(destination, payload), payloads))

        self.assertIn(json.loads(destination.read_text(encoding="utf-8")), payloads)
        self.assertEqual(list(self.root.glob(".shared.json.*.tmp")), [])

    def test_record_update_failure_preserves_disk_source_and_reload(self):
        repo = Repository(self.root / "data")
        project = repo.create_project({"name": "原子写入项目"})
        record = repo.create_record({
            "type": "todo", "title": "原始记录", "project_id": project["id"], "body": "旧正文",
        })
        source = Path(record["file_path"])
        original = source.read_bytes()

        with patch("workbench.records.atomic_write_text", side_effect=OSError("模拟记录写入中断")):
            with self.assertRaisesRegex(OSError, "模拟记录写入中断"):
                repo.update_record(record["id"], {"title": "不应落盘", "body": "新正文"})

        self.assertEqual(source.read_bytes(), original)
        reloaded = Repository(repo.root).get_record(record["id"])[0]
        self.assertEqual((reloaded["title"], reloaded["body"]), ("原始记录", "旧正文"))
        self.assertEqual(list(source.parent.glob(f".{source.name}.*.tmp")), [])

    def test_configuration_failure_preserves_previous_json(self):
        repo = Repository(self.root / "config-data")
        target = repo.config_dir / "project-sort.json"
        original = target.read_bytes()

        with patch("workbench.configuration.atomic_write_json", side_effect=OSError("模拟配置写入中断")):
            with self.assertRaisesRegex(OSError, "模拟配置写入中断"):
                repo.save_project_sort({"mode": "name", "order": []})

        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(Repository(repo.root).project_sort(), {"mode": "custom", "order": []})

    def test_persisted_markdown_and_json_do_not_use_direct_overwrite(self):
        allowed_direct_bytes = {"assets.py"}
        for source in (Path(__file__).parent / "workbench").glob("*.py"):
            if source.name == "persistence.py":
                continue
            content = source.read_text(encoding="utf-8")
            self.assertNotIn(".write_text(", content, source.name)
            if source.name not in allowed_direct_bytes:
                self.assertNotIn(".write_bytes(", content, source.name)


if __name__ == "__main__":
    unittest.main()
