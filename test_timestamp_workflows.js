const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');

const delay = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

async function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const {port} = server.address();
      server.close(error => error ? reject(error) : resolve(port));
    });
  });
}

function browserExecutable() {
  const candidates = [
    process.env.WORKBENCH_BROWSER_PATH,
    process.platform === 'win32' && path.join(process.env['ProgramFiles(x86)'] || '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    process.platform === 'win32' && path.join(process.env.ProgramFiles || '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    process.platform === 'linux' && '/usr/bin/microsoft-edge',
    process.platform === 'linux' && '/usr/bin/google-chrome',
    process.platform === 'linux' && '/usr/bin/chromium',
  ].filter(Boolean);
  const executable = candidates.find(candidate => fs.existsSync(candidate));
  if (!executable) throw new Error('未找到 Edge/Chrome；可通过 WORKBENCH_BROWSER_PATH 指定浏览器');
  return executable;
}

async function waitForHttp(url, timeout = 10000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch { /* 服务仍在启动 */ }
    await delay(100);
  }
  throw new Error(`等待服务超时：${url}`);
}

class DevToolsClient {
  constructor(url) {
    this.sequence = 0;
    this.pending = new Map();
    this.socket = new WebSocket(url);
  }

  async connect() {
    await new Promise((resolve, reject) => {
      this.socket.addEventListener('open', resolve, {once:true});
      this.socket.addEventListener('error', reject, {once:true});
    });
    this.socket.addEventListener('message', event => {
      const message = JSON.parse(String(event.data));
      if (!message.id) return;
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(message.error.message));
      else pending.resolve(message.result);
    });
  }

  call(method, params = {}) {
    const id = ++this.sequence;
    return new Promise((resolve, reject) => {
      this.pending.set(id, {resolve, reject});
      this.socket.send(JSON.stringify({id, method, params}));
    });
  }

  async evaluate(expression) {
    const response = await this.call('Runtime.evaluate', {expression, awaitPromise:true, returnByValue:true});
    if (response.exceptionDetails) {
      const detail = response.exceptionDetails.exception?.description || response.exceptionDetails.text;
      throw new Error(`浏览器表达式失败：${detail}`);
    }
    return response.result.value;
  }

  close() {
    this.socket.close();
  }
}

async function waitForPage(client, expression, timeout = 10000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      if (await client.evaluate(expression)) return;
    } catch { /* 导航期间执行上下文会短暂失效 */ }
    await delay(100);
  }
  throw new Error(`等待页面状态超时：${expression}`);
}

