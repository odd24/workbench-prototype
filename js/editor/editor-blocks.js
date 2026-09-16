(function initializeEditorBlocks(global) {
  'use strict';

  const selectionCore = global.Workbench?.editorSelection;
  const markdownCore = global.Workbench?.markdown;
  const documentModelCore = global.Workbench?.documentModel;

  function requireDependencies() {
    if (!selectionCore || !markdownCore || !documentModelCore) throw new Error('Editor block dependencies must load first');
  }

  function createBlock(document, tag, className = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.appendChild(document.createElement('br'));
    return element;
  }

  function isEmpty(node) {
    return !(node?.textContent || '').replace(/[\u200B\s]/g, '') && !node?.querySelector?.('img, input, .internal-link');
  }

  function structure(commandId, document, options = {}) {
    requireDependencies();
    const language = markdownCore.normalizeCodeLanguage(options.language || 'txt');
    let target;
    let nodes = [];
    if (['text', 'h1', 'h2', 'h3'].includes(commandId)) {
      target = createBlock(document, commandId === 'text' ? 'p' : commandId);
      nodes = [target];
    } else if (commandId === 'bullet' || commandId === 'number') {
      const list = document.createElement(commandId === 'bullet' ? 'ul' : 'ol');
      target = createBlock(document, 'li');
      list.appendChild(target);
      nodes = [list];
    } else if (commandId === 'task') {
      const list = document.createElement('ul');
      target = document.createElement('li');
      target.className = 'task-item';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.contentEditable = 'false';
      target.append(checkbox, document.createTextNode(' '), document.createElement('br'));
      list.appendChild(target);
      nodes = [list];
    } else if (commandId === 'quote') {
      const quote = document.createElement('blockquote');
      target = createBlock(document, 'p');
      quote.appendChild(target);
      nodes = [quote];
    } else if (commandId === 'code') {
      const pre = document.createElement('pre');
      target = document.createElement('code');
      target.dataset.language = language;
      target.appendChild(document.createElement('br'));
      pre.appendChild(target);
      nodes = [pre];
    } else if (commandId === 'divider') {
      target = createBlock(document, 'p');
      nodes = [document.createElement('hr'), target];
    } else if (commandId === 'table') {
      const wrap = document.createElement('div');
      wrap.className = 'editor-table-wrap';
      wrap.innerHTML = '<table><thead><tr><th><br></th><th><br></th><th><br></th></tr></thead><tbody><tr><td><br></td><td><br></td><td><br></td></tr><tr><td><br></td><td><br></td><td><br></td></tr></tbody></table>';
      target = wrap.querySelector('th');
      nodes = [wrap, createBlock(document, 'p')];
    }
    return {nodes, target};
  }

  function replaceWithStructure(editor, block, commandId, options = {}) {
    const {nodes, target} = structure(commandId, editor.ownerDocument, options);
    if (!nodes.length || !target) return false;
    if (block === editor) editor.replaceChildren(...nodes);
    else block.replaceWith(...nodes);
    selectionCore.placeCaret(target, true, options.selection);
    documentModelCore.hydrateEditorBlocks(editor);
    options.onChange?.();
    return true;
  }

  function insertTaskList(editor, options = {}) {
    requireDependencies();
    editor.focus();
    let selection = selectionCore.inside(editor, options.selection);
    if (!selection) {
      selectionCore.placeCaret(editor, false, options.selection);
      selection = selectionCore.inside(editor, options.selection);
    }
    if (!selection?.rangeCount) return false;
    const document = editor.ownerDocument;
    const selectedText = selection.toString().trim();
    const range = selection.getRangeAt(0);
    range.deleteContents();
    const marker = document.createElement('span');
    marker.dataset.taskInsertMarker = 'true';
    range.insertNode(marker);

    const list = document.createElement('ul');
    const item = document.createElement('li');
    item.className = 'task-item';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.contentEditable = 'false';
    const label = document.createTextNode(selectedText || options.placeholder || '待办项');
    item.append(checkbox, document.createTextNode(' '), label);
    list.appendChild(item);
    const after = createBlock(document, 'p');

    let topBlock = marker.parentElement;
    while (topBlock && topBlock !== editor && topBlock.parentElement !== editor) topBlock = topBlock.parentElement;
    const canSplit = topBlock && topBlock !== editor && ['P', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(topBlock.nodeName);
    if (canSplit) {
      const tailRange = document.createRange();
      tailRange.setStartAfter(marker);
      tailRange.setEnd(topBlock, topBlock.childNodes.length);
      const remainder = tailRange.extractContents();
      marker.remove();
      if (remainder.textContent || remainder.querySelector?.('img,br,.internal-link')) after.replaceChildren(remainder);
      if (isEmpty(topBlock)) topBlock.replaceWith(list, after);
      else topBlock.after(list, after);
    } else {
      marker.remove();
      if (topBlock && topBlock !== editor) topBlock.after(list, after);
      else editor.append(list, after);
    }

    const labelRange = document.createRange();
    labelRange.selectNodeContents(label);
    selection.removeAllRanges();
    selection.addRange(labelRange);
    documentModelCore.hydrateEditorBlocks(editor);
    options.onChange?.();
    return true;
  }

  function insertCodeBlock(editor, options = {}) {
    requireDependencies();
    editor.focus();
    let selection = selectionCore.inside(editor, options.selection);
    if (!selection) {
      selectionCore.placeCaret(editor, false, options.selection);
      selection = selectionCore.inside(editor, options.selection);
    }
    if (!selection?.rangeCount) return false;
    const document = editor.ownerDocument;
    const language = markdownCore.normalizeCodeLanguage(options.language || 'txt');
    const selectedText = selection.toString();
    const initialCode = selectedText || options.placeholder || '在这里输入代码';
    const pre = document.createElement('pre');
    const code = document.createElement('code');
    code.dataset.language = language;
    if (options.highlight) code.innerHTML = markdownCore.syntaxHighlightCode(initialCode, language) || '<br>';
    else code.textContent = initialCode;
    pre.appendChild(code);

    if (options.mode === 'split-selection') {
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const marker = document.createElement('span');
      marker.dataset.codeInsertMarker = 'true';
      range.insertNode(marker);
      const nearestBlock = selectionCore.closestBlock(marker, editor);
      let topBlock = nearestBlock;
      while (topBlock !== editor && topBlock.parentElement !== editor) topBlock = topBlock.parentElement;
      if (nearestBlock !== editor && topBlock === nearestBlock) {
        const trailing = document.createRange();
        trailing.setStartAfter(marker);
        trailing.setEnd(nearestBlock, nearestBlock.childNodes.length);
        const remainder = trailing.extractContents();
        marker.remove();
        const after = document.createElement(['P', 'DIV'].includes(nearestBlock.nodeName) ? nearestBlock.nodeName.toLowerCase() : 'p');
        after.appendChild(remainder);
        if (!after.textContent && !after.querySelector('img,br')) after.appendChild(document.createElement('br'));
        if (!nearestBlock.textContent && !nearestBlock.querySelector('img,br')) nearestBlock.replaceWith(pre);
        else nearestBlock.after(pre);
        pre.after(after);
      } else {
        marker.remove();
        const after = createBlock(document, 'p');
        if (topBlock === editor) editor.append(pre, after);
        else topBlock.after(pre, after);
      }
    } else {
      const block = selectionCore.closestBlock(selection.anchorNode, editor);
      if (block && block !== editor) block.replaceWith(pre);
      else editor.appendChild(pre);
      if (!pre.nextElementSibling) pre.after(createBlock(document, 'p'));
    }

    const codeRange = document.createRange();
    codeRange.selectNodeContents(code);
    if (options.mode !== 'split-selection' || selectedText) codeRange.collapse(false);
    selection.removeAllRanges();
    selection.addRange(codeRange);
    documentModelCore.hydrateEditorBlocks(editor);
    options.onChange?.();
    return codeRange.cloneRange();
  }

  function toggleBlockquote(editor, options = {}) {
    requireDependencies();
    const selection = selectionCore.inside(editor, options.selection);
    if (!selection) return false;
    const document = editor.ownerDocument;
    const block = selectionCore.closestBlock(selection.anchorNode, editor);
    const quote = block.closest?.('blockquote');
    if (quote) {
      const fragment = document.createDocumentFragment();
      const children = [...quote.children];
      if (children.length) children.forEach(child => fragment.appendChild(child));
      else {
        const paragraph = document.createElement('p');
        paragraph.innerHTML = quote.innerHTML || '<br>';
        fragment.appendChild(paragraph);
      }
      const last = fragment.lastChild;
      quote.replaceWith(fragment);
      selectionCore.placeCaret(last, false, selection);
    } else {
      const source = block === editor ? null : block;
      const quoteElement = document.createElement('blockquote');
      const paragraph = document.createElement('p');
      if (source) {
        paragraph.append(...source.childNodes);
        quoteElement.appendChild(paragraph);
        source.replaceWith(quoteElement);
      } else {
        paragraph.innerHTML = '<br>';
        quoteElement.appendChild(paragraph);
        editor.appendChild(quoteElement);
      }
      selectionCore.placeCaret(paragraph, false, selection);
    }
    documentModelCore.hydrateEditorBlocks(editor);
    options.onChange?.();
    return true;
  }

  function handleTaskListEnter(event, options = {}) {
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return false;
    const editor = options.editor || event.currentTarget;
    const selection = selectionCore.inside(editor, options.selection);
    if (!selection?.isCollapsed) return false;
    const element = selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement;
    const item = element?.closest('li.task-item');
    if (!item) return false;
    event.preventDefault();
    const document = editor.ownerDocument;
    const list = item.parentElement;
    if (!(item.textContent || '').trim()) {
      const paragraph = createBlock(document, 'p');
      item.remove();
      list.after(paragraph);
      if (!list.children.length) list.remove();
      selectionCore.placeCaret(paragraph, true, selection);
    } else {
      const range = selection.getRangeAt(0);
      const tailRange = document.createRange();
      tailRange.setStart(range.startContainer, range.startOffset);
      tailRange.setEnd(item, item.childNodes.length);
      const tail = tailRange.extractContents();
      const next = document.createElement('li');
      next.className = 'task-item';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.contentEditable = 'false';
      next.append(checkbox, document.createTextNode(' '), tail);
      item.after(next);
      selectionCore.placeCaret(next, false, selection);
    }
    documentModelCore.hydrateEditorBlocks(editor);
    options.onChange?.();
    return true;
  }

  function handleQuoteEnter(event, options = {}) {
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return false;
    const editor = options.editor || event.currentTarget;
    const selection = selectionCore.inside(editor, options.selection);
    if (!selection) return false;
    const element = selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement;
    const quote = element?.closest('blockquote');
    if (!quote) return false;
    event.preventDefault();
    if (!selection.isCollapsed) selection.getRangeAt(0).deleteContents();
    const document = editor.ownerDocument;
    let block = selectionCore.closestBlock(selection.anchorNode, editor);
    if (block === quote) {
      const paragraph = document.createElement('p');
      paragraph.append(...quote.childNodes);
      if (!paragraph.childNodes.length) paragraph.innerHTML = '<br>';
      quote.appendChild(paragraph);
      block = paragraph;
      selectionCore.placeCaret(block, false, selection);
    }
    if (isEmpty(block)) {
      const paragraph = createBlock(document, 'p');
      block.remove();
      quote.after(paragraph);
      if (!quote.textContent.trim() && !quote.querySelector('img, input, .internal-link')) quote.remove();
      selectionCore.placeCaret(paragraph, true, selection);
    } else {
      const range = selection.getRangeAt(0);
      const tailRange = document.createRange();
      tailRange.setStart(range.startContainer, range.startOffset);
      tailRange.setEnd(block, block.childNodes.length);
      const paragraph = document.createElement('p');
      paragraph.appendChild(tailRange.extractContents());
      if (isEmpty(paragraph)) paragraph.innerHTML = '<br>';
      block.after(paragraph);
      selectionCore.placeCaret(paragraph, true, selection);
    }
    documentModelCore.hydrateEditorBlocks(editor);
    options.onChange?.();
    return true;
  }

  function handleCodeBlockEnter(event, options = {}) {
    if (event.key !== 'Enter' || event.isComposing) return false;
    const editor = options.editor || event.currentTarget;
    const selection = selectionCore.inside(editor, options.selection);
    if (!selection) return false;
    const element = selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement;
    const pre = element?.closest('pre');
    const code = pre?.querySelector('code');
    if (!pre || !code) return false;
    const range = selection.getRangeAt(0);
    if (!code.contains(range.startContainer) || !code.contains(range.endContainer)) return false;
    event.preventDefault();
    const document = editor.ownerDocument;
    const beforeRange = document.createRange();
    beforeRange.selectNodeContents(code);
    beforeRange.setEnd(range.startContainer, range.startOffset);
    const afterRange = document.createRange();
    afterRange.selectNodeContents(code);
    afterRange.setStart(range.endContainer, range.endOffset);
    const before = documentModelCore.codeElementToText(beforeRange.cloneContents());
    const after = documentModelCore.codeElementToText(afterRange.cloneContents());
    const shouldExit = (event.ctrlKey || event.metaKey) || (!event.shiftKey && selection.isCollapsed && !after && before.endsWith('\n\n'));
    if (shouldExit) {
      const language = markdownCore.normalizeCodeLanguage(code.dataset.language);
      const content = documentModelCore.codeElementToText(code).replace(/\n$/, '');
      code.innerHTML = markdownCore.syntaxHighlightCode(content, language) || '<br>';
      let paragraph = pre.nextElementSibling;
      if (!paragraph || paragraph.nodeName !== 'P' || !isEmpty(paragraph)) {
        paragraph = createBlock(document, 'p');
        pre.after(paragraph);
      }
      selectionCore.placeCaret(paragraph, true, selection);
    } else selectionCore.insertLineBreak(editor, selection);
    documentModelCore.hydrateEditorBlocks(editor);
    options.onChange?.();
    return true;
  }

  function insertReference(editor, html, options = {}) {
    requireDependencies();
    editor.focus();
    let selection = selectionCore.inside(editor, options.selection);
    if (!selection) {
      selectionCore.placeCaret(editor, false, options.selection);
      selection = selectionCore.inside(editor, options.selection);
    }
    if (!selection?.rangeCount) return null;
    const document = editor.ownerDocument;
    const template = document.createElement('template');
    template.innerHTML = html;
    const fragment = template.content;
    const lastNode = fragment.lastChild;
    const range = selection.getRangeAt(0);
    range.deleteContents();
    range.insertNode(fragment);
    const caret = document.createRange();
    caret.setStartAfter(lastNode);
    caret.collapse(true);
    selection.removeAllRanges();
    selection.addRange(caret);
    documentModelCore.hydrateEditorBlocks(editor);
    options.onChange?.();
    return caret.cloneRange();
  }

  const api = {
    createBlock,
    handleCodeBlockEnter,
    handleQuoteEnter,
    handleTaskListEnter,
    insertCodeBlock,
    insertReference,
    insertTaskList,
    isEmpty,
    replaceWithStructure,
    structure,
    toggleBlockquote,
  };
  global.Workbench = global.Workbench || {};
  global.Workbench.editorBlocks = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
