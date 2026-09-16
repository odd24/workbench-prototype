import tempfile
import unittest
from pathlib import Path

import server
from workbench.markdown_io import (
    dump_markdown,
    load_markdown,
    load_markdown_text,
    normalize_info_fields,
    now_iso,
    parse_scalar,
    slugify,
    yaml_scalar,
)


BASELINE_DATA_DIR = Path(__file__).resolve().parent / "test-fixtures" / "baseline-data"


class MarkdownContractTests(unittest.TestCase):
    def test_server_keeps_compatible_markdown_helper_exports(self):
        self.assertIs(server.dump_markdown, dump_markdown)
        self.assertIs(server.load_markdown, load_markdown)
        self.assertIs(server.load_markdown_text, load_markdown_text)
        self.assertIs(server.normalize_info_fields, normalize_info_fields)
        self.assertIs(server.now_iso, now_iso)
        self.assertIs(server.parse_scalar, parse_scalar)
        self.assertIs(server.slugify, slugify)
        self.assertIs(server.yaml_scalar, yaml_scalar)

    def test_front_matter_scalars_and_mixed_lists(self):
        metadata, body = load_markdown_text(
            "---\r\n"
            "title: \"中文 🧪\"\r\n"
            "count: 3\r\n"
            "ratio: 1.5\r\n"
            "active: true\r\n"
            "missing: null\r\n"
            "plain: text: with colon\r\n"
            "values:\r\n"
            "  - \"列表项\"\r\n"
            "  - 7\r\n"
            "  - false\r\n"
            "---\r\n"
            "\r\n"
            "正文 Unicode：你好，世界。\r\n"
        )

        self.assertEqual(metadata, {
            "title": "中文 🧪",
            "count": 3,
            "ratio": 1.5,
            "active": True,
            "missing": None,
            "plain": "text: with colon",
            "values": ["列表项", 7, False],
        })
        self.assertEqual(body, "正文 Unicode：你好，世界。")

    def test_legacy_dictionary_fixture_and_multiline_info_fields(self):
        path = BASELINE_DATA_DIR / "projects" / "baseline-project" / "infos" / "INFO-0001-legacy-fields.md"
        metadata, body = load_markdown(path)

        self.assertEqual(metadata["id"], "INFO-0001")
        self.assertEqual(metadata["info_fields"][0], {
            "name": "启动命令",
            "value": "python server.py\npython -m unittest -v",
            "note": "保留换行、引号和  连续空格",
        })
        self.assertEqual(metadata["info_fields"][1]["value"], '键="值"\n路径仅为虚构示例')
        self.assertIn("不执行命令", body)

    def test_dump_write_and_reload_preserves_supported_metadata(self):
        metadata = {
            "id": "INFO-0042",
            "type": "info",
            "title": "多行与引号 🧪",
            "project_id": "contract-project",
            "enabled": False,
            "optional": None,
            "tags": ["中文", "空 格", "quote-\"value\""],
            "info_fields": [
                {"name": "命令", "value": "first line\n  second line", "note": '保留 "引号"'},
                {"name": "空白", "value": "value with  two spaces"},
            ],
        }
        body = "# 多行与引号\n\n正文第一行\n\n正文最后一行"

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "round-trip.md"
            path.write_text(dump_markdown(metadata, body), encoding="utf-8")
            reloaded_metadata, reloaded_body = load_markdown(path)

        self.assertEqual(reloaded_metadata, metadata)
        self.assertEqual(reloaded_body, body)
        self.assertEqual(normalize_info_fields(reloaded_metadata["info_fields"]), metadata["info_fields"])

    def test_empty_body_round_trip_is_empty(self):
        serialized = dump_markdown({"id": "DOC-0001", "type": "document", "tags": []}, "")
        metadata, body = load_markdown_text(serialized)

        self.assertEqual(metadata, {"id": "DOC-0001", "type": "document", "tags": []})
        self.assertEqual(body, "")

    def test_plain_and_malformed_documents_remain_readable(self):
        plain = "# 没有 front matter\n\n正文"
        self.assertEqual(load_markdown_text(plain), ({}, plain))

        malformed = "---\ntitle: \"缺少结束分隔线\"\n正文"
        self.assertEqual(load_markdown_text(malformed), ({}, malformed))

    def test_missing_and_non_utf8_files_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                load_markdown(root / "missing.md")

            invalid = root / "invalid.md"
            invalid.write_bytes(b"\xff\xfe\x00")
            with self.assertRaises(UnicodeDecodeError):
                load_markdown(invalid)


if __name__ == "__main__":
    unittest.main()
