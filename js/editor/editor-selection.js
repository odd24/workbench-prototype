(function initializeEditorSelection(global) {
  'use strict';

  function selectionFor(editor, selection) {
    return selection || editor?.ownerDocument?.defaultView?.getSelection?.() || global.getSelection?.();
  }

  function inside(editor, selection) {
    const active = selectionFor(editor, selection);
    return active?.rangeCount && editor?.contains(active.anchorNode) ? active : null;
  }

  function closestBlock(node, editor) {
    const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
    return element?.closest('p, div, h1, h2, h3, h4, h5, h6, pre, blockquote, li, td, th') || editor;
  }

  function capture(editor, selection) {
    const active = inside(editor, selection);
    return active ? active.getRangeAt(0).cloneRange() : null;
  }

  function restore(editor, savedRange, selection) {
    if (!savedRange || !editor?.contains(savedRange.commonAncestorContainer)) return false;
    const active = selectionFor(editor, selection);
    if (!active) return false;
    active.removeAllRanges();
    active.addRange(savedRange.cloneRange());
    return true;
  }

  function placeCaret(node, atStart = true, selection) {
    if (!node) return null;
    const document = node.ownerDocument;
    const range = document.createRange();
    range.selectNodeContents(node);
    range.collapse(atStart);
    const active = selectionFor(node, selection);
    active?.removeAllRanges();
    active?.addRange(range);
    return range;
  }

  function insertText(text, editor, selection) {
    const active = inside(editor, selection);
    if (!active) return false;
    const range = active.getRangeAt(0);
    range.deleteContents();
    const textNode = editor.ownerDocument.createTextNode(text);
    range.insertNode(textNode);
    range.setStartAfter(textNode);
    range.collapse(true);
    active.removeAllRanges();
    active.addRange(range);
    return true;
  }

  function pastePlainText(text, editor, selection) {
    if (!editor || typeof text !== 'string') return false;
    editor.focus();
    const document = editor.ownerDocument;
    if (document.execCommand('insertText', false, text)) return true;
    const active = inside(editor, selection);
    if (!active) return false;
    const range = active.getRangeAt(0);
    range.deleteContents();
    const fragment = document.createDocumentFragment();
    const lines = text.replace(/\r\n?/g, '\n').split('\n');
    let caretNode = null;
    lines.forEach((line, index) => {
      if (index) { caretNode = document.createElement('br'); fragment.appendChild(caretNode); }
      if (line) { caretNode = document.createTextNode(line); fragment.appendChild(caretNode); }
    });
    if (!caretNode) { caretNode = document.createTextNode(''); fragment.appendChild(caretNode); }
    range.insertNode(fragment);
    range.setStartAfter(caretNode);
    range.collapse(true);
    active.removeAllRanges();
    active.addRange(range);
    return true;
  }

  function insertLineBreak(editor, selection) {
    const active = inside(editor, selection);
    if (!active) return false;
    const range = active.getRangeAt(0);
    range.deleteContents();
    const document = editor.ownerDocument;
    const lineBreak = document.createElement('br');
    const caretAnchor = document.createTextNode('\u200B');
    range.insertNode(lineBreak);
    lineBreak.after(caretAnchor);
    range.setStartAfter(caretAnchor);
    range.collapse(true);
    active.removeAllRanges();
    active.addRange(range);
    return true;
  }

  const api = {capture, closestBlock, inside, insertLineBreak, insertText, pastePlainText, placeCaret, restore};
  global.Workbench = global.Workbench || {};
  global.Workbench.editorSelection = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
