(function runEditorBlocksContract(global) {
  'use strict';

  const isCommonJs = typeof module !== 'undefined' && module.exports;
  const assert = isCommonJs ? require('node:assert/strict') : null;
  if (isCommonJs) {
    require('./js/editor/markdown.js');
    require('./js/editor/document-model.js');
    require('./js/editor/editor-selection.js');
    require('./js/editor/editor-blocks.js');
  }
  const selectionCore = isCommonJs ? require('./js/editor/editor-selection.js') : global.Workbench.editorSelection;
  const blocks = isCommonJs ? require('./js/editor/editor-blocks.js') : global.Workbench.editorBlocks;
  const editorHost = isCommonJs ? require('./js/editor/editor-host.js') : global.Workbench.editorHost;
  const documentModel = global.Workbench.documentModel;
  const markdown = global.Workbench.markdown;

  function equal(actual, expected, message = '') {
    if (assert) return assert.equal(actual, expected, message);
    if (actual !== expected) throw new Error(`${message || '值不一致'}\n期望：${expected}\n实际：${actual}`);
  }

  ['inside', 'capture', 'restore', 'placeCaret', 'insertText'].forEach(name => equal(typeof selectionCore[name], 'function', `selection.${name}`));
  ['replaceWithStructure', 'insertTaskList', 'insertCodeBlock', 'toggleBlockquote', 'insertReference'].forEach(name => equal(typeof blocks[name], 'function', `blocks.${name}`));
  equal(typeof editorHost.create, 'function', 'editorHost.create');

  if (typeof document !== 'undefined') {
    const host = document.createElement('section');
    document.body.appendChild(host);
    const createEditor = source => {
      const editor = document.createElement('article');
      editor.contentEditable = 'true';
      host.appendChild(editor);
      documentModel.render(editor, source, {interactive:true});
      return editor;
    };
    const selectContents = node => {
      const range = document.createRange();
      range.selectNodeContents(node);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      return selection;
    };

    const caretEditor = createEditor('正文');
    selectionCore.placeCaret(caretEditor.firstElementChild, false);
    const savedRange = selectionCore.capture(caretEditor);
    equal(Boolean(savedRange), true, '捕获选区');
    window.getSelection().removeAllRanges();
    equal(selectionCore.restore(caretEditor, savedRange), true, '恢复选区');
    equal(selectionCore.insertText('追加', caretEditor), true, '插入文本');
    equal(documentModel.serialize(caretEditor), '正文追加', '光标文本结果');

    const taskEditor = createEditor('任务内容');
    selectContents(taskEditor.firstElementChild);
    let changes = 0;
    equal(blocks.insertTaskList(taskEditor, {onChange:() => changes++}), true, '插入任务列表');
    equal(documentModel.serialize(taskEditor), '- [ ] 任务内容', '任务列表结果');
    equal(changes, 1, '任务列表变更回调');

    const quoteEditor = createEditor('引用内容');
    selectionCore.placeCaret(quoteEditor.firstElementChild, false);
    equal(blocks.toggleBlockquote(quoteEditor), true, '切换引用块');
    equal(documentModel.serialize(quoteEditor), '> 引用内容', '引用块结果');

    const codeEditor = createEditor('const value = 1;');
    selectContents(codeEditor.firstElementChild);
    equal(Boolean(blocks.insertCodeBlock(codeEditor, {language:'javascript', mode:'replace-block'})), true, '插入代码块');
    equal(documentModel.serialize(codeEditor), '```javascript\nconst value = 1;\n```', '代码块结果');

    const referenceEditor = createEditor('引用：');
    selectionCore.placeCaret(referenceEditor.firstElementChild, false);
    const referenceHtml = markdown.referenceTokenToHtml('DOC-12', id => ({id, type:'document', title:'说明'}));
    equal(Boolean(blocks.insertReference(referenceEditor, referenceHtml)), true, '插入引用');
    equal(documentModel.serialize(referenceEditor), '引用：[[DOC-12]]', '引用结果');

    const tableEditor = createEditor('表格');
    blocks.replaceWithStructure(tableEditor, tableEditor.firstElementChild, 'table');
    equal(tableEditor.firstElementChild.classList.contains('editor-table-wrap'), true, '表格结构');
    equal(documentModel.normalize(tableEditor)[0].type, 'table', '表格模型');

    const dividerEditor = createEditor('分隔');
    blocks.replaceWithStructure(dividerEditor, dividerEditor.firstElementChild, 'divider');
    equal(documentModel.serialize(dividerEditor), '---', '分隔线结果');

    const listStructures = ['bullet', 'number'].map(command => blocks.structure(command, document).nodes[0].nodeName);
    equal(listStructures.join(','), 'UL,OL', '普通列表结构');

    const sharedSource = [
      '# 同一内容',
      '',
      '正文 **加粗** *斜体* ~~删除~~ <u>下划线</u>',
      '',
      '<span style="color:#123456;background-color:#abcdef">受控颜色</span>',
      '',
      '- [ ] 待处理',
      '- [x] 完成',
      '',
      '```javascript',
      'const ok = true;',
      '```',
      '',
      '| 左 | 中 | 右 |',
      '| :--- | :---: | ---: |',
      '| A | B | C |',
      '',
      '<div align="right">右对齐</div>',
    ].join('\n');
    const recordSurface = createEditor('');
    const documentSurface = createEditor('');
    const recordHost = editorHost.create({editor:recordSurface});
    const documentHost = editorHost.create({editor:documentSurface});
    recordHost.render(sharedSource, true);
    documentHost.render(sharedSource, true);
    equal(recordHost.serialize(), documentHost.serialize(), '双编辑器序列化一致');
    equal(recordHost.serialize(), sharedSource, '共享 Markdown 往返');
    documentHost.render(documentHost.serialize(), true);
    equal(documentHost.serialize(), sharedSource, '保存重开无损');

    const tableWrap = document.createElement('div');
    tableWrap.className = 'editor-table-wrap';
    tableWrap.innerHTML = '<table><tbody><tr><td>单元格</td></tr></tbody></table>表格后正文';
    recordSurface.replaceChildren(tableWrap);
    equal(recordHost.serialize(), '| 单元格 |\n| :--- |\n\n表格后正文', '表格后输入不会丢失');
    host.remove();
    document.body.dataset.testResult = 'passed';
    document.body.textContent = 'PASS shared-host,round-trip,html-extension,task-states,code-language,table-alignment,table-tail,selection,caret,bullet-list,number-list,task-list,reference,code,quote,table,divider';
  } else {
    console.log('Editor selection and block contract tests passed.');
  }
})(typeof window !== 'undefined' ? window : globalThis);
