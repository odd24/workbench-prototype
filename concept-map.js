/* Local concept-map workspace. Data is persisted by app.js through the local API. */
let conceptMapSpacePressed = false;
let conceptMapLinkGesture = null;
let conceptMapLinkGestureBlockedUntil = 0;
let conceptMapRevision = 0;
let conceptMapSavedRevision = 0;
let conceptMapSavePromise = null;
let conceptMapMultiSelection = new Set();
let conceptMapHistory = [];
let conceptMapHistoryIndex = -1;
let conceptMapClipboard = null;
let conceptMapCategories = [];
let conceptMapCategoryFilter = '';
const conceptMapCollapsedCategories = new Set((() => {
  try { const value = JSON.parse(localStorage.getItem('workbench-concept-map-collapsed-categories') || '[]'); return Array.isArray(value) ? value : []; }
  catch { return []; }
})());
let conceptMapSortMode = 'updated';
const CONCEPT_MAP_WIDTH = 12000;
const CONCEPT_MAP_HEIGHT = 8000;
const CONCEPT_MAP_HISTORY_LIMIT = 100;

function persistConceptMapCollapsedCategories() {
  try { localStorage.setItem('workbench-concept-map-collapsed-categories', JSON.stringify([...conceptMapCollapsedCategories])); }
  catch { /* 存储受限时仍保留当前页面状态 */ }
}

function conceptMapCategoriesUncategorizedLast(categories) {
  const unique = [...new Set(categories)];
  return [...unique.filter(name => name !== '未分类'), ...unique.filter(name => name === '未分类')];
}

function conceptMapCardHtml(item) {
  const category = item.category || '未分类';
  return `<article class="concept-map-card" data-concept-map-card="${escapeHtml(item.id)}"><button type="button" class="concept-map-card-open" data-open-concept-map="${escapeHtml(item.id)}"><div class="concept-map-card-copy"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.focus_question || '尚未填写焦点问题')}</p><footer><span>${item.node_count || 0} 个概念 · ${item.relation_count ?? item.edge_count ?? 0} 个连词</span><time>${new Date(item.updated).toLocaleDateString('zh-CN')}</time></footer><small>${escapeHtml(category)}</small></div></button><button type="button" class="concept-map-card-more" data-concept-map-card-more="${escapeHtml(item.id)}" title="更多操作" aria-label="${escapeHtml(item.title)}的更多操作">•••</button></article>`;
}

function sortConceptMapItems(items) {
  const sorted = [...items];
  if (conceptMapSortMode === 'title') sorted.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'));
  else if (conceptMapSortMode === 'created') sorted.sort((a, b) => String(b.created).localeCompare(String(a.created)));
  else if (conceptMapSortMode === 'nodes') sorted.sort((a, b) => (b.node_count || 0) - (a.node_count || 0) || String(b.updated).localeCompare(String(a.updated)));
  else sorted.sort((a, b) => String(b.updated).localeCompare(String(a.updated)));
  return sorted;
}

async function renderConceptMapLibrary() {
  conceptMapHistory = [];
  conceptMapHistoryIndex = -1;
  currentConceptMap = null;
  conceptMapSelection = null;
  conceptMapMultiSelection.clear();
  $('#conceptMapWorkspace').hidden = true;
  $('#conceptMapLibrary').hidden = false;
  [conceptMaps, conceptMapCategories] = await Promise.all([api('/concept-maps'), api('/concept-map-categories')]);
  conceptMapCategories = conceptMapCategoriesUncategorizedLast([...conceptMapCategories, ...conceptMaps.map(item => item.category || '未分类')]);
  const query = conceptMapSearch.trim().toLocaleLowerCase('zh-CN');
  const visible = sortConceptMapItems(conceptMaps.filter(item => (!conceptMapCategoryFilter || (item.category || '未分类') === conceptMapCategoryFilter) && (!query || `${item.title} ${item.focus_question || ''} ${item.category || '未分类'}`.toLocaleLowerCase('zh-CN').includes(query))));
  const shownCategories = conceptMapCategories.filter(category => !conceptMapCategoryFilter || category === conceptMapCategoryFilter);
  const categoryDrag = !query && !conceptMapCategoryFilter;
  const groups = shownCategories.map(category => {
    const items = visible.filter(item => (item.category || '未分类') === category);
    if (query && !items.length) return '';
    const actions = category === '未分类' ? '' : `<span class="category-entry-actions concept-map-category-actions"><button type="button" data-rename-concept-map-category="${escapeHtml(category)}">重命名</button><button type="button" class="danger" data-delete-concept-map-category="${escapeHtml(category)}">删除</button></span>`;
    const draggable = categoryDrag && category !== '未分类';
    return `<details class="category-entry concept-map-category-group" data-concept-map-category="${escapeHtml(category)}" ${conceptMapCollapsedCategories.has(category) ? '' : 'open'}><summary class="category-entry-summary"><span class="concept-map-category-drag" draggable="${draggable}" title="${draggable ? '拖动调整分类顺序' : category === '未分类' ? '未分类固定在最后' : '清除筛选后可拖动'}">⠿</span><span class="category-entry-chevron">›</span><span class="category-entry-icon concept-map-category-icon">▤</span><strong>${escapeHtml(category)}</strong><em>${items.length} 张</em>${actions}</summary><div class="concept-map-grid">${items.map(conceptMapCardHtml).join('') || '<div class="concept-map-category-empty">此分类还没有概念图</div>'}</div></details>`;
  }).join('');
  const categoryOptions = conceptMapCategories.map(name => `<option value="${escapeHtml(name)}" ${name === conceptMapCategoryFilter ? 'selected' : ''}>${escapeHtml(name)}</option>`).join('');
  $('#conceptMapLibrary').innerHTML = `<header class="concept-map-library-header"><div><p class="eyebrow">思维可视化</p><h1>概念图</h1><p>按分类整理概念图，并通过筛选和排序快速定位。</p></div><div class="concept-map-library-actions"><button type="button" class="secondary-button" id="newConceptMapCategory">＋ 新建分类</button><button type="button" class="primary-button" id="newConceptMap">＋ 新建概念图</button></div></header><div class="concept-map-filter-panel"><label class="concept-map-search"><span>⌕</span><input id="conceptMapSearch" value="${escapeHtml(conceptMapSearch)}" placeholder="搜索标题、焦点问题或分类"></label><label><span>分类</span><select id="conceptMapCategoryFilter"><option value="">全部分类</option>${categoryOptions}</select></label><label><span>排序</span><select id="conceptMapSortMode"><option value="updated" ${conceptMapSortMode === 'updated' ? 'selected' : ''}>最近更新</option><option value="created" ${conceptMapSortMode === 'created' ? 'selected' : ''}>最近创建</option><option value="title" ${conceptMapSortMode === 'title' ? 'selected' : ''}>标题名称</option><option value="nodes" ${conceptMapSortMode === 'nodes' ? 'selected' : ''}>概念数量</option></select></label>${query || conceptMapCategoryFilter ? '<button type="button" class="knowledge-filter-clear" id="clearConceptMapFilters">清除筛选</button>' : ''}</div><div class="concept-map-result-count">显示 ${visible.length} / ${conceptMaps.length} 张概念图 · ${shownCategories.length} 个分类</div><div class="concept-map-category-list">${groups || `<div class="concept-map-empty"><div><span>◇</span><h2>${conceptMaps.length ? '没有符合条件的概念图' : '从一个焦点问题开始'}</h2><p>${conceptMaps.length ? '调整搜索、分类或排序条件后再试。' : '先创建分类或直接新建一张概念图。'}</p>${conceptMaps.length ? '' : '<button type="button" class="primary-button" id="newConceptMapEmpty">创建第一张图</button>'}</div></div>`}</div>`;
  $('#conceptMapSearch')?.addEventListener('input', event => {
    conceptMapSearch = event.target.value;
    clearTimeout(renderConceptMapLibrary.searchTimer);
    renderConceptMapLibrary.searchTimer = setTimeout(async () => {
      await renderConceptMapLibrary();
      const input = $('#conceptMapSearch'); input?.focus(); input?.setSelectionRange(input.value.length, input.value.length);
    }, 180);
  });
  $('#conceptMapCategoryFilter')?.addEventListener('change', event => { conceptMapCategoryFilter = event.target.value; renderConceptMapLibrary(); });
  $('#conceptMapSortMode')?.addEventListener('change', event => { conceptMapSortMode = event.target.value; renderConceptMapLibrary(); });
  $$('.concept-map-category-group').forEach(group => group.addEventListener('toggle', () => {
    if (group.open) conceptMapCollapsedCategories.delete(group.dataset.conceptMapCategory);
    else conceptMapCollapsedCategories.add(group.dataset.conceptMapCategory);
    persistConceptMapCollapsedCategories();
  }));
  bindConceptMapCategoryDrag(categoryDrag);
}

