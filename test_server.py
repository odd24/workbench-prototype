import tempfile
import unittest
import base64
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from server import Repository, directory_browser_payload, export_to_saved_location, load_markdown, relocate_repository, save_export_location


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_project_record_search_update_and_trash(self):
        project = self.repo.create_project({"name": "测试项目", "description": "本地存储测试"})
        record = self.repo.create_record({
            "type": "issue",
            "title": "Markdown 自动保存",
            "project_id": project["id"],
            "priority": "高",
            "tags": ["存储"],
            "body": "# Markdown 自动保存\n\n正文内容",
        })

        path = Path(record["file_path"])
        self.assertTrue(path.exists())
        metadata, body = load_markdown(path)
        self.assertEqual(metadata["id"], record["id"])
        self.assertIn("正文内容", body)

        updated = self.repo.update_record(record["id"], {"status": "处理中", "body": body + "\n\n已更新"})
        self.assertEqual(updated["status"], "处理中")
        self.assertIsInstance(updated["file_mtime"], int)
        self.assertEqual(len(self.repo.search("已更新")), 1)
        self.assertEqual(len(self.repo.list_history(record["id"])), 1)

        attachment = self.repo.add_attachment(record["id"], "截图.png", base64.b64encode(b"image-bytes").decode())
        self.assertEqual(attachment["name"], "截图.png")
        attachment_path = self.repo.attachment_path(record["id"], attachment["name"])
        self.assertEqual(attachment_path.read_bytes(), b"image-bytes")
        self.assertGreaterEqual(len(self.repo.list_history(record["id"])), 2)

        deleted = self.repo.delete_record(record["id"])
        self.assertFalse(path.exists())
        self.assertTrue(Path(deleted["trash_path"]).exists())

    def test_non_idea_requires_project(self):
        with self.assertRaisesRegex(ValueError, "必须选择项目"):
            self.repo.create_record({"type": "todo", "title": "无项目待办"})
        with self.assertRaisesRegex(ValueError, "必须选择项目"):
            self.repo.create_record({"type": "info", "title": "无项目信息"})

    def test_new_record_respects_selected_status(self):
        project = self.repo.create_project({"name": "状态归属项目"})
        record = self.repo.create_record({
            "type": "issue", "title": "直接归入已解决", "project_id": project["id"],
            "status": "已解决", "completed": True,
        })
        self.assertEqual(record["project_id"], project["id"])
        self.assertEqual(record["status"], "已解决")
        self.assertTrue(record["completed"])
        reordered = self.repo.update_project(project["id"], {"issue_status_order": ["处理中", "待处理", "分析中", "已解决"]})
        self.assertEqual(reordered["issue_status_order"][0], "处理中")
        self.assertEqual(self.repo.project(project["id"])["issue_status_order"], reordered["issue_status_order"])
        second = self.repo.create_record({"type": "issue", "title": "第二条问题", "project_id": project["id"]})
        record_order = self.repo.update_project(project["id"], {
            "issue_record_sort": "manual", "issue_record_order": [second["id"], record["id"]],
        })
        self.assertEqual(record_order["issue_record_sort"], "manual")
        self.assertEqual(record_order["issue_record_order"], [second["id"], record["id"]])
        per_status = self.repo.update_project(project["id"], {"issue_status_record_sorts": {"待处理": "priority", "处理中": "manual"}})
        self.assertEqual(per_status["issue_status_record_sorts"]["待处理"], "priority")
        with self.assertRaisesRegex(ValueError, "不支持的记录排序规则"):
            self.repo.update_project(project["id"], {"issue_record_sort": "random"})

    def test_global_idea_is_allowed(self):
        idea = self.repo.create_record({"type": "idea", "title": "未归属想法"})
        self.assertIsNone(idea["project_id"])
        self.assertTrue(Path(idea["file_path"]).exists())
        orphan = self.repo.global_assets_dir / "files" / "orphan.txt"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_text("unused", encoding="utf-8")
        self.assertEqual(len(self.repo.orphan_assets()), 1)
        self.assertEqual(self.repo.cleanup_orphan_assets()["removed"], 1)
        self.assertFalse(orphan.exists())

    def test_information_record_uses_structured_fields_without_status(self):
        project = self.repo.create_project({"name": "信息记录项目"})
        record = self.repo.create_record({
            "type": "info", "title": "生产环境信息", "project_id": project["id"],
            "info_fields": [{"name": "地址", "value": "https://example.com", "note": "生产环境入口"}, {"name": "负责人", "value": "小王"}],
            "info_color": "#7c5ce7",
            "body": "补充说明",
        })
        self.assertEqual(record["id"], "INFO-0001")
        self.assertNotIn("status", record)
        self.assertNotIn("priority", record)
        self.assertEqual(record["info_fields"][0]["name"], "地址")
        self.assertEqual(record["info_fields"][0]["note"], "生产环境入口")
        self.assertEqual(record["info_color"], "#7c5ce7")
        loaded, _ = self.repo.get_record(record["id"])
        self.assertEqual(loaded["info_fields"][1]["value"], "小王")
        self.assertEqual(loaded["info_fields"][0]["note"], "生产环境入口")
        updated = self.repo.update_record(record["id"], {"info_fields": [{"name": "版本", "value": "v2"}], "status": "不应保存"})
        self.assertEqual(updated["info_fields"], [{"name": "版本", "value": "v2"}])
        recolored = self.repo.update_record(record["id"], {"info_color": "#ef6b73"})
        self.assertEqual(recolored["info_color"], "#ef6b73")
        reloaded, _ = self.repo.get_record(record["id"])
        self.assertEqual(reloaded["info_color"], "#ef6b73")
        info_order = self.repo.update_project(project["id"], {"info_record_sort": "manual", "info_record_order": [record["id"]]})
        self.assertEqual(info_order["info_record_order"], [record["id"]])
        self.assertNotIn("status", updated)
        self.assertTrue(any(item["id"] == record["id"] for item in self.repo.search("v2")))

    def test_record_ids_stay_unique_during_concurrent_creation(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            created = list(pool.map(
                lambda index: self.repo.create_record({"type": "idea", "title": f"并发想法 {index}"}),
                range(24),
            ))
        ids = [record["id"] for record in created]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(self.repo.list_records(record_type="idea")), 24)

    def test_data_directory_can_be_migrated_and_persisted(self):
        created = self.repo.create_record({"type": "idea", "title": "迁移后仍存在"})
        with tempfile.TemporaryDirectory() as destination_parent:
            target = Path(destination_parent) / "new-location"
            location_file = Path(destination_parent) / "location.json"
            moved = relocate_repository(self.repo, str(target), True, location_file)
            self.assertEqual(moved.root, target.resolve())
            self.assertEqual(moved.get_record(created["id"])[0]["title"], "迁移后仍存在")
            self.assertEqual(json.loads(location_file.read_text(encoding="utf-8"))["data_dir"], str(target.resolve()))
            self.assertTrue(Path(created["file_path"]).exists(), "原目录应保留为备份")

    def test_status_templates_and_reminders(self):
        templates = self.repo.config()["status_templates"]
        templates["issue"].append({"id": "verify", "name": "待验证", "color": "#7856c8"})
        saved = self.repo.save_status_templates(templates)
        self.assertEqual(saved["issue"][-1]["name"], "待验证")
        workflows = self.repo.config()["workflow_templates"]
        workflows.append({"id": "simple", "name": "简单流程", "statuses": templates})
        self.assertEqual(len(self.repo.save_workflow_templates(workflows)), 2)
        project = self.repo.create_project({"name": "提醒项目"})
        self.assertEqual(self.repo.update_project(project["id"], {"workflow_template": "simple"})["workflow_template"], "simple")
        self.repo.create_record({"type": "todo", "title": "今天处理", "project_id": project["id"], "due": "2026-08-27"})
        self.assertEqual(len(self.repo.reminders()), 1)

    def test_used_workflow_status_cannot_be_removed_and_rename_migrates_status(self):
        project = self.repo.create_project({"name": "工作流安全项目"})
        kept = self.repo.create_record({
            "type": "issue", "title": "删除状态也必须保留", "project_id": project["id"], "status": "分析中",
        })
        renamed = self.repo.create_record({
            "type": "issue", "title": "状态改名应同步", "project_id": project["id"], "status": "处理中",
        })
        self.repo.update_project(project["id"], {
            "issue_status_order": ["待处理", "分析中", "处理中", "已解决"],
            "issue_status_record_sorts": {"处理中": "priority"},
        })
        workflows = self.repo.config()["workflow_templates"]
        standard = next(item for item in workflows if item["id"] == "standard")
        issue_statuses = standard["statuses"]["issue"]
        standard["statuses"]["issue"] = [item for item in issue_statuses if item["name"] != "分析中"]
        processing = next(item for item in standard["statuses"]["issue"] if item["name"] == "处理中")
        processing["name"] = "进行处理"

        before_ids = {item["id"] for item in self.repo.list_records()}
        with self.assertRaisesRegex(ValueError, "分析中.*正在被使用"):
            self.repo.save_workflow_templates(workflows)
        after_rejected = {item["id"]: item for item in self.repo.list_records()}
        self.assertEqual(set(after_rejected), before_ids, "拒绝删除状态时不得删除或遗漏任何记录")
        self.assertEqual(after_rejected[kept["id"]]["status"], "分析中")
        self.assertTrue(any(item["name"] == "分析中" for item in self.repo.config()["workflow_templates"][0]["statuses"]["issue"]))

        standard["statuses"]["issue"] = issue_statuses
        self.repo.save_workflow_templates(workflows)
        after = {item["id"]: item for item in self.repo.list_records()}

        self.assertEqual(set(after), before_ids)
        self.assertEqual(after[kept["id"]]["status"], "分析中")
        self.assertEqual(after[renamed["id"]]["status"], "进行处理", "状态改名按稳定 ID 同步到记录")
        self.assertTrue(Path(after[kept["id"]]["file_path"]).exists())
        self.assertEqual(self.repo.list_trash(), [], "工作流配置变更不得把记录移入回收站")
        updated_project = self.repo.project(project["id"])
        self.assertIn("进行处理", updated_project["issue_status_order"])
        self.assertNotIn("处理中", updated_project["issue_status_order"])
        self.assertEqual(updated_project["issue_status_record_sorts"]["进行处理"], "priority")
        workflows = self.repo.config()["workflow_templates"]
        standard = next(item for item in workflows if item["id"] == "standard")
        standard["statuses"]["issue"].append({"id": "unused", "name": "未使用状态", "color": "#64748b"})
        self.repo.save_workflow_templates(workflows)
        standard["statuses"]["issue"] = [item for item in standard["statuses"]["issue"] if item["id"] != "unused"]
        self.repo.save_workflow_templates(workflows)
        self.assertFalse(any(item["id"] == "unused" for item in self.repo.config()["workflow_templates"][0]["statuses"]["issue"]))

    def test_project_archive_tags_import_and_export(self):
        project = self.repo.create_project({"name": "可归档项目", "description": "测试归档"})
        archived = self.repo.update_project(project["id"], {"status": "archived"})
        self.assertEqual(archived["status"], "archived")
        tags = self.repo.save_tags([{"name": "前端", "color": "#123456"}])
        self.assertEqual(tags[0]["color"], "#123456")
        tagged = self.repo.create_record({"type": "idea", "title": "标签同步", "tags": ["前端"]})
        with self.assertRaisesRegex(ValueError, "前端.*正在被使用"):
            self.repo.save_tags({"tags": [], "renames": {}, "removed": ["前端"]})
        self.assertEqual(self.repo.get_record(tagged["id"])[0]["tags"], ["前端"])
        self.assertTrue(any(item["name"] == "前端" for item in self.repo.list_tags()))
        self.repo.save_tags({"tags": [{"name": "客户端", "color": "#123456"}], "renames": {"前端": "客户端"}, "removed": []})
        self.assertEqual(self.repo.get_record(tagged["id"])[0]["tags"], ["客户端"])
        self.repo.save_tags({"tags": [{"name": "客户端", "color": "#123456"}, {"name": "未使用标签", "color": "#64748b"}], "renames": {}, "removed": []})
        remaining = self.repo.save_tags({"tags": [{"name": "客户端", "color": "#123456"}], "renames": {}, "removed": ["未使用标签"]})
        self.assertFalse(any(item["name"] == "未使用标签" for item in remaining))
        imported = self.repo.import_markdown({"name": "灵感.md", "content": "# 导入的灵感\n\n正文"})
        self.assertEqual(imported["type"], "idea")
        with zipfile.ZipFile(io.BytesIO(self.repo.export_zip())) as archive:
            self.assertTrue(any(name.endswith("README.md") for name in archive.namelist()))
            self.assertTrue(any(name.endswith(".md") and "导入的灵感" in name for name in archive.namelist()))

    def test_export_location_is_validated_persisted_and_written(self):
        self.repo.create_record({"type": "idea", "title": "导出位置测试"})
        with tempfile.TemporaryDirectory() as destination_parent:
            directory = Path(destination_parent) / "Downloads"
            location_file = Path(destination_parent) / "export-location.json"
            saved = save_export_location(str(directory), location_file)
            self.assertEqual(saved["path"], str(directory.resolve()))
            result = export_to_saved_location(self.repo, None, "workbench-test.zip", location_file)
            destination = Path(result["path"])
            self.assertTrue(destination.exists())
            with zipfile.ZipFile(destination) as archive:
                self.assertTrue(any(name.endswith(".md") and "导出位置测试" in name for name in archive.namelist()))
            with self.assertRaisesRegex(ValueError, "文件名无效"):
                export_to_saved_location(self.repo, None, "../outside.zip", location_file)
            child = directory / "manually-selected"
            child.mkdir()
            browser = directory_browser_payload(str(directory))
            self.assertEqual(browser["path"], str(directory.resolve()))
            self.assertIn(str(child.resolve()), [item["path"] for item in browser["directories"]])

    def test_project_sort_rules_and_custom_order(self):
        beta = self.repo.create_project({"name": "Beta 项目"})
        alpha = self.repo.create_project({"name": "Alpha 项目"})
        custom = self.repo.save_project_sort({"mode": "custom", "order": [alpha["id"], beta["id"]]})
        self.assertEqual(custom["order"][:2], [alpha["id"], beta["id"]])
        self.assertEqual([item["id"] for item in self.repo.list_projects()][:2], [alpha["id"], beta["id"]])
        self.repo.save_project_sort({"mode": "name", "order": custom["order"]})
        self.assertEqual([item["name"] for item in self.repo.list_projects()][:2], ["Alpha 项目", "Beta 项目"])
        self.repo.create_record({"type": "issue", "title": "计数排序", "project_id": beta["id"]})
        self.repo.save_project_sort({"mode": "record_count", "order": custom["order"]})
        self.assertEqual(self.repo.list_projects()[0]["id"], beta["id"])

    def test_trash_restore_and_permanent_delete(self):
        project = self.repo.create_project({"name": "回收项目"})
        record = self.repo.create_record({"type": "todo", "title": "可恢复待办", "project_id": project["id"]})
        trashed = self.repo.delete_record(record["id"])
        self.assertEqual(len(self.repo.list_trash()), 1)
        restored = self.repo.restore_trash(trashed["token"])
        self.assertTrue(Path(restored["restored_path"]).exists())
        trashed_again = self.repo.delete_record(record["id"])
        purged = self.repo.purge_trash(trashed_again["token"])
        self.assertTrue(purged["purged"])
        self.assertEqual(self.repo.list_trash(), [])


if __name__ == "__main__":
    unittest.main()
