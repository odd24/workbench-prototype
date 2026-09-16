"""Zero-dependency CLI and service lifecycle for 本地工作台."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from workbench import external_editor as external_editor_module
from workbench.concept_maps import CONCEPT_MAP_HEIGHT, CONCEPT_MAP_WIDTH
from workbench.external_editor import EXTERNAL_EDITOR_FILE
from workbench.http_api import APP_VERSION, WorkbenchHandler, WorkbenchHTTPServer
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
from workbench.paths import (
    DEFAULT_DATA_DIR,
    EXPORT_LOCATION_FILE,
    LOCATION_FILE,
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
from workbench.records import TYPE_DIRS, TYPE_PREFIXES
from workbench.repository import Repository as BaseRepository


APP_DIR = Path(__file__).resolve().parent


def detected_external_editors() -> list[dict]:
    return external_editor_module.detected_external_editors()


def external_editor_payload(config_file: Path = EXTERNAL_EDITOR_FILE) -> dict:
    return external_editor_module.external_editor_payload(config_file, detected_external_editors)


def save_external_editor(editor_id: str, custom_path: str = "", config_file: Path = EXTERNAL_EDITOR_FILE) -> dict:
    return external_editor_module.save_external_editor(editor_id, custom_path, config_file, detected_external_editors)


def open_markdown_external(path: Path, config_file: Path = EXTERNAL_EDITOR_FILE) -> str:
    return external_editor_module.open_markdown_external(path, config_file, detected_external_editors)


class Repository(BaseRepository):
    """Keep legacy patch points while assembling the extracted repository."""

    def __init__(self, data_dir: Path):
        super().__init__(
            data_dir,
            load_markdown_callback=lambda path: load_markdown(path),
            open_markdown_external_callback=lambda path: open_markdown_external(path),
        )


def windows_listener_pids(port: int) -> set[int]:
    """Return Windows PIDs listening on the selected local port."""
    if sys.platform != "win32":
        return set()
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True,
        encoding="utf-8", errors="ignore", check=False,
    )
    pids = set()
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) < 5 or columns[0].upper() != "TCP" or columns[-2].upper() != "LISTENING":
            continue
        local_address = columns[1].rsplit(":", 1)
        if len(local_address) == 2 and local_address[-1] == str(port) and columns[-1].isdigit():
            pids.add(int(columns[-1]))
    return pids


def replace_existing_workbench(host: str, port: int, data_dir: Path) -> bool:
    """Stop stale copies only after confirming the port serves this data directory."""
    pids = windows_listener_pids(port)
    if not pids:
        return False
    try:
        from urllib.request import urlopen
        with urlopen(f"http://{host}:{port}/api/health", timeout=2) as response:
            health = json.loads(response.read().decode("utf-8"))
    except Exception:
        return False
    if Path(health.get("data_dir", "")).resolve() != data_dir.resolve():
        return False
    if len(pids) == 1 and health.get("app_version") == APP_VERSION:
        return True
    print(f"检测到 {len(pids)} 个旧工作台服务，正在安全重启……")
    for pid in pids:
        if pid != os.getpid():
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
    for _ in range(30):
        if not windows_listener_pids(port):
            break
        time.sleep(0.1)
    return False


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="本地工作台服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--seed-demo", action="store_true", help="数据为空时创建演示项目和记录")
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    parser.add_argument("--replace", action="store_true", help="启动时替换同一数据目录的旧工作台服务")
    return parser


def main(argv=None):
    args = build_argument_parser().parse_args(argv)
    repository = Repository(configured_data_dir(args.data_dir))
    if args.seed_demo:
        repository.seed_demo()
    if args.replace and replace_existing_workbench(args.host, args.port, repository.root):
        print(f"本地工作台已在运行：http://{args.host}:{args.port}")
        if args.open:
            webbrowser.open(f"http://{args.host}:{args.port}/?session={int(time.time())}")
        return
    WorkbenchHandler.repository = repository
    server = WorkbenchHTTPServer((args.host, args.port), WorkbenchHandler)
    print(f"本地工作台已启动：http://{args.host}:{args.port}")
    print(f"Markdown 数据目录：{repository.root}")
    if args.open:
        session_url = f"http://{args.host}:{args.port}/?session={int(time.time())}"
        threading.Timer(0.35, lambda: webbrowser.open(session_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")


if __name__ == "__main__":
    main()