async function main() {
  const appPort = await freePort();
  const debugPort = await freePort();
  const baseUrl = `http://127.0.0.1:${appPort}`;
  const dataDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-times-'));
  const profileDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-edge-times-'));
  const python = process.env.PYTHON || 'python';
  const server = childProcess.spawn(python, ['server.py', '--data-dir', dataDirectory, '--seed-demo', '--port', String(appPort)], {
    cwd:__dirname,
    stdio:['ignore', 'pipe', 'pipe'],
    windowsHide:true,
  });
  let browser;
  let client;
  try {
    await waitForHttp(`${baseUrl}/api/health`);
    browser = childProcess.spawn(browserExecutable(), [
      '--headless', '--disable-gpu', '--no-first-run', '--disable-extensions', '--disable-background-networking',
      `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profileDirectory}`, baseUrl,
    ], {stdio:['ignore', 'ignore', 'pipe'], windowsHide:true});
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(response => response.json());
    const page = pages.find(item => item.type === 'page' && item.url.startsWith(baseUrl));
    if (!page) throw new Error('浏览器未创建工作台页面');
    client = new DevToolsClient(page.webSocketDebuggerUrl);
    await client.connect();
    await client.call('Page.enable');
    await client.call('Runtime.enable');
    await client.call('Network.enable');
    await waitForPage(client, `typeof apiAvailable !== 'undefined' && apiAvailable && projects.length > 0`);

    await waitForPage(client, `typeof applicationFeature !== 'undefined' && applicationFeature.diagnostics().started && !document.documentElement.classList.contains('navigation-restoring')`);
    await delay(300);



    const ids = await client.evaluate(`(async () => {
      const project = await api('/projects', {method:'POST', body:JSON.stringify({name:'时间展示验收项目与长中文标题'.repeat(3)})});
      const items = [];
      for (const type of ['issue', 'todo', 'info']) items.push(await api('/records', {method:'POST', body:JSON.stringify({type, title:'时间验收' + type, project_id:project.id, body:'# 原正文', info_fields:type === 'info' ? [{name:'说明', value:'多行\\n内容'}] : undefined})}));
      const doc = await api('/documents', {method:'POST', body:JSON.stringify({title:'时间验收文档', category:'时间验收', body:'# 原文档'})});
      await refreshData(); await refreshDocuments();
      selectedProjectId = project.id; projectTab = 'overview'; setPage('project');
      return {project:project.id, items:items.map(item => item.id), doc:doc.id};
    })()`);
    const sameTimes = async (selector, expression, detailed = true) => {
      assert.equal(await client.evaluate(`$(${JSON.stringify(selector)}).innerHTML === timestampsHtml(${expression}, ${detailed})`), true, selector);
    };
    const screenshot = async name => {
      if (!process.env.WORKBENCH_TIMESTAMP_SCREENSHOTS) return;
      await delay(100);
      const shot = await client.call('Page.captureScreenshot', {format:'png'});
      const target = path.join(os.tmpdir(), `workbench-times-${name}.png`);
      fs.writeFileSync(target, Buffer.from(shot.data, 'base64'));
      console.log(target);
    };
    for (const width of [1440, 390]) {
      for (const dark of [false, true]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${dark}); projectTab = 'overview'; projectViewMode = 'board'; setPage('project')`);
        await sameTimes('#projectTimes', `projects.find(item => item.id === ${JSON.stringify(ids.project)})`);
        await screenshot(`project-${width}-${dark}`);
        assert.equal(await client.evaluate(`$$('#kanban .kanban-card').every(card => card.querySelectorAll('.entity-times').length === 0)`), true);
        await client.evaluate(`projectViewMode = 'list'; renderProjectPage()`);
        assert.equal(await client.evaluate(`$$('#kanban th').slice(-2).map(node => node.textContent).join('|')`), '创建时间|上次修改时间');
        await client.evaluate(`projectTab = 'infos'; renderProjectPage()`);
        assert.equal(await client.evaluate(`$$('#kanban .info-display-card .entity-times time').length`), 0);
        await client.evaluate(`openGlobalStats()`);
        assert.equal(await client.evaluate(`$('.global-project-row .entity-times') === null`), true);
        await client.evaluate(`$('#globalStatsDialog').close()`);
        await client.evaluate(`openDocument(${JSON.stringify(ids.doc)})`);
        await sameTimes('#documentTimes', 'currentDocument');
        assert.equal(await client.evaluate(`Boolean($('#documentDialog footer #documentTimes'))`), true);
        await screenshot(`document-${width}-${dark}`);
        assert.equal(await client.evaluate(`(() => { const r = $('#documentTimes').getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; })()`), true);
        await client.evaluate(`$('#documentDialog').close(); openDocument()`);
        assert.equal(await client.evaluate(`$('#documentTimes').textContent`), '创建：保存后生成修改：保存后生成');
        await client.evaluate(`$('#documentDialog').close(); renderDocumentsPage()`);
        assert.equal(await client.evaluate(`$$('[data-document-card="${ids.doc}"] .entity-times time').length`), 0);
        if (process.env.WORKBENCH_TIMESTAMP_SCREENSHOTS) {
          await client.evaluate(`setPage('documents'); documentOpenCategories.add('时间验收'); renderDocumentsPage()`);
          await delay(100);
          const shot = await client.call('Page.captureScreenshot', {format:'png'});
          const screenshotPath = path.join(os.tmpdir(), `workbench-times-${width}-${dark ? 'dark' : 'light'}.png`);
          fs.writeFileSync(screenshotPath, Buffer.from(shot.data, 'base64'));
          console.log(screenshotPath);
        }
      }
    }
    await client.evaluate(`setPage('timeline')`);
    await waitForPage(client, `Boolean($('[data-timeline-sort="created"]'))`);
    assert.equal(await client.evaluate(`$$('.timeline-table th').length`), 8);
    for (const field of ['created', 'updated']) {
      await client.evaluate(`$('[data-timeline-sort="${field}"]').click()`);
      assert.equal(await client.evaluate(`timelineSort.field`), field);
    }
    await screenshot('timeline');
    await client.evaluate(`timelineFilters.type = ['missing']; renderManagePage('timeline')`);
    assert.equal(await client.evaluate(`$('.timeline-empty-row td').colSpan`), 8);
    await client.evaluate(`timelineFilters.type = []; renderManagePage('timeline')`);
    await delay(1100);
    for (const id of ids.items) {
      await client.evaluate(`openDrawer(${JSON.stringify(id)})`);
      await sameTimes('#drawerTimes', 'currentRecord');
      assert.equal(await client.evaluate(`Boolean($('#detailDrawer footer #drawerTimes'))`), true);
      await screenshot(`drawer-${id}`);
      const original = await client.evaluate(`({created:currentRecord.created, updated:currentRecord.updated})`);
      await client.evaluate(`window.timestampFetch = window.fetch; window.fetch = (url, options) => options?.method === 'PATCH' && String(url).includes('/records/') ? Promise.reject(new Error('验收模拟保存失败')) : window.timestampFetch(url, options); $('.drawer-title').value += '已编辑'; markEditorChanged(); recordSession.cancel()`);
      assert.equal(await client.evaluate(`saveEditorNow()`), false);
      assert.equal(await client.evaluate(`currentRecord.updated`), original.updated);
      await sameTimes('#drawerTimes', 'currentRecord');
      assert.equal(await client.evaluate(`recordSession.dirty`), true);
      await client.evaluate(`window.fetch = window.timestampFetch`);
      assert.equal(await client.evaluate(`saveEditorNow()`), true);
      assert.equal(await client.evaluate(`currentRecord.created`), original.created);
      assert.notEqual(await client.evaluate(`currentRecord.updated`), original.updated);
      await sameTimes('#drawerTimes', 'currentRecord');
      await client.evaluate(`closeDrawer(); openDrawer(${JSON.stringify(id)})`);
      await sameTimes('#drawerTimes', 'currentRecord');
      await client.evaluate(`closeDrawer()`);
    }
    await client.evaluate(`openDocument(${JSON.stringify(ids.doc)}); setDocumentMode('visual')`);
    const originalDoc = await client.evaluate(`({created:currentDocument.created, updated:currentDocument.updated})`);
    await client.evaluate(`window.fetch = (url, options) => options?.method === 'PATCH' && String(url).includes('/documents/') ? Promise.reject(new Error('验收模拟文档保存失败')) : window.timestampFetch(url, options); $('#documentTitle').value += '已编辑'; markDocumentChanged()`);
    assert.equal(await client.evaluate(`saveDocument({notifyUser:false})`), null);
    assert.equal(await client.evaluate(`currentDocument.updated`), originalDoc.updated);
    await sameTimes('#documentTimes', 'currentDocument');
    assert.equal(await client.evaluate(`documentSession.dirty`), true);
    await client.evaluate(`window.fetch = window.timestampFetch; saveDocument({notifyUser:false})`);
    assert.equal(await client.evaluate(`currentDocument.created`), originalDoc.created);
    assert.notEqual(await client.evaluate(`currentDocument.updated`), originalDoc.updated);
    await sameTimes('#documentTimes', 'currentDocument');
    await client.evaluate(`$('#documentDialog').close()`);
    await client.evaluate(`window.timestampReloadMarker = true`);
    await client.call('Page.reload');
    await waitForPage(client, `typeof window.timestampReloadMarker === 'undefined' && typeof openDocument === 'function' && typeof apiAvailable !== 'undefined' && apiAvailable && typeof applicationFeature !== 'undefined' && applicationFeature.diagnostics().started && !document.documentElement.classList.contains('navigation-restoring')`);
    await client.evaluate(`(async () => { await refreshDocuments(); openDocument(${JSON.stringify(ids.doc)}); })()`);
    await sameTimes('#documentTimes', 'currentDocument');
    assert.equal(await client.evaluate(`currentDocument.created`), originalDoc.created);

    // External changes are read from disk; displaying them must not rewrite timestamps.
    const diskDoc = await client.evaluate(`api('/documents/${ids.doc}')`);
    const external = fs.readFileSync(diskDoc.file_path, 'utf8').replace(diskDoc.body.trim(), '# 外部修改正文');
    fs.writeFileSync(diskDoc.file_path, external, 'utf8');
    await client.evaluate(`(async () => { reloadCurrentDocumentFromDisk(await api('/documents/${ids.doc}')); })()`);
    await sameTimes('#documentTimes', 'currentDocument');
    assert.equal(await client.evaluate(`currentDocument.updated`), diskDoc.updated);
    assert.match(await client.evaluate(`currentDocument.body`), /外部修改正文/);
    const history = await client.evaluate(`api('/documents/${ids.doc}/history')`);
    assert.ok(history.length > 0);
    await client.evaluate(`(async () => {
      const latest = await api('/documents/${ids.doc}');
      const restored = await api('/documents/${ids.doc}/restore', {method:'POST', body:JSON.stringify({version:${JSON.stringify(history[0].version)}, expected_revision:latest.revision})});
      reloadCurrentDocumentFromDisk(restored);
    })()`);
    await sameTimes('#documentTimes', 'currentDocument');
    assert.equal(await client.evaluate(`currentDocument.created`), originalDoc.created);
    // Missing/invalid legacy metadata is displayed without creating new business values.
    await client.evaluate(`reloadCurrentDocumentFromDisk({...currentDocument, created:'', updated:'invalid'})`);
    assert.equal(await client.evaluate(`$('#documentTimes').textContent`), '创建：未记录修改：时间格式异常');

    assert.equal(await client.evaluate(`(() => {
      const originalRecords = records; const originalDocuments = documents;
      try {
        records = []; documents = []; renderManagePage('timeline');
        if (!$('#manageContent .empty-state')) return false;
        renderDocumentsPage();
        if (!$('#manageContent .empty-state')) return false;
        const stamp = new Date().toISOString();
        records = Array.from({length:120}, (_, index) => ({...originalRecords[0], id:'ISSUE-TEST-' + index, created:stamp, updated:stamp, project_id:${JSON.stringify(ids.project)}}));
        documents = Array.from({length:120}, (_, index) => ({id:'DOC-TEST-' + index, type:'document', title:'大量数据与长中文标题'.repeat(5), body:'正文', category:'时间验收', tags:[], created:stamp, updated:stamp}));
        renderDocumentsPage();
        if ($$('.document-card .entity-times').length !== 0) return false;
        selectedProjectId = ${JSON.stringify(ids.project)}; projectTab = 'overview'; projectViewMode = 'list'; renderProjectPage();
        return $$('#kanban tbody time').length === 240 && $$('#kanban .auto-collapsed-record').length > 0;
      } finally { records = originalRecords; documents = originalDocuments; }
    })()`), true);
    console.log('Timestamp browser workflows passed: all record types, project and document views, new documents, save/failure/reopen/reload, external edits, history restore, sorting, legacy times, empty/120 items, light/dark, desktop/narrow.');
  } finally {
    const stopped = process => !process || process.exitCode !== null || process.signalCode !== null
      ? Promise.resolve() : new Promise(resolve => process.once('exit', resolve));
    const browserStopped = stopped(browser);
    const serverStopped = stopped(server);
    client?.close();
    browser?.kill();
    server.kill();
    await Promise.race([Promise.all([browserStopped, serverStopped]), delay(5000)]);
    await delay(300);
    for (const directory of [profileDirectory, dataDirectory]) {
      assert.equal(path.dirname(path.resolve(directory)), path.resolve(os.tmpdir()));
    }
    fs.rmSync(profileDirectory, {recursive:true, force:true, maxRetries:20, retryDelay:200});
    fs.rmSync(dataDirectory, {recursive:true, force:true, maxRetries:20, retryDelay:200});
  }
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
