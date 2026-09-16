(function initializeMarkdownCore(global) {
  'use strict';

  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));

  function unescapeHtml(value) {
    return String(value).replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&amp;/g, '&');
  }

  function safeColor(value, fallback = '#64748b') {
    return /^#[0-9a-f]{6}$/i.test(value || '') ? value.toLowerCase() : fallback;
  }

  function cssColorToHex(value = '') {
    const text = String(value).trim();
    if (!text || text.toLowerCase() === 'transparent' || (/^rgba\(/i.test(text) && /[,/]\s*0(?:\.0+)?\s*\)$/.test(text))) return '';
    if (/^#[0-9a-f]{6}$/i.test(text)) return text.toLowerCase();
    if (/^#[0-9a-f]{3}$/i.test(text)) return `#${[...text.slice(1)].map(character => character + character).join('')}`.toLowerCase();
    const rgb = text.match(/^rgba?\(\s*(\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)/i);
    if (!rgb) return '';
    return `#${rgb.slice(1, 4).map(channel => Math.max(0, Math.min(255, Number(channel))).toString(16).padStart(2, '0')).join('')}`;
  }

  function normalizeCodeLanguage(language = 'txt') {
    const value = String(language).toLowerCase().trim();
    const aliases = {text:'txt', plaintext:'txt', js:'javascript', ts:'typescript', py:'python', sh:'shell', bash:'shell', html:'html', xml:'html', yml:'yaml', csharp:'csharp', 'c#':'csharp', cpp:'cpp', 'c++':'cpp'};
    return aliases[value] || value.replace(/[^a-z0-9+#.-]/g, '') || 'txt';
  }

  function parseReferenceToken(token = '') {
    const match = String(token).match(/^([A-Za-z]+-\d+)(?:#(body|attachment)(?::(.+))?)?$/);
    if (!match) return null;
    let attachmentName = '';
    if (match[2] === 'attachment' && match[3]) {
      try { attachmentName = decodeURIComponent(match[3]); }
      catch { attachmentName = match[3]; }
    }
    return {id:match[1].toUpperCase(), kind:match[2] || '', attachmentName};
  }

  function referenceTokenDetails(token, resolveTarget = () => null) {
    const parsed = parseReferenceToken(token);
    if (!parsed) return {token, id:'', kind:'', label:token, title:'引用内容'};
    const target = resolveTarget(parsed.id);
    const isDocument = target?.type === 'document' || parsed.id.startsWith('DOC-');
    const kind = parsed.kind || (isDocument ? 'document' : 'body');
    const title = target?.title || parsed.id;
    const label = kind === 'attachment'
      ? `${parsed.id} · ${parsed.attachmentName || '附件'}`
      : kind === 'body' ? `${parsed.id} · ${title} · 正文` : `${parsed.id} · ${title}`;
    return {...parsed, token, kind, label, title, target};
  }

  function referenceTokenToHtml(token, resolveTarget = () => null) {
    const detail = referenceTokenDetails(token, resolveTarget);
    const className = detail.kind === 'attachment' ? ' reference-attachment-link' : detail.kind === 'document' ? ' reference-document-link' : '';
    const actionTitle = detail.kind === 'attachment' ? '打开引用附件' : detail.kind === 'document' ? '打开知识库文档' : '打开引用正文';
    return `<span class="internal-link${className}" contenteditable="false" role="button" tabindex="0" data-reference-id="${escapeHtml(detail.id)}" data-reference-token="${escapeHtml(detail.token)}" title="${actionTitle}">${escapeHtml(detail.label)}</span>&#8203;`;
  }

  function syntaxHighlightCode(code, language = 'txt') {
    const lang = normalizeCodeLanguage(language);
    if (lang === 'txt') return escapeHtml(code);
    const keywordSets = {
      javascript:'break case catch class const continue debugger default delete do else export extends finally for function if import in instanceof let new return static super switch this throw try typeof var void while with yield async await of true false null undefined',
      typescript:'abstract any as asserts bigint boolean break case catch class const constructor continue declare default delete do else enum export extends false finally for from function get if implements import in infer instanceof interface is keyof let module namespace never new null number object of package private protected public readonly require return set static string super switch symbol this throw true try type typeof undefined unique unknown var void while with yield async await',
      python:'and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield match case',
      java:'abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while true false null',
      c:'auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while',
      cpp:'alignas alignof and asm auto bool break case catch char class const constexpr continue default delete do double else enum explicit export extern false float for friend goto if inline int long namespace new nullptr operator private protected public register reinterpret_cast return short signed sizeof static struct switch template this throw true try typedef typename union unsigned using virtual void volatile while',
      csharp:'abstract as base bool break byte case catch char checked class const continue decimal default delegate do double else enum event explicit extern false finally fixed float for foreach goto if implicit in int interface internal is lock long namespace new null object operator out override params private protected public readonly ref return sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof uint ulong unchecked unsafe ushort using virtual void volatile while async await var',
      go:'break default func interface select case defer go map struct chan else goto package switch const fallthrough if range type continue for import return var true false nil',
      rust:'as async await break const continue crate dyn else enum extern false fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait true type unsafe use where while',
      css:'align-items background border bottom color content display flex font gap grid height justify-content left margin max-width min-height opacity overflow padding position right top transform transition width',
      json:'true false null',
      sql:'add all alter and any as asc backup between by case check column constraint create database default delete desc distinct drop exec exists foreign from full group having in index inner insert into is join key left like limit not null on or order outer primary procedure right rownum select set table top truncate union unique update values view where',
      shell:'case do done elif else esac fi for function if in local readonly return then until while export true false',
      yaml:'true false null yes no on off',
      markdown:''
    };
    const slashComments = ['javascript','typescript','java','c','cpp','csharp','go','rust','css'].includes(lang);
    const hashComments = ['python','shell','yaml'].includes(lang);
    const patterns = [];
    if (lang === 'html') patterns.push({type:'comment', source:'<!--[\\s\\S]*?-->'}, {type:'tag', source:'<\\/?[A-Za-z][^>]*>'});
    else if (lang === 'sql') patterns.push({type:'comment', source:'--[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/'});
    else if (slashComments) patterns.push({type:'comment', source:'\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*'});
    else if (hashComments) patterns.push({type:'comment', source:'#[^\\n]*'});
    if (lang === 'markdown') patterns.push({type:'keyword', source:'^#{1,6}[^\\n]*|^\\s*(?:[-*+] |\\d+\\. )'});
    patterns.push({type:'string', source:'"(?:\\\\.|[^"\\\\])*"|\'(?:\\\\.|[^\'\\\\])*\'|`(?:\\\\.|[^`\\\\])*`'});
    const keywords = keywordSets[lang];
    if (keywords) patterns.push({type:'keyword', source:`\\b(?:${keywords.split(' ').join('|')})\\b`});
    patterns.push({type:'number', source:'\\b(?:0x[\\da-fA-F]+|\\d+(?:\\.\\d+)?)\\b'});
    const matcher = new RegExp(patterns.map(item => `(${item.source})`).join('|'), 'gm');
    let cursor = 0;
    let output = '';
    for (const match of String(code).matchAll(matcher)) {
      output += escapeHtml(String(code).slice(cursor, match.index));
      const captureIndex = match.slice(1).findIndex(value => value !== undefined);
      output += `<span class="code-token token-${patterns[captureIndex].type}">${escapeHtml(match[0])}</span>`;
      cursor = match.index + match[0].length;
    }
    return output + escapeHtml(String(code).slice(cursor));
  }

  function splitMarkdownTableRow(line) {
    let source = String(line || '').trim();
    if (source.startsWith('|')) source = source.slice(1);
    if (source.endsWith('|') && !source.endsWith('\\|')) source = source.slice(0, -1);
    const cells = [];
    let cell = '';
    for (let index = 0; index < source.length; index++) {
      if (source[index] === '\\' && source[index + 1] === '|') { cell += '|'; index++; continue; }
      if (source[index] === '|') { cells.push(cell.trim()); cell = ''; continue; }
      cell += source[index];
    }
    cells.push(cell.trim());
    return cells;
  }

  function markdownTableAlignment(cell) {
    const marker = unescapeHtml(cell).trim();
    if (!/^:?-{3,}:?$/.test(marker)) return '';
    if (marker.startsWith(':') && marker.endsWith(':')) return 'center';
    if (marker.endsWith(':')) return 'right';
    return 'left';
  }

  function inlineMarkdownToHtml(text, options = {}) {
    const renderReference = options.renderReference || (token => `[[${escapeHtml(token)}]]`);
    const renderImage = options.renderImage || ((alt, source) => `![${escapeHtml(alt)}](${escapeHtml(source)})`);
    let output = String(text);
    output = output.replace(/&lt;br\s*\/?&gt;/gi, '<br>');
    output = output.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, source) => renderImage(unescapeHtml(alt), unescapeHtml(source)));
    output = output.replace(/\[\[([A-Za-z]+-\d+)(?:#(body|attachment)(?::([^\]]+))?)?\]\]/g, (_, id, kind = '', payload = '') => renderReference(`${id.toUpperCase()}${kind ? `#${kind}${payload ? `:${payload}` : ''}` : ''}`));
    output = output.replace(/\[([^\]]+)\]\(((?:https?:\/\/|mailto:)[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
    output = output.replace(/`([^`]+)`/g, '<code>$1</code>');
    output = output.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    output = output.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');
    output = output.replace(/~~([^~]+)~~/g, '<s>$1</s>');
    output = output.replace(/&lt;u&gt;([\s\S]*?)&lt;\/u&gt;/g, '<u>$1</u>');
    for (let pass = 0; pass < 6; pass++) {
      const next = output.replace(/&lt;span style=&quot;((?:color|background-color):#[0-9a-fA-F]{6}(?:;(?:color|background-color):#[0-9a-fA-F]{6})?)&quot;&gt;((?:(?!&lt;span style=)[\s\S])*?)&lt;\/span&gt;/g, '<span style="$1">$2</span>');
      if (next === output) break;
      output = next;
    }
    return output;
  }

  function markdownTableHtml(lines, startIndex, options = {}) {
    if (startIndex + 1 >= lines.length || !lines[startIndex].includes('|')) return null;
    const headers = splitMarkdownTableRow(lines[startIndex]);
    const separators = splitMarkdownTableRow(lines[startIndex + 1]);
    if (headers.length < 2 || separators.length !== headers.length) return null;
    const alignments = separators.map(markdownTableAlignment);
    if (alignments.some(value => !value)) return null;
    const rows = [];
    let index = startIndex + 2;
    while (index < lines.length && lines[index].trim() && lines[index].includes('|')) {
      const cells = splitMarkdownTableRow(lines[index]);
      if (cells.length !== headers.length) break;
      rows.push(cells);
      index++;
    }
    const cellHtml = (tag, value, column) => `<${tag} style="text-align:${alignments[column]}">${value ? inlineMarkdownToHtml(value, options) : '<br>'}</${tag}>`;
    const head = `<thead><tr>${headers.map((cell, column) => cellHtml('th', cell, column)).join('')}</tr></thead>`;
    const body = `<tbody>${rows.map(row => `<tr>${row.map((cell, column) => cellHtml('td', cell, column)).join('')}</tr>`).join('')}</tbody>`;
    return {html:`<div class="editor-table-wrap"><table>${head}${body}</table></div>`, endIndex:index - 1};
  }

  function markdownToHtml(markdown = '', options = {}) {
    const interactive = Boolean(options.interactive);
    const lines = escapeHtml(markdown).split('\n');
    const output = [];
    let listType = '';
    const closeList = () => { if (listType) output.push(`</${listType}>`); listType = ''; };
    for (let index = 0; index < lines.length; index++) {
      const line = lines[index];
      const table = markdownTableHtml(lines, index, options);
      if (table) { closeList(); output.push(table.html); index = table.endIndex; continue; }
      const fence = line.match(/^([ \t]*)(`{3,}|~{3,})(.*)$/);
      if (fence && !(fence[2][0] === '`' && fence[3].includes('`'))) {
        closeList();
        const indentation = fence[1].length;
        const marker = fence[2][0];
        const minimumFenceLength = fence[2].length;
        const language = normalizeCodeLanguage(unescapeHtml(fence[3].trim()));
        const codeLines = [];
        index++;
        while (index < lines.length) {
          const closingFence = lines[index].match(/^([ \t]*)(`{3,}|~{3,})\s*$/);
          if (closingFence && closingFence[2][0] === marker && closingFence[2].length >= minimumFenceLength) break;
          codeLines.push(lines[index].replace(new RegExp(`^[ \\t]{0,${indentation}}`), ''));
          index++;
        }
        const rawCode = unescapeHtml(codeLines.join('\n'));
        output.push(`<pre><code data-language="${language}">${rawCode ? syntaxHighlightCode(rawCode, language) : '<br>'}</code></pre>`);
        continue;
      }
      const task = line.match(/^- \[([ xX])\](?: (.*))?$/);
      const unordered = line.match(/^- (.*)$/);
      const ordered = line.match(/^\d+\. (.*)$/);
      if (task || unordered || ordered) {
        const nextType = ordered ? 'ol' : 'ul';
        if (listType !== nextType) { closeList(); output.push(`<${nextType}>`); listType = nextType; }
        if (task) output.push(`<li class="task-item"><input type="checkbox" ${interactive ? '' : 'disabled'} ${task[1].toLowerCase() === 'x' ? 'checked' : ''}>${task[2] ? inlineMarkdownToHtml(task[2], options) : '<br>'}</li>`);
        else output.push(`<li>${inlineMarkdownToHtml((ordered || unordered)[1], options)}</li>`);
        continue;
      }
      closeList();
      if (line.startsWith('###### ')) output.push(`<h6>${inlineMarkdownToHtml(line.slice(7), options)}</h6>`);
      else if (line.startsWith('##### ')) output.push(`<h5>${inlineMarkdownToHtml(line.slice(6), options)}</h5>`);
      else if (line.startsWith('#### ')) output.push(`<h4>${inlineMarkdownToHtml(line.slice(5), options)}</h4>`);
      else if (line.startsWith('### ')) output.push(`<h3>${inlineMarkdownToHtml(line.slice(4), options)}</h3>`);
      else if (line.startsWith('## ')) output.push(`<h2>${inlineMarkdownToHtml(line.slice(3), options)}</h2>`);
      else if (line.startsWith('# ')) output.push(`<h1>${inlineMarkdownToHtml(line.slice(2), options)}</h1>`);
      else if (/^&gt;($|\s)/.test(line)) {
        const quoteLines = [];
        while (index < lines.length && /^&gt;($|\s)/.test(lines[index])) { quoteLines.push(lines[index].replace(/^&gt; ?/, '')); index++; }
        index--;
        output.push(`<blockquote>${quoteLines.map(value => `<p>${value ? inlineMarkdownToHtml(value, options) : '<br>'}</p>`).join('')}</blockquote>`);
      } else if (/^&lt;div align=&quot;(left|center|right)&quot;&gt;([\s\S]*)&lt;\/div&gt;$/.test(line)) {
        const match = line.match(/^&lt;div align=&quot;(left|center|right)&quot;&gt;([\s\S]*)&lt;\/div&gt;$/);
        output.push(`<div style="text-align:${match[1]}">${inlineMarkdownToHtml(match[2], options)}</div>`);
      } else if (line.trim()) output.push(`<p>${inlineMarkdownToHtml(line, options)}</p>`);
    }
    closeList();
    if (interactive && output.at(-1)?.includes('internal-link')) output.push('<p class="after-reference-paragraph"><br></p>');
    return output.join('');
  }

  function markdownToPlainText(markdown = '', maxLength = 110, title = '', resolveTarget = () => null) {
    let text = String(markdown)
      .replace(/```([^\n]*)\n[\s\S]*?```/g, (_, language) => language.trim() ? ` [${normalizeCodeLanguage(language)} 代码块] ` : ' [代码块] ')
      .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/\[\[([A-Za-z]+-\d+(?:#(?:body|attachment)(?::[^\]]+)?)?)\]\]/g, (_, token) => {
        const detail = referenceTokenDetails(token, resolveTarget);
        return detail.kind === 'attachment' ? detail.attachmentName || '附件' : detail.title || detail.id;
      })
      .replace(/^\s{0,3}#{1,6}\s+/gm, '')
      .replace(/^\s*>\s?/gm, '')
      .replace(/^\s*[-*+]\s+\[[ xX]\]\s*/gm, '')
      .replace(/^\s*(?:[-*+]|\d+\.)\s+/gm, '')
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/__([^_]+)__/g, '$1')
      .replace(/(^|[^*])\*([^*]+)\*/g, '$1$2')
      .replace(/(^|[^_])_([^_]+)_/g, '$1$2')
      .replace(/~~([^~]+)~~/g, '$1')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    if (title && text.toLowerCase().startsWith(title.trim().toLowerCase())) text = text.slice(title.trim().length).trim().replace(/^[：:、·—-]+\s*/, '');
    const characters = [...text];
    return characters.length > maxLength ? `${characters.slice(0, maxLength).join('').trim()}…` : text;
  }

  const api = {
    cssColorToHex,
    escapeHtml,
    inlineMarkdownToHtml,
    markdownTableAlignment,
    markdownTableHtml,
    markdownToHtml,
    markdownToPlainText,
    normalizeCodeLanguage,
    parseReferenceToken,
    referenceTokenDetails,
    referenceTokenToHtml,
    safeColor,
    splitMarkdownTableRow,
    syntaxHighlightCode,
    unescapeHtml,
  };
  global.Workbench = global.Workbench || {};
  global.Workbench.markdown = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
