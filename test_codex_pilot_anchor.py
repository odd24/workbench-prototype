"""Ownership and failure recovery for the isolated Codex pilot directory."""

import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_pilot_anchor import IDLE_CONFIG, JOURNAL, AnchorSlot, anchor_slot, init_anchor
from workbench.persistence import atomic_write_bytes


class AnchorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = init_anchor(self.base / 'workbench-ag142-anchor-unit')
        self.config = self.root / '.codex' / 'config.toml'
        with socket.socket() as endpoint:
            endpoint.bind(('127.0.0.1', 0))
            self.port = endpoint.getsockname()[1]

    def test_lease_rejects_parallel_run_and_clears_only_owned_candidate(self):
        with anchor_slot(self.root) as slot:
            slot.publish('# synthetic candidate A\n', self.port)
            with self.assertRaises(FileExistsError), anchor_slot(self.root):
                self.fail('A second run entered the active anchor')
            self.assertEqual(self.config.read_bytes(), b'# synthetic candidate A\n')
        self.assertEqual(self.config.read_bytes(), IDLE_CONFIG)
        self.assertFalse((self.root / JOURNAL).exists())
        with anchor_slot(self.root) as slot:
            slot.publish('# synthetic candidate B\n', self.port)
        self.assertEqual(self.config.read_bytes(), IDLE_CONFIG)

    def test_recovery_refuses_live_port_then_clears_owned_stale_config(self):
        with socket.socket() as endpoint:
            endpoint.bind(('127.0.0.1', 0))
            endpoint.listen()
            AnchorSlot(self.root).publish('# abandoned candidate\n', endpoint.getsockname()[1])
            with self.assertRaisesRegex(ValueError, 'still open'), anchor_slot(self.root):
                self.fail('Recovery reset a running pilot')
        with anchor_slot(self.root):
            self.assertEqual(self.config.read_bytes(), IDLE_CONFIG)
        self.assertFalse((self.root / JOURNAL).exists())

    def test_external_configuration_is_preserved_and_existing_root_is_not_adopted(self):
        with self.assertRaises(FileExistsError):
            init_anchor(self.root)
        foreign = b'# foreign configuration\n'
        with anchor_slot(self.root) as slot:
            slot.publish('# owned candidate\n', self.port)
            atomic_write_bytes(self.config, foreign)
        self.assertIsInstance(slot.cleanup_error, ValueError)
        with self.assertRaisesRegex(ValueError, 'changed outside'), anchor_slot(self.root):
            self.fail('Recovery accepted a foreign edit')
        self.assertEqual(self.config.read_bytes(), foreign)
        self.assertTrue((self.root / JOURNAL).exists())

    def test_recovery_recognizes_idle_bytes_when_publication_was_interrupted(self):
        with patch('codex_pilot_anchor.atomic_write_bytes', side_effect=OSError('synthetic publication failure')):
            with self.assertRaises(OSError):
                AnchorSlot(self.root).publish('# unpublished candidate\n', self.port)
        self.assertEqual(self.config.read_bytes(), IDLE_CONFIG)
        self.assertTrue((self.root / JOURNAL).exists())
        with anchor_slot(self.root):
            self.assertFalse((self.root / JOURNAL).exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows file lock behavior')
    def test_locked_config_does_not_prevent_independent_data_cleanup_and_can_recover(self):
        data = tempfile.TemporaryDirectory(dir=self.base)
        self.addCleanup(data.cleanup)
        root = Path(data.name)
        (root / 'data-and-private-fixture').write_bytes(b'synthetic')
        with anchor_slot(self.root) as slot:
            slot.publish('# locked candidate\n', self.port)
            held = self.config.open('rb')
            self.addCleanup(held.close)
        try:
            self.assertIsInstance(slot.cleanup_error, PermissionError)
            data.cleanup()
            self.assertFalse(root.exists())
            self.assertEqual(held.read(), b'# locked candidate\n')
            self.assertTrue((self.root / JOURNAL).exists())
        finally:
            held.close()
        with anchor_slot(self.root):
            self.assertEqual(self.config.read_bytes(), IDLE_CONFIG)


if __name__ == '__main__':
    unittest.main()
