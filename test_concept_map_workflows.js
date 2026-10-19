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
  const dataDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-concept-'));
  const profileDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-edge-concept-'));
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

    const mouse = (type, point, buttons = 0) => client.call('Input.dispatchMouseEvent', {type, ...point, button:type === 'mouseMoved' && !buttons ? 'none' : 'left', buttons, clickCount:1});
    const center = selector => client.evaluate(`(() => { const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return {x:r.left+r.width/2,y:r.top+r.height/2}; })()`);
    const cases = [1, .2, .5, .9, 1.15, 2, 3].map(zoom => ({zoom, width:1440, dark:false}));
    cases.push({zoom:.5,width:1440,dark:true}, {zoom:.5,width:390,dark:false}, {zoom:.5,width:390,dark:true});
    for (const {zoom, width, dark} of cases) {
      await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1.25, mobile:false});
      await client.evaluate(`document.body.classList.toggle('dark', ${dark})`);
      await client.evaluate(`(async () => {
        await conceptMapFeature.flushSave(); document.querySelectorAll('.page').forEach(p => p.classList.remove('active')); document.querySelector('#conceptMapPage').classList.add('active');
        const nodes = [
          {id:'source', type:'concept', text:'源概念', x:60,y:60,width:100,height:38},
          {id:'target', type:'concept', text:'目标概念', x:260,y:140,width:100,height:38},
          {id:'phrase', type:'linking_phrase', text:'连接词', x:60,y:230,width:70,height:28}
        ];
        const map = await api('/concept-maps', {method:'POST', body:JSON.stringify({title:'缩放连线回归',nodes,edges:[],viewport:{x:60.3,y:60.3,zoom:${zoom}}})});
        await conceptMapFeature.open(map.id);
      })()`);
      await delay(200);
      await client.evaluate(`document.activeElement.blur()`);
      const source = await center('[data-concept-node="source"]');
      await mouse('mouseMoved', source); await mouse('mousePressed', source, 1); await mouse('mouseReleased', source);
      await client.call('Input.dispatchMouseEvent', {type:'mousePressed', ...source, button:'left', buttons:1, clickCount:2});
      await client.call('Input.dispatchMouseEvent', {type:'mouseReleased', ...source, button:'left', buttons:0, clickCount:2});

      assert.equal(await client.evaluate(`document.querySelector('[data-concept-node=source] strong').isContentEditable`), true, `double click: zoom ${zoom}, width ${width}, dark ${dark}`);
      const port = await center('[data-concept-node="source"] [data-concept-port="right"]');
      const target = await center('[data-concept-node="target"]');
      await mouse('mouseMoved', port); await delay(80); await mouse('mousePressed', port, 1); await delay(50);
      await mouse('mouseMoved', {x:(port.x+target.x)/2,y:(port.y+target.y)/2}, 1);
      await mouse('mouseMoved', target, 1);
      const highlighted = await client.evaluate(`document.querySelector('[data-concept-node="target"]').classList.contains('drop-target')`);
      await mouse('mouseReleased', target);
      assert.equal(highlighted,true, `zoom ${zoom}: target should highlight`);
      await delay(200);
      // The newly created phrase is still being edited. Moving another node
      // must survive the editor blur rebuilding the node DOM.
      const before = await client.evaluate(`Workbench.appState.editorState.currentConceptMap.nodes.find(n=>n.id==='target').x`);
      const point = await center('[data-concept-node="target"]');
      await mouse('mouseMoved', point); await mouse('mousePressed', point, 1);
      await mouse('mouseMoved', {x:point.x+20,y:point.y+10}, 1); await mouse('mouseReleased', {x:point.x+20,y:point.y+10});
      const after = await client.evaluate(`Workbench.appState.editorState.currentConceptMap.nodes.find(n=>n.id==='target').x`);
      assert.ok(Math.abs(after-before-20/zoom)<.01, `zoom ${zoom}: drag after inline editing: ${before} -> ${after}`);
      const link = async (from, to, {modifiers = 0, cancel = false} = {}) => {
        await delay(200);
        const sourcePoint = await center(`[data-concept-node="${from}"]`);
        await mouse('mouseMoved', sourcePoint); await mouse('mousePressed', sourcePoint, 1); await mouse('mouseReleased', sourcePoint);
        const handle = await center(`[data-concept-node="${from}"] [data-concept-port="right"]`);
        const destination = typeof to === 'string' ? await center(`[data-concept-node="${to}"]`) : to;
        await mouse('mouseMoved', handle);
        await client.call('Input.dispatchMouseEvent', {type:'mousePressed', ...handle, button:'left', buttons:1, clickCount:1, modifiers});
        await mouse('mouseMoved', {x:(handle.x+destination.x)/2,y:(handle.y+destination.y)/2}, 1);
        await mouse('mouseMoved', destination, 1);
        if (cancel) {
          // Unexpected capture loss must clear the preview and unblock the next drag.
          await client.evaluate(`document.querySelector('#conceptMapCanvasShell').releasePointerCapture(1)`);
          await mouse('mouseMoved', destination, 1);
        }
        await mouse('mouseReleased', destination);
        await delay(40);
        return client.evaluate(`({nodes:Workbench.appState.editorState.currentConceptMap.nodes,edges:Workbench.appState.editorState.currentConceptMap.edges})`);
      };
      let result = await link('phrase', 'target', {cancel:true});
      assert.equal(result.edges.length, 2, 'capture loss must not create an edge');
      assert.equal(await client.evaluate(`Boolean(document.querySelector('#conceptMapDraftEdge,.drop-target'))`), false);
      result = await link('phrase', 'target');
      assert.ok(result.edges.some(e=>e.from==='phrase' && e.to==='target'), 'phrase to concept');
      assert.equal(result.nodes.length, 4, 'connecting existing nodes must not create a concept');
      result = await link('source', 'phrase');
      assert.ok(result.edges.some(e=>e.from==='source' && e.to==='phrase'), 'concept to phrase');
      result = await link('source', 'target', {modifiers:10});
      assert.ok(result.edges.some(e=>e.from==='source' && e.to==='target'), 'Ctrl+Shift direct edge');

      // Legacy/native scrolling must not offset the cursor-to-canvas conversion.
      await client.evaluate(`document.querySelector('#conceptMapCanvasShell').scrollTop = 17`);
      // Dropping on blank space must use the rendered (pixel-snapped) origin.
      const stage = await client.evaluate(`document.querySelector('#conceptMapStage').getBoundingClientRect().toJSON()`);
      const blank = {x:stage.left+200*zoom, y:stage.top+310*zoom};
      const scrollBefore = await client.evaluate(`document.querySelector('#conceptMapCanvasShell').scrollTop`);
      result = await link('phrase', blank);
      assert.equal(await client.evaluate(`document.querySelector('#conceptMapCanvasShell').scrollTop`), scrollBefore, 'inline focus must not scroll the canvas');
      const created = result.nodes.find(n=>!['source','target','phrase'].includes(n.id) && n.type==='concept');
      assert.ok(created, 'blank drop creates a concept');
      assert.ok(Math.abs(created.x+created.width/2-200)<.01 && Math.abs(created.y+created.height/2-310)<.01, 'blank drop follows cursor');
      await client.evaluate(`document.activeElement.blur(); conceptMapFeature.flushSave()`);
      const key = async (key, modifiers) => {
        await client.call('Input.dispatchKeyEvent', {type:'keyDown', key, modifiers});
        await client.call('Input.dispatchKeyEvent', {type:'keyUp', key, modifiers});
      };
      let undoCount = 0;
      do { await key('z', 2); undoCount += 1; } while (undoCount < 3 && await client.evaluate(`Workbench.appState.editorState.currentConceptMap.nodes.length`) === 5);
      assert.equal(await client.evaluate(`Workbench.appState.editorState.currentConceptMap.nodes.length`), 4, 'undo blank extension');
      for (let i = 0; i < undoCount; i += 1) await key('y', 2);
      assert.equal(await client.evaluate(`Workbench.appState.editorState.currentConceptMap.nodes.length`), 5, 'redo blank extension');
      await client.evaluate(`conceptMapFeature.flushSave()`);
      const snapshot = await client.evaluate(`JSON.stringify({nodes:Workbench.appState.editorState.currentConceptMap.nodes,edges:Workbench.appState.editorState.currentConceptMap.edges})`);
      await client.evaluate(`conceptMapFeature.open(Workbench.appState.editorState.currentConceptMap.id)`);
      assert.deepEqual(JSON.parse(await client.evaluate(`JSON.stringify({nodes:Workbench.appState.editorState.currentConceptMap.nodes,edges:Workbench.appState.editorState.currentConceptMap.edges})`)), JSON.parse(snapshot), 'save and reopen');
      // Zoom with the pointer over a node, then verify another link still hits.
      const anchor = await center('[data-concept-node="target"]');
      await client.call('Input.dispatchMouseEvent', {type:'mouseWheel', ...anchor, deltaX:0, deltaY:100});
      await delay(80);
      assert.ok(Math.abs(await client.evaluate(`Workbench.appState.editorState.currentConceptMap.viewport.zoom`)-Math.max(.2,zoom*.9))<.00001);
      const zoomedAnchor = await center('[data-concept-node=target]');
      assert.ok(Math.hypot(anchor.x-zoomedAnchor.x,anchor.y-zoomedAnchor.y)<1, 'wheel zoom preserves the cursor anchor after native scrolling');
      result = await link('phrase', 'target');
      assert.equal(result.nodes.length, 5, 'link after wheel zoom reuses the target');
      assert.equal(result.edges.length, 7, 'link after wheel zoom succeeds');
      await client.evaluate(`document.querySelector('#conceptMapCanvasShell').scrollTop = 0; conceptMapFeature.flushSave()`);
      if (process.env.WORKBENCH_CONCEPT_SCREENSHOTS && (zoom === .5)) {
        const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
        const output = path.join(os.tmpdir(), `workbench-concept-${width}-${dark ? 'dark' : 'light'}.png`);
        fs.writeFileSync(output, Buffer.from(screenshot.data, 'base64'));
        console.log(`Screenshot: ${output}`);
      }


    }
    console.log('Concept-map browser workflows passed: zoom 20%-300%, concepts/phrases/direct links, capture loss, edit/drag, blank drop, save/reopen, light/dark, desktop/narrow.');
  } finally {
    client?.close();
    browser?.kill();
    server.kill();
    await delay(100);
    fs.rmSync(profileDirectory, {recursive:true, force:true, maxRetries:5, retryDelay:200});
    fs.rmSync(dataDirectory, {recursive:true, force:true, maxRetries:5, retryDelay:200});
  }
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
