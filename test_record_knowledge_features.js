const assert = require('node:assert/strict');
const editorSession = require('./js/features/editor-session.js');
const recordConflict = require('./js/features/record-conflict.js');
const knowledge = require('./js/features/knowledge.js');

const values = new Map();
const storage = {
  getItem:key => values.get(key) || null,
  setItem:(key, value) => values.set(key, value),
  removeItem:key => values.delete(key),
};
const session = editorSession.create({storage, prefix:'draft'});
assert.equal(session.key('ITEM-1'), 'draft:ITEM-1');
assert.equal(session.write('ITEM-1', {body:'保留\n空格 '}), true);
assert.deepEqual(session.read('ITEM-1'), {body:'保留\n空格 '});
session.dirty = 1;
session.saving = true;
assert.equal(session.dirty, true);
assert.equal(session.saving, true);
assert.equal(session.clear('ITEM-1'), true);
assert.equal(session.read('ITEM-1'), null);

const diff = recordConflict.lineDiff('共同\n本地', '共同\n磁盘');
assert.deepEqual(diff.rows.map(row => row.type), ['same', 'removed', 'added']);
assert.match(diff.merged, /<<<<<<< 工作台\n本地\n=======\n磁盘\n>>>>>>> 磁盘/);

const documents = [
  {id:'DOC-1', title:'Z', category:'设计', body:'alpha', tags:['A'], updated:'2026-01-03', created:'2026-01-01'},
  {id:'DOC-2', title:'A', category:'设计', body:'beta', tags:[], updated:'2026-01-02', created:'2026-01-04'},
  {id:'DOC-3', title:'无分类', category:'', body:'gamma', tags:[], updated:'2026-01-05', created:'2026-01-05'},
];
assert.deepEqual(knowledge.normalizeSortConfig({mode:'title'}), {category_mode:'manual', category_order:[], file_mode:'title', file_modes:{}, file_orders:{}});
const entries = knowledge.buildCategoryEntries(documents, ['空分类', '设计'], {category_mode:'manual', category_order:['空分类', '设计'], file_mode:'updated', file_modes:{设计:'manual'}, file_orders:{设计:['DOC-2', 'DOC-1']}}, '', {});
assert.deepEqual(entries.map(entry => entry.name), ['空分类', '设计', '未分类']);
assert.deepEqual(entries[1].items.map(item => item.id), ['DOC-2', 'DOC-1']);
assert.deepEqual(knowledge.buildCategoryEntries(documents, ['设计'], {category_mode:'count'}, '设计', {设计:'BETA'}).flatMap(entry => entry.items).map(item => item.id), ['DOC-2']);
assert.deepEqual(knowledge.parseMarkdownImport('fallback.md', '---\r\ntype: todo\r\ntitle: "导入标题"\r\nproject_id: P-1\r\n---\r\n正文'), {type:'todo', title:'导入标题', projectId:'P-1', body:'正文'});
assert.equal(knowledge.parseMarkdownImport('说明.md', '# 标题\n正文').title, '标题');
assert.equal(knowledge.safeExportName('名称:*? .'), '名称---');

console.log('Record and knowledge feature contract tests passed.');
