const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {DevToolsClient, freePort, browserExecutable, waitForHttp, waitForPage, delay} = require('./test_editor_workflows.js');

async function main() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-settings-browser-'));
  const screenshots = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-settings-shots-'));
  const data = path.join(base, 'data');
  const credentials = path.join(base, 'credentials');
  const port = await freePort();
  const debugPort = await freePort();
  const origin = `http://127.0.0.1:${port}`;
  const server = childProcess.spawn(process.env.PYTHON || 'python', ['server.py', '--data-dir', data, '--agent-config-dir', credentials, '--seed-demo', '--port', String(port)], {cwd:__dirname, stdio:'ignore', windowsHide:true});
  let browser;
  let client;
  try {
    await waitForHttp(`${origin}/api/health`);
    browser = childProcess.spawn(browserExecutable(), ['--headless', '--disable-gpu', '--no-first-run', '--disable-extensions', '--disable-background-networking', '--disable-sync', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${path.join(base, 'profile')}`, origin], {stdio:'ignore', windowsHide:true});
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(response => response.json());
    client = new DevToolsClient(pages.find(page => page.type === 'page' && page.url.startsWith(origin)).webSocketDebuggerUrl);
    await client.connect();
    await client.call('Page.enable');
    await client.call('Runtime.enable');
    await waitForPage(client, 'apiAvailable && projects.length > 0');
    await client.evaluate('applicationFeature.start().then(() => true)');
    const click = selector => client.evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    const confirm = async () => { await waitForPage(client, "$('#appDialog').open"); await click('#appDialogConfirm'); };
    const fill = (selector, value, type = 'input') => client.evaluate(`(() => { const node = document.querySelector(${JSON.stringify(selector)}); node.value = ${JSON.stringify(value)}; node.dispatchEvent(new Event(${JSON.stringify(type)}, {bubbles:true})); })()`);
    await click('.nav-item[data-page="settings"]');
    await waitForPage(client, "!!document.querySelector('[data-page=agent_settings]')");
    await click('[data-page="agent_settings"]');
    await waitForPage(client, "$('#agentRuntimeState')?.textContent === '尚未初始化'");
    assert.equal(fs.existsSync(path.join(data, '.agent', 'workspace.json')), false);
    assert.equal(fs.existsSync(credentials), false);
    await click('[data-agent-action="toggle"]');
    await confirm();
    await waitForPage(client, "$('#agentRuntimeState')?.textContent === '已开启'");
    await click('#agentStartupPreference');
    await click('[data-agent-action="preference"]');
    await waitForPage(client, "$('#agentStartupPreference')?.checked && !agentSettingsFeature.isBusy()");
    const workspace = JSON.parse(fs.readFileSync(path.join(data, '.agent', 'workspace.json'), 'utf8')).workspace_id;
    assert.equal(JSON.parse(fs.readFileSync(path.join(credentials, workspace, 'runtime.json'), 'utf8')).startup_enabled, true);
    await click('[data-agent-action="new"]');
    await waitForPage(client, "!!$('#agentClientName')");
    const longName = 'Codex 接入与长中文授权名称'.repeat(4);
    await fill('#agentClientName', longName);
    await fill('#agentClientPermission', 'write', 'change');
    await click('[data-agent-all="project_ids"]');
    await click('[data-agent-all="categories"]');
    // Persist the operation, then drop only its browser response.
    await client.evaluate(`window.__originalSettingsFetch = window.fetch.bind(window); window.fetch = async (...args) => { const response = await window.__originalSettingsFetch(...args); if (String(args[0]).endsWith('/agent-management/clients') && args[1]?.method === 'POST') { window.fetch = window.__originalSettingsFetch; throw new Error('injected lost response'); } return response; };`);
    await client.evaluate("$('#agentClientForm').requestSubmit()");
    await confirm();
    await waitForPage(client, "$('#agentFeedback')?.textContent.includes('查询上次操作') && agentSettingsFeature.isBusy()");
    await click('[data-agent-action="resolve"]');
    await waitForPage(client, "!!$('#agentSetupCommand') && !agentSettingsFeature.isBusy()");
    const registryPath = path.join(credentials, workspace, 'clients.json');
    let registry = JSON.parse(fs.readFileSync(registryPath, 'utf8')).clients;
    const clientId = Object.keys(registry)[0];
    assert.equal(Object.keys(registry).length, 1);
    assert.equal(registry[clientId].name, longName);
    const config = JSON.parse(fs.readFileSync(path.join(credentials, workspace, `${clientId}.json`), 'utf8'));
    assert.equal(await client.evaluate(`document.body.innerText.includes(${JSON.stringify(config.token)})`), false);
    assert.match(await client.evaluate("$('#agentSetupCommand').value"), /mcp add/);
    await fill('#agentTerminal', 'cmd', 'change');
    await waitForPage(client, "$('#agentTerminal').value === 'cmd' && $('#agentSetupCommand').value.startsWith('\"')");
    assert.equal(await client.evaluate("$('#agentSetupCommand').value.startsWith('&')"), false);
    assert.equal(await client.evaluate("document.querySelector('.agent-setup').textContent.includes('无需修改 PATH')"), true);
    assert.equal(await client.evaluate("document.querySelector('.agent-setup').textContent.includes('C:' + String.fromCharCode(92) + 'Users')"), true);
    await fill('#agentTerminal', 'powershell', 'change');
    await waitForPage(client, "$('#agentTerminal').value === 'powershell' && $('#agentSetupCommand').value.startsWith('& ')");
    await fill('#agentRegistrationName', 'workbench_personal');
    await click('[data-agent-action="generate"]');
    await waitForPage(client, "$('#agentSetupCommand').value.includes('workbench_personal')");
    await client.evaluate("window.__savedClipboard = navigator.clipboard.writeText.bind(navigator.clipboard); navigator.clipboard.writeText = async value => { window.__copiedSettingsCommand = value; }");
    await click('[data-agent-action="copy"]');
    await waitForPage(client, "$('#agentFeedback').textContent.includes('已复制')");
    assert.equal(await client.evaluate('window.__copiedSettingsCommand'), await client.evaluate("$('#agentSetupCommand').value"));
    await client.evaluate("navigator.clipboard.writeText = async () => { throw new Error('blocked'); }");
    await click('[data-agent-action="copy"]');
    await waitForPage(client, "$('#agentFeedback').textContent.includes('Ctrl+C')");
    await client.evaluate('navigator.clipboard.writeText = window.__savedClipboard');
    for (const theme of ['light', 'dark']) {
      await fill('#agentTerminal', theme === 'light' ? 'cmd' : 'powershell', 'change');
      await waitForPage(client, theme === 'light' ? "$('#agentSetupCommand').value.startsWith('\"')" : "$('#agentSetupCommand').value.startsWith('& ')");
      for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'})`);
        await delay(100);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false, `${theme}/${width} overflow`);
        assert.equal(await client.evaluate("[...document.querySelectorAll('.agent-settings button')].every(node => node.scrollWidth <= node.clientWidth + 1)"), true);
        await client.evaluate("document.querySelector('[data-agent-action=edit]').focus()");
        assert.equal(await client.evaluate('document.activeElement.dataset.agentAction'), 'edit');
        await client.evaluate('window.scrollTo(0, 0)');
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `settings-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
        await client.evaluate("$('#agentSetupPanel').scrollIntoView({block:'start'})");
        await delay(100);
        const terminalShot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `terminal-${theme}-${width}.png`), Buffer.from(terminalShot.data, 'base64'));
      }
    }
    await client.call('Emulation.setDeviceMetricsOverride', {width:1440, height:1000, deviceScaleFactor:1, mobile:false});
    await click('[data-agent-action="edit"]');
    await waitForPage(client, "!!$('#agentClientName')");
    for (const theme of ['light', 'dark']) {
      for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); document.querySelector('.agent-client-form').scrollIntoView({block:'start'});`);
        await delay(200);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
        assert.equal(await client.evaluate("[...document.querySelectorAll('[data-agent-scope]')].every(node => node.disabled)"), true);
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `form-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
      }
    }
    await client.call('Emulation.setDeviceMetricsOverride', {width:1440, height:1000, deviceScaleFactor:1, mobile:false});
    await fill('#agentClientName', '未保存的名称');
    await click('[data-page="settings"]');
    await waitForPage(client, "$('#unsavedChangesDialog').open");
    await client.evaluate("$('#unsavedChangesDialog').close('cancel')");
    assert.equal(await client.evaluate('currentPage'), 'agent_settings');
    assert.equal(await client.evaluate("$('#agentClientName').value"), '未保存的名称');
    await client.evaluate(`window.__originalSettingsFetch = window.fetch.bind(window); window.fetch = async (...args) => { if (String(args[0]).includes('/agent-management/clients/') && args[1]?.method === 'PATCH') { window.fetch = window.__originalSettingsFetch; return new Response(JSON.stringify({message:'管理会话已失效，请刷新后重试'}), {status:403, headers:{'Content-Type':'application/json'}}); } return window.__originalSettingsFetch(...args); };`);
    await client.evaluate("$('#agentClientForm').requestSubmit()");
    await confirm();
    await waitForPage(client, "$('#agentFeedback')?.textContent.includes('管理会话已失效')");
    assert.equal(await client.evaluate("$('#agentClientName').value"), '未保存的名称');
    assert.equal(JSON.parse(fs.readFileSync(registryPath, 'utf8')).clients[clientId].name, longName);
    // Force a server version conflict through a separate real management request.
    const headers = {'X-Workbench-Management':'1'};
    const status = await fetch(`${origin}/api/local/agent-management/status`, {headers}).then(response => response.json());
    const authorizedHeaders = {...headers, 'X-Workbench-Management-Token':status.management_token};
    const listing = await fetch(`${origin}/api/local/agent-management/clients`, {headers:authorizedHeaders}).then(response => response.json());
    const external = await fetch(`${origin}/api/local/agent-management/clients/${clientId}/rotate`, {method:'POST', headers:{...authorizedHeaders, Origin:origin, 'Content-Type':'application/json'}, body:JSON.stringify({workspace_id:workspace, request_id:'browser-external-rotate', expected_version:listing.items[0].version})});
    assert.equal(external.status, 200);
    await client.evaluate("$('#agentClientForm').requestSubmit()");
    await confirm();
    await waitForPage(client, "$('#agentFeedback')?.textContent.includes('已变化')");
    assert.equal(await client.evaluate("$('#agentClientName').value"), '未保存的名称');
    await click('[data-agent-action="cancel-form"]');
    await confirm();
    await waitForPage(client, "!$('#agentClientName') && !$('#appDialog').open");
    await click('[data-agent-action="refresh"]');
    await waitForPage(client, "!agentSettingsFeature.isBusy() && !$('#agentClientName')");
    await click('[data-agent-action="edit"]');
    await waitForPage(client, "!!$('#agentClientName')");
    await fill('#agentClientName', '成功修改的授权');
    await client.evaluate("$('#agentClientForm').requestSubmit()");
    await confirm();
    await waitForPage(client, "!$('#agentClientName') && !agentSettingsFeature.isBusy()");
    assert.equal(JSON.parse(fs.readFileSync(registryPath, 'utf8')).clients[clientId].name, '成功修改的授权');
    const previousToken = JSON.parse(fs.readFileSync(path.join(credentials, workspace, `${clientId}.json`), 'utf8')).token;
    await click('[data-agent-action="rotate"]');
    await confirm();
    await waitForPage(client, "$('#agentFeedback')?.textContent.includes('客户端设置已更新') && !agentSettingsFeature.isBusy()");
    assert.notEqual(JSON.parse(fs.readFileSync(path.join(credentials, workspace, `${clientId}.json`), 'utf8')).token, previousToken);
    await click('[data-agent-action="diagnose"]');
    await waitForPage(client, "document.querySelector('.agent-diagnostic')?.textContent.includes('自检 capabilities 只读请求成功')");
    assert.equal(await client.evaluate("document.querySelector('.agent-diagnostic').textContent.includes('12 个工具')"), true);
    await click('[data-agent-action="refresh"]');
    await waitForPage(client, "!agentSettingsFeature.isBusy() && document.querySelector('.agent-client')?.textContent.includes('最近自检请求：')");
    assert.equal(await client.evaluate("document.querySelector('.agent-client').textContent.includes('最近客户端请求：暂无记录')"), true);
    for (const theme of ['light', 'dark']) {
      for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); document.querySelector('.agent-diagnostic').scrollIntoView({block:'start'});`);
        await delay(200);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `diagnostic-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
      }
    }
    await client.call('Emulation.setDeviceMetricsOverride', {width:1440, height:1000, deviceScaleFactor:1, mobile:false});
    await click('[data-agent-action="toggle"]');
    await confirm();
    await waitForPage(client, "$('#agentRuntimeState')?.textContent === '已关闭'");
    await click('[data-agent-action="diagnose"]');
    await waitForPage(client, "document.querySelector('.agent-diagnostic')?.textContent.includes('Agent 接入已关闭')");
    await click('[data-agent-action="toggle"]');
    await confirm();
    await waitForPage(client, "$('#agentRuntimeState')?.textContent === '已开启'");
    await click('[data-agent-action="revoke"]');
    await confirm();
    await waitForPage(client, "document.querySelector('.agent-client-state')?.textContent === '已撤销'");
    registry = JSON.parse(fs.readFileSync(registryPath, 'utf8')).clients;
    assert.equal(registry[clientId].enabled, false);
    await click('[data-agent-action="toggle"]');
    await confirm();
    await waitForPage(client, "$('#agentRuntimeState')?.textContent === '已关闭'");
    await client.evaluate('window.__agentSettingsBeforeReload = true');
    await client.call('Page.reload');
    await waitForPage(client, "!window.__agentSettingsBeforeReload && $('#agentRuntimeState')?.textContent === '已关闭'");
    assert.equal(await client.evaluate("$('#agentStartupPreference').checked"), true);
    // Empty and many-scope layouts use this disposable service's real UI APIs.
    const uiRequest = async (resource, method = 'GET', payload) => {
      const response = await fetch(`${origin}/api${resource}`, {method, headers:{'Content-Type':'application/json'}, body:payload === undefined ? undefined : JSON.stringify(payload)});
      assert.ok(response.ok, resource);
      return response.json();
    };
    for (const project of await uiRequest('/projects')) await uiRequest(`/projects/${encodeURIComponent(project.id)}`, 'DELETE');
    await uiRequest('/document-categories', 'PUT', {categories:[]});
    await click('[data-agent-action="new"]');
    await waitForPage(client, "!!$('#agentClientName')");
    await click('[data-agent-action="cancel-form"]');
    await click('[data-agent-action="refresh"]');
    await waitForPage(client, "!agentSettingsFeature.isBusy()");
    await click('[data-agent-action="new"]');
    await waitForPage(client, "!!$('#agentClientForm')");
    assert.equal(await client.evaluate("document.querySelectorAll('[data-agent-scope]').length"), 0);
    assert.equal(await client.evaluate("document.querySelector('.agent-client-form').textContent.includes('暂无可选内容')"), true);
    await click('[data-agent-action="cancel-form"]');
    for (let index = 0; index < 60; index += 1) await uiRequest('/projects', 'POST', {name:`大量范围项目 ${index} ${'长中文'.repeat(8)}`});
    await uiRequest('/document-categories', 'PUT', {categories:Array.from({length:100}, (_, index) => `知识分类 ${index} ${'长中文'.repeat(6)}`)});
    await click('[data-agent-action="refresh"]');
    await waitForPage(client, "!agentSettingsFeature.isBusy()");
    await click('[data-agent-action="new"]');
    await waitForPage(client, "document.querySelectorAll('[data-agent-scope]').length === 160");
    for (const theme of ['light', 'dark']) {
      for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); document.querySelector('.agent-client-form').scrollIntoView({block:'start'});`);
        await delay(200);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
        assert.equal(await client.evaluate("[...document.querySelectorAll('.agent-scope-options')].every(node => node.clientHeight <= 250 && node.scrollHeight > node.clientHeight)"), true);
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `many-scopes-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
      }
    }
    await click('[data-agent-action="cancel-form"]');
    console.log('Agent settings browser tests passed: first-use,enable,preference,create,lost-response-recovery,setup,copy,theme,width,unsaved,session-failure,conflict,edit,rotate,revoke,disable,reload');
    console.log(`Screenshots: ${screenshots}`);
  } catch (error) {
    if (client) console.error('Settings UI failure:', await client.evaluate("({page:currentPage, feedback:$('#agentFeedback')?.textContent, state:$('#agentRuntimeState')?.textContent, dialog:$('#appDialog').open, message:$('#appDialogMessage').textContent})").catch(() => 'page unavailable'));
    if (client) console.error('Overflow:', await client.evaluate("({viewport:innerWidth, doc:document.documentElement.scrollWidth, scroll:scrollX, elements:[...document.querySelectorAll('body *')].filter(node => node.getBoundingClientRect().right > innerWidth + 1).slice(0,12).map(node => ({tag:node.tagName, cls:node.className, right:node.getBoundingClientRect().right, width:node.getBoundingClientRect().width}))})").catch(() => []));
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
module.exports = {main};
