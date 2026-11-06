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
      const node = root.querySelector('#proposalFeedback');
      if (node) { node.textContent = text; node.classList.toggle('agent-error', error); }
    }
    const button = (action, label, extra = '') => `<button type="button" class="secondary-button" data-proposal-action="${action}" ${busy ? 'disabled' : ''} ${extra}>${label}</button>`;
    function filter(key, label, items) {
      return `<label>${label}<select data-proposal-filter="${key}" ${busy ? 'disabled' : ''}><option value="">全部</option>${Object.entries(items).map(([value, name]) => `<option value="${esc(value)}" ${filters[key] === value ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select></label>`;
    }
    function detailHtml() {
      if (!detail) return '<p class="settings-hint">选择提案查看完整预览；编辑内容请回原客户端修改后重新预览。</p>';
      const preview = detail.preview;
      const receipt = detail.receipt;
      const content = preview?.content;
      return `<section class="settings-card agent-proposal-detail" aria-label="提案详情"><h2>${esc(detail.title)}</h2><p>客户端：${esc(detail.client_name)}（${esc(detail.client_id)}）</p><p>提案：${esc(detail.proposal_id)} · 版本 ${detail.version} · ${esc(states[detail.state] || detail.state)}</p><p>创建：${esc(detail.created_at)}；过期：${esc(detail.expires_at)}</p><p>确认方式：${esc(detail.confirmation_mode)}；当前写入授权：${detail.authorization_available ? '可用' : '不可用'}</p>${detail.recovery_in_progress ? '<p class="agent-error">原提交正在恢复或需要本机核查；查看详情不会发起新提交，请按维护说明处理。</p>' : ''}${detail.content_cleaned ? '<p>正文已按保留规则清理；不能批准残缺预览。</p>' : preview ? `<p>摘要：${esc(preview.preview_digest)}</p><h3>全部字段</h3><pre data-proposal-fields>${esc(JSON.stringify(content, null, 2))}</pre>${content.info_fields ? `<h3>有序信息字段</h3><ol>${content.info_fields.map(field => `<li><strong>${esc(field.name)}</strong><pre>${esc(field.value)}</pre>${field.note !== undefined ? `<p>说明</p><pre>${esc(field.note)}</pre>` : ''}</li>`).join('')}</ol>` : ''}<h3>正文预览</h3><div class="markdown-preview agent-proposal-markdown">${renderMarkdown(content.body || '', {type:detail.kind, project_id:detail.access_target.project_id})}</div><h3>字段差异</h3><pre>${esc(JSON.stringify(preview.changes, null, 2))}</pre><h3>正文差异</h3><pre>${esc(preview.body_diff || '无正文变化')}</pre><h3>警告</h3><ul>${preview.warnings.map(text => `<li>${esc(text)}</li>`).join('')}</ul><h3>来源说明</h3><pre>${esc(preview.source_note || '未提供来源说明')}</pre>` : ''}<div class="settings-actions">${button('review', '重新读取完整预览', `data-proposal-id="${esc(detail.proposal_id)}"`)}${button('cancel', '取消当前版本', `data-proposal-id="${esc(detail.proposal_id)}" ${['draft', 'previewed', 'conflicted'].includes(detail.state) && !detail.content_cleaned ? '' : 'disabled'}`)}<button type="button" class="primary-button" disabled title="网页批准尚未开放">批准并入库（尚未开放）</button>${receipt?.web_path && /^\/\?item=(issue|todo|info|document)&itemId=[A-Z]+-\d+$/.test(receipt.web_path) ? `<a class="secondary-button" href="${esc(receipt.web_path)}">打开入库结果</a>` : ''}</div><p class="settings-hint">提案管理不编辑正文；需要修改时请回原客户端生成新版本。</p></section>`;
    }
    function paint() {
      root.innerHTML = `<div class="settings-stack agent-settings"><section class="settings-card"><div class="agent-section-head"><h2>提案管理</h2>${button('refresh', '刷新列表')}</div><p>仅本机管理会话可查看当前空间各客户端的候选内容。</p><div class="agent-proposal-filters">${filter('client_id', '客户端', Object.fromEntries(listing.clients.map(client => [client.client_id, client.name])))}${filter('kind', '类型', kinds)}${filter('state', '状态', states)}${filter('operation', '操作', operations)}</div></section><p id="proposalFeedback" class="agent-feedback" role="status" aria-live="polite"></p>${pending ? `<section class="settings-card"><p>上次取消结果尚未确定，请先查询同一操作。</p>${button('resolve', '查询取消结果')}</section>` : ''}<section class="settings-card"><div class="agent-client-list">${listing.items.map(item => `<article class="agent-client"><strong>${esc(item.title)}</strong><small>${esc(item.client_name)} · ${esc(kinds[item.kind])} · ${esc(operations[item.operation])} · ${esc(states[item.state])}</small><small>归属：${esc(item.access_target.project_id || item.access_target.category || '—')} · 版本 ${item.version}</small><small>${esc(item.proposal_id)}</small>${button('review', '查看完整预览', `data-proposal-id="${esc(item.proposal_id)}"`)}</article>`).join('') || '<p class="empty-state">当前筛选下暂无提案。</p>'}</div><div class="settings-actions">${button('previous', '上一页', cursors.length < 2 ? 'disabled' : '')}<span>第 ${cursors.length} 页 · 每页 20 项</span>${button('next', '下一页', !listing.next_cursor ? 'disabled' : '')}</div></section>${detailHtml()}</div>`;
    }
    async function load() {
      const version = ++epoch;
      busy = true;
      root.innerHTML = '<p class="empty-state">正在加载提案…</p>';
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
        detail = null;
        busy = false;
        paint();
      } catch (error) { if (current(version)) { busy = false; paint(); message(error.payload?.message || error.message, true); } }
    }
    async function review(proposalId) {
      const version = ++epoch;
      busy = true; paint();
      try {
        const value = await request(`proposals/${encodeURIComponent(proposalId)}/preview`);
        if (!current(version)) return;
        if (value.workspace_id !== status.workspace_id) throw new Error('工作空间已变化，请刷新');
        detail = value;
        busy = false; paint();
        root.querySelector('.agent-proposal-detail')?.scrollIntoView({block:'start'});
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
        await load(); await review(result.proposal_id);
        message('提案已取消。');
      } catch (error) {
        if (current(version)) {
          if (error.status && error.status < 500) remember(null);
          busy = false; paint(); message(`${error.payload?.message || error.message}${pending ? '；请查询同一取消操作。' : '；请重新核对当前版本。'}`, true);
        }
      }
    }
    root.addEventListener('click', event => {
      if (!isActive() || busy) return;
      const node = event.target.closest('[data-proposal-action]');
      if (!node) return;
      event.preventDefault();
      const action = node.dataset.proposalAction;
      if (pending && action !== 'resolve') { message('请先查询取消结果。', true); return; }
      if (action === 'review') review(node.dataset.proposalId).catch(error => notify('提案加载失败', error.message, true));
      if (action === 'refresh') load();
      if (action === 'next' && listing.next_cursor) { cursors.push(listing.next_cursor); load(); }
      if (action === 'previous' && cursors.length > 1) { cursors.pop(); load(); }
      if (action === 'cancel' || action === 'resolve') cancel().catch(error => message(error.message, true));
    });
    root.addEventListener('change', event => {
      if (!isActive() || busy || pending || !event.target.dataset.proposalFilter) return;
      filters[event.target.dataset.proposalFilter] = event.target.value; cursors = ['0']; load();
    });
    return {load, deactivate:() => { epoch += 1; busy = false; detail = null; }, isBusy:() => busy || confirming || Boolean(pending)};
  }
  global.Workbench = global.Workbench || {};
  global.Workbench.agentProposals = {create};
})(typeof window !== 'undefined' ? window : globalThis);
