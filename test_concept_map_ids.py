"""Graph allocation metadata survives failure, deletion and portable recovery."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from server import Repository
from workbench.concept_map_ids import ConceptMapIdentityError
from workbench.paths import relocate_repository


class ConceptMapIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = Repository(self.base / 'data')
        self.cursor = self.repo.config_dir / 'concept-map-ids.json'

    def tearDown(self):
        self.temp.cleanup()

    def evidence(self):
        return {str(path.relative_to(self.repo.root)): path.read_bytes() for path in self.repo.root.rglob('*') if path.is_file()}

    def test_read_and_pure_prepare_never_initialize_and_bad_input_is_zero_write(self):
        self.repo.list_concept_maps()
        self.repo.get_concept_map('CMAP-0001')
        self.repo._concept_map_repository.prepare_create({'title': '纯准备'}, 'CMAP-0001')
        self.assertFalse(self.cursor.exists())
        for payload in ({'title': ''}, {'title': '未来', 'version': 99}, {'title': '越界', 'nodes': [{}] * 501}, None):
            before = self.evidence()
            with self.assertRaises(ValueError): self.repo.create_concept_map(payload)
            self.assertEqual(self.evidence(), before)

    def test_parallel_creates_reopen_purge_and_failed_publication_never_reuse(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            items = list(pool.map(lambda index: self.repo.create_concept_map({'title': f'同名也允许 {index % 2}'}), range(12)))
        self.assertEqual({item['id'] for item in items}, {f'CMAP-{index:04d}' for index in range(1, 13)})
        self.assertEqual(json.loads(self.cursor.read_text(encoding='utf-8'))['high_water'], 12)
        for item in items:
            token = self.repo.delete_concept_map(item['id'])['token']
            self.repo.purge_trash(token)
        self.assertEqual(list(self.repo.concept_maps_dir.iterdir()), [])
        self.repo = Repository(self.repo.root)
        with patch('workbench.concept_maps.PreparedConceptMapWrite.apply', side_effect=OSError('synthetic publication failure')):
            with self.assertRaises(OSError): self.repo.create_concept_map({'title': '不发布但安全跳号'})
        self.assertEqual(self.repo.create_concept_map({'title': '之后创建'})['id'], 'CMAP-0014')

    def test_legacy_formal_history_trash_and_orphan_trash_contribute_to_maximum(self):
        domain = self.repo._concept_map_repository
        old = domain.prepare_create({'title': '旧图'}, 'CMAP-0100')
        self.repo.apply_concept_map_write(old)
        directory = self.repo.history_dir / 'CMAP-0200'
        directory.mkdir()
        (directory / '20261110-000000-000000.json').write_text(json.dumps({'id': 'CMAP-0200', 'version': 2}), encoding='utf-8')
        old = domain.prepare_create({'title': '旧回收图'}, 'CMAP-0300')
        self.repo.apply_concept_map_write(old)
        token = self.repo.delete_concept_map('CMAP-0300')['token']
        (self.repo.trash_dir / 'concept-map-synthetic-orphan').write_text(json.dumps({'id': 'CMAP-0400', 'version': 1}), encoding='utf-8')
        self.assertFalse(self.cursor.exists())
        self.assertEqual(self.repo.create_concept_map({'title': '兼容升级'})['id'], 'CMAP-0401')
        self.repo.purge_trash(token)
        self.assertEqual(self.repo.create_concept_map({'title': '继续'})['id'], 'CMAP-0402')

    def test_unknown_cursor_and_occupancy_fail_closed_without_any_writes(self):
        for value in ({}, {'schema_version': 2, 'high_water': 1}, {'schema_version': True, 'high_water': 1},
                      {'schema_version': 1, 'high_water': True}, {'schema_version': 1, 'high_water': -1},
                      {'schema_version': 1, 'high_water': 1.5}, {'schema_version': 1, 'high_water': 3, 'other': 1}, None):
            self.cursor.write_text(json.dumps(value), encoding='utf-8')
            before = self.evidence()
            with self.assertRaises(ConceptMapIdentityError): self.repo.create_concept_map({'title': '拒绝'})
            self.assertEqual(self.evidence(), before)
        self.cursor.write_text('{invalid', encoding='utf-8')
        before = self.evidence()
        with self.assertRaises(ConceptMapIdentityError): self.repo.create_concept_map({'title': '损坏拒绝'})
        self.assertEqual(self.evidence(), before)
        self.cursor.unlink()
        for value in ('{invalid', json.dumps({'id': 'CMAP-0001', 'version': 99}), json.dumps({'id': 'CMAP-0002', 'version': 2})):
            path = self.repo.concept_maps_dir / 'CMAP-0001.json'
            path.write_text(value, encoding='utf-8')
            before = self.evidence()
            with self.assertRaises(ConceptMapIdentityError): self.repo.create_concept_map({'title': '占用损坏拒绝'})
            self.assertEqual(self.evidence(), before)
        path.unlink()
        history = self.repo.history_dir / 'CMAP-0080'
        history.mkdir()
        (history / 'unknown.json').write_text('{}', encoding='utf-8')
        before = self.evidence()
        with self.assertRaises(ConceptMapIdentityError): self.repo.create_concept_map({'title': '历史未知拒绝'})
        self.assertEqual(self.evidence(), before)

    def test_full_zip_and_actual_migration_keep_cursor_after_all_graphs_purged(self):
        item = self.repo.create_concept_map({'title': '之后永久删除'})
        self.repo.purge_trash(self.repo.delete_concept_map(item['id'])['token'])
        with zipfile.ZipFile(io.BytesIO(self.repo.export_zip())) as archive:
            self.assertIn('config/concept-map-ids.json', archive.namelist())
            restored = self.base / 'restored'
            restored.mkdir()
            archive.extractall(restored)
        copied = Repository(restored)
        self.assertEqual(copied.create_concept_map({'title': '完整ZIP恢复后'})['id'], 'CMAP-0002')
        moved = relocate_repository(self.repo, str(self.base / 'migrated'), True, self.base / 'location.json')
        self.assertEqual(moved.create_concept_map({'title': '实际迁移后'})['id'], 'CMAP-0002')
        project = moved.create_project({'name': '单项目包不含全库游标'})
        with zipfile.ZipFile(io.BytesIO(moved.export_zip(project['id']))) as archive:
            self.assertNotIn('config/concept-map-ids.json', archive.namelist())

    def test_true_exit_after_cursor_write_and_before_formal_publication_skips_id(self):
        script = '''import sys,os
from pathlib import Path
from server import Repository
import workbench.concept_map_ids as ids
r=Repository(Path(sys.argv[1]))
if sys.argv[2]=='cursor':
 original=ids.atomic_write_json
 def write(path,value):
  original(path,value)
  os._exit(73)
 ids.atomic_write_json=write
else:
 r._concept_map_repository.prepare_create=lambda *args,**kwargs:os._exit(73)
r.create_concept_map({'title':'synthetic exit'})
'''
        for stage in ('cursor', 'before_formal'):
            root = self.base / stage
            result = subprocess.run([sys.executable, '-c', script, str(root), stage], cwd=Path(__file__).parent, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 73, result.stderr)
            fresh = Repository(root)
            self.assertEqual(fresh.list_concept_maps(), [])
            self.assertEqual(fresh.create_concept_map({'title': '退出后重开'})['id'], 'CMAP-0002')

    def test_graph_restore_conflicts_and_parallel_restore_create_keep_ids(self):
        graph = self.repo.create_concept_map({'title':'恢复与创建'})
        deleted = self.repo.delete_concept_map(graph['id'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            restoring = pool.submit(self.repo.restore_trash, deleted['token'])
            creating = pool.submit(self.repo.create_concept_map, {'title':'同时创建'})
            self.assertEqual(Path(restoring.result()['restored_path']).name, graph['id'] + '.json')
            self.assertEqual(creating.result()['id'], 'CMAP-0002')
        deleted = self.repo.delete_concept_map(graph['id'])
        source = Path(deleted['trash_path']); destination = Path(deleted['original_path'])
        shutil.copyfile(source, destination)
        evidence = self.evidence()
        with self.assertRaises(FileExistsError): self.repo.restore_trash(deleted['token'])
        self.assertEqual(self.evidence(), evidence)

    def test_other_resource_restore_collision_contract_remains_unchanged(self):
        project = self.repo.create_project({'name':'原项目恢复'})
        record = self.repo.create_record({'project_id':project['id'], 'type':'issue', 'title':'记录恢复'})
        document = self.repo.create_document({'title':'文档恢复', 'category':'未分类'})
        for delete, key in ((self.repo.delete_record, record['id']), (self.repo.delete_document, document['id']), (self.repo.delete_project, project['id'])):
            deleted = delete(key)
            source = Path(deleted['trash_path']); destination = Path(deleted['original_path'])
            if source.is_dir(): shutil.copytree(source, destination)
            else: shutil.copyfile(source, destination)
            restored = self.repo.restore_trash(deleted['token'])
            restored_path = Path(restored['restored_path'])
            self.assertNotEqual(restored_path, destination)
            self.assertIn('-restored-', restored_path.name)
            self.assertTrue(destination.exists())
            self.assertTrue(restored_path.exists())

    def test_unknown_agent_occupancy_preflight_cannot_reset_or_advance_cursor(self):
        from workbench.agent_security import AgentSecurity
        from workbench.agent_service import AgentService
        security = AgentSecurity(self.repo.root, self.base / 'credentials')
        service = AgentService(self.repo, security)
        for path, value in ((service.store.proposals / 'unknown.json', {'schema_version':99}),
                            (service.store.receipts / 'unknown.json', {'kind':'future'}),
                            (service.store.operations / 'unknown' / 'manifest.json', {'schema_version':99})):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding='utf-8')
            before = self.evidence()
            with self.assertRaises((ConceptMapIdentityError, ValueError)):
                self.repo.create_concept_map({'title':'不能跳过未知占用'})
            self.assertEqual(self.evidence(), before)
            path.unlink()


if __name__ == '__main__':
    unittest.main()
