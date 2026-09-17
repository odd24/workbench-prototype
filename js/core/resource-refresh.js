(function initializeResourceRefresh(global) {
  'use strict';

  function signatureValue(item) {
    return item?.file_mtime ?? item?.updated ?? '';
  }

  function diff(currentItems = [], signatures = []) {
    const current = new Map(currentItems.filter(item => item?.id).map(item => [item.id, signatureValue(item)]));
    const next = new Map(signatures.filter(item => item?.id).map(item => [item.id, signatureValue(item)]));
    const changedIds = [];
    next.forEach((signature, id) => {
      if (!current.has(id) || !Object.is(current.get(id), signature)) changedIds.push(id);
    });
    const removedIds = [];
    current.forEach((_signature, id) => {
      if (!next.has(id)) removedIds.push(id);
    });
    return Object.freeze({changedIds, removedIds, changed:Boolean(changedIds.length || removedIds.length)});
  }

  function reconcile(currentItems = [], changedItems = [], signatures = [], change = diff(currentItems, signatures)) {
    const changedIds = new Set(change.changedIds);
    const items = new Map(
      currentItems
        .filter(item => item?.id && !changedIds.has(item.id) && !change.removedIds.includes(item.id))
        .map(item => [item.id, item]),
    );
    changedItems.filter(item => item?.id).forEach(item => items.set(item.id, item));
    return signatures.map(item => items.get(item.id)).filter(Boolean);
  }

  function queryForIds(ids = []) {
    return ids.map(id => `id=${encodeURIComponent(id)}`).join('&');
  }

  const resourceRefresh = Object.freeze({diff, queryForIds, reconcile, signatureValue});
  global.Workbench = global.Workbench || {};
  global.Workbench.resourceRefresh = resourceRefresh;
  if (typeof module !== 'undefined' && module.exports) module.exports = resourceRefresh;
})(typeof window !== 'undefined' ? window : globalThis);
