"""Real HTTP/stdio boundary for project creation proposals."""

import json
import unittest

import test_agent_delete_http as http_tests
import test_agent_runtime as runtime_tests
import test_mcp_stdio as bridge_tests
from workbench.agent_file_handles import SUPPORTED
from workbench.agent_management import client_version


class ProjectManagementUninitializedTests(unittest.TestCase):
    setUp = runtime_tests.AgentManagementHTTPTests.setUp
    tearDown = runtime_tests.AgentManagementHTTPTests.tearDown
    request = runtime_tests.AgentManagementHTTPTests.request

    def test_read_access_preview_does_not_initialize_workspace(self):
        status = self.request('status')[1]
        headers = {'Origin':self.origin,'X-Workbench-Management-Token':status['management_token']}
        self.assertEqual(self.request('proposals/00000000-0000-0000-0000-000000000000/project-access/preview',headers=headers)[0],404)
        self.assertFalse((self.base / 'private').exists())
        self.assertFalse((self.repo.root / '.agent').exists())


@unittest.skipUnless(SUPPORTED, 'native project publication requires Windows')
class ProjectBridgeTests(unittest.TestCase):
    setUp = bridge_tests.MCPBridgeTests.setUp
    tearDown = bridge_tests.MCPBridgeTests.tearDown
    start_bridge = bridge_tests.MCPBridgeTests.start_bridge
    tool = bridge_tests.MCPBridgeTests.tool
    request = http_tests.DeleteBridgeHTTPTests.request

    def test_raw_bridge_project_fields_private_local_order_and_original_receipt(self):
        security = self.workbench.security
        key = self.info['client_id']
        before = security.clients()[key]
        security.manager().run('edit', {'name':before['name'],'scopes':before['scopes'],'project_ids':[],'categories':['*']},
                               key, client_version(before))
        self.start_bridge()
        self.assertEqual(len(self.rpc.call('tools/list')['tools']),22)
        prefix = '/api/local/agent-management/'
        status = self.request(prefix+'status',headers={'X-Workbench-Management':'1'})[1]
        headers = {'X-Workbench-Management':'1','X-Workbench-Management-Token':status['management_token'],'Origin':self.workbench.base_url}
        agent_headers = {'Authorization':'Bearer '+self.config['token'],'X-Workbench-Workspace':status['workspace_id']}
        route = prefix+f'clients/{key}/project-creation'
        grant = {'workspace_id':status['workspace_id'],'expected_version':client_version(security.clients()[key])}
        for bad in ({}, {**headers,**agent_headers}, {**headers,'Origin':'http://evil.test'}):
            self.assertEqual(self.request(route+'/preview','POST',grant,bad)[0],403)
        code, review = self.request(route+'/preview','POST',grant,headers)
        self.assertEqual(code,200,review)
        approval = {**grant,'preview_id':review['preview_id'],'preview_digest':review['preview_digest'],'request_id':'project-stdio-grant','approved':True}
        self.assertEqual(self.request(route+'/confirm','POST',approval,headers)[0],200)
        arguments = {'request_id':'project-stdio','kind':'project','operation':'create',
                     'content':{'name':'项目协议','description':'多行\n原文','status':'paused','color':'#4d78e8','workflow_template':'standard'}}
        result = self.tool('prepare_proposal',arguments)
        self.assertFalse(result['isError'],result)
        proposal_id = result['structuredContent']['proposal_id']
        result = self.tool('preview_proposal',{'proposal_id':proposal_id})
        preview = result['structuredContent']
        self.assertEqual(preview,json.loads(result['content'][0]['text']))
        self.assertNotIn(self.project['id'],json.dumps(preview,ensure_ascii=False))
        self.assertEqual(preview['content']['fields'],arguments['content'])
        self.assertFalse((self.workbench.repository.projects_dir / preview['target_id']).exists())
        with self.assertRaisesRegex(RuntimeError,'-32602'):
            self.tool('prepare_proposal',{**arguments,'content':{**arguments['content'],'grant_access':True}})
        self.assertEqual(self.request('/api/agent/v1/proposals','POST',
                         {**arguments,'request_id':'bad-scope','content':{**arguments['content'],'grant_access':True}},agent_headers)[0],400)
        commit = {'proposal_id':proposal_id,'version':1,'preview_digest':preview['preview_digest'],
                  'confirmation':{'mode':'agent_attested','user_confirmed':True}}
        self.assertTrue(self.tool('commit_proposal',commit)['isError'])
        code, local = self.request(prefix+f'proposals/{proposal_id}/preview',headers=headers)
        self.assertEqual(code,200,local)
        self.assertIn(self.project['id'],local['local_project_plan']['visible_before'])
        code, done = self.request(prefix+f'proposals/{proposal_id}/approve','POST',
                                  {'workspace_id':status['workspace_id'],'version':1,'preview_digest':preview['preview_digest'],
                                   'preview_ticket':local['preview_ticket'],'request_id':'project-stdio-approve'},headers)
        self.assertEqual(code,200,done)
        receipt = done['receipt']
        self.assertEqual(self.tool('commit_proposal',commit)['structuredContent'],
                         {**receipt,'web_url':self.workbench.base_url+receipt['web_path']})
        self.assertEqual(self.tool('list_projects')['structuredContent']['items'],[])
        self.assertNotIn(self.config['token'],json.dumps([review,preview,local,done])+''.join(self.rpc.errors))
