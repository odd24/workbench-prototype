import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import Repository
from workbench.deletion_inventory import active_inventory
from workbench.references import references


class DeletionInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = Repository(self.root)
        self.project = self.repo.create_project({'name':'活动引用盘点'})
        self.document = self.repo.create_document({'title':'删除目标', 'body':'完整目标正文'})

    def tearDown(self):
        self.temp.cleanup()

    def test_shared_recognizer_uses_existing_syntax_and_ignores_external_links(self):
        found = references({'body':'代码示例 `[[DOC-0001#body]]` [[DOC-0001#attachment:a%20b.png]] /?item=concept_map&itemId=CMAP-0002',
                            'info_fields':[{'name':'说明', 'value':'/?item=document&itemId=DOC-0003'}],
                            'links':['DOC-0004'], 'other':'https://example.org/?item=document&itemId=DOC-9999'})
        self.assertEqual([x['id'] for x in found], ['DOC-0001', 'DOC-0001', 'CMAP-0002', 'DOC-0003', 'DOC-0004'])
        self.assertEqual(found[1]['attachment'], 'a b.png')
        with self.assertRaises(ValueError):
            references('[[DOC-0001#unknown]]', strict=True)
        with self.assertRaises(ValueError):
            references('/?item=concept_map&itemId=CMAP-0001&extra=1', strict=True)
        self.assertEqual(references('ordinary DOC-0001, no syntax'), [])

    def test_all_formal_source_kinds_are_bound_but_history_and_trash_are_not_active(self):
        key = self.document['id']
        info = self.repo.create_record({'type':'info', 'title':'字段内引用', 'project_id':self.project['id'],
                                       'info_fields':[{'name':'引用说明', 'value':f'[[{key}]]', 'note':'不执行'}]})
        self.repo.update_project(self.project['id'], {'description':f'项目说明 [[{key}]]'})
        legacy = self.root / 'ideas' / 'IDEA-0099.md'
        legacy.write_text(f'---\nid: IDEA-0099\ntype: idea\ntitle: 旧想法\n---\n[[{key}]]', encoding='utf-8')
        graph = self.repo.create_concept_map({'title':f'[[{key}]]', 'nodes':[{'id':'n1', 'text':'node'}]})
        before = {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        entries, revision = active_inventory(self.root, target_id=key)
        matches = {item['id'] for item in entries if any(ref['id'] == key for ref in item['references'])}
        self.assertEqual(matches, {info['id'], self.project['id'], 'IDEA-0099', graph['id']})
        self.assertEqual({p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, before)
        self.assertEqual({x['id'] for x in self.repo.list_document_backlinks(key)}, {info['id']})
        self.repo.delete_record(info['id'])
        after, changed = active_inventory(self.root)
        self.assertNotEqual(changed, revision)
        self.assertNotIn(info['id'], {x['id'] for x in after})

    def test_unknown_future_duplicate_and_unreadable_set_are_not_silently_skipped(self):
        graph = self.repo.create_concept_map({'title':'图'})
        path = self.root / 'concept-maps' / (graph['id'] + '.json')
        original = path.read_bytes()
        path.write_text(json.dumps({**graph, 'version':99}), encoding='utf-8')
        with self.assertRaises(ValueError):
            active_inventory(self.root)
        path.write_bytes(original)
        document_path = self.repo.get_document(self.document['id'])[1]
        duplicate = document_path.with_name('duplicate.md')
        duplicate.write_bytes(document_path.read_bytes())
        with self.assertRaises(ValueError):
            active_inventory(self.root)
        duplicate.unlink()
        document_path.write_bytes(document_path.read_bytes() + b'x' * 1048576)
        with self.assertRaises(ValueError):
            active_inventory(self.root)

    def test_unrelated_change_and_new_source_change_the_binding(self):
        _, first = active_inventory(self.root)
        item = self.repo.create_document({'title':'无关文档', 'body':'无引用'})
        _, second = active_inventory(self.root)
        self.assertNotEqual(first, second)
        self.repo.update_document(item['id'], {'body':'普通变化'})
        _, third = active_inventory(self.root)
        self.assertNotEqual(second, third)
        with patch('workbench.deletion_inventory.INVENTORY_FILES', 1), self.assertRaises(ValueError):
            active_inventory(self.root)
        with patch('workbench.deletion_inventory.INVENTORY_BYTES', 1), self.assertRaises(ValueError):
            active_inventory(self.root)

    def test_exact_file_and_aggregate_byte_limits_and_incremental_retention(self):
        from workbench.deletion_inventory import INVENTORY_BYTES
        # All actual source bytes count, including the initial project/document.
        entries, _ = active_inventory(self.root)
        self.assertTrue(all('raw' not in entry and 'body' not in entry['item'] for entry in entries))
        initial = sum((self.root / entry['relative_path']).stat().st_size for entry in entries)
        remaining = INVENTORY_BYTES - initial
        for index in range(32):
            key = f'DOC-{index + 1000:04d}'
            header = f'---\nid: {key}\ntype: document\ntitle: 原始字节边界\n---\n'.encode('utf-8')
            length = min(1048576, remaining)
            (self.root / 'documents' / (key + '.md')).write_bytes(header + b'x' * (length - len(header)))
            remaining -= length
        self.assertEqual(remaining, 0)
        entries, _ = active_inventory(self.root)
        self.assertTrue(all('raw' not in entry and 'body' not in entry['item'] for entry in entries))
        last = self.root / 'documents' / 'DOC-1031.md'
        last.write_bytes(last.read_bytes() + b'x')
        with self.assertRaisesRegex(ValueError, '集合.*字节'):
            active_inventory(self.root)
        first = self.root / 'documents' / 'DOC-1000.md'
        first.write_bytes(first.read_bytes() + b'x')
        with self.assertRaisesRegex(ValueError, '来源超过1MiB'):
            active_inventory(self.root)

    def test_exact_4096_files_and_one_more_are_not_partially_scanned(self):
        for index in range(4094):
            key = f'DOC-{index + 1000:04d}'
            (self.root / 'documents' / (key + '.md')).write_text(f'---\nid: {key}\ntype: document\ntitle: 项目\n---\n正文', encoding='utf-8')
        entries, _ = active_inventory(self.root)
        self.assertEqual(len(entries), 4096)
        (self.root / 'documents' / 'DOC-9999.md').write_text('---\nid: DOC-9999\ntype: document\ntitle: 超限\n---\n正文', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '集合超过完整扫描'):
            active_inventory(self.root)

    def test_duplicate_json_fields_cannot_hide_an_active_reference(self):
        path = self.root / 'concept-maps' / 'CMAP-9999.json'
        path.write_text('{"id":"CMAP-9999","version":2,"nodes":[{"text":"[[DOC-0001]]","text":"hidden"}]}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '重复字段'):
            active_inventory(self.root, target_id='DOC-0001')


if __name__ == '__main__':
    unittest.main()
