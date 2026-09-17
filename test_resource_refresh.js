const assert = require('node:assert/strict');
const refresh = require('./js/core/resource-refresh.js');

const current = [
  {id:'TODO-1', file_mtime:10, title:'旧待办'},
  {id:'ISSUE-1', file_mtime:20, title:'将删除'},
  {id:'INFO-1', file_mtime:30, title:'保持'},
];
const signatures = [
  {id:'TODO-2', file_mtime:40},
  {id:'TODO-1', file_mtime:11},
  {id:'INFO-1', file_mtime:30},
];

const change = refresh.diff(current, signatures);
assert.deepEqual(change.changedIds, ['TODO-2', 'TODO-1']);
assert.deepEqual(change.removedIds, ['ISSUE-1']);
assert.equal(change.changed, true);

const reconciled = refresh.reconcile(current, [
  {id:'TODO-1', file_mtime:11, title:'新待办'},
  {id:'TODO-2', file_mtime:40, title:'新增'},
], signatures, change);
assert.deepEqual(reconciled.map(item => item.id), ['TODO-2', 'TODO-1', 'INFO-1']);
assert.equal(reconciled[1].title, '新待办');
assert.equal(reconciled[2], current[2]);

assert.deepEqual(refresh.diff(reconciled, signatures), {changedIds:[], removedIds:[], changed:false});
assert.equal(refresh.queryForIds(['TODO-1', '空 格']), 'id=TODO-1&id=%E7%A9%BA%20%E6%A0%BC');

console.log('Incremental resource refresh contract tests passed.');
