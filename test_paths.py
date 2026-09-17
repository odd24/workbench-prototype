import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from server import Repository
from workbench import external_editor
from workbench.paths import (
    common_export_locations,
    configured_data_dir,
    configured_export_dir,
    directory_browser_payload,
    export_location_payload,
    export_to_saved_location,
    relocate_repository,
    save_data_location,
    save_export_location,
)


class PathAndExternalEditorTests(unittest.TestCase):
    def test_server_keeps_compatible_path_helper_exports(self):
        self.assertIs(server.common_export_locations, common_export_locations)
        self.assertIs(server.configured_data_dir, configured_data_dir)
        self.assertIs(server.configured_export_dir, configured_export_dir)
        self.assertIs(server.directory_browser_payload, directory_browser_payload)
        self.assertIs(server.export_location_payload, export_location_payload)
        self.assertIs(server.export_to_saved_location, export_to_saved_location)
        self.assertIs(server.relocate_repository, relocate_repository)
        self.assertIs(server.save_data_location, save_data_location)
        self.assertIs(server.save_export_location, save_export_location)
        self.assertEqual(server.EXTERNAL_EDITOR_FILE, external_editor.EXTERNAL_EDITOR_FILE)

    def test_invalid_and_nested_data_directories_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "current")
            location_file = Path(directory) / "location.json"

            with self.assertRaisesRegex(ValueError, "绝对路径"):
                relocate_repository(repo, "relative-data", False, location_file)
            with self.assertRaisesRegex(ValueError, "不能互相嵌套"):
                relocate_repository(repo, str(repo.root / "nested"), True, location_file)

    def test_invalid_custom_editor_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "editor.json"
            with self.assertRaisesRegex(ValueError, "程序不存在"):
                external_editor.save_external_editor("custom", str(Path(directory) / "missing.exe"), config_file)

    def test_custom_editor_uses_argument_array_without_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "Editor With Spaces.exe"
            document = root / "Document With Spaces.md"
            config_file = root / "editor.json"
            executable.write_bytes(b"")
            document.write_text("# Test", encoding="utf-8")
            external_editor.save_external_editor("custom", str(executable), config_file)

            with patch("workbench.external_editor.subprocess.Popen") as launcher:
                name = external_editor.open_markdown_external(document, config_file)

            self.assertEqual(name, "Editor With Spaces")
            arguments, options = launcher.call_args
            self.assertEqual(arguments[0], [str(executable.resolve()), str(document)])
            self.assertEqual(options["cwd"], str(document.parent))
            self.assertNotIn("shell", options)

    def test_system_editor_uses_platform_argument_array(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "system.md"
            document.write_text("# System", encoding="utf-8")
            detector = lambda: [{"id": "system", "name": "系统默认 Markdown 编辑器", "path": "", "kind": "system"}]

            with patch("workbench.external_editor.sys.platform", "linux"), patch("workbench.external_editor.subprocess.Popen") as launcher:
                name = external_editor.open_markdown_external(document, Path(directory) / "missing.json", detector)

            self.assertEqual(name, "系统默认 Markdown 编辑器")
            arguments, options = launcher.call_args
            self.assertEqual(arguments[0], ["xdg-open", str(document)])
            self.assertNotIn("shell", options)

    def test_attachment_opener_uses_markdown_setting_or_system_default(self):
        markdown = Path("说明.md")
        document = Path("资料.docx")
        with patch("workbench.external_editor.open_markdown_external", return_value="Typora") as markdown_opener, patch("workbench.external_editor._open_system_default") as system_opener:
            self.assertEqual(external_editor.open_file_external(markdown), "Typora")
            self.assertEqual(external_editor.open_file_external(document), "系统默认应用")

        markdown_opener.assert_called_once_with(markdown, external_editor.EXTERNAL_EDITOR_FILE, None)
        system_opener.assert_called_once_with(document)


if __name__ == "__main__":
    unittest.main()
