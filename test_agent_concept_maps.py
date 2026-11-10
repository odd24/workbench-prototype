"""AG-135 strict graph contracts; fixtures never use a real workbench directory."""

import copy
import json
import tempfile
import unittest
import uuid
import subprocess
import sys
import os
import io
import zipfile
import hashlib
from pathlib import Path
from unittest.mock import patch

from server import Repository
from test_agent_support import AgentFixture
from workbench.agent_concept_maps import GRAPH_BYTES, json_bytes, validate_graph
from workbench.agent_security import AgentError
from workbench.concept_maps import ConceptMapRepository
from workbench.agent_concept_authorization import client_graph_grants, graph_allows, graph_confirmation_mode, normalize_graph_grants
from workbench.agent_security import allows, client_kinds
from workbench.agent_management import client_version
from workbench.agent_concept_authorization import grant_dependencies
from workbench.agent_file_handles import SUPPORTED
import test_agent_runtime as runtime_tests
import test_mcp_stdio as mcp_tests


def graph():
    return ConceptMapRepository.normalize({'title': '完整候选', 'nodes': [
        {'id': 'a', 'text': '甲'}, {'id': 'b', 'text': '乙'}
    ], 'edges': [{'id': 'e', 'from': 'a', 'to': 'b', 'label': '关联'}]})


def graph_grants(resource, mode='agent_attested'):
    return {'schema_version': 1, 'grants': [
        {'capability': 'concept_maps.read', 'operations': ['read'], 'resources': [resource], 'minimum_confirmation_mode': 'agent_attested'},
        {'capability': 'concept_maps.write', 'operations': ['update'] if resource['type'] == 'concept_map' else ['create', 'update'], 'resources': [resource], 'minimum_confirmation_mode': mode},
    ]}


def graph_client(grants):
    return {'authorization_schema_version': 5, 'enabled': True, 'kinds': ['concept_map'], 'scopes': ['read', 'propose', 'commit'],
            'project_ids': ['*'], 'categories': ['*'], 'concept_map_grants': normalize_graph_grants(grants)}


class GraphGrantTests(unittest.TestCase):
    def test_dormant_config_and_legacy_wildcards_never_activate(self):
        client = {'authorization_schema_version': 3, 'enabled': True, 'kinds': ['issue', 'document'], 'scopes': ['read', 'propose', 'commit'],
                  'project_ids': ['*'], 'categories': ['*'], 'capability_grants': graph_grants({'type': 'project', 'id': 'p'}), 'capability_grant_state': 'dormant'}
        target = {'type': 'concept_map', 'id': 'CMAP-0001', 'project_id': 'p', 'category': '分类'}
        self.assertFalse(allows(client, target))
        self.assertFalse(graph_allows(client, target, 'update'))
        self.assertEqual(client_graph_grants(client), {'schema_version': 1, 'grants': []})
        client['concept_map_grants'] = graph_grants({'type': 'project', 'id': 'p'})
        with self.assertRaises(AgentError):
            client_kinds(client)

    def test_project_category_named_map_and_destination_are_distinct(self):
        item = {'type': 'concept_map', 'id': 'CMAP-0001', 'project_id': 'p', 'category': '分类'}
        project = graph_client(graph_grants({'type': 'project', 'id': 'p'}))
        category = graph_client(graph_grants({'type': 'concept_map_category', 'name': '分类'}))
        named = graph_client(graph_grants({'type': 'concept_map', 'id': 'CMAP-0001'}))
        self.assertTrue(allows(project, item))
        self.assertFalse(allows(category, item))
        self.assertTrue(allows(category, {**item, 'project_id': None}))
        self.assertFalse(allows(project, {**item, 'project_id': None}))
        self.assertTrue(allows(named, item))
        self.assertFalse(allows(named, {**item, 'id': 'CMAP-0002'}))
        self.assertTrue(graph_allows(named, item, 'update'))
        self.assertFalse(graph_allows(named, {**item, 'project_id': 'other'}, 'update', destination=True))
        self.assertFalse(graph_allows(project, {**item, 'type': 'issue'}))
        self.assertEqual(client_kinds(project), ['concept_map'])

    def test_scope_read_write_and_confirmation_intersection(self):
        item = {'type': 'concept_map', 'id': 'CMAP-0001', 'project_id': 'p', 'category': '分类'}
        client = graph_client(graph_grants({'type': 'project', 'id': 'p'}, 'local_web'))
        self.assertEqual(graph_confirmation_mode(client, item, 'update', 'agent_attested'), 'local_web')
        client['scopes'] = ['read']
        self.assertTrue(allows(client, item))
        self.assertFalse(graph_allows(client, item, 'update'))
        client['scopes'] = ['propose', 'commit']
        self.assertFalse(allows(client, item))
        client['scopes'] = ['read', 'propose', 'commit']
        client['concept_map_grants']['grants'] = [grant for grant in client['concept_map_grants']['grants'] if grant['capability'] == 'concept_maps.write']
        self.assertFalse(graph_allows(client, item, 'update'))
        with self.assertRaises(AgentError):
            graph_confirmation_mode(client, item, 'update', 'agent_attested')
        client = graph_client(graph_grants({'type': 'project', 'id': 'p'})); client['enabled'] = False
        self.assertFalse(allows(client, item))

    def test_explicit_graph_formats_do_not_change_old_declared_types(self):
        value = graph_grants({'type': 'concept_map', 'id': 'CMAP-0001'})
        value['grants'][1]['operations'] = ['create']
        with self.assertRaises(ValueError): normalize_graph_grants(value)
        with self.assertRaises(ValueError): normalize_graph_grants(graph_grants({'type':'concept_map', 'id':'CMAP-١'}))
        for version in (1, 2, 3, 4):
            with self.assertRaises(AgentError): client_kinds({'authorization_schema_version': version, 'kinds': ['concept_map']})
        with self.assertRaises(AgentError): client_kinds({'authorization_schema_version': 5, 'kinds': ['concept_map']})
        self.assertEqual(client_kinds({'authorization_schema_version': 4, 'kinds': ['info'], 'active_file_ids': []}), ['info'])


