(function initializeRecordConflictFeature(global) {
  'use strict';

  function lineDiff(localText, externalText) {
    const a = String(localText || '').split('\n');
    const b = String(externalText || '').split('\n');
    if (a.length * b.length > 120000) {
      const rows = Array.from({length:Math.max(a.length, b.length)}, (_, index) => ({type:a[index] === b[index] ? 'same' : 'changed', local:a[index] ?? '', external:b[index] ?? ''}));
      return {rows, merged:`<<<<<<< 工作台\n${localText}\n=======\n${externalText}\n>>>>>>> 磁盘`};
    }
    const dp = Array.from({length:a.length + 1}, () => new Uint16Array(b.length + 1));
    for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const rows = [];
    let i = 0;
    let j = 0;
    while (i < a.length || j < b.length) {
      if (i < a.length && j < b.length && a[i] === b[j]) { rows.push({type:'same', local:a[i], external:b[j]}); i++; j++; }
      else if (i < a.length && (j >= b.length || dp[i + 1][j] >= dp[i][j + 1])) { rows.push({type:'removed', local:a[i], external:''}); i++; }
      else { rows.push({type:'added', local:'', external:b[j]}); j++; }
    }
    const merged = [];
    let localChunk = [];
    let externalChunk = [];
    const flush = () => {
      if (!localChunk.length && !externalChunk.length) return;
      if (localChunk.join('\n') === externalChunk.join('\n')) merged.push(...localChunk);
      else merged.push('<<<<<<< 工作台', ...localChunk, '=======', ...externalChunk, '>>>>>>> 磁盘');
      localChunk = [];
      externalChunk = [];
    };
    rows.forEach(row => {
      if (row.type === 'same') { flush(); merged.push(row.local); }
      else { if (row.local) localChunk.push(row.local); if (row.external) externalChunk.push(row.external); }
    });
    flush();
    return {rows, merged:merged.join('\n')};
  }

  function create({dialog, localField, externalField, mergedField, diffContainer, escapeHtml, getLocalContent}) {
    let current = null;
    return {
      get current() { return current; },
      set current(value) { current = value; },
      show(latest) {
        current = latest;
        localField.value = getLocalContent();
        externalField.value = latest.body;
        const diff = lineDiff(localField.value, latest.body);
        diffContainer.innerHTML = diff.rows.map((row, index) => `<div class="diff-row ${row.type}"><span>${index + 1}</span><span>${escapeHtml(row.local ?? '')}</span><span>${escapeHtml(row.external ?? '')}</span></div>`).join('');
        mergedField.value = diff.merged;
        if (!dialog.open) dialog.showModal();
      },
      close() {
        if (dialog.open) dialog.close();
        current = null;
      },
    };
  }

  const recordConflict = Object.freeze({lineDiff, create});
  global.Workbench = global.Workbench || {};
  global.Workbench.recordConflict = recordConflict;
  if (typeof module !== 'undefined' && module.exports) module.exports = recordConflict;
})(typeof window !== 'undefined' ? window : globalThis);
