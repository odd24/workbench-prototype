import io
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from server import Repository
from workbench.security import (
    archive_name_for,
    validate_archive_member,
    validate_portable_filename,
    validate_zip_bytes,
)


class SecurityValidationTests(unittest.TestCase):
    def test_portable_filenames_reject_paths_controls_and_reserved_names(self):
        for name in ("../escape.md", "..\\escape.md", "/absolute.md", "C:drive.md", "NUL.md", "bad\x1fname.md"):
            with self.subTest(name=repr(name)):
                with self.assertRaises(ValueError):
                    validate_portable_filename(name, suffixes={".md"})
        self.assertEqual(validate_portable_filename("说明文档.md", suffixes={".md"}), "说明文档.md")

    def test_archive_members_reject_traversal_absolute_and_platform_paths(self):
        for name in ("../outside.txt", "folder/../outside.txt", "folder/./file.txt", "folder//file.txt", "/absolute.txt", "C:/drive.txt", "folder\\file.txt", "bad\x00.txt"):
            with self.subTest(name=repr(name)):
                with self.assertRaisesRegex(ValueError, "ZIP 路径无效"):
                    validate_archive_member(name)
        self.assertEqual(validate_archive_member("documents/说明.md"), "documents/说明.md")

    def test_zip_validation_rejects_malicious_duplicate_and_corrupt_archives(self):
        malicious = io.BytesIO()
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr("../outside.txt", "escape")
        with self.assertRaisesRegex(ValueError, "ZIP 路径无效"):
            validate_zip_bytes(malicious.getvalue(), verify_content=True)

        duplicate = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("same.txt", "first")
                archive.writestr("same.txt", "second")
        with self.assertRaisesRegex(ValueError, "重复路径"):
            validate_zip_bytes(duplicate.getvalue())

        symlink = io.BytesIO()
        with zipfile.ZipFile(symlink, "w") as archive:
            info = zipfile.ZipInfo("linked.txt")
            info.create_system = 3
            info.external_attr = (0o120777 << 16)
            archive.writestr(info, "outside.txt")
        with self.assertRaisesRegex(ValueError, "符号链接"):
            validate_zip_bytes(symlink.getvalue())

        with self.assertRaisesRegex(ValueError, "ZIP 归档损坏"):
            validate_zip_bytes(b"not-a-zip", verify_content=True)

        damaged = io.BytesIO()
        with zipfile.ZipFile(damaged, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("payload.txt", b"payload-marker")
        corrupted = damaged.getvalue().replace(b"payload-marker", b"payload-broken", 1)
        with self.assertRaisesRegex(ValueError, "ZIP"):
            validate_zip_bytes(corrupted, verify_content=True)

    def test_archive_name_only_accepts_paths_inside_source(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source"
            source.mkdir()
            inside = source / "inside.txt"
            outside = base / "outside.txt"
            inside.write_text("inside", encoding="utf-8")
            outside.write_text("outside", encoding="utf-8")

            self.assertEqual(archive_name_for(source, inside), "inside.txt")
            self.assertIsNone(archive_name_for(source, outside))

    def test_full_export_excludes_machine_specific_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Repository(Path(directory))
            (repository.root / ".workbench-private.json").write_text('{"path":"C:/private"}', encoding="utf-8")
            with zipfile.ZipFile(io.BytesIO(repository.export_zip())) as archive:
                names = set(archive.namelist())

            self.assertNotIn("config/settings.json", names)
            self.assertNotIn(".workbench-private.json", names)
            self.assertIn("config/labels.json", names)

    def test_imports_reject_unportable_source_names_without_changing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Repository(Path(directory))
            before_documents = repository.list_documents()
            before_records = repository.list_records()

            with self.assertRaisesRegex(ValueError, "导入文件名"):
                repository.import_document({"name": "../document.md", "content": "# 文档"})
            with self.assertRaisesRegex(ValueError, "导入文件名"):
                repository.import_markdown({"name": "..\\record.md", "content": "# 记录"})
            with self.assertRaisesRegex(ValueError, "类型"):
                repository.import_document({"name": "document.txt", "content": "# 文档"})

            self.assertEqual(repository.list_documents(), before_documents)
            self.assertEqual(repository.list_records(), before_records)

    def test_categories_reject_control_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Repository(Path(directory))
            with self.assertRaisesRegex(ValueError, "控制字符"):
                repository.save_document_categories(["正常", "损坏\x00分类"])
            with self.assertRaisesRegex(ValueError, "控制字符"):
                repository.save_concept_map_categories(["正常", "损坏\x1f分类"])


if __name__ == "__main__":
    unittest.main()