class GraphMCPTests(unittest.TestCase):
    setUp = mcp_tests.MCPBridgeTests.setUp
    tearDown = mcp_tests.MCPBridgeTests.tearDown
    start_bridge = mcp_tests.MCPBridgeTests.start_bridge
    tool = mcp_tests.MCPBridgeTests.tool

    def test_real_stdio_scoped_read_complete_graph_proposal_and_large_preview(self):
        repository, security = self.workbench.repository, self.workbench.security
        stored = repository.create_concept_map({'title': '原图', 'project_id': self.project['id']})
        self.start_bridge()
        self.assertEqual(len(self.rpc.call('tools/list')['tools']), 22)
        self.assertEqual(self.tool('list_concept_maps')['structuredContent']['items'], [])
        self.assertTrue(self.tool('get_concept_map', {'map_id':stored['id']})['isError'])
        current = security.clients()[self.info['client_id']]
        grants = graph_grants({'type':'project', 'id':self.project['id']})
        security.manager().run('concept_map_grants', {'grants':grants, 'approval_digest':'a' * 64, 'resource_dependencies':grant_dependencies(repository, grants)},
                               current['client_id'], client_version(current), 'stdio-graph-grant')
        listing = self.tool('list_concept_maps')['structuredContent']['items']
        self.assertEqual([item['id'] for item in listing], [stored['id']])
        read = self.tool('get_concept_map', {'map_id':stored['id']})
        self.assertFalse(read['isError'], read)
        self.assertEqual(read['structuredContent']['revision'], stored['revision'])
        self.assertEqual(read['structuredContent']['graph']['nodes'], stored['nodes'])
        with self.assertRaisesRegex(RuntimeError, '-32602'):
            self.tool('get_concept_map', {'map_id':'../../private'})
        value = graph(); value['project_id'] = self.project['id']
        spec = {'request_id':'stdio-concept', 'kind':'concept_map', 'operation':'create', 'content':{'graph':value}}
        proposal = self.tool('prepare_proposal', spec)
        self.assertFalse(proposal['isError'], proposal)
        proposal = proposal['structuredContent']
        preview = self.tool('preview_proposal', {'proposal_id':proposal['proposal_id']})
        self.assertFalse(preview['isError'], preview)
        preview = preview['structuredContent']
        self.assertEqual(preview['prepared_graph']['nodes'], value['nodes'])
        confirmation = {'mode':'agent_attested', 'user_confirmed':True, 'note':'synthetic current preview confirmed'}
        payload = {'proposal_id':proposal['proposal_id'], 'version':1, 'preview_digest':preview['preview_digest'], 'confirmation':confirmation}
        receipt = self.tool('commit_proposal', payload)
        self.assertFalse(receipt['isError'], receipt)
        self.assertEqual(self.tool('commit_proposal', payload)['structuredContent'], receipt['structuredContent'])
        self.assertEqual(repository.get_concept_map(proposal['target_id'])[0]['nodes'], value['nodes'])
        large = copy.deepcopy(value)
        large['nodes'] = [{**value['nodes'][0], 'id':f'n{i}', 'text':f'N{i}', 'note':'', 'x':(i % 25) * 180, 'y':(i // 25) * 100} for i in range(500)]
        large['edges'] = [{**value['edges'][0], 'id':f'e{i}', 'from':f'n{i % 500}', 'to':f'n{(i + 1) % 500}', 'label':''} for i in range(1000)]
        prepared = self.tool('prepare_proposal', {**spec, 'request_id':'stdio-large-graph', 'content':{'graph':large}})
        self.assertFalse(prepared['isError'], prepared)
        complete = self.tool('preview_proposal', {'proposal_id':prepared['structuredContent']['proposal_id']})
        self.assertFalse(complete['isError'], complete)
        self.assertEqual(len(complete['structuredContent']['prepared_graph']['nodes']), 500)
        self.assertEqual(len(complete['structuredContent']['prepared_graph']['edges']), 1000)
        self.assertLessEqual(len(json_bytes(complete)), 8 * 1024 * 1024)
        self.assertEqual(json.loads(complete['content'][0]['text']), complete['structuredContent'])
        for invalid in ({**value, 'viewport':{'x':True, 'y':0, 'zoom':1}}, {**value, 'nodes':[{'id':'incomplete'}]}, {**value, 'id':'CMAP-9999'}):
            with self.assertRaisesRegex(RuntimeError, '-32602'):
                self.tool('prepare_proposal', {**spec, 'request_id':uuid.uuid4().hex, 'content':{'graph':invalid}})


class GraphProposalTests(AgentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.repo.ensure_concept_map_category('未分类')
        GraphManagementTests.approve(self)
        self.client = self.security.clients()[self.client['client_id']]

    def graph_spec(self, **extra):
        value = graph()
        value['project_id'] = self.project['id']
        return {'request_id': uuid.uuid4().hex, 'kind': 'concept_map', 'operation': 'create', 'content': {'graph': value}, **extra}

    def test_true_exit_before_and_after_atomic_proposal_identity_save(self):
        script = '''import sys,os,json
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService
r=Repository(Path(sys.argv[1]));s=AgentSecurity(r.root,Path(sys.argv[2]));a=AgentService(r,s)
c=s.clients()[sys.argv[3]];spec=json.loads(Path(sys.argv[4]).read_text(encoding='utf-8'))
a.store.checkpoint=lambda stage:os._exit(75) if stage==sys.argv[5] else None
a.prepare_proposal(c,spec)
'''
        for stage in ('concept_map_id_claimed', 'concept_map_reserved'):
            fixture = AgentFixture(); fixture.setUp()
            try:
                fixture.repo.ensure_concept_map_category('未分类')
                GraphManagementTests.approve(self, fixture=fixture)
                client = fixture.security.clients()[fixture.client['client_id']]
                value = graph(); value['project_id'] = fixture.project['id']
                spec = {'request_id':'stable-identity-exit', 'kind':'concept_map', 'operation':'create', 'content':{'graph':value}}
                spec_path = fixture.base / 'synthetic-spec.json'; spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding='utf-8')
                result = subprocess.run([sys.executable, '-c', script, str(fixture.repo.root), str(fixture.base / 'credentials'), client['client_id'], str(spec_path), stage], cwd=Path(__file__).parent, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 75, result.stderr)
                from workbench.agent_service import AgentService
                repo = Repository(fixture.repo.root); service = AgentService(repo, fixture.security)
                retried = service.prepare_proposal(client, spec)
                self.assertEqual(retried['target_id'], 'CMAP-0002' if stage == 'concept_map_id_claimed' else 'CMAP-0001')
                self.assertEqual(service.prepare_proposal(client, spec)['proposal_id'], retried['proposal_id'])
                self.assertEqual(len(list(service.store.proposals.glob('*.json'))), 1)
                self.assertEqual(repo.list_concept_maps(), [])
            finally: fixture.tearDown()

    def test_real_exits_preserve_graph_identity_history_and_never_recreate_missing_create(self):
        script = '''import sys,os
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_service import AgentService
r=Repository(Path(sys.argv[1]));s=AgentSecurity(r.root,Path(sys.argv[2]));a=AgentService(r,s);a.store.recover()
c=s.clients()[sys.argv[3]];p=a.store._load(sys.argv[4],expire=False)
a.store.checkpoint=lambda stage:os._exit(74) if stage==sys.argv[5] else None
a.commit_proposal(c,p['proposal_id'],{'version':p['version'],'preview_digest':p['preview_digest'],'confirmation':{'mode':'agent_attested','user_confirmed':True,'note':'synthetic confirmed'}})
'''
        for operation in ('create', 'update'):
            for stage in ('snapshots', 'manifest', 'committing', 'applying', 'history', 'history_logged', 'target', 'target_logged', 'receipt', 'proposal'):
                with self.subTest(operation=operation, stage=stage):
                    fixture = AgentFixture(); fixture.setUp()
                    try:
                        fixture.repo.ensure_concept_map_category('未分类')
                        GraphManagementTests.approve(self, fixture=fixture)
                        client = fixture.security.clients()[fixture.client['client_id']]
                        value = graph(); value['project_id'] = fixture.project['id']
                        spec = {'request_id': uuid.uuid4().hex, 'kind': 'concept_map', 'operation': operation, 'content': {'graph': value}}
                        before = None
                        if operation == 'update':
                            old = fixture.repo.create_concept_map(value)
                            before = (fixture.repo.concept_maps_dir / f"{old['id']}.json").read_bytes()
                            spec.update(target_id=old['id'], base_revision=old['revision'])
                            value['title'] = '完整更新候选'
                        proposal = fixture.service.prepare_proposal(client, spec)
                        preview = fixture.service.preview_proposal(client, proposal['proposal_id'])
                        result = subprocess.run([sys.executable, '-c', script, str(fixture.repo.root), str(fixture.base / 'credentials'), client['client_id'], proposal['proposal_id'], stage],
                                                cwd=Path(__file__).parent, capture_output=True, timeout=20)
                        self.assertEqual(result.returncode, 74, result.stderr)
                        from workbench.agent_service import AgentService
                        repository = Repository(fixture.repo.root)
                        service = AgentService(repository, fixture.security)
                        recovered = service.store.recover()
                        if operation == 'create' and stage in ('applying', 'history', 'history_logged'):
                            self.assertTrue(recovered['blocked'])
                            self.assertEqual(repository.list_concept_maps(), [])
                            service.store.abandon(f"{proposal['proposal_id']}-1")
                            self.assertEqual(service.store._load(proposal['proposal_id'])['state'], 'cancelled')
                        else:
                            self.assertFalse(recovered['blocked'], recovered)
                            receipt = service.commit_proposal(client, proposal['proposal_id'], self.confirmation(preview))
                            stored, path = repository.get_concept_map(proposal['target_id'])
                            self.assertEqual(stored['revision'], receipt['revision'])
                            self.assertEqual(stored['title'], value['title'])
                            if before is not None:
                                manifest = json.loads((service.store.operations / f"{proposal['proposal_id']}-1" / 'manifest.json').read_text(encoding='utf-8'))
                                self.assertEqual((repository.history_dir / proposal['target_id'] / f"{manifest['history_version']}.json").read_bytes(), before)
                    finally:
                        fixture.tearDown()

    def test_create_reservation_preview_commit_receipt_revision_and_reopen(self):
        spec = self.graph_spec()
        proposal = self.service.prepare_proposal(self.client, spec)
        self.assertEqual(proposal['target_id'], 'CMAP-0001')
        self.assertEqual(self.repo.list_concept_maps(), [])
        self.assertEqual(self.service.prepare_proposal(self.client, spec)['proposal_id'], proposal['proposal_id'])
        self.assertEqual(json.loads((self.repo.config_dir / 'concept-map-ids.json').read_text(encoding='utf-8'))['high_water'], 1)
        preview = self.service.preview_proposal(self.client, proposal['proposal_id'])
        self.assertEqual(preview['prepared_graph']['nodes'], spec['content']['graph']['nodes'])
        self.assertEqual(preview['graph_diff']['nodes']['order_after'], ['a', 'b'])
        self.assertEqual(self.repo.list_concept_maps(), [])
        receipt = self.commit(preview)
        self.assertEqual(receipt['item_id'], proposal['target_id'])
        self.assertEqual(receipt, self.commit(preview))
        self.reload()
        current, path = self.repo.get_concept_map(receipt['item_id'])
        self.assertEqual(current['revision'], receipt['revision'])
        self.assertEqual(current['nodes'], spec['content']['graph']['nodes'])
        self.assertNotIn('服务端', current['created'])
        manifest = json.loads((self.store.operations / f"{proposal['proposal_id']}-1" / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['execution_schema_version'], 3)
        self.assertEqual(manifest['execution_plan']['handler'], 'concept_map@1')
        self.assertEqual(self.service.get_proposal(self.client, proposal['proposal_id'])['current_item']['changed_since_commit'], False)

    def test_revision_cancel_cleanup_and_web_allocation_keep_reserved_identity(self):
        from workbench.persistence import atomic_write_json
        from datetime import datetime, timedelta, timezone
        spec = self.graph_spec()
        proposal = self.service.prepare_proposal(self.client, spec)
        changed = copy.deepcopy(spec['content'])
        changed['graph']['title'] = '修订保留ID'
        revised = self.service.revise_proposal(self.client, proposal['proposal_id'], {'expected_version': 1, 'content': changed})
        self.assertEqual(revised['target_id'], proposal['target_id'])
        self.assertEqual(revised['identity'], proposal['identity'])
        canceled = self.service.cancel_proposal(self.client, proposal['proposal_id'], {'expected_version': 2})
        raw = self.store._load(proposal['proposal_id'], expire=False)
        raw['finished_at'] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        atomic_write_json(self.store.proposals / f"{proposal['proposal_id']}.json", raw)
        self.store.cleanup()
        cleaned = self.store._load(proposal['proposal_id'], expire=False)
        self.assertTrue(cleaned['content_cleaned'])
        self.assertEqual(cleaned['identity'], proposal['identity'])
        self.assertEqual(self.service.prepare_proposal(self.client, spec)['target_id'], proposal['target_id'])
        self.assertEqual(self.repo.create_concept_map({'title': '普通网页不会占预留图'})['id'], 'CMAP-0002')

    def test_update_preserves_raw_history_and_external_change_refuses_old_candidate(self):
        old = self.repo.create_concept_map(self.graph_spec()['content']['graph'])
        candidate = self.graph_spec(operation='update', target_id=old['id'], base_revision=old['revision'])
        candidate['content']['graph']['nodes'][0]['note'] = '完整保留多行\n空格  引号"'
        preview = self.prepare_preview(candidate)
        before = (self.repo.concept_maps_dir / f"{old['id']}.json").read_bytes()
        receipt = self.commit(preview)
        directory = self.store.operations / f"{preview['proposal_id']}-1"
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        history = self.repo.history_dir / old['id'] / f"{manifest['history_version']}.json"
        self.assertEqual(history.read_bytes(), before)
        updated, _ = self.repo.get_concept_map(old['id'])
        self.assertEqual(updated['nodes'][0]['note'], candidate['content']['graph']['nodes'][0]['note'])
        stale = self.prepare_preview(self.graph_spec(operation='update', target_id=old['id'], base_revision=updated['revision']))
        external = self.repo.update_concept_map(old['id'], {'title': '外部新变化', 'expected_revision': updated['revision']})
        with self.assertRaises(AgentError): self.commit(stale)
        self.assertEqual(self.repo.get_concept_map(old['id'])[0]['revision'], external['revision'])
        self.assertEqual(receipt, self.commit(preview))

    def test_cross_field_and_unknown_manifest_preflight_changes_no_json(self):
        from workbench.persistence import atomic_write_json
        from workbench.agent_execution import fingerprint
        preview = self.prepare_preview(self.graph_spec())
        def stop(stage):
            if stage == 'manifest': raise OSError('synthetic prepared exit')
        self.store.checkpoint = stop
        with self.assertRaises(AgentError): self.commit(preview)
        self.store.checkpoint = lambda stage: None
        path = self.store.operations / f"{preview['proposal_id']}-1" / 'manifest.json'
        original = json.loads(path.read_text(encoding='utf-8'))
        proposal_path = self.store.proposals / f"{preview['proposal_id']}.json"
        original_proposal = json.loads(proposal_path.read_text(encoding='utf-8'))
        # Call the actual frozen AG-134 validator: no new handler/step semantics
        # may be interpreted by the older program, regardless of registry state.
        legacy = GraphManagementTests.legacy_code(self)
        script = "import json,sys;from pathlib import Path;from workbench.agent_execution import validate_context,validate_manifest;p=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));m=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'));validate_context(p) if sys.argv[3]=='proposal' else validate_manifest(m,p)"
        evidence = GraphManagementTests.json_evidence(self)
        for mode in ('proposal', 'manifest'):
            result = subprocess.run([sys.executable, '-c', script, str(proposal_path), str(path), mode], cwd=legacy, capture_output=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(GraphManagementTests.json_evidence(self), evidence)
        def changed_steps(value):
            value['execution_plan']['steps'] = ['json_write']
            value['execution_plan_digest'] = fingerprint(value['execution_plan'])
            value['receipt']['execution_plan_digest'] = value['execution_plan_digest']
        changes = [lambda value: value.update(kind='issue'), lambda value: value.update(item_id='CMAP-9999'),
                   lambda value: value.update(relative_path='documents/DOC-0001.md'), lambda value: value.update(operation='delete'),
                   lambda value: value.update(execution_schema_version=4), lambda value: value.update(digest_algorithm='unknown'),
                   lambda value: value.update(history_version='../outside'), lambda value: value.update(managed_time='2030-01-01T00:00:00+00:00'),
                   lambda value: value.update(before_digest='b' * 64), lambda value: value.update(step_states=['completed', 'completed']), changed_steps]
        for change in changes:
            value = copy.deepcopy(original); change(value); atomic_write_json(path, value)
            evidence = GraphManagementTests.json_evidence(self)
            result = self.store.recover()
            self.assertTrue(result['blocked'], value)
            self.assertIn('format_error', result)
            self.assertEqual(GraphManagementTests.json_evidence(self), evidence)
            self.assertEqual(self.repo.list_concept_maps(), [])
        atomic_write_json(path, original)
        for change in (lambda value: value['identity'].update(client_id=str(uuid.uuid4())),
                       lambda value: value['normalized_content']['graph'].update(version=99)):
            value = copy.deepcopy(original_proposal); change(value); atomic_write_json(proposal_path, value)
            evidence = GraphManagementTests.json_evidence(self)
            result = self.store.recover()
            self.assertTrue(result['blocked'])
            self.assertEqual(GraphManagementTests.json_evidence(self), evidence)
        atomic_write_json(proposal_path, original_proposal)
        self.assertFalse(self.store.recover()['blocked'])

    def test_prepared_revocation_blocks_but_published_proof_finishes_after_revocation(self):
        for stage in ('manifest', 'target'):
            with self.subTest(stage=stage):
                fixture = AgentFixture(); fixture.setUp()
                try:
                    fixture.repo.ensure_concept_map_category('未分类')
                    GraphManagementTests.approve(self, fixture=fixture)
                    client = fixture.security.clients()[fixture.client['client_id']]
                    value = graph(); value['project_id'] = fixture.project['id']
                    proposal = fixture.service.prepare_proposal(client, {'request_id':uuid.uuid4().hex, 'kind':'concept_map', 'operation':'create', 'content':{'graph':value}})
                    preview = fixture.service.preview_proposal(client, proposal['proposal_id'])
                    def stop(current):
                        if current == stage: raise OSError('synthetic stage failure')
                    fixture.store.checkpoint = stop
                    with self.assertRaises(AgentError): fixture.service.commit_proposal(client, proposal['proposal_id'], self.confirmation(preview))
                    fixture.store.checkpoint = lambda current: None
                    fixture.security.manager().run('revoke', {}, client['client_id'], client_version(client))
                    recovered = fixture.store.recover()
                    if stage == 'manifest':
                        self.assertTrue(recovered['blocked'])
                        self.assertEqual(fixture.repo.list_concept_maps(), [])
                        fixture.store.abandon(f"{proposal['proposal_id']}-1")
                    else:
                        self.assertFalse(recovered['blocked'])
                        self.assertEqual(fixture.store._load(proposal['proposal_id'])['state'], 'committed')
                        self.assertEqual(fixture.repo.get_concept_map(proposal['target_id'])[0]['nodes'], value['nodes'])
                finally: fixture.tearDown()

    def test_history_then_revocation_does_not_publish_and_missing_history_does_not_finish(self):
        old = self.repo.create_concept_map(self.graph_spec()['content']['graph'])
        value = self.graph_spec(operation='update', target_id=old['id'], base_revision=old['revision'])
        value['content']['graph']['title'] = '不得在撤销后发布'
        preview = self.prepare_preview(value)
        def revoke(stage):
            if stage == 'history_logged': self.security.manager().run('revoke', {}, self.client['client_id'], client_version(self.client))
        self.store.checkpoint = revoke
        with self.assertRaises(AgentError): self.commit(preview)
        self.store.checkpoint = lambda stage: None
        self.assertEqual(self.repo.get_concept_map(old['id'])[0]['revision'], old['revision'])
        self.assertTrue(self.store.recover()['blocked'])
        self.store.abandon(f"{preview['proposal_id']}-1")
        # A separate client/operation proves publication alone is insufficient
        # when the required raw historical witness has disappeared.
        other = self.security.add_client('新的验收授权', ['read','propose','commit'], ['*'], ['*'], 'http://127.0.0.1:4174')
        current = self.security.clients()[other['client_id']]
        grants = graph_grants({'type':'project', 'id':self.project['id']})
        self.security.manager().run('concept_map_grants', {'grants':grants, 'approval_digest':'b' * 64, 'resource_dependencies':grant_dependencies(self.repo, grants)}, current['client_id'], client_version(current))
        self.client = self.security.clients()[current['client_id']]
        preview = self.prepare_preview(value)
        def stop(stage):
            if stage == 'target': raise OSError('synthetic after target')
        self.store.checkpoint = stop
        with self.assertRaises(AgentError): self.commit(preview)
        self.store.checkpoint = lambda stage: None
        directory = self.store.operations / f"{preview['proposal_id']}-1"
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        (self.repo.history_dir / old['id'] / f"{manifest['history_version']}.json").unlink()
        after = (self.repo.concept_maps_dir / f"{old['id']}.json").read_bytes()
        self.assertTrue(self.store.recover()['blocked'])
        self.assertFalse((self.store.receipts / f"{preview['proposal_id']}.json").exists())
        self.assertEqual((self.repo.concept_maps_dir / f"{old['id']}.json").read_bytes(), after)

    def test_completed_receipt_survives_delete_and_fixed_create_occupancy_is_409(self):
        preview = self.prepare_preview(self.graph_spec())
        receipt = self.commit(preview)
        self.repo.purge_trash(self.repo.delete_concept_map(receipt['item_id'])['token'])
        self.assertEqual(self.commit(preview), receipt)
        self.assertEqual(self.repo.list_concept_maps(), [])
        self.assertFalse(self.service.get_proposal(self.client, preview['proposal_id'])['current_item']['exists'])
        pending = self.prepare_preview(self.graph_spec())
        other = self.repo.create_project({'name':'不在当前图grant的项目'})
        value = graph(); value['project_id'] = other['id']
        prepared = self.repo._concept_map_repository.prepare_create(value, pending['target_id'])
        occupied = self.repo.apply_concept_map_write(prepared)
        before = GraphManagementTests.json_evidence(self)
        with self.assertRaises(AgentError) as error: self.commit(pending)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(GraphManagementTests.json_evidence(self), before)
        self.assertEqual(self.repo.get_concept_map(occupied['id'])[0]['revision'], occupied['revision'])


class GraphCandidateTests(AgentFixture, unittest.TestCase):
    def test_legacy_missing_classification_reads_defaults_without_mutating_source(self):
        service = self.candidates()
        raw = {**graph(), 'id':'CMAP-0088'}
        for field in ('version', 'project_id', 'category'): raw.pop(field)
        path = self.repo.concept_maps_dir / 'CMAP-0088.json'
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
        original = path.read_bytes()
        client = self.security.clients()[self.client['client_id']]
        grants = graph_grants({'type':'concept_map_category', 'name':'未分类'})
        self.security.manager().run('concept_map_grants', {'grants':grants, 'approval_digest':'a' * 64, 'resource_dependencies':grant_dependencies(self.repo, grants)}, client['client_id'], client_version(client))
        self.client = self.security.clients()[client['client_id']]
        read = service.get(self.client, raw['id'])
        self.assertEqual([item['id'] for item in service.list(self.client, {})['items']], [raw['id']])
        self.assertEqual(read['editable_graph']['category'], '未分类')
        self.assertIsNone(read['editable_graph']['project_id'])
        self.assertEqual(path.read_bytes(), original)
        content, base, _ = service.normalize(self.client, 'update', {'graph':read['editable_graph']}, raw['id'], read['revision'])
        prepared = service.prepare('update', content, raw['id'], read['revision'])
        from workbench.agent_concept_execution import graph_diff
        delta = graph_diff(base, json.loads(prepared.after))
        self.assertEqual(delta['metadata']['project_id'], {'before':None, 'after':None, 'before_present':False, 'after_present':True})
        self.repo.apply_concept_map_write(prepared)
        self.assertEqual(self.repo.get_concept_map(raw['id'])[0]['version'], 2)
        self.assertEqual(self.repo.get_concept_map(raw['id'])[0]['nodes'], raw['nodes'])

    def candidates(self):
        from workbench.agent_concept_service import GraphCandidateService
        self.repo.ensure_concept_map_category('未分类')
        GraphManagementTests.approve(self)
        self.client = self.security.clients()[self.client['client_id']]
        return GraphCandidateService(self.repo)

    def test_pure_complete_candidate_prepare_roundtrip_and_dependency_snapshot(self):
        from workbench.agent_concept_service import SERVICE_TIME
        service = self.candidates()
        value = graph()
        value['project_id'] = self.project['id']
        files = {str(path): path.read_bytes() for path in self.repo.root.rglob('*') if path.is_file()}
        content, base, warnings = service.normalize(self.client, 'create', {'graph': value})
        self.assertEqual((base, warnings), ({}, []))
        dependencies = service.dependencies(self.client, 'create', content, base)
        prepared = service.prepare('create', content, 'CMAP-0042', None)
        self.assertEqual(json.loads(prepared.after)['created'], SERVICE_TIME)
        self.assertEqual({str(path): path.read_bytes() for path in self.repo.root.rglob('*') if path.is_file()}, files)
        actual = service.prepare('create', content, 'CMAP-0042', None, managed_time='2026-11-10T01:02:03+00:00')
        created = self.repo.apply_concept_map_write(actual)
        stored, path = Repository(self.repo.root).get_concept_map(created['id'])
        self.assertEqual(stored['nodes'], value['nodes'])
        self.assertEqual(stored['created'], '2026-11-10T01:02:03+00:00')
        self.assertNotEqual(service.dependencies(self.client, 'create', content, base), dependencies)
        content['graph']['title'] = '更新后的图'
        normalized, base, warnings = service.normalize(self.client, 'update', content, stored['id'], stored['revision'])
        updated = service.prepare('update', normalized, stored['id'], stored['revision'], managed_time='2026-11-10T02:03:04+00:00')
        self.repo.apply_concept_map_write(updated)
        reloaded, _ = Repository(self.repo.root).get_concept_map(stored['id'])
        self.assertEqual(reloaded['created'], stored['created'])
        self.assertEqual(reloaded['updated'], '2026-11-10T02:03:04+00:00')
        self.assertEqual(self.repo.get_concept_map_history(stored['id'], updated.history_version)['title'], stored['title'])

    def test_named_graph_cannot_reparent_and_server_managed_fields_are_forbidden(self):
        service = self.candidates()
        value = graph(); value['project_id'] = self.project['id']
        created = self.repo.create_concept_map(value)
        current = self.security.clients()[self.client['client_id']]
        grants = graph_grants({'type': 'concept_map', 'id': created['id']})
        self.security.manager().run('concept_map_grants', {'grants': grants, 'approval_digest': 'a' * 64, 'resource_dependencies': grant_dependencies(self.repo, grants)},
                                    current['client_id'], client_version(current), 'named-only')
        client = self.security.clients()[current['client_id']]
        service.normalize(client, 'update', {'graph': value}, created['id'], created['revision'])
        for change in ({'project_id': None}, {'id': created['id']}, {'updated': 'forged'}, {'revision': created['revision']}):
            with self.assertRaises(AgentError):
                service.normalize(client, 'update', {'graph': {**value, **change}}, created['id'], created['revision'])
        with self.assertRaises(AgentError): service.normalize(client, 'create', {'graph': value})
        with self.assertRaises(AgentError): service.normalize(client, 'update', {'graph': value}, created['id'], 'b' * 64)
        with self.assertRaises(AgentError): service.normalize(client, 'append', {'graph': value}, created['id'], created['revision'])

    def test_extra_legacy_fields_are_preserved_or_explicitly_warned(self):
        service = self.candidates()
        value = graph(); value['project_id'] = self.project['id']
        created = self.repo.create_concept_map(value)
        path = self.repo.concept_maps_dir / f"{created['id']}.json"
        saved = json.loads(path.read_text(encoding='utf-8'))
        saved['legacy_meta'] = {'说明': '未知顶层保留'}
        saved['nodes'][0]['legacy_node'] = '将丢失须警告'
        path.write_text(json.dumps(saved, ensure_ascii=False), encoding='utf-8')
        stored, _ = self.repo.get_concept_map(created['id'])
        normalized, base, warnings = service.normalize(self.client, 'update', {'graph': value}, created['id'], stored['revision'])
        self.assertEqual(base['legacy_meta'], saved['legacy_meta'])
        self.assertTrue(any('legacy_node' in warning for warning in warnings))
        prepared = service.prepare('update', normalized, created['id'], stored['revision'])
        candidate = json.loads(prepared.after)
        self.assertEqual(candidate['legacy_meta'], saved['legacy_meta'])
        self.assertNotIn('legacy_node', candidate['nodes'][0])

    def test_full_read_budgets_distinguish_raw_pretty_json_and_compact_data(self):
        service = self.candidates()
        value = graph(); value['project_id'] = self.project['id']
        value['nodes'] = [{**value['nodes'][0], 'id':f'n{i}', 'text':f'N{i}', 'note':''} for i in range(500)]
        value['edges'] = [{**value['edges'][0], 'id':f'e{i}', 'from':f'n{i % 500}', 'to':f'n{(i + 1) % 500}', 'label':''} for i in range(1000)]
        created = self.repo.create_concept_map(value)
        path = self.repo.concept_maps_dir / f"{created['id']}.json"
        self.assertGreater(path.stat().st_size, GRAPH_BYTES)
        read = service.get(self.client, created['id'])
        self.assertEqual(len(read['graph']['nodes']), 500)
        self.assertEqual(len(read['editable_graph']['edges']), 1000)
        self.assertEqual(read['revision'], created['revision'])
        raw = json.loads(path.read_text(encoding='utf-8'))
        raw['extra_legacy'] = 'a' * GRAPH_BYTES
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(AgentError) as error: service.get(self.client, created['id'])
        self.assertEqual(error.exception.status, 413)
        path.write_bytes(b' ' * (1024 * 1024 + 1))
        from workbench.agent_concept_maps import read_graph
        with self.assertRaises(AgentError) as error: read_graph(self.repo.root, created['id'])
        self.assertEqual(error.exception.status, 413)

    def test_graph_only_scope_has_no_project_body_and_effective_operations_intersect(self):
        self.candidates()
        current = self.security.clients()[self.client['client_id']]
        params = {'name':current['name'], 'scopes':current['scopes'], 'project_ids':[], 'categories':[], 'kinds':[]}
        self.security.manager().run('edit', params, current['client_id'], client_version(current))
        client = self.security.clients()[current['client_id']]
        self.assertEqual(client['kinds'], ['concept_map'])
        self.assertEqual(self.service.projects(client, {})['items'], [])
        self.assertEqual(self.service.catalog(client, {})['document_categories'], [])
        issue = self.repo.create_record({'type':'issue', 'project_id':self.project['id'], 'title':'不可隐式读取'})
        with self.assertRaises(AgentError): self.service.get_item(client, 'issue', issue['id'])
        graph = self.repo.create_concept_map({'title':'已有指定图', 'project_id':self.project['id']})
        grants = graph_grants({'type':'concept_map', 'id':graph['id']})
        self.security.manager().run('concept_map_grants', {'grants':grants, 'approval_digest':'a' * 64, 'resource_dependencies':grant_dependencies(self.repo, grants)}, client['client_id'], client_version(client))
        client = self.security.clients()[client['client_id']]
        capabilities = self.service.capabilities(client)
        self.assertEqual(capabilities['kind_operations']['concept_map'], ['update'])
        self.assertEqual(capabilities['kind_fields']['concept_map'], {'update':['graph']})
        grants['grants'][0]['resources'] = [{'type':'concept_map_category', 'name':'未分类'}]
        grants['grants'][1]['resources'] = [{'type':'project', 'id':self.project['id']}]
        self.security.manager().run('concept_map_grants', {'grants':grants, 'approval_digest':'b' * 64, 'resource_dependencies':grant_dependencies(self.repo, grants)}, client['client_id'], client_version(client))
        capabilities = self.service.capabilities(self.security.clients()[client['client_id']])
        self.assertNotIn('concept_maps.write', capabilities['capability_authorization']['effective'])
        self.assertNotIn('concept_map', capabilities['kind_operations'])


class GraphGrantHTTPTests(unittest.TestCase):
    setUp = runtime_tests.AgentManagementHTTPTests.setUp
    tearDown = runtime_tests.AgentManagementHTTPTests.tearDown
    request = runtime_tests.AgentManagementHTTPTests.request

    def test_loopback_session_full_preview_explicit_approval_replay_and_revoke(self):
        status = self.request('status')[1]
        headers = {'Origin': self.origin, 'X-Workbench-Management-Token': status['management_token']}
        unknown = str(uuid.uuid4())
        self.assertEqual(self.request(f'clients/{unknown}/concept-maps', headers=headers)[0], 409)
        self.assertFalse((self.base / 'private').exists())
        self.request('runtime', 'PATCH', {'workspace_id': None, 'expected_version': status['version'], 'request_id': 'enable', 'enabled': True}, headers)
        workspace = self.repo.agent_runtime.status()['workspace_id']
        project = self.repo.create_project({'name': '授权范围'})
        created = self.request('clients', 'POST', {'workspace_id': workspace, 'request_id': 'create', 'name': '图客户端', 'scopes': ['read', 'propose', 'commit'], 'project_ids': ['*'], 'categories': []}, headers)[1]
        key = created['client_id']
        route = f'clients/{key}/concept-maps'
        before = (self.base / 'private' / workspace / 'clients.json').read_bytes()
        self.assertEqual(self.request(route, headers=headers)[0], 200)
        payload = {'workspace_id': workspace, 'expected_version': created['version'], 'grants': graph_grants({'type': 'project', 'id': project['id']})}
        for invalid in ({}, {**headers, 'Origin': 'http://evil.test'}, {**headers, 'Authorization': 'Bearer invalid'}, {**headers, 'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual(self.request(route + '/preview', 'POST', payload, invalid)[0], 403)
        self.assertEqual(self.request(route + '?extra=1', headers=headers)[0], 400)
        code, preview = self.request(route + '/preview', 'POST', payload, headers)
        self.assertEqual(code, 200, preview)
        self.assertEqual((self.base / 'private' / workspace / 'clients.json').read_bytes(), before)
        approval = {key: preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')} | {'request_id': 'grant-once', 'approved': True}
        self.assertEqual(self.request(route + '/confirm', 'POST', {**approval, 'approved': False}, headers)[0], 400)
        code, result = self.request(route + '/confirm', 'POST', approval, headers)
        self.assertEqual(code, 200, result)
        self.repo.agent_runtime.preview_tickets.clear()
        self.assertEqual(self.request(route + '/confirm', 'POST', approval, headers), (200, result))
        self.assertEqual(self.request(route, headers=headers)[1]['grants'], normalize_graph_grants(payload['grants']))
        code, withdrawn = self.request(route, 'DELETE', {'workspace_id': workspace, 'expected_version': result['version'], 'request_id': 'withdraw'}, headers)
        self.assertEqual(code, 200, withdrawn)
        self.assertEqual(self.request(route, headers=headers)[1]['grants']['grants'], [])


class GraphManagementTests(AgentFixture, unittest.TestCase):
    def test_narrow_preserves_inactive_kind_and_recovery_rejects_resource_expansion(self):
        from workbench.agent_management import digest
        from workbench.persistence import atomic_write_json
        self.approve()
        key = self.client['client_id']
        clients = self.security.clients()
        clients[key]['kinds'] = []  # Valid explicit restriction in private auth5.
        self.security.save_clients(clients)
        before = self.security.clients()[key]
        read_only = {'schema_version':1, 'grants':[grant for grant in before['concept_map_grants']['grants'] if grant['capability'] == 'concept_maps.read']}
        manager = self.security.manager()
        manager.run('concept_map_grants_narrow', {'grants':read_only}, key, client_version(before), 'inactive-kind-narrow')
        current = self.security.clients()[key]
        self.assertEqual(current['kinds'], [])
        self.assertFalse(graph_allows(current, {'type':'concept_map', 'id':'CMAP-1', 'project_id':self.project['id'], 'category':'未分类'}))
        self.approve(key='fresh-explicit-kind-approval')
        before = self.security.clients()[key]
        other = self.repo.create_project({'name':'不能被收窄操作扩大到这里'})
        def stop(stage):
            if stage == 'prepared': raise OSError('synthetic narrow intent interruption')
        manager.checkpoint = stop
        with self.assertRaises(OSError): manager.run('concept_map_grants_narrow', {'grants':read_only}, key, client_version(before), 'pending-narrow')
        manager.checkpoint = lambda stage: None
        operation = hashlib.sha256(b'pending-narrow').hexdigest()
        path = manager.directory / f'{operation}.json'
        snapshot_path = manager._snapshot_path(operation)
        original_log = json.loads(path.read_text(encoding='utf-8'))
        original_snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
        for mutate in (lambda client: client.update(kinds=[]),
                       lambda client: client['concept_map_grants']['grants'][0].update(resources=[{'type':'project', 'id':other['id']}]),
                       lambda client: client.update(scopes=['read'])):
            snapshot = copy.deepcopy(original_snapshot); mutate(snapshot['values']['after_client'])
            log = copy.deepcopy(original_log)
            log['graph_grants_digest'] = digest(snapshot['values']['after_client']['concept_map_grants'])
            snapshot['intent']['graph_grants_digest'] = log['graph_grants_digest']
            log['private_snapshot_digest'] = digest(snapshot)
            atomic_write_json(snapshot_path, snapshot); atomic_write_json(path, log)
            evidence = self.json_evidence()
            with self.assertRaises(AgentError): manager.recover()
            self.assertEqual(self.json_evidence(), evidence)
        atomic_write_json(snapshot_path, original_snapshot); atomic_write_json(path, original_log)
        manager.recover()
        self.assertEqual(self.security.clients()[key]['concept_map_grants'], read_only)

    def grant_management(self):
        from workbench.agent_runtime import AgentRuntime
        from workbench.agent_concept_authorization import GraphGrantManagement
        runtime = AgentRuntime(self.repo, base=self.base / 'credentials')
        self.repo.agent_runtime = runtime
        return GraphGrantManagement(runtime)

    def grant_preview(self, management, grants=None):
        client = self.security.clients()[self.client['client_id']]
        return management.preview(client['client_id'], {'workspace_id': self.security.workspace_id,
                                  'expected_version': client_version(client),
                                  'grants': grants or graph_grants({'type': 'project', 'id': self.project['id']})})

    def approval_payload(self, preview):
        return {key: preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')} | {'request_id': uuid.uuid4().hex, 'approved': True}

    def test_management_full_preview_is_zero_write_and_loss_replays_original(self):
        management = self.grant_management()
        created = self.repo.create_concept_map({'title': '范围内原图', 'project_id': self.project['id']})
        evidence = self.json_evidence()
        preview = self.grant_preview(management)
        self.assertEqual(evidence, self.json_evidence())
        self.assertEqual(preview['resources'][0]['maps'][0]['id'], created['id'])
        self.assertEqual(preview['resources'][0]['count'], 1)
        payload = self.approval_payload(preview)
        result = management.approve(self.client['client_id'], payload)
        evidence = self.json_evidence()
        management.runtime.preview_tickets.clear()
        self.assertEqual(result, management.approve(self.client['client_id'], payload))
        self.assertEqual(evidence, self.json_evidence())
        for changed in ({'preview_digest': 'b' * 64}, {'expected_version': 'c' * 64}, {'approved': False}):
            with self.assertRaises(AgentError):
                management.approve(self.client['client_id'], {**payload, **changed})
            self.assertEqual(evidence, self.json_evidence())
        fresh = self.security.clients()[self.client['client_id']]
        revoked = management.revoke(fresh['client_id'], {'workspace_id': self.security.workspace_id, 'expected_version': client_version(fresh), 'request_id': 'explicit-withdraw'})
        self.assertEqual(self.security.clients()[fresh['client_id']]['concept_map_grants']['grants'], [])
        self.assertEqual(revoked['version'], client_version(self.security.clients()[fresh['client_id']]))

    def test_management_stale_session_runtime_client_and_resources_refuse_approval(self):
        management = self.grant_management()
        key = self.client['client_id']
        for cause in ('session', 'runtime', 'expiry', 'digest', 'resource', 'client'):
            with self.subTest(cause=cause):
                preview = self.grant_preview(management)
                payload = self.approval_payload(preview)
                ticket = management.runtime.preview_tickets[preview['preview_id']]
                if cause == 'session': ticket['session'] = 'changed'
                elif cause == 'runtime': ticket['runtime_version'] = 'changed'
                elif cause == 'expiry': ticket['expires'] = 0
                elif cause == 'digest': ticket['graph_grant_preview']['resources'] = []
                elif cause == 'resource': self.repo.update_project(self.project['id'], {'description': '外部变化'})
                else: self.security.manager().run('rotate', {}, key, client_version(self.security.clients()[key]))
                evidence = self.json_evidence()
                with self.assertRaises(AgentError): management.approve(key, payload)
                self.assertEqual(evidence, self.json_evidence())
                self.assertNotIn('concept_map_grants', self.security.clients()[key])

    def test_category_rename_preserves_equivalent_scope_and_other_changes_narrow(self):
        management = self.grant_management()
        key = self.client['client_id']
        for action in ('rename', 'delete', 'empty', 'failure'):
            with self.subTest(action=action):
                category = '原分类' + action
                self.repo.ensure_concept_map_category(category)
                if action != 'empty': self.repo.create_concept_map({'title': '独立图', 'category': category})
                preview = self.grant_preview(management, graph_grants({'type': 'concept_map_category', 'name': category}))
                management.approve(key, self.approval_payload(preview))
                if action == 'rename': self.repo.rename_concept_map_category(category, '新分类')
                elif action == 'delete': self.repo.delete_concept_map_category(category)
                elif action == 'empty': self.repo.save_concept_map_categories([name for name in self.repo.concept_map_categories() if name != category])
                else:
                    def interrupted(point):
                        if point == 'category_business_applying':
                            raise OSError('synthetic write failure')
                    with patch.object(self.repo.agent_proposals, 'checkpoint', side_effect=interrupted):
                        with self.assertRaises(AgentError): self.repo.delete_concept_map_category(category)
                    self.assertIn(category, self.repo.concept_map_categories())
                expected = graph_grants({'type':'concept_map_category', 'name':'新分类'})['grants'] if action == 'rename' else []
                self.assertEqual(self.security.clients()[key]['concept_map_grants']['grants'], expected)
                if action == 'failure':
                    self.assertFalse(self.repo.agent_proposals.recover()['blocked'])
                self.repo.ensure_concept_map_category(category)
                self.assertEqual(self.security.clients()[key]['concept_map_grants']['grants'], expected)
                self.assertEqual(self.security.registry_version(), 8)

    def test_narrow_cannot_expand_and_unknown_paths_never_become_grant_dependencies(self):
        self.approve()
        key = self.client['client_id']
        current = self.security.clients()[key]
        evidence = self.json_evidence()
        with self.assertRaises(ValueError):
            self.security.manager().run('concept_map_grants_narrow', {'grants': graph_grants({'type': 'concept_map_category', 'name': '未分类'})}, key, client_version(current))
        self.assertEqual(evidence, self.json_evidence())
        source = self.repo.create_concept_map({'title': '硬链接受保护'})
        path = self.repo.concept_maps_dir / f"{source['id']}.json"
        alias = self.base / 'synthetic-hardlink.json'
        os.link(path, alias)
        with self.assertRaises(AgentError) as error:
            grant_dependencies(self.repo, current['concept_map_grants'])
        self.assertEqual(error.exception.code, 'unsafe_concept_map_path')
        alias.unlink()
        path.write_text('{invalid', encoding='utf-8')
        with self.assertRaises(AgentError): grant_dependencies(self.repo, current['concept_map_grants'])

    def legacy_code(self):
        directory = self.base / 'legacy-code'
        if not directory.exists():
            from workbench.security import validate_archive_member
            archive = subprocess.check_output(['git', 'archive', '--format=zip', '9e43aa3'], cwd=Path(__file__).parent)
            with zipfile.ZipFile(io.BytesIO(archive)) as source:
                for name in source.namelist():
                    validate_archive_member(name.rstrip('/'))
                source.extractall(directory)
        return directory

    def json_evidence(self, fixture=None):
        fixture = fixture or self
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for root in (fixture.repo.root, fixture.security.config_dir)
                for path in root.rglob('*.json')}

    def crash_graph_approval(self, fixture, stage):
        script = '''import sys,os
from pathlib import Path
from server import Repository
from workbench.agent_security import AgentSecurity
from workbench.agent_management import client_version
from workbench.agent_concept_authorization import grant_dependencies
r=Repository(Path(sys.argv[1]));s=AgentSecurity(r.root,Path(sys.argv[2]));c=s.clients()[sys.argv[3]]
resources=[{'type':'project','id':sys.argv[4]}]
grants={'schema_version':1,'grants':[{'capability':'concept_maps.read','operations':['read'],'resources':resources,'minimum_confirmation_mode':'agent_attested'},{'capability':'concept_maps.write','operations':['create','update'],'resources':resources,'minimum_confirmation_mode':'agent_attested'}]}
m=s.manager();m.checkpoint=lambda current:os._exit(76) if current==sys.argv[5] else None
m.run('concept_map_grants',{'grants':grants,'approval_digest':'a'*64,'resource_dependencies':grant_dependencies(r,grants)},c['client_id'],client_version(c),'real-'+sys.argv[5])
'''
        result = subprocess.run([sys.executable, '-c', script, str(fixture.repo.root), str(fixture.base / 'credentials'), fixture.client['client_id'], fixture.project['id'], stage],
                                cwd=Path(__file__).parent, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 76, result.stderr)

    def approve(self, key='graph-approval', fixture=None):
        fixture = fixture or self
        client = fixture.security.clients()[fixture.client['client_id']]
        grants = graph_grants({'type': 'project', 'id': fixture.project['id']})
        params = {'grants': grants, 'approval_digest': 'a' * 64, 'resource_dependencies': grant_dependencies(fixture.repo, grants)}
        return fixture.security.manager().run('concept_map_grants', params, client['client_id'], client_version(client), key)

    def test_graph_grant_persistence_and_other_credential_changes_never_downgrade(self):
        result = self.approve()
        key = self.client['client_id']
        after = self.security.clients()[key]
        self.assertEqual(after['authorization_schema_version'], 5)
        self.assertEqual(json.loads(self.security.registry.read_text(encoding='utf-8'))['schema_version'], 4)
        self.assertIn('concept_map', after['kinds'])
        saved = copy.deepcopy(after['concept_map_grants'])
        for action in ('edit', 'rotate'):
            params = {field: after[field] for field in ('name', 'scopes', 'project_ids', 'categories')} if action == 'edit' else {}
            if action == 'edit': params['kinds'] = ['issue']
            changed = self.security.manager().run(action, params, key, client_version(after), f'after-graph-{action}')
            after = self.security.clients()[key]
            self.assertEqual(after['concept_map_grants'], saved)
            self.assertEqual(after['authorization_schema_version'], 5)
            self.assertIn('concept_map', after['kinds'])
            self.assertEqual(changed['version'], client_version(after))
        # Root format stays even when a different, legacy client is created/edited.
        other = self.security.add_client('旧业务客户端', ['read'], ['*'], ['*'], 'http://127.0.0.1:4174', request_id='after-graph-create')
        self.assertNotIn('concept_map_grants', self.security.clients()[other['client_id']])
        self.assertEqual(json.loads(self.security.registry.read_text(encoding='utf-8'))['schema_version'], 4)
        revoked = self.security.manager().run('concept_map_grants_revoke', {}, key, client_version(after), 'graph-withdraw')
        after = self.security.clients()[key]
        self.assertEqual(after['authorization_schema_version'], 5)
        self.assertEqual(after['concept_map_grants']['grants'], [])
        self.assertFalse(allows(after, {'type': 'concept_map', 'id': 'CMAP-0001', 'project_id': self.project['id']}))
        self.assertEqual(revoked['version'], client_version(after))
        for path in self.security.manager().directory.glob('*.json'):
            value = json.loads(path.read_text(encoding='utf-8'))
            if value.get('schema_version') == 5:
                self.assertNotIn('after_client', value)
                self.assertNotIn('before_client', value)
        self.assertEqual(list((self.security.config_dir / 'management-snapshots').glob('*.json')), [])
        self.assertEqual(result['client_id'], key)

    def test_resource_change_before_approval_and_at_publish_never_activates(self):
        client = self.security.clients()[self.client['client_id']]
        grants = graph_grants({'type': 'project', 'id': self.project['id']})
        old = grant_dependencies(self.repo, grants)
        self.repo.update_project(self.project['id'], {'description': '授权前外部变化'})
        with self.assertRaises(AgentError):
            self.security.manager().run('concept_map_grants', {'grants': grants, 'approval_digest': 'a' * 64, 'resource_dependencies': old}, client['client_id'], client_version(client), 'outdated-resource')
        self.assertNotIn('concept_map_grants', self.security.clients()[client['client_id']])
        manager = self.security.manager()
        def change(stage):
            if stage == 'config': self.repo.update_project(self.project['id'], {'description': '发布前再次变化'})
        params = {'grants': grants, 'approval_digest': 'a' * 64, 'resource_dependencies': grant_dependencies(self.repo, grants)}
        with patch.object(manager, 'checkpoint', side_effect=change), self.assertRaises(AgentError):
            manager.run('concept_map_grants', params, client['client_id'], client_version(client), 'changed-at-publication')
        self.assertNotIn('concept_map_grants', self.security.clients()[client['client_id']])
        operations = manager.report()
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]['state'], 'recovery_required')
        manager.abandon(operations[0]['operation_id'])
        self.assertFalse(self.security.clients()[client['client_id']]['enabled'])
        self.assertEqual(json.loads(self.security.registry.read_text(encoding='utf-8'))['schema_version'], 4)

    @unittest.skipUnless(SUPPORTED, 'Native file/staging family compatibility requires Windows NTFS')
    def test_file_upload_attachment_and_withdraw_preserve_graph_authority(self):
        from workbench.agent_runtime import AgentRuntime
        from workbench.agent_files import FileManagement
        from workbench.agent_upload_policy import UploadPolicyManagement
        self.approve()
        key = self.client['client_id']
        saved = copy.deepcopy(self.security.clients()[key]['concept_map_grants'])
        runtime = AgentRuntime(self.repo, base=self.base / 'credentials')
        self.repo.agent_runtime, self.repo.agent_service = runtime, self.service
        files = FileManagement(runtime)
        source = self.base / 'temporary-source.txt'; source.write_text('本轮合成来源', encoding='utf-8')
        current = self.security.clients()[key]
        preview = files.preview(key, {'workspace_id': self.security.workspace_id, 'expected_version': client_version(current), 'path': str(source),
                                     'purposes': ['text_read'], 'encoding': 'auto', 'max_bytes': 1048576, 'duration_seconds': 3600})
        payload = {name: preview[name] for name in ('workspace_id', 'preview_id', 'preview_digest', 'expected_version')}
        payload.update(request_id=uuid.uuid4().hex, approved=True)
        record = files.approved_record(key, payload)
        files.commit(key, payload, record)
        current = self.security.clients()[key]
        self.assertEqual(current['concept_map_grants'], saved)
        self.assertEqual(current['authorization_schema_version'], 5)
        self.security.manager().run('file_grant_revoke', {'file_id': record['file_id']}, key, client_version(current), 'graph-then-file-revoke')
        policies = UploadPolicyManagement(runtime)
        for attachment in (False, True):
            current = self.security.clients()[key]
            values = {'workspace_id': self.security.workspace_id, 'expected_version': client_version(current), 'owner_kind': 'project', 'owner_id': self.project['id'],
                      'stream': True, 'files': [], 'max_bytes': 1048576, 'duration_seconds': 3600}
            if attachment: values.update(attachment_write=True, minimum_confirmation_mode='local_web')
            preview = policies.preview(key, values)
            payload = {name: preview[name] for name in ('workspace_id', 'preview_id', 'preview_digest', 'expected_version')}
            payload.update(request_id=uuid.uuid4().hex, approved=True)
            policies.approve(key, payload)
            current = self.security.clients()[key]
            self.assertEqual(current['authorization_schema_version'], 5)
            self.assertEqual(current['concept_map_grants'], saved)
        current = self.security.clients()[key]
        self.security.manager().run('upload_policy_revoke', {}, key, client_version(current), 'graph-then-upload-revoke')
        current = self.security.clients()[key]
        self.assertEqual(current['authorization_schema_version'], 5)
        self.assertEqual(current['concept_map_grants'], saved)
        self.security.manager().run('revoke', {}, key, client_version(current), 'graph-then-client-revoke')
        current = self.security.clients()[key]
        self.assertFalse(current['enabled'])
        self.assertEqual(current['authorization_schema_version'], 5)
        self.assertEqual(current['concept_map_grants'], saved)
        self.assertEqual(json.loads(self.security.registry.read_text(encoding='utf-8'))['schema_version'], 4)

    def test_each_graph_management_failure_recovers_or_abandons_preintent(self):
        for stage in ('private_snapshot', 'prepared', 'format_fence', 'config', 'registry', 'terminal_log', 'completed'):
            with self.subTest(stage=stage):
                fixture = AgentFixture(); fixture.setUp()
                try:
                    client = fixture.client
                    grants = graph_grants({'type': 'project', 'id': fixture.project['id']})
                    params = {'grants': grants, 'approval_digest': 'a' * 64, 'resource_dependencies': grant_dependencies(fixture.repo, grants)}
                    manager = fixture.security.manager()
                    def fail(current):
                        if current == stage: raise RuntimeError(stage)
                    with patch.object(manager, 'checkpoint', side_effect=fail), self.assertRaises(RuntimeError):
                        manager.run('concept_map_grants', params, client['client_id'], client_version(client), stage)
                    fixture.security.manager().recover()
                    current = fixture.security.clients()[client['client_id']]
                    self.assertEqual(current.get('authorization_schema_version') == 5, stage != 'private_snapshot')
                    self.assertEqual(json.loads(fixture.security.registry.read_text(encoding='utf-8'))['schema_version'], 4)
                    self.assertEqual(list((fixture.security.config_dir / 'management-snapshots').glob('*.json')), [])
                    if stage != 'private_snapshot':
                        original_version = client_version(current)
                        result = fixture.security.manager().run('concept_map_grants', params, client['client_id'], client_version(client), stage)
                        self.assertEqual(result['version'], original_version)
                finally:
                    fixture.tearDown()

    def test_real_management_exits_and_old_management_zero_json_write_fences(self):
        legacy = self.legacy_code()
        for stage in ('private_snapshot', 'prepared', 'format_fence', 'config', 'registry', 'terminal_log', 'completed'):
            with self.subTest(stage=stage):
                fixture = AgentFixture(); fixture.setUp()
                try:
                    self.crash_graph_approval(fixture, stage)
                    if stage in {'private_snapshot', 'prepared'}:
                        self.assertLess(fixture.security.registry_version(), 4)
                    current = fixture.security.clients()[fixture.client['client_id']]
                    self.assertEqual(current.get('authorization_schema_version') == 5, stage in {'registry', 'terminal_log', 'completed'})
                    before = self.json_evidence(fixture)
                    result = subprocess.run([sys.executable, str(legacy / 'server.py'), '--data-dir', str(fixture.repo.root), '--agent-config-dir', str(fixture.base / 'credentials'), '--agent-management-report'],
                                            cwd=legacy, capture_output=True, timeout=20, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.json_evidence(fixture), before, f'old management wrote JSON at {stage}')
                    fixture.security.manager().recover()
                    current = fixture.security.clients()[fixture.client['client_id']]
                    self.assertEqual(current.get('authorization_schema_version') == 5, stage != 'private_snapshot')
                    self.assertEqual(fixture.security.registry_version(), 4)
                finally:
                    fixture.tearDown()

    def test_old_business_write_is_allowed_but_prepublication_dependencies_conflict(self):
        legacy = self.legacy_code()
        self.crash_graph_approval(self, 'prepared')
        before = self.security.clients()[self.client['client_id']]
        self.assertNotIn('concept_map_grants', before)
        script = "from pathlib import Path;import sys;from server import Repository;r=Repository(Path(sys.argv[1]));r.update_project(sys.argv[2],{'description':'legitimate old business edit'})"
        result = subprocess.run([sys.executable, '-c', script, str(self.repo.root), self.project['id']], cwd=legacy, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.security.manager().recover()
        current = self.security.clients()[self.client['client_id']]
        self.assertNotIn('concept_map_grants', current)
        self.assertIn('legitimate old business edit', self.repo.project(self.project['id'])['description'])
        self.assertEqual(self.security.manager().report()[0]['state'], 'recovery_required')


class StrictConceptMapTests(unittest.TestCase):
    def test_prepare_create_is_pure_and_fixed_identity_cannot_be_taken_over(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Repository(Path(temp))
            domain = repo._concept_map_repository
            value = graph(); value['category'] = '尚未创建的分类'
            before = {p.relative_to(repo.root): p.read_bytes() for p in repo.root.rglob('*') if p.is_file()}
            prepared = domain.prepare_create(value, 'CMAP-0123', managed_time='提交时生成', default_node=False)
            self.assertEqual(prepared.before, None)
            self.assertEqual(json.loads(prepared.after)['id'], 'CMAP-0123')
            self.assertEqual(json.loads(prepared.after)['created'], '提交时生成')
            self.assertFalse(prepared.path.exists())
            self.assertEqual({p.relative_to(repo.root): p.read_bytes() for p in repo.root.rglob('*') if p.is_file()}, before)
            saved = repo.apply_concept_map_write(prepared)
            self.assertEqual(Repository(repo.root).get_concept_map(saved['id'])[0]['revision'], saved['revision'])
            raw = prepared.path.read_bytes()
            with self.assertRaises(FileExistsError):
                domain.prepare_create(value, 'CMAP-0123')
            self.assertEqual(prepared.path.read_bytes(), raw)

    def test_web_create_honors_injected_reservations_and_keeps_default_root(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Repository(Path(temp))
            domain = repo._concept_map_repository
            domain.reserved_ids = lambda: {'CMAP-0042', 'CMAP-0003'}
            item = repo.create_concept_map({'title': '网页默认根', 'category': '新的分类'})
            self.assertEqual(item['id'], 'CMAP-0043')
            self.assertEqual(item['nodes'][0]['id'], 'node-1')
            self.assertIn('新的分类', Repository(repo.root).concept_map_categories())
            self.assertEqual(Repository(repo.root).get_concept_map(item['id'])[0]['nodes'], item['nodes'])
            def unknown():
                raise ValueError('unknown reservation evidence')
            domain.reserved_ids = unknown
            before = sorted(repo.concept_maps_dir.iterdir())
            with self.assertRaises(ValueError):
                repo.create_concept_map({'title': '不能忽略未知占用'})
            self.assertEqual(sorted(repo.concept_maps_dir.iterdir()), before)

    def test_complete_candidate_keeps_ids_and_explicit_color_canonicalization(self):
        value = graph()
        normalized, warnings = validate_graph(value, create=True)
        self.assertEqual(normalized, value)
        self.assertEqual(warnings, [])
        value['nodes'][0]['color'] = '#AABBCC'
        normalized, warnings = validate_graph(value)
        self.assertEqual(normalized['nodes'][0]['color'], '#aabbcc')
        self.assertTrue(warnings)
        self.assertEqual(normalized['edges'][0]['id'], 'e')
        self.assertEqual(normalized['nodes'][0]['id'], 'a')

    def test_unknown_missing_and_invalid_typed_fields_reject_before_normalization(self):
        changes = [
            lambda g: g.update(id='CMAP-1234'),
            lambda g: g.pop('viewport'),
            lambda g: g['nodes'][0].update(extra='not allowed'),
            lambda g: g['edges'][0].pop('arrowhead'),
            lambda g: g.update(version=True),
            lambda g: g['viewport'].update(zoom=True),
            lambda g: g['nodes'][0].update(x=float('nan')),
            lambda g: g['nodes'][0].update(y=float('inf')),
            lambda g: g['nodes'][0].update(x=10**1000),
            lambda g: g['nodes'][0].update(font_size=13.5),
            lambda g: g['nodes'][0].update(color='red;position:fixed'),
            lambda g: g['nodes'][0].update(text='x' * 501),
            lambda g: g['nodes'][0].update(text=' leading'),
            lambda g: g['edges'][0].update(dashed='false'),
            lambda g: g['edges'][0].update(**{'from': []}),
            lambda g: g.update(project_id=False),
            lambda g: g.update(title='\ud800'),
        ]
        for change in changes:
            value = graph()
            change(value)
            with self.subTest(change=repr(value)[:160]), self.assertRaises(AgentError):
                validate_graph(value)

    def test_duplicates_unknown_references_self_edges_and_phrase_arrows_reject(self):
        changes = [
            lambda g: g['nodes'][1].update(id='a'),
            lambda g: g['edges'].append(copy.deepcopy(g['edges'][0])),
            lambda g: g['edges'][0].update(to='missing'),
            lambda g: g['edges'][0].update(to='a'),
            lambda g: g['nodes'][1].update(type='unknown'),
            lambda g: g['nodes'][1].update(type='linking_phrase'),
            lambda g: g['nodes'][0].update(type='linking_phrase') or g['edges'][0].update(arrowhead='both'),
        ]
        for change in changes:
            value = graph()
            change(value)
            with self.subTest(value=value), self.assertRaises(AgentError):
                validate_graph(value)

    def test_existing_numeric_bounds_and_large_count_boundary_remain(self):
        value = ConceptMapRepository.normalize({'title': '边界图',
            'nodes': [{'id': f'n-{i}', 'text': f'节点{i}'} for i in range(500)],
            'edges': [{'id': f'e-{i}', 'from': f'n-{i % 500}', 'to': f'n-{(i + 1 + i // 500) % 500}', 'label': '关联'} for i in range(1000)]})
        self.assertLess(len(json_bytes(value)), GRAPH_BYTES)
        self.assertEqual(len(validate_graph(value)[0]['nodes']), 500)
        for collection in ('nodes', 'edges'):
            invalid = copy.deepcopy(value)
            invalid[collection].append(copy.deepcopy(invalid[collection][0]))
            with self.assertRaises(AgentError):
                validate_graph(invalid)
        for key, number in (('width', 421), ('height', 261), ('x', 100001), ('font_size', 33), ('font_weight', 401)):
            invalid = graph(); invalid['nodes'][0][key] = number
            with self.assertRaises(AgentError):
                validate_graph(invalid)
        empty = graph(); empty.update(nodes=[], edges=[])
        self.assertEqual(validate_graph(empty)[0]['nodes'], [])
        with self.assertRaises(AgentError):
            validate_graph(empty, create=True)

    def test_byte_budget_refuses_complete_data_without_truncation(self):
        value = graph()
        value['nodes'] = [{**value['nodes'][0], 'id': f'n-{i}', 'note': '中' * 5000} for i in range(20)]
        value['edges'] = []
        original = copy.deepcopy(value)
        with self.assertRaises(AgentError) as caught:
            validate_graph(value)
        self.assertEqual(caught.exception.status, 413)
        self.assertEqual(value, original)
        with self.assertRaises(AgentError) as caught:
            validate_graph(graph(), base=value)
        self.assertEqual(caught.exception.status, 413)

    def test_only_unique_complete_structural_renumbering_is_provable(self):
        base = graph(); renamed = copy.deepcopy(base)
        renamed['nodes'][0]['id'] = 'renamed'
        renamed['edges'][0].update(id='new-edge', **{'from': 'renamed'})
        with self.assertRaises(AgentError) as caught:
            validate_graph(renamed, base=base)
        self.assertEqual(caught.exception.code, 'unstable_element_id')
        self.assertEqual({v['collection'] for v in caught.exception.details['changes']}, {'nodes', 'edges'})
        changed = copy.deepcopy(renamed)
        changed['nodes'][0]['x'] += 10
        # A moved/replaced element is not a provably identical full structure.
        validate_graph(changed, base=base)
        duplicated = graph(); duplicated['nodes'][1] = {**duplicated['nodes'][0], 'id': 'b'}
        duplicated['edges'] = []
        ambiguous = copy.deepcopy(duplicated); ambiguous['nodes'][1]['id'] = 'c'
        validate_graph(ambiguous, base=duplicated)
        invalid = copy.deepcopy(base); invalid['nodes'][1]['id'] = 'a'
        with self.assertRaises(AgentError) as caught:
            validate_graph(graph(), base=invalid)
        self.assertEqual(caught.exception.code, 'legacy_identity_invalid')


if __name__ == '__main__':
    unittest.main()
