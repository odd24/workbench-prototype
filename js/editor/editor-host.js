(function initializeEditorHost(global) {
  'use strict';

  const documentModelCore = global.Workbench?.documentModel;
  const selectionCore = global.Workbench?.editorSelection;
  const blocksCore = global.Workbench?.editorBlocks;

  function create(options = {}) {
    const {editor, onChange = () => {}, renderOptions = () => ({})} = options;
    if (!editor || !documentModelCore || !selectionCore || !blocksCore) throw new Error('Editor host dependencies are incomplete');
    let savedRange = null;
    const change = () => onChange();
    const selection = () => selectionCore.inside(editor);

    return {
      editor,
      render(markdown, interactive = true) {
        documentModelCore.render(editor, markdown, {interactive, ...renderOptions()});
        savedRange = null;
        return editor;
      },
      normalize() {
        return documentModelCore.normalize(editor);
      },
      serialize() {
        return documentModelCore.serialize(editor);
      },
      selection,
      captureSelection(activeSelection) {
        const range = selectionCore.capture(editor, activeSelection);
        if (!range) return false;
        savedRange = range;
        return true;
      },
      restoreSelection(activeSelection) {
        return selectionCore.restore(editor, savedRange, activeSelection);
      },
      clearSelection() {
        savedRange = null;
      },
      savedSelection() {
        return savedRange?.cloneRange() || null;
      },
      setSelection(range) {
        savedRange = range?.cloneRange?.() || null;
        return savedRange;
      },
      placeCaret(node = editor, atStart = true, activeSelection) {
        const range = selectionCore.placeCaret(node, atStart, activeSelection);
        if (range) savedRange = range.cloneRange();
        return range;
      },
      insertText(text, activeSelection) {
        const result = selectionCore.insertText(text, editor, activeSelection);
        if (result) this.captureSelection(activeSelection);
        return result;
      },
      pastePlainText(text, activeSelection) {
        const result = selectionCore.pastePlainText(text, editor, activeSelection);
        if (result) this.captureSelection(activeSelection);
        return result;
      },
      replaceWithStructure(block, commandId, blockOptions = {}) {
        const result = blocksCore.replaceWithStructure(editor, block, commandId, {...blockOptions, onChange:change});
        if (result) this.captureSelection();
        return result;
      },
      insertTaskList(blockOptions = {}) {
        const result = blocksCore.insertTaskList(editor, {...blockOptions, onChange:change});
        if (result) this.captureSelection();
        return result;
      },
      insertCodeBlock(blockOptions = {}) {
        const range = blocksCore.insertCodeBlock(editor, {...blockOptions, onChange:change});
        if (range) this.setSelection(range);
        return range;
      },
      toggleBlockquote(blockOptions = {}) {
        const result = blocksCore.toggleBlockquote(editor, {...blockOptions, onChange:change});
        if (result) this.captureSelection();
        return result;
      },
      insertReference(html, blockOptions = {}) {
        const range = blocksCore.insertReference(editor, html, {...blockOptions, onChange:change});
        if (range) this.setSelection(range);
        return range;
      },
      handleStructuralKeydown(event) {
        const blockOptions = {editor, onChange:change};
        const handled = blocksCore.handleTaskListEnter(event, blockOptions)
          || blocksCore.handleCodeBlockEnter(event, blockOptions)
          || blocksCore.handleQuoteEnter(event, blockOptions);
        if (handled) this.captureSelection();
        return handled;
      },
    };
  }

  const api = {create};
  global.Workbench = global.Workbench || {};
  global.Workbench.editorHost = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
