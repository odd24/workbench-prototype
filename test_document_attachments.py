"""Document attachment storage, web operations, references and portable exports."""

import io
import json
import tempfile
import unittest
import uuid
from pathlib import Path

from server import Repository


class DocumentAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Repository(Path(self.temp.name) / 'data')
        self.document = self.repo.create_document({'title':'知识文档', 'category':'分类', 'body':'原文\n'})

    def short(self, action):
        with self.repo.write_lock:
            return action()

    def upload(self, data=b'file bytes', name='中文 [图](1)%#.txt'):
        key = str(uuid.uuid4())
        result = self.repo.document_uploads.receive(self.document['id'], key, name, len(data), self.document['revision'], io.BytesIO(data), self.short)
        return key, result

    def test_web_upload_is_persisted_and_query_does_not_duplicate(self):
        key, result = self.upload()
        self.assertEqual(result['state'], 'completed')
        receipt = result['receipt']
        self.assertEqual(self.repo.attachment_path(self.document['id'], receipt['attachment']['name']).read_bytes(), b'file bytes')
        self.assertEqual(self.repo.document_uploads.query(self.document['id'], key, self.short), result)
        reloaded = Repository(self.repo.root)
        document, _ = reloaded.get_document(self.document['id'])
        self.assertEqual(len(document['attachments']), 1)
        stored = Path(document['file_path']).read_text(encoding='utf-8')
        self.assertTrue(stored.split('attachments:\n', 1)[1].startswith('  - \"'))
        updated = reloaded.update_document(document['id'], {'body':document['body'], 'expected_revision':document['revision']})
        self.assertTrue(Path(updated['file_path']).read_text(encoding='utf-8').split('attachments:\n', 1)[1].startswith('  - \"'))
        from workbench.assets import AttachmentRepository
        self.assertEqual(document['body'].count(AttachmentRepository.attachment_link(receipt['attachment'])), 1)
        self.assertIn('原文', document['body'])
        self.assertEqual(len(reloaded.list_document_history(document['id'])), 2)

    def test_conflict_and_interrupted_stream_do_not_publish_links(self):
        key = str(uuid.uuid4())
        with self.assertRaises(ValueError):
            self.repo.document_uploads.receive(self.document['id'], key, 'part.txt', 9, self.document['revision'], io.BytesIO(b'part'), self.short)
        self.assertEqual(self.repo.document_uploads.query(self.document['id'], key, self.short)['state'], 'failed')
        self.assertFalse(self.repo.get_document(self.document['id'])[0].get('attachments'))
        self.repo.update_document(self.document['id'], {'body':'外部变化'})
        with self.assertRaises(FileExistsError):
            self.upload()
        self.assertFalse(list((self.repo.global_assets_dir / 'files').glob('*')))

    def test_raw_body_unknown_metadata_and_history_restore_roundtrip(self):
        from workbench.markdown_io import dump_markdown, load_markdown_text
        from workbench.write_coordinator import content_revision
        path = Path(self.document['file_path'])
        meta, _ = load_markdown_text(path.read_text(encoding='utf-8'))
        meta['unknown'] = {'value':'双引号" 空格'}
        meta['project_id'] = 'legacy-unknown-project-field'
        raw = '\r\n\r\n  原始正文  \r\n\r\n'
        header = dump_markdown(meta, '').split('\n---\n', 1)[0] + '\n---\n'
        path.write_bytes((header + raw).encode('utf-8'))
        self.document = self.repo.get_document(self.document['id'])[0]
        self.upload()
        uploaded, _ = self.repo.get_document(self.document['id'])
        self.assertEqual(uploaded['unknown'], meta['unknown'])
        self.assertEqual(uploaded['project_id'], meta['project_id'])
        self.assertTrue(path.read_bytes().split(b'\n---\n', 1)[1].startswith(raw.encode('utf-8')))
        self.assertNotIn('body:', path.read_text(encoding='utf-8').split('\n---\n', 1)[0])
        old = self.repo.list_document_history(uploaded['id'])[0]['version']
        self.repo.restore_document_history(uploaded['id'], old, uploaded['revision'])
        restored = self.repo.get_document(uploaded['id'])[0]
        self.assertEqual(restored.get('attachments'), [])
        self.assertEqual(restored['unknown'], meta['unknown'])
        history = self.repo.list_document_history(uploaded['id'])
        with_attachment = next(item for item in history if self.repo.read_history(uploaded['id'], item['version']).get('attachments'))
        restored = self.repo.restore_document_history(uploaded['id'], with_attachment['version'], restored['revision'])
        self.assertEqual(len(restored['attachments']), 1)

    def test_shared_metadata_body_history_and_trash_protect_assets(self):
        from workbench.assets import AttachmentRepository
        key, result = self.upload()
        item = result['receipt']['attachment']
        asset = self.repo.attachment_path(self.document['id'], item['name'])
        other = self.repo.create_document({'title':'共享引用', 'body':AttachmentRepository.attachment_link(item)})
        self.assertEqual(self.repo.orphan_asset_report()['warnings'], [])
        self.assertNotIn(str(asset), {x['path'] for x in self.repo.orphan_assets()})
        deleted = self.repo.delete_document(self.document['id'])
        self.assertEqual(self.repo.cleanup_orphan_assets()['removed'], 0)
        self.repo.restore_trash(deleted['token'])
        self.assertTrue(asset.exists())
        # The shared body remains sufficient after the owner's metadata is gone.
        deleted_again = self.repo.delete_document(self.document['id'])
        self.repo.purge_trash(deleted_again['token'])
        self.assertTrue(asset.exists())
        self.assertEqual(self.repo.cleanup_orphan_assets()['removed'], 0)
        self.assertIn('共享引用', self.repo.get_document(other['id'])[0]['title'])

    def test_unknown_metadata_keeps_orphans_and_reports_without_private_path(self):
        path = self.repo.global_assets_dir / 'files' / 'orphan.txt'
        path.parent.mkdir(); path.write_bytes(b'orphan')
        docpath = Path(self.document['file_path'])
        docpath.write_text('not a valid owner', encoding='utf-8')
        report = self.repo.orphan_asset_report()
        self.assertEqual(report['orphans'], [])
        self.assertTrue(report['warnings'])
        self.assertNotIn(str(self.repo.root), json.dumps(report['warnings']))
        self.assertEqual(self.repo.cleanup_orphan_assets()['removed'], 0)
        self.assertTrue(path.exists())

    def test_zip_copy_resolves_metadata_body_internal_and_external_images(self):
        import zipfile
        from urllib.parse import unquote
        from workbench.document_attachments import attachment_items, local_links
        from workbench.markdown_io import load_markdown
        key, result = self.upload(data=b'unique bytes')
        item = result['receipt']['attachment']
        image = self.repo.documents_dir / 'outside image.png'; image.write_bytes(b'png bytes')
        shared = self.repo.create_document({'title':'导出共享', 'body':f"[[{self.document['id']}#attachment:{__import__('urllib.parse', fromlist=['quote']).quote(item['name'])}]]\n\n![图](outside%20image.png)"})
        originals = {p:p.read_bytes() for p in self.repo.documents_dir.glob('*.md')}
        content = self.repo.export_documents_zip([self.document['id'], shared['id']])
        with tempfile.TemporaryDirectory() as extracted:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                self.assertTrue(all(not n.startswith('/') and '..' not in Path(n).parts for n in archive.namelist()))
                self.assertEqual(len([n for n in archive.namelist() if n.startswith('assets/')]), 2)
                archive.extractall(extracted)
            for md in Path(extracted).glob('*.md'):
                meta, body = load_markdown(md)
                for attachment in attachment_items(meta.get('attachments', [])):
                    self.assertEqual((md.parent / attachment['path']).read_bytes(), b'unique bytes')
                for _match, source in local_links(body):
                    self.assertIn((md.parent / unquote(source)).read_bytes(), (b'unique bytes', b'png bytes'))
        self.assertEqual({p:p.read_bytes() for p in originals}, originals)
        self.assertIn('../assets/', self.repo.export_document(self.document['id'])[0].decode('utf-8'))

    def test_download_cross_owner_paths_and_missing_export_are_rejected(self):
        self.upload()
        other = self.repo.create_document({'title':'其他文档'})
        item = self.repo.get_document(self.document['id'])[0]['attachments'][0]
        if isinstance(item, str): item = json.loads(item)
        self.assertIsNone(self.repo.attachment_path(other['id'], item['name']))
        self.repo.attachment_path(self.document['id'], item['name']).unlink()
        with self.assertRaises(FileNotFoundError):
            self.repo.export_documents_zip([self.document['id']])

    def test_completed_compaction_failed_retirement_and_empty_initialization(self):
        from unittest.mock import patch
        key, result = self.upload()
        self.repo.document_uploads.maintain(self.short, cleanup=True)
        value = self.repo.document_uploads.load(key)
        self.assertTrue(value['compacted'])
        self.assertFalse((self.repo.document_uploads.folder(key) / 'before.md').exists())
        self.assertEqual(self.repo.document_uploads.query(self.document['id'], key, self.short)['receipt'], result['receipt'])
        self.document = self.repo.get_document(self.document['id'])[0]
        failed = str(uuid.uuid4())
        with self.assertRaises(ValueError):
            self.repo.document_uploads.receive(self.document['id'], failed, 'failed.txt', 10, self.document['revision'], io.BytesIO(b'partial'), self.short)
        def fail(stage):
            if stage == 'failed_deleted': raise OSError('synthetic cleanup exit')
        with patch.object(self.repo.document_uploads, 'checkpoint', fail), self.assertRaises(OSError):
            self.repo.document_uploads.maintain(self.short, cleanup=True)
        self.assertFalse(self.repo.document_uploads.load(failed)['removed'])
        self.repo.document_uploads.maintain(self.short, cleanup=True)
        self.assertTrue(self.repo.document_uploads.load(failed)['removed'])
        empty = str(uuid.uuid4()); self.repo.document_uploads.folder(empty).mkdir()
        self.assertEqual(self.repo.document_uploads.report()['errors'][0]['operation_id'], empty)
        self.repo.document_uploads.abandon_empty(empty, self.short)
        self.assertEqual(self.repo.document_uploads.load(empty)['state'], 'abandoned')
        self.assertEqual(self.repo.document_uploads.report()['errors'], [])

    def test_large_terminal_catalog_does_not_exhaust_active_slots_and_old_result_stays(self):
        from workbench.persistence import atomic_write_json
        import copy
        key, original = self.upload()
        self.repo.document_uploads.maintain(self.short, cleanup=True)
        template = self.repo.document_uploads.load(key)
        # Synthetic terminal receipts isolate the active-vs-historical limit;
        # this is not a claim of 1001 end-to-end file uploads or a performance run.
        for _ in range(1001):
            item = copy.deepcopy(template); new_key = str(uuid.uuid4())
            item['operation_id'] = new_key
            item['receipt']['attachment']['id'] = 'ASSET-' + uuid.UUID(new_key).hex
            folder = self.repo.document_uploads.folder(new_key); folder.mkdir()
            atomic_write_json(folder / 'operation.json', item)
        self.document = self.repo.get_document(self.document['id'])[0]
        self.upload(data=b'new', name='new.txt')
        self.assertEqual(self.repo.document_uploads.query(self.document['id'], key, self.short)['receipt'], original['receipt'])

    def test_real_process_exit_stages_recover_without_agent(self):
        import subprocess
        import sys
        script = '''
import io, os, sys
from pathlib import Path
from server import Repository
r=Repository(Path(sys.argv[1])); doc=r.get_document(sys.argv[2])[0]
r.document_uploads.checkpoint=lambda stage: os._exit(71) if stage==sys.argv[4] else None
r.document_uploads.receive(doc['id'],sys.argv[3],'exit.txt',5,doc['revision'],io.BytesIO(b'bytes'),lambda action:action())
'''
        for stage in ('folder_created', 'receiving', 'stream_identity', 'stream_fsynced', 'prepared', 'identity', 'applying', 'binary', 'history', 'target', 'completed'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'data'; repo = Repository(root)
                document = repo.create_document({'title':'退出恢复', 'category':'原分类', 'body':'原文'})
                key = str(uuid.uuid4())
                exited = subprocess.run([sys.executable, '-c', script, str(root), document['id'], key, stage], capture_output=True, timeout=20)
                self.assertEqual(exited.returncode, 71, exited.stderr.decode(errors='replace'))
                recovered = Repository(root)
                if stage == 'folder_created':
                    self.assertEqual(recovered.document_uploads.report()['errors'][0]['operation_id'], key)
                    recovered.document_uploads.abandon_empty(key, lambda action:action())
                    self.assertEqual(recovered.document_uploads.load(key)['state'], 'abandoned')
                    continue
                result = recovered.document_uploads.query(document['id'], key, lambda action:action())
                if stage in {'receiving', 'stream_identity', 'stream_fsynced'}:
                    self.assertEqual(result['state'], 'failed')
                    self.assertFalse(recovered.get_document(document['id'])[0].get('attachments'))
                    recovered.document_uploads.maintain(lambda action:action(), cleanup=True)
                else:
                    self.assertEqual(result['state'], 'completed')
                    saved = recovered.get_document(document['id'])[0]
                    self.assertEqual(len(saved['attachments']), 1)
                    self.assertEqual(recovered.attachment_path(document['id'], 'exit.txt').read_bytes(), b'bytes')
                    self.assertEqual(recovered.document_uploads.query(document['id'], key, lambda action:action()), result)

    def test_unknown_log_preflight_is_zero_write_and_completed_receipt_is_strict(self):
        from workbench.document_uploads import UploadRecoveryError
        key, result = self.upload()
        log = self.repo.document_uploads.folder(key) / 'operation.json'
        original = log.read_bytes()
        for change in ('schema_bool', 'receipt_revision', 'receipt_size', 'filename_bool', 'state_array', 'mime_object', 'future_view_field'):
            value = json.loads(original)
            if change == 'schema_bool': value['schema_version'] = True
            elif change == 'receipt_revision': value['receipt']['revision'] = '0' * 64
            elif change == 'receipt_size': value['receipt']['attachment']['size'] = True
            elif change == 'filename_bool': value['filename'] = True
            elif change == 'state_array': value['state'] = []
            elif change == 'mime_object': value['view']['attachment']['mime'] = {}
            else: value['view']['future_field'] = True
            log.write_text(json.dumps(value), encoding='utf-8')
            before = {p:p.read_bytes() for p in self.repo.root.rglob('*') if p.is_file()}
            self.assertTrue(self.repo.orphan_asset_report()['warnings'])
            with self.assertRaises(UploadRecoveryError):
                self.repo.document_uploads.maintain(self.short, cleanup=True)
            self.assertEqual({p:p.read_bytes() for p in before}, before)
        log.write_bytes(original)

    def test_real_exit_during_terminal_cleanup_keeps_original_result_and_budget(self):
        import subprocess
        import sys
        script = '''
import os,sys
from pathlib import Path
from server import Repository
r=Repository(Path(sys.argv[1]))
r.document_uploads.checkpoint=lambda stage:os._exit(72) if stage==sys.argv[2] else None
r.document_uploads.maintain(lambda action:action(),cleanup=True)
'''
        for stage in ('compacted', 'failed_deleted', 'failed_retired'):
            with self.subTest(stage=stage):
                case = DocumentAttachmentTests(); case.setUp()
                try:
                    key, result = case.upload()
                    case.document = case.repo.get_document(case.document['id'])[0]
                    failed = str(uuid.uuid4())
                    with self.assertRaises(ValueError):
                        case.repo.document_uploads.receive(case.document['id'], failed, 'partial.txt', 10, case.document['revision'], io.BytesIO(b'part'), case.short)
                    child = subprocess.run([sys.executable, '-c', script, str(case.repo.root), stage], capture_output=True, timeout=30)
                    self.assertEqual(child.returncode, 72, child.stderr.decode(errors='replace'))
                    repo = Repository(case.repo.root)
                    repo.document_uploads.maintain(lambda action:action(), cleanup=True)
                    self.assertTrue(repo.document_uploads.load(failed)['removed'])
                    self.assertEqual(repo.document_uploads.query(case.document['id'], key, lambda action:action())['receipt'], result['receipt'])
                finally: case.doCleanups()

    def test_valid_orphan_cleanup_and_record_external_body_history_are_not_disabled(self):
        project = self.repo.create_project({'name':'旧记录资源'})
        record = self.repo.create_record({'type':'issue', 'title':'外部图片', 'project_id':project['id'], 'body':'![外部](../assets/images/external.png)'})
        image = self.repo.projects_dir / project['id'] / 'assets' / 'images' / 'external.png'
        image.parent.mkdir(parents=True, exist_ok=True); image.write_bytes(b'png')
        orphan = self.repo.global_assets_dir / 'files' / 'real-orphan.txt'
        orphan.parent.mkdir(); orphan.write_bytes(b'orphan')
        report = self.repo.orphan_asset_report()
        self.assertEqual(report['warnings'], [])
        self.assertEqual({x['path'] for x in report['orphans']}, {str(orphan)})
        self.assertEqual(self.repo.cleanup_orphan_assets()['removed'], 1)
        self.repo.update_record(record['id'], {'body':'移除正文但历史保留'})
        self.assertEqual(self.repo.cleanup_orphan_assets()['removed'], 0)
        deleted = self.repo.delete_record(record['id'])
        self.assertEqual(self.repo.cleanup_orphan_assets()['removed'], 0)
        self.repo.restore_trash(deleted['token'])
        self.assertTrue(image.exists())

    def test_internal_document_attachment_backlink_and_tampered_targets(self):
        _key, result = self.upload()
        name = result['receipt']['attachment']['name']
        from urllib.parse import quote
        other = self.repo.create_document({'title':'引用附件的文档', 'body':f"[[{self.document['id']}#attachment:{quote(name)}]]"})
        self.assertIn(other['id'], {x['id'] for x in self.repo.list_document_backlinks(self.document['id'])})
        path = Path(self.document['file_path'])
        from workbench.markdown_io import load_markdown, dump_markdown
        meta, body = load_markdown(path)
        for source in ('../../outside.png', '../assets/files/%2E%2E/%2E%2E/config/settings.json', 'C:/synthetic.png'):
            meta['attachments'] = [json.dumps({'name':'evil.png', 'path':source, 'mime':'image/png', 'size':1})]
            path.write_text(dump_markdown(meta, body), encoding='utf-8')
            self.assertIsNone(self.repo.attachment_path(self.document['id'], 'evil.png'))
            self.assertEqual(next(x for x in self.repo.list_reference_targets() if x['id'] == self.document['id'])['attachments'], [])
            with self.assertRaises((ValueError, FileNotFoundError)):
                self.repo.export_documents_zip([self.document['id']])

    def test_one_gib_declared_reservations_have_exact_boundary_and_can_retire(self):
        from workbench.persistence import atomic_write_json
        import copy
        failed = str(uuid.uuid4())
        with self.assertRaises(ValueError):
            self.repo.document_uploads.receive(self.document['id'], failed, 'quota.txt', 1, self.document['revision'], io.BytesIO(b''), self.short)
        template = self.repo.document_uploads.load(failed)
        for size in [100 * 1048576] * 10 + [24 * 1048576]:
            key = str(uuid.uuid4()); value = copy.deepcopy(template)
            value.update(operation_id=key, size=size, removed=False, partial=None, stream_identity=None)
            folder = self.repo.document_uploads.folder(key); folder.mkdir()
            atomic_write_json(folder / 'operation.json', value)
        with self.assertRaisesRegex(ValueError, '预算'):
            self.upload(data=b'x')
        self.repo.document_uploads.maintain(self.short, cleanup=True)
        self.upload(data=b'x')

    def test_hundred_mib_web_stream_has_bounded_memory_and_exact_real_bytes(self):
        import hashlib
        import tracemalloc
        class Source:
            def __init__(self): self.remaining = 100 * 1048576
            def read(self, size):
                self.remaining -= size
                return b'x' * size
        key = str(uuid.uuid4())
        tracemalloc.start()
        try:
            result = self.repo.document_uploads.receive(self.document['id'], key, 'large.bin', 100 * 1048576, self.document['revision'], Source(), self.short)
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 8 * 1048576)
        path = self.repo.attachment_path(self.document['id'], 'large.bin')
        self.assertEqual(path.stat().st_size, 100 * 1048576)
        checksum = hashlib.sha256()
        with path.open('rb') as source:
            while chunk := source.read(65536): checksum.update(chunk)
        self.assertEqual(checksum.hexdigest(), result['receipt']['attachment']['sha256'])
        print(f'Document web 100MiB peak Python bytes={peak}')

    def test_unsupported_platform_or_target_rejects_before_receiving_any_bytes(self):
        from unittest.mock import patch
        from workbench.agent_security import AgentError
        class NeverRead:
            def read(self, size): raise AssertionError('unsupported target must not read stream')
        for supported in (False, True):
            with self.subTest(supported=supported), patch('workbench.document_uploads.SUPPORTED', supported):
                with patch('workbench.document_uploads.LocalFileHandle.__enter__', side_effect=AgentError('unsupported_file', 'synthetic volume', 403)):
                    with self.assertRaises(AgentError) as caught:
                        self.repo.document_uploads.receive(self.document['id'], str(uuid.uuid4()), 'large.bin', 104857600, self.document['revision'], NeverRead(), self.short)
                    self.assertEqual(caught.exception.status, 503)
                    self.assertFalse(self.repo.document_uploads.directory.exists())

    def test_failed_part_replaced_with_same_bytes_is_not_deleted_or_released(self):
        from workbench.document_uploads import UploadRecoveryError
        key = str(uuid.uuid4())
        with self.assertRaises(ValueError):
            self.repo.document_uploads.receive(self.document['id'], key, 'failed.txt', 10, self.document['revision'], io.BytesIO(b'part'), self.short)
        part = self.repo.document_uploads.folder(key) / 'binary.part'
        original = Path(self.temp.name) / 'original-part.bin'
        self.assertTrue(original.resolve().is_relative_to(Path(self.temp.name).resolve()))
        part.rename(original); part.write_bytes(b'part')
        with self.assertRaises(UploadRecoveryError):
            self.repo.document_uploads.maintain(self.short, cleanup=True)
        self.assertTrue(part.exists())
        self.assertFalse(self.repo.document_uploads.load(key)['removed'])

    def test_hardlinked_attachment_and_unknown_inflight_are_not_treated_as_safe(self):
        import os
        _key, result = self.upload(name='binary.txt')
        binary = self.repo.attachment_path(self.document['id'], 'binary.txt')
        alias = Path(self.temp.name) / 'synthetic-alias.txt'
        os.link(binary, alias)
        self.assertIsNone(self.repo.attachment_path(self.document['id'], 'binary.txt'))
        with self.assertRaises(ValueError): self.repo.export_documents_zip([self.document['id']])
        self.assertTrue(self.repo.orphan_asset_report()['warnings'])
        alias.unlink()
        manifest = self.repo.root / '.agent' / 'operations' / str(uuid.uuid4()) / 'manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'schema_version':99, 'kind':'future', 'binary_relative':'assets/files/binary.txt'}), encoding='utf-8')
        self.assertTrue(self.repo.orphan_asset_report()['warnings'])
        self.assertEqual(self.repo.orphan_assets(), [])

    def test_literal_percent_metadata_and_url_decoding_resolve_distinct_bytes(self):
        import zipfile
        from urllib.parse import unquote
        from workbench.document_attachments import attachment_items, local_links, safe_local_path
        from workbench.markdown_io import load_markdown
        expected = {}
        for index, name in enumerate(('%3A.txt', '%253A.txt', '%2F.txt', '%25.txt', '# 中文 %.txt')):
            data = f'file-{index}'.encode(); expected[name] = data
            self.document = self.repo.get_document(self.document['id'])[0]
            self.upload(data=data, name=name)
            self.assertEqual(self.repo.attachment_path(self.document['id'], name).read_bytes(), data)
        saved, path = self.repo.get_document(self.document['id'])
        self.assertIn('%253A', saved['body'])
        for _match, source in local_links(saved['body']):
            actual = safe_local_path(path.parent, source, (self.repo.global_assets_dir / 'files',), required=True)
            self.assertEqual(actual.read_bytes(), expected[actual.name])
        self.assertEqual(self.repo.orphan_asset_report()['warnings'], [])
        self.assertEqual(self.repo.cleanup_orphan_assets()['removed'], 0)
        with tempfile.TemporaryDirectory() as extracted:
            with zipfile.ZipFile(io.BytesIO(self.repo.export_documents_zip([saved['id']]))) as archive:
                archive.extractall(extracted)
            md = next(Path(extracted).glob('*.md')); meta, body = load_markdown(md)
            for item in attachment_items(meta['attachments']):
                self.assertEqual((md.parent / item['path']).read_bytes(), expected[item['name']])
            for _match, source in local_links(body):
                actual = md.parent / unquote(source)
                self.assertIn(actual.read_bytes(), expected.values())
        with self.assertRaises(ValueError):
            safe_local_path(path.parent, '../assets/files/%3A.txt', (self.repo.global_assets_dir / 'files',), required=True)
        latest = self.repo.get_document(saved['id'])[0]
        self.repo.update_document(saved['id'], {'body':latest['body'] + '\nchanged'})
        history = self.repo.list_document_history(saved['id'])[0]['version']
        latest = self.repo.get_document(saved['id'])[0]
        restored = self.repo.restore_document_history(saved['id'], history, latest['revision'])
        self.assertEqual(len(restored['attachments']), len(expected))
        self.assertEqual(self.repo.attachment_path(saved['id'], '%3A.txt').read_bytes(), expected['%3A.txt'])

    def test_external_document_image_url_is_decoded_once_with_both_names_present(self):
        directory = self.repo.documents_dir / 'outside'; directory.mkdir()
        literal = directory / '%3A.png'; encoded = directory / '%253A.png'
        literal.write_bytes(b'intended bytes'); encoded.write_bytes(b'other bytes')
        self.assertEqual(self.repo.markdown_image_path(self.document['id'], './outside/%253A.png').read_bytes(), b'intended bytes')
        self.assertEqual(self.repo.markdown_image_path(self.document['id'], './outside/%25253A.png').read_bytes(), b'other bytes')
        with self.assertRaises(ValueError):
            self.repo.markdown_image_path(self.document['id'], './outside/%3A.png')

    def test_retired_source_resurrection_is_unknown_and_migration_requires_failed_retirement(self):
        from workbench.document_uploads import UploadRecoveryError
        from workbench.paths import relocate_repository
        key, completed = self.upload()
        self.document = self.repo.get_document(self.document['id'])[0]
        failed = str(uuid.uuid4())
        with self.assertRaises(ValueError):
            self.repo.document_uploads.receive(self.document['id'], failed, 'partial.txt', 10, self.document['revision'], io.BytesIO(b'part'), self.short)
        target = Path(self.temp.name) / 'migrated'
        location = Path(self.temp.name) / 'location.json'
        with self.assertRaises(FileExistsError):
            relocate_repository(self.repo, str(target), True, location)
        self.assertFalse(target.exists())
        self.repo.document_uploads.maintain(self.short, cleanup=True)
        copied = relocate_repository(self.repo, str(target), True, location)
        self.assertEqual(copied.document_uploads.query(self.document['id'], key, lambda action:action())['receipt'], completed['receipt'])
        self.assertEqual(copied.attachment_path(self.document['id'], completed['receipt']['attachment']['name']).read_bytes(), b'file bytes')
        part = self.repo.document_uploads.folder(failed) / 'binary.part'
        part.write_bytes(b'unknown replacement')
        with self.assertRaises(UploadRecoveryError):
            self.repo.document_uploads.maintain(self.short, cleanup=True)
        self.assertEqual(part.read_bytes(), b'unknown replacement')
        self.assertTrue(self.repo.orphan_asset_report()['warnings'])

    def test_legacy_dictionary_attachment_with_boolean_fields_roundtrips_as_json_string(self):
        from workbench.markdown_io import load_markdown, dump_markdown
        from workbench.document_attachments import attachment_items
        path = Path(self.document['file_path']); meta, body = load_markdown(path)
        legacy = {'name':'legacy.bin', 'path':'../assets/files/legacy.bin', 'size':3, 'mime':'application/octet-stream', 'category':'分类', 'custom_flag':True, 'note':'  原说明\n尾部  '}
        target = self.repo.global_assets_dir / 'files' / 'legacy.bin'
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(b'old')
        meta['attachments'] = [legacy]
        path.write_text(dump_markdown(meta, body), encoding='utf-8')
        self.document = self.repo.get_document(self.document['id'])[0]
        self.upload()
        saved = self.repo.get_document(self.document['id'])[0]
        self.assertEqual(attachment_items(saved['attachments'])[0], legacy)
        self.assertEqual(self.repo.attachment_path(saved['id'], 'legacy.bin').read_bytes(), b'old')
        self.assertTrue(path.read_text(encoding='utf-8').split('attachments:\n', 1)[1].startswith('  - "'))
        old = self.repo.list_document_history(saved['id'])[0]['version']
        restored = self.repo.restore_document_history(saved['id'], old, saved['revision'])
        self.assertEqual(attachment_items(restored['attachments']), [legacy])


