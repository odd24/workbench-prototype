(function initializeKnowledgeFeature(global) {
  'use strict';

  function normalizeSortConfig(value = {}) {
    return {
      category_mode:value.category_mode || 'manual',
      category_order:Array.isArray(value.category_order) ? value.category_order : [],
      file_mode:value.file_mode || value.mode || 'updated',
      file_modes:value.file_modes && typeof value.file_modes === 'object' ? value.file_modes : {},
      file_orders:value.file_orders && typeof value.file_orders === 'object' ? value.file_orders : {},
    };
  }

  function categoryNames(documents, configured = [], includeUncategorized = true) {
    const names = [...configured, ...documents.map(item => item.category || '未分类')];
    if (includeUncategorized) names.push('未分类');
    return [...new Set(names)];
  }

  function buildCategoryEntries(documents, configured, sortValue, categoryQuery = '', fileQueries = {}) {
    const sortConfig = normalizeSortConfig(sortValue);
    const query = String(categoryQuery || '').trim().toLocaleLowerCase('zh-CN');
    const categoryIndex = new Map(sortConfig.category_order.map((name, index) => [name, index]));
    const entries = categoryNames(documents, configured, false).map(name => {
      const allItems = documents.filter(item => (item.category || '未分类') === name);
      return {name, allItems, updated:Math.max(0, ...allItems.map(item => Date.parse(item.updated || '') || 0))};
    }).filter(entry => !query || entry.name.toLocaleLowerCase('zh-CN').includes(query));
    entries.sort((a, b) => {
      if (a.name === '未分类') return 1;
      if (b.name === '未分类') return -1;
      if (sortConfig.category_mode === 'manual') return (categoryIndex.get(a.name) ?? 999999) - (categoryIndex.get(b.name) ?? 999999) || a.name.localeCompare(b.name, 'zh-CN');
      if (sortConfig.category_mode === 'count') return b.allItems.length - a.allItems.length || a.name.localeCompare(b.name, 'zh-CN');
      if (sortConfig.category_mode === 'updated') return b.updated - a.updated || a.name.localeCompare(b.name, 'zh-CN');
      return a.name.localeCompare(b.name, 'zh-CN');
    });
    return entries.map(entry => {
      const fileQuery = String(fileQueries[entry.name] || '').trim().toLocaleLowerCase('zh-CN');
      const fileMode = sortConfig.file_modes[entry.name] || sortConfig.file_mode;
      const fileIndex = new Map((sortConfig.file_orders[entry.name] || []).map((id, index) => [id, index]));
      const items = entry.allItems.filter(item => !fileQuery || `${item.title} ${item.body} ${(item.tags || []).join(' ')}`.toLocaleLowerCase('zh-CN').includes(fileQuery)).sort((a, b) => {
        if (fileMode === 'manual') return (fileIndex.get(a.id) ?? 999999) - (fileIndex.get(b.id) ?? 999999) || String(a.title).localeCompare(String(b.title), 'zh-CN');
        if (fileMode === 'title') return String(a.title).localeCompare(String(b.title), 'zh-CN');
        const field = fileMode === 'created' ? 'created' : 'updated';
        return (Date.parse(b[field] || '') || 0) - (Date.parse(a[field] || '') || 0);
      });
      return {...entry, items, fileQuery, fileMode};
    });
  }

  function parseMarkdownImport(name, content) {
    const normalized = String(content || '').replace(/\r\n/g, '\n');
    const frontmatterEnd = normalized.indexOf('\n---\n', 4);
    const frontmatter = normalized.startsWith('---\n') && frontmatterEnd >= 0 ? normalized.slice(4, frontmatterEnd) : '';
    const body = frontmatter ? normalized.slice(frontmatterEnd + 5).trim() : normalized.trim();
    const readMeta = key => { const match = frontmatter.match(new RegExp(`^${key}:\\s*["']?([^"'\\n]+)`, 'm')); return match?.[1]?.trim(); };
    const metaType = readMeta('type');
    const heading = body.match(/^#\s+(.+)$/m)?.[1]?.trim();
    return {
      type:['issue', 'todo', 'info'].includes(metaType) ? metaType : 'issue',
      title:readMeta('title') || heading || String(name || '').replace(/\.md$/i, ''),
      projectId:readMeta('project_id') || '',
      body,
    };
  }

  function safeExportName(value) {
    return String(value || 'workbench').replace(/[<>:"/\\|?*\x00-\x1F]/g, '-').replace(/[. ]+$/g, '').trim() || 'workbench';
  }

  const knowledge = Object.freeze({normalizeSortConfig, categoryNames, buildCategoryEntries, parseMarkdownImport, safeExportName});
  global.Workbench = global.Workbench || {};
  global.Workbench.knowledge = knowledge;
  if (typeof module !== 'undefined' && module.exports) module.exports = knowledge;
})(typeof window !== 'undefined' ? window : globalThis);
