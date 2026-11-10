"""AG-136 real process exits, disk evidence, and ordinary-entry protection."""

import copy
import hashlib
import json
import subprocess
import sys
import unittest
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import test_agent_deletions as fixtures
from server import Repository
from workbench.agent_security import AgentError, read_json
from workbench.agent_service import AgentService
from workbench.agent_runtime import AgentRuntime
from workbench.agent_proposal_management import ProposalManagement
from workbench.persistence import atomic_write_json


class DeleteRecoveryTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.DeleteProposalTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        return fixture

    def reload(self, fixture):
        fixture.repo = Repository(fixture.repo.root)
        fixture.service = AgentService(fixture.repo, fixture.security)
        fixture.repo.agent_service = fixture.service
        fixture.runtime = AgentRuntime(fixture.repo, base=fixture.base / 'credentials')
        fixture.repo.agent_runtime = fixture.runtime
        fixture.store = fixture.service.store
        fixture.store.recover()
        fixture.proposal_management = ProposalManagement(fixture.runtime)

    def test_completed_directory_copy_with_matching_private_config_restores_relative_source(self):
        fixture = self.fixture()
        item, path = fixture.create_target('concept_map')
        raw = path.read_bytes()
        preview = fixture.deletion_preview('concept_map', item, path)
        receipt = fixture.proposal_management.approve(preview['proposal_id'], fixture.local_payload(preview))['receipt']
        migrated = fixture.base / 'completed-copy'
        shutil.copytree(fixture.repo.root, migrated)
        from workbench.agent_security import AgentSecurity
        repository = Repository(migrated)
        security = AgentSecurity(migrated, fixture.base / 'credentials')
        service = AgentService(repository, security)
        repository.agent_service = service
        service.store.recover()
        self.assertFalse(service.store.blocked)
        restored = repository.restore_trash(receipt['trash_token'])
        self.assertEqual(Path(restored['restored_path']).read_bytes(), raw)
        self.assertTrue(Path(restored['restored_path']).resolve().is_relative_to(migrated.resolve()))
        self.assertFalse(path.exists())
        client = security.clients()[fixture.client['client_id']]
        self.assertEqual(service.commit_proposal(client, preview['proposal_id'], fixture.confirmation(preview)), receipt)
        self.assertEqual(repository.get_concept_map(item['id'])[1].read_bytes(), raw)
        self.assertNotEqual(repository.create_concept_map({'title':'保持游标'})['id'], item['id'])

    def test_terminal_content_cleanup_keeps_original_receipt_and_restore_proof(self):
        fixture = self.fixture()
        item, path = fixture.create_target('issue')
        raw = path.read_bytes()
        preview = fixture.deletion_preview('issue', item, path)
        receipt = fixture.proposal_management.approve(preview['proposal_id'], fixture.local_payload(preview))['receipt']
        proposal = fixture.store._load(preview['proposal_id'], expire=False)
        proposal['finished_at'] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        fixture.store._save(proposal)
        fixture.store.cleanup()
        directory = fixture.store.operations / f"{preview['proposal_id']}-1"
        self.assertFalse((directory / 'before.md').exists())
        self.assertFalse((directory / 'index-before.json').exists())
        self.reload(fixture)
        self.assertFalse(fixture.store.blocked)
        restored = fixture.repo.restore_trash(receipt['trash_token'])
        self.assertEqual(Path(restored['restored_path']).read_bytes(), raw)
        self.assertEqual(fixture.service.commit_proposal(fixture.client, preview['proposal_id'], fixture.confirmation(preview)), receipt)

    def test_real_exit_five_types_at_all_twelve_durable_boundaries(self):
        script = '''import os,sys,hashlib
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService
from workbench.agent_runtime import AgentRuntime
from workbench.agent_proposal_management import ProposalManagement
r=Repository(Path(sys.argv[1]));s=AgentSecurity(r.root,Path(sys.argv[2]));v=AgentService(r,s)
r.agent_service=v;r.agent_runtime=AgentRuntime(r,base=Path(sys.argv[2]));c=s.clients()[sys.argv[3]]
kind,key,stage=sys.argv[4:7]
item,path=(r.get_concept_map(key) if kind=='concept_map' else r.get_document(key) if kind=='document' else r.get_record(key))
p=v.prepare_proposal(c,{'request_id':'real-delete-'+stage,'kind':kind,'operation':'delete','target_id':key,'base_revision':hashlib.sha256(path.read_bytes()).hexdigest()})
preview=v.preview_proposal(c,p['proposal_id']);m=ProposalManagement(r.agent_runtime);review=m.preview(p['proposal_id'])
v.store.checkpoint=lambda current:os._exit(79) if current==stage else None
m.approve(p['proposal_id'],{'workspace_id':s.workspace_id,'version':1,'preview_digest':preview['preview_digest'],'preview_ticket':review['preview_ticket'],'request_id':'real-web-'+stage})
'''
        stages = ('snapshots', 'manifest', 'committing', 'delete_move_applying', 'trash_moved', 'delete_move_logged',
                  'delete_index', 'delete_index_logged', 'delete_cache', 'delete_cache_logged', 'receipt', 'proposal')
        for kind in ('issue', 'todo', 'info', 'document', 'concept_map'):
            for stage in stages:
                with self.subTest(kind=kind, stage=stage):
                    fixture = fixtures.DeleteProposalTests()
                    fixture.setUp()
                    try:
                        other = fixture.repo.create_record({'type':'issue', 'project_id':fixture.project['id'], 'title':'普通回收项'})
                        old_trash = fixture.repo.delete_record(other['id'])
                        item, path = fixture.create_target(kind)
                        raw = path.read_bytes()
                        result = subprocess.run([sys.executable, '-c', script, str(fixture.repo.root), str(fixture.base / 'credentials'),
                                                 fixture.client['client_id'], kind, item['id'], stage], cwd=Path(__file__).parent,
                                                capture_output=True, timeout=30)
                        self.assertEqual(result.returncode, 79, result.stderr)
                        self.reload(fixture)  # Also proves disabled-startup recovery precedes cleanup.
                        proposal = fixture.store._load(next(fixture.store.proposals.glob('*.json')).stem, expire=False)
                        if stage == 'snapshots':
                            self.assertEqual(proposal['state'], 'previewed')
                            self.assertTrue(path.exists())
                            self.assertEqual(fixture.proposal_management.action('real-web-' + stage)['state'], 'not_applied')
                            self.assertEqual(len(fixture.repo.list_trash()), 1)
                        elif stage == 'delete_move_applying':
                            self.assertTrue(fixture.store.blocked)
                            self.assertTrue(path.exists())
                            self.assertTrue(fixture.repo.list_trash()[0]['protected'])
                            for operation in (lambda:fixture.repo.restore_trash(old_trash['token']),
                                              lambda:fixture.repo.purge_trash(old_trash['token']),
                                              lambda:fixture.repo.batch_restore_trash({'tokens':[old_trash['token']]}),
                                              lambda:fixture.repo.batch_purge_trash({'tokens':[old_trash['token']]}),
                                              lambda:fixture.repo.cleanup_trash(-1),
                                              lambda:fixture.repo.delete_project(fixture.project['id']),
                                              lambda:fixture.repo.create_document({'title':'不能绕过保护'}),
                                              lambda:fixture.repo.cleanup_orphan_assets()):
                                with self.assertRaises(AgentError):
                                    operation()
                            fixture.store.abandon(f"{proposal['proposal_id']}-1")
                            self.assertEqual(path.read_bytes(), raw)
                            self.assertFalse(fixture.store.blocked)
                            self.assertEqual(fixture.proposal_management.action('real-web-' + stage)['state'], 'abandoned')
                        else:
                            self.assertEqual(proposal['state'], 'committed')
                            self.assertFalse(fixture.store.blocked)
                            receipt = proposal['receipt']
                            self.assertFalse(path.exists())
                            self.assertEqual((fixture.repo.trash_dir / receipt['trash_token']).read_bytes(), raw)
                            fixture.repo.restore_trash(receipt['trash_token'])
                            replay = fixture.service.commit_proposal(fixture.client, proposal['proposal_id'],
                                      {'version':1, 'preview_digest':proposal['preview_digest'], 'confirmation':{'mode':'agent_attested', 'user_confirmed':True}})
                            self.assertEqual(replay, receipt)
                            self.assertEqual(path.read_bytes(), raw)
                    finally:
                        fixture.tearDown()

    def test_moved_original_finishes_without_touching_recreated_source_or_current_permission(self):
        fixture = self.fixture()
        item, path = fixture.create_target('document')
        preview = fixture.deletion_preview('document', item, path)
        raw = path.read_bytes()
        payload = fixture.local_payload(preview)
        def fail(stage):
            if stage == 'trash_moved':
                raise OSError('synthetic move-before-index failure')
        with patch.object(fixture.store, 'checkpoint', side_effect=fail), self.assertRaises(AgentError):
            fixture.proposal_management.approve(preview['proposal_id'], payload)
        self.assertFalse(path.exists())
        path.write_bytes(raw + b'\nnew independent input')
        current = fixture.security.clients()[fixture.client['client_id']]
        fixture.security.manager().run('delete_grants_revoke', {}, current['client_id'], fixtures.client_version(current), 'revoke-after-move')
        self.reload(fixture)
        self.assertFalse(fixture.store.blocked)
        proposal = fixture.store._load(preview['proposal_id'])
        self.assertEqual(proposal['state'], 'committed')
        self.assertEqual(path.read_bytes(), raw + b'\nnew independent input')
        self.assertEqual((fixture.repo.trash_dir / proposal['receipt']['trash_token']).read_bytes(), raw)

    def test_index_foreign_member_is_preserved_and_abandon_does_not_unprotect_its_residue(self):
        fixture = self.fixture()
        item, path = fixture.create_target('issue')
        preview = fixture.deletion_preview('issue', item, path)
        payload = fixture.local_payload(preview)
        with patch.object(fixture.store, 'checkpoint', side_effect=lambda stage:(_ for _ in ()).throw(OSError('stop')) if stage == 'trash_moved' else None), self.assertRaises(AgentError):
            fixture.proposal_management.approve(preview['proposal_id'], payload)
        index = fixture.repo._trash_index()
        foreign = {'token':preview['trash_token'], 'id':'FOREIGN-1', 'kind':'record', 'title':'foreign index', 'deleted_at':'2000-01-01T00:00:00+00:00',
                   'original_path':str(path), 'trash_path':str(fixture.repo.trash_dir / preview['trash_token'])}
        index[preview['trash_token']] = foreign
        fixture.repo._write_trash_index(index)
        fixture.store.recover()
        self.assertTrue(fixture.store.blocked)
        self.assertEqual(fixture.repo._trash_index()[preview['trash_token']], foreign)
        fixture.store.abandon(f"{preview['proposal_id']}-1")
        self.assertFalse(fixture.store.blocked)
        self.assertTrue(fixture.repo.list_trash()[0]['protected'])
        for operation in (lambda:fixture.repo.restore_trash(preview['trash_token']), lambda:fixture.repo.purge_trash(preview['trash_token'])):
            with self.assertRaises(AgentError):
                operation()
        fixture.repo.cleanup_trash(-1)
        self.assertTrue((fixture.repo.trash_dir / preview['trash_token']).exists())
        self.assertEqual(fixture.repo.orphan_asset_report()['orphans'], [])
        self.assertTrue(fixture.repo.orphan_asset_report()['warnings'])

    def test_unknown_or_cross_field_execution_changes_preflight_zero_json_writes(self):
        fixture = self.fixture()
        item, path = fixture.create_target('todo')
        preview = fixture.deletion_preview('todo', item, path)
        payload = fixture.local_payload(preview)
        with patch.object(fixture.store, 'checkpoint', side_effect=lambda stage:(_ for _ in ()).throw(OSError('stop')) if stage == 'manifest' else None), self.assertRaises(AgentError):
            fixture.proposal_management.approve(preview['proposal_id'], payload)
        manifest_path = next(fixture.store.operations.glob('*/manifest.json'))
        original = read_json(manifest_path)
        for mutate in (lambda value:value.update(execution_schema_version=99),
                       lambda value:value.update(trash_token='record-agent-' + str(fixtures.uuid.uuid4()) + '-1'),
                       lambda value:value.update(relative_path='documents/another.md'),
                       lambda value:value.update(step_states=['completed'] * 4),
                       lambda value:value['receipt'].update(item_id='TODO-9999'),
                       lambda value:value['execution_plan'].update(handler='trash_delete@2'),
                       lambda value:value.update(deleted_at='not-time')):
            changed = copy.deepcopy(original)
            mutate(changed)
            atomic_write_json(manifest_path, changed)
            before = fixture.evidence()
            self.assertTrue(fixture.store.recover()['blocked'])
            self.assertEqual(fixture.evidence(), before)
            with self.assertRaises(AgentError):
                fixture.store.abandon(original['operation_id'])
            self.assertEqual(fixture.evidence(), before)
        atomic_write_json(manifest_path, original)
        fixture.store.recover()
        self.assertFalse(fixture.store.blocked)


if __name__ == '__main__':
    unittest.main()
