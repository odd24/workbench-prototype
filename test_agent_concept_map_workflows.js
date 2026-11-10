const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {DevToolsClient, freePort, browserExecutable, waitForHttp, waitForPage, delay} = require('./test_editor_workflows.js');

async function main() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-agent-concept-'));
  const screenshots = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-agent-concept-shots-'));
  const data = path.join(base, 'data'), credentials = path.join(base, 'credentials');
  const port = await freePort(), debugPort = await freePort(), origin = `http://127.0.0.1:${port}`;
  const server = childProcess.spawn(process.env.PYTHON || 'python', ['server.py', '--data-dir', data, '--agent-config-dir', credentials, '--seed-demo', '--enable-agent', '--port', String(port)], {cwd:__dirname, stdio:'ignore', windowsHide:true});
  let browser, client;
  try {
    await waitForHttp(`${origin}/api/health`);
    async function json(route, options = {}) {
      const response = await fetch(origin + route, {...options, headers:{'Content-Type':'application/json', ...options.headers}});
      const value = await response.json();
      assert.ok(response.ok, `${route}: ${response.status} ${JSON.stringify(value)}`);
      return value;
    }
    const status = await json('/api/local/agent-management/status', {headers:{'X-Workbench-Management':'1'}});
    const managementHeaders = {'X-Workbench-Management':'1', 'X-Workbench-Management-Token':status.management_token, Origin:origin};
    const management = (route, method = 'GET', value) => json(`/api/local/agent-management/${route}`, {method, headers:managementHeaders, ...(value ? {body:JSON.stringify(value)} : {})});
    const project = (await json('/api/projects'))[0];
    const background = await json('/api/concept-maps', {method:'POST', body:JSON.stringify({title:'后台原画布', project_id:project.id,
      nodes:[{id:'a', text:'长中文概念与完整样式', note:'完整多行说明\n保留空格  和引号"', x:100, y:120}, {id:'b', text:'另一概念', x:420, y:220}],
      edges:[{id:'e', from:'a', to:'b', label:'', arrowhead:'both', dashed:true}], viewport:{x:10, y:20, zoom:1}})});
    const created = await management('clients', 'POST', {workspace_id:status.workspace_id, request_id:'browser-graph-client', name:'图提案浏览器验收', scopes:['read', 'propose', 'commit'], project_ids:[project.id], categories:[], minimum_confirmation_mode:'local_web'});
    const grants = {schema_version:1, grants:[{capability:'concept_maps.read', operations:['read'], resources:[{type:'project', id:project.id}], minimum_confirmation_mode:'agent_attested'}, {capability:'concept_maps.write', operations:['create', 'update'], resources:[{type:'project', id:project.id}], minimum_confirmation_mode:'local_web'}]};
    const grantPreview = await management(`clients/${created.client_id}/concept-maps/preview`, 'POST', {workspace_id:status.workspace_id, expected_version:created.version, grants});
    await management(`clients/${created.client_id}/concept-maps/confirm`, 'POST', {workspace_id:status.workspace_id, expected_version:created.version, preview_id:grantPreview.preview_id, preview_digest:grantPreview.preview_digest, request_id:'browser-graph-grant', approved:true});
    const config = JSON.parse(fs.readFileSync(path.join(credentials, status.workspace_id, `${created.client_id}.json`), 'utf8'));
    const agentHeaders = {'Authorization':`Bearer ${config.token}`, 'X-Workbench-Workspace':status.workspace_id};
    const agent = (route, method = 'GET', value) => json(`/api/agent/v1/${route}`, {method, headers:agentHeaders, ...(value ? {body:JSON.stringify(value)} : {})});
    const graphKeys = ['version', 'title', 'project_id', 'category', 'focus_question', 'theme', 'viewport', 'nodes', 'edges'];
    const graph = Object.fromEntries(graphKeys.map(key => [key, background[key]]));
    graph.title = '完整概念图提案与长中文验收'.repeat(3);
    graph.edges[0].label = '完整关系文字';
    graph.edges[0].color = '#a13c6f';
    const editedRelationLabel = '关系长中文'.repeat(10) + '\n第二行 []()%# <img src=x onerror=window.__graphXss=true>';
    assert.ok(editedRelationLabel.length <= 120);
    graph.nodes[0].note = '<script>window.__graphXss = true</script>\n完整说明与换行  引号"';
    const proposal = await agent('proposals', 'POST', {request_id:'browser-graph-proposal', kind:'concept_map', operation:'create', content:{graph}});
    const agentPreview = await agent(`proposals/${proposal.proposal_id}/preview`);
    assert.equal(agentPreview.prepared_graph.nodes[0].note, graph.nodes[0].note);
    assert.equal(fs.existsSync(path.join(data, 'concept-maps', `${proposal.target_id}.json`)), false);
    browser = childProcess.spawn(browserExecutable(), ['--headless', '--disable-gpu', '--no-first-run', '--disable-extensions', '--disable-background-networking', '--disable-sync', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${path.join(base, 'profile')}`, origin], {stdio:'ignore', windowsHide:true});
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`);
    const pages = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(response => response.json());
    client = new DevToolsClient(pages.find(page => page.type === 'page' && page.url.startsWith(origin)).webSocketDebuggerUrl);
    await client.connect(); await client.call('Page.enable'); await client.call('Runtime.enable');
    await waitForPage(client, 'apiAvailable && projects.length > 0');
    await client.evaluate('applicationFeature.start().then(() => true)');
    const click = selector => client.evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    await client.evaluate(`setPage('concept_maps').then(() => conceptMapFeature.open(${JSON.stringify(background.id)})).then(() => true)`);
    await waitForPage(client, '!!Workbench.appState.editorState.currentConceptMap');
    await client.evaluate("setPage('agent_proposals').then(() => true)");
    await waitForPage(client, `!!document.querySelector('[data-proposal-id="${proposal.proposal_id}"]')`);
    // Leave a dirty main canvas and stop only its existing autosave timer.
    await client.evaluate(`(() => { const node = $('#conceptMapTitle'); node.value = '后台未保存输入'; node.dispatchEvent(new Event('input', {bubbles:true})); clearTimeout(Workbench.appState.draftState.conceptMapSaveTimer); Workbench.appState.draftState.conceptMapSaveTimer = null; window.__background = JSON.stringify(Workbench.appState.editorState.currentConceptMap); window.__drafts = JSON.stringify({...localStorage}); window.__graphWrites = []; window.__graphFetch = window.fetch.bind(window); window.fetch = (...args) => { if (String(args[0]).includes('/concept-maps/') && args[1]?.method === 'PATCH') window.__graphWrites.push(String(args[0])); return window.__graphFetch(...args); }; })()`);
    const review = async () => {
      await click(`[data-proposal-action="review"][data-proposal-id="${proposal.proposal_id}"]`);
      await waitForPage(client, "document.querySelector('[data-proposal-graph-state]')?.textContent.includes('全部明细已载入')");
    };
    await review();
    assert.equal(await client.evaluate("document.querySelectorAll('[data-concept-readonly-node]').length"), 2);
    assert.equal(await client.evaluate("document.querySelectorAll('[data-concept-readonly-edge]').length"), 1);
    assert.equal(await client.evaluate("document.querySelectorAll('[data-concept-readonly] [contenteditable],[data-concept-readonly] [data-concept-port]').length"), 0);
    assert.equal(await client.evaluate("window.__graphXss === true"), false);
    assert.equal(await client.evaluate("!!document.querySelector('[data-proposal-action=approve]').disabled"), false);
    assert.equal(await client.evaluate(`document.querySelector('[data-proposal-graph-canvas]').textContent.includes('完整关系文字')`), true);
    const initialTransform = await client.evaluate("document.querySelector('[data-concept-readonly] .concept-map-canvas').style.transform");
    await click('[data-concept-view="in"]');
    assert.notEqual(await client.evaluate("document.querySelector('[data-concept-readonly] .concept-map-canvas').style.transform"), initialTransform);
    await client.evaluate(`(() => { const node = document.querySelector('.concept-preview-shell'); node.focus(); for (const [key, code, ctrlKey] of [['Delete','Delete',false],['z','KeyZ',true],['v','KeyV',true],['ArrowRight','ArrowRight',false]]) node.dispatchEvent(new KeyboardEvent('keydown',{key,code,ctrlKey,bubbles:true})); const data = new DataTransfer(); data.setData('text/plain','不能粘贴进主画布'); node.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true})); })()`);
    assert.equal(await client.evaluate('JSON.stringify(Workbench.appState.editorState.currentConceptMap) === window.__background'), true);
    assert.equal(await client.evaluate('JSON.stringify({...localStorage}) === window.__drafts'), true);
    assert.deepEqual(await client.evaluate('window.__graphWrites'), []);
    for (const theme of ['light', 'dark']) for (const width of [1440, 390]) {
      await client.call('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
      await client.evaluate(`document.body.classList.toggle('dark', ${theme === 'dark'}); document.querySelector('.agent-proposal-preview-body').scrollTop = 0;`);
      await delay(100);
      await click('[data-concept-view="fit"]');
      await client.evaluate("document.querySelector('.concept-preview-shell').scrollIntoView({block:'center'});");
      assert.equal(await client.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), false);
      assert.equal(await client.evaluate("(() => { const shell = document.querySelector('.concept-preview-shell').getBoundingClientRect(); return [...document.querySelectorAll('[data-concept-readonly-node]')].every(node => { const rect = node.getBoundingClientRect(); return rect.left >= shell.left && rect.right <= shell.right && rect.top >= shell.top && rect.bottom <= shell.bottom; }); })()"), true);
      const screenshot = await client.call('Page.captureScreenshot', {format:'png'});
      fs.writeFileSync(path.join(screenshots, `graph-preview-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
    }
    await client.call('Emulation.setDeviceMetricsOverride', {width:1440, height:1000, deviceScaleFactor:1, mobile:false});
    for (let index = 0; index < 3; index += 1) {
      await click('[data-proposal-action="close-preview"]');
      await waitForPage(client, "!document.querySelector('#proposalPreviewDialog').open");
      assert.equal(await client.evaluate("document.querySelectorAll('[data-concept-readonly]').length"), 0);
      await review();
    }
    // A failed renderer discards the visible ticket and cannot approve old data.
    await click('[data-proposal-action="close-preview"]');
    await client.evaluate("window.__graphFactory = Workbench.conceptMap; Workbench.conceptMap = {create:() => { throw new Error('synthetic renderer failure'); }};");
    await click(`[data-proposal-action="review"][data-proposal-id="${proposal.proposal_id}"]`);
    await waitForPage(client, "document.querySelector('[data-proposal-graph-state]')?.textContent.includes('载入失败')");
    assert.equal(await client.evaluate("document.querySelector('[data-proposal-action=approve]').disabled"), true);
    await click('[data-proposal-action="approve"]');
    assert.equal(fs.existsSync(path.join(data, 'concept-maps', `${proposal.target_id}.json`)), false);
    await client.evaluate('Workbench.conceptMap = window.__graphFactory');
    await click('[data-proposal-action="close-preview"]');
    // A response arriving after close cannot mount a canvas or revive its ticket.
    await client.evaluate(`window.__lateGraphFetch = window.fetch; window.__lateGraphRelease = null; window.fetch = async (...args) => { const response = await window.__lateGraphFetch(...args); if (String(args[0]).includes('/proposals/${proposal.proposal_id}/preview')) { await new Promise(resolve => { window.__lateGraphRelease = resolve; }); } return response; };`);
    await click(`[data-proposal-action="review"][data-proposal-id="${proposal.proposal_id}"]`);
    await waitForPage(client, '!!window.__lateGraphRelease');
    await click('[data-proposal-action="close-preview"]');
    await client.evaluate('window.fetch = window.__lateGraphFetch; window.__lateGraphRelease(); true');
    await delay(100);
    assert.equal(await client.evaluate("document.querySelectorAll('[data-concept-readonly]').length"), 0);
    assert.equal(await client.evaluate("document.querySelector('#proposalPreviewDialog').open"), false);
    await review();
    await click('[data-proposal-action="approve"]');
    await waitForPage(client, "$('#appDialog').open");
    await click('#appDialogConfirm');
    await waitForPage(client, "document.querySelector('#proposalPreviewDialog')?.textContent.includes('已入库') && !agentProposalsFeature.isBusy()");
    assert.equal(fs.existsSync(path.join(data, 'concept-maps', `${proposal.target_id}.json`)), true);
    const committed = JSON.parse(fs.readFileSync(path.join(data, 'concept-maps', `${proposal.target_id}.json`), 'utf8'));
    assert.equal(committed.nodes[0].note, graph.nodes[0].note);
    assert.equal(await client.evaluate('JSON.stringify(Workbench.appState.editorState.currentConceptMap) === window.__background'), true);
    assert.deepEqual(await client.evaluate('window.__graphWrites'), []);
    const receiptLink = await client.evaluate("document.querySelector('#proposalPreviewDialog a[href*=concept_map]')?.getAttribute('href')");
    assert.equal(receiptLink, `/?item=concept_map&itemId=${proposal.target_id}`);
    const committedPath = path.join(data, 'concept-maps', `${proposal.target_id}.json`);
    const committedBytes = fs.readFileSync(committedPath);
    await client.evaluate('window.fetch = window.__graphFetch; true');
    await click('[data-proposal-concept-result]');
    await waitForPage(client, `currentPage === 'concept_maps' && Workbench.appState.editorState.currentConceptMap?.id === ${JSON.stringify(proposal.target_id)}`);
    assert.equal(await client.evaluate('location.search'), `?item=concept_map&itemId=${proposal.target_id}`);
    await delay(900);
    assert.deepEqual(fs.readFileSync(committedPath), committedBytes, 'opening a v2 edge label must not migrate IDs or autosave');
    assert.equal(await client.evaluate("$('#conceptMapLabels [data-concept-edge-label=e]').textContent"), '完整关系文字');
    await client.evaluate(`(() => { const label = $('#conceptMapLabels [data-concept-edge-label=e]'); label.dispatchEvent(new MouseEvent('dblclick', {bubbles:true})); label.textContent = ${JSON.stringify(editedRelationLabel)}; label.blur(); })()`);
    assert.equal(await client.evaluate('conceptMapFeature.flushSave()'), true);
    await client.evaluate(`conceptMapFeature.open(${JSON.stringify(proposal.target_id)}).then(() => true)`);
    const edited = JSON.parse(fs.readFileSync(committedPath, 'utf8'));
    assert.deepEqual(edited.nodes.map(node => node.id), ['a', 'b']);
    assert.deepEqual(edited.edges.map(edge => edge.id), ['e']);
    assert.equal(edited.edges[0].dashed, true);
    assert.equal(edited.edges[0].arrowhead, 'both');
    assert.equal(edited.edges[0].label, editedRelationLabel);
    assert.equal(edited.edges[0].color, '#a13c6f');
    assert.equal(await client.evaluate('window.__graphXss === true'), false);
    await client.evaluate(`window.__graphDownloads = []; window.__graphCanvasText = []; window.__anchorClick = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function() { if (this.download) { window.__graphDownloads.push({name:this.download, header:this.href.slice(0,70)}); return; } return window.__anchorClick.call(this); }; window.__graphStroke = []; window.__stroke = CanvasRenderingContext2D.prototype.stroke; CanvasRenderingContext2D.prototype.stroke = function(...args) { window.__graphStroke.push(this.strokeStyle); return window.__stroke.apply(this,args); }; window.__fillText = CanvasRenderingContext2D.prototype.fillText; CanvasRenderingContext2D.prototype.fillText = function(...args) { const point = new DOMPoint(args[1],args[2]).matrixTransform(this.getTransform()); window.__graphCanvasText.push({text:args[0], x:point.x, y:point.y, half:this.measureText(args[0]).width * this.getTransform().a / 2, width:this.canvas.width, height:this.canvas.height}); return window.__fillText.apply(this,args); }; window.__createGraphUrl = URL.createObjectURL; URL.createObjectURL = blob => { blob.text().then(value => { window.__graphJson = value; }); return window.__createGraphUrl(blob); };`);
    await click('#exportConceptMap');
    const renderedLines = await client.evaluate('window.__graphCanvasText');
    for (const line of editedRelationLabel.split('\n')) {
      const rendered = renderedLines.find(item => item.text === line);
      assert.ok(rendered, 'PNG retains each full relation line');
      assert.ok(rendered.x - rendered.half >= 0 && rendered.x + rendered.half <= rendered.width && rendered.y >= 0 && rendered.y <= rendered.height, 'PNG relation stays within scaled export bounds');
      assert.ok(rendered.width <= 5000 && rendered.height <= 5000);
    }
    assert.equal(await client.evaluate("window.__graphStroke.includes('#a13c6f')"), true);
    assert.equal(await client.evaluate("window.__graphDownloads.some(item => item.header.startsWith('data:image/png;base64,iVBORw0KGgo'))"), true);
    await click('#conceptMapMore');
    await click('[data-export-concept-json]');
    await waitForPage(client, '!!window.__graphJson');
    const exported = await client.evaluate('JSON.parse(window.__graphJson)');
    assert.deepEqual(exported.edges, edited.edges);
    assert.deepEqual(exported.nodes, edited.nodes);
    assert.equal(Object.hasOwn(exported, 'revision'), false);
    await client.evaluate('HTMLAnchorElement.prototype.click = window.__anchorClick; CanvasRenderingContext2D.prototype.fillText = window.__fillText; CanvasRenderingContext2D.prototype.stroke = window.__stroke; URL.createObjectURL = window.__createGraphUrl; true');
    const fullRead = await agent(`concept-maps/${proposal.target_id}`);
    assert.equal(fullRead.graph.edges[0].label, edited.edges[0].label);
    assert.equal(fullRead.editable_graph.nodes.length, 2);
    const large = {...graph, title:'500节点1000关系完整图'};
    large.nodes = Array.from({length:500}, (_, index) => ({...graph.nodes[0], id:`n${index}`, text:`节点${index}`, note:'', x:(index % 25) * 180, y:Math.floor(index / 25) * 100}));
    large.edges = Array.from({length:1000}, (_, index) => ({...graph.edges[0], id:`e${index}`, from:`n${index % 500}`, to:`n${(index + 1) % 500}`, label:''}));
    const largeProposal = await agent('proposals', 'POST', {request_id:'browser-large-graph', kind:'concept_map', operation:'create', content:{graph:large}});
    await client.evaluate("setPage('agent_proposals').then(() => true)");
    await waitForPage(client, `!!document.querySelector('[data-proposal-id="${largeProposal.proposal_id}"]')`);
    await click(`[data-proposal-action="review"][data-proposal-id="${largeProposal.proposal_id}"]`);
    await waitForPage(client, "document.querySelector('[data-proposal-graph-state]')?.textContent.includes('500 个节点、1000 条关系的全部明细已载入')");
    assert.deepEqual(await client.evaluate("[document.querySelectorAll('[data-concept-readonly-node]').length,document.querySelectorAll('[data-concept-readonly-edge]').length,document.querySelectorAll('[data-graph-node-details]').length,document.querySelectorAll('[data-graph-edge-details]').length]"), [500,1000,500,1000]);
    assert.equal(await client.evaluate("document.querySelector('[data-proposal-action=approve]').disabled"), false);
    await click('[data-proposal-action="preview-next"]');
    await waitForPage(client, "document.querySelector('[data-proposal-graph-state]')?.textContent.includes('2 个节点、1 条关系的全部明细已载入')");
    assert.equal(await client.evaluate("document.querySelector('[data-proposal-action=approve]').disabled"), true);
    assert.equal(await client.evaluate("document.querySelectorAll('[data-concept-readonly-node]').length"), 2);
    await click('[data-proposal-action="preview-previous"]');
    await waitForPage(client, "document.querySelector('[data-proposal-graph-state]')?.textContent.includes('500 个节点、1000 条关系的全部明细已载入')");
    assert.equal(await client.evaluate("document.querySelector('[data-proposal-action=approve]').disabled"), false);
    await click('[data-proposal-action="close-preview"]');
    assert.equal(await client.evaluate("document.querySelectorAll('[data-concept-readonly]').length"), 0);
    await agent(`proposals/${largeProposal.proposal_id}/cancel`, 'POST', {expected_version:1});
    await client.evaluate("setPage('concept_maps').then(() => true)");
    await client.evaluate(`conceptMapFeature.open(${JSON.stringify(proposal.target_id)}).then(() => true)`);
    await client.evaluate("(() => { const node = $('#conceptMapTitle'); node.value = '当前画布本地输入仍保留'; node.dispatchEvent(new Event('input', {bubbles:true})); clearTimeout(Workbench.appState.draftState.conceptMapSaveTimer); Workbench.appState.draftState.conceptMapSaveTimer = null; })()");
    const updatingRead = await agent(`concept-maps/${proposal.target_id}`);
    const updateCandidate = updatingRead.editable_graph;
    updateCandidate.title = 'Agent更新当前画布的磁盘版';
    const updating = await agent('proposals', 'POST', {request_id:'browser-graph-external-update', kind:'concept_map', operation:'update', target_id:proposal.target_id, base_revision:updatingRead.revision, content:{graph:updateCandidate}});
    const updatePreview = await management(`proposals/${updating.proposal_id}/preview`);
    const updateApproval = await management(`proposals/${updating.proposal_id}/approve`, 'POST', {workspace_id:status.workspace_id, version:1, preview_digest:updatePreview.preview.preview_digest, preview_ticket:updatePreview.preview_ticket, request_id:'browser-graph-external-approve'});
    assert.equal(updateApproval.state, 'completed');
    assert.equal(await client.evaluate('conceptMapFeature.flushSave()'), false);
    assert.equal(await client.evaluate("$('#conceptMapTitle').value"), '当前画布本地输入仍保留');
    assert.equal(JSON.parse(fs.readFileSync(committedPath, 'utf8')).title, 'Agent更新当前画布的磁盘版');
    assert.equal(await client.evaluate("!!localStorage.getItem('workbench-concept-map-draft:' + window.workbenchDataDir + ':' + Workbench.appState.editorState.currentConceptMap.id)"), true);
    await click('#conceptMapResolveConflict');
    await waitForPage(client, "$('#appDialog').open");
    await client.evaluate("new Promise(resolve => { $('#appDialog').addEventListener('close', () => setTimeout(resolve, 0), {once:true}); document.querySelector('[data-app-dialog-choice=disk]').click(); })");
    await waitForPage(client, "$('#conceptMapTitle').value === 'Agent更新当前画布的磁盘版'");
    await client.evaluate("$('#conceptMapTitle').blur(); $('#conceptMapCanvasShell').dispatchEvent(new KeyboardEvent('keydown', {key:'z',code:'KeyZ',ctrlKey:true,bubbles:true}));");
    assert.equal(await client.evaluate("$('#conceptMapTitle').value"), '当前画布本地输入仍保留');
    assert.equal(await client.evaluate('conceptMapFeature.flushSave()'), true);
    assert.equal(JSON.parse(fs.readFileSync(committedPath, 'utf8')).title, '当前画布本地输入仍保留');
    for (const [legacyId, version] of [['CMAP-9000', 1], ['CMAP-9001', undefined], ['CMAP-9002', 99]]) {
      const legacy = {...committed, id:legacyId, version};
      const legacyPath = path.join(data, 'concept-maps', `${legacyId}.json`);
      fs.writeFileSync(legacyPath, JSON.stringify(legacy));
      const original = fs.readFileSync(legacyPath);
      await client.evaluate(`conceptMapFeature.open(${JSON.stringify(legacyId)}).then(() => true)`);
      if (version === 99) {
        await delay(900);
        assert.deepEqual(fs.readFileSync(legacyPath), original, 'future versions must not enter old migration');
      } else {
        assert.equal(await client.evaluate('conceptMapFeature.flushSave()'), true);
        const migrated = JSON.parse(fs.readFileSync(legacyPath, 'utf8'));
        assert.equal(migrated.version, 2);
        assert.equal(migrated.nodes.length, 3);
        assert.equal(migrated.edges.length, 2);
      }
    }
    console.log('Agent concept-map browser workflow passed: full canvas/details/diff,local approval,escaping,zoom,background dirty/draft/keyboard/paste isolation,repeat disposal,light/dark,desktop/narrow');
    console.log(`Screenshots: ${screenshots}`);
  } catch (error) {
    if (client) console.error('Graph preview state:', await client.evaluate("({page:currentPage, feedback:document.querySelector('[data-proposal-feedback]')?.textContent, graph:document.querySelector('[data-proposal-graph-state]')?.textContent, dialog:document.querySelector('#proposalPreviewDialog')?.open, approve:document.querySelector('[data-proposal-action=approve]')?.disabled})").catch(() => null));
    throw error;
  } finally {
    client?.close(); browser?.kill(); server.kill();
    await delay(300);
    assert.ok(path.resolve(base).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(base, {recursive:true, force:true, maxRetries:5, retryDelay:200});
  }
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
module.exports = {main};
