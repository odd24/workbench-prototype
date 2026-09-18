const assert = require('node:assert/strict');
const fs = require('node:fs');
const home = require('./js/features/home.js');
const projectView = require('./js/features/project-view.js');

const storage = new Map();
const adapter = {getItem:key => storage.get(key) || null, setItem:(key, value) => storage.set(key, value)};
storage.set('legacy', JSON.stringify([{id:'ISSUE-1'}, {id:'ISSUE-1'}, {id:'TODO-1'}]));
assert.deepEqual(home.load(adapter, 'current', 'legacy').columns[0].items, ['ISSUE-1', 'TODO-1']);
const normalized = home.save(adapter, 'current', {columns:[{id:'a', title:' A ', items:['ISSUE-1']}, {id:'a', title:'', items:['ISSUE-1', 'TODO-1']}], statusWatch:['处理中', '处理中', '']});
assert.deepEqual(normalized, {columns:[{id:'a', title:'A', items:['ISSUE-1']}, {id:'a_1', title:'分栏 2', items:['TODO-1']}], statusWatch:['处理中']});
assert.equal(home.itemCount(normalized), 2);
assert.deepEqual(home.fromBoard(normalized, [{id:'a_1', items:['TODO-1']}, {id:'a', items:['ISSUE-1']}]).columns.map(column => column.id), ['a_1', 'a']);

const records = [
  {id:'I-1', title:'B', project_id:'P-1', type:'issue', status:'处理中', priority:'高', tags:['A'], updated:'2026-01-02', created:'2026-01-01', due:'2026-01-05'},
  {id:'T-1', title:'A', project_id:'P-1', type:'todo', status:'待处理', priority:'普通', tags:['B'], updated:'2026-01-03', created:'2026-01-02', due:'2026-01-04'},
  {id:'N-1', project_id:'P-1', type:'info', status:'', priority:'', tags:['A'], updated:'2026-01-01'},
];
assert.deepEqual(projectView.selectRecords(records, 'P-1', 'overview', {tag:'A'}).map(item => item.id), ['I-1']);
assert.deepEqual(projectView.sortRecords(records.slice(0, 2), 'manual', ['T-1', 'I-1']).map(item => item.id), ['T-1', 'I-1']);
assert.deepEqual(projectView.sortRecords(records.slice(0, 2), 'updated').map(item => item.id), ['T-1', 'I-1']);
assert.deepEqual(projectView.sortRecords(records.slice(0, 2), 'priority').map(item => item.id), ['I-1', 'T-1']);
assert.deepEqual(projectView.sortRecords(records.slice(0, 2), 'due').map(item => item.id), ['T-1', 'I-1']);
assert.deepEqual(projectView.sortRecords(records.slice(0, 2), 'title').map(item => item.id), ['T-1', 'I-1']);
assert.deepEqual(projectView.sortRecords(records.slice(0, 2), 'created').map(item => item.id), ['T-1', 'I-1']);
assert.deepEqual(projectView.mergeVisibleOrder(['I-1', 'HIDDEN', 'T-1'], ['I-1', 'HIDDEN', 'T-1'], ['T-1', 'I-1']), ['T-1', 'HIDDEN', 'I-1']);
assert.deepEqual(projectView.filterAssets([{category:'图', item:{name:'架构.png'}}, {category:'', item:{name:'说明.txt'}}], '__uncategorized__', '说明').map(entry => entry.item.name), ['说明.txt']);

const appSource = fs.readFileSync('./app.js', 'utf8');
assert.match(appSource, /records\?summary=1&project=\$\{encodeURIComponent\(projectId\)\}&attachments=1/);
assert.match(appSource, /renderProjectAssets\(project, projectAssetRecords\)/);

console.log('Home and project feature contract tests passed.');
