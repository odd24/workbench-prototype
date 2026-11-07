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

  function timestampHtml(value, detailed = false, pending = false) {
    if (pending) return '<span>保存后生成</span>';
    if (value === undefined || value === null || value === '') return '<span>未记录</span>';
    const date = typeof value === 'string' ? new Date(value) : new Date(NaN);
    if (Number.isNaN(date.valueOf())) return '<span>时间格式异常</span>';
    const part = number => String(number).padStart(2, '0');
    const text = `${date.getFullYear()}-${part(date.getMonth() + 1)}-${part(date.getDate())} ${part(date.getHours())}:${part(date.getMinutes())}${detailed ? `:${part(date.getSeconds())}` : ''}`;
    return `<time datetime="${date.toISOString()}">${text}</time>`;
  }

  function timestampsHtml(item, detailed = false) {
    return `<span class="entity-times${detailed ? ' entity-times-detail' : ''}"><span>创建：${timestampHtml(item?.created, detailed, !item)}</span></span>`;
  }

  const api = {$, $$, escapeHtml, safeColor, timestampHtml, timestampsHtml};
  global.Workbench = global.Workbench || {};
  global.Workbench.dom = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
