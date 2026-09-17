"""Data, export, and directory path handling for the local workbench."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from .persistence import atomic_write_bytes, atomic_write_json
from .security import validate_portable_filename


APP_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = APP_DIR / "workbench-data"
LOCATION_FILE = APP_DIR / ".workbench-location.json"
EXPORT_LOCATION_FILE = APP_DIR / ".workbench-export.json"


def _validate_migration_source(root: Path):
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("数据目录包含符号链接，无法安全复制；请移除链接后重试")


def save_data_location(data_dir: Path, location_file: Path = LOCATION_FILE):
    location_file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(location_file, {"data_dir": str(data_dir.resolve())})


def relocate_repository(current: Any, raw_path: str, migrate: bool, location_file: Path = LOCATION_FILE):
    value = os.path.expandvars(str(raw_path).strip())
    if not value:
        raise ValueError("数据目录不能为空")
    target = Path(value).expanduser()
    if not target.is_absolute():
        raise ValueError("请输入完整的绝对路径，例如 E:\\WorkBenchData")
    target = target.resolve()
    if target == current.root:
        save_data_location(target, location_file)
        return current
    if migrate and (target.is_relative_to(current.root) or current.root.is_relative_to(target)):
        raise ValueError("新旧数据目录不能互相嵌套，请选择独立目录")
    if migrate:
        if target.exists() and any(target.iterdir()):
            raise ValueError("复制数据时目标目录必须为空；如需打开已有工作台，请选择“直接使用已有目录”")
        target.parent.mkdir(parents=True, exist_ok=True)
        _validate_migration_source(current.root)
        shutil.copytree(current.root, target, dirs_exist_ok=True)
    else:
        target.mkdir(parents=True, exist_ok=True)
    repository = current.__class__(target)
    save_data_location(repository.root, location_file)
    return repository


def configured_data_dir(command_line_value: Path | None) -> Path:
    if command_line_value is not None:
        return command_line_value
    environment_value = os.environ.get("WORKBENCH_DATA_DIR")
    if environment_value:
        return Path(environment_value)
    try:
        saved = json.loads(LOCATION_FILE.read_text(encoding="utf-8"))
        if saved.get("data_dir"):
            return Path(saved["data_dir"])
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return DEFAULT_DATA_DIR


def common_export_locations() -> list[dict]:
    home = Path.home()
    choices = [
        ("downloads", "下载", home / "Downloads"),
        ("desktop", "桌面", home / "Desktop"),
        ("documents", "文档", home / "Documents"),
    ]
    return [{"id": key, "label": label, "path": str(path.resolve())} for key, label, path in choices]


def configured_export_dir(location_file: Path = EXPORT_LOCATION_FILE) -> Path | None:
    try:
        saved = json.loads(location_file.read_text(encoding="utf-8"))
        path = Path(saved.get("export_dir", ""))
        return path.resolve() if path.is_absolute() else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def export_location_payload(location_file: Path = EXPORT_LOCATION_FILE) -> dict:
    directory = configured_export_dir(location_file)
    return {"path": str(directory) if directory else "", "name": directory.name if directory else "", "common": common_export_locations()}


def save_export_location(raw_path: str, location_file: Path = EXPORT_LOCATION_FILE) -> dict:
    value = os.path.expandvars(str(raw_path).strip())
    if not value:
        raise ValueError("请选择或填写导出目录")
    target = Path(value).expanduser()
    if not target.is_absolute():
        raise ValueError("请输入完整的绝对路径，例如 C:\\Users\\用户名\\Downloads")
    target.mkdir(parents=True, exist_ok=True)
    target = target.resolve()
    # 创建并立即删除探测文件，在保存设置前确认目录确实可写。
    with tempfile.NamedTemporaryFile(prefix=".workbench-write-test-", dir=target, delete=True):
        pass
    location_file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(location_file, {"export_dir": str(target)})
    return export_location_payload(location_file)


def directory_browser_payload(raw_path: str = "") -> dict:
    value = os.path.expandvars(str(raw_path).strip())
    target = Path(value).expanduser() if value else (configured_export_dir() or Path.home())
    if not target.is_absolute():
        raise ValueError("请输入完整目录路径")
    target = target.resolve()
    if not target.is_dir():
        raise ValueError("该目录不存在，请选择已有目录")
    directories = []
    try:
        children = sorted((item for item in target.iterdir() if item.is_dir() and not item.name.startswith(".")), key=lambda item: item.name.casefold())
        for child in children:
            try:
                directories.append({"name": child.name, "path": str(child.resolve())})
            except OSError:
                continue
    except PermissionError as exc:
        raise ValueError("没有权限浏览该目录，请返回上一级") from exc
    roots = []
    if sys.platform == "win32":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            if drive.exists():
                roots.append({"name": f"本地磁盘 ({letter}:)", "path": str(drive)})
    else:
        roots.append({"name": "根目录", "path": "/"})
    parent = target.parent
    return {"path": str(target), "name": target.name or str(target), "parent": str(parent) if parent != target else "", "directories": directories, "roots": roots}


def export_to_saved_location(repository: Any, project_id: str | None, filename: str, location_file: Path = EXPORT_LOCATION_FILE) -> dict:
    directory = configured_export_dir(location_file)
    if not directory:
        raise ValueError("请先选择导出位置")
    if not directory.is_dir():
        raise ValueError("已保存的导出目录不存在，请重新选择位置")
    clean_name = validate_portable_filename(filename, label="导出文件名", suffixes={".zip"})
    content = repository.export_zip(project_id)
    destination = directory / clean_name
    atomic_write_bytes(destination, content)
    return {"ok": True, "path": str(destination), "directory": str(directory), "filename": clean_name, "size": len(content)}
