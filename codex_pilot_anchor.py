"""Explicitly managed empty Codex project for isolated AG-142 pilots."""

import argparse
import hashlib
import json
import re
import socket
import stat
from contextlib import contextmanager
from pathlib import Path

from workbench.persistence import atomic_write_bytes, atomic_write_json
from workbench.write_coordinator import DataDirectoryLock


IDLE_CONFIG = b'# Workbench AG-142 idle project. No temporary MCP connection.\n[mcp_servers]\n'
MARKER = '.ag142-anchor'
MARKER_BYTES = b'workbench-ag142-anchor-v1\n'
JOURNAL = '.ag142-active.json'
LOCK = '.workbench-service.lock'


def _check_path(path, directory):
    info = path.lstat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if (not kind(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            or not directory and info.st_nlink != 1):
        raise ValueError('Anchor path contains a link or unexpected file type')


def _anchor_path(path, exists):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or not path.name.casefold().startswith('workbench-ag142-anchor-'):
        raise ValueError('Use an absolute dedicated workbench-ag142-anchor-* path')
    for parent in reversed(path.parents):
        _check_path(parent, directory=True)
    if exists:
        _check_path(path, directory=True)
    return path.resolve()


def init_anchor(path):
    path = _anchor_path(path, exists=False)
    path.mkdir()
    (path / '.codex').mkdir()
    atomic_write_bytes(path / '.codex' / 'config.toml', IDLE_CONFIG)
    atomic_write_bytes(path / MARKER, MARKER_BYTES)
    return path


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _port_closed(port):
    with socket.socket() as probe:
        probe.settimeout(5)
        try:
            probe.connect(('127.0.0.1', port))
        except ConnectionRefusedError:
            return True
    return False


class AnchorSlot:
    def __init__(self, root):
        self.root = root
        self.config = root / '.codex' / 'config.toml'
        self.journal = root / JOURNAL
        self.cleanup_error = None

    def clear(self):
        _check_path(self.root, directory=True)
        _check_path(self.config.parent, directory=True)
        _check_path(self.config, directory=False)
        current = self.config.read_bytes()
        try:
            _check_path(self.journal, directory=False)
        except FileNotFoundError:
            if current != IDLE_CONFIG:
                raise ValueError('Unexpected anchor configuration; preserved for inspection')
            return
        state = json.loads(self.journal.read_bytes())
        if (not isinstance(state, dict) or state.keys() != {'config_sha256', 'port'}
                or not isinstance(state['config_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', state['config_sha256'])
                or type(state['port']) is not int or not 1 <= state['port'] <= 65535):
            raise ValueError('Invalid anchor journal; preserved for inspection')
        if current != IDLE_CONFIG and _digest(current) != state['config_sha256']:
            raise ValueError('Anchor configuration changed outside the fixture; preserved for inspection')
        if not _port_closed(state['port']):
            raise ValueError('Previous pilot port is still open; anchor preserved for inspection')
        _check_path(self.config, directory=False)
        if self.config.read_bytes() != current:
            raise ValueError('Anchor configuration changed during recovery; preserved for inspection')
        if current != IDLE_CONFIG:
            atomic_write_bytes(self.config, IDLE_CONFIG)
        self.journal.unlink()

    def publish(self, text, port):
        _check_path(self.root, directory=True)
        _check_path(self.config.parent, directory=True)
        _check_path(self.config, directory=False)
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('Anchor publication requires the isolated listener port')
        if self.config.read_bytes() != IDLE_CONFIG or self.journal.exists() or self.journal.is_symlink():
            raise ValueError('Anchor is not idle')
        raw = text.encode('utf-8')
        # Record ownership before publishing. Recovery can recognize either
        # side of the atomic replace and never overwrites foreign content.
        atomic_write_json(self.journal, {'config_sha256':_digest(raw), 'port':port})
        _check_path(self.config, directory=False)
        if self.config.read_bytes() != IDLE_CONFIG:
            raise ValueError('Anchor configuration changed before publication; preserved for inspection')
        atomic_write_bytes(self.config, raw)


@contextmanager
def anchor_slot(path):
    if path is None:
        yield None
        return
    root = _anchor_path(path, exists=True)
    if not {item.name for item in root.iterdir()} <= {'.codex', MARKER, JOURNAL, LOCK}:
        raise ValueError('Anchor contains unexpected entries')
    _check_path(root / MARKER, directory=False)
    if (root / MARKER).read_bytes() != MARKER_BYTES:
        raise ValueError('Anchor marker does not match the fixture')
    _check_path(root / '.codex', directory=True)
    if {item.name for item in (root / '.codex').iterdir()} != {'config.toml'}:
        raise ValueError('Anchor contains unexpected Codex configuration')
    try:
        _check_path(root / LOCK, directory=False)
    except FileNotFoundError:
        pass
    with DataDirectoryLock(root):
        slot = AnchorSlot(root)
        slot.clear()
        try:
            yield slot
        finally:
            try:
                slot.clear()
            except (OSError, ValueError) as error:
                # Let the independently owned data directory finish cleanup.
                # The caller reports the anchor failure after that outcome.
                slot.cleanup_error = error


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--init', type=Path, required=True, help='Create an empty managed directory; no Codex settings are changed')
    print(init_anchor(parser.parse_args().init))