class DocumentUploadHTTPTests(unittest.TestCase):
    def setUp(self):
        import threading
        from server import WorkbenchHandler, WorkbenchHTTPServer
        DocumentAttachmentTests.setUp(self)
        class Handler(WorkbenchHandler):
            def log_message(self, *_args): pass
        Handler.repository = self.repo
        self.server = WorkbenchHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); self.port = self.server.server_address[1]
        def stop():
            self.server.shutdown(); self.server.server_close(); self.thread.join(5)
        self.addCleanup(stop)

    def request(self, path, method='GET', data=None, headers=None):
        import http.client
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            connection.request(method, path, body=data, headers=headers or {})
            response = connection.getresponse(); body = response.read()
            return response.status, dict(response.getheaders()), json.loads(body) if response.getheader('Content-Type', '').startswith('application/json') else body
        finally: connection.close()

    def route(self, key):
        return f'/api/documents/{self.document["id"]}/attachments/uploads/{key}'

    def test_upload_replay_download_sandbox_and_static_private_boundary(self):
        from urllib.parse import quote
        key = str(uuid.uuid4())
        route = self.route(key) + '?name=unsafe.html&expected_revision=' + self.document['revision']
        code, headers, result = self.request(route, 'POST', b'<script>bad()</script>')
        self.assertEqual(code, 201)
        other = b'different same length!'
        self.assertEqual(len(other), len(b'<script>bad()</script>'))
        code, headers, replay = self.request(route, 'POST', other)
        self.assertEqual(code, 201)
        self.assertEqual(replay, result)  # Existing ID returns ORIGINAL result; new bytes were not accepted.
        code, headers, body = self.request(f'/api/attachments/{self.document["id"]}/unsafe.html')
        self.assertEqual(body, b'<script>bad()</script>')
        self.assertEqual(headers['Content-Type'], 'application/octet-stream')
        self.assertTrue(headers['Content-Disposition'].startswith('attachment;'))
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(headers['Content-Security-Policy'], 'sandbox')
        private = '/.workbench-document-uploads/' + key + '/before.md'
        self.assertEqual(self.request(private)[0], 404)
        with __import__('zipfile').ZipFile(io.BytesIO(self.repo.export_zip())) as archive:
            self.assertFalse(any('.workbench-document-uploads' in n for n in archive.namelist()))

    def test_slow_stream_does_not_lock_document_edit_and_final_revision_rejects(self):
        import http.client
        import time
        key = str(uuid.uuid4()); connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            connection.putrequest('POST', self.route(key) + '?name=slow.txt&expected_revision=' + self.document['revision'])
            connection.putheader('Content-Length', '10'); connection.endheaders(); connection.send(b'a')
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if self.repo.document_uploads.report()['items']: break
                time.sleep(0.01)
            start = time.monotonic()
            code, _, saved = self.request(f'/api/documents/{self.document["id"]}', 'PATCH', json.dumps({'body':'上传期间外部修改', 'expected_revision':self.document['revision']}).encode(), {'Content-Type':'application/json'})
            self.assertEqual(code, 200)
            self.assertLess(time.monotonic() - start, 2)
            connection.send(b'b' * 9)
            response = connection.getresponse(); response.read(); self.assertEqual(response.status, 409)
            self.assertEqual(self.request(self.route(key))[2]['state'], 'failed')
            self.assertEqual(self.repo.get_document(self.document['id'])[0]['body'], '上传期间外部修改')
            self.assertFalse(self.repo.get_document(self.document['id'])[0].get('attachments'))
        finally: connection.close()

    def test_missing_query_is_readonly_and_full_catalog_can_recover_without_browser_storage(self):
        key = str(uuid.uuid4())
        self.assertEqual(self.request(self.route(key))[0], 404)
        self.assertFalse(self.repo.document_uploads.folder(key).exists())
        def crash(stage):
            if stage == 'binary': raise OSError('synthetic response loss')
        from unittest.mock import patch
        with patch.object(self.repo.document_uploads, 'checkpoint', crash):
            code, _, _body = self.request(self.route(key) + '?name=ready.txt&expected_revision=' + self.document['revision'], 'POST', b'bytes')
        self.assertEqual(code, 503)
        code, _, report = self.request('/api/document-uploads')
        self.assertEqual(report['items'][0]['operation_id'], key)
        self.assertEqual(self.request('/api/document-uploads/recover', 'POST', b'{}', {'Content-Type':'application/json'})[0], 200)
        self.assertEqual(self.request(self.route(key))[2]['state'], 'completed')

    def test_raw_ambiguous_lengths_and_replayed_body_cannot_become_another_request(self):
        import socket
        key = str(uuid.uuid4()); route = self.route(key) + '?name=pipeline.txt&expected_revision=' + self.document['revision']
        def raw(headers, body):
            with socket.create_connection(('127.0.0.1', self.port), timeout=5) as connection:
                connection.sendall((f'POST {route} HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n' + headers + '\r\n').encode() + body)
                data = b''
                while chunk := connection.recv(65536): data += chunk
                return data
        self.assertIn(b'400', raw('Content-Length: 1\r\nContent-Length: 1\r\n', b'x').split(b'\r\n', 1)[0])
        self.assertIn(b'400', raw('Transfer-Encoding: chunked\r\nContent-Length: 1\r\n', b'x').split(b'\r\n', 1)[0])
        self.assertFalse(self.repo.document_uploads.directory.exists())
        self.assertEqual(self.request(route, 'POST', b'original')[0], 201)
        before = len(self.repo.list_projects())
        injected = json.dumps({'name':'must never be parsed'}).encode()
        pipeline = b'changed!' + f'POST /api/projects HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\nContent-Type: application/json\r\nContent-Length: {len(injected)}\r\n\r\n'.encode() + injected
        response = raw('Content-Length: 8\r\n', pipeline)
        self.assertEqual(response.count(b'HTTP/1.'), 1)
        self.assertEqual(len(self.repo.list_projects()), before)
        self.assertEqual(self.repo.attachment_path(self.document['id'], 'pipeline.txt').read_bytes(), b'original')

    def test_protocol_decodes_percent_filename_once_and_rejects_real_ads_or_question(self):
        from urllib.parse import quote
        key = str(uuid.uuid4()); name = '%3A%2F%25 #中文.txt'
        route = self.route(key) + '?name=' + quote(name, safe='') + '&expected_revision=' + self.document['revision']
        self.assertEqual(self.request(route, 'POST', b'percent bytes')[0], 201)
        self.assertEqual(self.request(f'/api/attachments/{self.document["id"]}/' + quote(name, safe=''))[2], b'percent bytes')
        self.assertEqual(self.request(f'/api/attachments/{self.document["id"]}/' + quote(name, safe='%'))[0], 404)
        current = self.repo.get_document(self.document['id'])[0]
        before = len(self.repo.document_uploads.report()['items'])
        for invalid in ('bad:stream.txt', 'what?.txt', 'C:/synthetic.txt'):
            route = self.route(str(uuid.uuid4())) + '?name=' + quote(invalid, safe='') + '&expected_revision=' + current['revision']
            self.assertEqual(self.request(route, 'POST', b'x')[0], 400)
        self.assertEqual(len(self.repo.document_uploads.report()['items']), before)

    def test_legacy_record_and_project_audio_video_keep_inline_mime(self):
        import mimetypes
        from urllib.parse import quote
        project = self.repo.create_project({'name':'媒体兼容'})
        record = self.repo.create_record({'type':'issue', 'title':'媒体', 'project_id':project['id']})
        for name in ('audio.wav', 'video.webm', 'passive.ico', 'active.svg', 'active.html'):
            data = ('synthetic MIME contract ' + name).encode()
            item = self.repo.add_record_attachment_stream(record['id'], name, io.BytesIO(data), len(data))
            asset = self.repo.add_project_asset_stream(project['id'], name, io.BytesIO(data), len(data))
            for path in (f'/api/attachments/{record["id"]}/{quote(item["name"])}', f'/api/project-assets/{quote(project["id"])}/{asset["id"]}'):
                code, headers, body = self.request(path)
                self.assertEqual(code, 200)
                self.assertEqual(body, data)
                active = name.startswith('active.')
                self.assertEqual(headers['Content-Type'], 'application/octet-stream' if active else mimetypes.guess_type(name)[0])
                self.assertTrue(headers['Content-Disposition'].startswith('attachment;' if active else 'inline;'))
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                if active: self.assertEqual(headers['Content-Security-Policy'], 'sandbox')
                else: self.assertNotIn('Content-Security-Policy', headers)  # Passive native media keeps its original origin.