function bindConceptMapCategoryDrag(enabled) {
  if (!enabled) return;
  const list = $('.concept-map-category-list'); if (!list) return;
  let dragged = null;
  $$('.concept-map-category-group', list).forEach(group => {
    const handle = $('.concept-map-category-drag', group);
    handle?.addEventListener('dragstart', event => {
      if (group.dataset.conceptMapCategory === '未分类') { event.preventDefault(); return; }
      dragged = group; group.classList.add('dragging'); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', group.dataset.conceptMapCategory);
    });
    handle?.addEventListener('dragend', () => { group.classList.remove('dragging'); dragged = null; });
    group.addEventListener('dragover', event => {
      if (!dragged || dragged === group) return;
      event.preventDefault();
      if (group.dataset.conceptMapCategory === '未分类') { list.insertBefore(dragged, group); return; }
      const rect = group.getBoundingClientRect(); list.insertBefore(dragged, event.clientY < rect.top + rect.height / 2 ? group : group.nextSibling);
    });
    group.addEventListener('drop', async event => {
      if (!dragged) return;
      event.preventDefault();
      const order = conceptMapCategoriesUncategorizedLast($$('.concept-map-category-group', list).map(item => item.dataset.conceptMapCategory));
      try { conceptMapCategories = await api('/concept-map-categories', {method:'PUT', body:JSON.stringify({categories:order})}); notify('分类顺序已保存', '刷新页面后仍会保持当前顺序'); }
      catch (error) { notify('分类顺序保存失败', error.message, true); await renderConceptMapLibrary(); }
    });
  });
}

async function createConceptMap() {
  const title = await appPrompt({title:'新建概念图', message:'先写下这次思考的主题。', confirmText:'创建并开始', input:{label:'概念图标题', placeholder:'例如：新产品增长路径'}});
  if (!title?.trim()) return;
  const created = await api('/concept-maps', {method:'POST', body:JSON.stringify({title:title.trim(), focus_question:'', category:conceptMapCategoryFilter || '未分类'})});
  await openConceptMap(created.id, {centerInitial:true});
}

async function createConceptMapCategory() {
  const value = await appPrompt({title:'新建概念图分类', message:'分类可以先保持为空，之后再为概念图选择分类。', confirmText:'创建分类', input:{label:'分类名称', placeholder:'例如：产品规划'}});
  const category = value?.trim(); if (!category) return;
  if (conceptMapCategories.includes(category)) { notify('分类已存在', `「${category}」已经存在`, true); return; }
  try {
    conceptMapCategories = await api('/concept-map-categories', {method:'PUT', body:JSON.stringify({categories:conceptMapCategoriesUncategorizedLast([...conceptMapCategories, category])})});
    await renderConceptMapLibrary(); notify('分类已创建', `「${category}」现在可以接收概念图；当前筛选保持不变`);
  } catch (error) { notify('创建分类失败', error.message, true); }
}

async function renameConceptMapCategory(oldName) {
  const value = await appPrompt({title:'重命名概念图分类', message:'分类中的概念图会一起迁移。', confirmText:'保存名称', input:{label:'新分类名称', value:oldName}});
  const newName = value?.trim(); if (!newName || newName === oldName) return;
  try {
    const result = await api('/concept-map-categories/rename', {method:'PATCH', body:JSON.stringify({old_name:oldName, new_name:newName})});
    conceptMapCategories = result.categories;
    if (conceptMapCollapsedCategories.delete(oldName)) { conceptMapCollapsedCategories.add(newName); persistConceptMapCollapsedCategories(); }
    if (conceptMapCategoryFilter === oldName) conceptMapCategoryFilter = newName;
    await renderConceptMapLibrary(); notify('分类已重命名', `${oldName} → ${newName} · 已同步 ${result.updated_maps} 张概念图`);
  } catch (error) { notify('重命名失败', error.message, true); }
}

async function deleteConceptMapCategory(name) {
  const count = conceptMaps.filter(item => (item.category || '未分类') === name).length;
  const approved = await appConfirm({title:`删除分类「${name}」？`, message:count ? `其中 ${count} 张概念图将移动到“未分类”。` : '这是一个空分类。', detail:'只删除分类，不会删除任何概念图。', confirmText:'删除分类', danger:true});
  if (!approved) return;
  try {
    const result = await api(`/concept-map-categories/${encodeURIComponent(name)}`, {method:'DELETE'});
    conceptMapCategories = result.categories;
    conceptMapCollapsedCategories.delete(name); persistConceptMapCollapsedCategories();
    if (conceptMapCategoryFilter === name) conceptMapCategoryFilter = '';
    await renderConceptMapLibrary(); notify('分类已删除', result.updated_maps ? `${result.updated_maps} 张概念图已移动到“未分类”` : '概念图内容未受影响');
  } catch (error) { notify('删除分类失败', error.message, true); }
}

async function openConceptMap(mapId, {centerInitial = false} = {}) {
  currentConceptMap = await api(`/concept-maps/${encodeURIComponent(mapId)}`);
  currentConceptMap.nodes = currentConceptMap.nodes.map(node => {
    const legacySize = !node.border_color && node.width === 180 && node.height === 72;
    const type = node.type === 'linking_phrase' ? 'linking_phrase' : 'concept';
    const normalized = {...node, type, color:node.color || (type === 'linking_phrase' ? '#eef0f2' : '#f4f8fa'), border_color:node.border_color || (type === 'linking_phrase' ? '#eef0f2' : '#9eb4c7'), text_color:node.text_color || '#213044', font_size:node.font_size || (type === 'linking_phrase' ? 11 : 13), font_weight:node.font_weight || 400};
    if (legacySize) Object.assign(normalized, conceptNodeNaturalSize(normalized.text, normalized.font_size, type));
    return normalized;
  });
  const migrated = migrateConceptMapLinkingPhrases();
  conceptMapSelection = null;
  conceptMapMultiSelection.clear();
  conceptMapConnectSource = '';
  conceptMapRevision = 0;
  conceptMapSavedRevision = 0;
  conceptMapSavePromise = null;
  $('#conceptMapLibrary').hidden = true;
  $('#conceptMapWorkspace').hidden = false;
  $('#conceptMapTitle').value = currentConceptMap.title;
  $('#conceptMapFocus').value = currentConceptMap.focus_question || '';
  if (centerInitial && currentConceptMap.nodes[0]) {
    const shell = $('#conceptMapCanvasShell'), node = currentConceptMap.nodes[0];
    currentConceptMap.viewport = {zoom:1, x:shell.clientWidth / 2 - node.x - node.width / 2, y:shell.clientHeight / 2 - node.y - node.height / 2};
  }
  resetConceptMapHistory();
  renderConceptMap();
  if (migrated || centerInitial) scheduleConceptMapSave();
  requestAnimationFrame(() => currentConceptMap.nodes.length === 1 && !currentConceptMap.viewport.x && !currentConceptMap.viewport.y ? fitConceptMap() : applyConceptMapViewport());
}

function conceptNode(nodeId) { return currentConceptMap?.nodes.find(item => item.id === nodeId); }
function conceptEdge(edgeId) { return currentConceptMap?.edges.find(item => item.id === edgeId); }
function nextConceptElementId(prefix, items) {
  let id;
  do { id = `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`; } while (items.some(item => item.id === id));
  return id;
}

function conceptNodeNaturalSize(text, fontSize = 13, type = 'concept') {
  const lines = String(text || '???').split('\n'), longest = Math.max(...lines.map(line => [...line].reduce((width, char) => width + (/[^\x00-\xff]/.test(char) ? 1 : .58), 0)));
  if (type === 'linking_phrase') return {width:Math.max(34, Math.min(240, Math.ceil(longest * fontSize + 14))), height:Math.max(22, Math.min(120, Math.ceil(lines.length * fontSize * 1.35 + 7)))};
  return {width:Math.max(72, Math.min(280, Math.ceil(longest * fontSize + 22))), height:Math.max(30, Math.min(180, Math.ceil(lines.length * fontSize * 1.4 + 12)))};
}

function conceptMapPathBetween(from, to) {
  if (!from || !to) return null;
  const fromCenter = {x:from.x + from.width / 2, y:from.y + from.height / 2};
  const toCenter = {x:to.x + to.width / 2, y:to.y + to.height / 2};
  const boundaryPoint = (node, center, toward) => {
    const dx = toward.x - center.x, dy = toward.y - center.y;
    if (!dx && !dy) return {...center};
    const scale = 1 / Math.max(Math.abs(dx) / Math.max(1, node.width / 2), Math.abs(dy) / Math.max(1, node.height / 2));
    return {x:center.x + dx * scale, y:center.y + dy * scale};
  };
  const start = boundaryPoint(from, fromCenter, toCenter), end = boundaryPoint(to, toCenter, fromCenter);
  const mid = {x:(start.x + end.x) / 2, y:(start.y + end.y) / 2};
  return {d:`M ${start.x} ${start.y} L ${end.x} ${end.y}`, start, c1:start, c2:start, end, mid};
}

function conceptMapPath(edge) { return conceptMapPathBetween(conceptNode(edge.from), conceptNode(edge.to)); }

function recenterLinkingPhrase(phrase) {
  if (!phrase || phrase.type !== 'linking_phrase') return false;
  const adjacentIds = new Set();
  currentConceptMap.edges.forEach(edge => {
    if (edge.from === phrase.id && conceptNode(edge.to)?.type === 'concept') adjacentIds.add(edge.to);
    if (edge.to === phrase.id && conceptNode(edge.from)?.type === 'concept') adjacentIds.add(edge.from);
  });
  const concepts = [...adjacentIds].map(conceptNode).filter(Boolean);
  if (concepts.length < 2) return false;
  let center;
  if (concepts.length === 2) center = conceptMapPathBetween(concepts[0], concepts[1]).mid;
  else center = {x:concepts.reduce((sum, node) => sum + node.x + node.width / 2, 0) / concepts.length, y:concepts.reduce((sum, node) => sum + node.y + node.height / 2, 0) / concepts.length};
  const nextX = Math.max(0, Math.min(CONCEPT_MAP_WIDTH - phrase.width, center.x - phrase.width / 2));
  const nextY = Math.max(0, Math.min(CONCEPT_MAP_HEIGHT - phrase.height, center.y - phrase.height / 2));
  if (Math.abs(phrase.x - nextX) < .01 && Math.abs(phrase.y - nextY) < .01) return false;
  phrase.x = nextX; phrase.y = nextY;
  return true;
}

