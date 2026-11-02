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
  const dataDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-filters-'));
  const profileDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-edge-filters-'));
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


    await client.evaluate(`(async () => {
      const project = await api('/projects', {method:'POST', body:JSON.stringify({name:'筛选回归项目'})});
      const other = await api('/projects', {method:'POST', body:JSON.stringify({name:'另一项目'})});
      window.filterTestProjects = [project.id, other.id];
      for (const item of [
        {type:'todo', title:'专属标签待办', tags:['待办专属'], priority:'高'},
        {type:'todo', title:'普通待办', tags:['共享'], priority:'普通'},
        {type:'issue', title:'问题甲', tags:['共享'], priority:'高'},
        {type:'issue', title:'问题乙', tags:[], priority:'普通'},
        {type:'info', title:'信息甲', tags:['共享']},
      ]) await api('/records', {method:'POST', body:JSON.stringify({...item, project_id:project.id})});
      await refreshData();
      selectedProjectId = project.id;
      projectTab = 'todos';
      setPage('project');
    })()`);
    const change = (id, value) => client.evaluate(`(() => { const select = document.getElementById(${JSON.stringify(id)}); select.value = ${JSON.stringify(value)}; select.dispatchEvent(new Event('change', {bubbles:true})); })()`);
    const tab = name => client.evaluate(`document.querySelector('[data-project-tab="${name}"]').click()`);
    const count = () => client.evaluate(`document.querySelectorAll('#kanban [data-record-id]').length`);
    const cleared = async () => {
      assert.deepEqual(await client.evaluate(`({...projectFilters})`), {status:'', tag:'', priority:''});
      assert.equal(await client.evaluate(`document.querySelector('#clearProjectFilters').disabled`), true);
    };
    for (const width of [1440, 390]) {
      for (const dark of [false, true]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:900, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${dark})`);
        await tab('todos');
        await change('filterTag', '待办专属');
        assert.equal(await count(), 1);
        assert.equal(await client.evaluate(`$('#clearProjectFilters').disabled`), false);
        await tab('issues');
        await cleared();
        assert.equal(await count(), 2, 'todo-only tag must not hide issues');
        await change('filterTag', '共享');
        await change('filterPriority', '高');
        await change('filterStatus', '待处理');
        assert.equal(await count(), 1);
        await client.evaluate(`$('#clearProjectFilters').click()`);
        await cleared();
        assert.equal(await count(), 2, 'clear all three filters');
        await change('filterPriority', '低');
        assert.equal(await count(), 0, 'valid filters can yield no records');
        await client.evaluate(`$('#clearProjectFilters').click()`);
        await cleared();
        assert.equal(await count(), 2, 'clear filters recovers from empty results');
        await change('filterStatus', '待处理');
        await client.evaluate(`records = records.map(item => item.project_id === selectedProjectId && item.type === 'issue' ? {...item, status:'分析中'} : item); renderProjectPage()`);
        await cleared();
        assert.equal(await count(), 2, 'removed status must not remain a hidden filter');
        await client.evaluate(`(async () => { await refreshData(); renderProjectPage(); })()`);
        await change('filterTag', '共享');
        await client.evaluate(`document.querySelector('[data-view-mode="list"]').click()`);
        assert.equal(await client.evaluate(`projectFilters.tag`), '共享', 'view changes preserve filters');
        await tab('infos');
        await cleared();
        await change('filterTag', '共享');
        await client.evaluate(`$('#clearProjectFilters').click()`);
        await cleared();
        await tab('issues');
        await change('filterTag', '共享');
        await tab('overview');
        await cleared();
        await tab('todos');
        await change('filterTag', '待办专属');
        await client.evaluate(`selectedProjectId = filterTestProjects[1]; renderProjectPage()`);
        await cleared();
        assert.equal(await client.evaluate(`$('#filterTag').value`), '');
        await client.evaluate(`selectedProjectId = filterTestProjects[0]; renderProjectPage(); document.querySelector('[data-view-mode="board"]').click()`);
        await change('filterTag', '待办专属');
        await client.evaluate(`records = records.map(item => item.tags?.includes('待办专属') ? {...item, tags:[]} : item); renderProjectPage()`);
        await cleared();
        assert.equal(await count(), 2, 'removed tag must not remain a hidden filter');
        await client.evaluate(`(async () => { await refreshData(); renderProjectPage(); })()`);
        if (process.env.WORKBENCH_FILTER_SCREENSHOTS) {
          await change('filterTag', '待办专属');
          await client.evaluate(`$('#clearProjectFilters').scrollIntoView({block:'nearest', inline:'nearest'}); $('#clearProjectFilters').focus()`);
          const shot = await client.call('Page.captureScreenshot', {format:'png'});
          const output = path.join(os.tmpdir(), `workbench-filters-${width}-${dark ? 'dark' : 'light'}.png`);
          fs.writeFileSync(output, Buffer.from(shot.data, 'base64'));
          console.log(`Screenshot: ${output}`);
          await client.evaluate(`$('#clearProjectFilters').click()`);
        }
      }
    }
    await client.call('Page.reload');
    await waitForPage(client, `typeof window.filterTestProjects === 'undefined' && typeof projectFilters !== 'undefined' && typeof applicationFeature !== 'undefined' && applicationFeature.diagnostics().started && !document.documentElement.classList.contains('navigation-restoring')`);
    await cleared();
    console.log('Project filter browser workflows passed: tab/project switching, combined reset, view preservation, removed tags, reload, light/dark, desktop/narrow.');
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
