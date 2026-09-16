const assert = require('node:assert/strict');

require('./js/editor/markdown.js');
const dom = require('./js/core/dom.js');
const api = require('./js/core/api.js');
const dialogs = require('./js/core/dialogs.js');

assert.equal(dom.$('.item', {querySelector:selector => selector}), '.item');
assert.deepEqual(dom.$$('.item', {querySelectorAll:() => new Set(['a', 'b'])}), ['a', 'b']);
assert.equal(dom.escapeHtml('<unsafe>'), '&lt;unsafe&gt;');
assert.equal(dom.safeColor('#FF0000'), '#ff0000');
assert.equal(dom.safeColor('rgb(255, 0, 0)'), '#64748b');
assert.equal(typeof api.request, 'function');
assert.equal(typeof dialogs.notify, 'function');
assert.equal(typeof dialogs.open, 'function');
assert.equal(typeof dialogs.confirm, 'function');
assert.equal(typeof dialogs.prompt, 'function');

const originalFetch = global.fetch;
let capturedRequest;
global.fetch = async (url, options) => {
  capturedRequest = {url, options};
  return {ok:true, status:200, json:async () => ({ok:true})};
};

(async () => {
  try {
    assert.deepEqual(await api.request('/contract', {method:'POST', headers:{'X-Test':'yes'}, body:'{}'}), {ok:true});
    assert.equal(capturedRequest.url, '/api/contract');
    assert.deepEqual(capturedRequest.options.headers, {'Content-Type':'application/json', 'X-Test':'yes'});
    global.fetch = async () => ({ok:false, status:409, json:async () => ({error:'冲突'})});
    await assert.rejects(api.request('/contract'), /冲突/);
    global.fetch = async () => ({ok:false, status:500, json:async () => { throw new Error('invalid json'); }});
    await assert.rejects(api.request('/contract'), /请求失败 \(500\)/);
    console.log('App core contract tests passed.');
  } finally {
    global.fetch = originalFetch;
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
