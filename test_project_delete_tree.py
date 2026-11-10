"""AG-138 actual project tree evidence and native rename boundaries."""

import base64
import tempfile
import unittest
from pathlib import Path

from server import Repository
from workbench.agent_file_handles import SUPPORTED
from workbench.project_delete_tree import classify_tree, move_tree, read_tree
from workbench.write_coordinator import RevisionConflict


@unittest.skipUnless(SUPPORTED,'native fixed NTFS tree validation')
class ProjectDeleteTreeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Repository(Path(temp.name))
        self.project = self.repo.create_project({'name':'受控项目','description':'原始说明'})
        self.source = self.repo.projects_dir / self.project['id']
        self.destination = self.repo.trash_dir / 'controlled-test-token'

    def test_classify_full_text_record_and_explicit_indexed_attachment(self):
        record = self.repo.create_record({'type':'info','project_id':self.project['id'],'title':'有序字段',
                                          'info_fields':[{'name':'只记录','value':'echo x\n  echo y'}]})
        asset = self.repo.add_project_asset(self.project['id'],'附件.txt',base64.b64encode(b'example').decode())
        tree = read_tree(self.repo.root,self.source)
        project, records, assets, binaries = classify_tree(self.repo.root,self.project['id'],tree)
        self.assertEqual(project['id'],self.project['id'])
        self.assertEqual(records[0]['item']['id'],record['id'])
        self.assertEqual(records[0]['item']['info_fields'][0]['value'],'echo x\n  echo y')
        self.assertEqual(assets[0]['id'],asset['id'])
        self.assertEqual(binaries,{'assets/library/附件.txt'})
        self.assertNotIn('assets/library/附件.txt',tree.raw_text)
        move_tree(self.repo.root,self.source,self.destination,tree.physical_digest,lambda _:None)
        moved = read_tree(self.repo.root,self.destination)
        self.assertEqual(moved.physical_digest,tree.physical_digest)
        self.assertEqual(moved.portable_digest,tree.portable_digest)
        self.assertFalse(self.source.exists())

    def test_unknown_file_hardlink_and_named_stream_are_rejected(self):
        unknown = self.source / 'unclassified.txt'
        unknown.write_bytes(b'outside taxonomy')
        with self.assertRaises(ValueError):
            read_tree(self.repo.root,self.source)
        unknown.unlink()
        readme = self.source / 'README.md'
        alternate = Path(str(readme) + ':hidden-test-stream')
        alternate.write_bytes(b'not the unnamed stream')
        with self.assertRaisesRegex(ValueError,'数据流'):
            read_tree(self.repo.root,self.source)
        alternate.unlink()
        duplicate = self.repo.root / 'link-proof'
        duplicate.hardlink_to(readme)
        with self.assertRaises(ValueError):
            read_tree(self.repo.root,self.source)

    def test_late_child_before_final_scan_prevents_move_and_after_scan_leaves_evidence(self):
        expected = read_tree(self.repo.root,self.source)
        late = self.source / 'issues/late.md'
        with self.assertRaises((ValueError,RevisionConflict)):
            move_tree(self.repo.root,self.source,self.destination,expected.physical_digest,lambda _:late.write_bytes(b'late'))
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())
        late.unlink()
        with self.assertRaises((ValueError,RevisionConflict)):
            move_tree(self.repo.root,self.source,self.destination,expected.physical_digest,lambda _:None,
                      before_rename=lambda:late.write_bytes(b'late'))
        self.assertFalse(self.source.exists())
        self.assertEqual((self.destination / 'issues/late.md').read_bytes(),b'late')

    def test_destination_member_length_is_checked_before_native_rename(self):
        from workbench.agent_security import AgentError
        leaf = self.source / 'assets/files' / ('a' * (200 - len(str(self.source))))
        leaf.write_bytes(b'test length')
        tree = read_tree(self.repo.root, self.source)
        destination = self.repo.trash_dir / ('d' * 110)
        with self.assertRaises(AgentError):
            move_tree(self.repo.root, self.source, destination, tree.physical_digest, lambda _:None)
        self.assertTrue(leaf.is_file())
        self.assertFalse(destination.exists())
