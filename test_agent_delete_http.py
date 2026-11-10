"""AG-136 actual local HTTP management and raw stdio deletion boundaries."""

import hashlib
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import test_mcp_stdio as bridge_tests
import test_agent_runtime as runtime_tests
from test_agent_deletions import delete_grants


class DeleteGrantHTTPTests(unittest.TestCase):
    setUp = runtime_tests.AgentManagementHTTPTests.setUp
    tearDown = runtime_tests.AgentManagementHTTPTests.tearDown
    request = runtime_tests.AgentManagementHTTPTests.request

    def test_uninitialized_status_does_not_create_workspace(self):
        status = self.request('status')[1]
        headers = {'Origin':self.origin, 'X-Workbench-Management-Token':status['management_token']}
        self.assertEqual(self.request('clients/00000000-0000-0000-0000-000000000000/deletions', headers=headers)[0], 409)
        self.assertFalse((self.base / 'private').exists())


class DeleteBridgeHTTPTests(unittest.TestCase):
    setUp = bridge_tests.MCPBridgeTests.setUp
    tearDown = bridge_tests.MCPBridgeTests.tearDown
    start_bridge = bridge_tests.MCPBridgeTests.start_bridge
    tool = bridge_tests.MCPBridgeTests.tool

    def request(self, route, method='GET', payload=None, headers=None):
        request = Request(self.workbench.base_url + route, method=method,
                          data=json.dumps(payload).encode('utf-8') if payload is not None else None,
                          headers={'Content-Type':'application/json', **(headers or {})})
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read().decode('utf-8'))

    def test_full_fresh_http_grant_raw_stdio_web_approval_restore_and_old_replay(self):
        repo = self.workbench.repository
        item = repo.create_record({'type':'issue', 'project_id':self.project['id'], 'title':'原始协议删除', 'body':'完整原文\n第二行'})
        path = repo.get_record(item['id'])[1]
        original = path.read_bytes()
        self.start_bridge()
        self.assertEqual(len(self.rpc.call('tools/list')['tools']), 22)
        arguments = {'request_id':'delete-before-fresh', 'kind':'issue', 'operation':'delete',
                     'target_id':item['id'], 'base_revision':hashlib.sha256(original).hexdigest()}
        self.assertTrue(self.tool('prepare_proposal', arguments)['isError'])
        prefix = '/api/local/agent-management/'
        status = self.request(prefix + 'status', headers={'X-Workbench-Management':'1'})[1]
        headers = {'Origin':self.workbench.base_url, 'X-Workbench-Management':'1', 'X-Workbench-Management-Token':status['management_token']}
        client = self.workbench.security.clients()[self.info['client_id']]
        from workbench.agent_management import client_version
        route = prefix + f"clients/{self.info['client_id']}/deletions"
        payload = {'workspace_id':status['workspace_id'], 'expected_version':client_version(client),
                   'grants':delete_grants({'type':'project', 'id':self.project['id']})}
        for invalid in ({}, {**headers, 'Origin':'http://evil.test'}, {**headers, 'Authorization':'Bearer synthetic'}, {**headers, 'Sec-Fetch-Site':'cross-site'}):
            self.assertEqual(self.request(route + '/preview', 'POST', payload, invalid)[0], 403)
        before = {str(p):p.read_bytes() for directory in (repo.root, self.workbench.security.config_dir) for p in directory.rglob('*.json')}
        code, grant_preview = self.request(route + '/preview', 'POST', payload, headers)
        self.assertEqual(code, 200, grant_preview)
        self.assertEqual(before, {str(p):p.read_bytes() for directory in (repo.root, self.workbench.security.config_dir) for p in directory.rglob('*.json')})
        approval = {key:grant_preview[key] for key in ('workspace_id', 'expected_version', 'preview_id', 'preview_digest')}
        approval.update(request_id='delete-http-fresh', approved=True)
        self.assertEqual(self.request(route + '/confirm', 'POST', {**approval, 'approved':False}, headers)[0], 400)
        code, granted = self.request(route + '/confirm', 'POST', approval, headers)
        self.assertEqual(code, 200, granted)
        self.assertEqual(self.workbench.security.registry_version(), 5)
        self.assertEqual(self.workbench.security.clients()[self.info['client_id']]['authorization_schema_version'], 6)
        prepared = self.tool('prepare_proposal', {**arguments, 'request_id':'delete-http-ready'})
        self.assertFalse(prepared['isError'], prepared)
        proposal_id = prepared['structuredContent']['proposal_id']
        result = self.tool('preview_proposal', {'proposal_id':proposal_id})
        preview = result['structuredContent']
        self.assertEqual(preview, json.loads(result['content'][0]['text']))
        self.assertEqual(preview['content']['target']['raw_source'].encode('utf-8'), original)
        commit = {'proposal_id':proposal_id, 'version':1, 'preview_digest':preview['preview_digest'],
                  'confirmation':{'mode':'agent_attested', 'user_confirmed':True}}
        self.assertTrue(self.tool('commit_proposal', commit)['isError'])
        with self.assertRaisesRegex(RuntimeError, '-32602'):
            self.tool('prepare_proposal', {**arguments, 'held_source':{}})
        agent_headers = {'Authorization':'Bearer ' + self.config['token'], 'X-Workbench-Workspace':status['workspace_id']}
        self.assertEqual(self.request('/api/agent/v1/proposals', 'POST', {**arguments, 'held_source':{}}, agent_headers)[0], 400)
        code, review = self.request(prefix + f'proposals/{proposal_id}/preview', headers=headers)
        self.assertEqual(code, 200, review)
        code, completed = self.request(prefix + f'proposals/{proposal_id}/approve', 'POST',
                                      {'workspace_id':status['workspace_id'], 'version':1, 'preview_digest':preview['preview_digest'],
                                       'preview_ticket':review['preview_ticket'], 'request_id':'delete-http-business'}, headers)
        self.assertEqual(code, 200, completed)
        receipt = completed['receipt']
        self.assertFalse(path.exists())
        self.assertEqual((repo.trash_dir / receipt['trash_token']).read_bytes(), original)
        self.assertEqual(self.request('/api/trash/' + receipt['trash_token'] + '/restore', 'POST', {})[0], 200)
        self.assertEqual(path.read_bytes(), original)
        replay = self.tool('commit_proposal', commit)['structuredContent']
        self.assertEqual(replay, {**receipt, 'web_url':self.workbench.base_url + receipt['web_path']})
        self.assertEqual(path.read_bytes(), original)
        self.assertNotIn(self.config['token'], json.dumps([preview, completed]) + '\n'.join(self.rpc.errors))


if __name__ == '__main__':
    unittest.main()