function recenterLinkingPhrasesForConcept(conceptId, excludedIds = new Set()) {
  const phraseIds = new Set();
  currentConceptMap.edges.forEach(edge => {
    if (edge.from === conceptId && conceptNode(edge.to)?.type === 'linking_phrase') phraseIds.add(edge.to);
    if (edge.to === conceptId && conceptNode(edge.from)?.type === 'linking_phrase') phraseIds.add(edge.from);
  });
  return [...phraseIds].filter(id => !excludedIds.has(id)).map(conceptNode).filter(phrase => recenterLinkingPhrase(phrase));
}

function recenterAllLinkingPhrases() {
  return currentConceptMap.nodes.filter(node => node.type === 'linking_phrase' && recenterLinkingPhrase(node));
}

function conceptEdgeHasArrow(edge) {
  const from = conceptNode(edge.from), to = conceptNode(edge.to);
  return (from?.type === 'linking_phrase' && to?.type === 'concept') || edge.arrowhead !== 'none';
}

function migrateConceptMapLinkingPhrases() {
  if (!currentConceptMap || (currentConceptMap.version >= 2 && !currentConceptMap.edges.some(edge => edge.label))) return false;
  const migratedEdges = [], linkingPhrases = [];
  currentConceptMap.edges.forEach(edge => {
    const from = conceptNode(edge.from), to = conceptNode(edge.to);
    if (!from || !to) return;
    if (!edge.label || from.type === 'linking_phrase' || to.type === 'linking_phrase') {
      migratedEdges.push({...edge, label:'', arrowhead:edge.arrowhead || (to.type === 'linking_phrase' ? 'none' : 'to')});
      return;
    }
    const path = conceptMapPathBetween(from, to), size = conceptNodeNaturalSize(edge.label, 11, 'linking_phrase');
    let phraseId = `link-${edge.id}`;
    while (currentConceptMap.nodes.some(node => node.id === phraseId) || linkingPhrases.some(node => node.id === phraseId)) phraseId += 'x';
    linkingPhrases.push({id:phraseId, type:'linking_phrase', text:edge.label, note:'', x:path.mid.x - size.width / 2, y:path.mid.y - size.height / 2, ...size, color:'#eef0f2', border_color:'#eef0f2', text_color:'#44505e', font_size:11, font_weight:400, shape:'rectangle'});
    migratedEdges.push({id:`${edge.id}-in`, from:edge.from, to:phraseId, label:'', color:edge.color || '#687b8e', dashed:!!edge.dashed, arrowhead:'none'});
    migratedEdges.push({...edge, from:phraseId, label:'', arrowhead:'to'});
  });
  currentConceptMap.nodes.push(...linkingPhrases);
  currentConceptMap.edges = migratedEdges;
  currentConceptMap.version = 2;
  return true;
}

function renderConceptMapEdges() {
  if (!currentConceptMap) return;
  $('#conceptMapEdges').innerHTML = currentConceptMap.edges.map(edge => {
    const path = conceptMapPath(edge); if (!path) return '';
    const markerId = `concept-arrow-${edge.id}`;
    const marker = conceptEdgeHasArrow(edge) ? ` marker-end="url(#${escapeHtml(markerId)})"` : '';
    return `<g class="concept-map-edge-group ${conceptMapSelection?.type === 'edge' && conceptMapSelection.id === edge.id ? 'selected' : ''}" data-concept-edge="${escapeHtml(edge.id)}"><defs><marker id="${escapeHtml(markerId)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="${escapeHtml(edge.color)}"/></marker></defs><path class="concept-map-edge-hit" d="${path.d}"/><path class="concept-map-edge-line" d="${path.d}" stroke="${escapeHtml(edge.color)}" stroke-dasharray="${edge.dashed ? '6 5' : 'none'}"${marker}/></g>`;
  }).join('');
}

function renderConceptMapLabels() {
  if (!currentConceptMap) return;
  $('#conceptMapLabels').innerHTML = '';
}

function renderConceptMapNodes() {
  if (!currentConceptMap) return;
  $('#conceptMapNodes').innerHTML = currentConceptMap.nodes.map(node => {
    const primary = conceptMapSelection?.type === 'node' && conceptMapSelection.id === node.id, multi = conceptMapMultiSelection.has(node.id);
    return `<article class="concept-node ${node.type === 'linking_phrase' ? 'linking-phrase' : 'concept'} ${escapeHtml(node.shape)} ${primary ? 'selected' : ''} ${multi ? 'multi-selected' : ''}" data-concept-node="${escapeHtml(node.id)}" data-concept-node-type="${escapeHtml(node.type || 'concept')}" style="left:${node.x}px;top:${node.y}px;width:${node.width}px;height:${node.height}px;background:${escapeHtml(node.color || '#f4f8fa')};--concept-border:${escapeHtml(node.border_color || '#9eb4c7')}"><strong style="color:${escapeHtml(node.text_color || '#213044')};font-size:${node.font_size || 13}px;font-weight:${node.font_weight || 400}">${escapeHtml(node.text)}</strong><button type="button" class="concept-port top" data-concept-port="top" aria-label="向上扩展">↑</button><button type="button" class="concept-port right" data-concept-port="right" aria-label="向右扩展">→</button><button type="button" class="concept-port bottom" data-concept-port="bottom" aria-label="向下扩展">↓</button><button type="button" class="concept-port left" data-concept-port="left" aria-label="向左扩展">←</button></article>`;
  }).join('');
  $$('[data-concept-node]', $('#conceptMapNodes')).forEach(bindConceptNode);
  $$('[data-concept-port]', $('#conceptMapNodes')).forEach(bindConceptPort);
}

function renderConceptMap() {
  renderConceptMapNodes(); renderConceptMapEdges(); renderConceptMapLabels(); renderConceptMapMiniMap(); applyConceptMapViewport();
}

function updateConceptMapSelectionUi() {
  $$('[data-concept-node]', $('#conceptMapNodes')).forEach(element => {
    element.classList.toggle('selected', conceptMapSelection?.type === 'node' && conceptMapSelection.id === element.dataset.conceptNode);
    element.classList.toggle('multi-selected', conceptMapMultiSelection.has(element.dataset.conceptNode));
  });
  renderConceptMapEdges();
}

function applyConceptMapViewport() {
  if (!currentConceptMap) return;
  const viewport = currentConceptMap.viewport || (currentConceptMap.viewport = {x:0, y:0, zoom:1});
  const stage = $('#conceptMapStage'), pixelRatio = window.devicePixelRatio || 1;
  const snappedX = Math.round(viewport.x * pixelRatio) / pixelRatio, snappedY = Math.round(viewport.y * pixelRatio) / pixelRatio;
  stage.style.left = `${snappedX / viewport.zoom}px`;
  stage.style.top = `${snappedY / viewport.zoom}px`;
  stage.style.zoom = viewport.zoom;
  stage.style.transform = 'none';
  stage.style.setProperty('--concept-map-inverse-zoom', 1 / viewport.zoom);
  stage.style.setProperty('--concept-map-hairline', `${1 / viewport.zoom}px`);
  stage.style.setProperty('--concept-map-focus-ring', `${3 / viewport.zoom}px`);
  $('#conceptMapZoomValue').textContent = `${Math.round(viewport.zoom * 100)}%`;
  renderConceptMapMiniMap();
}

function conceptMapPoint(clientX, clientY) {
  const rect = $('#conceptMapCanvasShell').getBoundingClientRect(), viewport = currentConceptMap.viewport;
  return {x:(clientX - rect.left - viewport.x) / viewport.zoom, y:(clientY - rect.top - viewport.y) / viewport.zoom};
}

function addConceptNodeAt(x, y, text = '???', edit = true, persist = true) {
  if (!currentConceptMap) return;
  const size = conceptNodeNaturalSize(text);
  const node = {id:nextConceptElementId('node', currentConceptMap.nodes), type:'concept', text, note:'', x:Math.max(0, Math.min(CONCEPT_MAP_WIDTH - size.width, x - size.width / 2)), y:Math.max(0, Math.min(CONCEPT_MAP_HEIGHT - size.height, y - size.height / 2)), ...size, color:'#f4f8fa', border_color:'#9eb4c7', text_color:'#213044', font_size:13, font_weight:400, shape:'rounded'};
  currentConceptMap.nodes.push(node); conceptMapMultiSelection.clear(); conceptMapSelection = {type:'node', id:node.id}; renderConceptMap();
  if (persist) scheduleConceptMapSave();
  if (edit) requestAnimationFrame(() => beginConceptNodeEdit(node.id));
  return node;
}

