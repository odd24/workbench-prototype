(function initializeProjectViewFeature(global) {
  'use strict';

  const keysByTab = Object.freeze({
    overview:{sort:'mixed_record_sort', order:'mixed_record_order', statusSorts:'mixed_status_record_sorts'},
    issues:{sort:'issue_record_sort', order:'issue_record_order', statusSorts:'issue_status_record_sorts'},
    todos:{sort:'todo_record_sort', order:'todo_record_order', statusSorts:'todo_status_record_sorts'},
    infos:{sort:'info_record_sort', order:'info_record_order', statusSorts:null},
  });

  function recordSortKeys(tab) { return keysByTab[tab] || null; }

  function sortRecords(items, mode, savedOrder = []) {
    const originalIndex = new Map(items.map((item, index) => [item.id, index]));
    const priorityRank = {紧急:0, 高:1, 普通:2, 低:3};
    const time = value => { const parsed = Date.parse(value || ''); return Number.isNaN(parsed) ? 0 : parsed; };
    return [...items].sort((a, b) => {
      if (mode === 'manual') {
        const ai = savedOrder.indexOf(a.id), bi = savedOrder.indexOf(b.id);
        return (ai < 0 ? savedOrder.length + originalIndex.get(a.id) : ai) - (bi < 0 ? savedOrder.length + originalIndex.get(b.id) : bi);
      }
      if (mode === 'updated') return time(b.updated) - time(a.updated);
      if (mode === 'priority') return (priorityRank[a.priority] ?? 9) - (priorityRank[b.priority] ?? 9) || time(b.updated) - time(a.updated);
      if (mode === 'due') return (a.due ? time(a.due) : Number.MAX_SAFE_INTEGER) - (b.due ? time(b.due) : Number.MAX_SAFE_INTEGER) || time(b.updated) - time(a.updated);
      if (mode === 'title') return String(a.title || '').localeCompare(String(b.title || ''), 'zh-CN');
      if (mode === 'created') return time(b.created) - time(a.created);
      return 0;
    });
  }

  function selectRecords(records, projectId, tab, filters = {}) {
    const typeForTab = {issues:'issue', todos:'todo', infos:'info'};
    let selected = records.filter(record => record.project_id === projectId);
    if (typeForTab[tab]) selected = selected.filter(record => record.type === typeForTab[tab]);
    if (tab === 'overview') selected = selected.filter(record => ['issue', 'todo'].includes(record.type));
    return selected.filter(record => (tab === 'infos' || !filters.status || record.status === filters.status)
      && (!filters.tag || (record.tags || []).includes(filters.tag))
      && (tab === 'infos' || !filters.priority || record.priority === filters.priority));
  }

  function mergeVisibleOrder(savedOrder, eligible, displayed) {
    const eligibleSet = new Set(eligible);
    const visibleSet = new Set(displayed);
    const base = [...(Array.isArray(savedOrder) ? savedOrder : []), ...eligible].filter((id, index, list) => eligibleSet.has(id) && list.indexOf(id) === index);
    let cursor = 0;
    const merged = base.map(id => visibleSet.has(id) ? displayed[cursor++] : id);
    while (cursor < displayed.length) merged.push(displayed[cursor++]);
    return merged;
  }

  function filterAssets(entries, category, query) {
    const needle = String(query || '').trim().toLocaleLowerCase('zh-CN');
    return entries.filter(entry => ((!category || entry.category === category) || (category === '__uncategorized__' && !entry.category))
      && (!needle || `${entry.item.name} ${entry.category} ${entry.record?.title || ''}`.toLocaleLowerCase('zh-CN').includes(needle)));
  }

  const projectView = Object.freeze({recordSortKeys, sortRecords, selectRecords, mergeVisibleOrder, filterAssets});
  global.Workbench = global.Workbench || {};
  global.Workbench.projectView = projectView;
  if (typeof module !== 'undefined' && module.exports) module.exports = projectView;
})(typeof window !== 'undefined' ? window : globalThis);
