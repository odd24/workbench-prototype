"""AG-137 project allocation and pure preparation contracts."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from server import Repository
from workbench.project_prepared import prepare_project


class PreparedProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Repository(Path(temporary.name))

    def test_residual_paths_trash_and_concurrent_web_creates_never_get_adopted(self):
        root = self.repo.projects_dir
        (root / 'Alpha').mkdir()
        (root / 'Alpha' / 'keep.txt').write_bytes(b'original')
        (root / 'alpha-2').write_bytes(b'occupied')
        old = self.repo.create_project({'name':'alpha'})
        self.assertEqual(old['id'], 'alpha-3')
        token = self.repo.delete_project(old['id'])['token']
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = set(pool.map(lambda _:self.repo.create_project({'name':'alpha'})['id'], range(2)))
        self.assertEqual(ids, {'alpha-4', 'alpha-5'})
        self.assertEqual((root / 'Alpha' / 'keep.txt').read_bytes(), b'original')
        self.assertFalse((root / 'Alpha' / 'README.md').exists())
        reopened = Repository(self.repo.root)
        self.assertEqual({item['id'] for item in reopened.list_projects()}, ids)
        self.assertEqual(reopened.restore_trash(token)['id'], old['id'])
        self.assertEqual(reopened.create_project({'name':'CON.txt'})['id'], 'project-CON.txt')

    def test_pure_fixed_candidate_and_canonical_order_preserve_effective_order(self):
        for name in ('甲', '乙', '丙'):
            self.repo.create_project({'name':name})
        sorting = self.repo.config_dir / 'project-sort.json'
        sorting.write_text('{"mode":"custom","order":["甲","乙","甲","失效"]}', encoding='utf-8')
        original = sorting.read_bytes()
        candidate = prepare_project(self.repo, {'name':' 新项目 ', 'description':' 多行\n描述 ', 'status':'paused'})
        self.assertEqual(candidate.visible_before, [item['id'] for item in self.repo.list_projects()])
        self.assertEqual(candidate.visible_after, ['乙', '甲', '丙', '新项目'])
        self.assertEqual(json.loads(candidate.sort_after)['order'], candidate.visible_after)
        self.assertEqual(sorting.read_bytes(), original)
        self.assertFalse((self.repo.root / candidate.relative_path).exists())
        meta, raw = candidate.readme()
        self.assertEqual(meta['status'], 'paused')
        self.assertIn('多行\n描述', raw)
        self.assertEqual(prepare_project(self.repo, {'name':'改名'}, project_id=candidate.project_id).project_id, candidate.project_id)
        (self.repo.root / candidate.relative_path).mkdir()
        with self.assertRaises(FileExistsError):
            prepare_project(self.repo, {'name':'改名'}, project_id=candidate.project_id)

    def test_noncustom_keeps_exact_bytes_and_invalid_candidate_never_publishes(self):
        sorting = self.repo.config_dir / 'project-sort.json'
        original = b'{"mode": "name", "order": []}\r\n'
        sorting.write_bytes(original)
        candidate = prepare_project(self.repo, {'name':'候选'}, occupied={'候选'})
        self.assertEqual(candidate.project_id, '候选-2')
        self.assertEqual(candidate.sort_before, original)
        self.assertEqual(candidate.sort_after, original)
        for fields in ({'name':'\n注入'}, {'workflow_template':'不存在'}, {'status':'other'}, {'color':'red'}, {'project_ids':['*']}, {'description':False}, {'name':'{\'coerced\': True}'}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                prepare_project(self.repo, {'name':'候选', **fields})
        self.assertEqual(list(self.repo.projects_dir.iterdir()), [])
        self.assertEqual(sorting.read_bytes(), original)
        sorting.write_bytes(b'{"mode":"custom","mode":"name","order":[]}')
        with self.assertRaises(ValueError):
            prepare_project(self.repo, {'name':'候选'})

    def test_native_stage_moves_exact_tree_and_refuses_late_occupation(self):
        from workbench.agent_file_handles import SUPPORTED
        from workbench.agent_security import AgentError
        from workbench.project_directory import probe_publication, publish_project, stage_project, verify_project
        if not SUPPORTED:
            self.skipTest('Windows directory publication only')
        candidate = prepare_project(self.repo, {'name':'发布证据'})
        raw = candidate.readme()[1].encode('utf-8')
        stage = self.repo.root / 'test-stage'
        target = self.repo.root / candidate.relative_path
        probe_publication(self.repo.root, stage, target)
        original = stage_project(self.repo.root, stage, raw)
        with self.assertRaises(FileExistsError):
            stage_project(self.repo.root, stage, raw)
        with self.assertRaises(AgentError):
            publish_project(self.repo.root, stage, target, raw, original, target.mkdir)
        self.assertEqual(verify_project(self.repo.root, stage, raw), original)
        self.assertEqual(list(target.iterdir()), [])
        target.rmdir()
        publish_project(self.repo.root, stage, target, raw, original, lambda:None)
        self.assertFalse(stage.exists())
        self.assertEqual(verify_project(self.repo.root, target, raw), original)
        self.assertEqual(Repository(self.repo.root).project(candidate.project_id)['name'], '发布证据')


if __name__ == '__main__':
    unittest.main()
