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

async function waitForHttp(url, timeout = 20000) {
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
      throw new Error(response.exceptionDetails.exception?.description || response.exceptionDetails.text);
    }
    return response.result.value;
  }

  close() { this.socket.close(); }
}

async function main() {
  const dataDirectory = process.env.WORKBENCH_PERF_DATA;
  const manifest = JSON.parse(process.env.WORKBENCH_PERF_MANIFEST || '{}');
  if (!dataDirectory || !manifest.projectId || !manifest.documentId || !manifest.conceptMapId) {
    throw new Error('缺少 WORKBENCH_PERF_DATA 或 WORKBENCH_PERF_MANIFEST');
  }
  const appPort = await freePort();
  const debugPort = await freePort();
  const baseUrl = `http://127.0.0.1:${appPort}`;
  const profileDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-edge-rf504-'));
  const python = process.env.PYTHON || 'python';
  const server = childProcess.spawn(python, ['server.py', '--data-dir', dataDirectory, '--port', String(appPort)], {
    cwd:__dirname,
    stdio:['ignore', 'pipe', 'pipe'],
    windowsHide:true,
  });
  let browser;
  let client;
  let serverError = '';
  server.stderr.on('data', chunk => { serverError += String(chunk); });
  try {
    const serverStarted = performance.now();
    await waitForHttp(`${baseUrl}/api/health`);
    const serverStartupMs = performance.now() - serverStarted;
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

    const readyStarted = performance.now();
    const deadline = Date.now() + 30000;
    while (Date.now() < deadline) {
      try {
        if (await client.evaluate(`typeof apiAvailable !== 'undefined' && apiAvailable && records.length === ${manifest.recordCount} && projects.length === ${manifest.projectCount}`)) break;
      } catch { /* 页面初始化中 */ }
      await delay(100);
    }
    const ready = await client.evaluate(`({apiAvailable, records:records.length, documents:documents.length, projects:projects.length})`);
    assert.equal(ready.apiAvailable, true);
    assert.equal(ready.records, manifest.recordCount);
    assert.equal(ready.projects, manifest.projectCount);

    const metrics = await client.evaluate(`(async () => {
      const measurements = [];
      const measure = async (name, action) => {
        let maxLag = 0;
        let previous = performance.now();
        const timer = setInterval(() => {
          const now = performance.now();
          maxLag = Math.max(maxLag, now - previous - 16);
          previous = now;
        }, 16);
        const started = performance.now();
        await action();
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        await new Promise(resolve => setTimeout(resolve, 32));
        clearInterval(timer);
        const durationMs = performance.now() - started;
        measurements.push({name, durationMs, maxEventLoopLagMs:maxLag});
        if (durationMs > 30000) throw new Error(name + ' 超过 30 秒，视为浏览器冻结');
      };
      await measure('home', async () => { setPage('home'); });
      await measure('project', async () => {
        selectedProjectId = ${JSON.stringify(manifest.projectId)};
        projectTab = 'issues';
        setPage('project');
        await loadProjectAssets(selectedProjectId, {force:true});
      });
      await measure('knowledge', async () => {
        setPage('documents');
        await renderManagePage('documents');
      });
      if (documents.length !== ${manifest.documentCount}) throw new Error('知识库文档数量不完整');
      await measure('long-document', async () => {
        await openDocument(${JSON.stringify(manifest.documentId)});
      });
      const documentLength = Workbench.appState.editorState.currentDocument?.body?.length || 0;
      if ($('#documentDialog').open) $('#documentDialog').close();
      await measure('concept-library', async () => {
        setPage('concept_maps');
        await conceptMapFeature.renderLibrary();
      });
      await measure('concept-map-500', async () => {
        await conceptMapFeature.open(${JSON.stringify(manifest.conceptMapId)});
      });
      const map = Workbench.appState.editorState.currentConceptMap;
      const signatures = await measureFetch('/record-signatures');
      const ids = records.slice(0, 20).map(item => 'id=' + encodeURIComponent(item.id)).join('&');
      const summaries = await measureFetch('/records?summary=1&' + ids);
      return {
        measurements,
        documentLength,
        mapNodes:map?.nodes?.length || 0,
        mapEdges:map?.edges?.length || 0,
        renderedNodes:document.querySelectorAll('#conceptMapNodes .concept-node').length,
        http:{signatures, summaries},
      };

      async function measureFetch(resource) {
        const started = performance.now();
        const response = await fetch('/api' + resource);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || response.status);
        return {durationMs:performance.now() - started, count:payload.length};
      }
    })()`);
    assert.equal(metrics.documentLength, manifest.longDocumentLength);
    assert.equal(metrics.mapNodes, 500);
    assert.equal(metrics.mapEdges, manifest.conceptMapEdgeCount);
    assert.equal(metrics.renderedNodes, 500);
    assert.equal(metrics.http.signatures.count, manifest.recordCount);
    assert.equal(metrics.http.summaries.count, Math.min(20, manifest.recordCount));
    process.stdout.write(JSON.stringify({
      serverStartupMs,
      pageReadyMs:performance.now() - readyStarted,
      ...metrics,
    }));
  } finally {
    client?.close();
    browser?.kill();
    server.kill();
    await delay(200);
    fs.rmSync(profileDirectory, {recursive:true, force:true, maxRetries:5, retryDelay:200});
    if (serverError) process.stderr.write(serverError);
  }
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
