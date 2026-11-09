(function initializeAgentProposals(global) {
  'use strict';

  function create({root, api, escapeHtml:esc, confirm, notify, renderMarkdown, isActive}) {
    let status = null;
    let listing = {items:[], clients:[], next_cursor:null};
    let filters = {client_id:'', kind:'', state:'', operation:''};
    let cursors = ['0'];
    let detail = null;
    let busy = false;
    let pending = null;
    let confirming = false;
    let epoch = 0;
    let previewId = null;
    let returnId = null;
    let listScroll = 0;
    let feedback = '';
    let feedbackError = false;
    let savedOverflow = null;
    let savedRootStyle = null;
    const dialog = () => root.querySelector('#proposalPreviewDialog');
    function closePreview({force = false} = {}) {
      if ((!force && confirming) || !dialog() || (!dialog().open && !previewId)) return;
      epoch += 1;
      busy = false;
      detail = null;
      previewId = null;
      dialog().close();
      dialog().innerHTML = '';
      if (savedOverflow !== null) { global.document.body.style.overflow = savedOverflow; savedOverflow = null; }
      if (savedRootStyle) {
        Object.assign(global.document.documentElement.style, savedRootStyle);
        savedRootStyle = null;
      }
      paint();
      const trigger = [...root.querySelectorAll('.agent-client [data-proposal-action="review"]')].find(node => node.dataset.proposalId === returnId);
      trigger?.focus({preventScroll:true});
      global.scrollTo({top:listScroll, behavior:'instant'});
    }
    const states = {draft:'草案', previewed:'已预览', committing:'提交恢复中', committed:'已入库', conflicted:'有冲突', cancelled:'已取消', expired:'已过期', recovery_required:'需要恢复'};
    const kinds = {issue:'问题', todo:'待办', info:'信息', document:'知识文档'};
    const operations = {create:'新建', append:'追加', update:'更新'};
    const key = () => `workbench.proposalAction.pending.${status?.workspace_id}`;
    const current = version => version === epoch && isActive();
    function remember(value) {
      pending = value;
      try { if (value) global.sessionStorage.setItem(key(), JSON.stringify(value)); else global.sessionStorage.removeItem(key()); } catch { /* Query remains available in this page. */ }
    }
    async function request(route, options = {}) {
      return api(`/local/agent-management/${route}`, {...options, headers:{'X-Workbench-Management':'1', ...(status?.management_token ? {'X-Workbench-Management-Token':status.management_token} : {})}, signal:AbortSignal.timeout(15000)});
    }
    function message(text, error = false) {
      feedback = text;
      feedbackError = error;
      for (const node of root.querySelectorAll('[data-proposal-feedback]')) {
        node.textContent = text;
        node.classList.toggle('agent-error', error);
      }
    }
    const button = (action, label, extra = '') => `<button type="button" class="secondary-button" data-proposal-action="${action}" ${busy ? 'disabled' : ''} ${extra}>${label}</button>`;
    function filter(key, label, items) {
      return `<label>${label}<select data-proposal-filter="${key}" ${busy ? 'disabled' : ''}><option value="">全部</option>${Object.entries(items).map(([value, name]) => `<option value="${esc(value)}" ${filters[key] === value ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select></label>`;
    }
    function detailHtml() {
      if (!detail) return `<p class="empty-state">${busy ? '正在加载完整预览…' : '完整预览未加载，请重新读取。'}</p>`;
      const preview = detail.preview;
      const content = preview?.content;
      const labels = {title:'标题', project_id:'所属项目', category:'分类', status:'状态', priority:'优先级', tags:'标签', due:'到期日', completed:'已完成'};
      const fieldValue = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
      return `<section class="agent-proposal-detail" aria-label="提案详情"><p>客户端：${esc(detail.client_name)}（${esc(detail.client_id)}）</p><p>提案：${esc(detail.proposal_id)} · 版本 ${detail.version} · ${esc(states[detail.state] || detail.state)}</p><p>归属：${esc(detail.access_target.project_id || detail.access_target.category || '—')} · ${esc(kinds[detail.kind] || detail.kind)} · ${esc(operations[detail.operation] || detail.operation)}</p><p>确认方式：${detail.confirmation_mode === 'local_web' ? '本机网页独立批准' : '对话内确认'}；当前写入授权：${detail.authorization_available ? '可用' : '不可用'}</p>${detail.recovery_in_progress ? '<p class="agent-error">原提交正在恢复或需要本机核查；查看详情不会发起新提交，请按维护说明处理。</p>' : ''}${detail.content_cleaned ? '<p>正文已按保留规则清理；不能批准残缺预览。</p>' : preview ? `<h3>警告</h3>${preview.warnings.length ? `<ul class="agent-error">${preview.warnings.map(text => `<li>${esc(text)}</li>`).join('')}</ul>` : '<p>无警告</p>'}<h3>字段内容</h3><dl class="agent-proposal-fields">${Object.entries(content).filter(([key]) => !['body', 'info_fields'].includes(key)).map(([key, value]) => `<dt>${esc(labels[key] || key)}</dt><dd><pre>${esc(fieldValue(value))}</pre></dd>`).join('')}</dl>${content.info_fields ? `<h3>有序信息字段</h3><ol>${content.info_fields.map(field => `<li><strong>${esc(field.name)}</strong><pre>${esc(field.value)}</pre>${field.note !== undefined ? `<p>说明</p><pre>${esc(field.note)}</pre>` : ''}</li>`).join('')}</ol>` : ''}<h3>完整正文</h3><div class="markdown-preview agent-proposal-markdown">${renderMarkdown(content.body || '', {type:detail.kind, project_id:detail.access_target.project_id})}</div><h3>字段差异</h3><pre>${esc(JSON.stringify(preview.changes, null, 2))}</pre><h3>正文差异</h3><pre>${esc(preview.body_diff || '无正文变化')}</pre>${preview.execution_plan ? `<h3>保存范围</h3><p>先保留历史快照，再保存正文；新建条目不写旧内容快照。相关依赖或授权变化后须重新整理和确认。</p><details data-proposal-execution><summary>查看执行依据和版本</summary><pre>${esc(JSON.stringify({authorization_revision:preview.authorization_revision, dependencies:preview.dependencies, execution_plan:preview.execution_plan, plan_digest:preview.plan_digest}, null, 2))}</pre></details>` : ''}<h3>来源说明</h3><pre>${esc(preview.source_note || '未提供来源说明')}</pre><details><summary>查看全部原始字段（JSON）</summary><pre data-proposal-fields>${esc(JSON.stringify(content, null, 2))}</pre></details><p>摘要：${esc(preview.preview_digest)}</p>` : ''}<p>创建：${esc(detail.created_at)}；过期：${esc(detail.expires_at)}</p><p class="settings-hint">提案管理不编辑正文；需要修改时请回原客户端生成新版本。</p></section>`;
    }
    function paintPreview() {
      const modal = dialog();
      if (!modal) return;
      const body = modal.querySelector('.agent-proposal-preview-body');
      const scroll = body?.scrollTop || 0;
      const focused = modal.contains(global.document.activeElement) ? global.document.activeElement.dataset.proposalAction : null;
      const index = listing.items.findIndex(item => item.proposal_id === previewId);
      const receipt = detail?.receipt;
      modal.innerHTML = `<header><div><p class="eyebrow">提案完整预览</p><h2 id="proposalPreviewTitle">${esc(detail?.title || '加载提案')}</h2><small>${detail ? `${esc(kinds[detail.kind] || detail.kind)} · ${esc(operations[detail.operation] || detail.operation)} · ${esc(states[detail.state] || detail.state)} · 版本 ${detail.version}` : ''}</small></div><button type="button" class="icon-button dialog-close" data-proposal-action="close-preview" aria-label="关闭预览" ${confirming ? 'disabled' : ''}>✕</button></header><div class="agent-proposal-preview-body" tabindex="0">${detailHtml()}</div><footer><p class="agent-feedback" data-proposal-feedback role="status" aria-live="polite"></p>${pending ? `<div class="settings-actions">上次操作结果尚未确定。${button('resolve', '查询提案操作结果')}</div>` : ''}<div class="settings-actions"><nav aria-label="本页提案切换">${button('preview-previous', '上一条', index <= 0 || pending ? 'disabled' : '')}<span>${index < 0 ? '当前提案不在本页' : `本页第 ${index + 1} / ${listing.items.length} 条`}</span>${button('preview-next', '下一条', index < 0 || index >= listing.items.length - 1 || pending ? 'disabled' : '')}</nav><div class="settings-actions">${button('review', '重新读取完整预览', `data-proposal-id="${esc(previewId || '')}" ${pending ? 'disabled' : ''}`)}${button('cancel', '取消当前版本', `data-proposal-id="${esc(detail?.proposal_id || '')}" ${!pending && detail && ['draft', 'previewed', 'conflicted'].includes(detail.state) && !detail.content_cleaned ? '' : 'disabled'}`)}<button type="button" class="primary-button" data-proposal-action="approve" ${busy || pending || !detail?.preview_ticket || !detail.authorization_available || detail.content_cleaned || detail.confirmation_mode !== 'local_web' ? 'disabled' : ''}>批准并入库</button>${receipt?.web_path && /^\/\?item=(issue|todo|info|document)&itemId=[A-Z]+-\d+$/.test(receipt.web_path) ? `<a class="secondary-button" href="${esc(receipt.web_path)}">打开入库结果</a>` : ''}</div></div></footer>`;
      modal.querySelector('.agent-proposal-preview-body').scrollTop = scroll;
      if (focused) modal.querySelector(`[data-proposal-action="${focused}"]`)?.focus({preventScroll:true});
    }
    function paint() {
      const scroll = global.scrollY;
      if (!root.querySelector('#proposalListShell')) {
        root.innerHTML = '<div id="proposalListShell"></div><dialog id="proposalPreviewDialog" class="history-dialog agent-proposal-dialog agent-settings" aria-labelledby="proposalPreviewTitle"></dialog>';
        dialog().addEventListener('cancel', event => { event.preventDefault(); closePreview(); });
        dialog().addEventListener('close', () => {
          if (previewId && !dialog().open) closePreview({force:true});
        });
      }
      root.querySelector('#proposalListShell').innerHTML = `<div class="settings-stack agent-settings"><section class="settings-card"><div class="agent-section-head"><h2>提案管理</h2>${button('refresh', '刷新列表')}</div><p>仅本机管理会话可查看当前空间各客户端的候选内容。</p><div class="agent-proposal-filters">${filter('client_id', '客户端', Object.fromEntries(listing.clients.map(client => [client.client_id, client.name])))}${filter('kind', '类型', kinds)}${filter('state', '状态', states)}${filter('operation', '操作', operations)}</div></section><p id="proposalFeedback" data-proposal-feedback class="agent-feedback" role="status" aria-live="polite"></p>${pending ? `<section class="settings-card"><p>上次提案操作结果尚未确定，请先查询同一操作。</p>${button('resolve', '查询提案操作结果')}</section>` : ''}<section class="settings-card"><div class="agent-client-list">${listing.items.map(item => `<article class="agent-client"><strong>${esc(item.title)}</strong><small>${esc(item.client_name)} · ${esc(kinds[item.kind])} · ${esc(operations[item.operation])} · ${esc(states[item.state])}</small><small>归属：${esc(item.access_target.project_id || item.access_target.category || '—')} · 版本 ${item.version}</small><small>${esc(item.proposal_id)}</small>${button('review', '查看完整预览', `data-proposal-id="${esc(item.proposal_id)}"`)}</article>`).join('') || '<p class="empty-state">当前筛选下暂无提案。</p>'}</div><div class="settings-actions">${button('previous', '上一页', cursors.length < 2 ? 'disabled' : '')}<span>第 ${cursors.length} 页 · 每页 20 项</span>${button('next', '下一页', !listing.next_cursor ? 'disabled' : '')}</div></section></div>`;
      if (previewId) paintPreview();
      message(feedback, feedbackError);
      global.scrollTo({top:scroll, behavior:'instant'});
    }
    async function load({preservePreview = false} = {}) {
      if (!preservePreview && dialog()?.open) closePreview();
      message('');
      const version = ++epoch;
      busy = true;
      paint();
      try {
        const fresh = await request('status');
        if (!current(version)) return;
        if (status?.workspace_id !== fresh.workspace_id) { detail = null; pending = null; filters = {client_id:'', kind:'', state:'', operation:''}; cursors = ['0']; }
        status = fresh;
        if (!pending) { try { pending = JSON.parse(global.sessionStorage.getItem(key()) || 'null'); } catch { pending = null; } }
        const params = new URLSearchParams({...filters, cursor:cursors.at(-1), limit:20});
        const result = await request(`proposals?${params}`);
        if (!current(version)) return;
        if (result.workspace_id !== status.workspace_id) throw new Error('工作空间已变化，请刷新');
        listing = result;
        if (!preservePreview) detail = null;
        busy = false;
        paint();
        return true;
      } catch (error) { if (current(version)) { busy = false; paint(); message(error.payload?.message || error.message, true); } }
      return false;
    }
    async function review(proposalId) {
      if (!isActive()) return;
      const opening = !dialog()?.open;
      if (opening) { listScroll = global.scrollY; returnId = proposalId; }
      previewId = proposalId;
      detail = null;
      message('');
      const version = ++epoch;
      busy = true; paint();
      dialog().querySelector('.agent-proposal-preview-body').scrollTop = 0;
      if (opening) {
        savedOverflow = global.document.body.style.overflow;
        global.document.body.style.overflow = 'hidden';
        const style = global.document.documentElement.style;
        savedRootStyle = {overflow:style.overflow, scrollbarGutter:style.scrollbarGutter};
        style.overflow = 'hidden';
        style.scrollbarGutter = 'auto';
        dialog().showModal();
        dialog().querySelector('[data-proposal-action="close-preview"]').focus({preventScroll:true});
      }
      try {
        const value = await request(`proposals/${encodeURIComponent(proposalId)}/preview`);
        if (!current(version)) return;
        if (value.workspace_id !== status.workspace_id) throw new Error('工作空间已变化，请刷新');
        detail = value;
        busy = false; paint();
      } catch (error) { if (current(version)) { busy = false; paint(); message(error.payload?.message || error.message, true); } }
    }
    async function cancel() {
      if (!pending) {
        const shown = detail;
        if (!shown || confirming) return;
        confirming = true;
        let approved;
        try { approved = await confirm({title:'取消当前提案版本？', message:`${shown.title} · 版本 ${shown.version}`, detail:'候选内容不再提交，已存在的正式记录不受影响。', confirmText:'取消提案', danger:true}); } finally { confirming = false; }
        if (!approved) return;
        if (shown !== detail || !isActive()) return;
        remember({proposal_id:detail.proposal_id, payload:{workspace_id:status.workspace_id, expected_version:detail.version, request_id:global.crypto.randomUUID()}});
      }
      const version = ++epoch;
      busy = true; paint();
      try {
        const result = await request(`proposals/${encodeURIComponent(pending.proposal_id)}/cancel`, {method:'POST', body:JSON.stringify(pending.payload)});
        if (!current(version)) return;
        remember(null);
        busy = false;
        if (!await load({preservePreview:true})) return;
        await review(result.proposal_id);
        message('提案已取消。');
      } catch (error) {
        if (current(version)) {
          if (error.status && error.status < 500) remember(null);
          busy = false; paint(); message(`${error.payload?.message || error.message}${pending ? '；请查询同一取消操作。' : '；请重新核对当前版本。'}`, true);
        }
      }
    }
    async function approve() {
      const shown = detail;
      if (!shown?.preview_ticket || confirming || pending) return;
      confirming = true;
      let approved;
      try { approved = await confirm({title:'批准当前完整预览并入库？', message:`${shown.title} · 版本 ${shown.version}`, detail:'将以原客户端当前权限写入此版本；修改后必须重新预览批准。', confirmText:'批准并入库'}); }
      finally { confirming = false; }
      if (!approved || shown !== detail || !isActive()) return;
      const payload = {workspace_id:status.workspace_id, version:shown.version, preview_digest:shown.preview.preview_digest, preview_ticket:shown.preview_ticket, request_id:global.crypto.randomUUID()};
      remember({operation:'approve', proposal_id:shown.proposal_id, request_id:payload.request_id});
      const version = ++epoch;
      busy = true; paint();
      try {
        const result = await request(`proposals/${shown.proposal_id}/approve`, {method:'POST', body:JSON.stringify(payload)});
        if (!current(version)) return;
        remember(null); busy = false;
        if (!await load({preservePreview:true})) return;
        await review(result.proposal_id);
        message(result.state === 'completed' ? '已批准并入库。' : '原操作尚未完成，请重新核查。', result.state !== 'completed');
      } catch (error) {
        if (current(version)) {
          if (error.status && error.status < 500) { remember(null); detail = null; }
          busy = false; paint(); message(`${error.payload?.message || error.message}${pending ? '；请先查询原操作结果。' : '；请重新完整预览。'}`, true);
        }
      }
    }
    async function resolve() {
      if (pending?.operation !== 'approve') return cancel();
      const version = ++epoch;
      busy = true; paint();
      try {
        const result = await request(`proposal-actions/${encodeURIComponent(pending.request_id)}`);
        if (!current(version)) return;
        if (['completed', 'not_applied'].includes(result.state)) {
          remember(null); busy = false;
          if (!await load({preservePreview:true})) return;
          await review(result.proposal_id);
          message(result.state === 'completed' ? '已查到原入库回执。' : '原批准未应用；请重新完整预览后批准。');
        } else { busy = false; paint(); message('原事务需要恢复核查，请按维护说明处理。', true); }
      } catch (error) {
        if (current(version)) { busy = false; paint(); message(error.payload?.message || error.message, true); }
      }
    }
    root.addEventListener('click', event => {
      if (!isActive()) return;
      const node = event.target.closest('[data-proposal-action]');
      if (!node) return;
      event.preventDefault();
      const action = node.dataset.proposalAction;
      if (action === 'close-preview') { closePreview(); return; }
      if (busy || confirming) return;
      if (action === 'preview-previous' || action === 'preview-next') {
        if (pending) { message('请先查询提案操作结果。', true); return; }
        const index = listing.items.findIndex(item => item.proposal_id === previewId);
        const target = index < 0 ? null : listing.items[index + (action === 'preview-next' ? 1 : -1)];
        if (target) review(target.proposal_id);
        return;
      }
      if (pending && action !== 'resolve') { message('请先查询提案操作结果。', true); return; }
      if (action === 'review') review(node.dataset.proposalId).catch(error => notify('提案加载失败', error.message, true));
      if (action === 'refresh') load();
      if (action === 'next' && listing.next_cursor) { cursors.push(listing.next_cursor); load(); }
      if (action === 'previous' && cursors.length > 1) { cursors.pop(); load(); }
      if (action === 'cancel') cancel().catch(error => message(error.message, true));
      if (action === 'resolve') resolve().catch(error => message(error.message, true));
      if (action === 'approve') approve().catch(error => message(error.message, true));
    });
    root.addEventListener('change', event => {
      if (!isActive() || busy || pending || !event.target.dataset.proposalFilter) return;
      filters[event.target.dataset.proposalFilter] = event.target.value; cursors = ['0']; load();
    });
    return {load, deactivate:() => { closePreview({force:true}); epoch += 1; busy = false; detail = null; }, isBusy:() => busy || confirming || Boolean(pending)};
  }
  global.Workbench = global.Workbench || {};
  global.Workbench.agentProposals = {create};
})(typeof window !== 'undefined' ? window : globalThis);
