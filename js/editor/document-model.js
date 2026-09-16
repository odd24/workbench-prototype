(function initializeDocumentModel(global) {
  'use strict';

  const markdownCore = global.Workbench?.markdown;
  let editorBlockSequence = 0;

  function requireMarkdownCore() {
    if (!markdownCore) throw new Error('Workbench.markdown must load before Workbench.documentModel');
    return markdownCore;
  }

  function inlineNodeToMarkdown(node) {
    if (node.nodeType === Node.TEXT_NODE) return (node.nodeValue || '').replace(/\u200B/g, '');
    if (node.nodeType !== Node.ELEMENT_NODE) return '';
    const element = node;
    if (element.nodeName === 'SPAN' && element.dataset.documentColorBoundary) return [...element.childNodes].map(inlineNodeToMarkdown).join('').replace(/\u200b/g, '');
    if (element.matches('.internal-link[data-reference-id]')) return `[[${element.dataset.referenceToken || element.dataset.referenceId}]]`;
    if (element.matches('.after-reference-paragraph')) return '';
    if (element.nodeName === 'INPUT') return '';
    if (element.nodeName === 'IMG') return `![${element.getAttribute('alt') || ''}](${element.dataset.markdownSrc || element.getAttribute('src') || ''})`;
    if (element.nodeName === 'BR') return '\n';
    const content = [...element.childNodes].map(inlineNodeToMarkdown).join('');
    if (['STRONG', 'B'].includes(element.nodeName)) return `**${content}**`;
    if (['EM', 'I'].includes(element.nodeName)) return `*${content}*`;
    if (['S', 'STRIKE', 'DEL'].includes(element.nodeName)) return `~~${content}~~`;
    if (element.nodeName === 'U') return `<u>${content}</u>`;
    if (element.nodeName === 'FONT') {
      const color = requireMarkdownCore().cssColorToHex(element.getAttribute('color') || element.style.color);
      const background = requireMarkdownCore().cssColorToHex(element.style.backgroundColor);
      if (color || background) return `<span style="${color ? `color:${color}` : ''}${color && background ? ';' : ''}${background ? `background-color:${background}` : ''}">${content}</span>`;
    }
    if (element.nodeName === 'SPAN') {
      const color = requireMarkdownCore().cssColorToHex(element.style.color);
      const background = requireMarkdownCore().cssColorToHex(element.style.backgroundColor);
      if (color || background) return `<span style="${color ? `color:${color}` : ''}${color && background ? ';' : ''}${background ? `background-color:${background}` : ''}">${content}</span>`;
    }
    if (element.nodeName === 'CODE') return `\`${content}\``;
    if (element.nodeName === 'A') return `[${content}](${element.getAttribute('href') || ''})`;
    return content;
  }

  function codeElementToText(root) {
    const output = [];
    const appendNewline = () => { if (output.at(-1) !== '\n') output.push('\n'); };
    const visit = node => {
      if (node.nodeType === Node.TEXT_NODE) {
        output.push(node.nodeValue || '');
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return;
      if (node.nodeName === 'BR') {
        output.push('\n');
        return;
      }
      const blockLine = ['DIV', 'P'].includes(node.nodeName);
      if (blockLine && node.previousSibling) appendNewline();
      node.childNodes.forEach(visit);
      if (blockLine && node.nextSibling) appendNewline();
    };
    root.childNodes.forEach(visit);
    return output.join('').replace(/\u200B/g, '').replace(/\r\n?/g, '\n');
  }

  function tableElementToMarkdown(table) {
    const rows = [...table.rows];
    if (!rows.length) return '';
    const columnCount = Math.max(...rows.map(row => row.cells.length));
    const values = rows.map(row => Array.from({length:columnCount}, (_, column) => {
      const cell = row.cells[column];
      return cell ? inlineNodeToMarkdown(cell).trim().replace(/\|/g, '\\|').replace(/\n+/g, '<br>') : '';
    }));
    const firstCells = [...rows[0].cells];
    const separators = Array.from({length:columnCount}, (_, column) => {
      const alignment = firstCells[column]?.style.textAlign || '';
      return alignment === 'center' ? ':---:' : alignment === 'right' ? '---:' : ':---';
    });
    return [values[0], separators, ...values.slice(1)].map(row => `| ${row.join(' | ')} |`).join('\n');
  }

  function serializeEditorNode(node) {
    const table = node.nodeName === 'TABLE'
      ? node
      : node.nodeType === Node.ELEMENT_NODE && node.classList.contains('editor-table-wrap')
        ? node.querySelector('table')
        : null;
    if (table) return tableElementToMarkdown(table);
    if (node.nodeName === 'PRE') {
      const code = node.querySelector('code');
      const language = code?.dataset.language || '';
      return `\`\`\`${language}\n${codeElementToText(code || node).replace(/\n$/, '')}\n\`\`\``;
    }
    if (node.nodeName === 'BLOCKQUOTE') {
      const quoteBlocks = [...node.childNodes].filter(child => child.nodeType === Node.ELEMENT_NODE && ['P', 'DIV'].includes(child.nodeName));
      const quoteLines = quoteBlocks.length
        ? quoteBlocks.map(child => inlineNodeToMarkdown(child).trim())
        : [inlineNodeToMarkdown(node).trim()];
      return quoteLines.filter(Boolean).map(line => `> ${line}`).join('\n');
    }
    if (node.nodeName === 'UL') {
      return [...node.children].map(item => {
        const content = inlineNodeToMarkdown(item).trim();
        if (item.classList.contains('task-item')) return `- [${item.querySelector('input')?.checked ? 'x' : ' '}]${content ? ` ${content}` : ''}`;
        return `-${content ? ` ${content}` : ''}`;
      }).join('\n');
    }
    if (node.nodeName === 'OL') {
      return [...node.children].map((item, index) => {
        const content = inlineNodeToMarkdown(item).trim();
        return `${index + 1}.${content ? ` ${content}` : ''}`;
      }).join('\n');
    }
    if (node.nodeName === 'HR') return '---';
    const text = inlineNodeToMarkdown(node).trim();
    if (!text) return '';
    if (/^H[1-6]$/.test(node.nodeName)) return `${'#'.repeat(Number(node.nodeName.slice(1)))} ${text}`;
    if (node.nodeName === 'DIV' && ['left', 'center', 'right'].includes(node.style?.textAlign)) return `<div align="${node.style.textAlign}">${text}</div>`;
    return text;
  }

  function serializeEditorNodesToMarkdown(editor) {
    return [...editor.childNodes].map(serializeEditorNode).filter(Boolean).join('\n\n');
  }

  function editorBlockType(node) {
    if (node?.nodeType === Node.TEXT_NODE) return 'paragraph';
    if (node?.nodeType !== Node.ELEMENT_NODE) return 'unknown';
    if (node.nodeName === 'TABLE' || node.classList.contains('editor-table-wrap')) return 'table';
    if (/^H[1-6]$/.test(node.nodeName)) return 'heading';
    if (node.nodeName === 'UL') return [...node.children].some(item => item.classList.contains('task-item')) ? 'task-list' : 'bullet-list';
    if (node.nodeName === 'OL') return 'number-list';
    if (node.nodeName === 'BLOCKQUOTE') return 'quote';
    if (node.nodeName === 'PRE') return 'code';
    if (node.nodeName === 'HR') return 'divider';
    return 'paragraph';
  }

  function nextEditorBlockId() {
    editorBlockSequence += 1;
    return `block-${Date.now().toString(36)}-${editorBlockSequence.toString(36)}`;
  }

  function hydrateEditorBlocks(editor) {
    if (!editor) return editor;
    [...editor.children].forEach(block => {
      block.dataset.editorBlockType = editorBlockType(block);
      if (!block.dataset.editorBlockId) block.dataset.editorBlockId = nextEditorBlockId();
      if (['UL', 'OL'].includes(block.nodeName)) {
        [...block.children].forEach(item => {
          if (!item.dataset.editorBlockId) item.dataset.editorBlockId = nextEditorBlockId();
          if (item.classList.contains('task-item')) {
            item.dataset.editorBlockType = 'task';
            const checkbox = item.querySelector('input[type="checkbox"]');
            if (checkbox) checkbox.contentEditable = 'false';
          } else item.dataset.editorBlockType = 'list-item';
        });
      }
    });
    return editor;
  }

  function editorModelBlock(node, inheritedId = '') {
    const markdown = serializeEditorNode(node);
    if (!markdown) return null;
    const element = node.nodeType === Node.ELEMENT_NODE ? node : null;
    const type = editorBlockType(node);
    const block = {id:element?.dataset.editorBlockId || inheritedId || nextEditorBlockId(), type, markdown};
    if (type === 'heading') block.level = Number(node.nodeName.slice(1));
    if (type === 'task-list') {
      block.items = [...node.children].map(item => ({
        id:item.dataset.editorBlockId || nextEditorBlockId(),
        checked:Boolean(item.querySelector('input[type="checkbox"]')?.checked),
        content:inlineNodeToMarkdown(item).trim(),
      }));
    }
    return block;
  }

  function editorNodeToModelBlocks(node) {
    const element = node.nodeType === Node.ELEMENT_NODE ? node : null;
    const canContainAccidentalBlocks = element && ['P', 'DIV'].includes(element.nodeName) && !element.classList.contains('editor-table-wrap');
    const structuralChild = child => child.nodeType === Node.ELEMENT_NODE && (
      ['P', 'DIV', 'UL', 'OL', 'PRE', 'BLOCKQUOTE', 'HR', 'TABLE', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(child.nodeName)
      || child.classList.contains('editor-table-wrap')
    );
    if (!canContainAccidentalBlocks || ![...element.childNodes].some(structuralChild)) {
      const block = editorModelBlock(node);
      return block ? [block] : [];
    }

    const blocks = [];
    let inlineNodes = [];
    const flushInline = () => {
      if (!inlineNodes.length) return;
      const container = element.cloneNode(false);
      inlineNodes.forEach(child => container.appendChild(child.cloneNode(true)));
      const block = editorModelBlock(container, element.dataset.editorBlockId);
      if (block) blocks.push(block);
      inlineNodes = [];
    };
    [...element.childNodes].forEach(child => {
      if (structuralChild(child)) {
        flushInline();
        blocks.push(...editorNodeToModelBlocks(child));
      } else inlineNodes.push(child);
    });
    flushInline();
    return blocks;
  }

  function editorToDocumentModel(editor) {
    hydrateEditorBlocks(editor);
    return [...editor.childNodes].flatMap(editorNodeToModelBlocks);
  }

  function documentModelToMarkdown(model) {
    return Array.isArray(model) ? model.map(block => block?.markdown).filter(Boolean).join('\n\n') : '';
  }

  function serialize(editor) {
    return documentModelToMarkdown(editorToDocumentModel(editor));
  }

  function render(editor, markdown, options = {}) {
    const {interactive = true, renderReference, renderImage} = options;
    editor.innerHTML = requireMarkdownCore().markdownToHtml(markdown, {interactive, renderReference, renderImage});
    return hydrateEditorBlocks(editor);
  }

  const api = {
    codeElementToText,
    documentModelToMarkdown,
    editorBlockType,
    editorToDocumentModel,
    hydrateEditorBlocks,
    inlineNodeToMarkdown,
    normalize:editorToDocumentModel,
    render,
    serialize,
    serializeEditorNodesToMarkdown,
    tableElementToMarkdown,
  };
  global.Workbench = global.Workbench || {};
  global.Workbench.documentModel = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
