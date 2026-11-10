const assert = require('node:assert/strict');
const navigationCore = require('./js/core/navigation.js');
const applicationCore = require('./js/core/application.js');

const values = new Map();
const storage = {getItem:key => values.get(key) || null, setItem:(key, value) => values.set(key, value)};
const location = {hash:'#project', pathname:'/index.html', search:'?test=1'};
let replaced = '';
const navigation = navigationCore.create({storage, location, history:{replaceState:(_state, _title, url) => { replaced = url; }}});

assert.deepEqual(navigation.read(), {});
assert.equal(navigation.write({page:'project', projectId:'P-1', projectTab:'issues'}), true);
assert.deepEqual(navigation.read(), {page:'project', projectId:'P-1', projectTab:'issues'});
assert.equal(navigation.normalizeProjectTab('mixed'), 'overview');
assert.equal(navigation.normalizeProjectTab('todos'), 'todos');
assert.equal(navigation.normalizeProjectTab('invalid'), 'overview');
assert.equal(navigation.resolvePage('project', [{id:'P-1'}], 'P-1'), 'project');
assert.equal(navigation.resolvePage('project', [], 'P-1'), 'home');
assert.equal(navigation.resolvePage('invalid', [], ''), 'home');
assert.equal(navigation.clearHash(), true);
assert.equal(replaced, '/index.html?test=1');

assert.equal(navigation.readItemLink(), null);
location.search = '?session=1&item=issue&itemId=ISSUE-0001';
assert.deepEqual(navigation.readItemLink(), {kind:'issue', itemId:'ISSUE-0001'});
location.search = '?item=info&itemId=INFO-0001';
assert.deepEqual(navigation.readItemLink(), {kind:'info', itemId:'INFO-0001'});
location.search = '?item=todo&itemId=TODO-0001';
assert.deepEqual(navigation.readItemLink(), {kind:'todo', itemId:'TODO-0001'});
location.search = '?item=document&itemId=DOC%2D0001';
assert.deepEqual(navigation.readItemLink(), {kind:'document', itemId:'DOC-0001'});
location.search = '?item=concept_map&itemId=CMAP-0001';
assert.deepEqual(navigation.readItemLink(), {kind:'concept_map', itemId:'CMAP-0001'});
for (const search of ['?item=concept_map&itemId=DOC-1', '?item=concept_map&itemId=CMAP-1&itemId=CMAP-2', '?item=concept_map&itemId=CMAP-1&extra=1', '?item=concept_map&itemId=..%2Fsecret']) {
  location.search = search;
  assert.deepEqual(navigation.readItemLink(), {invalid:true});
}
location.search = '?item=project&itemId=%E9%A1%B9%E7%9B%AE&assetId=ASSET-123456781234123412341234567890ab';
assert.deepEqual(navigation.readItemLink(), {kind:'project', itemId:'项目', assetId:'ASSET-123456781234123412341234567890ab'});
for (const search of ['?item=project&itemId=..&assetId=ASSET-123456781234123412341234567890ab', '?item=project&itemId=P&assetId=other', '?item=project&itemId=P', '?item=info&itemId=TODO-1', '?item=todo&itemId=ISSUE-1', '?item=todo&itemId=DOC-1', '?item=document', '?item=unknown&itemId=DOC-1', '?item=document&itemId=ISSUE-1', '?item=issue&item=issue&itemId=ISSUE-1', '?item=document&itemId=..%2F..%2Fsecret']) {
  location.search = search;
  assert.deepEqual(navigation.readItemLink(), {invalid:true});
}
location.search = '?session=1&item=document&itemId=DOC-1';
location.hash = '';
assert.equal(navigation.clearItemLink(), true);
assert.equal(replaced, '/index.html?session=1');

const listeners = [];
let initializeCount = 0;
const application = applicationCore.create({
  window:{addEventListener:(type, listener) => listeners.push({type, listener})},
  initialize:async () => { initializeCount += 1; },
  beforeUnload:() => {},
  pageHide:() => {},
});

(async () => {
  await Promise.all([application.start(), application.start()]);
  assert.equal(initializeCount, 1);
  assert.deepEqual(listeners.map(item => item.type), ['beforeunload', 'pagehide']);
  assert.deepEqual(application.diagnostics(), {started:true});
  console.log('Frontend entry contract tests passed.');
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
