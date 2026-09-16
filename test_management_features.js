const assert = require('node:assert/strict');

const search = require('./js/features/search.js');
const trash = require('./js/features/trash.js');
const manage = require('./js/features/manage.js');

assert.equal(typeof search.create, 'function');
assert.equal(typeof trash.create, 'function');
assert.equal(typeof manage.createUsageNavigator, 'function');

const records = [
  {id:'ISSUE-1', type:'issue', project_id:'P-1', tags:['后端'], status:'待处理', priority:'高'},
  {id:'TODO-1', type:'todo', project_id:'P-2', tags:['前端'], status:'进行中', priority:'普通'},
  {id:'INFO-1', type:'info', project_id:null, tags:[], status:'', priority:''},
  {id:'IDEA-1', type:'idea', project_id:null, tags:[], status:'', priority:''},
];

assert.deepEqual(search.filterResults(records, '', {project:'', tag:'', status:'', priority:''}).map(item => item.id), ['ISSUE-1', 'TODO-1', 'INFO-1']);
assert.deepEqual(search.filterResults(records, 'issue', {project:'P-1', tag:'后端', status:'待处理', priority:'高'}).map(item => item.id), ['ISSUE-1']);
assert.deepEqual(search.filterResults(records, '', {project:'__none__', tag:'', status:'', priority:''}).map(item => item.id), ['INFO-1']);

console.log('Management feature contract tests passed.');
