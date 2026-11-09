const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {DevToolsClient, freePort, browserExecutable, waitForHttp, waitForPage, delay} = require('./test_editor_workflows.js');

async function main() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-document-browser-'));
  const screenshots = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-document-shots-'));
  const port = await freePort(); const debugPort = await freePort(); const origin = `http://127.0.0.1:${port}`;
  const server = childProcess.spawn('python', ['server.py', '--data-dir', path.join(base, 'data'), '--port', String(port), '--disable-agent'], {cwd:__dirname, stdio:'ignore', windowsHide:true});
  let browser; let client;
  try {
    await waitForHttp(`${origin}/api/health`);
    const json = async (route, method = 'GET', body) => {
      const response = await fetch(origin + '/api' + route, {method, headers:{'Content-Type':'application/json'}, body:body === undefined ? undefined : JSON.stringify(body)});
      const value = await response.json(); assert.ok(response.ok, JSON.stringify(value)); return value;
    };
    const document = await json('/documents', 'POST', {title:'中文知识附件'.repeat(12), category:'文档原分类', body:'上传前原文'});
    const other = await json('/documents', 'POST', {title:'另一个文档', body:'保持不变'});
    const filename = '文档 %3A%2F%25[方](圆)%# 空格.png'; const source = path.join(base, filename);
    const bytes = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=', 'base64');
    fs.writeFileSync(source, bytes);
    browser = childProcess.spawn(browserExecutable(), ['--headless', '--disable-gpu', '--no-first-run', '--disable-extensions', '--disable-background-networking', '--disable-sync', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${path.join(base, 'profile')}`, origin], {stdio:'ignore', windowsHide:true});
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(r => r.json());
    client = new DevToolsClient(pages.find(page => page.type === 'page' && page.url.startsWith(origin)).webSocketDebuggerUrl);
    await client.connect(); await client.call('Page.enable'); await client.call('Runtime.enable');
    await waitForPage(client, 'apiAvailable');
    await client.evaluate("applicationFeature.start().then(async () => { documents = await api('/documents'); return true; })");
    await client.evaluate(`openDocument(${JSON.stringify(document.id)}); setDocumentMode('visual'); $('#documentVisualEditor').innerHTML = '<p>上传前原文 · 首次编辑</p>'; markDocumentChanged();`);
    await client.evaluate("window.preUploadFetch = window.fetch; window.fetch = async (...args) => { if (String(args[0]).startsWith('/api/documents/') && args[1]?.method === 'PATCH') return new Response(JSON.stringify({error:'synthetic pre-upload save failure'}), {status:503, headers:{'Content-Type':'application/json'}}); if (String(args[0]).includes('/attachments/uploads/')) throw new Error('upload must not start after failed save'); return preUploadFetch(...args); };");
    await client.evaluate("uploadDocumentAttachment(new File(['never sent'], 'not-sent.txt'))");
    assert.equal(await client.evaluate("!documentUploadActive && !readDocumentUpload() && documentSession.dirty && readDocumentDraft(currentDocument.id).body.includes('首次编辑')"), true);
    assert.equal((await json(`/documents/${document.id}`)).attachments, undefined);
    assert.equal(fs.existsSync(path.join(base, 'data', '.workbench-document-uploads')), false);
    await client.evaluate('window.fetch = preUploadFetch; documentSession.cancel()');
    // Delay a real POST, permitting input while its independent upload state is
    // active. This does not change the server result or skip streaming IO.
    await client.evaluate("window.originalUploadFetch = window.fetch; window.fetch = async (...args) => { if (String(args[0]).includes('/attachments/uploads/') && args[1]?.method === 'POST') await new Promise(resolve => { window.releaseDocumentUpload = resolve; }); return originalUploadFetch(...args); };");
    const dom = await client.call('DOM.getDocument');
    const input = await client.call('DOM.querySelector', {nodeId:dom.root.nodeId, selector:'#documentAttachmentInput'});
    await client.call('DOM.setFileInputFiles', {nodeId:input.nodeId, files:[source]});
    await waitForPage(client, "documentUploadActive?.phase === 'uploading' && Boolean(readDocumentUpload())");
    await client.evaluate("$('#documentVisualEditor').innerHTML += '<p>上传期间继续输入</p>'; markDocumentChanged();");
    assert.equal(await client.evaluate('documentSession.timer === null'), true);
    await client.evaluate(`openDocument(${JSON.stringify(other.id)})`);
    assert.equal(await client.evaluate('currentDocument.id'), document.id);
    assert.equal(await client.evaluate('closeDocumentEditor()'), false);
    await client.evaluate('releaseDocumentUpload();');
    await waitForPage(client, "!documentUploadActive && !readDocumentUpload() && !documentSession.dirty && !documentSession.saving");
    let saved = await json(`/documents/${document.id}`);
    assert.ok(saved.body.includes('首次编辑') && saved.body.includes('上传期间继续输入'));
    assert.equal(saved.attachments.length, 1);
    assert.equal((saved.body.match(/!\[/g) || []).length, 1);
    await waitForPage(client, "Boolean($('#documentVisualEditor img')?.naturalWidth)");
    const name = typeof saved.attachments[0] === 'string' ? JSON.parse(saved.attachments[0]).name : saved.attachments[0].name;
    assert.deepEqual(Buffer.from(await fetch(`${origin}/api/attachments/${document.id}/${encodeURIComponent(name)}`).then(r => r.arrayBuffer())), bytes);
    const targets = await json('/reference-targets');
    assert.equal(targets.find(x => x.id === document.id).attachments[0].name, name);
    // Lose a successful response, refresh, recover the draft and query the
    // original stable operation. Never resend a file or replace the draft body.
    await client.evaluate("window.fetch = async (...args) => { const response = await originalUploadFetch(...args); if (String(args[0]).includes('/attachments/uploads/') && args[1]?.method === 'POST') throw new Error('synthetic lost upload response'); return response; }; uploadDocumentAttachment(new File(['second bytes'], '第二附件.txt')); ");
    await waitForPage(client, "!documentUploadActive && Boolean(readDocumentUpload())");
    await client.evaluate("$('#documentVisualEditor').appendChild(Object.assign(document.createElement('p'), {textContent:'丢响应后仍有输入'})); markDocumentChanged(); handlePageHide();");
    await client.evaluate('window.documentReloadMarker = true');
    await client.call('Page.reload');
    await waitForPage(client, "typeof window.documentReloadMarker === 'undefined' && typeof applicationFeature !== 'undefined' && apiAvailable");
    await client.evaluate("applicationFeature.start().then(async () => { documents = await api('/documents'); return true; })");
    await client.evaluate(`openDocument(${JSON.stringify(document.id)}); setDocumentMode('visual');`);
    assert.equal(await client.evaluate('Boolean(readDocumentUpload()) && documentSession.dirty'), true);
    await client.evaluate('resolveDocumentUpload()');
    await waitForPage(client, '!documentUploadActive && !readDocumentUpload() && !documentSession.dirty && !documentSession.saving');
    saved = await json(`/documents/${document.id}`);
    assert.equal(saved.attachments.length, 2);
    assert.ok(saved.body.includes('丢响应后仍有输入'));
    assert.equal((saved.body.match(/第二附件/g) || []).length, 1);
    assert.equal(await client.evaluate("Boolean($('#documentVisualEditor a[data-markdown-src]'))"), true);
    await client.evaluate("documentOutlineCollapsed = true; updateDocumentOutline();");
    for (const mode of ['visual', 'read']) {
      await client.evaluate(`setDocumentMode(${JSON.stringify(mode)})`);
      for (const theme of ['light', 'dark']) for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'})`);
        await delay(80);
        assert.equal(await client.evaluate("$('#documentDialog').scrollWidth > $('#documentDialog').clientWidth + 1"), false);
        const shot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `${mode}-${theme}-${width}.png`), Buffer.from(shot.data, 'base64'));
      }
    }
    await client.evaluate("(async () => { const markdown = documentMarkdownContent(); renderMarkdownEditor($('#documentVisualEditor'), markdown, true); markDocumentChanged(); await saveDocument({readAfterSave:false, notifyUser:false}); await closeDocumentEditor(); documents = await api('/documents'); openDocument(" + JSON.stringify(document.id) + "); setDocumentMode('visual'); return true; })()");
    await waitForPage(client, "Boolean($('#documentVisualEditor img')?.naturalWidth)");
    assert.equal((await json(`/documents/${document.id}`)).body.trim(), saved.body.trim());
    assert.equal((await json(`/documents/${other.id}`)).body, '保持不变');
    await client.evaluate("window.originalUploadFetch = window.fetch; window.fetch = async (...args) => { if (String(args[0]).includes('/attachments/uploads/') && args[1]?.method === 'POST') await new Promise(resolve => { window.releaseConflictUpload = resolve; }); return originalUploadFetch(...args); }; void uploadDocumentAttachment(new File(['conflict bytes'], 'conflict.txt'));");
    await waitForPage(client, "documentUploadActive?.phase === 'uploading'");
    await client.evaluate("$('#documentVisualEditor').appendChild(Object.assign(document.createElement('p'), {textContent:'409仍保留工作台输入'})); markDocumentChanged();");
    const beforeConflict = await json(`/documents/${document.id}`);
    await json(`/documents/${document.id}`, 'PATCH', {body:beforeConflict.body + '\n\n磁盘新修改', expected_revision:beforeConflict.revision});
    await client.evaluate('releaseConflictUpload()');
    await waitForPage(client, '!documentUploadActive && Boolean(readDocumentUpload())');
    await client.evaluate('resolveDocumentUpload()');
    await waitForPage(client, "!documentUploadActive && !readDocumentUpload() && $('#conflictDialog').open");
    assert.equal(await client.evaluate("$('#localConflictContent').value.includes('409仍保留工作台输入') && $('#externalConflictContent').value.includes('磁盘新修改')"), true);
    assert.equal((await json(`/documents/${document.id}`)).attachments.length, 2);
    await client.evaluate("$('#conflictLocal').click()");
    await waitForPage(client, "!$('#conflictDialog').open && !documentSession.dirty && !documentSession.saving");
    assert.ok((await json(`/documents/${document.id}`)).body.includes('409仍保留工作台输入'));
    await client.evaluate("(async () => { await closeDocumentEditor(); setPage('settings'); return true; })()");
    await waitForPage(client, "Boolean($('#reportDocumentUploads'))");
    await client.evaluate("$('#reportDocumentUploads').click()");
    await waitForPage(client, "Boolean(document.querySelector('[data-document-upload-state=completed]'))");
    await client.evaluate("$('#cleanupDocumentUploads').click()");
    await waitForPage(client, "[...document.querySelectorAll('#documentUploadReport p')].length === 2");
    // Wait on actual durable compaction rather than treating the old report as
    // proof that the maintenance POST has finished.
    const uploadRoot = path.join(base, 'data', '.workbench-document-uploads');
    const compactDeadline = Date.now() + 10000;
    while (Date.now() < compactDeadline) {
      if (fs.readdirSync(uploadRoot).every(id => JSON.parse(fs.readFileSync(path.join(uploadRoot, id, 'operation.json'), 'utf8')).compacted)) break;
      await delay(40);
    }
    assert.equal(fs.readdirSync(uploadRoot).every(id => JSON.parse(fs.readFileSync(path.join(uploadRoot, id, 'operation.json'), 'utf8')).compacted), true);
    const externalDir = path.join(path.dirname(document.file_path), 'outside'); fs.mkdirSync(externalDir);
    const externalBytes = Buffer.concat([bytes, Buffer.from('external image marker')]);
    const encodedName = encodeURIComponent(filename).replace(/[!'()*]/g, character => `%${character.charCodeAt(0).toString(16).toUpperCase()}`);
    fs.writeFileSync(path.join(externalDir, filename), externalBytes);
    fs.writeFileSync(path.join(externalDir, encodedName), Buffer.concat([bytes, Buffer.from('wrong encoded filename bytes')]));
    await client.evaluate(`(async () => { documents = await api('/documents'); openDocument(${JSON.stringify(document.id)}); setDocumentMode('visual'); const external = documentAttachmentMarkdown({name:'外部同名', path:${JSON.stringify('./outside/' + filename)}, mime:'image/png'}); renderMarkdownEditor($('#documentVisualEditor'), documentMarkdownContent() + '\\n\\n' + external, true); markDocumentChanged(); await saveDocument({readAfterSave:false, notifyUser:false}); return true; })()`);
    await waitForPage(client, "Boolean($('#documentVisualEditor img[alt=外部同名]')?.naturalWidth)");
    const externalUrl = await client.evaluate("$('#documentVisualEditor img[alt=外部同名]').src");
    assert.ok(externalUrl.includes('/api/markdown-images/'));
    assert.deepEqual(Buffer.from(await fetch(externalUrl).then(response => response.arrayBuffer())), externalBytes);
    const mediaProject = await json('/projects', 'POST', {name:'原媒体预览兼容'});
    const mediaRecord = await json('/records', 'POST', {type:'issue', project_id:mediaProject.id, title:'媒体兼容记录'});
    const wave = Buffer.alloc(44 + 16000);
    wave.write('RIFF', 0); wave.writeUInt32LE(wave.length - 8, 4); wave.write('WAVEfmt ', 8); wave.writeUInt32LE(16, 16); wave.writeUInt16LE(1, 20); wave.writeUInt16LE(1, 22); wave.writeUInt32LE(8000, 24); wave.writeUInt32LE(16000, 28); wave.writeUInt16LE(2, 32); wave.writeUInt16LE(16, 34); wave.write('data', 36); wave.writeUInt32LE(16000, 40);
    const video = Buffer.from(await client.evaluate(`(async () => {
      const canvas = document.createElement('canvas'); canvas.width = 16; canvas.height = 16;
      const context = canvas.getContext('2d'); context.fillStyle = 'blue'; context.fillRect(0, 0, 16, 16);
      const stream = canvas.captureStream(10); const recorder = new MediaRecorder(stream, {mimeType:'video/webm;codecs=vp8'}); const chunks = [];
      recorder.ondataavailable = event => chunks.push(event.data);
      const stopped = new Promise(resolve => { recorder.onstop = resolve; }); recorder.start();
      await new Promise(resolve => setTimeout(resolve, 150)); context.fillStyle = 'green'; context.fillRect(0, 0, 16, 16);
      await new Promise(resolve => setTimeout(resolve, 200)); recorder.stop(); await stopped; stream.getTracks().forEach(track => track.stop());
      return Array.from(new Uint8Array(await new Blob(chunks, {type:'video/webm'}).arrayBuffer()));
    })()`));
    for (const [name, content, type] of [['preview.wav', wave, 'audio'], ['preview.webm', video, 'video']]) {
      const upload = async route => { const response = await fetch(origin + '/api' + route, {method:'POST', headers:{'Content-Type':'application/octet-stream'}, body:content}); const value = await response.json(); assert.ok(response.ok, JSON.stringify(value)); return value; };
      const item = await upload(`/records/${mediaRecord.id}/attachments/upload?name=${name}`);
      const asset = await upload(`/projects/${encodeURIComponent(mediaProject.id)}/assets/upload?name=${name}`);
      for (const route of [`/attachments/${mediaRecord.id}/${encodeURIComponent(item.name)}`, `/project-assets/${encodeURIComponent(mediaProject.id)}/${asset.id}`]) {
        const url = origin + '/api' + route; const response = await fetch(url);
        assert.ok(response.headers.get('Content-Type').startsWith(type + '/'));
        assert.ok(response.headers.get('Content-Disposition').startsWith('inline;'));
        assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff');
        assert.deepEqual(Buffer.from(await response.arrayBuffer()), content);
        const target = await client.call('Target.createTarget', {url});
        let mediaClient;
        try {
          const deadline = Date.now() + 5000; let page;
          while (Date.now() < deadline && !page) { page = (await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(result => result.json())).find(value => value.id === target.targetId); if (!page) await delay(30); }
          assert.ok(page); mediaClient = new DevToolsClient(page.webSocketDebuggerUrl); await mediaClient.connect(); await mediaClient.call('Page.enable'); await mediaClient.call('Runtime.enable');
          await waitForPage(mediaClient, "Boolean(document.querySelector('video,audio'))");
          await mediaClient.call('Runtime.evaluate', {expression:"document.querySelector('video,audio').play().catch(() => {}); true", awaitPromise:true, returnByValue:true, userGesture:true});
          await waitForPage(mediaClient, "document.querySelector('video,audio').readyState >= 2 && !document.querySelector('video,audio').error");
          if (type === 'video') assert.equal(await mediaClient.evaluate("document.querySelector('video').videoWidth"), 16);
          else assert.equal(await mediaClient.evaluate("document.querySelector('video,audio').duration"), 1);
        } finally { mediaClient?.close(); await client.call('Target.closeTarget', {targetId:target.targetId}); }
      }
    }
    console.log('Document attachment workflows passed: ordinary upload without Agent, save-before-upload and failure guard, concurrent typing, autosave pause/resume, switch/close guards, lost response/reload/draft/query, exact-once link, percent names, same-basename external image isolation, download, references, 409 conflict, maintenance UI, native record/project audio/video previews, Markdown roundtrip, light/dark 1440/390');
    console.log(`Screenshots: ${screenshots}`);
  } catch (error) {
    if (client) console.error('Document UI state:', await client.evaluate("({api:typeof apiAvailable === 'undefined' ? 'undefined' : apiAvailable, docs:typeof documents === 'undefined' ? 'undefined' : documents.length, text:document.body.innerText.slice(-1600)})").catch(e => e.message));
    throw error;
  } finally {
    client?.close(); browser?.kill(); server.kill(); await delay(200);
    assert.ok(path.resolve(base).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(base, {recursive:true, force:true, maxRetries:5, retryDelay:200});
  }
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
module.exports = {main};
