(function initializeSearchFeature(global) {
  'use strict';

  function filterResults(results, type, filters) {
    return results.filter(record => record.type !== 'idea'
      && (!type || record.type === type)
      && (!filters.project || (filters.project === '__none__' ? !record.project_id : record.project_id === filters.project))
      && (!filters.tag || (record.tags || []).includes(filters.tag))
      && (!filters.status || record.status === filters.status)
      && (!filters.priority || record.priority === filters.priority));
  }

  function create(options) {
    const {panel, trigger, api, notify, escapeHtml, getProjects, projectName, typeNames, typeIcon, summary, showOverlay, hideOverlay, isAvailable = () => true} = options;
    const input = panel.querySelector('#searchInput');
    const clearButton = panel.querySelector('#clearSearchInput');
    let results = [];
    let type = '';
    let filters = {project:'', tag:'', status:'', priority:''};
    let timer = null;
    let requestVersion = 0;
    let bindCount = 0;

    function updateClearButton() { clearButton.hidden = !input.value; }
    function selectOptions(selector, values, emptyLabel, key) {
      const select = panel.querySelector(selector);
      select.innerHTML = `<option value="">${emptyLabel}</option>${values.map(([value, label]) => `<option value="${escapeHtml(value)}" ${value === filters[key] ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}`;
    }
    function render(nextResults = results) {
      results = nextResults.filter(record => record.type !== 'idea');
      panel.querySelectorAll('[data-search-type]').forEach(button => {
        button.classList.toggle('active', button.dataset.searchType === type);
        const count = button.querySelector('span');
        if (count) count.textContent = results.filter(item => !button.dataset.searchType || item.type === button.dataset.searchType).length;
      });
      selectOptions('#searchProjectFilter', [['__none__', '未归属'], ...getProjects().map(item => [item.id, item.name])], '全部项目', 'project');
      selectOptions('#searchTagFilter', [...new Set(results.flatMap(item => item.tags || []))].map(value => [value, value]), '全部标签', 'tag');
      selectOptions('#searchStatusFilter', [...new Set(results.map(item => item.status).filter(Boolean))].map(value => [value, value]), '全部状态', 'status');
      panel.querySelector('#searchPriorityFilter').value = filters.priority;
      const visible = filterResults(results, type, filters);
      panel.querySelector('.search-body section').innerHTML = `<div class="search-caption">找到 ${visible.length} 条记录</div>${visible.map(record => `<button class="search-result" data-record-id="${escapeHtml(record.id)}">${typeIcon(record)}<span><strong>${escapeHtml(record.title)}</strong><small>${escapeHtml(record.project_name || projectName(record.project_id))} · ${escapeHtml(typeNames[record.type] || record.type)} · ${escapeHtml(summary(record))}</small></span><em>${escapeHtml(record.type === 'info' ? '信息' : record.status)}</em></button>`).join('') || '<div class="empty-state">没有找到匹配记录</div>'}`;
    }
    async function search(query = input.value) {
      if (!isAvailable()) return;
      const version = ++requestVersion;
      try {
        const loaded = await api(`/search?q=${encodeURIComponent(query)}`);
        if (version === requestVersion) render(loaded);
      } catch (error) {
        if (version === requestVersion) notify('搜索失败', error.message, true);
      }
    }
    function open() {
      showOverlay();
      panel.classList.add('visible');
      panel.setAttribute('aria-hidden', 'false');
      updateClearButton();
      search();
      setTimeout(() => input.focus(), 50);
    }
    function close() {
      requestVersion += 1;
      panel.classList.remove('visible');
      panel.setAttribute('aria-hidden', 'true');
      hideOverlay();
    }
    function bind() {
      if (bindCount) return;
      bindCount += 1;
      trigger.addEventListener('click', open);
      input.addEventListener('input', () => {
        updateClearButton();
        clearTimeout(timer);
        timer = setTimeout(() => search(), 180);
      });
      clearButton.addEventListener('click', () => {
        clearTimeout(timer);
        input.value = '';
        updateClearButton();
        input.focus();
        search('');
      });
      panel.addEventListener('click', event => {
        const button = event.target.closest('[data-search-type]');
        if (!button) return;
        type = button.dataset.searchType;
        render();
      });
      panel.addEventListener('change', event => {
        if (!['searchProjectFilter', 'searchTagFilter', 'searchStatusFilter', 'searchPriorityFilter'].includes(event.target.id)) return;
        filters = {
          project:panel.querySelector('#searchProjectFilter').value,
          tag:panel.querySelector('#searchTagFilter').value,
          status:panel.querySelector('#searchStatusFilter').value,
          priority:panel.querySelector('#searchPriorityFilter').value,
        };
        render();
      });
    }
    bind();
    return Object.freeze({open, close, render, search, diagnostics:() => ({bindCount, type, filters:{...filters}, resultCount:results.length})});
  }

  const search = Object.freeze({create, filterResults});
  global.Workbench = global.Workbench || {};
  global.Workbench.search = search;
  if (typeof module !== 'undefined' && module.exports) module.exports = search;
})(typeof window !== 'undefined' ? window : globalThis);
