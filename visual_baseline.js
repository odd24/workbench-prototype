const childProcess = require('node:child_process');
const assert = require('node:assert/strict');
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
    if (response.exceptionDetails) throw new Error(response.exceptionDetails.exception?.description || response.exceptionDetails.text);
    return response.result.value;
  }

  close() { this.socket.close(); }
}

async function waitFor(url, timeout = 10000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try { if ((await fetch(url)).ok) return; } catch { /* browser is starting */ }
    await delay(100);
  }
  throw new Error(`等待超时：${url}`);
}

async function main() {
  const baseUrl = process.env.WORKBENCH_BASELINE_URL || 'http://127.0.0.1:4174';
  const outputDirectory = path.resolve(process.env.WORKBENCH_BASELINE_OUTPUT || path.join(os.tmpdir(), `workbench-visual-${Date.now()}`));
  const emptyData = process.env.WORKBENCH_BASELINE_EMPTY === '1';
  const debugPort = await freePort();
  const profileDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-edge-visual-'));
  fs.mkdirSync(outputDirectory, {recursive:true});
  let browser;
  let client;
  try {
    await waitFor(`${baseUrl}/api/health`);
    browser = childProcess.spawn(browserExecutable(), [
      '--headless', '--disable-gpu', '--no-first-run', '--disable-extensions', '--disable-background-networking',
      `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profileDirectory}`, baseUrl,
    ], {stdio:['ignore', 'ignore', 'pipe'], windowsHide:true});
    await waitFor(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(response => response.json());
    const page = pages.find(item => item.type === 'page' && item.url.startsWith(baseUrl));
    client = new DevToolsClient(page.webSocketDebuggerUrl);
    await client.connect();
    await client.call('Page.enable');
    await client.call('Runtime.enable');
    await client.call('DOM.enable');
    await client.call('CSS.enable');
    const deadline = Date.now() + 10000;
    while (Date.now() < deadline && !await client.evaluate("typeof apiAvailable !== 'undefined' && apiAvailable")) await delay(100);

    const standardEnvironments = [
      {name:'light-desktop', dark:false, width:1440, height:1000},
      {name:'dark-desktop', dark:true, width:1440, height:1000},
      {name:'light-narrow', dark:false, width:390, height:844},
      {name:'dark-narrow', dark:true, width:390, height:844},
    ];
    const responsiveEnvironments = [1050, 920, 760, 620, 390]
      .map(width => ({name:`responsive-${width}`, dark:false, width, height:844}));
    const environments = process.env.WORKBENCH_BASELINE_RESPONSIVE === '1'
      ? responsiveEnvironments
      : standardEnvironments;
    const capture = async (environment, state) => {
      await delay(180);
      const overflow = await client.evaluate(`(()=>{
        const targets=['html','body','#documentDialog','.document-dialog-shell','.document-workspace','.document-workspace-main'];
        return targets.map(selector=>{
          const element=document.querySelector(selector);
          return element&&element.getClientRects().length?{selector,clientWidth:element.clientWidth,scrollWidth:element.scrollWidth}:null;
        }).filter(Boolean).filter(item=>item.scrollWidth>item.clientWidth+1);
      })()`);
      assert.deepEqual(overflow, [], `${environment.name}/${state} has horizontal viewport overflow`);
      const result = await client.call('Page.captureScreenshot', {format:'png', fromSurface:true});
      fs.writeFileSync(path.join(outputDirectory, `preview-${environment.name}-${state}.png`), Buffer.from(result.data, 'base64'));
    };

    for (const environment of environments) {
      await client.call('Emulation.setDeviceMetricsOverride', {width:environment.width, height:environment.height, deviceScaleFactor:1, mobile:environment.width < 500});
      await client.evaluate(`document.body.classList.toggle('dark', ${environment.dark}); localStorage.setItem('workbench-theme', ${JSON.stringify(environment.dark ? 'dark' : 'light')}); setPage('home'); true`);
      if (environment.name.startsWith('responsive-')) {
        await client.evaluate("(()=>{const title=document.querySelector('#homePage h1'); if(title) title.textContent='我的工作台连续长中文标题用于验证窄屏自然换行与布局边界'; return true})()");
      }
      await capture(environment, emptyData ? 'empty' : 'home');
      if (emptyData) {
        assert.equal(await client.evaluate("document.body.textContent.includes('新建项目') && !document.body.textContent.includes('重构基线项目')"), true);
        continue;
      }
      assert.equal(await client.evaluate("document.body.textContent.includes('重构基线项目')"), true);
      await client.evaluate("selectedProjectId='baseline-project'; projectTab='issues'; setPage('project'); true");
      await capture(environment, 'project');
      assert.equal(await client.evaluate("$('#projectPage').textContent.includes('引用与 Markdown 往返')"), true);
      await client.evaluate("(async()=>{await openDrawer('ISSUE-0001'); return true})()");
      await capture(environment, 'record-editor');
      const documentNode = await client.call('DOM.getDocument');
      const focusNode = await client.call('DOM.querySelector', {nodeId:documentNode.root.nodeId, selector:'.drawer-title'});
      const hoverNode = await client.call('DOM.querySelector', {nodeId:documentNode.root.nodeId, selector:'#closeDrawer'});
      await client.call('CSS.forcePseudoState', {nodeId:focusNode.nodeId, forcedPseudoClasses:['focus']});
      await client.call('CSS.forcePseudoState', {nodeId:hoverNode.nodeId, forcedPseudoClasses:['hover']});
      await client.evaluate("$('#saveRecord').disabled=true; notify('视觉错误状态','保存失败时仍保留当前内容',true); true");
      await capture(environment, 'interaction-states');
      await client.evaluate("$('#saveRecord').disabled=false; $('#toast').classList.remove('visible','error'); true");
      await client.evaluate("(async()=>{await closeDrawer(); setPage('documents'); await renderManagePage('documents'); return true})()");
      await capture(environment, 'knowledge');
      assert.equal(await client.evaluate("$('#manageContent').textContent.includes('维护手册') && $('#manageContent').textContent.includes('空分类')"), true);
      await client.evaluate("(async()=>{documents=await api('/documents'); openDocument('DOC-0001'); return true})()");
      await capture(environment, 'document');
      assert.equal(await client.evaluate("$('#documentDialog').textContent.includes('保存契约') && $('#documentDialog').textContent.includes('引用与 Markdown 往返')"), true);
      await client.evaluate("(()=>{if($('#documentDialog').open) $('#documentDialog').close(); setPage('concept_maps'); return conceptMapFeature.open('CMAP-0001')})()");
      await capture(environment, 'concept-map');
      assert.equal(await client.evaluate("Workbench.appState.editorState.currentConceptMap.nodes.some(node=>node.type==='linking_phrase') && Workbench.appState.editorState.currentConceptMap.edges.length===2"), true);
      await client.evaluate("(async()=>{setPage('home'); searchFeature.open(); await searchFeature.search('基线'); return true})()");
      await capture(environment, 'search');
      assert.equal(await client.evaluate("searchFeature.diagnostics().resultCount >= 2"), true);
      await client.evaluate("searchFeature.close(); true");
    }
    console.log(`Visual baseline screenshots: ${outputDirectory}`);
  } finally {
    client?.close();
    browser?.kill();
    await delay(100);
    fs.rmSync(profileDirectory, {recursive:true, force:true, maxRetries:5, retryDelay:200});
  }
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
