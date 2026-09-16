(function initializeCoreDom(global) {
  'use strict';

  const markdownCore = global.Workbench?.markdown;

  function requireMarkdownCore() {
    if (!markdownCore) throw new Error('Workbench.markdown must load before Workbench.dom');
    return markdownCore;
  }

  function $(selector, root = global.document) {
    return root.querySelector(selector);
  }

  function $$(selector, root = global.document) {
    return [...root.querySelectorAll(selector)];
  }

  function escapeHtml(value) {
    return requireMarkdownCore().escapeHtml(value);
  }

  function safeColor(value, fallback = '#64748b') {
    return requireMarkdownCore().safeColor(value, fallback);
  }

  const api = {$, $$, escapeHtml, safeColor};
  global.Workbench = global.Workbench || {};
  global.Workbench.dom = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
