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