function bindConceptNode(element) {
  element.addEventListener('pointerdown', event => {
    if (conceptMapSpacePressed || event.button !== 0 || event.target.closest('.concept-port') || event.target.isContentEditable) return;
    event.stopPropagation();
    const node = conceptNode(element.dataset.conceptNode);
    const moveIds = conceptMapMultiSelection.has(node.id) && conceptMapMultiSelection.size > 1 ? new Set(conceptMapMultiSelection) : new Set([node.id]);
    if (moveIds.size === 1) conceptMapMultiSelection.clear();
    conceptMapSelection = {type:'node', id:node.id}; updateConceptMapSelectionUi();
    const movedNodes = [...moveIds].map(conceptNode).filter(Boolean), positions = new Map(movedNodes.map(item => [item.id, {x:item.x, y:item.y}]));
    const limits = {
      minX:Math.min(...movedNodes.map(item => item.x)), minY:Math.min(...movedNodes.map(item => item.y)),
      maxX:Math.max(...movedNodes.map(item => item.x + item.width)), maxY:Math.max(...movedNodes.map(item => item.y + item.height))
    };
    const start = {x:event.clientX, y:event.clientY};
    const gesture = {pointerId:event.pointerId, moved:false, finished:false};
    element.setPointerCapture(event.pointerId);
    const move = moveEvent => {
      if (moveEvent.pointerId !== gesture.pointerId || gesture.finished) return;
      const rawDx = (moveEvent.clientX - start.x) / currentConceptMap.viewport.zoom, rawDy = (moveEvent.clientY - start.y) / currentConceptMap.viewport.zoom;
      const dx = Math.max(-limits.minX, Math.min(CONCEPT_MAP_WIDTH - limits.maxX, rawDx));
      const dy = Math.max(-limits.minY, Math.min(CONCEPT_MAP_HEIGHT - limits.maxY, rawDy));
      if (Math.abs(dx) + Math.abs(dy) > 2 && !gesture.moved) { gesture.moved = true; scheduleConceptMapSave(); }
      movedNodes.forEach(item => { const original = positions.get(item.id); item.x = original.x + dx; item.y = original.y + dy; });
      const movedPhrases = new Map();
      movedNodes.filter(item => item.type === 'concept').forEach(item => recenterLinkingPhrasesForConcept(item.id, moveIds).forEach(phrase => movedPhrases.set(phrase.id, phrase)));
      [...movedNodes, ...movedPhrases.values()].forEach(item => { const itemElement = $(`[data-concept-node="${item.id}"]`); if (itemElement) { itemElement.style.left = `${item.x}px`; itemElement.style.top = `${item.y}px`; } });
      renderConceptMapEdges(); renderConceptMapLabels(); renderConceptMapMiniMap();
    };
    const finish = finishEvent => {
      if (finishEvent.pointerId !== gesture.pointerId || gesture.finished) return;
      gesture.finished = true;
      element.removeEventListener('pointermove', move); element.removeEventListener('pointerup', finish); element.removeEventListener('pointercancel', finish);
      if (gesture.moved) { renderConceptMapEdges(); renderConceptMapLabels(); scheduleConceptMapSave(); }
      else { conceptMapSelection = {type:'node', id:node.id}; updateConceptMapSelectionUi(); }
    };
    element.addEventListener('pointermove', move); element.addEventListener('pointerup', finish, {once:true}); element.addEventListener('pointercancel', finish, {once:true});
  });
  element.addEventListener('dblclick', event => { event.stopPropagation(); beginConceptNodeEdit(element.dataset.conceptNode); });
}

function beginConceptNodeEdit(nodeId) {
  const node = conceptNode(nodeId), element = $(`[data-concept-node="${nodeId}"]`), text = $('strong', element);
  if (!node || !element || text.isContentEditable) return;
  conceptMapMultiSelection.clear(); conceptMapSelection = {type:'node', id:nodeId}; updateConceptMapSelectionUi(); element.classList.add('editing'); text.contentEditable = 'true'; text.focus();
  const selection = window.getSelection(), range = document.createRange(); range.selectNodeContents(text); selection.removeAllRanges(); selection.addRange(range);
  const finish = () => {
    text.contentEditable = 'false'; element.classList.remove('editing'); node.text = text.textContent.trim() || '???';
    Object.assign(node, conceptNodeNaturalSize(node.text, node.font_size, node.type)); if (node.type === 'concept') recenterLinkingPhrasesForConcept(node.id); renderConceptMap(); scheduleConceptMapSave();
  };
  text.addEventListener('blur', finish, {once:true});
  text.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); text.blur(); } if (event.key === 'Escape') { event.preventDefault(); text.textContent = node.text; text.blur(); } });
}

function beginConceptEdgeEdit(edgeId) {
  const edge = conceptEdge(edgeId), label = $(`[data-concept-edge-label="${edgeId}"]`); if (!edge || !label || label.isContentEditable) return;
  conceptMapSelection = {type:'edge', id:edgeId}; updateConceptMapSelectionUi(); label.contentEditable = 'true'; label.focus();
  const selection = window.getSelection(), range = document.createRange(); range.selectNodeContents(label); selection.removeAllRanges(); selection.addRange(range);
  const finish = () => { label.contentEditable = 'false'; edge.label = label.textContent.trim(); renderConceptMapLabels(); scheduleConceptMapSave(); };
  label.addEventListener('blur', finish, {once:true}); label.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); label.blur(); } });
}

function addLinkingPhraseAt(x, y, text = '连接') {
  const size = conceptNodeNaturalSize(text, 11, 'linking_phrase');
  const node = {id:nextConceptElementId('link', currentConceptMap.nodes), type:'linking_phrase', text, note:'', x:Math.max(0, x - size.width / 2), y:Math.max(0, y - size.height / 2), ...size, color:'#eef0f2', border_color:'#eef0f2', text_color:'#44505e', font_size:11, font_weight:400, shape:'rectangle'};
  currentConceptMap.nodes.push(node);
  return node;
}

function createDirectConceptEdge(fromId, toId, arrowhead = 'to') {
  if (fromId === toId) return null;
  const edge = {id:nextConceptElementId('edge', currentConceptMap.edges), from:fromId, to:toId, label:'', color:'#687b8e', dashed:false, arrowhead};
  currentConceptMap.edges.push(edge);
  return edge;
}

function createConceptEdge(fromId, toId, label = '连接') {
  if (fromId === toId) return null;
  const from = conceptNode(fromId), to = conceptNode(toId);
  if (!from || !to) return null;
  if (!label || from.type === 'linking_phrase' || to.type === 'linking_phrase') {
    createDirectConceptEdge(fromId, toId, to.type === 'linking_phrase' ? 'none' : 'to');
    return null;
  }
  const path = conceptMapPathBetween(from, to), phrase = addLinkingPhraseAt(path.mid.x, path.mid.y, label);
  createDirectConceptEdge(fromId, phrase.id, 'none');
  createDirectConceptEdge(phrase.id, toId, 'to');
  conceptMapSelection = {type:'node', id:phrase.id};
  return phrase;
}

function branchPosition(node, direction, distance = 90) {
  const center = {x:node.x + node.width / 2, y:node.y + node.height / 2};
  if (direction === 'top') center.y -= distance; if (direction === 'bottom') center.y += distance;
  if (direction === 'left') center.x -= distance + node.width / 2; if (direction === 'right') center.x += distance + node.width / 2;
  return center;
}

function bindConceptPort(port) {
  port.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); });
  port.addEventListener('pointerdown', event => {
    if (event.button !== 0 || conceptMapLinkGesture || performance.now() < conceptMapLinkGestureBlockedUntil) return;
    event.preventDefault(); event.stopPropagation();
    const sourceElement = port.closest('[data-concept-node]'), source = conceptNode(sourceElement.dataset.conceptNode), start = {x:event.clientX, y:event.clientY};
    const gesture = {pointerId:event.pointerId, sourceId:source.id, moved:false, finished:false, direct:event.ctrlKey && event.shiftKey};
    conceptMapLinkGesture = gesture; port.setPointerCapture(event.pointerId);
    const sourceCenter = {x:source.x + source.width / 2, y:source.y + source.height / 2};
    const move = moveEvent => {
      if (moveEvent.pointerId !== gesture.pointerId || gesture.finished) return;
      if (Math.abs(moveEvent.clientX - start.x) + Math.abs(moveEvent.clientY - start.y) > 4) gesture.moved = true;
      const target = conceptDropTarget(moveEvent.clientX, moveEvent.clientY, source.id);
      $$('.concept-node.drop-target').forEach(element => element.classList.remove('drop-target'));
      if (target) target.classList.add('drop-target');
      const targetNode = target ? conceptNode(target.dataset.conceptNode) : null;
      const point = targetNode ? {x:targetNode.x + targetNode.width / 2, y:targetNode.y + targetNode.height / 2} : conceptMapPoint(moveEvent.clientX, moveEvent.clientY);
      $('#conceptMapDraftEdge')?.remove(); $('#conceptMapEdges').insertAdjacentHTML('beforeend', `<path id="conceptMapDraftEdge" class="concept-map-draft-line" vector-effect="non-scaling-stroke" d="M ${sourceCenter.x} ${sourceCenter.y} L ${point.x} ${point.y}"/>`);
    };
    const cleanup = () => {
      port.removeEventListener('pointermove', move); port.removeEventListener('pointerup', up); port.removeEventListener('pointercancel', cancel);
      $('#conceptMapDraftEdge')?.remove(); $$('.concept-node.drop-target').forEach(element => element.classList.remove('drop-target'));
      conceptMapLinkGesture = null; conceptMapLinkGestureBlockedUntil = performance.now() + 180;
    };
    const up = upEvent => {
      if (upEvent.pointerId !== gesture.pointerId || gesture.finished) return;
      gesture.finished = true;
      const targetElement = conceptDropTarget(upEvent.clientX, upEvent.clientY, source.id);
      cleanup();
      if (gesture.moved) {
        if (!targetElement) {
          const dropPoint = conceptMapPoint(upEvent.clientX, upEvent.clientY), target = addConceptNodeAt(dropPoint.x, dropPoint.y, '???', false, false);
          createConceptEdge(source.id, target.id, gesture.direct ? '' : '连接'); recenterLinkingPhrasesForConcept(source.id); renderConceptMap(); scheduleConceptMapSave(); requestAnimationFrame(() => beginConceptNodeEdit(target.id));
          return;
        }
        const phrase = createConceptEdge(source.id, targetElement.dataset.conceptNode, gesture.direct ? '' : '连接'); renderConceptMap(); scheduleConceptMapSave();
        if (phrase) requestAnimationFrame(() => beginConceptNodeEdit(phrase.id));
        return;
      }
      const point = branchPosition(source, port.dataset.conceptPort), target = addConceptNodeAt(point.x, point.y, '???', false, false);
      createConceptEdge(source.id, target.id, gesture.direct ? '' : '连接'); renderConceptMap(); scheduleConceptMapSave(); requestAnimationFrame(() => beginConceptNodeEdit(target.id));
    };
    const cancel = cancelEvent => { if (cancelEvent.pointerId !== gesture.pointerId || gesture.finished) return; gesture.finished = true; cleanup(); renderConceptMapEdges(); };
    port.addEventListener('pointermove', move); port.addEventListener('pointerup', up, {once:true}); port.addEventListener('pointercancel', cancel, {once:true});
  });
}

