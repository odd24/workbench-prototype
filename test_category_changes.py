"""Pure AG-139 category plans preserve membership and default semantics."""

import base64
import tempfile
import unittest
import uuid
from pathlib import Path

from workbench.category_changes import DEFAULT_NAME, FAMILIES, PROJECT_ASSETS, plan_categories
from workbench.category_identity import FENCE_PATH, IDENTITY_PATH, load_category_identities, namespace_key
from workbench.category_prepared import DOCUMENT, GRAPH, apply_category_files, prepare_category
from workbench.write_coordinator import RevisionConflict


class CategoryChangeTests(unittest.TestCase):
    def test_each_family_creates_renames_deletes_and_reorders(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                old = ['甲', '乙']
                if family != PROJECT_ASSETS:
                    old.append(DEFAULT_NAME)
                create = plan_categories(family, 'create', old, '新增')
                self.assertNotIn('新增', create.before)
                self.assertEqual([name for name in create.after if name != DEFAULT_NAME], ['甲', '乙', '新增'])
                renamed = plan_categories(family, 'rename', create.after, '甲', new_name='新名称')
                self.assertEqual(renamed.member_category('甲'), '新名称')
                self.assertEqual(renamed.member_category('乙'), '乙')
                reordered = plan_categories(family, 'reorder', renamed.after, '新增', anchor='新名称', position='before')
                self.assertEqual(reordered.after[:3], ('新增', '新名称', '乙'))
                deleted = plan_categories(family, 'delete', reordered.after, '乙')
                self.assertEqual(deleted.member_category('乙'), '' if family == PROJECT_ASSETS else DEFAULT_NAME)
                self.assertNotIn('乙', deleted.after)

    def test_project_assets_keep_legacy_named_default_distinct_from_empty_destination(self):
        plan = plan_categories(PROJECT_ASSETS, 'delete', [DEFAULT_NAME, '资料'], DEFAULT_NAME)
        self.assertEqual(plan.after, ('资料',))
        self.assertEqual(plan.member_category(DEFAULT_NAME), '')
        with self.assertRaises(ValueError):
            plan_categories(PROJECT_ASSETS, 'create', ['资料'], DEFAULT_NAME)
        for family in FAMILIES - {PROJECT_ASSETS}:
            with self.assertRaises(ValueError):
                plan_categories(family, 'delete', [DEFAULT_NAME], DEFAULT_NAME)

    def test_category_identity_follows_rename_but_does_not_follow_reused_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / 'config').mkdir()
            family = 'document_category'
            key = namespace_key(family, None)
            initial = load_category_identities(root)
            original = initial.scope(key, ['原名'])['active']['原名']
            self.assertFalse((root / IDENTITY_PATH).exists())
            epoch = str(uuid.uuid4())
            rename = plan_categories(family, 'rename', ['原名'], '原名', new_name='新名')
            moved, fence, ledger = initial.plan(rename, None, epoch)
            self.assertEqual(moved['active']['新名'], original)
            self.assertFalse((root / FENCE_PATH).exists())
            (root / FENCE_PATH).write_bytes(fence)
            with self.assertRaises(ValueError):
                load_category_identities(root)
            (root / IDENTITY_PATH).write_bytes(ledger)
            saved = load_category_identities(root)
            with self.assertRaises(RevisionConflict):
                saved.scope(key, ['原名'])
            create = plan_categories(family, 'create', rename.after, '原名')
            recreated, _, _ = saved.plan(create, None, epoch)
            self.assertEqual(recreated['active']['新名'], original)
            self.assertNotEqual(recreated['active']['原名'], original)
            self.assertGreater(recreated['generations']['原名'], moved['generations']['原名'])

    def test_prepared_document_category_preserves_history_and_sort_with_no_preview_write(self):
        from server import Repository
        with tempfile.TemporaryDirectory() as temp:
            repo = Repository(Path(temp))
            first = repo.create_document({'title':'原文', 'category':'旧类', 'body':'原始正文\n\n完整第二段'})
            repo.ensure_document_category('空类')
            repo.save_document_sort({'file_modes':{'旧类':'manual'}, 'file_orders':{'旧类':[first['id']]}})
            plan = prepare_category(repo, DOCUMENT, 'rename', '旧类', new_name='新类', epoch=str(uuid.uuid4()), managed_time='2026-11-10T12:00:00')
            self.assertEqual(repo.get_document(first['id'])[0]['category'], '旧类')
            self.assertFalse((repo.root / IDENTITY_PATH).exists())
            apply_category_files(repo.root, DOCUMENT, plan.files, plan.watch, history_version='20261110-120000-000000')
            reopened = Repository(repo.root)
            self.assertEqual(reopened.get_document(first['id'])[0]['category'], '新类')
            self.assertEqual(reopened.document_sort()['file_orders']['新类'], [first['id']])
            self.assertIn('空类', reopened.document_categories())
            self.assertEqual(reopened.read_history(first['id'], '20261110-120000-000000')['category'], '旧类')

    def test_prepared_graph_category_rejects_unrelated_member_added_after_preview(self):
        from server import Repository
        with tempfile.TemporaryDirectory() as temp:
            repo = Repository(Path(temp))
            original = repo.create_concept_map({'title':'原图', 'category':'旧类'})
            plan = prepare_category(repo, GRAPH, 'delete', '旧类', epoch=str(uuid.uuid4()), managed_time='2026-11-10T12:00:00')
            repo.create_concept_map({'title':'新图'})
            with self.assertRaises(RevisionConflict):
                apply_category_files(repo.root, GRAPH, plan.files, plan.watch)
            self.assertEqual(repo.get_concept_map(original['id'])[0]['category'], '旧类')
            self.assertFalse((repo.root / IDENTITY_PATH).exists())

    def test_standalone_delete_preserves_record_attachment_and_binary(self):
        from server import Repository
        with tempfile.TemporaryDirectory() as temp:
            repo = Repository(Path(temp))
            project = repo.create_project({'name':'附件项目'})['id']
            record = repo.create_record({'type':'issue', 'title':'保留记录', 'project_id':project})
            original = base64.b64encode(b'original asset').decode()
            repo.save_project_asset_categories(project, [{'name':'旧类','tag':'原标签'}, {'name':'空类','tag':'保留标签'}])
            asset = repo.add_project_asset(project, 'standalone.txt', original, '旧类')
            repo.add_attachment(record['id'], 'record.txt', original)
            repo.update_record_attachment_category(record['id'], 'record.txt', '旧类')
            review = repo.preview_category_change({'operation':'delete',
                'selection':{'family':PROJECT_ASSETS, 'project_id':project, 'name':'旧类'}})
            self.assertEqual([row['id'] for row in review['impact']['members']], [asset['id']])
            repo.approve_category_change({'ticket':review['ticket']})
            reopened = Repository(repo.root)
            self.assertEqual(reopened.project_assets(project)[0]['category'], '')
            self.assertEqual(reopened.project_asset_categories(project), [{'name':'空类','tag':'保留标签'}])
            self.assertEqual(reopened.get_record(record['id'])[0]['attachments'][0]['category'], '旧类')
            self.assertEqual((reopened.projects_dir / project / asset['path']).read_bytes(), b'original asset')
