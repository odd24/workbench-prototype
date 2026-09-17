(function initializeEditorSessionFeature(global) {
  'use strict';

  function create({storage, prefix, defaultId = 'new'} = {}) {
    if (!storage || typeof storage.getItem !== 'function' || typeof storage.setItem !== 'function') throw new TypeError('storage is required');
    if (!prefix) throw new TypeError('prefix is required');
    let dirty = false;
    let saving = false;
    let timer = null;

    const key = id => `${prefix}:${id || defaultId}`;
    const read = id => {
      try { return JSON.parse(storage.getItem(key(id)) || 'null'); }
      catch { return null; }
    };
    const write = (id, value) => {
      try { storage.setItem(key(id), JSON.stringify(value)); return true; }
      catch { return false; }
    };
    const clear = id => {
      try { storage.removeItem(key(id)); return true; }
      catch { return false; }
    };
    const cancel = () => {
      if (timer !== null) global.clearTimeout(timer);
      timer = null;
    };
    const schedule = (callback, delay = 1400) => {
      cancel();
      timer = global.setTimeout(() => {
        timer = null;
        callback();
      }, delay);
      return timer;
    };

    return {
      key,
      read,
      write,
      clear,
      cancel,
      schedule,
      get dirty() { return dirty; },
      set dirty(value) { dirty = Boolean(value); },
      get saving() { return saving; },
      set saving(value) { saving = Boolean(value); },
      get timer() { return timer; },
    };
  }

  const editorSession = Object.freeze({create});
  global.Workbench = global.Workbench || {};
  global.Workbench.editorSession = editorSession;
  if (typeof module !== 'undefined' && module.exports) module.exports = editorSession;
})(typeof window !== 'undefined' ? window : globalThis);
