const assert = require('node:assert/strict');

const listeners = [];
const canvasShell = {addEventListener:(type, listener) => listeners.push({target:'canvas', type, listener})};
global.window = {addEventListener:(type, listener) => listeners.push({target:'window', type, listener})};
global.document = {
  addEventListener:(type, listener) => listeners.push({target:'document', type, listener}),
  querySelector:selector => selector === '#conceptMapCanvasShell' ? canvasShell : null,
};
global.localStorage = {getItem:() => null, setItem:() => {}};

const conceptMap = require('./concept-map.js');

assert.equal(typeof conceptMap.create, 'function');
assert.throws(() => conceptMap.create({}), /DOM, API, dialogs, and app state/);

const library = {hidden:true, innerHTML:''};
const workspace = {hidden:false};
const nodes = new Map([
  ['#conceptMapLibrary', library],
  ['#conceptMapWorkspace', workspace],
]);
const appState = {
  serverData:{conceptMaps:[{id:'stale'}]},
  uiState:{conceptMapSearch:''},
  editorState:{currentConceptMap:{id:'stale'}, conceptMapSelection:{type:'node', id:'old'}, conceptMapConnectSource:'old', conceptMapSaving:false},
  draftState:{conceptMapSaveTimer:null},
};
const requests = [];
const feature = conceptMap.create({
  dom:{
    $:selector => nodes.get(selector) || null,
    $$:() => [],
    escapeHtml:value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;'),
  },
  api:{request:async path => {
    requests.push(path);
    if (path === '/concept-maps') return [{id:'CMAP-1', title:'显式依赖', focus_question:'', category:'未分类', updated:'2026-09-17', node_count:1, edge_count:0}];
    if (path === '/concept-map-categories') return ['未分类'];
    throw new Error(`Unexpected request: ${path}`);
  }},
  dialogs:{notify:() => {}, confirm:async () => true, prompt:async () => ''},
  appState,
});

assert.deepEqual(Object.keys(feature).sort(), ['flushSave', 'open', 'renderLibrary']);

(async () => {
  await feature.renderLibrary();
  assert.deepEqual(requests, ['/concept-maps', '/concept-map-categories']);
  assert.equal(workspace.hidden, true);
  assert.equal(library.hidden, false);
  assert.match(library.innerHTML, /显式依赖/);
  assert.deepEqual(appState.serverData.conceptMaps.map(item => item.id), ['CMAP-1']);
  assert.equal(appState.editorState.currentConceptMap, null);
  assert.equal(appState.editorState.conceptMapSelection, null);
  assert.ok(listeners.some(item => item.target === 'canvas' && item.type === 'pointerdown'));
  assert.ok(listeners.some(item => item.target === 'document' && item.type === 'click'));
  console.log('Concept map frontend dependency contract tests passed.');
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
