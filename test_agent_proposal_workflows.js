const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {DevToolsClient, freePort, browserExecutable, waitForHttp, waitForPage, delay} = require('./test_editor_workflows.js');

async function main() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-proposals-browser-'));
  const screenshots = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-proposals-shots-'));
  const data = path.join(base, 'data');
  const credentials = path.join(base, 'credentials');
  const port = await freePort(); const debugPort = await freePort();
  const origin = `http://127.0.0.1:${port}`;
  const server = childProcess.spawn('python', ['server.py', '--data-dir', data, '--agent-config-dir', credentials, '--port', String(port), '--seed-demo'], {cwd:__dirname, stdio:'ignore', windowsHide:true});
  let browser; let client;
  try {
    await waitForHttp(`${origin}/api/health`);
    browser = childProcess.spawn(browserExecutable(), ['--headless', '--disable-gpu', '--no-first-run', '--disable-extensions', '--disable-background-networking', '--disable-sync', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${path.join(base, 'profile')}`, origin], {stdio:'ignore', windowsHide:true});
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(value => value.json());
    client = new DevToolsClient(pages.find(page => page.type === 'page' && page.url.startsWith(origin)).webSocketDebuggerUrl);
    await client.connect(); await client.call('Page.enable'); await client.call('Runtime.enable');
    await waitForPage(client, 'apiAvailable && projects.length > 0');
    await client.evaluate('applicationFeature.start().then(() => true)');
    const click = selector => client.evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    const select = (key, value) => client.evaluate(`(() => { const node = document.querySelector('[data-proposal-filter=${key}]'); node.value = ${JSON.stringify(value)}; node.dispatchEvent(new Event('change', {bubbles:true})); })()`);
    const confirm = async () => { await waitForPage(client, "$('#appDialog').open"); await click('#appDialogConfirm'); };
    await click('[data-page=settings]');
    await waitForPage(client, "!!document.querySelector('[data-page=agent_settings]')");
    await click('[data-page=agent_settings]');
    await waitForPage(client, "!!document.querySelector('[data-page=agent_proposals]') && !agentSettingsFeature.isBusy()");
    await click('[data-page=agent_proposals]');
    await waitForPage(client, "!agentProposalsFeature.isBusy() && !!document.querySelector('[data-proposal-filter=kind]')");
    assert.equal(fs.existsSync(path.join(data, '.agent')), false);
    assert.equal(fs.existsSync(credentials), false);
    const local = async (route, method = 'GET', body) => {
      const status = await fetch(`${origin}/api/local/agent-management/status`, {headers:{'X-Workbench-Management':'1'}}).then(response => response.json());
      const response = await fetch(`${origin}/api/local/agent-management/${route}`, {method, headers:{'X-Workbench-Management':'1', 'X-Workbench-Management-Token':status.management_token, Origin:origin, 'Content-Type':'application/json'}, body:body ? JSON.stringify(body(status)) : undefined});
      const value = await response.json(); assert.ok(response.ok, JSON.stringify(value)); return value;
    };
    await local('runtime', 'PATCH', status => ({workspace_id:null, expected_version:status.version, request_id:'enable', enabled:true}));
    const provisioned = childProcess.spawnSync('python', ['server.py', '--data-dir', data, '--agent-config-dir', credentials, '--agent-client-add', '多行长中文客户端'.repeat(6), '--agent-scope', 'read', '--agent-scope', 'propose', '--agent-scope', 'commit', '--agent-project', '*', '--agent-category', '*', ...['issue', 'todo', 'info', 'document'].flatMap(kind => ['--agent-kind', kind]), '--port', String(port)], {cwd:__dirname, encoding:'utf8', env:{...process.env, PYTHONIOENCODING:'utf-8'}, windowsHide:true});
    assert.equal(provisioned.status, 0, provisioned.stderr);
    const config = JSON.parse(fs.readFileSync(JSON.parse(provisioned.stdout).config_file, 'utf8'));
    const agent = async (route, method = 'GET', payload) => {
      const response = await fetch(`${origin}/api/agent/v1/${route}`, {method, headers:{Authorization:`Bearer ${config.token}`, 'X-Workbench-Workspace':config.workspace_id, 'Content-Type':'application/json'}, body:payload ? JSON.stringify(payload) : undefined});
      const value = await response.json(); assert.ok(response.ok, JSON.stringify(value)); return value;
    };
    const project = (await agent('projects')).items[0];
    const proposals = [];
    const value = '  echo "quoted"\n  第二行与尾部空格  ';
    for (let index = 0; index < 25; index++) {
      const kind = ['issue', 'todo', 'info'][index % 3];
      proposals.push(await agent('proposals', 'POST', {request_id:`browser-${index}`, operation:'create', kind, content:{title:`${index} 长中文提案`.repeat(6), project_id:project.id, body:'## 事实\n\n```sh\necho "stored only"\n```\n\n最后一行完整内容', ...(kind === 'info' ? {info_fields:[{name:'命令', value, note:'  首尾说明  '}]} : {})}, source_note:'仅为一次性验收数据'}));
    }
    await click('[data-proposal-action=refresh]');
    await waitForPage(client, "document.querySelectorAll('.agent-client').length === 20 && !agentProposalsFeature.isBusy()");
    await click('[data-proposal-action=next]');
    await waitForPage(client, "document.querySelectorAll('.agent-client').length === 5 && !agentProposalsFeature.isBusy()");
    await click('[data-proposal-action=previous]');
    await waitForPage(client, "document.querySelectorAll('.agent-client').length === 20 && !agentProposalsFeature.isBusy()");
    await select('kind', 'info');
    await waitForPage(client, "document.querySelectorAll('.agent-client').length === 8 && !agentProposalsFeature.isBusy()");
    await click('[data-proposal-action=review]');
    await waitForPage(client, "!!document.querySelector('.agent-proposal-detail') && !agentProposalsFeature.isBusy()");
    const selected = await client.evaluate("document.querySelector('.agent-proposal-detail [data-proposal-action=cancel]').dataset.proposalId");
    assert.equal(await client.evaluate("document.querySelector('.agent-proposal-detail').textContent.includes('最后一行完整内容')"), true);
    assert.equal(await client.evaluate("document.querySelector('.agent-proposal-detail .primary-button').disabled"), true);
    assert.equal(await client.evaluate(`document.body.textContent.includes(${JSON.stringify(config.token)})`), false);
    assert.equal(await client.evaluate("document.querySelectorAll('.agent-proposal-detail [contenteditable=true], .agent-proposal-detail [data-editor-block]').length"), 0);
    for (const theme of ['light', 'dark']) for (const width of [1440, 390]) {
      await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
      await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); document.querySelector('.agent-proposal-detail').scrollIntoView({block:'start'});`);
      await delay(150);
      assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
      const shot = await client.call('Page.captureScreenshot', {format:'png'});
      fs.writeFileSync(path.join(screenshots, `proposal-${theme}-${width}.png`), Buffer.from(shot.data, 'base64'));
    }
    const original = proposals.find(item => item.proposal_id === selected);
    await agent(`proposals/${selected}`, 'PATCH', {expected_version:1, content:{...original.normalized_content, body:'已修订'}});
    await click('.agent-proposal-detail [data-proposal-action=cancel]'); await confirm();
    await waitForPage(client, "$('#proposalFeedback').textContent.includes('重新核对') && !agentProposalsFeature.isBusy()");
    assert.equal((await agent(`proposals/${selected}`)).state, 'draft');
    await click('.agent-proposal-detail [data-proposal-action=review]');
    await waitForPage(client, "document.querySelector('.agent-proposal-detail').textContent.includes('版本 2') && !agentProposalsFeature.isBusy()");
    await client.evaluate(`window.__proposalFetch = window.fetch.bind(window); window.fetch = async (...args) => { const response = await window.__proposalFetch(...args); if (String(args[0]).endsWith('/cancel')) { window.fetch = window.__proposalFetch; throw new Error('injected lost response'); } return response; };`);
    await click('.agent-proposal-detail [data-proposal-action=cancel]'); await confirm();
    await waitForPage(client, "!!document.querySelector('[data-proposal-action=resolve]') && $('#proposalFeedback').textContent.includes('查询')");
    const epoch = await client.evaluate('performance.timeOrigin');
    await client.call('Page.reload');
    await waitForPage(client, `performance.timeOrigin !== ${epoch} && !!document.querySelector('[data-proposal-action=resolve]')`);
    await click('[data-proposal-action=resolve]');
    await waitForPage(client, "$('#proposalFeedback').textContent === '提案已取消。' && !agentProposalsFeature.isBusy()");
    assert.equal((await agent(`proposals/${selected}`)).state, 'cancelled');
    await select('state', 'committed');
    await waitForPage(client, "document.querySelectorAll('.agent-client').length === 0 && !agentProposalsFeature.isBusy()");
    await client.evaluate(`window.__proposalFetch = window.fetch.bind(window); window.fetch = async (...args) => { if (String(args[0]).includes('/proposals?')) { window.fetch = window.__proposalFetch; return new Response(JSON.stringify({message:'管理会话已失效'}), {status:403, headers:{'Content-Type':'application/json'}}); } return window.__proposalFetch(...args); };`);
    await click('[data-proposal-action=refresh]');
    await waitForPage(client, "$('#proposalFeedback').textContent.includes('管理会话已失效') && !agentProposalsFeature.isBusy()");
    await click('[data-proposal-action=refresh]');
    await waitForPage(client, "$('#proposalFeedback').textContent === '' && !agentProposalsFeature.isBusy()");
    console.log(`Proposal browser workflows passed: uninitialized,pagination,filters,full-preview,disabled-approval,stale-version,cancel,response-loss,reload-query,session-failure,light/dark,desktop/narrow. Screenshots: ${screenshots}`);
  } catch (error) {
    if (client) console.error(await client.evaluate("({page:currentPage, content:$('#manageContent').innerText, busy:agentProposalsFeature.isBusy(), pages:navigationFeature.managePages, resolved:navigationFeature.resolvePage('agent_proposals', projects, selectedProjectId)})").catch(() => null));
    throw error;
  } finally {
    if (client) await client.call('Browser.close').catch(() => {});
    client?.close(); browser?.kill(); server.kill(); await delay(500);
    assert.ok(path.resolve(base).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(base, {recursive:true, force:true, maxRetries:5, retryDelay:200});
  }
}
if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
module.exports = {main};
