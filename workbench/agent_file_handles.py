"""Conservative Windows handle validation for explicitly approved local files.

No file contents are accessed by metadata inspection. Unsupported platforms fail
closed. Paths and native error strings must never escape this module's boundary.
"""

import ctypes
import ntpath
import os
import re
import time
from pathlib import Path
from ctypes import wintypes

from .agent_security import AgentError


SUPPORTED = os.name == "nt"
CHUNK_BYTES = 65536
MAX_FILE_BYTES = 100 * 1024 * 1024


class FileTime(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]


class FileInformation(ctypes.Structure):
    _fields_ = [("attributes", wintypes.DWORD), ("created", FileTime), ("accessed", FileTime), ("written", FileTime),
                ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD), ("size_low", wintypes.DWORD),
                ("links", wintypes.DWORD), ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD)]


class BasicInformation(ctypes.Structure):
    _fields_ = [("created", ctypes.c_longlong), ("accessed", ctypes.c_longlong), ("written", ctypes.c_longlong),
                ("changed", ctypes.c_longlong), ("attributes", wintypes.DWORD)]


def _kernel():
    if not SUPPORTED:
        raise AgentError("unsupported_platform", "本机文件授权仅支持已验证的Windows固定NTFS卷", 503)
    library = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateFileW": ([wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE], wintypes.HANDLE),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        "GetFileType": ([wintypes.HANDLE], wintypes.DWORD),
        "GetFileAttributesW": ([wintypes.LPCWSTR], wintypes.DWORD),
        "GetFileInformationByHandle": ([wintypes.HANDLE, ctypes.POINTER(FileInformation)], wintypes.BOOL),
        "GetFileInformationByHandleEx": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
        "SetFileInformationByHandle": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
        "GetFinalPathNameByHandleW": ([wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD], wintypes.DWORD),
        "GetDriveTypeW": ([wintypes.LPCWSTR], wintypes.UINT),
        "QueryDosDeviceW": ([wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD], wintypes.DWORD),
        "GetVolumeInformationW": ([wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.LPWSTR, wintypes.DWORD], wintypes.BOOL),
        "ReadFile": ([wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p], wintypes.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(library, name)
        function.argtypes, function.restype = arguments, result
    return library


def native_attributes(path):
    if not SUPPORTED:
        return None
    attributes = _kernel().GetFileAttributesW(str(path))
    if attributes == 0xFFFFFFFF:
        if ctypes.get_last_error() in {2, 3}:
            return None
        raise AgentError("unsupported_file", "无法核查本机对象属性", 503)
    return attributes


def lexical_path(value):
    if not isinstance(value, str) or len(value) > 240 or not re.fullmatch(r"[A-Za-z]:\\.+", value) or re.search(r"[\x00-\x1f*?/]", value) or ":" in value[2:]:
        raise AgentError("invalid_file_path", "请选择普通本机盘符绝对路径，不支持网络、设备或特殊路径")
    for component in value[3:].split("\\"):
        if not component or component in {".", ".."} or component.endswith((" ", ".")) or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", component, re.I):
            raise AgentError("invalid_file_path", "文件路径含不受支持的名称")
    return value


def deny_sensitive(path, denied_roots=()):
    normalized = ntpath.normcase(path)
    for root in denied_roots:
        root = ntpath.normcase(str(root)).rstrip("\\")
        if normalized == root or normalized.startswith(root + "\\"):
            raise AgentError("sensitive_file", "该位置属于认证或私人配置范围，不能授权", 403)
    parts = [part.lower() for part in path.split("\\")]
    if any(part in {".git", ".ssh", ".aws", ".azure", ".gnupg", ".kube", ".codex", ".config"} for part in parts) or parts[-1].startswith((".env", "id_rsa", "id_ed25519")) or parts[-1] in {"auth.json", "credentials", "credentials.json", "cookies", "login data"} or ntpath.splitext(parts[-1])[1] in {".key", ".pem", ".pfx", ".p12", ".kdbx"}:
        raise AgentError("sensitive_file", "该名称属于默认拒绝的秘密或认证文件", 403)


class LocalFileHandle:
    def __init__(self, path, *, read=False, denied_roots=(), delete=False):
        self.path = lexical_path(path)
        deny_sensitive(self.path, denied_roots)
        self.read_allowed = read
        self.delete_allowed = delete and read
        self.denied_roots = denied_roots
        self.library = _kernel()
        self.handles = []
        self.handle = None

    def _open(self, path, directory=False, directory_delete=False):
        flags = 0x00200000 | (0x02000000 if directory else 0)  # OPEN_REPARSE_POINT / BACKUP_SEMANTICS
        access = 0x80 if directory or not self.read_allowed else 0x80000000
        if self.delete_allowed and (not directory or directory_delete):
            access |= 0x10000  # DELETE, for verified private staging cleanup only.
        handle = self.library.CreateFileW(path, access, 1, None, 3, flags, None)  # SHARE_READ only, OPEN_EXISTING
        if handle == ctypes.c_void_p(-1).value:
            raise AgentError("source_unavailable", "文件暂不可用或被其他进程占用", 409, True)
        self.handles.append(handle)
        information = FileInformation()
        if self.library.GetFileType(handle) != 1 or not self.library.GetFileInformationByHandle(handle, ctypes.byref(information)):
            raise AgentError("unsupported_file", "无法证明该对象是受支持的本机普通文件", 403)
        if bool(information.attributes & 0x10) != directory or information.attributes & (0x400 | 0x40 | 0x1000 | 0x40000 | 0x400000):
            raise AgentError("unsupported_file", "不支持目录、重解析或特殊文件", 403)
        if not directory and information.links != 1:
            raise AgentError("unsupported_file", "不支持硬链接或无法确认唯一身份的文件", 403)
        return handle

    def _open_leaf(self):
        return self._open(self.path)

    def __enter__(self):
        try:
            root = self.path[:3]
            target = ctypes.create_unicode_buffer(32768)
            if not self.library.QueryDosDeviceW(root[:2], target, len(target)) or not re.fullmatch(r"\\Device\\HarddiskVolume[0-9]+", target.value):
                raise AgentError("unsupported_file", "不支持映射盘符或无法确认物理卷的别名", 403)
            filesystem = ctypes.create_unicode_buffer(32)
            if self.library.GetDriveTypeW(root) != 3 or not self.library.GetVolumeInformationW(root, None, 0, None, None, None, filesystem, len(filesystem)) or filesystem.value.upper() != "NTFS":
                raise AgentError("unsupported_file", "仅支持Windows报告的本机固定NTFS卷", 403)
            self._open(root, directory=True)
            parts = self.path[3:].split("\\")
            for index in range(1, len(parts)):
                self._open(root + "\\".join(parts[:index]), directory=True)
            self.handle = self._open_leaf()
            buffer = ctypes.create_unicode_buffer(32768)
            length = self.library.GetFinalPathNameByHandleW(self.handle, buffer, len(buffer), 0)
            if not 0 < length < len(buffer) or not buffer.value.startswith("\\\\?\\"):
                raise AgentError("unsupported_file", "无法确认句柄最终路径", 403)
            self.path = lexical_path(buffer.value[4:])
            deny_sensitive(self.path, self.denied_roots)
            self.initial = self.identity()
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def identity(self):
        return self._identity(directory=False)

    def _identity(self, *, directory):
        information, basic = FileInformation(), BasicInformation()
        if not self.library.GetFileInformationByHandle(self.handle, ctypes.byref(information)) or not self.library.GetFileInformationByHandleEx(self.handle, 0, ctypes.byref(basic), ctypes.sizeof(basic)):
            raise AgentError("unsupported_file", "无法确认文件身份或版本", 403)
        if bool(information.attributes & 0x10) != directory or not directory and information.links != 1 or information.attributes & (0x400 | 0x40 | 0x1000 | 0x40000 | 0x400000):
            raise AgentError("source_changed", "源文件身份或属性已变化", 409)
        return {"volume": information.volume, "index": (information.index_high << 32) | information.index_low,
                "size": (information.size_high << 32) | information.size_low, "created": basic.created,
                "written": basic.written, "changed": basic.changed}

    def chunks(self, deadline):
        if not self.read_allowed:
            raise AgentError("forbidden", "授权预览禁止读取正文", 403)
        buffer = ctypes.create_string_buffer(CHUNK_BYTES)
        while True:
            if time.monotonic() > deadline:
                raise AgentError("source_timeout", "文件读取超时，请缩小文件范围", 408, True)
            count = wintypes.DWORD()
            if not self.library.ReadFile(self.handle, buffer, CHUNK_BYTES, ctypes.byref(count), None):
                raise AgentError("source_unavailable", "源文件读取失败", 409, True)
            if not count.value:
                break
            yield buffer.raw[:count.value]

    def delete_verified(self):
        if not self.delete_allowed:
            raise AgentError("forbidden", "此句柄不允许删除", 403)
        disposition = ctypes.c_ubyte(1)
        if not self.library.SetFileInformationByHandle(self.handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
            raise AgentError("upload_cleanup_pending", "暂存删除未完成，保留占用供重试", 409)

    def rename_verified(self, destination):
        """Rename this exact private handle without replacement or copy fallback."""
        if not self.delete_allowed:
            raise AgentError('forbidden', '此句柄不允许发布', 403)
        destination = lexical_path(str(destination))
        deny_sensitive(destination)
        if destination[:2].upper() != self.path[:2].upper():
            raise AgentError('unsupported_volume', '正式附件必须与事务目录位于同一卷', 409)
        parts = destination[3:].split('\\')
        for index in range(1, len(parts)):
            self._open(destination[:3] + '\\'.join(parts[:index]), directory=True)
        class RenameInformation(ctypes.Structure):
            _fields_ = [('flags', wintypes.DWORD), ('root', wintypes.HANDLE),
                        ('length', wintypes.DWORD), ('name', wintypes.WCHAR * 1)]
        encoded = destination.encode('utf-16-le')
        size = max(ctypes.sizeof(RenameInformation), RenameInformation.name.offset + len(encoded) + 2)
        buffer = ctypes.create_string_buffer(size)
        information = RenameInformation.from_buffer(buffer)
        information.flags, information.root, information.length = 0, None, len(encoded)
        ctypes.memmove(ctypes.addressof(buffer) + RenameInformation.name.offset, encoded, len(encoded))
        if not self.library.SetFileInformationByHandle(self.handle, 3, buffer, size):
            raise AgentError('attachment_publish_conflict', '正式名称被占用或路径变化，未覆盖任何文件', 409)

    def __exit__(self, *_args):
        for handle in reversed(self.handles):
            self.library.CloseHandle(handle)
        self.handles.clear()