function conceptDropTarget(clientX, clientY, sourceId, tolerance = 14) {
  const candidates = $$('[data-concept-node]', $('#conceptMapNodes')).filter(element => element.dataset.conceptNode !== sourceId).map(element => ({element, rect:element.getBoundingClientRect()}));
  const exact = candidates.find(({rect}) => clientX >= rect.left && clientX <= rect.right && clientY >= rect.top && clientY <= rect.bottom);
  if (exact) return exact.element;
  const nearby = candidates.filter(({rect}) => clientX >= rect.left - tolerance && clientX <= rect.right + tolerance && clientY >= rect.top - tolerance && clientY <= rect.bottom + tolerance);
  nearby.sort((a, b) => Math.hypot(clientX - (a.rect.left + a.rect.right) / 2, clientY - (a.rect.top + a.rect.bottom) / 2) - Math.hypot(clientX - (b.rect.left + b.rect.right) / 2, clientY - (b.rect.top + b.rect.bottom) / 2));
  return nearby[0]?.element || null;
}

function renderConceptMapMiniMap() {
  const minimap = $('#conceptMapMiniMap'); if (!currentConceptMap?.nodes.length || !minimap) return;
  const minX = Math.min(...currentConceptMap.nodes.map(node => node.x)) - 80, minY = Math.min(...currentConceptMap.nodes.map(node => node.y)) - 80;
  const maxX = Math.max(...currentConceptMap.nodes.map(node => node.x + node.width)) + 80, maxY = Math.max(...currentConceptMap.nodes.map(node => node.y + node.height)) + 80;
  const width = maxX - minX, height = maxY - minY, scale = Math.min(140 / width, 82 / height), offsetX = (150 - width * scale) / 2, offsetY = (92 - height * scale) / 2;
  const viewport = currentConceptMap.viewport || {x:0,y:0,zoom:1}, shell = $('#conceptMapCanvasShell');
  const viewX = (-viewport.x / viewport.zoom - minX) * scale + offsetX, viewY = (-viewport.y / viewport.zoom - minY) * scale + offsetY;
  const viewWidth = shell.clientWidth / viewport.zoom * scale, viewHeight = shell.clientHeight / viewport.zoom * scale;
  minimap.innerHTML = currentConceptMap.nodes.map(node => `<i class="concept-map-minimap-node" style="left:${(node.x - minX) * scale + offsetX}px;top:${(node.y - minY) * scale + offsetY}px;width:${Math.max(3,node.width * scale)}px;height:${Math.max(2,node.height * scale)}px"></i>`).join('') + `<b class="concept-map-minimap-viewport" style="left:${viewX}px;top:${viewY}px;width:${viewWidth}px;height:${viewHeight}px"></b>`;
}

function deleteSelectedConceptElement() {
  if (!currentConceptMap || !conceptMapSelection) return;
  if (conceptMapSelection.type === 'node') {
    const ids = conceptMapMultiSelection.size > 1 ? new Set(conceptMapMultiSelection) : new Set([conceptMapSelection.id]);
    currentConceptMap.nodes = currentConceptMap.nodes.filter(item => !ids.has(item.id));
    currentConceptMap.edges = currentConceptMap.edges.filter(item => !ids.has(item.from) && !ids.has(item.to));
    if (ids.has(conceptMapConnectSource)) conceptMapConnectSource = '';
  } else currentConceptMap.edges = currentConceptMap.edges.filter(item => item.id !== conceptMapSelection.id);
  pruneOrphanLinkingPhrases();
  conceptMapMultiSelection.clear(); conceptMapSelection = null; renderConceptMap(); scheduleConceptMapSave();
}

function pruneOrphanLinkingPhrases() {
  let removed = true;
  while (removed) {
    removed = false;
    const orphanIds = currentConceptMap.nodes.filter(node => {
      if (node.type !== 'linking_phrase') return false;
      return !currentConceptMap.edges.some(edge => edge.to === node.id) || !currentConceptMap.edges.some(edge => edge.from === node.id);
    }).map(node => node.id);
    if (orphanIds.length) {
      removed = true;
      currentConceptMap.nodes = currentConceptMap.nodes.filter(node => !orphanIds.includes(node.id));
      currentConceptMap.edges = currentConceptMap.edges.filter(edge => !orphanIds.includes(edge.from) && !orphanIds.includes(edge.to));
    }
  }
}

function conceptMapHistorySnapshot() {
  if (!currentConceptMap) return '';
  return JSON.stringify({
    title:currentConceptMap.title,
    focus_question:currentConceptMap.focus_question || '',
    theme:currentConceptMap.theme || 'light',
    nodes:currentConceptMap.nodes,
    edges:currentConceptMap.edges
  });
}

function resetConceptMapHistory() {
  const snapshot = conceptMapHistorySnapshot();
  conceptMapHistory = snapshot ? [snapshot] : [];
  conceptMapHistoryIndex = conceptMapHistory.length - 1;
}

function recordConceptMapHistory() {
  const snapshot = conceptMapHistorySnapshot();
  if (!snapshot || conceptMapHistory[conceptMapHistoryIndex] === snapshot) return;
  conceptMapHistory = conceptMapHistory.slice(0, conceptMapHistoryIndex + 1);
  conceptMapHistory.push(snapshot);
  if (conceptMapHistory.length > CONCEPT_MAP_HISTORY_LIMIT) conceptMapHistory.shift();
  conceptMapHistoryIndex = conceptMapHistory.length - 1;
}

function applyConceptMapHistory(index) {
  if (!currentConceptMap || index < 0 || index >= conceptMapHistory.length || index === conceptMapHistoryIndex) return false;
  const state = JSON.parse(conceptMapHistory[index]);
  conceptMapHistoryIndex = index;
  Object.assign(currentConceptMap, state);
  conceptMapMultiSelection.clear(); conceptMapSelection = null; conceptMapConnectSource = '';
  $('#conceptMapTitle').value = currentConceptMap.title;
  $('#conceptMapFocus').value = currentConceptMap.focus_question || '';
  renderConceptMap(); scheduleConceptMapSave({recordHistory:false});
  return true;
}

function undoConceptMap() { return applyConceptMapHistory(conceptMapHistoryIndex - 1); }
function redoConceptMap() { return applyConceptMapHistory(conceptMapHistoryIndex + 1); }

function selectedConceptNodeIds() {
  if (conceptMapSelection?.type !== 'node') return [];
  const ids = conceptMapMultiSelection.size > 1 ? [...conceptMapMultiSelection] : [conceptMapSelection.id];
  return ids.filter(id => conceptNode(id));
}

function copyConceptMapSelection() {
  const ids = selectedConceptNodeIds();
  if (!ids.length) return false;
  const selected = new Set(ids);
  conceptMapClipboard = {
    nodes:currentConceptMap.nodes.filter(node => selected.has(node.id)).map(node => structuredClone(node)),
    edges:currentConceptMap.edges.filter(edge => selected.has(edge.from) && selected.has(edge.to)).map(edge => structuredClone(edge))
  };
  return true;
}

function pasteConceptMapSelection() {
  if (!currentConceptMap || !conceptMapClipboard?.nodes.length) return false;
  const idMap = new Map(), pastedIds = [];
  conceptMapClipboard.nodes.forEach(source => {
    const node = structuredClone(source), prefix = node.type === 'linking_phrase' ? 'link' : 'node';
    node.id = nextConceptElementId(prefix, currentConceptMap.nodes); idMap.set(source.id, node.id); pastedIds.push(node.id);
    node.x = Math.max(0, Math.min(CONCEPT_MAP_WIDTH - node.width, node.x + 32));
    node.y = Math.max(0, Math.min(CONCEPT_MAP_HEIGHT - node.height, node.y + 32));
    currentConceptMap.nodes.push(node);
  });
  conceptMapClipboard.edges.forEach(source => {
    if (!idMap.has(source.from) || !idMap.has(source.to)) return;
    const edge = structuredClone(source); edge.id = nextConceptElementId('edge', currentConceptMap.edges); edge.from = idMap.get(source.from); edge.to = idMap.get(source.to);
    currentConceptMap.edges.push(edge);
  });
  conceptMapMultiSelection = new Set(pastedIds);
  conceptMapSelection = {type:'node', id:pastedIds[0]};
  renderConceptMap(); scheduleConceptMapSave();
  return true;
}

