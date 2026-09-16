(function runDocumentModelContract(global) {
  'use strict';

  const isCommonJs = typeof module !== 'undefined' && module.exports;
  const assert = isCommonJs ? require('node:assert/strict') : null;
  if (isCommonJs) require('./js/editor/markdown.js');
  const documentModel = isCommonJs ? require('./js/editor/document-model.js') : global.Workbench.documentModel;

  function equal(actual, expected, message = '') {
    if (assert) return assert.equal(actual, expected, message);
    if (actual !== expected) throw new Error(`${message || '值不一致'}\n期望：${expected}\n实际：${actual}`);
  }

  function deepEqual(actual, expected, message = '') {
    if (assert) return assert.deepEqual(actual, expected, message);
    equal(JSON.stringify(actual), JSON.stringify(expected), message);
  }

  equal(typeof documentModel.render, 'function');
  equal(typeof documentModel.serialize, 'function');
  equal(typeof documentModel.normalize, 'function');
  equal(
    documentModel.documentModelToMarkdown([
      {id:'block-1', type:'heading', level:2, markdown:'## 标题'},
      {id:'block-2', type:'divider', markdown:'---'},
      {id:'block-3', type:'paragraph', markdown:''},
    ]),
    '## 标题\n\n---'
  );
  equal(documentModel.documentModelToMarkdown(null), '');

  if (typeof document !== 'undefined') {
    const source = [
      '# 一级标题',
      '',
      '普通 **粗体** *斜体* ~~删除线~~ <u>下划线</u> `inline()` [链接](https://example.com)',
      '',
      '<span style="color:#123456;background-color:#abcdef">受控颜色</span>',
      '',
      '## 标题',
      '',
      '- 项目',
      '- [ ] 待处理',
      '- [x] 任务',
      '',
      '1. 第一',
      '2. 第二',
      '',
      '> 引用',
      '',
      '```javascript',
      'const value = 1;',
      '```',
      '',
      '```python',
      'print("中文")',
      '```',
      '',
      '```shell',
      'printf "%s\\n" "ok"',
      '```',
      '',
      '---',
      '',
      '| 左 | 中 | 右 |',
      '| :--- | :---: | ---: |',
      '| A\\|B | 两行<br>内容 | C |',
      '',
      '<div align="center">居中</div>',
    ].join('\n');
    const editor = document.createElement('article');
    documentModel.render(editor, source, {interactive:false});
    const model = documentModel.normalize(editor);
    equal(documentModel.serialize(editor), source, '结构块往返结果');
    deepEqual(model.map(block => block.type), [
      'heading', 'paragraph', 'paragraph', 'heading', 'task-list', 'number-list', 'quote', 'code', 'code', 'code', 'divider', 'table', 'paragraph'
    ], '结构块类型');
    deepEqual(model.find(block => block.type === 'task-list').items.map(item => ({checked:item.checked, content:item.content})), [
      {checked:false, content:'项目'},
      {checked:false, content:'待处理'},
      {checked:true, content:'任务'},
    ], '任务列表模型');
    deepEqual(model.filter(block => block.type === 'code').map(block => block.markdown.split('\n')[0]), [
      '```javascript', '```python', '```shell'
    ], '代码语言');
    equal(model.find(block => block.type === 'table').markdown, '| 左 | 中 | 右 |\n| :--- | :---: | ---: |\n| A\\|B | 两行<br>内容 | C |', '表格对齐与转义');
    equal(new Set(model.map(block => block.id)).size, model.length, '块 ID 唯一');
    document.body.dataset.testResult = 'passed';
    document.body.textContent = `PASS ${model.map(block => block.type).join(',')}`;
  } else {
    console.log('Document model contract tests passed.');
  }
})(typeof window !== 'undefined' ? window : globalThis);
