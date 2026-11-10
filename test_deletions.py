"""AG-136 domain preparation and exact-object, no-replacement trash moves."""

import hashlib
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from server import Repository
from workbench.agent_file_handles import SUPPORTED
from workbench.agent_security import AgentError
from workbench.deletion_prepared import PreparedDelete, deletion_token
from workbench.write_coordinator import content_revision, RevisionConflict


@unittest.skipUnless(SUPPORTED, 'Verified Agent deletion requires Windows fixed NTFS')
class PreparedDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = Repository(self.root)
        self.project = self.repo.create_project({'name':'删除领域验证'})

    def tearDown(self):
        self.temp.cleanup()

    def create(self, kind):
        if kind == 'concept_map':
            item = self.repo.create_concept_map({'title':'完整图原始字节'})
            path = self.root / 'concept-maps' / (item['id'] + '.json')
        elif kind == 'document':
            item = self.repo.create_document({'title':'完整文档', 'body':'多行\n原文 [内容](x) 空格  '})
            _, path = self.repo.get_document(item['id'])
        else:
            item = self.repo.create_record({'type':kind, 'title':'完整记录', 'project_id':self.project['id'],
                                           'body':'完整正文\n\n原始空格  ',
                                           **({'info_fields':[{'name':'说明', 'value':'echo "a"\n  echo b', 'note':'仅记录'}]} if kind == 'info' else {})})
            _, path = self.repo.get_record(item['id'])
        return item, path

    def evidence(self):
        return {p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def test_five_types_prepare_is_pure_and_move_preserves_exact_object_and_bytes(self):
        for kind in ('issue', 'todo', 'info', 'document', 'concept_map'):
            with self.subTest(kind=kind):
                item, path = self.create(kind)
                before = path.read_bytes()
                disk = self.evidence()
                prepared = self.repo.prepare_delete(kind, item['id'], content_revision(before))
                self.assertEqual(self.evidence(), disk)
                self.assertEqual(prepared.before, before)
                token = deletion_token(kind, str(uuid.uuid4()), 1)
                stages = []
                destination = prepared.move(token, checkpoint=stages.append)
                self.assertEqual(stages, ['trash_moved'])
                self.assertFalse(path.exists())
                self.assertEqual(destination.read_bytes(), before)
                self.assertEqual(prepared.verify_trash(token), destination)
                self.assertEqual(self.repo._trash_index(), {})  # Index belongs to the journaled caller.
                self.assertEqual(prepared.source_identity.keys(), {'volume', 'index', 'created'})

    def test_revision_kind_missing_and_legacy_idea_fail_without_writes(self):
        item, path = self.create('issue')
        disk = self.evidence()
        for kind, key, revision, error in (
                ('issue', item['id'], '0' * 64, RevisionConflict),
                ('todo', item['id'], content_revision(path.read_bytes()), FileNotFoundError),
                ('issue', 'ISSUE-9999', '0' * 64, FileNotFoundError),
                ('idea', item['id'], '0' * 64, ValueError),
                ('issue', item['id'], None, ValueError)):
            with self.subTest(kind=kind, key=key, revision=revision), self.assertRaises(error):
                self.repo.prepare_delete(kind, key, revision)
            self.assertEqual(self.evidence(), disk)

    def test_same_bytes_replacement_is_not_the_original_object(self):
        item, path = self.create('document')
        before = path.read_bytes()
        prepared = self.repo.prepare_delete('document', item['id'], content_revision(before))
        replacement = path.with_name('replacement.tmp')
        replacement.write_bytes(before)
        os.replace(replacement, path)
        disk = self.evidence()
        with self.assertRaises(RevisionConflict):
            prepared.move(deletion_token('document', str(uuid.uuid4()), 1))
        self.assertEqual(self.evidence(), disk)

    def test_collision_created_after_final_check_never_replaces_destination(self):
        item, path = self.create('todo')
        before = path.read_bytes()
        prepared = self.repo.prepare_delete('todo', item['id'], content_revision(before))
        token = deletion_token('todo', str(uuid.uuid4()), 1)
        destination = self.root / '.trash' / token
        with self.assertRaises(AgentError):
            prepared.move(token, permit=lambda held:destination.write_bytes(b'foreign occupant'))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(destination.read_bytes(), b'foreign occupant')
        self.assertEqual(self.repo._trash_index(), {})

    def test_changed_bytes_permission_failure_hardlink_and_oversize_do_not_move(self):
        item, path = self.create('info')
        before = path.read_bytes()
        prepared = self.repo.prepare_delete('info', item['id'], content_revision(before))
        token = deletion_token('info', str(uuid.uuid4()), 1)
        def deny(_held):
            raise PermissionError('revoked')
        with self.assertRaises(PermissionError):
            prepared.move(token, permit=deny)
        self.assertEqual(path.read_bytes(), before)
        path.write_bytes(before + b'\nchanged')
        with self.assertRaises(RevisionConflict):
            prepared.move(token)
        path.write_bytes(before)
        hardlink = path.with_name('linked.md')
        os.link(path, hardlink)
        try:
            with self.assertRaises((AgentError, ValueError)):
                self.repo.prepare_delete('info', item['id'], content_revision(before))
        finally:
            hardlink.unlink()
        path.write_bytes(before + b'x' * 1048576)
        with self.assertRaises(ValueError):
            self.repo.prepare_delete('info', item['id'], content_revision(path.read_bytes()))
        self.assertFalse((self.root / '.trash' / token).exists())

    def test_moved_evidence_cannot_be_recreated_from_snapshot_or_matching_copy(self):
        item, path = self.create('concept_map')
        prepared = self.repo.prepare_delete('concept_map', item['id'], content_revision(path.read_bytes()))
        token = deletion_token('concept_map', str(uuid.uuid4()), 1)
        destination = prepared.move(token)
        replacement = self.root / 'unrelated.tmp'
        replacement.write_bytes(prepared.before)
        os.replace(replacement, destination)
        disk = self.evidence()
        with self.assertRaises(RevisionConflict):
            prepared.verify_trash(token)
        self.assertEqual(self.evidence(), disk)
        self.assertFalse(path.exists())

    def test_unsupported_platform_and_uncontrolled_token_are_rejected(self):
        item, path = self.create('document')
        revision = content_revision(path.read_bytes())
        disk = self.evidence()
        with patch('workbench.deletion_prepared.SUPPORTED', False), self.assertRaises(AgentError) as error:
            self.repo.prepare_delete('document', item['id'], revision)
        self.assertEqual(error.exception.code, 'unsupported_platform')
        prepared = self.repo.prepare_delete('document', item['id'], revision)
        for token in ('../escape', 'document-agent-' + str(uuid.uuid4()) + '-0', deletion_token('issue', str(uuid.uuid4()), 1)):
            with self.assertRaises(ValueError):
                prepared.move(token)
        self.assertEqual(self.evidence(), disk)

    def test_held_source_is_internal_live_and_cannot_be_reused_after_move(self):
        from workbench.deletion_inventory import active_inventory
        from workbench.deletion_prepared import HeldDeleteSource
        item, path = self.create('issue')
        prepared = self.repo.prepare_delete('issue', item['id'], content_revision(path.read_bytes()))
        with self.assertRaises(ValueError):
            active_inventory(self.root, item['id'], held_source=prepared)
        with self.assertRaises(ValueError):
            HeldDeleteSource(prepared, None, object())
        captured = []
        def permit(held):
            captured.append(held)
            entries, _ = active_inventory(self.root, item['id'], held_source=held)
            self.assertEqual(next(entry['raw'] for entry in entries if entry['id'] == item['id']), prepared.before)
        prepared.move(deletion_token('issue', str(uuid.uuid4()), 1), permit=permit)
        with self.assertRaises(ValueError):
            active_inventory(self.root, item['id'], held_source=captured[0])


if __name__ == '__main__':
    unittest.main()
