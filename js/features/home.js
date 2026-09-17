(function initializeHomeFeature(global) {
  'use strict';

  const fallbackLayout = () => ({columns:[{id:'home_focus', title:'重点工作', items:[]}], statusWatch:[]});

  function normalizeLayout(layout) {
    const usedColumns = new Set();
    const usedItems = new Set();
    const columns = (layout?.columns || []).filter(column => column && typeof column.id === 'string').map((column, index) => {
      let id = column.id;
      if (usedColumns.has(id)) id = `${id}_${index}`;
      usedColumns.add(id);
      const items = (Array.isArray(column.items) ? column.items : []).filter(item => typeof item === 'string' && !usedItems.has(item) && usedItems.add(item));
      return {id, title:String(column.title || `分栏 ${index + 1}`).trim().slice(0, 30) || `分栏 ${index + 1}`, items};
    });
    const statusWatch = [...new Set((Array.isArray(layout?.statusWatch) ? layout.statusWatch : []).filter(status => typeof status === 'string').map(status => status.trim()).filter(Boolean))];
    return {columns, statusWatch};
  }

  function load(storage, key, legacyKey) {
    try {
      const saved = JSON.parse(storage.getItem(key) || 'null');
      if (saved && Array.isArray(saved.columns)) return normalizeLayout(saved);
      const legacy = JSON.parse(storage.getItem(legacyKey) || '[]');
      const items = Array.isArray(legacy) ? legacy.filter(item => item && typeof item.id === 'string').map(item => item.id) : [];
      return normalizeLayout({columns:[{id:'home_focus', title:'重点工作', items:[...new Set(items)]}]});
    } catch { return fallbackLayout(); }
  }

  function save(storage, key, layout) {
    const normalized = normalizeLayout(layout);
    storage.setItem(key, JSON.stringify(normalized));
    return normalized;
  }

  function itemCount(layout) {
    return (layout?.columns || []).reduce((count, column) => count + (column.items || []).length, 0);
  }

  function fromBoard(layout, renderedColumns) {
    const titles = new Map((layout?.columns || []).map(column => [column.id, column.title]));
    const originalItems = new Map((layout?.columns || []).map(column => [column.id, column.items || []]));
    const visibleIds = new Set(renderedColumns.flatMap(column => column.items));
    return normalizeLayout({...layout, columns:renderedColumns.map(column => ({
      id:column.id,
      title:titles.get(column.id) || '未命名分栏',
      items:[...column.items, ...(originalItems.get(column.id) || []).filter(id => !visibleIds.has(id))],
    }))});
  }

  const home = Object.freeze({normalizeLayout, load, save, itemCount, fromBoard});
  global.Workbench = global.Workbench || {};
  global.Workbench.home = home;
  if (typeof module !== 'undefined' && module.exports) module.exports = home;
})(typeof window !== 'undefined' ? window : globalThis);
