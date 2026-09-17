"""Validation helpers for untrusted paths, names, labels, and ZIP archives."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path, PurePosixPath


WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def validate_portable_filename(value, *, label: str = "文件名", suffixes: set[str] | None = None) -> str:
    name = str(value or "")
    if not name or name in {".", ".."} or len(name) > 240:
        raise ValueError(f"{label}无效")
    if name != name.strip() or name.endswith((".", " ")):
        raise ValueError(f"{label}无效")
    if INVALID_FILENAME_CHARS.search(name) or any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError(f"{label}无效")
    if name.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        raise ValueError(f"{label}无效")
    if suffixes is not None and Path(name).suffix.lower() not in {suffix.lower() for suffix in suffixes}:
        raise ValueError(f"{label}类型无效")
    return name


def validate_category_name(value, *, default: str = "未分类", label: str = "分类名称", max_length: int = 80) -> str:
    name = str(value or default).strip() or default
    if len(name) > max_length:
        raise ValueError(f"{label}不能超过 {max_length} 个字符")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError(f"{label}包含无效控制字符")
    return name


def validate_archive_member(value: str) -> str:
    name = str(value or "")
    if not name or "\\" in name or any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError("ZIP 路径无效")
    candidate = name[:-1] if name.endswith("/") else name
    path = PurePosixPath(candidate)
    parts = candidate.split("/")
    if not candidate or path.is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("ZIP 路径无效")
    if re.match(r"^[A-Za-z]:", candidate):
        raise ValueError("ZIP 路径无效")
    return name


def validate_zip_bytes(
    content: bytes,
    *,
    verify_content: bool = False,
    max_entries: int | None = None,
    max_uncompressed_size: int | None = None,
) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if max_entries is not None and len(infos) > max_entries:
                raise ValueError("ZIP 文件数量过多")
            names = set()
            total_size = 0
            for info in infos:
                name = validate_archive_member(info.filename)
                if name in names:
                    raise ValueError("ZIP 包含重复路径")
                names.add(name)
                if info.flag_bits & 0x1:
                    raise ValueError("不支持加密 ZIP")
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("ZIP 不允许符号链接")
                total_size += info.file_size
                if max_uncompressed_size is not None and total_size > max_uncompressed_size:
                    raise ValueError("ZIP 解压后内容过大")
            if verify_content:
                broken = archive.testzip()
                if broken:
                    raise ValueError(f"ZIP 内容损坏：{broken}")
    except zipfile.BadZipFile as exc:
        raise ValueError("ZIP 归档损坏") from exc
    return content


def archive_name_for(source: Path, path: Path) -> str | None:
    source = source.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(source):
        return None
    return validate_archive_member(resolved.relative_to(source).as_posix())
