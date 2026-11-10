const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {DevToolsClient, freePort, browserExecutable, waitForHttp, waitForPage, delay} = require('./test_editor_workflows.js');

async function main() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-project-create-'));
  const shots = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-project-create-shots-'));
  const data = path.join(base,'data'), credentials = path.join(base,'credentials');
  const port = await freePort(), debugPort = await freePort(), origin = `http://127.0.0.1:${port}`;
  const server = childProcess.spawn(process.env.PYTHON || 'python', ['server.py','--data-dir',data,'--agent-config-dir',credentials,'--seed-demo','--enable-agent','--port',String(port)], {cwd:__dirname,stdio:'ignore',windowsHide:true});
  let browser, client;
  try {
    await waitForHttp(origin + '/api/health');
    async function json(route, options = {}) {
      const response = await fetch(origin + route,{...options,headers:{'Content-Type':'application/json',...options.headers}});
      const value = await response.json();
      assert.ok(response.ok,`${route}: ${response.status} ${JSON.stringify(value)}`);
      return value;
    }
    const localStatus = await json('/api/local/agent-management/status',{headers:{'X-Workbench-Management':'1'}});
    const headers = {'X-Workbench-Management':'1','X-Workbench-Management-Token':localStatus.management_token,Origin:origin};
    const manage = (route, method = 'GET', body) => json('/api/local/agent-management/' + route,{method,headers,...(body ? {body:JSON.stringify(body)} : {})});
    const originalProjects = await json('/api/projects');
    const created = await manage('clients','POST',{workspace_id:localStatus.workspace_id,request_id:'project-browser-client',
      name:'项目创建与单独访问授权客户端'.repeat(3),scopes:['read','propose','commit'],kinds:['issue','document'],
      project_ids:[originalProjects[0].id],categories:[],minimum_confirmation_mode:'agent_attested'});
    const config = JSON.parse(fs.readFileSync(path.join(credentials,localStatus.workspace_id,`${created.client_id}.json`),'utf8'));
    const agentHeaders = {Authorization:`Bearer ${config.token}`,'X-Workbench-Workspace':localStatus.workspace_id};
    const agent = (route, method = 'GET', body) => json('/api/agent/v1/' + route,{method,headers:agentHeaders,...(body ? {body:JSON.stringify(body)} : {})});
    browser = childProcess.spawn(browserExecutable(),['--headless','--disable-gpu','--no-first-run','--disable-extensions','--disable-background-networking','--disable-sync',`--remote-debugging-port=${debugPort}`,`--user-data-dir=${path.join(base,'profile')}`,origin],{stdio:'ignore',windowsHide:true});
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(response => response.json());
    client = new DevToolsClient(pages.find(page => page.type === 'page' && page.url.startsWith(origin)).webSocketDebuggerUrl);
    await client.connect(); await client.call('Page.enable'); await client.call('Runtime.enable');
    await waitForPage(client, 'apiAvailable && projects.length > 0');
    await client.evaluate('applicationFeature.start().then(() => true)');
    const click = selector => client.evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    const confirm = async () => { await waitForPage(client,"$('#appDialog').open"); await click('#appDialogConfirm'); };
    async function screenshot(name, selector) {
      for (const theme of ['light','dark']) for (const width of [1440,390]) {
        await client.call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark',${theme === 'dark'}); document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center'});`);
        await waitForPage(client,`Math.abs(document.querySelector('.main').getBoundingClientRect().left - ${width <= 760 ? 0 : 244}) < 1`);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'),false);
        fs.writeFileSync(path.join(shots,`${name}-${theme}-${width}.png`),Buffer.from((await client.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
      }
      await client.call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    }
    await client.evaluate("setPage('agent_settings').then(() => true)");
    const grantButton = `[data-agent-action=project-creation-open][data-client-id="${created.client_id}"]`;
    await waitForPage(client,`!!document.querySelector(${JSON.stringify(grantButton)}) && !agentSettingsFeature.isBusy()`);
    await click(grantButton);
    await waitForPage(client,"!!$('#agentProjectCreationPanel') && !agentSettingsFeature.isBusy()");
    await click('[data-agent-action=project-creation-preview]');
    await waitForPage(client,"!!$('#agentProjectCreationFull') && !agentSettingsFeature.isBusy()");
    await screenshot('grant','#agentProjectCreationFull');
    await click('[data-agent-action=project-creation-cancel]');
    const route = `clients/${created.client_id}/project-creation`;
    assert.equal((await manage(route)).grant.enabled,false);
    await click('[data-agent-action=project-creation-preview]');
    await waitForPage(client,"!!$('#agentProjectCreationFull') && !agentSettingsFeature.isBusy()");
    await click('[data-agent-action=project-creation-confirm]'); await confirm();
    await waitForPage(client,"!!document.querySelector('[data-agent-action=project-creation-revoke]') && !agentSettingsFeature.isBusy()");
    assert.equal((await manage(route)).grant.enabled,true);
    assert.deepEqual((await agent('capabilities')).kind_operations.project,['create']);
    const proposal = await agent('proposals','POST',{request_id:'project-browser-proposal',kind:'project',operation:'create',
      content:{name:'浏览器验证项目',description:'完整多行项目说明\n<script>window.__projectXss=true</script>\n' + '长中文项目说明。'.repeat(50),status:'paused'}});
    const preview = await agent(`proposals/${proposal.proposal_id}/preview`);
    assert.ok(!JSON.stringify(preview).includes(originalProjects[0].id));
    const target = path.join(data,'projects',proposal.target_id);
    assert.equal(fs.existsSync(target),false);
    await client.evaluate("setPage('agent_proposals').then(() => true)");
    const review = `[data-proposal-action=review][data-proposal-id="${proposal.proposal_id}"]`;
    await waitForPage(client,`!!document.querySelector(${JSON.stringify(review)})`);
    await click(review);
    await waitForPage(client,"!!document.querySelector('[data-project-order]') && !document.querySelector('[data-proposal-action=approve]').disabled");
    assert.equal(await client.evaluate('!!window.__projectXss'),false);
    await screenshot('project','[data-project-order]');
    await click('[data-proposal-action=approve]');
    await waitForPage(client,"$('#appDialog').open");
    await click('#appDialog button[value=cancel]');
    await waitForPage(client,"!$('#appDialog').open && !agentProposalsFeature.isBusy()");
    assert.equal(fs.existsSync(target),false);
    await click('[data-project-access-after]');
    await click('[data-proposal-action=approve]'); await confirm();
    await waitForPage(client,"!!document.querySelector('[data-project-access-full]') && !agentProposalsFeature.isBusy()");
    assert.equal(fs.existsSync(path.join(target,'README.md')),true);
    assert.deepEqual((await agent('projects')).items.map(p=>p.id),[originalProjects[0].id]);
    const completed = await agent(`proposals/${proposal.proposal_id}`);
    assert.equal(completed.receipt.item_id,proposal.target_id);
    await screenshot('access','[data-project-access-full]');
    await click('[data-proposal-action=project-access-approve]');
    await waitForPage(client,"$('#appDialog').open");
    await click('#appDialog button[value=cancel]');
    await waitForPage(client,"!$('#appDialog').open && !agentProposalsFeature.isBusy()");
    assert.deepEqual((await agent('projects')).items.map(p=>p.id),[originalProjects[0].id]);
    await client.evaluate('window.__ag137BeforeReload = true');
    await client.call('Page.reload',{ignoreCache:true});
    await waitForPage(client,`window.__ag137BeforeReload !== true && document.readyState === 'complete' && currentPage === 'agent_proposals' && !!document.querySelector(${JSON.stringify(review)})`);
    await click(review);
    await waitForPage(client,"!!document.querySelector('[data-proposal-project-result]') && !agentProposalsFeature.isBusy()");
    await click('[data-proposal-action=project-access-preview]');
    await waitForPage(client,"!!document.querySelector('[data-project-access-full]') && !agentProposalsFeature.isBusy()");
    await client.evaluate(`window.__projectGrantStatus = null; window.__projectGrantFetch = window.fetch; window.fetch = async (...args) => { const response = await window.__projectGrantFetch(...args); if (String(args[0]).endsWith('/${proposal.proposal_id}/project-access/confirm') && args[1]?.method === 'POST') { await response.clone().json(); window.__projectGrantStatus = response.status; window.fetch = window.__projectGrantFetch; throw new Error('synthetic access response loss'); } return response; };`);
    await click('[data-proposal-action=project-access-approve]'); await confirm();
    await waitForPage(client,"window.__projectGrantStatus === 200 && [...document.querySelectorAll('[data-proposal-action=resolve]')].some(node => !node.disabled) && agentProposalsFeature.isBusy()");
    await click('#proposalPreviewDialog [data-proposal-action=resolve]');
    await waitForPage(client,"$('#proposalFeedback').textContent === '已查到独立项目访问授权回执。' && !agentProposalsFeature.isBusy()");
    const after = await agent('projects');
    assert.deepEqual(new Set(after.items.map(p=>p.id)),new Set([originalProjects[0].id,proposal.target_id]));
    assert.deepEqual((await agent(`proposals/${proposal.proposal_id}`)).receipt,completed.receipt);
    await click('[data-proposal-project-result]');
    await waitForPage(client,`currentPage === 'project' && selectedProjectId === ${JSON.stringify(proposal.target_id)} && projectTab === 'overview'`);
    console.log('AG-137 browser passed: independent grant, full preview, cancel, project creation, separate scope approval, response loss, original receipt and result navigation.');
    console.log(`Screenshots: ${shots}`);
  } catch (error) {
    if (client) console.error('Project browser state:', await client.evaluate("({page:currentPage,ready:document.readyState,dialog:$('#appDialog')?.open,proposals:$('#proposalFeedback')?.textContent,settings:$('#agentFeedback')?.textContent})").catch(()=>'context unavailable'));
    throw error;
  } finally {
    if (client) await client.evaluate('if (window.__projectGrantFetch) window.fetch = window.__projectGrantFetch').catch(()=>{});
    client?.close(); browser?.kill(); server.kill(); await delay(200);
    assert.ok(path.resolve(base).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(base,{recursive:true,force:true,maxRetries:5,retryDelay:200});
  }
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
