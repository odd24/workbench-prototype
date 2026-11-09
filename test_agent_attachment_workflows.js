const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const {DevToolsClient, freePort, browserExecutable, waitForHttp, waitForPage, delay} = require('./test_editor_workflows.js');

async function main() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-attachment-browser-'));
  const screenshots = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-attachment-shots-'));
  const data = path.join(base, 'data'); const credentials = path.join(base, 'credentials');
  const port = await freePort(); const debugPort = await freePort(); const origin = `http://127.0.0.1:${port}`;
  const server = childProcess.spawn('python', ['server.py', '--data-dir', data, '--agent-config-dir', credentials, '--port', String(port), '--seed-demo', '--enable-agent'], {cwd:__dirname, stdio:'ignore', windowsHide:true});
  let browser; let client;
  try {
    await waitForHttp(`${origin}/api/health`);
    const json = async (url, method = 'GET', body, headers = {}) => {
      const response = await fetch(origin + url, {method, headers:{Origin:origin, 'Content-Type':'application/json', ...headers}, body:body === undefined ? undefined : JSON.stringify(body)});
      const value = await response.json(); assert.ok(response.ok, JSON.stringify(value)); return value;
    };
    const status = await json('/api/local/agent-management/status', 'GET', undefined, {'X-Workbench-Management':'1'});
    const managementHeaders = {'X-Workbench-Management':'1', 'X-Workbench-Management-Token':status.management_token};
    const local = (route, method = 'GET', body) => json('/api/local/agent-management/' + route, method, body, managementHeaders);
    const project = await json('/api/projects', 'POST', {name:'附件完整预览中文项目'.repeat(6)});
    const provisioned = await local('clients', 'POST', {workspace_id:status.workspace_id, request_id:crypto.randomUUID(), name:'正式附件专项客户端', scopes:['read', 'propose', 'commit'], kinds:['issue', 'todo', 'info'], project_ids:[project.id], categories:[], minimum_confirmation_mode:'agent_attested'});
    const config = JSON.parse(fs.readFileSync(path.join(credentials, status.workspace_id, `${provisioned.client_id}.json`), 'utf8'));
    const agentHeaders = {Authorization:`Bearer ${config.token}`, 'X-Workbench-Workspace':status.workspace_id};
    const agent = (route, method = 'GET', body) => json('/api/agent/v1/' + route, method, body, agentHeaders);
    const filename = '源文件[方](圆)%# 空格.png';
    const source = path.join(base, filename);
    const bytes = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=', 'base64');
    fs.writeFileSync(source, bytes);
    let catalog = await local('clients');
    const filePreview = await local(`clients/${provisioned.client_id}/files/preview`, 'POST', {workspace_id:status.workspace_id, expected_version:catalog.items.find(item => item.client_id === provisioned.client_id).version, path:source, purposes:['attachment_source'], encoding:'binary', max_bytes:10485760, duration_seconds:3600});
    const approvedFile = await local(`clients/${provisioned.client_id}/files/confirm`, 'POST', {workspace_id:status.workspace_id, expected_version:filePreview.expected_version, preview_id:filePreview.preview_id, preview_digest:filePreview.preview_digest, request_id:crypto.randomUUID(), approved:true});
    assert.ok(approvedFile.file_id);
    browser = childProcess.spawn(browserExecutable(), ['--headless', '--disable-gpu', '--no-first-run', '--disable-extensions', '--disable-background-networking', '--disable-sync', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${path.join(base, 'profile')}`, origin], {stdio:'ignore', windowsHide:true});
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(value => value.json());
    client = new DevToolsClient(pages.find(page => page.type === 'page' && page.url.startsWith(origin)).webSocketDebuggerUrl);
    await client.connect(); await client.call('Page.enable'); await client.call('Runtime.enable');
    await waitForPage(client, 'apiAvailable && projects.length > 0');
    await client.evaluate('applicationFeature.start().then(() => true)');
    const click = selector => client.evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    const fill = (selector, value) => client.evaluate(`(() => { const node = document.querySelector(${JSON.stringify(selector)}); node.value = ${JSON.stringify(value)}; node.dispatchEvent(new Event('change', {bubbles:true})); })()`);
    const confirm = async () => { await waitForPage(client, "$('#appDialog').open"); await click('#appDialogConfirm'); };
    const showSettings = async () => {
      await client.evaluate("setPage('agent_settings')");
      await waitForPage(client, "!agentSettingsFeature.isBusy() && !!document.querySelector('[data-agent-action=upload-policy]')");
      await click(`[data-agent-action=upload-policy][data-client-id="${provisioned.client_id}"]`);
      await waitForPage(client, "!!$('#agentUploadOwner')");
    };
    const capture = async (prefix, selector) => {
      for (const theme of ['light', 'dark']) for (const width of [1440, 390]) {
        await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
        await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'start'});`);
        await delay(100);
        assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
        const shot = await client.call('Page.captureScreenshot', {format:'png'});
        fs.writeFileSync(path.join(screenshots, `${prefix}-${theme}-${width}.png`), Buffer.from(shot.data, 'base64'));
      }
    };
    const authorize = async (kind, ownerId, shots = false) => {
      await showSettings();
      await fill('#agentUploadOwnerKind', kind); await fill('#agentUploadOwner', ownerId);
      await click('[data-agent-upload-source]'); await click('#agentAttachmentWrite');
      await fill('#agentAttachmentConfirmation', 'local_web');
      await click('[data-agent-action=upload-preview]');
      await waitForPage(client, "!!$('#agentUploadPreview')");
      assert.equal(await client.evaluate("$('#agentUploadPreview').textContent.includes('本机网页独立批准') && $('#agentUploadPreview').textContent.includes('共同授权')"), true);
      if (shots) await capture('joint-policy', '#agentUploadPreview');
      await click('[data-agent-action=upload-cancel-preview]');
      assert.equal(await client.evaluate("!!$('#agentUploadPreview')"), false);
      await fill('#agentUploadOwnerKind', kind); await fill('#agentUploadOwner', ownerId);
      await click('[data-agent-upload-source]'); await click('#agentAttachmentWrite');
      await fill('#agentAttachmentConfirmation', 'local_web');
      await click('[data-agent-action=upload-preview]'); await waitForPage(client, "!!$('#agentUploadPreview')");
      await click('[data-agent-action=upload-confirm]'); await confirm();
      await waitForPage(client, `!agentSettingsFeature.isBusy() && !$('#agentUploadPreview') && !document.querySelector('[data-agent-action=upload-resolve]') && $('#agentUploadPanel')?.textContent.includes(${JSON.stringify(` · ${kind} / ${ownerId} · 当前有效`)})`);
      const policies = await agent('capabilities');
      assert.equal(policies.attachment_write.policies.length, 1);
      assert.equal(policies.attachment_write.policies[0].owner_id, ownerId);
      return policies.attachment_write.policies[0];
    };
    const stageProposal = async (kind, ownerId, displayName, policy) => {
      const grant = Object.values(JSON.parse(fs.readFileSync(path.join(credentials, status.workspace_id, 'file-grants.json'), 'utf8')).files)[0];
      const upload = await agent('uploads', 'POST', {request_id:crypto.randomUUID(), policy_id:policy.policy_id, source:{mode:'file', file_id:grant.file_id, source_revision:grant.source_revision}, owner_kind:kind, owner_id:ownerId, filename:grant.display_name, bytes:bytes.length, sha256:crypto.createHash('sha256').update(bytes).digest('hex')});
      await agent(`uploads/${upload.upload_id}/complete`, 'POST', {});
      const target = await agent(`attachment-targets/${kind}/${encodeURIComponent(ownerId)}`);
      return agent('proposals', 'POST', {request_id:crypto.randomUUID(), kind:'attachment', operation:'create', target_id:ownerId, base_revision:target.revision, content:{owner_kind:kind, owner_id:ownerId, upload_id:upload.upload_id, display_name:displayName, category:'', insert_link:kind !== 'project'}});
    };
    const approveProposal = async (proposal, shots = false) => {
      await client.evaluate("setPage('agent_proposals')");
      await waitForPage(client, `!agentProposalsFeature.isBusy() && !!document.querySelector('[data-proposal-id="${proposal.proposal_id}"]')`);
      await click(`[data-proposal-action=review][data-proposal-id="${proposal.proposal_id}"]`);
      await waitForPage(client, "$('#proposalPreviewDialog').open && !agentProposalsFeature.isBusy() && !!document.querySelector('[data-proposal-action=approve]:not(:disabled)')");
      assert.equal(await client.evaluate("$('#proposalPreviewDialog').textContent.includes('未解析') && $('#proposalPreviewDialog').textContent.includes('SHA')"), true);
      assert.equal(fs.existsSync(path.join(data, proposal.normalized_content.binary_relative)), false);
      if (shots) await capture('attachment-preview', '.agent-proposal-detail');
      await click('[data-proposal-action=approve]'); await confirm();
      await waitForPage(client, "!agentProposalsFeature.isBusy() && $('#proposalPreviewDialog').textContent.includes('已入库')");
      const saved = await agent(`proposals/${proposal.proposal_id}`);
      assert.equal(saved.state, 'committed'); assert.equal(saved.current_item.exists, true);
      assert.equal(await client.evaluate(`document.body.textContent.includes(${JSON.stringify(config.token)})`), false);
      await click('[data-proposal-action=close-preview]');
      return saved.receipt;
    };
    const projectPolicy = await authorize('project', project.id, true);
    const projectProposal = await stageProposal('project', project.id, '项目[方](圆)%# 空格.png', projectPolicy);
    const projectReceipt = await approveProposal(projectProposal, true);
    await client.call('Page.navigate', {url:origin + projectReceipt.web_path});
    await waitForPage(client, `projectTab === 'assets' && !!document.querySelector('[data-project-asset-id="${projectReceipt.item_id}"]')`);
    assert.deepEqual(Buffer.from(await fetch(`${origin}/api/project-assets/${encodeURIComponent(project.id)}/${projectReceipt.item_id}`).then(response => response.arrayBuffer())), bytes);
    const info = await json('/api/records', 'POST', {type:'info', title:'有序信息附件', project_id:project.id, body:'必须保留的原文', info_fields:[{name:'字段', value:'  a\n"b"  ', note:'尾部 '}]});
    const recordPolicy = await authorize('info', info.id);
    const recordProposal = await stageProposal('info', info.id, '记录[方](圆)%# 空格.png', recordPolicy);
    const recordReceipt = await approveProposal(recordProposal);
    await client.call('Page.navigate', {url:origin + recordReceipt.web_path});
    await waitForPage(client, `currentRecord?.id === ${JSON.stringify(info.id)} && Boolean($('.editor img')?.naturalWidth)`);
    const originalMarkdown = (await json(`/api/records/${info.id}`)).body;
    assert.equal(await client.evaluate("$('.editor img').getAttribute('alt')"), '记录[方](圆)%# 空格.png');
    await client.evaluate("(async () => { setEditorMode('markdown'); markEditorChanged(); await saveEditorNow(); await closeDrawer(); await openDrawer(" + JSON.stringify(info.id) + "); setEditorMode('wysiwyg'); return true; })()");
    await waitForPage(client, "Boolean($('.editor img')?.naturalWidth)");
    assert.equal((await json(`/api/records/${info.id}`)).body.trim(), originalMarkdown.trim());
    assert.deepEqual((await json(`/api/records/${info.id}`)).info_fields, info.info_fields);
    await client.evaluate('closeDrawer()');
    const encoded = encodeURIComponent(filename).replace(/[!'()*]/g, character => `%${character.charCodeAt(0).toString(16).toUpperCase()}`);
    const documentMarkdown = `![${filename.replace(/([\\`*{}_\[\]<>!])/g, '\\$1')}](./\${img}/${encoded})`;
    const document = await json('/api/documents', 'POST', {title:'共享图片往返', body:documentMarkdown});
    const imagePath = path.join(path.dirname(document.file_path), '${img}', filename);
    fs.mkdirSync(path.dirname(imagePath), {recursive:true}); fs.writeFileSync(imagePath, bytes);
    await client.evaluate(`(async () => { documents = await api('/documents'); openDocument(${JSON.stringify(document.id)}); setDocumentMode('visual'); return true; })()`);
    await waitForPage(client, "Boolean($('#documentVisualEditor img')?.naturalWidth)");
    await client.evaluate("(async () => { documentMarkdownContent(); markDocumentChanged(); await saveDocument({readAfterSave:false, notifyUser:false}); await closeDocumentEditor(); documents = await api('/documents'); openDocument(" + JSON.stringify(document.id) + "); setDocumentMode('visual'); return true; })()");
    await waitForPage(client, "Boolean($('#documentVisualEditor img')?.naturalWidth)");
    assert.equal((await json(`/api/documents/${document.id}`)).body.trim(), documentMarkdown);
    console.log('Attachment browser workflow passed: joint-consent,cancel,complete-preview,local-web,project-result,download,special-filenames,record-and-document-roundtrip,light/dark,1440/390');
    console.log(`Screenshots: ${screenshots}`);
  } catch (error) {
    if (client) console.error('Attachment UI state:', await client.evaluate("({page:currentPage, projectTab, selectedProjectId, projectAssetProjectId, library:projectAssetLibrary, url:location.href, content:$('#kanban')?.textContent?.slice(0,400), notices:document.querySelector('.toast-stack')?.textContent, feedback:$('#agentFeedback')?.textContent, dialog:$('#appDialog')?.textContent, preview:$('#proposalPreviewDialog')?.textContent?.slice(-700)})").catch(() => 'unavailable'));
    throw error;
  } finally {
    client?.close(); browser?.kill(); server.kill(); await delay(200);
    assert.ok(path.resolve(base).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(base, {recursive:true, force:true, maxRetries:5, retryDelay:200});
  }
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
module.exports = {main};
