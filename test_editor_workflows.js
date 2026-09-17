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
  const dataDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-rf205-'));
  const profileDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-edge-rf205-'));
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

    let result = await client.evaluate(`({
      dom:Workbench.dom.$ === $ && Workbench.dom.$$ === $$ && Workbench.dom.escapeHtml === escapeHtml && Workbench.dom.safeColor === safeColor,
      api:Workbench.api.request === api,
      dialogs:Workbench.dialogs.notify === notify && Workbench.dialogs.open === openAppDialog && Workbench.dialogs.confirm === appConfirm && Workbench.dialogs.prompt === appPrompt,
      state:Workbench.state.groups.join(',') === 'serverData,uiState,editorState,draftState' && Workbench.appState.serverData.projects === projects && Workbench.appState.uiState.selectedProjectId === selectedProjectId,
      features:Workbench.search && Workbench.trash && Workbench.manage && searchFeature.diagnostics().bindCount === 1 && trashFeature.diagnostics().bindCount === 1 && usageFeature.diagnostics().bindCount === 1,
      homeProject:Workbench.home && Workbench.projectView && typeof Workbench.home.normalizeLayout === 'function' && typeof Workbench.projectView.mergeVisibleOrder === 'function',
      recordKnowledge:Workbench.editorSession && Workbench.recordConflict && Workbench.knowledge && typeof Workbench.knowledge.buildCategoryEntries === 'function',
      conceptMap:Workbench.conceptMap && typeof Workbench.conceptMap.create === 'function' && typeof conceptMapFeature.renderLibrary === 'function',
      entry:Workbench.navigation && Workbench.application && applicationFeature.diagnostics().started
    })`);
    assert.deepEqual(result, {dom:true, api:true, dialogs:true, state:true, features:true, homeProject:true, recordKnowledge:true, conceptMap:true, entry:true});
    result = await client.evaluate(`(async () => {
      notify('核心通知', '错误详情', true);
      const toastState = {title:$('.toast strong').textContent, detail:$('.toast small').textContent, error:$('#toast').classList.contains('error')};
      const pending = appPrompt({title:'核心输入', input:{label:'选择', choices:[{value:'unsafe-value', label:'<不安全>', color:'#123456'}]}});
      const escaped = $('#appDialogOptions').innerHTML.includes('&lt;不安全&gt;');
      $('[data-app-dialog-choice]').click();
      const value = await pending;
      await conceptMapFeature.renderLibrary();
      const conceptMapLibrary = Boolean($('#conceptMapLibrary .concept-map-library-header'));
      const createdMap = await api('/concept-maps', {method:'POST', body:JSON.stringify({title:'依赖边界验证'})});
      await conceptMapFeature.open(createdMap.id);
      $('#conceptMapTitle').value = '显式依赖已保存';
      $('#conceptMapTitle').dispatchEvent(new Event('input', {bubbles:true}));
      const conceptMapFlushed = await conceptMapFeature.flushSave();
      const savedMap = await api('/concept-maps/' + encodeURIComponent(createdMap.id));
      await conceptMapFeature.renderLibrary();
      return {toastState, escaped, value, conceptMapLibrary, conceptMapFlushed, conceptMapTitle:savedMap.title};
    })()`);
    assert.deepEqual(result, {toastState:{title:'核心通知', detail:'错误详情', error:true}, escaped:true, value:'unsafe-value', conceptMapLibrary:true, conceptMapFlushed:true, conceptMapTitle:'显式依赖已保存'});

    const request = async (resource, options = {}) => {
      const response = await fetch(`${baseUrl}/api${resource}`, {
        method:options.method || 'GET',
        headers:options.body ? {'Content-Type':'application/json'} : undefined,
        body:options.body ? JSON.stringify(options.body) : undefined,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `${response.status}`);
      return payload;
    };
    const writeExternalBody = async (resource, body) => {
      const item = await request(resource);
      const source = fs.readFileSync(item.file_path, 'utf8');
      const frontMatter = source.match(/^---\r?\n[\s\S]*?\r?\n---\r?\n/);
      if (!frontMatter) throw new Error(`Markdown front matter 无效：${item.file_path}`);
      fs.writeFileSync(item.file_path, `${frontMatter[0]}${body}\n`, 'utf8');
    };
    const project = await request('/projects', {method:'POST', body:{name:'RF-205 验收项目'}});
    const record = await request('/records', {method:'POST', body:{
      type:'issue', title:'RF-205 验收记录', project_id:project.id, status:'待处理', priority:'普通', body:'初始记录正文'
    }});
    const orderRecord = await request('/records', {method:'POST', body:{
      type:'issue', title:'RF-304 排序记录', project_id:project.id, status:'待处理', priority:'高', body:'排序写回验证'
    }});
    const raceProject = await request('/projects', {method:'POST', body:{name:'RF-302 竞态项目'}});
    const raceRecord = await request('/records', {method:'POST', body:{
      type:'issue', title:'RF-302 后发记录', project_id:raceProject.id, status:'待处理', priority:'普通', body:'后发记录正文'
    }});
    const documentItem = await request('/documents', {method:'POST', body:{
      title:'RF-205 验收文档', category:'验收', tags:[], body:'初始文档正文'
    }});
    const raceDocument = await request('/documents', {method:'POST', body:{
      title:'RF-302 后发文档', category:'验收', tags:[], body:'后发文档正文'
    }});
    const trashRecord = await request('/records', {method:'POST', body:{
      type:'todo', title:'RF-303 回收站记录', project_id:project.id, status:'待处理', priority:'普通', body:'等待恢复'
    }});
    await request(`/records/${trashRecord.id}`, {method:'DELETE'});

    const recordId = JSON.stringify(record.id);
    const orderRecordId = JSON.stringify(orderRecord.id);
    const raceRecordId = JSON.stringify(raceRecord.id);
    const projectId = JSON.stringify(project.id);
    const raceProjectId = JSON.stringify(raceProject.id);
    const documentId = JSON.stringify(documentItem.id);
    const raceDocumentId = JSON.stringify(raceDocument.id);
    result = await client.evaluate(`(async () => {
      await refreshData();
      const nativeFetch = window.fetch.bind(window);
      window.fetch = (url, options) => String(url).includes('/api/records/' + ${recordId})
        ? new Promise(resolve => setTimeout(() => resolve(nativeFetch(url, options)), 250))
        : nativeFetch(url, options);
      try {
        const first = openDrawer(${recordId});
        await new Promise(resolve => setTimeout(resolve, 20));
        const second = openDrawer(${raceRecordId});
        await Promise.all([first, second]);
        return {id:currentRecord?.id, title:$('.drawer-title').value, stateId:Workbench.appState.editorState.currentRecord?.id};
      } finally { window.fetch = nativeFetch; }
    })()`);
    assert.deepEqual(result, {id:raceRecord.id, title:'RF-302 后发记录', stateId:raceRecord.id});

    result = await client.evaluate(`(async () => {
      const nativeFetch = window.fetch.bind(window);
      window.fetch = (url, options) => String(url).includes('/api/projects/' + ${projectId} + '/')
        ? new Promise(resolve => setTimeout(() => resolve(nativeFetch(url, options)), 250))
        : nativeFetch(url, options);
      try {
        selectedProjectId = ${projectId};
        const first = loadProjectAssets(${projectId}, {force:true});
        await new Promise(resolve => setTimeout(resolve, 20));
        selectedProjectId = ${raceProjectId};
        const second = loadProjectAssets(${raceProjectId}, {force:true});
        await Promise.all([first, second]);
        return {projectId:projectAssetProjectId, selectedProjectId, stateProjectId:Workbench.appState.uiState.selectedProjectId};
      } finally { window.fetch = nativeFetch; }
    })()`);
    assert.deepEqual(result, {projectId:raceProject.id, selectedProjectId:raceProject.id, stateProjectId:raceProject.id});

    result = await client.evaluate(`(async () => {
      documents = await api('/documents');
      openDocument(${documentId});
      setDocumentMode('visual');
      documentEditorHost.render('延迟保存内容', true);
      markDocumentChanged();
      documentSession.cancel();
      const nativeFetch = window.fetch.bind(window);
      window.fetch = (url, options) => String(url).includes('/api/documents/' + ${documentId})
        ? new Promise(resolve => setTimeout(() => resolve(nativeFetch(url, options)), 250))
        : nativeFetch(url, options);
      try {
        const first = saveDocument({readAfterSave:false, notifyUser:false});
        await new Promise(resolve => setTimeout(resolve, 20));
        openDocument(${raceDocumentId});
        await first;
        return {id:currentDocument?.id, title:$('#documentTitle').value, dirty:documentSession.dirty, stateId:Workbench.appState.editorState.currentDocument?.id};
      } finally { window.fetch = nativeFetch; }
    })()`);
    assert.deepEqual(result, {id:raceDocument.id, title:'RF-302 后发文档', dirty:false, stateId:raceDocument.id});

    result = await client.evaluate(`(async () => {
      homeLayout = normalizeHomeLayout({columns:[
        {id:'home_a', title:'第一栏', items:[${recordId}]},
        {id:'home_b', title:'第二栏', items:[${orderRecordId}]}
      ], statusWatch:['待处理']});
      homeLayout = homeCore.fromBoard(homeLayout, [
        {id:'home_b', items:[${orderRecordId}]},
        {id:'home_a', items:[${recordId}]}
      ]);
      saveHomeLayout();
      const reloadedLayout = homeCore.load(localStorage, HOME_LAYOUT_STORAGE_KEY, HOME_LAYOUT_LEGACY_KEY);
      await refreshData();
      selectedProjectId = ${projectId};
      projectTab = 'issues';
      projectViewMode = 'board';
      projectFilters = {status:'', tag:'', priority:''};
      renderProjectPage();
      await persistRecordOrder([${orderRecordId}, ${recordId}], ['待处理']);
      const columns = $$('.kanban-column', $('#kanban'));
      let expectedColumns = columns.map(column => column.dataset.status);
      if (columns.length > 1) {
        columns[0].before(columns[1]);
        expectedColumns = $$('.kanban-column', $('#kanban')).map(column => column.dataset.status);
        await persistColumnOrder();
      }
      await refreshData();
      selectedProjectId = ${projectId};
      projectTab = 'issues';
      renderProjectPage();
      const persistedProject = projects.find(item => item.id === ${projectId});
      const visibleCards = $$('.kanban-card', $('#kanban')).map(card => card.dataset.recordId);
      const visibleColumns = $$('.kanban-column', $('#kanban')).map(column => column.dataset.status);
      return {
        homeColumns:reloadedLayout.columns.map(column => column.id),
        recordOrder:persistedProject.issue_record_order.slice(0, 2),
        visibleCards:visibleCards.filter(id => [${orderRecordId}, ${recordId}].includes(id)).slice(0, 2),
        columnsPersisted:expectedColumns.every((name, index) => visibleColumns[index] === name),
      };
    })()`);
    assert.deepEqual(result, {homeColumns:['home_b', 'home_a'], recordOrder:[orderRecord.id, record.id], visibleCards:[orderRecord.id, record.id], columnsPersisted:true});

    result = await client.evaluate(`(async () => {
      await refreshData();
      activeManagePage = 'status_templates';
      selectedWorkflowId = projects.find(item => item.id === ${projectId})?.workflow_template || 'standard';
      await renderManagePage('status_templates');
      await renderManagePage('status_templates');
      openUsageOverview('status');
      const overview = $('#usageDialogContent').querySelector('button .in-use')?.closest('button');
      overview?.click();
      const usageRecordButton = $('#usageDialogContent').querySelector('[data-usage-record]');
      usageRecordButton?.click();
      const deadline = Date.now() + 4000;
      while (!detailDrawer.classList.contains('visible') && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 25));
      const openedRecord = currentRecord?.id || '';
      await returnToUsage();
      const returnedView = usageFeature.diagnostics().view;
      usageFeature.back();
      const overviewView = usageFeature.diagnostics().view;
      activeManagePage = 'trash';
      await renderManagePage('trash');
      await renderManagePage('trash');
      const checkbox = $('#manageContent').querySelector('[data-trash-select]');
      if (checkbox) { checkbox.checked = true; checkbox.dispatchEvent(new Event('change', {bubbles:true})); }
      $('#searchTrigger').click();
      await new Promise(resolve => setTimeout(resolve, 250));
      return {
        openedRecord,
        returnedView,
        overviewView,
        trashSelected:trashFeature.diagnostics().selectedCount,
        searchVisible:searchPanel.classList.contains('visible'),
        bindings:[searchFeature.diagnostics().bindCount, trashFeature.diagnostics().bindCount, usageFeature.diagnostics().bindCount],
      };
    })()`);
    assert.ok(result.openedRecord);
    assert.deepEqual({...result, openedRecord:'opened'}, {openedRecord:'opened', returnedView:'detail', overviewView:'overview', trashSelected:1, searchVisible:true, bindings:[1, 1, 1]});
    await client.evaluate(`(() => { closeSearch(); usageFeature.close(); return true; })()`);

    result = await client.evaluate(`(async () => {
      await refreshData();
      await openDrawer(${recordId});
      recordEditorHost.render('# 自动保存\\n\\n- [x] 记录', true);
      markEditorChanged();
      const saved = await saveEditorNow();
      await openDrawer(${recordId});
      return {saved, body:localEditorContent(), dirty:recordSession.dirty, draft:localStorage.getItem(editorDraftKey(${recordId}))};
    })()`);
    assert.deepEqual(result, {saved:true, body:'# 自动保存\n\n- [x] 记录', dirty:false, draft:null});

    result = await client.evaluate(`(async () => {
      documents = await api('/documents');
      openDocument(${documentId});
      setDocumentMode('visual');
      documentEditorHost.render('# 自动保存文档\\n\\n| 左 | 右 |\\n| :--- | ---: |\\n| A | B |', true);
      markDocumentChanged();
      const saved = await saveDocument({readAfterSave:false, notifyUser:false});
      openDocument(${documentId});
      return {saved:Boolean(saved), body:documentMarkdownContent(), dirty:documentSession.dirty, draft:localStorage.getItem(documentDraftKey(${documentId}))};
    })()`);
    assert.deepEqual(result, {saved:true, body:'# 自动保存文档\n\n| 左 | 右 |\n| :--- | ---: |\n| A | B |', dirty:false, draft:null});

    await client.call('Network.setBlockedURLs', {urls:['*/api/records/*']});
    result = await client.evaluate(`(async () => {
      await openDrawer(${recordId});
      recordEditorHost.render('记录失败后重试', true);
      markEditorChanged();
      recordSession.cancel();
      const saved = await saveEditorNow();
      return {saved, dirty:recordSession.dirty, draft:Boolean(recordSession.read(${recordId})), state:$('.save-indicator').textContent};
    })()`);
    assert.deepEqual(result, {saved:false, dirty:true, draft:true, state:'保存失败，请重试'});
    await client.call('Network.setBlockedURLs', {urls:[]});
    result = await client.evaluate(`(async () => ({saved:await saveEditorNow(), dirty:recordSession.dirty, draft:recordSession.read(${recordId})}))()`);
    assert.deepEqual(result, {saved:true, dirty:false, draft:null});

    await client.call('Network.setBlockedURLs', {urls:['*/api/documents/*']});
    result = await client.evaluate(`(async () => {
      documents = await api('/documents');
      openDocument(${documentId});
      setDocumentMode('visual');
      documentEditorHost.render('文档失败后重试', true);
      markDocumentChanged();
      documentSession.cancel();
      const saved = await saveDocument({readAfterSave:false, notifyUser:false});
      return {saved:Boolean(saved), dirty:documentSession.dirty, draft:Boolean(documentSession.read(${documentId})), state:$('#documentSaveState').textContent};
    })()`);
    assert.deepEqual(result, {saved:false, dirty:true, draft:true, state:'保存失败，请重试'});
    await client.call('Network.setBlockedURLs', {urls:[]});
    result = await client.evaluate(`(async () => ({saved:Boolean(await saveDocument({readAfterSave:false, notifyUser:false})), dirty:documentSession.dirty, draft:documentSession.read(${documentId})}))()`);
    assert.deepEqual(result, {saved:true, dirty:false, draft:null});

    result = await client.evaluate(`(async () => {
      localStorage.setItem('workbench-save-on-leave', 'true');
      $('#saveOnLeave').checked = true;
      await openDrawer(${recordId});
      recordEditorHost.render('关闭记录时保存', true); markEditorChanged(); recordSession.cancel();
      const closed = await closeDrawer();
      const closedBody = (await api('/records/' + ${recordId})).body;
      await openDrawer(${recordId});
      recordEditorHost.render('切换记录时保存', true); markEditorChanged(); recordSession.cancel();
      if (await confirmLeaveRecord()) await openDrawer(${JSON.stringify(orderRecord.id)});
      const switchedBody = (await api('/records/' + ${recordId})).body;
      return {closed, closedBody, switchedBody, currentId:currentRecord?.id, dirty:recordSession.dirty};
    })()`);
    assert.deepEqual(result, {closed:true, closedBody:'关闭记录时保存', switchedBody:'切换记录时保存', currentId:orderRecord.id, dirty:false});

    result = await client.evaluate(`(async () => {
      documents = await api('/documents');
      openDocument(${documentId});
      setDocumentMode('visual');
      documentEditorHost.render('关闭文档时保存', true); markDocumentChanged(); documentSession.cancel();
      const closing = closeDocumentEditor();
      await new Promise(resolve => setTimeout(resolve, 20));
      $('#unsavedChangesDialog button[value="save"]').click();
      const closed = await closing;
      const savedBody = (await api('/documents/' + ${documentId})).body;
      return {closed, open:$('#documentDialog').open, savedBody, dirty:documentSession.dirty};
    })()`);
    assert.deepEqual(result, {closed:true, open:false, savedBody:'关闭文档时保存', dirty:false});

    result = await client.evaluate(`(async () => {
      await openDrawer(${recordId});
      localStorage.setItem('workbench-save-on-leave', 'false');
      $('#saveOnLeave').checked = false;
      recordEditorHost.render('刷新后恢复的记录草稿', true);
      markEditorChanged();
      documents = await api('/documents');
      openDocument(${documentId});
      setDocumentMode('visual');
      documentEditorHost.render('刷新后恢复的文档草稿', true);
      markDocumentChanged();
      recordSession.cancel();
      documentSession.cancel();
      return {
        recordDraft:Boolean(localStorage.getItem(editorDraftKey(${recordId}))),
        documentDraft:Boolean(localStorage.getItem(documentDraftKey(${documentId})))
      };
    })()`);
    assert.deepEqual(result, {recordDraft:true, documentDraft:true});
    const pageEpoch = await client.evaluate('performance.timeOrigin');
    await client.call('Page.reload', {ignoreCache:true});
    await waitForPage(client, `performance.timeOrigin !== ${JSON.stringify(pageEpoch)} && typeof apiAvailable !== 'undefined' && apiAvailable && projects.length > 0`);
    result = await client.evaluate(`(async () => {
      await openDrawer(${recordId});
      const recoveredRecord = {body:localEditorContent(), dirty:recordSession.dirty};
      const recordSaved = await saveEditorNow();
      documents = await api('/documents');
      openDocument(${documentId});
      const recoveredDocument = {body:documentMarkdownContent(), dirty:documentSession.dirty};
      const documentSaved = await saveDocument({readAfterSave:false, notifyUser:false});
      return {
        recoveredRecord, recoveredDocument, recordSaved, documentSaved:Boolean(documentSaved),
        recordDraft:localStorage.getItem(editorDraftKey(${recordId})),
        documentDraft:localStorage.getItem(documentDraftKey(${documentId}))
      };
    })()`);
    assert.deepEqual(result, {
      recoveredRecord:{body:'刷新后恢复的记录草稿', dirty:true},
      recoveredDocument:{body:'刷新后恢复的文档草稿', dirty:true},
      recordSaved:true, documentSaved:true, recordDraft:null, documentDraft:null
    });

    await client.evaluate(`(async () => {
      await openDrawer(${recordId});
      recordEditorHost.render('历史版本一', true); markEditorChanged(); await saveEditorNow();
      recordEditorHost.render('历史版本二', true); markEditorChanged(); await saveEditorNow();
      await showHistory();
      return true;
    })()`);
    result = await client.evaluate(`({rows:$$('[data-restore-version]', $('#historyList')).length, previews:$('#historyList').textContent})`);
    assert.ok(result.rows >= 2, '历史列表应至少包含两个版本');
    assert.match(result.previews, /历史版本一/);
    await client.evaluate(`(() => { $('[data-restore-version]', $('#historyList')).click(); return true; })()`);
    await waitForPage(client, `!$('#historyDialog').open && currentRecord?.id === ${recordId} && localEditorContent() !== '历史版本二'`);
    result = await client.evaluate(`({body:localEditorContent(), id:currentRecord.id})`);
    const restoredOnDisk = await request(`/records/${record.id}`);
    assert.equal(result.body, restoredOnDisk.body);

    await client.evaluate(`(async () => { await openDrawer(${recordId}); return true; })()`);
    await writeExternalBody(`/records/${record.id}`, '无 dirty 外部版本');
    await waitForPage(client, `currentRecord?.body === '无 dirty 外部版本' && localEditorContent() === '无 dirty 外部版本'`, 20000);

    await client.evaluate(`(() => { recordEditorHost.render('本地冲突内容', true); markEditorChanged(); recordSession.cancel(); return true; })()`);
    await writeExternalBody(`/records/${record.id}`, '磁盘冲突内容');
    await waitForPage(client, `$('#conflictDialog').open && recordConflict.current?.body === '磁盘冲突内容'`, 20000);
    result = await client.evaluate(`({local:$('#localConflictContent').value, external:$('#externalConflictContent').value, dirty:recordSession.dirty})`);
    assert.deepEqual(result, {local:'本地冲突内容', external:'磁盘冲突内容', dirty:true});

    await client.evaluate(`(() => { $('#conflictExternal').click(); return true; })()`);
    await waitForPage(client, `!$('#conflictDialog').open && localEditorContent() === '磁盘冲突内容'`);
    await client.evaluate(`(async () => {
      recordEditorHost.render('保留工作台版本', true); markEditorChanged(); recordSession.cancel();
      const latest = await api('/records/' + ${recordId});
      showConflict({...latest, body:'被替换的磁盘版本'});
      $('#conflictLocal').click();
      return true;
    })()`);
    await waitForPage(client, `!$('#conflictDialog').open && currentRecord?.body === '保留工作台版本'`);
    assert.equal((await request(`/records/${record.id}`)).body, '保留工作台版本');
    await client.evaluate(`(async () => {
      recordEditorHost.render('本地待合并', true); markEditorChanged(); recordSession.cancel();
      const latest = await api('/records/' + ${recordId});
      showConflict({...latest, body:'磁盘待合并'});
      $('#mergedConflictContent').value = '最终合并版本';
      $('#conflictMerged').click();
      return true;
    })()`);
    await waitForPage(client, `!$('#conflictDialog').open && currentRecord?.body === '最终合并版本'`);
    assert.equal((await request(`/records/${record.id}`)).body, '最终合并版本');

    await client.evaluate(`(async () => { documents = await api('/documents'); openDocument(${documentId}); return true; })()`);
    await writeExternalBody(`/documents/${documentItem.id}`, '外部文档干净刷新');
    await waitForPage(client, `currentDocument?.body === '外部文档干净刷新' && documentMarkdownContent() === '外部文档干净刷新'`, 20000);
    await client.evaluate(`(() => {
      setDocumentMode('visual');
      documentEditorHost.render('文档本地未保存', true); markDocumentChanged(); documentSession.cancel();
      return true;
    })()`);
    await writeExternalBody(`/documents/${documentItem.id}`, '文档磁盘新版本');
    await waitForPage(client, `Boolean($('#documentDialog').dataset.pendingExternalMtime)`, 20000);
    result = await client.evaluate(`({body:documentMarkdownContent(), dirty:documentSession.dirty, pending:Boolean($('#documentDialog').dataset.pendingExternalMtime)})`);
    assert.deepEqual(result, {body:'文档本地未保存', dirty:true, pending:true});

    console.log('Editor workflow browser tests passed: save,retry,close,switch,reopen,draft,history,external-refresh,record-conflicts,document-external-guard');
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