function nudgeConceptMapSelection(dx, dy) {
  const ids = selectedConceptNodeIds();
  if (!ids.length) return false;
  const selected = new Set(ids), nodes = ids.map(conceptNode).filter(Boolean);
  const minX = Math.min(...nodes.map(node => node.x)), minY = Math.min(...nodes.map(node => node.y));
  const maxX = Math.max(...nodes.map(node => node.x + node.width)), maxY = Math.max(...nodes.map(node => node.y + node.height));
  const moveX = Math.max(-minX, Math.min(CONCEPT_MAP_WIDTH - maxX, dx)), moveY = Math.max(-minY, Math.min(CONCEPT_MAP_HEIGHT - maxY, dy));
  nodes.forEach(node => { node.x += moveX; node.y += moveY; });
  nodes.filter(node => node.type === 'concept').forEach(node => recenterLinkingPhrasesForConcept(node.id, selected));
  renderConceptMap(); scheduleConceptMapSave();
  return true;
}

function scheduleConceptMapSave({recordHistory = true} = {}) {
  if (!currentConceptMap) return;
  if (recordHistory) recordConceptMapHistory();
  conceptMapRevision += 1;
  clearTimeout(conceptMapSaveTimer); $('#conceptMapSaveState').textContent = '有未保存修改'; $('#conceptMapSaveState').classList.add('saving');
  conceptMapSaveTimer = setTimeout(saveConceptMap, 650);
}

async function saveConceptMap() {
  if (!currentConceptMap) return false;
  if (conceptMapSavePromise) return conceptMapSavePromise;
  clearTimeout(conceptMapSaveTimer);
  const mapId = currentConceptMap.id, savingRevision = conceptMapRevision;
  currentConceptMap.title = $('#conceptMapTitle').value.trim() || currentConceptMap.title;
  currentConceptMap.focus_question = $('#conceptMapFocus').value.trim();
  const payload = JSON.stringify(currentConceptMap);
  conceptMapSaving = true; $('#conceptMapSaveState').textContent = '正在保存…';
  conceptMapSavePromise = (async () => {
    let succeeded = false;
    try {
      const saved = await api(`/concept-maps/${encodeURIComponent(mapId)}`, {method:'PATCH', body:payload});
      if (currentConceptMap?.id === mapId) {
        currentConceptMap.updated = saved.updated;
        currentConceptMap.version = saved.version;
        conceptMapSavedRevision = Math.max(conceptMapSavedRevision, savingRevision);
        succeeded = true;
      }
      return true;
    } catch (error) {
      if (currentConceptMap?.id === mapId) { $('#conceptMapSaveState').textContent = '保存失败'; notify('概念图保存失败', error.message, true); }
      return false;
    } finally {
      conceptMapSaving = false;
      conceptMapSavePromise = null;
      if (currentConceptMap?.id !== mapId) return;
      if (succeeded && conceptMapRevision > conceptMapSavedRevision) {
        $('#conceptMapSaveState').textContent = '有未保存修改'; $('#conceptMapSaveState').classList.add('saving');
        clearTimeout(conceptMapSaveTimer); conceptMapSaveTimer = setTimeout(saveConceptMap, 80);
      } else if (succeeded) {
        $('#conceptMapSaveState').textContent = '已自动保存'; $('#conceptMapSaveState').classList.remove('saving');
      }
    }
  })();
  return conceptMapSavePromise;
}

async function flushConceptMapSave() {
  clearTimeout(conceptMapSaveTimer);
  while (currentConceptMap && conceptMapSavedRevision < conceptMapRevision) {
    const succeeded = await saveConceptMap();
    if (!succeeded) return false;
  }
  return true;
}

function changeConceptMapZoom(nextZoom, anchorX = null, anchorY = null) {
  const shell = $('#conceptMapCanvasShell'), rect = shell.getBoundingClientRect(), viewport = currentConceptMap.viewport, oldZoom = viewport.zoom;
  const zoom = Math.min(3, Math.max(.2, nextZoom)), px = anchorX ?? rect.left + rect.width / 2, py = anchorY ?? rect.top + rect.height / 2;
  const localX = px - rect.left, localY = py - rect.top;
  viewport.x = localX - (localX - viewport.x) * zoom / oldZoom; viewport.y = localY - (localY - viewport.y) * zoom / oldZoom; viewport.zoom = zoom;
  applyConceptMapViewport(); scheduleConceptMapSave();
}

function fitConceptMap() {
  if (!currentConceptMap?.nodes.length) return;
  const shell = $('#conceptMapCanvasShell'), minX = Math.min(...currentConceptMap.nodes.map(node => node.x)), minY = Math.min(...currentConceptMap.nodes.map(node => node.y));
  const maxX = Math.max(...currentConceptMap.nodes.map(node => node.x + node.width)), maxY = Math.max(...currentConceptMap.nodes.map(node => node.y + node.height));
  const zoom = Math.min(1, Math.max(.25, Math.min((shell.clientWidth - 100) / Math.max(1, maxX - minX), (shell.clientHeight - 100) / Math.max(1, maxY - minY))));
  currentConceptMap.viewport = {zoom, x:(shell.clientWidth - (maxX - minX) * zoom) / 2 - minX * zoom, y:(shell.clientHeight - (maxY - minY) * zoom) / 2 - minY * zoom};
  applyConceptMapViewport(); scheduleConceptMapSave();
}

function layoutConceptMap() {
  if (!currentConceptMap?.nodes.length) return;
  const incoming = new Map(currentConceptMap.nodes.map(node => [node.id, 0]));
  currentConceptMap.edges.forEach(edge => incoming.set(edge.to, (incoming.get(edge.to) || 0) + 1));
  const depth = new Map(), queue = currentConceptMap.nodes.filter(node => !incoming.get(node.id)).map(node => (depth.set(node.id, 0), node.id));
  if (!queue.length) { queue.push(currentConceptMap.nodes[0].id); depth.set(queue[0], 0); }
  for (let i = 0; i < queue.length; i += 1) currentConceptMap.edges.filter(edge => edge.from === queue[i]).forEach(edge => { if (!depth.has(edge.to)) { depth.set(edge.to, (depth.get(queue[i]) || 0) + 1); queue.push(edge.to); } });
  currentConceptMap.nodes.forEach(node => { if (!depth.has(node.id)) depth.set(node.id, Math.max(0, ...depth.values()) + 1); });
  const columns = new Map(); currentConceptMap.nodes.forEach(node => { const level = depth.get(node.id); if (!columns.has(level)) columns.set(level, []); columns.get(level).push(node); });
  [...columns.entries()].sort(([a], [b]) => a - b).forEach(([level, nodes]) => nodes.forEach((node, index) => { node.x = 180 + level * 205; node.y = 150 + index * 90; }));
  recenterAllLinkingPhrases();
  renderConceptMap(); fitConceptMap(); scheduleConceptMapSave();
}

function exportConceptMapPng() {
  if (!currentConceptMap?.nodes.length) return;
  const minX = Math.min(...currentConceptMap.nodes.map(node => node.x)) - 60, minY = Math.min(...currentConceptMap.nodes.map(node => node.y)) - 60;
  const maxX = Math.max(...currentConceptMap.nodes.map(node => node.x + node.width)) + 60, maxY = Math.max(...currentConceptMap.nodes.map(node => node.y + node.height)) + 60;
  const width = maxX - minX, height = maxY - minY, scale = Math.min(2, 5000 / Math.max(width, height));
  const canvas = document.createElement('canvas'); canvas.width = Math.ceil(width * scale); canvas.height = Math.ceil(height * scale);
  const context = canvas.getContext('2d'); context.scale(scale, scale); context.translate(-minX, -minY); context.fillStyle = '#eef0f2'; context.fillRect(minX, minY, width, height);
  context.textAlign = 'center'; context.textBaseline = 'middle';
  currentConceptMap.edges.forEach(edge => {
    const data = conceptMapPath(edge); if (!data) return;
    context.strokeStyle = edge.color; context.lineWidth = 1.35; context.setLineDash(edge.dashed ? [6, 5] : []); context.stroke(new Path2D(data.d)); context.setLineDash([]);
    if (conceptEdgeHasArrow(edge)) { const angle = Math.atan2(data.end.y - data.start.y, data.end.x - data.start.x); context.beginPath(); context.moveTo(data.end.x, data.end.y); context.lineTo(data.end.x - 8 * Math.cos(angle - .45), data.end.y - 8 * Math.sin(angle - .45)); context.lineTo(data.end.x - 8 * Math.cos(angle + .45), data.end.y - 8 * Math.sin(angle + .45)); context.closePath(); context.fillStyle = edge.color; context.fill(); }
  });
  currentConceptMap.nodes.forEach(node => { if (node.type !== 'linking_phrase') { context.fillStyle = node.color; context.strokeStyle = node.border_color || '#9eb4c7'; context.lineWidth = 1; context.beginPath(); const radius = node.shape === 'rectangle' ? 2 : node.shape === 'pill' ? node.height / 2 : node.shape === 'ellipse' ? Math.min(node.width, node.height) / 2 : 4; context.roundRect(node.x, node.y, node.width, node.height, radius); context.fill(); context.stroke(); } else { context.fillStyle = '#eef0f2'; context.fillRect(node.x, node.y, node.width, node.height); } context.fillStyle = node.text_color || '#213044'; context.font = `${node.font_weight || 400} ${node.font_size || 13}px Microsoft YaHei`; context.fillText(node.text.slice(0, 40), node.x + node.width / 2, node.y + node.height / 2, node.width - (node.type === 'linking_phrase' ? 4 : 16)); });
  const link = document.createElement('a'); link.download = `${currentConceptMap.id}-${currentConceptMap.title.replace(/[\\/:*?"<>|]/g, '-')}.png`; link.href = canvas.toDataURL('image/png'); link.click(); notify('概念图已导出', link.download);
}

