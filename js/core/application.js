(function initializeApplicationCore(global) {
  'use strict';

  function create({window:windowTarget, initialize, beforeUnload, pageHide}) {
    if (!windowTarget || typeof initialize !== 'function') throw new Error('Application requires a window and initialize callback');
    let started = false;
    let startPromise = null;

    function start() {
      if (started) return startPromise;
      started = true;
      if (typeof beforeUnload === 'function') windowTarget.addEventListener('beforeunload', beforeUnload);
      if (typeof pageHide === 'function') windowTarget.addEventListener('pagehide', pageHide);
      startPromise = Promise.resolve().then(initialize);
      return startPromise;
    }

    return Object.freeze({diagnostics:() => ({started}), start});
  }

  const application = Object.freeze({create});
  global.Workbench = global.Workbench || {};
  global.Workbench.application = application;
  if (typeof module !== 'undefined' && module.exports) module.exports = application;
})(typeof window !== 'undefined' ? window : globalThis);
