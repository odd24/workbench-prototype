'use strict';

const assert = require('node:assert/strict');
const markdown = require('./js/editor/markdown.js');

const sample = '# 标题\n\n<script>alert(1)</script>\n\n| 左 | 右 |\n| :--- | ---: |\n| **值** | 2 |';
assert.equal(
  markdown.markdownToHtml(sample),
  '<h1>标题</h1><p>&lt;script&gt;alert(1)&lt;/script&gt;</p><div class="editor-table-wrap"><table><thead><tr><th style="text-align:left">左</th><th style="text-align:right">右</th></tr></thead><tbody><tr><td style="text-align:left"><strong>值</strong></td><td style="text-align:right">2</td></tr></tbody></table></div>'
);

assert.deepEqual(markdown.splitMarkdownTableRow('| a\\|b | c |'), ['a|b', 'c']);
assert.equal(markdown.markdownTableAlignment(':---:'), 'center');
assert.equal(markdown.markdownTableAlignment('invalid'), '');

assert.deepEqual(markdown.parseReferenceToken('doc-12#attachment:%E6%96%87%E4%BB%B6.txt'), {
  id:'DOC-12', kind:'attachment', attachmentName:'文件.txt'
});
assert.equal(markdown.parseReferenceToken('not-a-reference'), null);
assert.equal(
  markdown.referenceTokenToHtml('doc-12', id => ({id, type:'document', title:'说明 <script>'})),
  '<span class="internal-link reference-document-link" contenteditable="false" role="button" tabindex="0" data-reference-id="DOC-12" data-reference-token="doc-12" title="打开知识库文档">DOC-12 · 说明 &lt;script&gt;</span>&#8203;'
);

assert.equal(markdown.normalizeCodeLanguage(' C++ '), 'cpp');
assert.equal(markdown.normalizeCodeLanguage('PY'), 'python');
assert.equal(markdown.safeColor('#AABBCC'), '#aabbcc');
assert.equal(markdown.safeColor('red'), '#64748b');
assert.equal(markdown.cssColorToHex('rgb(255, 8, 16)'), '#ff0810');
assert.equal(markdown.cssColorToHex('rgba(1, 2, 3, 0)'), '');

assert.equal(markdown.syntaxHighlightCode('<script>', 'txt'), '&lt;script&gt;');
assert.match(markdown.syntaxHighlightCode('const value = 2;', 'javascript'), /token-keyword/);
assert.equal(
  markdown.markdownToPlainText('# 标题\n\n[[DOC-12]]', 110, '标题', id => ({id, type:'document', title:'说明'})),
  '说明'
);

console.log('Markdown core contract tests passed.');
