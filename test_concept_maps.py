import hashlib
import json
import subprocess
import sys
import threading
from unittest.mock import patch

import tempfile
import unittest
from pathlib import Path

import server
from server import Repository
from workbench.concept_maps import CONCEPT_MAP_HEIGHT, CONCEPT_MAP_WIDTH, ConceptMapRepository


class ConceptMapRepositoryTests(unittest.TestCase):
    def test_repository_facade_uses_extracted_concept_map_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory))
            created = repo.create_concept_map({"title": "模块边界"})

            self.assertIsInstance(repo._concept_map_repository, ConceptMapRepository)
            self.assertEqual(repo._concept_map_repository.get(created["id"])[0], repo.get_concept_map(created["id"])[0])
            self.assertEqual(server.CONCEPT_MAP_WIDTH, CONCEPT_MAP_WIDTH)
            self.assertEqual(server.CONCEPT_MAP_HEIGHT, CONCEPT_MAP_HEIGHT)

    def test_update_is_atomically_persisted_and_reloaded(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            repo = Repository(data_dir)
            created = repo.create_concept_map({"title": "原子写入"})
            repo.update_concept_map(created["id"], {
                "viewport": {"x": 12, "y": -8, "zoom": 1.4},
                "nodes": [{"id": "stable-node", "text": "稳定节点", "x": 10, "y": 20}],
            })

            self.assertEqual(list(repo.concept_maps_dir.glob("*.tmp")), [])
            reloaded = Repository(data_dir).get_concept_map(created["id"])[0]
            self.assertEqual(reloaded["nodes"][0]["id"], "stable-node")
            self.assertEqual(reloaded["viewport"], {"x": 12.0, "y": -8.0, "zoom": 1.4})


class ConceptMapVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = Repository(self.root)
        self.item = self.repo.create_concept_map({'title':'版本图', 'nodes':[{'id':'a','text':'甲'}, {'id':'b','type':'linking_phrase','text':'关系'}], 'edges':[{'id':'e','from':'a','to':'b','arrowhead':'none'}]})
        self.id = self.item['id']
        self.path = self.root / 'concept-maps' / f'{self.id}.json'

    def tearDown(self):
        self.temp.cleanup()

    def test_bytes_revision_read_only_and_legacy_update(self):
        raw = self.path.read_bytes()
        self.assertEqual(self.item['revision'], hashlib.sha256(raw).hexdigest())
        self.assertNotIn('revision', json.loads(raw))
        self.assertFalse((self.root/'history'/self.id).exists())
        self.repo.get_concept_map(self.id); self.repo.list_concept_maps(); self.repo.list_concept_map_history(self.id)
        self.assertFalse((self.root/'history'/self.id).exists())
        self.assertEqual(self.repo.list_concept_maps()[0]['revision'], self.item['revision'])
        after = self.repo.update_concept_map(self.id, {'title':'旧Python调用'})
        self.assertEqual(Repository(self.root).get_concept_map(self.id)[0], after)
        version = self.repo.list_concept_map_history(self.id)[0]['version']
        self.assertEqual((self.root/'history'/self.id/f'{version}.json').read_bytes(), raw)
        self.assertNotEqual(after['revision'], self.item['revision'])

    def test_prepare_external_conflict_and_raw_history_restore(self):
        # Preserve noncanonical formatting in snapshots; hash exact disk bytes.
        old = json.loads(self.path.read_bytes()); old['custom'] = {'keep':True}
        raw = ('  '+json.dumps(old,ensure_ascii=False)+'\n').encode('utf-8');self.path.write_bytes(raw)
        current = self.repo.get_concept_map(self.id)[0]
        prepared = self.repo.prepare_concept_map_update(self.id, {'title':'准备', 'expected_revision':current['revision']})
        self.path.write_bytes(raw+b' ')
        with self.assertRaises(FileExistsError): self.repo.apply_concept_map_write(prepared)
        self.assertEqual(self.repo.list_concept_map_history(self.id), [])
        self.path.write_bytes(raw)
        updated = self.repo.apply_concept_map_write(prepared)
        versions = self.repo.list_concept_map_history(self.id)
        snapshot = self.repo.get_concept_map_history(self.id, versions[0]['version'])
        self.assertEqual(snapshot['custom'], {'keep':True})
        restored = self.repo.restore_concept_map_history(self.id, versions[0]['version'], {'expected_revision':updated['revision']})
        self.assertEqual(restored['title'], '版本图');self.assertEqual(restored['custom'], {'keep':True})
        self.assertEqual([n['id'] for n in restored['nodes']], ['a','b'])
        self.assertEqual(restored['edges'][0]['arrowhead'],'none')
        self.assertEqual(len(self.repo.list_concept_map_history(self.id)),2)

    def test_concurrent_cas_has_one_winner_and_no_stale_history(self):
        barrier = threading.Barrier(3); results=[]
        def write(title):
            barrier.wait()
            try: self.repo.update_concept_map(self.id, {'title':title,'expected_revision':self.item['revision']});results.append('ok')
            except FileExistsError: results.append('conflict')
        threads=[threading.Thread(target=write,args=(str(i),)) for i in range(2)]
        for t in threads:t.start()
        barrier.wait()
        for t in threads:t.join(5);self.assertFalse(t.is_alive())
        self.assertCountEqual(results,['ok','conflict'])
        self.assertEqual(len(self.repo.list_concept_map_history(self.id)),1)
        with self.assertRaises(FileExistsError):self.repo.update_concept_map(self.id,{'expected_revision':self.item['revision']})

    def test_history_failure_target_failure_and_post_replace_failure(self):
        prepared=self.repo.prepare_concept_map_update(self.id,{'title':'后图'})
        raw=self.path.read_bytes()
        with patch('workbench.concept_maps.save_concept_map_snapshot',side_effect=OSError('history disk full')):
            with self.assertRaises(OSError):self.repo.apply_concept_map_write(prepared)
        self.assertEqual(self.path.read_bytes(),raw)
        with patch('workbench.concept_maps.atomic_write_bytes',side_effect=OSError('target disk full')):
            with self.assertRaises(OSError):self.repo.apply_concept_map_write(prepared)
        self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual(len(self.repo.list_concept_map_history(self.id)),1)
        def fail(stage):
            if stage=='target':raise OSError('response interrupted after replace')
        with self.assertRaises(OSError):self.repo.apply_concept_map_write(prepared,fail)
        self.assertEqual(Repository(self.root).get_concept_map(self.id)[0]['revision'],hashlib.sha256(prepared.after).hexdigest())
        with self.assertRaises(FileExistsError):self.repo.apply_concept_map_write(prepared)
        self.assertEqual(len(self.repo.list_concept_map_history(self.id)),1)

    def test_real_exit_history_and_target_no_automatic_replay(self):
        for stage in ('history','target'):
            with self.subTest(stage=stage):
                raw=self.path.read_bytes()
                code="""import os,sys
from pathlib import Path
from server import Repository
r=Repository(Path(sys.argv[1]));p=r.prepare_concept_map_update(sys.argv[2],{'title':sys.argv[3]})
r.apply_concept_map_write(p,lambda stage:os._exit(73) if stage==sys.argv[4] else None)
"""
                result=subprocess.run([sys.executable,'-c',code,str(self.root),self.id,stage,stage],capture_output=True,timeout=20)
                self.assertEqual(result.returncode,73,result.stderr)
                after=Repository(self.root).get_concept_map(self.id)[0]
                self.assertEqual(after['title'],'版本图' if stage=='history' else 'target')
                self.assertEqual(any(p.read_bytes()==raw for p in (self.root/'history'/self.id).glob('*.json')),True)
                stable=self.path.read_bytes();Repository(self.root);self.assertEqual(self.path.read_bytes(),stable)

    def test_legacy_supported_and_future_unknown_evidence_preserved(self):
        legacy=json.loads(self.path.read_bytes());legacy.pop('version');legacy['extra']='保留'
        self.path.write_text(json.dumps(legacy),encoding='utf-8')
        after=self.repo.update_concept_map(self.id,{'focus_question':'旧图'})
        self.assertEqual(after['version'],2);self.assertEqual(after['extra'],'保留')
        future={**legacy,'version':999};self.path.write_text(json.dumps(future),encoding='utf-8');raw=self.path.read_bytes()
        with self.assertRaises(ValueError):self.repo.update_concept_map(self.id,{'title':'不能降级'})
        self.assertEqual(self.path.read_bytes(),raw)
        directory=self.root/'history'/self.id
        unknown=directory/'20990101-000000-000000-deadbeef.json';unknown.write_bytes(raw)
        damaged=directory/'20990102-000000-000000-deadbeef.json';damaged.write_text('{broken',encoding='utf-8')
        entries=self.repo.list_concept_map_history(self.id)
        self.assertEqual(sum(not v['available'] for v in entries),2)
        for version in (unknown.stem,damaged.stem,'../../other'):
            with self.assertRaises(ValueError):self.repo.restore_concept_map_history(self.id,version,{'expected_revision':after['revision']})
        self.assertEqual(unknown.read_bytes(),raw);self.assertEqual(damaged.read_text(),'{broken')

    def test_category_trash_export_and_old_canvas_conflict(self):
        after=self.repo.update_concept_map(self.id,{'category':'原分类'})
        self.repo.rename_concept_map_category('原分类','新分类')
        with self.assertRaises(FileExistsError):self.repo.update_concept_map(self.id,{'title':'旧页面','expected_revision':after['revision']})
        self.repo.delete_concept_map_category('新分类')
        self.assertEqual(len(self.repo.list_concept_map_history(self.id)),3)
        entry=self.repo.delete_concept_map(self.id)
        self.repo.restore_trash(entry['token'])
        current=Repository(self.root).get_concept_map(self.id)[0]
        self.assertEqual(current['category'],'未分类')
        import io,zipfile
        with zipfile.ZipFile(io.BytesIO(self.repo.export_zip())) as z:
            data=json.loads(z.read(f'concept-maps/{self.id}.json'))
            self.assertNotIn('revision',data);self.assertEqual(data['version'],2)

    def test_external_write_during_history_does_not_get_overwritten(self):
        prepared=self.repo.prepare_concept_map_update(self.id,{'title':'候选'})
        original=self.path.read_bytes()
        def edit(stage):
            if stage=='history':self.path.write_bytes(original+b' ')
        with self.assertRaises(FileExistsError):self.repo.apply_concept_map_write(prepared,edit)
        self.assertEqual(self.path.read_bytes(),original+b' ')
        self.assertEqual((self.root/'history'/self.id/f'{prepared.history_version}.json').read_bytes(),original)

    def test_partial_category_failure_reports_error_and_keeps_each_graph_history(self):
        self.repo.update_concept_map(self.id,{'category':'批量'})
        other=self.repo.create_concept_map({'title':'第二张','category':'批量'})
        domain=self.repo._concept_map_repository;original=domain.update;calls=[]
        def fail_second(map_id,payload):
            calls.append(map_id)
            if len(calls)==2:raise OSError('second graph failed')
            return original(map_id,payload)
        with patch.object(domain,'update',side_effect=fail_second):
            with self.assertRaises(OSError):self.repo.rename_concept_map_category('批量','迁移')
        self.assertEqual(len(calls),2)
        cats=[self.repo.get_concept_map(i)[0]['category'] for i in (self.id,other['id'])]
        self.assertCountEqual(cats,['批量','迁移'])
        self.assertEqual(len(self.repo.list_concept_map_history(calls[0]))>=1,True)
        # Retry migrates only the remaining graph; no claim of a multi-file transaction.
        self.repo.rename_concept_map_category('批量','继续')
        self.assertNotIn('批量',[self.repo.get_concept_map(i)[0]['category'] for i in (self.id,other['id'])])

    def test_invalid_payload_limits_and_supported_normalization_unchanged(self):
        before=self.path.read_bytes()
        for payload in ({'nodes':[{}]*501},{'edges':[{}]*1001},{'title':''},{'expected_revision':'no'},{'nodes':{}},{'version':999},[]):
            with self.assertRaises(ValueError):self.repo.update_concept_map(self.id,payload)
            self.assertEqual(self.path.read_bytes(),before)
        after=self.repo.update_concept_map(self.id,{'nodes':[{'id':'dup','text':'x'*600,'x':999999,'color':'bad','width':9999},{'id':'dup','type':'unknown','font_size':999}], 'viewport':{'zoom':999}})
        self.assertEqual([n['id'] for n in after['nodes']],['dup','node-2'])
        self.assertEqual(len(after['nodes'][0]['text']),500);self.assertEqual(after['nodes'][0]['width'],420)
        self.assertEqual(after['nodes'][0]['color'],'#ffffff');self.assertEqual(after['nodes'][0]['x'],0)
        self.assertEqual(after['nodes'][1]['type'],'concept');self.assertEqual(after['viewport']['zoom'],3)


import test_http

class ConceptMapHTTPVersionTests(unittest.TestCase):
    setUp = test_http.HTTPIntegrationTests.setUp
    tearDown = test_http.HTTPIntegrationTests.tearDown
    request = test_http.HTTPIntegrationTests.request
    request_json = test_http.HTTPIntegrationTests.request_json

    def test_cas_upgrade_history_restore_and_missing_resource(self):
        status,_,item=self.request_json('POST','/api/concept-maps',{'title':'HTTP图'})
        self.assertEqual(status,201)
        endpoint=f"/api/concept-maps/{item['id']}"
        for payload in ({'title':'旧缓存'}, {'title':'null','expected_revision':None}):
            status,_,error=self.request_json('PATCH',endpoint,payload)
            self.assertEqual(status,409);self.assertIn('刷新',error['error'])
        status,_,updated=self.request_json('PATCH',endpoint,{'title':'更新','expected_revision':item['revision']})
        self.assertEqual(status,200)
        self.assertEqual(self.request_json('PATCH',endpoint,{'title':'旧版本','expected_revision':item['revision']})[0],409)
        status,_,history=self.request_json('GET',endpoint+'/history');self.assertEqual(status,200)
        version=history[0]['version']
        self.assertEqual(self.request_json('POST',endpoint+f'/history/{version}/restore',{})[0],409)
        self.assertEqual(self.request_json('POST',endpoint+f'/history/{version}/restore',{'expected_revision':item['revision']})[0],409)
        status,_,restored=self.request_json('POST',endpoint+f'/history/{version}/restore',{'expected_revision':updated['revision']})
        self.assertEqual(status,200);self.assertEqual(restored['title'],item['title'])
        self.assertEqual(self.request_json('GET',endpoint+'/history/20000101-000000-000000')[0],404)
        self.assertEqual(self.request_json('PATCH',endpoint,{'title':'bad','expected_revision':'bad'})[0],400)


if __name__ == "__main__":
    unittest.main()
