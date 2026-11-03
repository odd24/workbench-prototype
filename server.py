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
from workbench.write_coordinator import DataDirectoryLock
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


def open_file_external(path: Path, config_file: Path = EXTERNAL_EDITOR_FILE) -> str:
    return external_editor_module.open_file_external(path, config_file, detected_external_editors)


class Repository(BaseRepository):
    """Keep legacy patch points while assembling the extracted repository."""

    def __init__(self, data_dir: Path):
        super().__init__(
            data_dir,
            load_markdown_callback=lambda path: load_markdown(path),
            open_markdown_external_callback=lambda path: open_markdown_external(path),
            open_file_external_callback=lambda path: open_file_external(path),
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


def replace_existing_workbench(host: str, port: int, data_dir: Path, agent_enabled=None) -> bool:
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
    if len(pids) == 1 and health.get("app_version") == APP_VERSION and (agent_enabled is None or bool(health.get("agent_enabled")) == agent_enabled):
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
    parser.add_argument("--enable-agent", action="store_true", help="启用本机 Agent 接口")
    parser.add_argument("--agent-config-dir", type=Path, help="本机凭据根目录（必须在仓库和数据目录外）")
    admin = parser.add_mutually_exclusive_group()
    admin.add_argument("--agent-client-add", metavar="NAME", help="创建 Agent 客户端后退出")
    admin.add_argument("--agent-client-revoke", metavar="ID", help="撤销 Agent 客户端后退出")
    admin.add_argument("--agent-client-rotate", metavar="ID", help="轮换 Agent 客户端令牌后退出")
    parser.add_argument("--agent-scope", action="append", choices=["read", "propose", "commit"], help="允许操作，可重复；默认只读")
    parser.add_argument("--agent-project", action="append", default=[], help="允许项目 ID，可重复；* 表示全部")
    parser.add_argument("--agent-category", action="append", default=[], help="允许文档分类，可重复；* 表示全部")
    return parser


def main(argv=None):
    args = build_argument_parser().parse_args(argv)
    data_root = configured_data_dir(args.data_dir).resolve()
    if args.enable_agent and args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Agent 接入只允许监听本机 loopback")
    if args.agent_client_add or args.agent_client_revoke or args.agent_client_rotate:
        from workbench.agent_security import AgentSecurity
        # Administration never opens a second business repository.
        existing = (data_root / ".agent" / "workspace.json").exists()
        lock = None if existing else DataDirectoryLock(data_root)
        try:
            security = AgentSecurity(data_root, args.agent_config_dir)
            if args.agent_client_add:
                result = security.add_client(args.agent_client_add, args.agent_scope or ["read"], args.agent_project, args.agent_category, f"http://{'[::1]' if args.host == '::1' else args.host}:{args.port}")
            else:
                result = security.change_client(args.agent_client_revoke or args.agent_client_rotate, bool(args.agent_client_rotate))
            print(json.dumps(result, ensure_ascii=False))
        finally:
            if lock:
                lock.close()
        return
    if args.replace and replace_existing_workbench(args.host, args.port, data_root, agent_enabled=args.enable_agent):
        print(f"本地工作台已在运行：http://{args.host}:{args.port}")
        if args.open:
            webbrowser.open(f"http://{args.host}:{args.port}/?session={int(time.time())}")
        return
    ownership = DataDirectoryLock(data_root)
    try:
        repository = Repository(data_root)
        repository.service_lock = ownership
        if args.enable_agent:
            from workbench.agent_security import AgentSecurity
            from workbench.agent_service import AgentService
            repository.agent_service = AgentService(repository, AgentSecurity(data_root, args.agent_config_dir))
        WorkbenchHandler.repository = repository
        server = WorkbenchHTTPServer((args.host, args.port), WorkbenchHandler)
    except BaseException:
        ownership.close()
        raise
    if args.seed_demo:
        repository.seed_demo()
    print(f"本地工作台已启动：http://{args.host}:{args.port}")
    print(f"Markdown 数据目录：{repository.root}")
    if args.open:
        session_url = f"http://{args.host}:{args.port}/?session={int(time.time())}"
        threading.Timer(0.35, lambda: webbrowser.open(session_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
