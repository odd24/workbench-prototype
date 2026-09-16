(function initializeManageFeature(global) {
  'use strict';

  function createUsageNavigator(options) {
    const {dialog, manageRoot, recordBackButton, escapeHtml, typeIcons, typeNames, projectName, tagColor, statusColor, tagUsage, statusUsage, openRecord, openDocument} = options;
    const content = dialog.querySelector('#usageDialogContent');
    let currentView = null;
    let navigationStack = [];
    let returnContext = null;
    let bindCount = 0;

    function rowsHtml(items) {
      return items.length ? `<div class="usage-record-list">${items.map(record => `<button type="button" class="usage-record-row" ${record.type === 'document' ? `data-usage-document="${escapeHtml(record.id)}"` : `data-usage-record="${escapeHtml(record.id)}"`}><span class="type-icon ${escapeHtml(record.type)}">${record.type === 'document' ? '▤' : escapeHtml(typeIcons[record.type] || '•')}</span><span><strong>${escapeHtml(record.title)}</strong><small>${escapeHtml(record.id)} · ${record.type === 'document' ? `知识库文档 · ${escapeHtml(record.category || '未分类')}` : `${escapeHtml(typeNames[record.type] || record.type)} · ${escapeHtml(projectName(record.project_id))}${record.status ? ` · ${escapeHtml(record.status)}` : ''}`}</small></span><em>打开</em></button>`).join('')}</div>` : '<div class="usage-empty"><span>✓</span><strong>暂无内容使用</strong><small>当前可以安全删除这项配置</small></div>';
    }
    function updateDialogBack() {
      const button = dialog.querySelector('#usageDialogBack');
      const available = navigationStack.length > 0 || currentView?.view === 'detail';
      button.classList.toggle('available', available);
      button.tabIndex = available ? 0 : -1;
      const destination = navigationStack.length ? '使用统计' : currentView?.kind === 'status' ? '状态模板' : '标签管理';
      button.setAttribute('aria-label', `返回${destination}`);
      button.title = `返回${destination}`;
    }
    function updateRecordBack(stackLength = 0) {
      const returnsToUsage = stackLength === 0 && Boolean(returnContext);
      recordBackButton.classList.toggle('available', stackLength > 0 || Boolean(returnContext));
      recordBackButton.classList.toggle('usage-return', returnsToUsage);
      recordBackButton.innerHTML = returnsToUsage ? '<span aria-hidden="true">←</span><b>使用统计</b>' : '←';
      const label = returnsToUsage ? '返回使用统计' : '返回上一条记录';
      recordBackButton.setAttribute('aria-label', label);
      recordBackButton.title = label;
    }
    function openDetail({kind, name, recordType = '', statusId = ''}, renderOptions = {}) {
      if (!renderOptions.preserveStack) navigationStack = [];
      currentView = {view:'detail', kind, name, recordType, statusId};
      const items = kind === 'tag' ? tagUsage(name) : statusUsage(recordType, name, statusId);
      dialog.querySelector('#usageDialogEyebrow').textContent = kind === 'tag' ? '标签使用情况' : `${typeNames[recordType] || recordType}状态使用情况`;
      dialog.querySelector('#usageDialogTitle').textContent = `「${name}」`;
      dialog.querySelector('#usageDialogSummary').innerHTML = `<strong>${items.length}</strong><span>条内容正在使用</span>${items.length ? '<small>需要先在下列记录或文档中移除或更改，才能删除此配置。</small>' : '<small>这项配置目前未被使用，可以安全删除。</small>'}`;
      content.innerHTML = rowsHtml(items);
      updateDialogBack();
      if (!dialog.open) dialog.showModal();
    }
    function openOverview(kind, renderOptions = {}) {
      if (!renderOptions.preserveStack) navigationStack = [];
      currentView = {view:'overview', kind};
      const isTag = kind === 'tag';
      const items = isTag
        ? [...manageRoot.querySelectorAll('.tag-edit')].map(row => { const name = row.dataset.originalName || row.querySelector('input[type="text"]').value.trim(); return {name, count:tagUsage(name).length}; })
        : [...manageRoot.querySelectorAll('.status-edit-row')].map(row => { const recordType = row.closest('.template-panel').dataset.templateType; const name = row.querySelector('input[type="text"]').value.trim(); const statusId = row.dataset.statusId || ''; return {name, recordType, statusId, count:statusUsage(recordType, name, statusId).length}; });
      const totalUsage = items.reduce((sum, item) => sum + item.count, 0);
      dialog.querySelector('#usageDialogEyebrow').textContent = isTag ? '标签使用统计' : '状态使用统计';
      dialog.querySelector('#usageDialogTitle').textContent = isTag ? '全部标签' : '当前工作流状态';
      dialog.querySelector('#usageDialogSummary').innerHTML = `<strong>${items.length}</strong><span>项配置</span><small>合计 ${totalUsage} 次内容引用；点击任一项查看具体记录或文档。</small>`;
      content.innerHTML = `<div class="usage-overview-list">${items.map(item => `<button type="button" data-usage-detail-kind="${kind}" data-usage-detail-name="${escapeHtml(item.name)}" ${item.recordType ? `data-usage-detail-type="${escapeHtml(item.recordType)}" data-usage-detail-status-id="${escapeHtml(item.statusId)}"` : ''}><span><i style="background:${isTag ? tagColor(item.name) : statusColor(item.recordType, item.statusId, item.name)}"></i><strong>${escapeHtml(item.name)}</strong>${item.recordType ? `<small>${escapeHtml(typeNames[item.recordType] || item.recordType)}</small>` : ''}</span><em class="${item.count ? 'in-use' : ''}">${item.count} 条</em><b>查看 ›</b></button>`).join('') || '<div class="usage-empty"><strong>暂无配置</strong></div>'}</div>`;
      updateDialogBack();
      if (!dialog.open) dialog.showModal();
    }
    function back() {
      const previous = navigationStack.pop();
      if (!previous) { close(); return; }
      if (previous.view === 'overview') openOverview(previous.kind, {preserveStack:true}); else openDetail(previous, {preserveStack:true});
      requestAnimationFrame(() => { content.scrollTop = previous.scrollTop || 0; });
    }
    function close() {
      currentView = null;
      navigationStack = [];
      returnContext = null;
      dialog.close('cancel');
    }
    function restoreReturnContext() {
      if (!returnContext) return false;
      const context = returnContext;
      returnContext = null;
      navigationStack = (context.navigationStack || []).map(item => ({...item}));
      if (context.view?.view === 'overview') openOverview(context.view.kind, {preserveStack:true}); else if (context.view) openDetail(context.view, {preserveStack:true});
      requestAnimationFrame(() => { content.scrollTop = context.scrollTop || 0; });
      return true;
    }
    function bind() {
      if (bindCount) return;
      bindCount += 1;
      dialog.querySelector('#usageDialogBack').addEventListener('click', back);
      dialog.querySelector('#closeUsageDialog').addEventListener('click', close);
      manageRoot.addEventListener('click', event => {
        if (event.target.closest('#statusUsageOverview')) openOverview('status');
        else if (event.target.closest('#tagUsageOverview')) openOverview('tag');
      });
      dialog.addEventListener('click', async event => {
        const detail = event.target.closest('[data-usage-detail-kind]');
        if (detail) {
          if (currentView) navigationStack.push({...currentView, scrollTop:content.scrollTop});
          openDetail({kind:detail.dataset.usageDetailKind, name:detail.dataset.usageDetailName, recordType:detail.dataset.usageDetailType || '', statusId:detail.dataset.usageDetailStatusId || ''}, {preserveStack:true});
          return;
        }
        const record = event.target.closest('[data-usage-record]');
        if (record) {
          returnContext = {view:{...currentView}, navigationStack:navigationStack.map(item => ({...item})), scrollTop:content.scrollTop};
          dialog.close();
          await openRecord(record.dataset.usageRecord);
          return;
        }
        const document = event.target.closest('[data-usage-document]');
        if (document) { dialog.close(); openDocument(document.dataset.usageDocument); }
      });
    }
    bind();
    return Object.freeze({openDetail, openOverview, back, close, updateRecordBack, restoreReturnContext, hasReturnContext:() => Boolean(returnContext), clearReturnContext:() => { returnContext = null; }, diagnostics:() => ({bindCount, view:currentView?.view || '', depth:navigationStack.length})});
  }

  const manage = Object.freeze({createUsageNavigator});
  global.Workbench = global.Workbench || {};
  global.Workbench.manage = manage;
  if (typeof module !== 'undefined' && module.exports) module.exports = manage;
})(typeof window !== 'undefined' ? window : globalThis);
