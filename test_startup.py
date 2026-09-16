import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import server
from workbench.repository import Repository as ExtractedRepository


class StartupBoundaryTests(unittest.TestCase):
    def test_server_repository_is_a_compatible_extracted_facade(self):
        self.assertTrue(issubclass(server.Repository, ExtractedRepository))

        with tempfile.TemporaryDirectory() as directory:
            repository = ExtractedRepository(Path(directory))
            project = repository.create_project({"name": "独立仓储入口"})
            self.assertEqual(repository.project(project["id"])["name"], "独立仓储入口")

    def test_argument_parser_preserves_all_launch_options(self):
        data_dir = Path("custom-data")
        args = server.build_argument_parser().parse_args([
            "--host", "127.0.0.2",
            "--port", "4174",
            "--data-dir", str(data_dir),
            "--seed-demo",
            "--replace",
            "--open",
        ])

        self.assertEqual(args.host, "127.0.0.2")
        self.assertEqual(args.port, 4174)
        self.assertEqual(args.data_dir, data_dir)
        self.assertTrue(args.seed_demo)
        self.assertTrue(args.replace)
        self.assertTrue(args.open)

    def test_main_wires_custom_directory_seed_replace_and_open(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            repository = MagicMock(root=data_dir)
            with (
                patch.object(server, "configured_data_dir", return_value=data_dir) as configured,
                patch.object(server, "Repository", return_value=repository) as repository_type,
                patch.object(server, "replace_existing_workbench", return_value=True) as replace,
                patch.object(server, "WorkbenchHTTPServer") as http_server,
                patch.object(server.webbrowser, "open") as browser_open,
                patch("builtins.print"),
            ):
                server.main(["--data-dir", str(data_dir), "--port", "4174", "--seed-demo", "--replace", "--open"])

            configured.assert_called_once_with(data_dir)
            repository_type.assert_called_once_with(data_dir)
            repository.seed_demo.assert_called_once_with()
            replace.assert_called_once_with("127.0.0.1", 4174, data_dir)
            browser_open.assert_called_once()
            http_server.assert_not_called()


if __name__ == "__main__":
    unittest.main()
