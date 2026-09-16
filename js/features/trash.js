(function initializeTrashFeature(global) {
  'use strict';

  function create(options) {
    const {root, actions, content, api, confirm, notify, escapeHtml, refreshData, isActive} = options;
    let items = [];
    let selection = new Set();
    let loadVersion = 0;
    let bindCount = 0;
    const kindName = kind => kind === 'project' ? '项目' : kind === 'document' ? '文档' : kind === 'concept-map' ? '概念图' : '记录';

    function updateSelection() {
      const count = selection.size;
      const selectAll = content.querySelector('#selectAllTrash');
      if (selectAll) {
        selectAll.checked = Boolean(items.length) && count === items.length;
        selectAll.indeterminate = count > 0 && count < items.length;
      }
      const countNode = actions.querySelector('#trashSelectionCount');
      if (countNode) countNode.textContent = `已选择 ${count} 项`;
      const restore = actions.querySelector('#batchRestoreTrash');
      const purge = actions.querySelector('#batchPurgeTrash');
      if (restore) restore.disabled = !count;
      if (purge) purge.disabled = !count;
      content.querySelectorAll('[data-trash-row]').forEach(row => row.classList.toggle('selected', selection.has(row.dataset.trashRow)));
    }
    function render() {
      const selectedCount = selection.size;
      actions.innerHTML = items.length ? `<span class="trash-selection-count" id="trashSelectionCount">已选择 ${selectedCount} 项</span><button class="secondary-button" id="batchRestoreTrash" ${selectedCount ? '' : 'disabled'}>批量恢复</button><button class="secondary-button danger-button" id="batchPurgeTrash" ${selectedCount ? '' : 'disabled'}>批量永久删除</button>` : '';
      content.innerHTML = items.length ? `<div class="trash-table-wrap"><table class="data-table trash-table"><thead><tr><th class="trash-select-cell"><input type="checkbox" id="selectAllTrash" aria-label="全选回收站内容" ${selectedCount === items.length ? 'checked' : ''}></th><th>名称</th><th>类型</th><th>删除时间</th><th>操作</th></tr></thead><tbody>${items.map(item => `<tr data-trash-row="${escapeHtml(item.token)}" class="${selection.has(item.token) ? 'selected' : ''}"><td class="trash-select-cell"><input type="checkbox" data-trash-select="${escapeHtml(item.token)}" aria-label="选择 ${escapeHtml(item.title)}" ${selection.has(item.token) ? 'checked' : ''}></td><td><strong>${escapeHtml(item.title)}</strong><br><small>${escapeHtml(item.id)}</small></td><td>${kindName(item.kind)}</td><td>${new Date(item.deleted_at).toLocaleString('zh-CN')}</td><td><div class="trash-row-actions"><button class="secondary-button" data-restore-trash="${escapeHtml(item.token)}">恢复</button><button class="secondary-button danger-button" data-purge-trash="${escapeHtml(item.token)}">永久删除</button></div></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty-state">回收站为空</div>';
      updateSelection();
    }
    async function load() {
      const version = ++loadVersion;
      content.innerHTML = '<div class="empty-state">正在加载回收站…</div>';
      const loaded = await api('/trash');
      if (version !== loadVersion || !isActive()) return false;
      items = loaded;
      selection = new Set([...selection].filter(token => items.some(item => item.token === token)));
      render();
      return true;
    }
    async function reload({refresh = false} = {}) {
      if (refresh) await refreshData();
      if (isActive()) await load();
    }
    async function restore(tokens) {
      if (!tokens.length) return;
      const result = tokens.length === 1
        ? await api(`/trash/${encodeURIComponent(tokens[0])}/restore`, {method:'POST'})
        : await api('/trash/batch/restore', {method:'POST', body:JSON.stringify({tokens})});
      selection.clear();
      await reload({refresh:true});
      notify(tokens.length === 1 ? '已从回收站恢复' : `已恢复 ${result.count} 项内容`);
    }
    async function purge(tokens) {
      if (!tokens.length) return;
      const accepted = await confirm({title:tokens.length === 1 ? '永久删除这条内容？' : `永久删除所选 ${tokens.length} 项？`, message:'此操作无法撤销，删除后不能从回收站恢复。', confirmText:tokens.length === 1 ? '永久删除' : '批量永久删除', danger:true});
      if (!accepted) return;
      const result = tokens.length === 1
        ? await api(`/trash/${encodeURIComponent(tokens[0])}`, {method:'DELETE'})
        : await api('/trash/batch', {method:'DELETE', body:JSON.stringify({tokens})});
      selection.clear();
      await reload();
      notify(tokens.length === 1 ? '已永久删除' : `已永久删除 ${result.count} 项内容`);
    }
    function bind() {
      if (bindCount) return;
      bindCount += 1;
      root.addEventListener('change', event => {
        if (event.target.id === 'selectAllTrash') {
          selection = event.target.checked ? new Set(items.map(item => item.token)) : new Set();
          content.querySelectorAll('[data-trash-select]').forEach(input => { input.checked = event.target.checked; });
          updateSelection();
        } else if (event.target.matches('[data-trash-select]')) {
          if (event.target.checked) selection.add(event.target.dataset.trashSelect); else selection.delete(event.target.dataset.trashSelect);
          updateSelection();
        }
      });
      root.addEventListener('click', async event => {
        try {
          const restoreOne = event.target.closest('[data-restore-trash]');
          const purgeOne = event.target.closest('[data-purge-trash]');
          if (restoreOne) await restore([restoreOne.dataset.restoreTrash]);
          else if (purgeOne) await purge([purgeOne.dataset.purgeTrash]);
          else if (event.target.closest('#batchRestoreTrash')) await restore([...selection]);
          else if (event.target.closest('#batchPurgeTrash')) await purge([...selection]);
        } catch (error) { notify('回收站操作失败', error.message, true); }
      });
    }
    bind();
    return Object.freeze({load, render, diagnostics:() => ({bindCount, itemCount:items.length, selectedCount:selection.size})});
  }

  const trash = Object.freeze({create});
  global.Workbench = global.Workbench || {};
  global.Workbench.trash = trash;
  if (typeof module !== 'undefined' && module.exports) module.exports = trash;
})(typeof window !== 'undefined' ? window : globalThis);
