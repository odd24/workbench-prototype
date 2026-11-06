import tempfile
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import server
from workbench.repository import Repository as ExtractedRepository


class StartupBoundaryTests(unittest.TestCase):
    def test_codex_fixture_reaps_descendants_after_parent_exit(self):
        if os.name != "nt":
            return
        from codex_agent_acceptance import RpcProcess
        script = "import subprocess,sys,json; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); print(json.dumps({'child':p.pid}),flush=True)"
        with tempfile.TemporaryDirectory() as directory:
            rpc = RpcProcess([sys.executable, "-c", script], directory, terminate_tree=True)
            try:
                self.assertIn("child", rpc.messages.get(timeout=5))
                rpc.process.wait(timeout=5)
            finally:
                rpc.close()
            self.assertTrue(all(not reader.is_alive() for reader in rpc.readers))
            self.assertTrue(rpc.process.stdout.closed and rpc.process.stderr.closed)

    def test_codex_fixture_reaps_windows_descendants_and_inherited_pipes(self):
        if os.name != "nt":
            return  # Windows-specific failure; no Linux process-tree claim.
        from codex_agent_acceptance import RpcProcess
        script = "import subprocess,sys,time,json; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); print(json.dumps({'child':p.pid}),flush=True); time.sleep(30)"
        with tempfile.TemporaryDirectory() as directory:
            rpc = RpcProcess([sys.executable, "-c", script], directory, terminate_tree=True)
            started = time.monotonic()
            try:
                self.assertIn("child", rpc.messages.get(timeout=5))
            finally:
                rpc.close()
            self.assertLess(time.monotonic() - started, 10)
            self.assertIsNotNone(rpc.process.poll())
            self.assertTrue(all(not reader.is_alive() for reader in rpc.readers))
            self.assertTrue(rpc.process.stdout.closed and rpc.process.stderr.closed)

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
            repository_type.assert_not_called()  # Reusing a service must not touch its data directory.
            repository.seed_demo.assert_not_called()  # Reused service owns all writes.
            replace.assert_called_once_with("127.0.0.1", 4174, data_dir.resolve(), agent_enabled=False)
            browser_open.assert_called_once()
            http_server.assert_not_called()


if __name__ == "__main__":
    unittest.main()
