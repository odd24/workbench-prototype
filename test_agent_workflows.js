const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {DevToolsClient, freePort, browserExecutable, waitForHttp, waitForPage, delay} = require('./test_editor_workflows.js');

async function main() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-agent-browser-'));
  const data = path.join(base, 'data');
  const credentials = path.join(base, 'credentials');
  const profile = path.join(base, 'browser');
  const port = await freePort();
  const debugPort = await freePort();
  const baseUrl = `http://127.0.0.1:${port}`;
  const python = process.env.PYTHON || 'python';
  const server = childProcess.spawn(python, ['server.py', '--data-dir', data, '--agent-config-dir', credentials, '--enable-agent', '--seed-demo', '--port', String(port)], {cwd:__dirname, stdio:'ignore', windowsHide:true});
  let browser;
  let client;
  try {
    await waitForHttp(`${baseUrl}/api/health`);
    const provisioned = childProcess.spawnSync(python, ['server.py', '--data-dir', data, '--agent-config-dir', credentials, '--agent-client-add', '浏览器临时验收', '--agent-scope', 'read', '--agent-scope', 'propose', '--agent-scope', 'commit', '--agent-kind', 'issue', '--agent-kind', 'document', '--agent-kind', 'todo', '--agent-project', '*', '--agent-category', '*', '--port', String(port)], {cwd:__dirname, encoding:'utf8', env:{...process.env, PYTHONIOENCODING:'utf-8'}, windowsHide:true});
    assert.equal(provisioned.status, 0, provisioned.stderr);
    const info = JSON.parse(provisioned.stdout);
    const config = JSON.parse(fs.readFileSync(info.config_file, 'utf8'));
    const request = async (resource, method = 'GET', payload, agent = false) => {
      const response = await fetch(`${baseUrl}/api${agent ? '/agent/v1' : ''}${resource}`, {method,
        headers:{'Content-Type':'application/json', ...(agent ? {Authorization:`Bearer ${config.token}`, 'X-Workbench-Workspace':config.workspace_id} : {})},
        body:payload === undefined ? undefined : JSON.stringify(payload)});
      const result = await response.json();
      assert.ok(response.ok, JSON.stringify(result));
      return result;
    };
    const project = await request('/projects', 'POST', {name:'Agent 网页验收项目'});
    // First-use setup is an explicit user/UI action, never an Agent side effect.
    await request('/document-categories', 'PUT', {categories:['未分类']});
    let sequence = 0;
    const saveByAgent = async (kind, operation, content, target = null) => {
      const proposal = await request('/proposals', 'POST', {request_id:`browser-${++sequence}`, kind, operation, content,
        ...(target ? {target_id:target.id, base_revision:target.revision} : {})}, true);
      const preview = await request(`/proposals/${proposal.proposal_id}/preview`, 'GET', undefined, true);
      assert.equal(preview.version, 1);
      assert.ok(preview.content.body);
      return request(`/proposals/${proposal.proposal_id}/commit`, 'POST', {version:preview.version, preview_digest:preview.preview_digest, confirmation:{mode:'agent_attested', user_confirmed:true, note:'临时浏览器测试夹具'}}, true);
    };
    const body = '## 已验证事实\n\n- [ ] 后续验证\n\n```sh\nprintf \'one two\'\nprintf "three"\n```\n\n| 项目 | 结论 |\n| --- | --- |\n| 检查 | 待验证 |';
    const issue = await saveByAgent('issue', 'create', {title:'AI 整理的问题：' + '长中文标题验收'.repeat(8), project_id:project.id, body});
    const document = await saveByAgent('document', 'create', {title:'AI 整理的知识：' + '长中文标题验收'.repeat(8), category:'未分类', body:body + `\n\n关联问题：[[${issue.item_id}]]`});
    const todo = await saveByAgent('todo', 'create', {title:'AI 待办验收', project_id:project.id, body, due:'2028-02-29'});
    for (const receipt of [issue, document, todo]) {
      assert.equal(new URL(receipt.web_url).origin, baseUrl);
      assert.equal(new URL(receipt.web_url).searchParams.get('itemId'), receipt.item_id);
    }
    browser = childProcess.spawn(browserExecutable(), ['--headless', '--disable-gpu', '--no-first-run', '--disable-extensions', '--disable-background-networking', '--disable-sync', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`, issue.web_url], {stdio:'ignore', windowsHide:true});
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(response => response.json());
    const page = pages.find(item => item.type === 'page' && item.url.startsWith(baseUrl));
    assert.ok(page);
    client = new DevToolsClient(page.webSocketDebuggerUrl);
    await client.connect();
    await client.call('Page.enable');
    await client.call('Runtime.enable');
    const waitOpened = async receipt => waitForPage(client, receipt.kind !== 'document'
      ? `!window.__agentOldDocument && apiAvailable && currentRecord?.id === ${JSON.stringify(receipt.item_id)} && detailDrawer.classList.contains('visible')`
      : `!window.__agentOldDocument && apiAvailable && currentDocument?.id === ${JSON.stringify(receipt.item_id)} && $('#documentDialog').open`);
    const navigate = async receipt => { await client.evaluate('window.__agentOldDocument = true'); await client.call('Page.navigate', {url:receipt.web_url}); await waitOpened(receipt); };
    await waitOpened(issue);
    for (const receipt of [issue, document, todo]) {
      await navigate(receipt);
      await client.evaluate('window.__agentOldDocument = true');
      await client.call('Page.reload');
      await waitOpened(receipt);
      for (const theme of ['light', 'dark']) {
        for (const width of [1440, 390]) {
          await client.call('Emulation.setDeviceMetricsOverride', {width, height:900, deviceScaleFactor:1, mobile:false});
          await client.evaluate(`(() => { document.body.classList.toggle('dark', ${theme === 'dark'}); $('#documentOutline').classList.toggle('collapsed', ${width < 600}); return true; })()`);
          await delay(200);
          const state = await client.evaluate(`({overflow:document.documentElement.scrollWidth > innerWidth + 1, dirty:${receipt.kind !== 'document' ? 'recordSession.dirty' : 'documentSession.dirty'}, controls:${receipt.kind === 'document' ? "$$('[contenteditable=true], [data-editor-block]', $('#documentReadPane')).length" : '0'}})`);
          assert.equal(state.overflow, false);
          assert.equal(state.dirty, false);
          assert.equal(state.controls, 0);
          if (width === 390) {
            if (receipt.kind === 'document') {
              const readBounds = await client.evaluate(`({width:$('#documentReadPane').getBoundingClientRect().width, parent:$('.document-workspace-main').clientWidth, padding:getComputedStyle($('#documentReadPane')).paddingLeft})`);
              assert.ok(readBounds.width <= readBounds.parent + 1);
              assert.equal(readBounds.padding, '18px');
              await client.evaluate(`$('#showDocumentHistory').focus()`);
              const focusBounds = await client.evaluate(`(() => { const button = $('#showDocumentHistory').getBoundingClientRect(); return {left:button.left, right:button.right, focused:document.activeElement.id}; })()`);
              assert.equal(focusBounds.focused, 'showDocumentHistory');
              assert.ok(focusBounds.left >= 0 && focusBounds.right <= width + 1);
            } else {
              assert.equal(await client.evaluate(`$$('.detail-drawer>footer button').every(button => button.scrollWidth <= button.clientWidth + 1)`), true);
            }
          }
          if (process.env.WORKBENCH_AGENT_SCREENSHOTS) {
            fs.mkdirSync(process.env.WORKBENCH_AGENT_SCREENSHOTS, {recursive:true});
            const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
            fs.writeFileSync(path.join(process.env.WORKBENCH_AGENT_SCREENSHOTS, `agent-${receipt.kind}-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
          }
        }
      }
      const isIssue = receipt.kind !== 'document';
      const serialized = await client.evaluate(`(async () => {
        ${isIssue ? "setEditorMode('wysiwyg'); const markdown = editorToMarkdown($('.editor')); setEditorMode('markdown'); $('.markdown-source').value = markdown; markEditorChanged(); recordSession.cancel(); await saveEditorNow(); await openDrawer(currentRecord.id); return markdown.trim();" : "setDocumentMode('visual'); const markdown = documentMarkdownContent(); $('#documentBody').value = markdown; markDocumentChanged(); documentSession.cancel(); await saveDocument({notifyUser:false}); const id = currentDocument.id; await closeDocumentEditor(); documents = await api('/documents'); openDocument(id); return markdown.trim();"}
      })()`);
      const saved = await request(`/${isIssue ? 'records' : 'documents'}/${receipt.item_id}`);
      assert.equal(saved.body, serialized);
      assert.ok(saved.body.includes("printf 'one two'"));
      assert.ok(saved.body.includes('printf "three"'));
    }
    await navigate(issue);
    await client.evaluate(`(() => { $('#saveOnLeave').checked = false; recordEditorHost.render('工作台未保存输入', true); markEditorChanged(); recordSession.cancel(); window.agentLinkPending = openItemLink({kind:'document', itemId:${JSON.stringify(document.item_id)}}); return true; })()`);
    await waitForPage(client, `$('#unsavedChangesDialog').open`);
    await client.evaluate(`(() => { $('#unsavedChangesDialog button[value="cancel"]').click(); return true; })()`);
    assert.equal(await client.evaluate('window.agentLinkPending'), false);
    assert.equal(await client.evaluate('localEditorContent()'), '工作台未保存输入');
    const currentIssue = await request(`/records/${issue.item_id}`);
    await saveByAgent('issue', 'append', {body:'Agent 新增的排查结果'}, currentIssue);
    await client.evaluate(`(async () => { await saveEditorNow(); return true; })()`);
    await waitForPage(client, `$('#conflictDialog').open`);
    assert.equal(await client.evaluate('localEditorContent()'), '工作台未保存输入');
    await client.evaluate(`(() => { $('#conflictExternal').click(); return true; })()`);
    await waitForPage(client, `!$('#conflictDialog').open && !recordSession.dirty && localEditorContent().includes('Agent 新增的排查结果')`);
    assert.ok((await client.evaluate('localEditorContent()')).includes('Agent 新增的排查结果'));
    await navigate(document);
    await client.evaluate(`(() => { setDocumentMode('visual'); documentEditorHost.render('知识库未保存输入', true); markDocumentChanged(); documentSession.cancel(); return true; })()`);
    const currentDocument = await request(`/documents/${document.item_id}`);
    await saveByAgent('document', 'update', {body:'Agent 更新的知识总结'}, currentDocument);
    await client.evaluate(`(async () => { await saveDocument({notifyUser:false}); return true; })()`);
    await waitForPage(client, `$('#conflictDialog').open && conflictKind === 'document'`);
    assert.equal(await client.evaluate('documentMarkdownContent()'), '知识库未保存输入');
    await client.evaluate(`(() => { $('#mergedConflictContent').value = '合并后的知识总结'; $('#conflictMerged').click(); return true; })()`);
    await waitForPage(client, `!$('#conflictDialog').open && !documentSession.dirty`);
    assert.equal((await request(`/documents/${document.item_id}`)).body, '合并后的知识总结');
    for (const receipt of [issue, document, todo]) {
      await navigate(receipt);
      const isIssue = receipt.kind !== 'document';
      const endpoint = `/api/${isIssue ? 'records' : 'documents'}/${receipt.item_id}`;
      await client.evaluate(`(() => {
        const originalFetch = window.fetch;
        window.agentOriginalFetch = originalFetch;
        window.agentOldSaveStored = false;
        window.fetch = async (url, options = {}) => {
          const response = await originalFetch(url, options);
          if (url === ${JSON.stringify(endpoint)} && options.method === 'PATCH' && !window.agentOldSaveStored) {
            window.agentOldSaveStored = true;
            await new Promise(resolve => { window.agentReleaseSave = resolve; });
          }
          return response;
        };
        ${isIssue ? "$('#saveOnLeave').checked = false; setEditorMode('wysiwyg'); recordEditorHost.render('较早的保存内容', true); markEditorChanged(); recordSession.cancel(); window.agentSaving = saveEditorNow();" : "setDocumentMode('visual'); documentEditorHost.render('较早的保存内容', true); markDocumentChanged(); documentSession.cancel(); window.agentSaving = saveDocument({notifyUser:false});"}
        return true;
      })()`);
      await waitForPage(client, 'Boolean(window.agentReleaseSave)');
      assert.equal((await request(`/${isIssue ? 'records' : 'documents'}/${receipt.item_id}`)).body, '较早的保存内容');
      const duringSave = await client.evaluate(`(async () => {
        ${isIssue ? "recordEditorHost.render('保存期间新增的输入', true); markEditorChanged(); recordSession.cancel();" : "documentEditorHost.render('保存期间新增的输入', true); markDocumentChanged(); documentSession.cancel();"}
        window.agentReleaseSave();
        const saved = await window.agentSaving;
        window.fetch = window.agentOriginalFetch;
        ${isIssue ? 'recordSession' : 'documentSession'}.cancel();
        return {complete:Boolean(saved), dirty:${isIssue ? 'recordSession' : 'documentSession'}.dirty, body:${isIssue ? 'localEditorContent()' : 'documentMarkdownContent()'}, draft:${isIssue ? 'readEditorDraft(currentRecord.id)' : 'readDocumentDraft(currentDocument.id)'}?.body};
      })()`);
      assert.deepEqual(duringSave, {complete:false, dirty:true, body:'保存期间新增的输入', draft:'保存期间新增的输入'});
      await client.evaluate(`(async () => { ${isIssue ? 'await saveEditorNow()' : 'await saveDocument({notifyUser:false})'}; return true; })()`);
      await navigate(receipt);
      assert.equal((await request(`/${isIssue ? 'records' : 'documents'}/${receipt.item_id}`)).body, '保存期间新增的输入');
    }
    await client.evaluate(`(async () => { await closeDocumentEditor(); setPage('home'); return true; })()`);
    assert.equal(await client.evaluate(`new URLSearchParams(location.search).has('item')`), false);
    const beforeDocuments = (await request('/documents')).length;
    await client.call('Page.navigate', {url:`${baseUrl}/?item=document&itemId=DOC-999999`});
    await waitForPage(client, `apiAvailable && $('.toast strong').textContent === '无法打开条目'`);
    assert.equal(await client.evaluate(`$('#documentDialog').open`), false);
    assert.equal((await request('/documents')).length, beforeDocuments);
    await client.call('Page.navigate', {url:`${baseUrl}/?item=script&itemId=${encodeURIComponent('<img src=x onerror=alert(1)>')}`});
    await waitForPage(client, `apiAvailable && $('.toast strong').textContent === '打开链接无效'`);
    assert.equal(await client.evaluate(`new URLSearchParams(location.search).has('item')`), false);
    console.log('Agent browser workflows passed: previewed writes, deep links/reload, light/dark desktop/narrow, Markdown roundtrip, unsaved cancel, Agent/UI conflicts, missing/invalid links.');
  } finally {
    client?.close();
    browser?.kill();
    server.kill();
    await delay(200);
    fs.rmSync(base, {recursive:true, force:true, maxRetries:5, retryDelay:200});
  }
}

main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
