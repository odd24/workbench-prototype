const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {DevToolsClient, freePort, browserExecutable, waitForHttp, waitForPage, delay} = require('./test_editor_workflows.js');

async function main() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-category-browser-'));
  const shots = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-category-shots-'));
  const data = path.join(base, 'data'), credentials = path.join(base, 'credentials');
  const port = await freePort(), debugPort = await freePort(), origin = `http://127.0.0.1:${port}`;
  const server = childProcess.spawn(process.env.PYTHON || 'python', [
    'server.py', '--data-dir', data, '--agent-config-dir', credentials, '--seed-demo', '--enable-agent', '--port', String(port)
  ], {cwd:__dirname, stdio:'ignore', windowsHide:true});
  let browser, client;
  try {
    await waitForHttp(origin + '/api/health');
    async function json(route, method = 'GET', headers = {}, body) {
      const response = await fetch(origin + route, {method, headers:{'Content-Type':'application/json', Origin:origin, ...headers},
        ...(body === undefined ? {} : {body:JSON.stringify(body)})});
      const result = await response.json();
      assert.ok(response.ok, `${route} ${response.status} ${JSON.stringify(result)}`);
      return result;
    }
    const status = await json('/api/local/agent-management/status', 'GET', {'X-Workbench-Management':'1'});
    const manage = (route, method, body) => json('/api/local/agent-management/' + route, method,
      {'X-Workbench-Management':'1','X-Workbench-Management-Token':status.management_token}, body);
    const oldName = '完整预览分类', newName = '浏览器确认的新分类';
    const document = await json('/api/documents', 'POST', {}, {title:'跨主题验收', category:oldName,
      body:'<script>window.__categoryXss = true</script>\n' + '长中文正文保持完整。'.repeat(85)});
    const created = await manage('clients', 'POST', {workspace_id:status.workspace_id, request_id:'category-browser-client',
      name:'浏览器分类客户端', scopes:['read','propose','commit'], kinds:['document'], project_ids:[], categories:[oldName],
      minimum_confirmation_mode:'agent_attested'});
    const config = JSON.parse(fs.readFileSync(path.join(credentials, status.workspace_id, created.client_id + '.json'), 'utf8'));
    const agent = (route, method, body) => json('/api/agent/v1/' + route, method,
      {Authorization:`Bearer ${config.token}`, 'X-Workbench-Workspace':status.workspace_id}, body);
    browser = childProcess.spawn(browserExecutable(), ['--headless','--disable-gpu','--no-first-run','--disable-extensions',
      '--disable-background-networking','--disable-sync', `--remote-debugging-port=${debugPort}`,
      `--user-data-dir=${path.join(base, 'profile')}`, origin], {stdio:'ignore', windowsHide:true});
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(result => result.json());
    client = new DevToolsClient(pages.find(page => page.type === 'page' && page.url.startsWith(origin)).webSocketDebuggerUrl);
    await client.connect();
    await client.call('Page.enable');
    await client.call('Runtime.enable');
    await waitForPage(client, 'apiAvailable && projects.length > 0');
    await client.evaluate('applicationFeature.start().then(() => true)');
    const element = selector => `document.querySelector(${JSON.stringify(selector)})`;
    const click = selector => client.evaluate(`${element(selector)}.click()`);
    const waitElement = selector => waitForPage(client, `!!${element(selector)}`);
    const confirm = async () => {
      await waitForPage(client, "$('#appDialog').open");
      await click('#appDialogConfirm');
    };
    async function screenshot(name, selector) {
      for (const theme of ['light','dark']) for (const width of [1440,390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width,height:1000,deviceScaleFactor:1,mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); ${element(selector)}.scrollIntoView({block:'center'});`);
        await waitForPage(client, `innerWidth === ${width} && Math.abs(document.querySelector('.main').getBoundingClientRect().left - ${width <= 760 ? 0 : 244}) < 1`);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
        const shot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(shots, `${name}-${theme}-${width}.png`), Buffer.from(shot.data, 'base64'));
      }
      await client.call('Emulation.setDeviceMetricsOverride', {width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    }
    await client.evaluate("setPage('agent_settings').then(() => true)");
    await waitForPage(client, "currentPage === 'agent_settings'");
    const grantButton = `[data-agent-action=project-creation-category][data-client-id="${created.client_id}"]`;
    await waitForPage(client, `!!${element(grantButton)} && !agentSettingsFeature.isBusy()`);
    await click(grantButton);
    await waitForPage(client, "!!$('#agentCategoryGrantPanel fieldset') && !agentSettingsFeature.isBusy()");
    await client.evaluate(`$('#agentCategoryName').value = ${JSON.stringify(oldName)}; $('#agentCategoryOperation').value = 'rename';`);
    await click('[data-agent-action=project-creation-preview]');
    await waitForPage(client, "!!$('#agentProjectCreationFull') && !agentSettingsFeature.isBusy()");
    await screenshot('grant', '#agentProjectCreationFull');
    await click('[data-agent-action=project-creation-confirm]');
    await confirm();
    await waitForPage(client, "!!$('#agentCategoryGrantPanel [data-agent-action=project-creation-revoke]') && !agentSettingsFeature.isBusy()");
    const proposal = await agent('proposals', 'POST', {request_id:'category-browser-proposal', kind:'category', operation:'rename',
      content:{family:'document_category', name:oldName, new_name:newName}});
    assert.equal(Object.hasOwn(proposal, 'category_local_details'), false);
    await client.evaluate("setPage('agent_proposals').then(() => true)");
    const review = `[data-proposal-action=review][data-proposal-id="${proposal.proposal_id}"]`;
    await waitElement(review);
    await click(review);
    await waitForPage(client, "!!document.querySelector('[data-category-local-plan]') && !document.querySelector('[data-proposal-action=approve]').disabled");
    assert.equal(await client.evaluate('Boolean(window.__categoryXss)'), false);
    await screenshot('proposal', '[data-category-local-plan]');
    await click('[data-proposal-action=approve]');
    await waitForPage(client, "$('#appDialog').open");
    await click('#appDialog button[value=cancel]');
    await waitForPage(client, "!$('#appDialog').open && !agentProposalsFeature.isBusy()");
    assert.equal((await json('/api/documents/' + document.id)).category, oldName);
    await click('[data-proposal-action=approve]');
    await confirm();
    await waitForPage(client, "!$('#appDialog').open && !agentProposalsFeature.isBusy()");
    assert.equal((await json('/api/documents/' + document.id)).category, newName);
    const completed = await agent('proposals/' + proposal.proposal_id);
    assert.equal(completed.receipt.kind, 'category');
    async function fillCategoryName(name) {
      await waitForPage(client, "$('#appDialog').open && !$('#appDialogInput').readOnly && $('#appDialog').classList.contains('input-mode')");
      await client.evaluate(`$('#appDialogInput').value = ${JSON.stringify(name)}`);
      await click('#appDialogConfirm');
      await waitForPage(client, "$('#appDialog').open && !$('#appDialog').classList.contains('input-mode') && $('#appDialogDetail').textContent.includes('configuration')");
    }
    await client.evaluate("setPage('documents').then(() => true)");
    await waitElement('#newDocumentCategory');
    await click('#newDocumentCategory');
    const ordinaryName = '本机空分类 # & +';
    await fillCategoryName(ordinaryName);
    await client.evaluate(`window.__categoryFetch = fetch; window.fetch = async (...args) => {
      const response = await window.__categoryFetch(...args);
      if (String(args[0]).endsWith('/category-operations/approve')) {
        window.fetch = window.__categoryFetch;
        window.__categoryReceipt = await response.clone().json();
        throw new TypeError('synthetic response loss');
      }
      return response;
    }`);
    await confirm();
    await waitForPage(client, `window.__categoryReceipt?.kind === 'category' && !!${element(`[data-document-category="${ordinaryName}"]`)}`);
    await client.evaluate("setPage('concept_maps').then(() => true)");
    await waitElement('#newConceptMapCategory');
    await click('#newConceptMapCategory');
    const graphName = '空概念图分类 # & +';
    await fillCategoryName(graphName);
    await confirm();
    await waitElement(`[data-concept-map-category="${graphName}"]`);
    await client.evaluate("selectedProjectId = projects[0].id; projectTab = 'assets'; setPage('project').then(() => true)");
    await waitElement('#manageAssetCategories');
    await click('#manageAssetCategories');
    await waitForPage(client, "$('#assetCategoryDialog').open");
    await click('#changeIndependentAssetCategory');
    await waitElement('[data-app-dialog-choice=create]');
    await click('[data-app-dialog-choice=create]');
    const assetName = '独立附件空分类 # & +';
    await fillCategoryName(assetName);
    await confirm();
    await waitForPage(client, `$('#assetCategoryDialog').open && projectAssetCategories.some(item => item.name === ${JSON.stringify(assetName)})`);
    console.log('AG-139 browser passed: exact grant, complete local review, cancellation, migration, ordinary entry points for all three families and receipt replay.');
    console.log(`Screenshots: ${shots}`);
  } catch (error) {
    if (client) console.error('Category browser state:', await client.evaluate(
      "({page:currentPage, project:selectedProjectId, tab:projectTab, assets:projectAssetCategories, dialog:$('#assetCategoryDialog')?.open, appDialog:$('#appDialog')?.open, toast:$('#toast')?.textContent, settings:$('#agentFeedback')?.textContent, proposal:$('#proposalFeedback')?.textContent})").catch(() => null));
    throw error;
  } finally {
    client?.close();
    browser?.kill();
    server.kill();
    await delay(200);
    assert.ok(path.resolve(base).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(base, {recursive:true, force:true, maxRetries:5, retryDelay:200});
  }
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
