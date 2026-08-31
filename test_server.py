import tempfile
import unittest
import base64
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from server import Repository, directory_browser_payload, dump_markdown, export_to_saved_location, external_editor_payload, load_markdown, relocate_repository, save_export_location, save_external_editor


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

    def test_record_cache_reuses_parse_and_detects_external_edits(self):
        project = self.repo.create_project({"name": "缓存测试"})
        record = self.repo.create_record({"type": "issue", "title": "初始标题", "project_id": project["id"]})
        path = Path(record["file_path"])
        self.repo._record_cache.clear()

        with patch("server.load_markdown", wraps=load_markdown) as loader:
            self.assertEqual(self.repo.list_records()[0]["title"], "初始标题")
            first_count = loader.call_count
            self.repo.list_records()
            self.repo.record_signatures()
            self.assertEqual(loader.call_count, first_count)

            metadata, body = load_markdown(path)
            metadata["title"] = "外部修改"
            path.write_text(dump_markdown(metadata, body), encoding="utf-8")
            self.assertEqual(self.repo.list_records()[0]["title"], "外部修改")
            self.assertEqual(loader.call_count, first_count + 1)

    def test_record_summaries_omit_heavy_detail_fields(self):
        project = self.repo.create_project({"name": "摘要测试"})
        record = self.repo.create_record({
            "type": "issue", "title": "按需加载", "project_id": project["id"],
            "body": "# 按需加载\n\n" + "正文" * 500,
            "attachments": [{"name": "large.bin", "path": "assets/large.bin"}],
        })

        summary = self.repo.list_record_summaries()[0]
        self.assertEqual(summary["id"], record["id"])
        self.assertNotIn("body", summary)
        self.assertNotIn("attachments", summary)
        self.assertNotIn("file_path", summary)
        self.assertLessEqual(len(summary["body_preview"]), 600)
        self.assertIn("正文", summary["body_preview"])

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

    def test_record_can_open_in_external_markdown_editor(self):
        project = self.repo.create_project({"name": "外部编辑项目"})
        record = self.repo.create_record({"type": "issue", "title": "Typora 测试", "project_id": project["id"]})
        with patch("server.open_markdown_external", return_value="Typora") as opener:
            result = self.repo.open_record_external(record["id"])
        self.assertEqual(result["editor"], "Typora")
        self.assertEqual(result["record_id"], record["id"])
        opener.assert_called_once()
        self.assertEqual(opener.call_args.args[0], Path(record["file_path"]))

    def test_document_can_open_in_external_markdown_editor(self):
        document = self.repo.create_document({"title": "外部编辑文档", "body": "# 外部编辑文档"})
        with patch("server.open_markdown_external", return_value="Visual Studio Code") as opener:
            result = self.repo.open_document_external(document["id"])
        self.assertEqual(result["editor"], "Visual Studio Code")
        self.assertEqual(result["document_id"], document["id"])
        opener.assert_called_once_with(Path(document["file_path"]))

    def test_external_editor_selection_is_persisted(self):
        config_file = Path(self.temp.name) / "editor.json"
        detected = [{"id": "vscode", "name": "Visual Studio Code", "path": "C:/Code.exe", "kind": "detected"}, {"id": "system", "name": "系统默认 Markdown 编辑器", "path": "", "kind": "system"}]
        with patch("server.detected_external_editors", return_value=detected):
            saved = save_external_editor("vscode", config_file=config_file)
            loaded = external_editor_payload(config_file)
        self.assertEqual(saved["selected"], "vscode")
        self.assertEqual(loaded["selected_name"], "Visual Studio Code")
        self.assertEqual(json.loads(config_file.read_text(encoding="utf-8"))["id"], "vscode")

    def test_custom_external_editor_path_is_supported(self):
        config_file = Path(self.temp.name) / "editor.json"
        executable = Path(self.temp.name) / "MyEditor.exe"
        executable.write_bytes(b"")
        saved = save_external_editor("custom", str(executable), config_file)
        self.assertEqual(saved["selected"], "custom")
        self.assertEqual(saved["selected_name"], "MyEditor")

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

    def test_status_templates_and_workflows(self):
        templates = self.repo.config()["status_templates"]
        templates["issue"].append({"id": "verify", "name": "待验证", "color": "#7856c8"})
        saved = self.repo.save_status_templates(templates)
        self.assertEqual(saved["issue"][-1]["name"], "待验证")
        workflows = self.repo.config()["workflow_templates"]
        workflows.append({"id": "simple", "name": "简单流程", "statuses": templates})
        self.assertEqual(len(self.repo.save_workflow_templates(workflows)), 2)
        project = self.repo.create_project({"name": "工作流项目"})
        self.assertEqual(self.repo.update_project(project["id"], {"workflow_template": "simple"})["workflow_template"], "simple")

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

    def test_project_independent_assets_can_be_uploaded_and_categorized(self):
        project = self.repo.create_project({"name": "附件库项目"})
        asset = self.repo.add_project_asset(
            project["id"], "需求说明.txt", base64.b64encode("项目附件内容".encode()).decode(), "需求文档",
        )
        self.assertEqual(asset["category"], "需求文档")
        self.assertEqual(len(self.repo.project_assets(project["id"])), 1)
        path = self.repo.project_asset_path(project["id"], asset["id"])
        self.assertEqual(path.read_text(encoding="utf-8"), "项目附件内容")
        updated = self.repo.update_project_asset(project["id"], asset["id"], {"category": "交付资料"})
        self.assertEqual(updated["category"], "交付资料")
        categories = self.repo.save_project_asset_categories(project["id"], [{"name": "交付资料", "tag": "交付"}])
        self.assertEqual(categories, [{"name": "交付资料", "tag": "交付"}])
        self.assertNotIn(path.resolve(), {Path(item["path"]).resolve() for item in self.repo.orphan_assets()})
        with zipfile.ZipFile(io.BytesIO(self.repo.export_zip(project["id"]))) as archive:
            self.assertIn("assets/library/需求说明.txt", archive.namelist())
            self.assertIn("assets/index.json", archive.namelist())

    def test_assets_support_unlimited_stream_batch_category_and_confirmable_delete_backend(self):
        project = self.repo.create_project({"name": "批量附件项目"})
        record = self.repo.create_record({"type": "issue", "title": "包含记录附件", "project_id": project["id"]})
        large_size = 10 * 1024 * 1024 + 1
        project_asset = self.repo.add_project_asset_stream(project["id"], "large.bin", io.BytesIO(b"x" * large_size), large_size, "大文件")
        self.assertEqual(project_asset["size"], large_size)
        record_asset = self.repo.add_record_attachment_stream(record["id"], "record.txt", io.BytesIO(b"record"), 6)
        selections = [
            {"source": "project", "id": project_asset["id"]},
            {"source": "record", "record_id": record["id"], "name": record_asset["name"]},
        ]
        changed = self.repo.batch_update_assets(project["id"], selections, "统一资料")
        self.assertEqual(changed["updated"], 2)
        self.assertEqual(self.repo.project_assets(project["id"])[0]["category"], "统一资料")
        parsed_record_attachment = self.repo.get_record(record["id"])[0]["attachments"][0]
        if isinstance(parsed_record_attachment, str):
            parsed_record_attachment = json.loads(parsed_record_attachment)
        self.assertEqual(parsed_record_attachment["category"], "统一资料")
        self.repo.save_project_asset_categories(project["id"], [])
        self.assertEqual(self.repo.project_assets(project["id"])[0]["category"], "")
        cleared_record_attachment = self.repo.get_record(record["id"])[0]["attachments"][0]
        if isinstance(cleared_record_attachment, str):
            cleared_record_attachment = json.loads(cleared_record_attachment)
        self.assertEqual(cleared_record_attachment["category"], "")
        removed = self.repo.batch_delete_assets(project["id"], selections)
        self.assertEqual(removed["deleted"], 2)
        self.assertEqual(self.repo.project_assets(project["id"]), [])
        refreshed_record = self.repo.get_record(record["id"])[0]
        self.assertEqual(refreshed_record["attachments"], [])
        self.assertNotIn("record.txt", refreshed_record["body"])

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

    def test_trash_batch_restore_and_permanent_delete(self):
        project = self.repo.create_project({"name": "批量回收站"})
        first = self.repo.create_record({"type": "issue", "title": "恢复一", "project_id": project["id"]})
        second = self.repo.create_record({"type": "todo", "title": "恢复二", "project_id": project["id"]})
        first_trash = self.repo.delete_record(first["id"])
        second_trash = self.repo.delete_record(second["id"])

        restored = self.repo.batch_restore_trash({"tokens": [first_trash["token"], second_trash["token"]]})
        self.assertEqual(restored["count"], 2)
        self.assertEqual({item["id"] for item in self.repo.list_records()}, {first["id"], second["id"]})

        first_trash = self.repo.delete_record(first["id"])
        second_trash = self.repo.delete_record(second["id"])
        purged = self.repo.batch_purge_trash({"tokens": [first_trash["token"], second_trash["token"]]})
        self.assertEqual(purged["count"], 2)
        self.assertEqual(self.repo.list_trash(), [])

    def test_documents_support_categories_editing_and_trash(self):
        self.repo.save_tags([{"name": "后端", "color": "#123456"}])
        document = self.repo.create_document({"title": "接口规范", "document_type": "技术文档", "category": "后端", "tags": ["后端"], "body": "# 接口规范\n\n正文"})
        self.assertEqual(document["id"], "DOC-0001")
        self.assertEqual(document["category"], "后端")
        self.assertNotIn("document_type", document)
        self.assertEqual(document["tags"], ["后端"])
        self.repo.save_tags({"tags": [{"name": "服务端", "color": "#123456"}], "renames": {"后端": "服务端"}, "removed": []})
        self.assertEqual(self.repo.get_document(document["id"])[0]["tags"], ["服务端"])
        updated = self.repo.update_document(document["id"], {"title": "接口说明", "document_type": "说明文档", "category": "公共", "tags": ["服务端"], "body": "新正文"})
        self.assertNotIn("document_type", updated)
        self.assertEqual(updated["category"], "公共")
        self.assertEqual(self.repo.get_document(document["id"])[0]["body"], "新正文")
        trashed = self.repo.delete_document(document["id"])
        self.assertEqual(trashed["kind"], "document")
        self.assertEqual(self.repo.list_documents(), [])
        self.repo.restore_trash(trashed["token"])
        self.assertEqual(len(self.repo.list_documents()), 1)

    def test_knowledge_base_import_and_export(self):
        imported = self.repo.import_document({"name": "部署手册.md", "content": "---\ndocument_type: \"说明文档\"\ncategory: \"运维\"\n---\n# 部署手册\n\n部署步骤"})
        self.assertEqual(imported["title"], "部署手册")
        self.assertNotIn("document_type", imported)
        self.assertEqual(imported["category"], "运维")
        content, filename = self.repo.export_document(imported["id"])
        self.assertEqual(filename, "DOC-0001.md")
        self.assertIn("部署步骤", content.decode("utf-8"))
        self.assertNotIn("document_type", content.decode("utf-8"))
        with zipfile.ZipFile(io.BytesIO(self.repo.export_documents_zip())) as archive:
            self.assertEqual(len(archive.namelist()), 1)
            exported = archive.read(archive.namelist()[0]).decode("utf-8")
            self.assertIn("部署步骤", exported)
            self.assertNotIn("document_type", exported)
        second = self.repo.create_document({"title": "第二篇", "body": "不应导出"})
        with zipfile.ZipFile(io.BytesIO(self.repo.export_documents_zip([imported["id"]]))) as archive:
            self.assertEqual(len(archive.namelist()), 1)
            self.assertNotIn(second["id"], archive.namelist()[0])

    def test_document_sort_supports_separate_category_and_file_orders(self):
        first = self.repo.create_document({"title": "乙文档", "category": "技术"})
        second = self.repo.create_document({"title": "甲文档", "category": "技术"})
        third = self.repo.create_document({"title": "部署文档", "category": "运维"})
        manual = self.repo.save_document_sort({
            "category_mode": "manual", "category_order": ["运维", "技术"],
            "file_mode": "manual", "file_orders": {"技术": [second["id"], first["id"]], "运维": [third["id"]]},
        })
        self.assertEqual(manual["category_order"], ["运维", "技术"])
        self.assertEqual(manual["file_orders"]["技术"], [second["id"], first["id"]])
        configured = self.repo.config()["document_sort"]
        self.assertEqual(configured["category_mode"], "manual")
        self.assertEqual(configured["file_mode"], "manual")
        per_category = self.repo.save_document_sort({"file_modes": {"技术": "title", "运维": "created"}})
        self.assertEqual(per_category["file_modes"], {"技术": "title", "运维": "created"})
        automatic = self.repo.save_document_sort({"category_mode": "count", "file_mode": "title"})
        self.assertEqual(automatic["category_mode"], "count")
        self.assertEqual(automatic["file_mode"], "title")
        with self.assertRaises(ValueError):
            self.repo.save_document_sort({"category_mode": "unknown"})
        with self.assertRaises(ValueError):
            self.repo.save_document_sort({"file_mode": "unknown"})
        with self.assertRaises(ValueError):
            self.repo.save_document_sort({"file_modes": {"技术": "unknown"}})

    def test_empty_document_categories_can_be_created_and_persisted(self):
        categories = self.repo.save_document_categories(["产品设计", "技术资料"])
        self.assertEqual(categories, ["产品设计", "技术资料"])
        self.assertEqual(self.repo.config()["document_categories"], categories)
        sorting = self.repo.save_document_sort({"category_mode": "manual", "category_order": ["技术资料", "产品设计"]})
        self.assertEqual(sorting["category_order"], ["技术资料", "产品设计"])
        document = self.repo.create_document({"title": "部署说明", "category": "运维文档"})
        self.assertEqual(document["category"], "运维文档")
        self.assertEqual(self.repo.document_categories(), ["产品设计", "技术资料", "运维文档"])

    def test_document_category_rename_migrates_documents_and_sorting(self):
        self.repo.save_document_categories(["技术资料", "空分类"])
        first = self.repo.create_document({"title": "接口规范", "category": "技术资料"})
        second = self.repo.create_document({"title": "代码约定", "category": "技术资料"})
        self.repo.save_document_sort({
            "category_mode": "manual", "category_order": ["空分类", "技术资料"],
            "file_modes": {"技术资料": "manual"}, "file_orders": {"技术资料": [second["id"], first["id"]]},
        })
        renamed = self.repo.rename_document_category("技术资料", "研发资料")
        self.assertEqual(renamed["updated_documents"], 2)
        self.assertEqual(renamed["categories"], ["研发资料", "空分类"])
        self.assertEqual(renamed["document_sort"]["category_order"], ["空分类", "研发资料"])
        self.assertEqual(renamed["document_sort"]["file_modes"]["研发资料"], "manual")
        self.assertEqual(renamed["document_sort"]["file_orders"]["研发资料"], [second["id"], first["id"]])
        self.assertTrue(all(document["category"] == "研发资料" for document in self.repo.list_documents()))
        with self.assertRaises(ValueError):
            self.repo.rename_document_category("研发资料", "空分类")


if __name__ == "__main__":
    unittest.main()
