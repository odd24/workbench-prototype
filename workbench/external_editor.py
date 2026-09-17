"""External Markdown editor discovery, configuration, and launching."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from .persistence import atomic_write_json


APP_DIR = Path(__file__).resolve().parent.parent
EXTERNAL_EDITOR_FILE = APP_DIR / ".workbench-editor.json"
EditorDetector = Callable[[], list[dict]]


def _environment_path(variable: str, *parts: str) -> str | None:
    root = os.environ.get(variable)
    return str(Path(root, *parts)) if root else None


def detected_external_editors() -> list[dict]:
    definitions = [
        ("typora", "Typora", [os.environ.get("TYPORA_PATH"), shutil.which("Typora.exe"), shutil.which("Typora"), _environment_path("LOCALAPPDATA", "Programs", "Typora", "Typora.exe"), _environment_path("LOCALAPPDATA", "Typora", "Typora.exe"), _environment_path("PROGRAMFILES", "Typora", "Typora.exe"), _environment_path("PROGRAMFILES(X86)", "Typora", "Typora.exe")]),
        ("vscode", "Visual Studio Code", [shutil.which("Code.exe"), _environment_path("LOCALAPPDATA", "Programs", "Microsoft VS Code", "Code.exe"), _environment_path("PROGRAMFILES", "Microsoft VS Code", "Code.exe"), shutil.which("code")]),
        ("obsidian", "Obsidian", [shutil.which("Obsidian.exe"), shutil.which("obsidian"), _environment_path("LOCALAPPDATA", "Obsidian", "Obsidian.exe"), _environment_path("LOCALAPPDATA", "Programs", "Obsidian", "Obsidian.exe")]),
        ("notepadpp", "Notepad++", [shutil.which("notepad++.exe"), _environment_path("PROGRAMFILES", "Notepad++", "notepad++.exe"), _environment_path("PROGRAMFILES(X86)", "Notepad++", "notepad++.exe")]),
        ("sublime", "Sublime Text", [shutil.which("sublime_text.exe"), shutil.which("subl"), _environment_path("PROGRAMFILES", "Sublime Text", "sublime_text.exe")]),
        ("marktext", "MarkText", [shutil.which("MarkText.exe"), shutil.which("marktext"), _environment_path("LOCALAPPDATA", "Programs", "MarkText", "MarkText.exe")]),
        ("zettlr", "Zettlr", [shutil.which("Zettlr.exe"), shutil.which("zettlr"), _environment_path("LOCALAPPDATA", "Programs", "Zettlr", "Zettlr.exe"), _environment_path("LOCALAPPDATA", "Zettlr", "Zettlr.exe")]),
    ]
    editors = []
    for editor_id, name, candidates in definitions:
        executable = next((Path(candidate).resolve() for candidate in candidates if candidate and Path(candidate).is_file()), None)
        if executable:
            editors.append({"id": editor_id, "name": name, "path": str(executable), "kind": "detected"})
    editors.append({"id": "system", "name": "系统默认 Markdown 编辑器", "path": "", "kind": "system"})
    return editors


def external_editor_payload(config_file: Path = EXTERNAL_EDITOR_FILE, detector: EditorDetector | None = None) -> dict:
    try:
        selected = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        selected = {}
    editors = (detector or detected_external_editors)()
    custom_path = str(selected.get("path", "")).strip()
    if selected.get("id") == "custom" and custom_path and Path(custom_path).is_file():
        editors.insert(0, {"id": "custom", "name": selected.get("name") or Path(custom_path).stem, "path": str(Path(custom_path).resolve()), "kind": "custom"})
    available_ids = {editor["id"] for editor in editors}
    selected_id = selected.get("id") if selected.get("id") in available_ids else ("typora" if "typora" in available_ids else "system")
    selected_editor = next(editor for editor in editors if editor["id"] == selected_id)
    return {"selected": selected_id, "selected_name": selected_editor["name"], "editors": editors}


def save_external_editor(editor_id: str, custom_path: str = "", config_file: Path = EXTERNAL_EDITOR_FILE, detector: EditorDetector | None = None) -> dict:
    editor_id = str(editor_id or "").strip()
    detect = detector or detected_external_editors
    if editor_id == "custom":
        executable = Path(str(custom_path or "").strip()).expanduser()
        if not executable.is_file():
            raise ValueError("自定义编辑器程序不存在，请填写可执行程序的完整路径")
        config = {"id": "custom", "name": executable.stem, "path": str(executable.resolve())}
    else:
        editor = next((item for item in detect() if item["id"] == editor_id), None)
        if not editor:
            raise ValueError("所选编辑器当前不可用")
        config = {"id": editor["id"], "name": editor["name"], "path": editor["path"]}
    atomic_write_json(config_file, config)
    return external_editor_payload(config_file, detect)


def open_markdown_external(path: Path, config_file: Path = EXTERNAL_EDITOR_FILE, detector: EditorDetector | None = None) -> str:
    payload = external_editor_payload(config_file, detector)
    editor = next(item for item in payload["editors"] if item["id"] == payload["selected"])
    if editor["kind"] != "system":
        subprocess.Popen([editor["path"], str(path)], cwd=str(path.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return editor["name"]
    _open_system_default(path)
    return editor["name"]


def _open_system_default(path: Path):
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_file_external(path: Path, config_file: Path = EXTERNAL_EDITOR_FILE, detector: EditorDetector | None = None) -> str:
    """Open an attachment with its configured desktop application."""
    if path.suffix.lower() in {".md", ".markdown"}:
        return open_markdown_external(path, config_file, detector)
    _open_system_default(path)
    return "系统默认应用"
