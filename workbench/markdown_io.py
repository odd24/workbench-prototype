"""Lightweight Markdown front matter and naming helpers.

The front matter parser intentionally supports the project's existing subset
rather than full YAML. Keep its permissive legacy dictionary handling stable.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def slugify(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "-", value.strip())
    value = re.sub(r"\s+", "-", value).strip(".- ")
    return value[:80] or "untitled"


def yaml_scalar(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(str(value), ensure_ascii=False)


def dump_markdown(meta: dict, body: str) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {yaml_scalar(item)}" for item in value)
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.extend(["---", "", body.strip(), ""])
    return "\n".join(lines)


def parse_scalar(value: str):
    value = value.strip()
    if value == "null":
        return None
    if value in {"true", "false"}:
        return value == "true"
    try:
        parsed = json.loads(value)
        # 兼容旧版本把字典先转成 Python 字符串、再包成 JSON 字符串的格式。
        if isinstance(parsed, str) and parsed.startswith("{") and parsed.endswith("}"):
            try:
                legacy = ast.literal_eval(parsed)
                if isinstance(legacy, dict):
                    return legacy
            except (ValueError, SyntaxError):
                pass
        return parsed
    except (json.JSONDecodeError, TypeError):
        return value


def normalize_info_fields(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    fields = []
    for item in value[:100]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()[:120]
        content = str(item.get("value", "")).strip()
        note = str(item.get("note", "")).strip()
        if name or content:
            field = {"name": name or "未命名字段", "value": content}
            if note:
                field["note"] = note
            fields.append(field)
    return fields


def load_markdown(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    return load_markdown_text(text)


def load_markdown_text(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    try:
        raw_meta, body = text[4:].split("\n---\n", 1)
    except ValueError:
        return {}, text
    meta, current_list = {}, None
    for line in raw_meta.splitlines():
        if line.startswith("  - ") and current_list:
            meta[current_list].append(parse_scalar(line[4:]))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value:
            meta[key], current_list = parse_scalar(value), None
        else:
            meta[key], current_list = [], key
    return meta, body.strip()