function exportConceptMapJson() {
  const blob = new Blob([JSON.stringify(currentConceptMap, null, 2)], {type:'application/json'}), link = document.createElement('a');
  link.download = `${currentConceptMap.id}.concept-map.json`; link.href = URL.createObjectURL(blob); link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function closeConceptMapMenus() {
  $$('.concept-map-menu').forEach(menu => menu.remove());
  $$('[data-concept-map-card-more]').forEach(item => item.setAttribute('aria-expanded', 'false'));
}

function showConceptMapMenu(button) {
  closeConceptMapMenus();
  const rect = button.getBoundingClientRect(), menu = document.createElement('div'); menu.className = 'concept-map-menu'; menu.style.top = `${rect.bottom + 5}px`; menu.style.right = `${innerWidth - rect.right}px`;
  menu.innerHTML = '<button type="button" data-export-concept-json>导出原始 JSON</button><button type="button" class="danger" data-delete-concept-map>删除这张概念图</button>'; document.body.appendChild(menu);
}

function showConceptMapCardMenu(button, mapId) {
  closeConceptMapMenus();
  $$('[data-concept-map-card-more]').forEach(item => item.setAttribute('aria-expanded', 'false')); button.setAttribute('aria-expanded', 'true');
  const item = conceptMaps.find(map => map.id === mapId); if (!item) return;
  const rect = button.getBoundingClientRect(), menu = document.createElement('div'); menu.className = 'concept-map-menu concept-map-card-menu';
  menu.style.top = `${rect.bottom + 5}px`; menu.style.left = `${Math.max(8, Math.min(innerWidth - 218, rect.right - 210))}px`;
  menu.innerHTML = `<button type="button" data-open-concept-map="${escapeHtml(mapId)}">打开概念图</button><button type="button" data-concept-card-menu-categories="${escapeHtml(mapId)}">所属分类</button><button type="button" class="danger" data-delete-concept-card="${escapeHtml(mapId)}">删除概念图</button>`;
  document.body.appendChild(menu);
  const menuRect = menu.getBoundingClientRect(); if (menuRect.bottom > innerHeight - 8) menu.style.top = `${Math.max(8, rect.top - menuRect.height - 5)}px`;
}

function showConceptMapCategorySubmenu(trigger, mapId) {
  $('.concept-map-card-submenu')?.remove();
  $('.concept-map-card-menu [data-concept-card-menu-categories]')?.classList.remove('submenu-open');
  const item = conceptMaps.find(map => map.id === mapId), parent = trigger.closest('.concept-map-card-menu');
  if (!item || !parent) return;
  trigger.classList.add('submenu-open');
  const category = item.category || '未分类', submenu = document.createElement('div');
  submenu.className = 'concept-map-menu concept-map-card-submenu';
  submenu.innerHTML = `<div class="concept-map-menu-label">选择分类</div>${conceptMapCategories.map(name => `<button type="button" data-set-concept-map-category="${escapeHtml(mapId)}" data-category="${escapeHtml(name)}" ${name === category ? 'disabled' : ''}>${escapeHtml(name)}${name === category ? '<span class="menu-tail">当前</span>' : ''}</button>`).join('')}`;
  document.body.appendChild(submenu);
  const parentRect = parent.getBoundingClientRect(), submenuRect = submenu.getBoundingClientRect(), gap = 7;
  const right = parentRect.right + gap;
  const left = right + submenuRect.width <= innerWidth - 8 ? right : Math.max(8, parentRect.left - submenuRect.width - gap);
  const top = Math.max(8, Math.min(parentRect.top, innerHeight - submenuRect.height - 8));
  submenu.style.left = `${left}px`; submenu.style.top = `${top}px`;
}

const conceptMapCanvasShell = document.querySelector('#conceptMapCanvasShell');

function beginConceptMapMarquee(event) {
  event.preventDefault();
  const shellRect = conceptMapCanvasShell.getBoundingClientRect(), start = {x:event.clientX, y:event.clientY};
  const gesture = {pointerId:event.pointerId, moved:false, finished:false};
  const marquee = document.createElement('div'); marquee.className = 'concept-map-marquee'; conceptMapCanvasShell.appendChild(marquee);
  conceptMapMultiSelection.clear(); conceptMapSelection = null; updateConceptMapSelectionUi();
  conceptMapCanvasShell.classList.add('marquee-selecting'); conceptMapCanvasShell.setPointerCapture(event.pointerId);
  const move = moveEvent => {
    if (moveEvent.pointerId !== gesture.pointerId || gesture.finished) return;
    const left = Math.max(shellRect.left, Math.min(start.x, moveEvent.clientX));
    const top = Math.max(shellRect.top, Math.min(start.y, moveEvent.clientY));
    const right = Math.min(shellRect.right, Math.max(start.x, moveEvent.clientX));
    const bottom = Math.min(shellRect.bottom, Math.max(start.y, moveEvent.clientY));
    if (!gesture.moved && Math.abs(moveEvent.clientX - start.x) + Math.abs(moveEvent.clientY - start.y) > 3) gesture.moved = true;
    marquee.style.left = `${left - shellRect.left}px`; marquee.style.top = `${top - shellRect.top}px`;
    marquee.style.width = `${Math.max(0, right - left)}px`; marquee.style.height = `${Math.max(0, bottom - top)}px`;
    const hits = $$('[data-concept-node]', $('#conceptMapNodes')).filter(item => {
      const rect = item.getBoundingClientRect();
      return rect.right >= left && rect.left <= right && rect.bottom >= top && rect.top <= bottom;
    }).map(item => item.dataset.conceptNode);
    conceptMapMultiSelection = new Set(hits);
    conceptMapSelection = hits.length ? {type:'node', id:hits[0]} : null;
    updateConceptMapSelectionUi();
  };
  const finish = finishEvent => {
    if (finishEvent.pointerId !== gesture.pointerId || gesture.finished) return;
    gesture.finished = true; marquee.remove(); conceptMapCanvasShell.classList.remove('marquee-selecting');
    conceptMapCanvasShell.removeEventListener('pointermove', move); conceptMapCanvasShell.removeEventListener('pointerup', finish); conceptMapCanvasShell.removeEventListener('pointercancel', finish);
    if (conceptMapMultiSelection.size < 2) conceptMapMultiSelection.clear();
    if (!gesture.moved) conceptMapSelection = null;
    updateConceptMapSelectionUi();
  };
  conceptMapCanvasShell.addEventListener('pointermove', move); conceptMapCanvasShell.addEventListener('pointerup', finish, {once:true}); conceptMapCanvasShell.addEventListener('pointercancel', finish, {once:true});
}

conceptMapCanvasShell.addEventListener('pointerdown', event => {
  if (!currentConceptMap) return;
  const interactive = event.target.closest('[data-concept-node],[data-concept-edge],[data-concept-edge-label],.concept-map-zoom,.concept-map-minimap');
  if (!interactive && event.button === 0 && event.shiftKey && !conceptMapSpacePressed) { beginConceptMapMarquee(event); return; }
  const spacePan = conceptMapSpacePressed && event.button === 0, middlePan = event.button === 1, blankPan = !interactive && event.button === 0;
  const wantsPan = spacePan || middlePan || blankPan;
  if (!wantsPan || (interactive && !spacePan && !middlePan)) return;
  if (!interactive) { conceptMapMultiSelection.clear(); conceptMapSelection = null; updateConceptMapSelectionUi(); }
  if (spacePan || middlePan) event.preventDefault();
  const viewport = currentConceptMap.viewport, start = {x:event.clientX, y:event.clientY, vx:viewport.x, vy:viewport.y};
  const gesture = {pointerId:event.pointerId, moved:false, finished:false};
  conceptMapCanvasShell.setPointerCapture(event.pointerId);
  const move = moveEvent => {
    if (moveEvent.pointerId !== gesture.pointerId || gesture.finished) return;
    const dx = moveEvent.clientX - start.x, dy = moveEvent.clientY - start.y;
    if (!gesture.moved && Math.abs(dx) + Math.abs(dy) > 3) { gesture.moved = true; conceptMapCanvasShell.classList.add('panning'); scheduleConceptMapSave(); }
    if (!gesture.moved) return;
    moveEvent.preventDefault(); viewport.x = start.vx + dx; viewport.y = start.vy + dy; applyConceptMapViewport();
  };
  const finish = finishEvent => {
    if (finishEvent.pointerId !== gesture.pointerId || gesture.finished) return;
    gesture.finished = true; conceptMapCanvasShell.classList.remove('panning');
    conceptMapCanvasShell.removeEventListener('pointermove', move); conceptMapCanvasShell.removeEventListener('pointerup', finish); conceptMapCanvasShell.removeEventListener('pointercancel', finish);
    if (gesture.moved) scheduleConceptMapSave();
  };
  conceptMapCanvasShell.addEventListener('pointermove', move); conceptMapCanvasShell.addEventListener('pointerup', finish, {once:true}); conceptMapCanvasShell.addEventListener('pointercancel', finish, {once:true});
});
conceptMapCanvasShell.addEventListener('dblclick', event => { if (!event.target.closest('[data-concept-node],[data-concept-edge],[data-concept-edge-label],.concept-map-minimap')) { const point = conceptMapPoint(event.clientX, event.clientY); addConceptNodeAt(point.x, point.y); } });
conceptMapCanvasShell.addEventListener('wheel', event => { if (!currentConceptMap) return; event.preventDefault(); changeConceptMapZoom(currentConceptMap.viewport.zoom * (event.deltaY > 0 ? .9 : 1.1), event.clientX, event.clientY); }, {passive:false});

document.addEventListener('pointerdown', event => {
  const edgeGroup = event.target.closest('[data-concept-edge]');
  if (edgeGroup && currentConceptMap) { event.stopPropagation(); conceptMapMultiSelection.clear(); conceptMapSelection = {type:'edge', id:edgeGroup.dataset.conceptEdge}; updateConceptMapSelectionUi(); }
  if (!event.target.closest('.concept-map-menu,#conceptMapMore,.concept-map-card-more')) closeConceptMapMenus();
});

document.addEventListener('input', event => {
  if (!currentConceptMap) return;
  if (event.target.id === 'conceptMapTitle') { currentConceptMap.title = event.target.value; scheduleConceptMapSave(); return; }
  if (event.target.id === 'conceptMapFocus') { currentConceptMap.focus_question = event.target.value; scheduleConceptMapSave(); return; }
});

document.addEventListener('click', async event => {
  if (event.target.closest('#newConceptMapCategory')) { await createConceptMapCategory(); return; }
  const renameCategory = event.target.closest('[data-rename-concept-map-category]');
  if (renameCategory) { event.preventDefault(); await renameConceptMapCategory(renameCategory.dataset.renameConceptMapCategory); return; }
  const deleteCategory = event.target.closest('[data-delete-concept-map-category]');
  if (deleteCategory) { event.preventDefault(); await deleteConceptMapCategory(deleteCategory.dataset.deleteConceptMapCategory); return; }
  if (event.target.closest('#clearConceptMapFilters')) { conceptMapSearch = ''; conceptMapCategoryFilter = ''; await renderConceptMapLibrary(); return; }
  if (event.target.closest('#newConceptMap,#newConceptMapEmpty')) { await createConceptMap(); return; }
  const cardMore = event.target.closest('[data-concept-map-card-more]');
  if (cardMore) { showConceptMapCardMenu(cardMore, cardMore.dataset.conceptMapCardMore); return; }
  const cardCategories = event.target.closest('[data-concept-card-menu-categories]');
  if (cardCategories) { showConceptMapCategorySubmenu(cardCategories, cardCategories.dataset.conceptCardMenuCategories); return; }
  const setCardCategory = event.target.closest('[data-set-concept-map-category]');
  if (setCardCategory) {
    const mapId = setCardCategory.dataset.setConceptMapCategory, category = setCardCategory.dataset.category;
    try { await api(`/concept-maps/${encodeURIComponent(mapId)}`, {method:'PATCH', body:JSON.stringify({category})}); closeConceptMapMenus(); await renderConceptMapLibrary(); notify('概念图分类已更新', `已移动到「${category}」`); }
    catch (error) { notify('分类更新失败', error.message, true); }
    return;
  }
  const deleteCard = event.target.closest('[data-delete-concept-card]');
  if (deleteCard) {
    const item = conceptMaps.find(map => map.id === deleteCard.dataset.deleteConceptCard); if (!item) return;
    const approved = await appConfirm({title:'删除这张概念图？', message:`“${item.title}”将移入回收站。`, confirmText:'移入回收站', danger:true});
    if (approved) { await api(`/concept-maps/${encodeURIComponent(item.id)}`, {method:'DELETE'}); closeConceptMapMenus(); await renderConceptMapLibrary(); notify('概念图已移入回收站', item.title); }
    return;
  }
  const open = event.target.closest('[data-open-concept-map]'); if (open) { closeConceptMapMenus(); await openConceptMap(open.dataset.openConceptMap); return; }
  if (event.target.closest('#closeConceptMap')) { await flushConceptMapSave(); await renderConceptMapLibrary(); return; }
  if (event.target.closest('#addConceptNode')) { const shell = $('#conceptMapCanvasShell'), rect = shell.getBoundingClientRect(), point = conceptMapPoint(rect.left + rect.width / 2, rect.top + rect.height / 2); addConceptNodeAt(point.x, point.y); return; }
  if (event.target.closest('#layoutConceptMap')) { layoutConceptMap(); return; }
  if (event.target.closest('#fitConceptMap,#conceptMapZoomValue')) { fitConceptMap(); return; }
  if (event.target.closest('#conceptMapMiniMap')) { fitConceptMap(); return; }
  if (event.target.closest('#conceptMapZoomIn')) { changeConceptMapZoom(currentConceptMap.viewport.zoom * 1.15); return; }
  if (event.target.closest('#conceptMapZoomOut')) { changeConceptMapZoom(currentConceptMap.viewport.zoom / 1.15); return; }
  if (event.target.closest('#exportConceptMap')) { exportConceptMapPng(); return; }
  if (event.target.closest('#conceptMapMore')) { showConceptMapMenu($('#conceptMapMore')); return; }
  if (event.target.closest('[data-export-concept-json]')) { exportConceptMapJson(); closeConceptMapMenus(); return; }
  if (event.target.closest('[data-delete-concept-map]') && currentConceptMap) {
    const approved = await appConfirm({title:'删除这张概念图？', message:`“${currentConceptMap.title}”将移入回收站。`, confirmText:'移入回收站', danger:true});
    if (approved) { await api(`/concept-maps/${encodeURIComponent(currentConceptMap.id)}`, {method:'DELETE'}); closeConceptMapMenus(); notify('概念图已移入回收站'); await renderConceptMapLibrary(); }
  }
});

document.addEventListener('keydown', event => {
  if (!currentConceptMap || $('#conceptMapWorkspace').hidden) return;
  const editable = event.target.matches('input,textarea,select,[contenteditable="true"]'), modifier = event.ctrlKey || event.metaKey, key = event.key.toLowerCase();
  if (!editable && modifier && key === 'z') { event.preventDefault(); event.shiftKey ? redoConceptMap() : undoConceptMap(); return; }
  if (!editable && modifier && key === 'y') { event.preventDefault(); redoConceptMap(); return; }
  if (!editable && modifier && key === 'a') {
    event.preventDefault(); conceptMapMultiSelection = new Set(currentConceptMap.nodes.map(node => node.id));
    conceptMapSelection = currentConceptMap.nodes[0] ? {type:'node', id:currentConceptMap.nodes[0].id} : null; updateConceptMapSelectionUi(); return;
  }
  if (!editable && modifier && key === 'c' && copyConceptMapSelection()) { event.preventDefault(); return; }
  if (!editable && modifier && key === 'x' && copyConceptMapSelection()) { event.preventDefault(); deleteSelectedConceptElement(); return; }
  if (!editable && modifier && key === 'v' && pasteConceptMapSelection()) { event.preventDefault(); return; }
  if (!editable && modifier && key === 'd' && copyConceptMapSelection()) { event.preventDefault(); pasteConceptMapSelection(); return; }
  if (!editable && !modifier && ['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)) {
    const distance = event.shiftKey ? 10 : 1, dx = event.key === 'ArrowLeft' ? -distance : event.key === 'ArrowRight' ? distance : 0, dy = event.key === 'ArrowUp' ? -distance : event.key === 'ArrowDown' ? distance : 0;
    if (nudgeConceptMapSelection(dx, dy)) event.preventDefault();
    return;
  }
  if (!editable && event.key === 'Escape') { conceptMapMultiSelection.clear(); conceptMapSelection = null; conceptMapConnectSource = ''; updateConceptMapSelectionUi(); return; }
  if (event.code === 'Space' && !editable) { conceptMapSpacePressed = true; conceptMapCanvasShell.classList.add('space-pan'); event.preventDefault(); }
  if ((event.key === 'Delete' || event.key === 'Backspace') && conceptMapSelection && !editable) deleteSelectedConceptElement();
  if (modifier && event.key === 'Enter' && !editable) { event.preventDefault(); const shell = $('#conceptMapCanvasShell'), rect = shell.getBoundingClientRect(), point = conceptMapPoint(rect.left + rect.width / 2, rect.top + rect.height / 2); addConceptNodeAt(point.x, point.y); }
});

document.addEventListener('keyup', event => { if (event.code === 'Space') { conceptMapSpacePressed = false; conceptMapCanvasShell.classList.remove('space-pan'); } });
window.addEventListener('blur', () => { conceptMapSpacePressed = false; conceptMapCanvasShell.classList.remove('space-pan'); });
document.addEventListener('paste', event => {
  if (!currentConceptMap || $('#conceptMapWorkspace').hidden || event.target.matches('input,textarea,[contenteditable="true"]')) return;
  const text = event.clipboardData?.getData('text/plain').trim(); if (!text) return; event.preventDefault();
  const shell = $('#conceptMapCanvasShell'), rect = shell.getBoundingClientRect(), point = conceptMapPoint(rect.left + rect.width / 2, rect.top + rect.height / 2); addConceptNodeAt(point.x, point.y, text.slice(0, 500), false);
});
