(function initializeNavigationCore(global) {
  'use strict';

  const STORAGE_KEY = 'workbench-navigation-state';
  const MANAGE_PAGES = Object.freeze(['status_templates', 'archive', 'documents', 'timeline', 'tags', 'trash', 'settings', 'agent_settings']);
  const PAGE_NAMES = new Set(['home', 'project', 'concept_maps', ...MANAGE_PAGES]);
  const PROJECT_TABS = new Set(['overview', 'issues', 'todos', 'infos', 'assets']);

  function create({storage, location, history}) {
    function read() {
      try {
        const value = JSON.parse(storage.getItem(STORAGE_KEY) || 'null');
        return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
      } catch { return {}; }
    }

    function write({page, projectId, projectTab}) {
      try {
        storage.setItem(STORAGE_KEY, JSON.stringify({page, projectId, projectTab}));
        return true;
      } catch { return false; }
    }

    function normalizeProjectTab(value) {
      if (value === 'mixed') return 'overview';
      return PROJECT_TABS.has(value) ? value : 'overview';
    }

    function resolvePage(page, projects, selectedProjectId) {
      const resolved = PAGE_NAMES.has(page) ? page : 'home';
      if (resolved === 'project' && !projects.some(project => project.id === selectedProjectId)) return 'home';
      return resolved;
    }

    function clearHash() {
      if (!location.hash) return false;
      history.replaceState(null, '', `${location.pathname}${location.search}`);
      return true;
    }

    function readItemLink() {
      const params = new URLSearchParams(location.search);
      if (!params.has('item') && !params.has('itemId')) return null;
      const kind = params.get('item');
      const itemId = params.get('itemId');
      if (params.getAll('item').length !== 1 || params.getAll('itemId').length !== 1 ||
          !['issue', 'document', 'todo', 'info'].includes(kind) || !/^(?:ISSUE|TODO|INFO|IDEA|DOC)-\d+$/.test(itemId || '') ||
          (kind === 'document' && !itemId.startsWith('DOC-')) || (kind === 'todo' && !itemId.startsWith('TODO-')) || (kind === 'info' && !itemId.startsWith('INFO-'))) return {invalid:true};
      return {kind, itemId};
    }

    function clearItemLink() {
      const params = new URLSearchParams(location.search);
      if (!params.has('item') && !params.has('itemId')) return false;
      params.delete('item');
      params.delete('itemId');
      const query = params.toString();
      history.replaceState(null, '', `${location.pathname}${query ? `?${query}` : ''}${location.hash || ''}`);
      return true;
    }

    return Object.freeze({clearHash, clearItemLink, readItemLink, managePages:MANAGE_PAGES, normalizeProjectTab, read, resolvePage, write});
  }

  const navigation = Object.freeze({create});
  global.Workbench = global.Workbench || {};
  global.Workbench.navigation = navigation;
  if (typeof module !== 'undefined' && module.exports) module.exports = navigation;
})(typeof window !== 'undefined' ? window : globalThis);
