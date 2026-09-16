const assert = require('node:assert/strict');
const stateCore = require('./js/core/state.js');

const backing = {projects:[], selectedProjectId:'', currentRecord:null, recordDraft:null};
const appState = stateCore.create({
  serverData:{
    get projects() { return backing.projects; },
    set projects(value) { backing.projects = value; },
  },
  uiState:{
    get selectedProjectId() { return backing.selectedProjectId; },
    set selectedProjectId(value) { backing.selectedProjectId = value; },
  },
  editorState:{
    get currentRecord() { return backing.currentRecord; },
    set currentRecord(value) { backing.currentRecord = value; },
  },
  draftState:{
    get recordDraft() { return backing.recordDraft; },
    set recordDraft(value) { backing.recordDraft = value; },
  },
});

assert.deepEqual(stateCore.groups, ['serverData', 'uiState', 'editorState', 'draftState']);
assert.notEqual(appState.serverData, appState.uiState);
appState.serverData.projects = [{id:'P-1'}];
appState.uiState.selectedProjectId = 'P-1';
appState.editorState.currentRecord = {id:'ISSUE-1'};
appState.draftState.recordDraft = {body:'draft'};
assert.equal(backing.projects[0].id, 'P-1');
assert.equal(backing.selectedProjectId, 'P-1');
assert.equal(backing.currentRecord.id, 'ISSUE-1');
assert.equal(backing.recordDraft.body, 'draft');

const first = appState.requests.begin('record-detail', 'ISSUE-1');
const second = appState.requests.begin('record-detail', 'ISSUE-2');
assert.equal(appState.requests.isCurrent(first), false);
assert.equal(appState.requests.isCurrent(second), true);
assert.equal(appState.requests.isCurrent(second, 'ISSUE-1'), false);
appState.requests.invalidate('record-detail');
assert.equal(appState.requests.isCurrent(second), false);

const assetRequest = appState.requests.begin('project-assets', 'P-1');
assert.equal(appState.requests.isCurrent(assetRequest), true);
assert.equal(appState.requests.isCurrent(second), false);

console.log('State boundary contract tests passed.');
