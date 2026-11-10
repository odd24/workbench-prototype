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
  const codexHome = path.join(base, 'isolated Codex 中文 & home');
  fs.mkdirSync(codexHome);
  const codexConfig = path.join(codexHome, 'config.toml');
  const originalCodex = '[mcp_servers.workbench]\ncommand = "SECRET-EXISTING"\nargs = ["SECRET-ARGUMENT"]\n';
  fs.writeFileSync(codexConfig, originalCodex);
  const port = await freePort();
  const debugPort = await freePort();
  const origin = `http://127.0.0.1:${port}`;
  const server = childProcess.spawn(process.env.PYTHON || 'python', ['server.py', '--data-dir', data, '--agent-config-dir', credentials, '--seed-demo', '--port', String(port)], {cwd:__dirname, stdio:'ignore', windowsHide:true, env:{...process.env, CODEX_HOME:codexHome}});
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
    assert.deepEqual(await client.evaluate("[...document.querySelectorAll('[data-agent-kind]:checked')].map(node => node.dataset.agentKind)"), ['issue', 'document']);
    await click('[data-agent-kind=todo]');
    const longName = 'Codex 接入与长中文授权名称'.repeat(4);
    await fill('#agentClientName', longName);
    await fill('#agentClientPermission', 'write', 'change');
    await fill('#agentMinimumConfirmation', 'local_web', 'change');
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
    assert.deepEqual(registry[clientId].kinds, ['issue', 'document', 'todo']);
    assert.equal(registry[clientId].minimum_confirmation_mode, 'local_web');
    const config = JSON.parse(fs.readFileSync(path.join(credentials, workspace, `${clientId}.json`), 'utf8'));
    assert.equal(await client.evaluate(`document.body.innerText.includes(${JSON.stringify(config.token)})`), false);
    await click('[data-agent-action="registration-preview"]');
    await waitForPage(client, "!!$('#agentRegistrationPreview') && !agentSettingsFeature.isBusy()");
    assert.equal(await client.evaluate("$('#agentRegistrationPreview').textContent.includes('同名登记不同')"), true);
    assert.equal(await client.evaluate("document.body.textContent.includes('SECRET-EXISTING')"), false);
    assert.equal(fs.readFileSync(codexConfig, 'utf8'), originalCodex);
    for (const theme of ['light', 'dark']) {
      for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); $('#agentRegistrationPreview').scrollIntoView({block:'start'});`);
        await delay(100);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `registration-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
      }
    }
    await client.call('Emulation.setDeviceMetricsOverride', {width:1440, height:1000, deviceScaleFactor:1, mobile:false});
    await click('[data-agent-action="registration-confirm"]');
    await waitForPage(client, "$('#agentFeedback')?.textContent.includes('勾选替换')");
    assert.equal(await client.evaluate("$('#appDialog').open"), false);
    await click('#agentReplaceRegistration');
    await click('[data-agent-action="registration-confirm"]');
    await waitForPage(client, "$('#appDialog').open");
    await click('#appDialog button[value=cancel]');
    await waitForPage(client, "!$('#appDialog').open && !agentSettingsFeature.isBusy()");
    assert.equal(fs.readFileSync(codexConfig, 'utf8'), originalCodex);
    await client.evaluate(`window.__beforeRegistrationFetch = window.fetch.bind(window); window.fetch = async (...args) => { const response = await window.__beforeRegistrationFetch(...args); if (String(args[0]).endsWith('/registration') && args[1]?.method === 'POST') { window.fetch = window.__beforeRegistrationFetch; throw new Error('injected registration response loss'); } return response; };`);
    await click('[data-agent-action="registration-confirm"]');
    await click('[data-agent-action="registration-confirm"]'); // Ignore a double click while confirmation is open.
    await confirm();
    await waitForPage(client, "$('#agentFeedback')?.textContent.includes('查询上次接入结果') && agentSettingsFeature.isBusy()");
    assert.notEqual(fs.readFileSync(codexConfig, 'utf8'), originalCodex);
    await client.evaluate('window.__registrationBeforeReload = true');
    await client.call('Page.reload');
    await waitForPage(client, "!window.__registrationBeforeReload && !!document.querySelector('[data-agent-action=registration-resolve]')");
    await click('[data-agent-action="registration-resolve"]');
    await delay(300);
    await waitForPage(client, "$('#agentRegistrationResult')?.textContent.includes('配置已登记') && !agentSettingsFeature.isBusy()");
    await waitForPage(client, "document.querySelector('.agent-diagnostic')?.textContent.includes('自检 capabilities 只读请求成功')");
    const registrationLogs = path.join(credentials, workspace, 'codex-registrations');
    const receiptDirs = fs.readdirSync(registrationLogs).filter(name => fs.existsSync(path.join(registrationLogs, name, 'receipt.json')));
    assert.equal(receiptDirs.length, 1);
    assert.equal(fs.readFileSync(path.join(registrationLogs, receiptDirs[0], 'before.toml'), 'utf8'), originalCodex);
    assert.equal(await client.evaluate(`sessionStorage.getItem('workbench.agentRegistration.pending.${workspace}')`), null);
    await click('[data-agent-action="registration-preview"]');
    await waitForPage(client, "$('#agentRegistrationPreview')?.textContent.includes('无需重复写入')");
    await fill('#agentRegistrationName', 'workbench_personal');
    assert.equal(await client.evaluate("!!$('#agentRegistrationPreview')"), false, '名称变更必须使预览失效');
    // Terminal commands remain available in the advanced fallback.
    await client.evaluate("document.querySelector('.agent-setup > details').open = true");
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
    assert.equal(await client.evaluate("document.querySelector('.agent-diagnostic').textContent.includes('22 个工具')"), true);
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
        assert.equal(await client.evaluate("[...document.querySelectorAll('.agent-scope-options:has([data-agent-scope])')].every(node => node.clientHeight <= 250 && node.scrollHeight > node.clientHeight)"), true);
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `many-scopes-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
      }
    }
    await click('[data-agent-action="cancel-form"]');
    // AG-128: save a dormant client with no legacy type or scope, then query a lost response.
    await click('[data-agent-action="new"]');
    await waitForPage(client, "!!$('#agentClientName')");
    await fill('#agentClientName', '休眠独立客户端与长中文说明'.repeat(4));
    await client.evaluate("document.querySelectorAll('[data-agent-kind]:checked').forEach(node => node.click())");
    await fill('#agentGrantCapability', 'projects.create', 'change');
    await click('[data-agent-action="add-grant"]');
    await waitForPage(client, "$('#agentFeedback').textContent.includes('请选择操作')");
    await click('[data-grant-operation="create"]');
    await click('[data-agent-action="add-grant"]');
    assert.equal(await client.evaluate("document.querySelector('.agent-client-form').textContent.includes('创建项目：新建')"), true);
    for (const theme of ['light', 'dark']) {
      for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); $('#agentGrantCapability').focus({preventScroll:true}); $('#agentGrantCapability').closest('fieldset').scrollIntoView({block:'start', behavior:'instant'});`);
        await delay(200);
        await client.evaluate("window.scrollTo({top:window.scrollY + $('#agentGrantCapability').closest('fieldset').getBoundingClientRect().top - 85, behavior:'instant'})");
        await delay(100);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `dormant-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
      }
    }
    await client.evaluate("$('#agentClientForm').requestSubmit()");
    await waitForPage(client, "$('#appDialog').open");
    assert.equal(await client.evaluate("$('#appDialog').textContent.includes('旧版不能管理授权')"), true);
    assert.equal(await client.evaluate("$('#appDialog').textContent.includes('创建项目：新建')"), true);
    await client.evaluate("new Promise(resolve => { $('#appDialog').addEventListener('close', () => resolve(true), {once:true}); $('#appDialog button[value=cancel]').click(); })");
    await client.evaluate(`window.__dormantCalls = []; window.__dormantFetch = window.fetch.bind(window); window.fetch = async (...args) => { window.__dormantCalls.push([String(args[0]), args[1]?.method]); const response = await window.__dormantFetch(...args); if (String(args[0]).endsWith('/agent-management/clients') && args[1]?.method === 'POST') { window.fetch = window.__dormantFetch; throw new Error('dormant response loss'); } return response; };`);
    await client.evaluate("$('#agentClientForm').requestSubmit()");
    await confirm();
    await waitForPage(client, "$('#agentFeedback').textContent.includes('查询上次操作') && agentSettingsFeature.isBusy()");
    await click('[data-agent-action="resolve"]');
    await waitForPage(client, "!$('#agentClientName') && !agentSettingsFeature.isBusy()");
    const dormantRegistry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
    assert.equal(dormantRegistry.schema_version, 2);
    const dormant = Object.values(dormantRegistry.clients).find(item => item.name.startsWith('休眠独立'));
    assert.deepEqual(dormant.kinds, []);
    assert.deepEqual(dormant.project_ids, []);
    assert.deepEqual(dormant.categories, []);
    assert.equal(dormant.capability_grant_state, 'dormant');
    const dormantConfig = JSON.parse(fs.readFileSync(path.join(credentials, workspace, `${dormant.client_id}.json`), 'utf8'));
    assert.equal(dormantConfig.schema_version, 2);
    assert.equal('capability_grants' in dormantConfig, false);
    assert.equal(await client.evaluate("document.querySelector('.agent-client-list').textContent.includes('无旧业务条目权限；概念图按单独批准范围和基本权限使用，连接成功仅表示接入可达。')"), true);
    await click(`[data-agent-action="edit"][data-client-id="${dormant.client_id}"]`);
    await waitForPage(client, "!!$('#agentClientName')");
    assert.equal(await client.evaluate("document.querySelectorAll('[data-agent-kind]:checked').length"), 0);
    await click('[data-agent-action="remove-grant"]');
    await client.evaluate("$('#agentClientForm').requestSubmit()");
    await confirm();
    await waitForPage(client, "!$('#agentClientName') && !agentSettingsFeature.isBusy()");
    assert.deepEqual(JSON.parse(fs.readFileSync(registryPath, 'utf8')).clients[dormant.client_id].capability_grants.grants, []);
    // AG-130: no source bytes before consent; explicit file-only client,
    // preview/cancel/approve, lost response and refresh/query, revoke.
    const source = path.join(base, '临时文件与长中文名称'.repeat(4) + '.txt');
    fs.writeFileSync(source, 'FILE-PRIVATE-BODY-不得出现在授权预览😀\n'.repeat(4));
    await click('[data-agent-action="new-file"]');
    await waitForPage(client, "!!$('#agentClientName')");
    assert.equal(await client.evaluate("document.querySelectorAll('[data-agent-kind]:checked').length"), 0);
    await fill('#agentClientName', '文件专用验收');
    await client.evaluate("$('#agentClientForm').requestSubmit()");
    await confirm();
    await waitForPage(client, "!$('#agentClientName') && !agentSettingsFeature.isBusy()");
    registry = JSON.parse(fs.readFileSync(registryPath, 'utf8')).clients;
    const fileClient = Object.values(registry).find(item => item.name === '文件专用验收');
    assert.deepEqual(fileClient.kinds, []);
    assert.deepEqual(fileClient.project_ids, []);
    assert.deepEqual(fileClient.active_file_ids, []);
    assert.equal(fileClient.authorization_schema_version, 4);
    await click(`[data-agent-action="files"][data-client-id="${fileClient.client_id}"]`);
    await waitForPage(client, "!!$('#agentFilePath')");
    await fill('#agentFilePath', source);
    await click('[data-agent-action="file-preview"]');
    await waitForPage(client, "!!$('#agentFilePreview')");
    assert.equal(await client.evaluate("$('#agentFilePreview').textContent.includes('FILE-PRIVATE-BODY')"), false);
    assert.equal(fs.existsSync(path.join(credentials, workspace, 'file-grants.json')), false);
    await click('[data-agent-action="file-cancel"]');
    assert.equal(await client.evaluate("!!$('#agentFilePreview')"), false);
    await fill('#agentFilePath', source);
    await click('[data-agent-action="file-preview"]');
    await waitForPage(client, "!!$('#agentFilePreview')");
    for (const theme of ['light', 'dark']) {
      for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); $('#agentFilePreview').scrollIntoView({block:'start'});`);
        await delay(100);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `file-grants-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
      }
    }
    await client.evaluate(`window.__fileFetch = window.fetch.bind(window); window.fetch = async (...args) => { const response = await window.__fileFetch(...args); if (String(args[0]).endsWith('/files/confirm')) { window.fetch = window.__fileFetch; throw new Error('injected file confirmation response loss'); } return response; };`);
    await click('[data-agent-action="file-confirm"]');
    await confirm();
    await waitForPage(client, "!!document.querySelector('[data-agent-action=file-resolve]') && $('#agentFeedback')?.textContent.includes('先查询原请求结果') && agentSettingsFeature.isBusy()");
    assert.equal(Object.keys(JSON.parse(fs.readFileSync(path.join(credentials, workspace, 'file-grants.json'), 'utf8')).files).length, 1);
    await client.evaluate('window.__stagingReloadPending = true');
    await client.call('Page.reload');
    await waitForPage(client, "window.__stagingReloadPending !== true && !!document.querySelector('[data-agent-action=file-resolve]')");
    await click('[data-agent-action="file-resolve"]');
    await waitForPage(client, "!!document.querySelector('[data-agent-action=file-revoke]') && !document.querySelector('[data-agent-action=file-resolve]')");
    assert.equal(Object.keys(JSON.parse(fs.readFileSync(path.join(credentials, workspace, 'file-grants.json'), 'utf8')).files).length, 1);
    await click('[data-agent-action="file-revoke"]');
    await confirm();
    await waitForPage(client, "!!$('#agentFilesPanel') && !document.querySelector('[data-agent-action=file-revoke]')");
    assert.deepEqual(JSON.parse(fs.readFileSync(registryPath, 'utf8')).clients[fileClient.client_id].active_file_ids, []);
    assert.equal(Object.values(JSON.parse(fs.readFileSync(path.join(credentials, workspace, 'file-grants.json'), 'utf8')).files)[0].status, 'revoked');
    // AG-131: independent policy approval does not grant an implicit owner
    // scope; file source intention is explicitly reapproved per policy.
    const uploadProject = await client.evaluate("fetch('/api/projects').then(response => response.json()).then(items => items[0].id)");
    await click(`[data-agent-action="upload-policy"][data-client-id="${fileClient.client_id}"]`);
    await waitForPage(client, "!!$('#agentUploadOwner')");
    await fill('#agentUploadOwner', uploadProject);
    await click('[data-agent-action="upload-preview"]');
    await waitForPage(client, "$('#agentFeedback')?.textContent.includes('目标不存在或不可访问')");
    assert.equal(fs.existsSync(path.join(credentials, workspace, 'upload-policies.json')), false);
    await click(`[data-agent-action="edit"][data-client-id="${fileClient.client_id}"]`);
    await waitForPage(client, "!!$('#agentClientName')");
    await click('[data-agent-kind=issue]');
    await click('[data-agent-all="project_ids"]');
    await client.evaluate("$('#agentClientForm').requestSubmit()");
    await confirm();
    await waitForPage(client, "!$('#agentClientName') && !agentSettingsFeature.isBusy()");
    await click(`[data-agent-action="files"][data-client-id="${fileClient.client_id}"]`);
    await waitForPage(client, "!!$('#agentFilePath')");
    await fill('#agentFilePath', source);
    await fill('#agentFilePurpose', 'attachment_source', 'change');
    await fill('#agentFileEncoding', 'binary', 'change');
    await click('[data-agent-action="file-preview"]');
    await waitForPage(client, "!!$('#agentFilePreview')");
    await click('[data-agent-action="file-confirm"]');
    await confirm();
    await waitForPage(client, "!$('#agentFilePreview') && !agentSettingsFeature.isBusy()");
    await click(`[data-agent-action="upload-policy"][data-client-id="${fileClient.client_id}"]`);
    await waitForPage(client, "document.querySelectorAll('[data-agent-upload-source]').length === 1");
    await fill('#agentUploadOwner', uploadProject);
    await click('[data-agent-upload-source]');
    await click('[data-agent-action="upload-preview"]');
    await waitForPage(client, "!!$('#agentUploadPreview')");
    assert.equal(await client.evaluate("$('#agentUploadPreview').textContent.includes('FILE-PRIVATE-BODY')"), false);
    assert.equal(fs.existsSync(path.join(credentials, workspace, 'upload-policies.json')), false);
    await click('[data-agent-action="upload-cancel-preview"]');
    assert.equal(await client.evaluate("!!$('#agentUploadPreview')"), false);
    await fill('#agentUploadOwner', uploadProject);
    await click('[data-agent-upload-source]');
    await click('[data-agent-action="upload-preview"]');
    await waitForPage(client, "!!$('#agentUploadPreview')");
    for (const theme of ['light', 'dark']) {
      for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); $('#agentUploadPreview details').open = true; $('#agentUploadPreview').scrollIntoView({block:'start'});`);
        await delay(100);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `upload-policy-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
      }
    }
    await client.evaluate(`window.__uploadFetch = window.fetch.bind(window); window.fetch = async (...args) => { const response = await window.__uploadFetch(...args); if (String(args[0]).endsWith('/upload-policy/confirm')) { window.fetch = window.__uploadFetch; throw new Error('injected upload policy response loss'); } return response; };`);
    await click('[data-agent-action="upload-confirm"]');
    await confirm();
    await waitForPage(client, "!!document.querySelector('[data-agent-action=upload-resolve]') && $('#agentFeedback')?.textContent.includes('请查询原操作') && agentSettingsFeature.isBusy()");
    const uploadPolicyPath = path.join(credentials, workspace, 'upload-policies.json');
    assert.equal(Object.keys(JSON.parse(fs.readFileSync(uploadPolicyPath, 'utf8')).policies).length, 1);
    await client.evaluate('window.__stagingReloadPending = true');
    await client.call('Page.reload');
    await waitForPage(client, "window.__stagingReloadPending !== true && !!document.querySelector('[data-agent-action=upload-resolve]')");
    await click('[data-agent-action="upload-resolve"]');
    await waitForPage(client, "!!$('#agentUploadPanel') && !document.querySelector('[data-agent-action=upload-resolve]') && !agentSettingsFeature.isBusy()");
    const policy = Object.values(JSON.parse(fs.readFileSync(uploadPolicyPath, 'utf8')).policies)[0];
    assert.equal(policy.enabled, true);
    assert.equal(policy.owner_id, uploadProject);
    assert.equal(policy.files.length, 1);
    assert.equal(Object.keys(JSON.parse(fs.readFileSync(uploadPolicyPath, 'utf8')).policies).length, 1);
    await click('[data-agent-action="upload-report"]');
    await waitForPage(client, "!!$('#agentUploadSessions')");
    assert.equal(await client.evaluate("$('#agentUploadSessions').textContent.includes('没有暂存会话')"), true);
    // Populate the report through real authenticated control APIs; no raw
    // bytes or credentials are embedded into the browser's document.
    await click('[data-agent-action="toggle"]');
    await confirm();
    await waitForPage(client, "$('#agentRuntimeState')?.textContent === '已开启'");
    const stageConfig = JSON.parse(fs.readFileSync(path.join(credentials, workspace, `${fileClient.client_id}.json`), 'utf8'));
    const stageSource = Object.values(JSON.parse(fs.readFileSync(path.join(credentials, workspace, 'file-grants.json'), 'utf8')).files).find(item => item.status === 'active');
    const stageHeaders = {'Authorization':`Bearer ${stageConfig.token}`, 'X-Workbench-Workspace':workspace, 'Content-Type':'application/json'};
    const stageRequest = await fetch(`${origin}/api/agent/v1/uploads`, {method:'POST', headers:stageHeaders, body:JSON.stringify({request_id:'browser-report', policy_id:policy.policy_id, source:{mode:'file', file_id:stageSource.file_id, source_revision:stageSource.source_revision}, owner_kind:'project', owner_id:uploadProject, filename:stageSource.display_name, bytes:stageSource.identity.size, sha256:stageSource.sha256})});
    assert.equal(stageRequest.status, 200);
    const stage = await stageRequest.json();
    const stageComplete = await fetch(`${origin}/api/agent/v1/uploads/${stage.upload_id}/complete`, {method:'POST', headers:stageHeaders, body:'{}'});
    assert.equal(stageComplete.status, 200);
    assert.equal((await stageComplete.json()).formal_attachment_created, false);
    await click('[data-agent-action="upload-report"]');
    await waitForPage(client, "$('#agentUploadSessions')?.textContent.includes('暂存已校验')");
    assert.equal(await client.evaluate(`document.body.textContent.includes(${JSON.stringify(stageConfig.token)})`), false);
    await click('[data-agent-action="upload-revoke"]');
    await confirm();
    await waitForPage(client, "!agentSettingsFeature.isBusy() && !document.querySelector('[data-agent-action=upload-resolve]')");
    await waitForPage(client, "$('#agentUploadPanel')?.textContent.includes('已失效')");
    assert.equal(Object.values(JSON.parse(fs.readFileSync(uploadPolicyPath, 'utf8')).policies)[0].enabled, false);
    assert.deepEqual(JSON.parse(fs.readFileSync(registryPath, 'utf8')).clients[fileClient.client_id].kinds, ['issue']);
    // Fresh graph permission is separate from every dormant/file/upload grant.
    const graphTitle = '完整授权预览长中文概念图'.repeat(8);
    const createdGraphResponse = await fetch(`${origin}/api/concept-maps`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title:graphTitle, project_id:uploadProject})});
    assert.equal(createdGraphResponse.status, 201);
    const grantedGraph = await createdGraphResponse.json();
    await click(`[data-agent-action="graph-grants"][data-client-id="${fileClient.client_id}"]`);
    await waitForPage(client, "!!$('#agentGraphGrantsPanel')");
    await fill('#agentGraphGrantResource', JSON.stringify({type:'project', id:uploadProject}), 'change');
    await click('[data-agent-action="graph-add"]');
    const beforeGraphApproval = fs.readFileSync(registryPath, 'utf8');
    await click('[data-agent-action="graph-preview"]');
    await waitForPage(client, "!!$('#agentGraphGrantPreview')");
    assert.equal(fs.readFileSync(registryPath, 'utf8'), beforeGraphApproval);
    assert.equal(await client.evaluate(`$('#agentGraphGrantPreview').textContent.includes(${JSON.stringify(grantedGraph.id)})`), true);
    assert.equal(await client.evaluate(`$('#agentGraphGrantPreview').textContent.includes(${JSON.stringify(grantedGraph.revision)})`), true);
    await click('[data-agent-action="graph-cancel-preview"]');
    assert.equal(await client.evaluate("!!$('#agentGraphGrantPreview')"), false);
    assert.equal(fs.readFileSync(registryPath, 'utf8'), beforeGraphApproval);
    await click('[data-agent-action="graph-preview"]');
    await waitForPage(client, "!!$('#agentGraphGrantPreview')");
    await click('[data-agent-action="graph-confirm"]');
    await waitForPage(client, "$('#appDialog').open");
    await client.evaluate("new Promise(resolve => { $('#appDialog').addEventListener('close', () => resolve(true), {once:true}); $('#appDialog button[value=cancel]').click(); })");
    assert.equal(fs.readFileSync(registryPath, 'utf8'), beforeGraphApproval);
    for (const theme of ['light', 'dark']) {
      for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); $('#agentGraphGrantPreview').scrollIntoView({block:'start'});`);
        await delay(100);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false, `graph grants ${theme}/${width} overflow`);
        await client.evaluate("document.querySelector('[data-agent-action=graph-confirm]').focus({preventScroll:true})");
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `graph-grants-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
      }
    }
    await client.call('Emulation.setDeviceMetricsOverride', {width:1440, height:1000, deviceScaleFactor:1, mobile:false});
    await client.evaluate(`window.__originalGraphFetch = window.fetch.bind(window); window.fetch = async (...args) => { const response = await window.__originalGraphFetch(...args); if (String(args[0]).includes('/concept-maps/confirm') && args[1]?.method === 'POST') { window.fetch = window.__originalGraphFetch; throw new Error('injected graph grant response loss'); } return response; };`);
    await click('[data-agent-action="graph-confirm"]');
    await confirm();
    await waitForPage(client, "!!document.querySelector('[data-agent-action=graph-resolve]') && agentSettingsFeature.isBusy()");
    const graphApprovalPage = await client.evaluate('performance.timeOrigin');
    await client.call('Page.reload');
    await waitForPage(client, `performance.timeOrigin !== ${graphApprovalPage} && currentPage === 'agent_settings' && !!document.querySelector('[data-agent-action=graph-resolve]')`);
    await click('[data-agent-action="graph-resolve"]');
    await waitForPage(client, "!!$('#agentGraphGrantsPanel') && !document.querySelector('[data-agent-action=graph-resolve]') && !agentSettingsFeature.isBusy()");
    let graphRegistry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
    assert.equal(graphRegistry.schema_version, 4);
    assert.equal(graphRegistry.clients[fileClient.client_id].authorization_schema_version, 5);
    assert.equal(graphRegistry.clients[fileClient.client_id].concept_map_grants.grants.length, 1);
    assert.equal(graphRegistry.clients[fileClient.client_id].capability_grant_state, 'dormant');
    await client.evaluate(`window.__graphRevokeObservation = {}; window.__beforeGraphRevokeFetch = window.fetch; window.fetch = async (...args) => { const matches = String(args[0]).endsWith(${JSON.stringify(`/clients/${fileClient.client_id}/concept-maps`)}); const method = args[1]?.method || 'GET'; if (matches && method === 'DELETE') window.__graphRevokeObservation.started = true; const response = await window.__beforeGraphRevokeFetch(...args); if (matches && method === 'DELETE') window.__graphRevokeObservation.response = {status:response.status, payload:await response.clone().json()}; if (matches && method === 'GET' && window.__graphRevokeObservation.response) window.__graphRevokeObservation.reloaded = await response.clone().json(); return response; };`);
    try {
      await click('[data-agent-action="graph-revoke"]');
      await confirm();
      await waitForPage(client, `window.__graphRevokeObservation.started && window.__graphRevokeObservation.response?.status === 200 && window.__graphRevokeObservation.reloaded?.client_id === ${JSON.stringify(fileClient.client_id)} && window.__graphRevokeObservation.reloaded.expected_version === window.__graphRevokeObservation.response.payload.version && window.__graphRevokeObservation.reloaded.grants.grants.length === 0 && !$('#appDialog').open && !!$('#agentGraphGrantsPanel') && !agentSettingsFeature.isBusy() && !document.querySelector('[data-agent-action=graph-resolve]') && document.querySelectorAll('#agentGraphGrantEditor ol li p').length === 0`);
      const observedRevoke = await client.evaluate('window.__graphRevokeObservation');
      assert.equal(observedRevoke.response.payload.client_id, fileClient.client_id);
      assert.match(observedRevoke.response.payload.version, /^[a-f0-9]{64}$/);
      assert.match(observedRevoke.response.payload.operation_id, /^[a-f0-9]{64}$/);
      console.log('Graph revoke observed: DELETE started/completed=200, operation/version bound to same-client reloaded empty grants');
    } finally {
      await client.evaluate('window.fetch = window.__beforeGraphRevokeFetch');
    }
    graphRegistry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
    assert.equal(graphRegistry.schema_version, 4);
    assert.deepEqual(graphRegistry.clients[fileClient.client_id].concept_map_grants.grants, []);
    assert.deepEqual(graphRegistry.clients[fileClient.client_id].kinds, ['issue', 'concept_map']);
    console.log('AG-135 graph grant browser tests passed: explicit fresh scope,complete resource preview,cancel,no-write-before-consent,lost-response,reload-query,withdraw,dormant-preserved,light/dark,desktop/narrow');
    console.log('AG-131 browser tests passed: independent-policy,owner-scope-rejection,explicit-source-reapproval,cancel,consent,response-loss,reload-query,report,revoke,light/dark,desktop/narrow');
    console.log('AG-130 browser tests passed: file-only,metadata-preview,cancel,explicit-consent,lost-response,refresh-query,revoke,light/dark,desktop/narrow');
    console.log('Agent settings browser tests passed: first-use,enable,preference,create,lost-response-recovery,setup,registration-preview,explicit-replace,cancel,double-click,registration-response-loss,reload-query,automatic-read-check,copy,theme,width,unsaved,session-failure,conflict,edit,rotate,revoke,disable,reload');
    console.log(`Screenshots: ${screenshots}`);
  } catch (error) {
    if (client) console.error('Settings UI failure:', await client.evaluate("({page:currentPage, feedback:$('#agentFeedback')?.textContent, state:$('#agentRuntimeState')?.textContent, dialog:$('#appDialog').open, message:$('#appDialogMessage').textContent, form:!!$('#agentClientName'), busy:agentSettingsFeature.isBusy(), calls:window.__dormantCalls})").catch(() => 'page unavailable'));
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
