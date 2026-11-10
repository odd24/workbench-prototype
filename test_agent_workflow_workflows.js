const assert = require('node:assert/strict');
const http = require('node:http');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {DevToolsClient, freePort, browserExecutable, waitForHttp, waitForPage, delay} = require('./test_editor_workflows.js');

async function main() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-workflow-browser-'));
  const shots = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-workflow-shots-'));
  const port = await freePort(), debugPort = await freePort(), origin = `http://127.0.0.1:${port}`;
  const credentials = path.join(base,'credentials');
  const server = spawn(process.env.PYTHON || 'python', ['server.py','--data-dir',path.join(base,'data'),
    '--agent-config-dir',credentials,'--enable-agent','--port',String(port)], {cwd:__dirname,stdio:'ignore',windowsHide:true});
  let browser, client;
  try {
    await waitForHttp(origin + '/api/health');
    async function json(route, {method='GET', headers={}, body, expected} = {}) {
      const response = await fetch(origin + route, {method, headers:{Origin:origin,'Content-Type':'application/json',...headers},
        ...(body === undefined ? {} : {body:JSON.stringify(body)})});
      const value = await response.json();
      assert.ok(expected ? response.status === expected : response.ok,`${route}: ${response.status} ${JSON.stringify(value)}`);
      return value;
    }
    const status = await json('/api/local/agent-management/status',{headers:{'X-Workbench-Management':'1'}});
    const manage = (route,method,body) => json('/api/local/agent-management/' + route,{method,body,
      headers:{'X-Workbench-Management':'1','X-Workbench-Management-Token':status.management_token}});
    const config = await json('/api/config');
    const template = {id:'browser-template',name:'验收自定义流程',statuses:config.workflow_templates[0].statuses};
    await json('/api/workflow-templates',{method:'PUT',body:{templates:[]},expected:400});
    await json('/api/workflow-templates',{method:'PUT',body:[false],expected:400});
    await json('/api/projects',{method:'POST',body:[],expected:400});
    const oversize = await new Promise((resolve,reject) => {
      const request = http.request(origin + '/api/workflow-templates', {method:'PUT',
        headers:{Origin:origin,'Content-Type':'application/json','Content-Length':'15000001'}}, response => {
        response.resume();
        resolve(response.statusCode);
      });
      request.on('error',reject);
      request.end();
    });
    assert.equal(oversize,400);
    await json('/api/workflow-templates',{method:'PUT',body:[...config.workflow_templates, template]});
    const project = await json('/api/projects',{method:'POST',body:{name:'工作流项目 #&',workflow_template:template.id}});
    const route = '/api/projects/' + encodeURIComponent(project.id);
    const todo = await json('/api/records',{method:'POST',body:{title:'待办迁移',type:'todo',project_id:project.id,status:'进行中',
      body:'<script>window.__workflowXss = true</script>\n' + '完整中文正文。'.repeat(100)}});
    const recordRoute = '/api/records/' + todo.id;
    const invalidRemoval = {...template,statuses:{...template.statuses,todo:template.statuses.todo.filter(item => item.id !== 'doing')}};
    assert.equal((await json('/api/workflow-templates',{method:'PUT',body:[...config.workflow_templates,invalidRemoval],expected:409})).code,'mapping_required');
    const implicitRename = {...template,statuses:{...template.statuses,todo:template.statuses.todo.map(item => item.id === 'doing' ? {...item,name:'旧请求不可直接改名'} : item)}};
    assert.equal((await json('/api/workflow-templates',{method:'PUT',body:[...config.workflow_templates,implicitRename],expected:409})).code,'workflow_preview_required');
    assert.equal((await json(recordRoute)).revision,todo.revision);
    await json(route,{method:'PATCH',body:{mixed_status_order:['进行中','已完成'],mixed_status_record_sorts:{'进行中':'title','已完成':'manual'}}});
    assert.equal((await json(route,{method:'PATCH',body:{workflow_template:'standard'},expected:409})).code,'workflow_preview_required');
    const added = await manage('clients','POST',{workspace_id:status.workspace_id,request_id:'workflow-browser-client',
      name:'工作流浏览器客户端',scopes:['read','propose','commit'],kinds:['issue','todo'],project_ids:[project.id],categories:[]});
    const token = JSON.parse(fs.readFileSync(path.join(credentials,status.workspace_id,added.client_id + '.json'),'utf8')).token;
    const agent = (route, method, body) => json('/api/agent/v1/' + route,{method,body,
      headers:{Authorization:`Bearer ${token}`,'X-Workbench-Workspace':status.workspace_id}});
    browser = spawn(browserExecutable(),['--headless','--disable-gpu','--no-first-run','--disable-extensions','--disable-background-networking',
      '--disable-sync',`--remote-debugging-port=${debugPort}`,`--user-data-dir=${path.join(base,'profile')}`,origin],{stdio:'ignore',windowsHide:true});
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(response => response.json());
    client = new DevToolsClient(pages.find(page => page.type === 'page' && page.url.startsWith(origin)).webSocketDebuggerUrl);
    await client.connect();
    await client.call('Page.enable');
    await client.call('Runtime.enable');
    await waitForPage(client,'apiAvailable && projects.length > 0');
    await client.evaluate('applicationFeature.start().then(() => true)');
    const element = selector => `document.querySelector(${JSON.stringify(selector)})`;
    const click = selector => client.evaluate(`${element(selector)}.click()`);
    const confirm = async () => { await waitForPage(client,"$('#appDialog').open"); await click('#appDialogConfirm'); };
    async function screenshot(name, selector) {
      for (const theme of ['light','dark']) for (const width of [1440,390]) {
        await client.call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); ${element(selector)}.scrollIntoView({block:'center'});`);
        await waitForPage(client,`Math.abs(document.querySelector('.main').getBoundingClientRect().left - ${width <= 760 ? 0 : 244}) < 1`);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'),false);
        const image = await client.call('Page.captureScreenshot',{format:'png'});
        fs.writeFileSync(path.join(shots,`${name}-${theme}-${width}.png`),Buffer.from(image.data,'base64'));
      }
      await client.call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    }
    await client.evaluate("setPage('agent_settings').then(() => true)");
    const grant = `[data-agent-action=project-creation-workflow][data-client-id="${added.client_id}"]`;
    await waitForPage(client,`!!${element(grant)} && !agentSettingsFeature.isBusy()`);
    await click(grant);
    await waitForPage(client,"!!$('#agentWorkflowGrantPanel fieldset') && !agentSettingsFeature.isBusy()");
    await client.evaluate("$('#agentWorkflowOperation').value='delete_status'; $('#agentWorkflowTemplate').value='browser-template'; $('#agentWorkflowKind').value='todo';");
    await click('[data-agent-action=project-creation-preview]');
    await waitForPage(client,"!!$('#agentProjectCreationFull') && !agentSettingsFeature.isBusy()");
    assert.equal(await client.evaluate("$('#agentProjectCreationFull').textContent.includes('当前和以后合法状态')"),true);
    await screenshot('grant','#agentProjectCreationFull');
    await click('[data-agent-action=project-creation-confirm]');
    await confirm();
    await waitForPage(client,"!!$('#agentWorkflowGrantPanel [data-agent-action=project-creation-revoke]') && !agentSettingsFeature.isBusy()");
    const selection = {template_id:template.id,record_type:'todo',status_id:'doing'};
    const proposal = await agent('proposals','POST',{request_id:'browser-workflow-remap',kind:'workflow',operation:'delete_status',content:selection});
    assert.equal(proposal.normalized_content.unmapped[0].record_id,todo.id);
    await client.evaluate("setPage('agent_proposals').then(() => true)");
    const review = `[data-proposal-action=review][data-proposal-id="${proposal.proposal_id}"]`;
    await waitForPage(client,`!!${element(review)}`);
    await click(review);
    await waitForPage(client,"!!document.querySelector('[data-workflow-impact]')");
    assert.equal(await client.evaluate("document.querySelector('[data-proposal-action=approve]').disabled"),true);
    await agent('proposals/' + proposal.proposal_id,'PATCH',{expected_version:1,content:{...selection,target_status_id:'done'}});
    await click('#proposalPreviewDialog [data-proposal-action=review]');
    await waitForPage(client,"!!document.querySelector('[data-workflow-local-plan]') && !document.querySelector('[data-proposal-action=approve]').disabled");
    assert.equal(await client.evaluate('Boolean(window.__workflowXss)'),false);
    await screenshot('proposal','[data-workflow-local-plan]');
    await click('[data-proposal-action=approve]');
    await waitForPage(client,"$('#appDialog').open");
    await click('#appDialog button[value=cancel]');
    await waitForPage(client,"!$('#appDialog').open && !agentProposalsFeature.isBusy()");
    assert.equal((await json(recordRoute)).status,'进行中');
    await click('[data-proposal-action=approve]');
    await confirm();
    await waitForPage(client,"!$('#appDialog').open && !agentProposalsFeature.isBusy()");
    const current = await json(recordRoute);
    assert.equal(current.status,'已完成');
    assert.equal(current.completed,true);
    const history = await json(recordRoute + '/history');
    const restore = {version:history[0].version,expected_revision:current.revision};
    assert.equal((await json(recordRoute + '/restore',{method:'POST',body:restore,expected:409})).code,'history_workflow_resolution_required');
    assert.equal((await json(recordRoute + '/restore',{method:'POST',body:{...restore,status_resolution:{mode:'keep_current'}}})).status,'已完成');
    await client.evaluate(`selectedProjectId=${JSON.stringify(project.id)}; setPage('project').then(() => true)`);
    await waitForPage(client,"!!$('#editProject')");
    await click('#editProject');
    await client.evaluate("$('#projectWorkflow').value='standard'");
    await click('#saveProjectEdit');
    await waitForPage(client,"$('#appDialog').open && $('#appDialogDetail').textContent.includes('template_after')");
    await confirm();
    await waitForPage(client,"!$('#appDialog').open && !$('#projectEditDialog').open");
    assert.equal((await json('/api/projects')).find(item => item.id === project.id).workflow_template,'standard');
    await client.evaluate("selectedWorkflowId='standard'; setPage('status_templates').then(() => true)");
    const remove = '[data-template-type=todo] [data-status-id=done] .remove-status';
    await waitForPage(client,`!!${element(remove)}`);
    await click(remove);
    await waitForPage(client,"$('#appDialog').open && $('#appDialogTitle').textContent === '需要选择状态映射'");
    await confirm();
    await waitForPage(client,"!!document.querySelector('[data-app-dialog-choice=doing]')");
    await click('[data-app-dialog-choice=doing]');
    await waitForPage(client,"$('#appDialog').open && $('#appDialogTitle').textContent === '删除状态并迁移'");
    await screenshot('ordinary','#appDialogDetail');
    await confirm();
    await waitForPage(client,`!$('#appDialog').open && !${element(remove)}`);
    const migrated = await json(recordRoute);
    assert.deepEqual([migrated.status,migrated.completed], ['进行中',false]);
    console.log('AG-140 browser passed: exact grant, complete mapping, disabled approval, cancellation, terminal state, history choice, ordinary switch and ordinary explicit deletion mapping.');
    console.log(`Screenshots: ${shots}`);
  } catch (error) {
    if (client) console.error('Workflow browser state:',await client.evaluate(
      "({page:currentPage, settings:$('#agentFeedback')?.textContent, proposal:$('#proposalFeedback')?.textContent, toast:$('#toast')?.textContent})").catch(() => null));
    throw error;
  } finally {
    client?.close(); browser?.kill(); server.kill(); await delay(200);
    assert.ok(path.resolve(base).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(base,{recursive:true,force:true,maxRetries:5,retryDelay:200});
  }
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
