(function initializeCoreApi(global) {
  'use strict';

  async function request(path, options = {}) {
    const response = await global.fetch(`/api${path}`, {
      ...options,
      headers:{'Content-Type':'application/json', ...(options.headers || {})},
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(payload.error || payload.message || `请求失败 (${response.status})`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  const api = {request};
  global.Workbench = global.Workbench || {};
  global.Workbench.api = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
