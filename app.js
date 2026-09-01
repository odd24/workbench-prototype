const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

const sidebar = $('#sidebar');
const main = $('.main');
const overlay = $('#modalOverlay');
const createDialog = $('#createDialog');
const searchPanel = $('#searchPanel');
const detailDrawer = $('#detailDrawer');
const toast = $('#toast');
const typeMap = {'问题':'issue', '待办':'todo', '信息':'info'};
const typeNames = {issue:'问题', todo:'待办', info:'信息'};
const typeIcons = {issue:'!', todo:'✓', info:'i'};
const boardStatuses = ['待处理', '分析中', '处理中', '已解决'];
const statusColors = {'待处理':'gray', '分析中':'blue', '处理中':'orange', '已解决':'green'};
const COLOR_THEME_PALETTE = ['#ffffff','#4e83fd','#14c0ff','#00d6b9','#34c724','#b3d600','#fff258','#ff8800','#f54a45','#f14ba9','#7f3bf5'];
const COLOR_SHADE_PALETTE = [
  ['#f8f9fa','#e1eaff','#d9f3fd','#d5f6f2','#d9f5d6','#eef6c6','#faf1d1','#fed4a4','#fbbfbc','#fdddef','#ece2fe'],
  ['#dee0e3','#bacefd','#7edafb','#64e8d6','#8ee085','#c3dd40','#fad355','#ffba6b','#f76964','#f57ac0','#ad82f7'],
  ['#8f959e','#3370ff','#049fd7','#04b49c','#2ea121','#8fac02','#ffc60a','#de7802','#d83931','#f01d94','#6425d0'],
  ['#373c43','#245bdb','#037eaa','#036356','#186010','#667901','#dc9b04','#8f4f04','#812520','#9e1361','#380d82'],
  ['#1f2329','#133c9a','#006185','#024b41','#124b0c','#495700','#795101','#6b3900','#621c18','#7a0f4b','#270561'],
];

function recentColors(storageKey) {
  try { return JSON.parse(localStorage.getItem(storageKey) || '[]').filter(value => /^#[0-9a-f]{6}$/i.test(value)).slice(0, 12); }
  catch { return []; }
}

function rememberRecentColor(storageKey, value) {
  if (!/^#[0-9a-f]{6}$/i.test(value || '')) return;
  const normalized = value.toLowerCase();
  localStorage.setItem(storageKey, JSON.stringify([normalized, ...recentColors(storageKey).filter(item => item !== normalized)].slice(0, 12)));
}
let selectedType = '问题';
let selectedProjectId = '';
let projectTab = 'issues';
let currentPage = 'home';
let projectViewMode = 'board';
let projectFilters = {status:'', tag:'', priority:''};
let timelineFilters = {type:[], project:[], status:[], priority:[], tag:[]};
let timelineSort = {field:'updated', direction:'desc'};
let editorMode = 'wysiwyg';
let projects = [];
let records = [];
let projectAssetLibrary = [];
let projectAssetCategories = [];
let projectAssetProjectId = '';
let projectAssetCategoryFilter = '';
let projectAssetSearch = '';
let projectAssetSearchTimer = null;
let currentRecord = null;
let configData = null;
let apiAvailable = false;
let externalEditorData = null;
let draggedCard = null;
let draggedInfoCard = null;
let draggedInfoField = null;
let draggedColumn = null;
let draggedProjectLink = null;
let cardOrderChanged = false;
let cardDropHandled = false;
let draggedCardSourceStatus = '';
let lastSearchResults = [];
let searchTypeFilter = '';
let searchFilters = {project:'', tag:'', status:'', priority:''};
let editorDirty = false;
let conflictRecord = null;
let selectedWorkflowId = 'standard';
let pendingImport = null;
let activeManagePage = '';
let savedManageSnapshot = null;
let projectEditSnapshot = null;
let unsavedPromptPromise = null;
let recordNavigationStack = [];
let currentUsageView = null;
let usageNavigationStack = [];
let usageReturnContext = null;
let editorSaveTimer = null;
let editorExpanded = false;
let editorContentExpanded = false;
let lastEditorRange = null;
let createContext = {projectId:'', status:''};
let lastRecordSignature = '';
let trashItems = [];
let trashSelection = new Set();
let documents = [];
let currentDocument = null;
let documentMode = 'read';
let documentDirty = false;
let documentSaving = false;
let documentFilters = {categoryQuery:''};
let documentCategoryFileQueries = {};
let documentOpenCategories = new Set();
let documentSelection = new Set();
let documentExportMode = false;
let documentLastRange = null;
let documentExpanded = false;
let documentOutlineCollapsed = localStorage.getItem('workbench-document-outline-collapsed') === 'true';
let documentOutlineTimer = null;
let conceptMaps = [];
let currentConceptMap = null;
let conceptMapSelection = null;
let conceptMapConnectSource = '';
let conceptMapSaveTimer = null;
let conceptMapSaving = false;
let conceptMapSearch = '';

const PROJECT_CARD_COLLAPSE_LIMIT = 5;
const PROJECT_LIST_COLLAPSE_LIMIT = 12;
const EDITOR_COLLAPSE_HEIGHT = 420;

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {'Content-Type':'application/json', ...(options.headers || {})},
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `请求失败 (${response.status})`);
  return payload;
}

function notify(title, detail = '对应 Markdown 文件已自动更新', error = false) {
  $('.toast > span').textContent = error ? '!' : '✓';
  $('.toast strong').textContent = title;
  $('.toast small').textContent = detail;
  toast.classList.toggle('error', error);
  toast.classList.add('visible');
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => toast.classList.remove('visible'), 3000);
}

function openAppDialog({title, message = '', detail = '', confirmText = '确认', cancelText = '取消', danger = false, input = null}) {
  const dialog = $('#appDialog');
  if (dialog.open) dialog.close('cancel');
  dialog.classList.toggle('danger', danger);
  dialog.classList.toggle('input-mode', Boolean(input));
  $('.app-dialog-icon', dialog).textContent = danger ? '!' : '?';
  $('#appDialogEyebrow').textContent = input ? '填写信息' : danger ? '危险操作' : '请确认操作';
  $('#appDialogTitle').textContent = title;
  $('#appDialogMessage').textContent = message;
  $('#appDialogDetail').textContent = detail;
  $('#appDialogConfirm').textContent = confirmText;
  $('button[value="cancel"]:not(.dialog-close)', dialog).textContent = cancelText;
  const field = $('#appDialogInput');
  const options = $('#appDialogOptions');
  if (input) {
    $('#appDialogInputLabel').textContent = input.label || '请输入内容';
    field.type = input.type || 'text';
    field.value = input.value || '';
    field.placeholder = input.placeholder || '';
    field.required = input.required !== false;
    field.readOnly = Boolean(input.readOnly);
    const choices = Array.isArray(input.choices) ? input.choices.filter(choice => choice?.value || choice?.label) : [];
    options.hidden = !choices.length;
    options.innerHTML = choices.map(choice => `<button type="button" data-app-dialog-choice="${escapeHtml(choice.value || choice.label)}" style="--choice-color:${safeColor(choice.color)}"><i></i><span>${escapeHtml(choice.label || choice.value)}</span></button>`).join('');
    options.onclick = event => {
      const choice = event.target.closest('[data-app-dialog-choice]');
      if (!choice) return;
      field.value = choice.dataset.appDialogChoice;
      dialog.close('confirm');
    };
  } else {
    field.value = '';
    field.required = false;
    field.readOnly = false;
    options.hidden = true;
    options.innerHTML = '';
    options.onclick = null;
  }
  dialog.returnValue = 'cancel';
  dialog.showModal();
  setTimeout(() => {
    if (input) { field.focus(); if (input.select !== false) field.select(); }
    else $('#appDialogConfirm').focus();
  }, 20);
  return new Promise(resolve => dialog.addEventListener('close', () => resolve({confirmed:dialog.returnValue === 'confirm', value:field.value}), {once:true}));
}

async function appConfirm(options) {
  return (await openAppDialog(options)).confirmed;
}

async function appPrompt(options) {
  const result = await openAppDialog({...options, input:options.input || {label:options.label, value:options.value, placeholder:options.placeholder, type:options.type}});
  return result.confirmed ? result.value : null;
}

function safeExportName(value) {
  return String(value || 'workbench').replace(/[<>:"/\\|?*\x00-\x1F]/g, '-').replace(/[. ]+$/g, '').trim() || 'workbench';
}

function exportDateStamp() {
  const date = new Date();
  return `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}`;
}

let exportLocationData = null;
let exportDirectoryBrowserData = null;
let exportDirectoryRequestId = 0;

async function loadExportDirectory() {
  exportLocationData = await api('/export-location');
  return exportLocationData;
}

function renderExportLocation() {
  const selected = Boolean(exportLocationData?.path);
  $('#exportLocationCard').classList.toggle('selected', selected);
  $('#exportLocationName').textContent = selected ? exportLocationData.name : '尚未选择位置';
  $('#exportLocationHint').textContent = selected ? exportLocationData.path : '选择一次后会记住，下次可直接导出';
  $('#chooseExportLocation').textContent = selected ? '更换位置' : '选择位置';
  $('#confirmExport').disabled = !selected;
}

async function chooseExportDirectory() {
  if (!exportLocationData) await loadExportDirectory();
  const dialog = $('#exportLocationDialog');
  $('#exportLocationChoices').innerHTML = (exportLocationData.common || []).map(item => `<button type="button" class="export-location-choice" data-export-path="${escapeHtml(item.path)}"><span>${item.id === 'downloads' ? '⇩' : item.id === 'desktop' ? '▣' : '▤'}</span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.path)}</small></button>`).join('');
  const firstExport = !$('#exportDialog').open;
  $('#saveExportLocation').dataset.defaultText = firstExport ? '选择此目录并导出' : '使用此位置';
  $('#saveExportLocation').textContent = $('#saveExportLocation').dataset.defaultText;
  dialog.returnValue = 'cancel';
  dialog.showModal();
  await loadExportDirectoryBrowser(exportLocationData.path || '');
  return new Promise(resolve => dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), {once:true}));
}

async function loadExportDirectoryBrowser(path = '') {
  const list = $('#exportDirectoryList');
  const requestId = ++exportDirectoryRequestId;
  const hasExistingContent = Boolean(exportDirectoryBrowserData && list.children.length);
  let loadingTimer = setTimeout(() => {
    if (requestId !== exportDirectoryRequestId) return;
    list.classList.add('loading');
    list.setAttribute('aria-busy', 'true');
    if (!hasExistingContent) list.innerHTML = '<div class="export-directory-loading">正在读取文件夹…</div>';
  }, 120);
  try {
    const result = await api(`/directories?path=${encodeURIComponent(path)}`);
    if (requestId !== exportDirectoryRequestId) return false;
    exportDirectoryBrowserData = result;
    $('#exportLocationPath').value = exportDirectoryBrowserData.path;
    $('#exportDirectoryCurrent').textContent = exportDirectoryBrowserData.path;
    $('#exportDirectoryUp').disabled = !exportDirectoryBrowserData.parent;
    const roots = exportDirectoryBrowserData.roots || [];
    const rootButtons = roots.length > 1 ? `<div class="export-directory-roots">${roots.map(item => `<button type="button" data-directory-path="${escapeHtml(item.path)}" title="${escapeHtml(item.path)}"><span>▣</span>${escapeHtml(item.name)}</button>`).join('')}</div>` : '';
    const folders = (exportDirectoryBrowserData.directories || []).map(item => `<button type="button" class="export-directory-item" data-directory-path="${escapeHtml(item.path)}" title="进入 ${escapeHtml(item.name)}"><span>▰</span><strong>${escapeHtml(item.name)}</strong><small>打开</small></button>`).join('');
    list.innerHTML = `${rootButtons}${folders || '<div class="export-directory-empty">当前文件夹中没有子文件夹，可直接选择这里。</div>'}`;
    return true;
  } catch (error) {
    if (requestId !== exportDirectoryRequestId) return false;
    list.innerHTML = `<div class="export-directory-empty error">${escapeHtml(error.message)}</div>`;
    notify('无法浏览该目录', error.message, true);
    return false;
  } finally {
    clearTimeout(loadingTimer);
    if (requestId === exportDirectoryRequestId) {
      list.classList.remove('loading');
      list.removeAttribute('aria-busy');
    }
  }
}

async function saveChosenExportDirectory() {
  const path = $('#exportLocationPath').value.trim();
  const button = $('#saveExportLocation');
  button.disabled = true;
  button.textContent = '正在验证…';
  try {
    exportLocationData = await api('/export-location', {method:'PUT', body:JSON.stringify({path})});
    renderExportLocation();
    $('#exportLocationDialog').close('confirm');
    notify('导出位置已保存', exportLocationData.path);
    return true;
  } catch (error) {
    notify('无法使用该导出位置', error.message, true);
    $('#exportLocationPath').focus();
    return false;
  } finally {
    button.disabled = false;
    button.textContent = button.dataset.defaultText || '使用此位置';
  }
}

async function browseExportDirectory() {
  const button = $('#browseExportLocation');
  button.disabled = true;
  button.textContent = '正在打开…';
  try {
    return await loadExportDirectoryBrowser($('#exportLocationPath').value.trim());
  } finally {
    button.disabled = false;
    button.textContent = '打开路径';
  }
}

async function confirmExportDetails({project, filename}) {
  await loadExportDirectory();
  const dialog = $('#exportDialog');
  $('#exportDialogTitle').textContent = project ? '导出当前项目' : '导出完整工作台';
  $('#exportDialogMessage').textContent = project
    ? `将项目「${project.name}」及其记录、附件打包为 ZIP。`
    : '将全部项目、记录、配置和附件打包为 ZIP 备份。';
  $('#exportFilename').textContent = filename;
  renderExportLocation();
  if (!exportLocationData.path) return chooseExportDirectory();
  dialog.returnValue = 'cancel';
  dialog.showModal();
  return new Promise(resolve => dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), {once:true}));
}

async function exportArchive({project = null} = {}) {
  const projectNameValue = project?.name || '';
  const filename = project
    ? `${safeExportName(projectNameValue)}-${exportDateStamp()}.zip`
    : `workbench-backup-${exportDateStamp()}.zip`;
  if (!await confirmExportDetails({project, filename})) return false;
  try {
    notify('正在准备导出文件', project ? projectNameValue : '完整工作台备份');
    const result = await api('/export-file', {method:'POST', body:JSON.stringify({project_id:project?.id || null, filename})});
    notify('导出完成', result.path);
    return true;
  } catch (error) {
    notify('导出失败', error.message || '无法写入所选位置', true);
    return false;
  }
}

function formatDate(value) {
  if (!value) return '无截止日期';
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat('zh-CN', {month:'numeric', day:'numeric'}).format(date);
}

function projectName(projectId) {
  return projects.find(item => item.id === projectId)?.name || '未归属';
}

function projectChipHtml(projectId) {
  const project = projects.find(item => item.id === projectId);
  const color = safeColor(project?.color);
  return `<span class="project-color-chip" style="--project-color:${color}"><i></i>${escapeHtml(project?.name || '未归属')}</span>`;
}

function safeColor(value, fallback = '#64748b') {
  return /^#[0-9a-f]{6}$/i.test(value || '') ? value.toLowerCase() : fallback;
}

function tagColor(tagName) {
  const configured = (configData?.tags || []).find(item => item.name === tagName)?.color;
  return safeColor(configured);
}

function drawerTagHtml(tagName) {
  const color = tagColor(tagName);
  return `<span class="record-tag color-tag" style="--tag-color:${color}" title="标签颜色：${color.toUpperCase()}">${escapeHtml(tagName)} <button data-remove-tag="${escapeHtml(tagName)}" aria-label="移除标签 ${escapeHtml(tagName)}">×</button></span>`;
}

function projectTagHtml(tagName) {
  const color = tagColor(tagName);
  return `<span class="project-tag color-tag" style="--tag-color:${color}" title="${escapeHtml(tagName)} · ${color.toUpperCase()}">${escapeHtml(tagName)}</span>`;
}

function recordStatusColor(record) {
  return safeColor(statusesFor(record.type, record.project_id).find(item => item.name === record.status)?.color);
}

function statusChipHtml(record) {
  const color = recordStatusColor(record);
  return `<span class="project-status-chip" style="--status-color:${color}"><i></i>${escapeHtml(record.status)}</span>`;
}

function priorityChipHtml(priority) {
  const className = priority === '紧急' ? 'urgent' : priority === '高' ? 'high' : priority === '低' ? 'low' : 'normal';
  return `<span class="priority ${className}">${escapeHtml(priority || '普通')}</span>`;
}

function typeChipHtml(record) {
  return `<span class="record-type-chip ${record.type}">${typeIcon(record)}${escapeHtml(typeNames[record.type] || record.type)}</span>`;
}

function infoFieldRowHtml(field = {}, scope = 'drawer') {
  const insertLabel = scope === 'create' ? '插入到补充说明' : '插入正文';
  return `<div class="info-field-row" data-info-field-row><button type="button" class="info-field-drag" draggable="true" aria-label="拖动调整字段顺序" title="拖动调整顺序">⠿</button><input data-info-field-name value="${escapeHtml(field.name || '')}" placeholder="字段名称，如：服务器地址" aria-label="信息字段名称"><textarea data-info-field-value placeholder="字段内容" aria-label="信息字段内容">${escapeHtml(field.value || '')}</textarea><input data-info-field-note value="${escapeHtml(field.note || '')}" placeholder="字段说明（可选）" aria-label="信息字段说明"><button type="button" class="insert-info-field" data-insert-info-field title="将该键值对及说明插入正文">${insertLabel}</button><button type="button" data-remove-info-field aria-label="删除字段" title="删除字段">×</button></div>`;
}

function infoFieldsFrom(root) {
  return $$('[data-info-field-row]', root).map(row => {
    const field = {name:$('[data-info-field-name]', row).value.trim(), value:$('[data-info-field-value]', row).value.trim()};
    const note = $('[data-info-field-note]', row)?.value.trim();
    if (note) field.note = note;
    return field;
  }).filter(field => field.name || field.value);
}

function drawerInfoColor() {
  return $('#infoColorPicker input[type="color"]')?.value || currentRecord?.info_color || '#35a99a';
}

function renderCreateInfoFields(fields = [{name:'', value:''}]) {
  $('#createInfoFieldList').innerHTML = fields.map(field => infoFieldRowHtml(field, 'create')).join('');
  requestAnimationFrame(() => autoSizeInfoFieldTextareas($('#createInfoFieldList')));
}

function renderDrawerInfoFields(fields = []) {
  $('#drawerInfoFieldList').innerHTML = (fields.length ? fields : [{name:'', value:''}]).map(field => infoFieldRowHtml(field)).join('');
  requestAnimationFrame(() => autoSizeInfoFieldTextareas($('#drawerInfoFieldList')));
}

function autoSizeInfoFieldTextareas(root = document) {
  $$('[data-info-field-value]', root).forEach(textarea => {
    textarea.style.height = '39px';
    const height = Math.min(Math.max(textarea.scrollHeight, 39), 120);
    textarea.style.height = `${height}px`;
    textarea.style.overflowY = textarea.scrollHeight > 120 ? 'auto' : 'hidden';
  });
}

function infoCardHtml(record, index = 0) {
  const fields = record.info_fields || [];
  const visibleFields = fields.slice(0, 8);
  const color = safeColor(record.info_color, '#35a99a');
  return `<article class="info-display-card ${index >= PROJECT_LIST_COLLAPSE_LIMIT ? 'auto-collapsed-record' : ''}" draggable="true" style="--card-order:${index};--info-color:${color}" data-record-id="${escapeHtml(record.id)}"><div class="info-card-title-row"><span class="info-card-drag" aria-hidden="true">⠿</span><h3>${escapeHtml(record.title)}</h3></div><div class="info-card-fields">${visibleFields.map(field => `<div class="info-card-field"><span title="${escapeHtml(field.name)}">${escapeHtml(field.name)}</span><div><strong title="${escapeHtml(`${field.value || ''}${field.note ? `\n说明：${field.note}` : ''}`)}">${escapeHtml(field.value || '—')}</strong><button type="button" data-copy-info-value="${encodeURIComponent(field.value || '')}" aria-label="复制 ${escapeHtml(field.name)}" title="复制字段内容">⧉</button></div></div>`).join('') || '<div class="info-card-empty">尚未填写结构化字段</div>'}${fields.length > visibleFields.length ? `<button type="button" class="info-more-fields" data-record-id="${escapeHtml(record.id)}">还有 ${fields.length - visibleFields.length} 个字段，查看全部</button>` : ''}</div></article>`;
}

function timelineFilterOptions(field) {
  const counts = new Map();
  const add = value => counts.set(value, (counts.get(value) || 0) + 1);
  if (field === 'tag') records.forEach(record => (record.tags || []).length ? record.tags.forEach(add) : add('__none__'));
  else records.forEach(record => add(field === 'project' ? (record.project_id || '__none__') : (record[field] ?? '__none__')));
  const labels = value => field === 'type' ? (typeNames[value] || value) : field === 'project' ? (value === '__none__' ? '（空白）' : projectName(value)) : value === '__none__' ? '（空白）' : value;
  const order = field === 'priority' ? ['紧急','高','普通','低'] : [...counts.keys()].sort((a, b) => labels(a).localeCompare(labels(b), 'zh-CN'));
  return order.filter(value => counts.has(value)).map(value => ({value, label:labels(value), count:counts.get(value)}));
}

function recordMatchesTimelineFilter(record, field) {
  const selected = timelineFilters[field] || [];
  if (!selected.length) return true;
  if (field === 'project') return selected.includes(record.project_id || '__none__');
  if (field === 'tag') return selected.some(value => value === '__none__' ? !(record.tags || []).length : (record.tags || []).includes(value));
  return selected.includes(record[field] ?? '__none__');
}

function hasTimelineFilters() {
  return Object.values(timelineFilters).some(values => values.length);
}

function closeTimelineFilter() {
  const popover = $('#timelineFilterPopover');
  if (!popover) return;
  popover.classList.remove('visible');
  popover.setAttribute('aria-hidden', 'true');
  $$('.timeline-filter-trigger[aria-expanded="true"]').forEach(button => button.setAttribute('aria-expanded', 'false'));
}

function openTimelineFilter(trigger) {
  const popover = $('#timelineFilterPopover');
  const field = trigger.dataset.timelineFilter;
  const names = {type:'类型', project:'项目', status:'状态', priority:'优先级', tag:'标签'};
  const options = timelineFilterOptions(field);
  const configured = timelineFilters[field] || [];
  const selected = new Set(configured.length ? configured : options.map(item => item.value));
  popover.dataset.field = field;
  popover.innerHTML = `<header><strong>${names[field]}筛选</strong><button type="button" data-timeline-filter-close aria-label="关闭">×</button></header><div class="timeline-filter-search"><span>⌕</span><input id="timelineFilterSearch" placeholder="搜索选项" autocomplete="off"></div><label class="timeline-filter-option timeline-filter-all"><input type="checkbox" id="timelineFilterSelectAll" ${selected.size === options.length ? 'checked' : ''}><span>全选</span><em>${options.reduce((sum,item) => sum + item.count, 0)}</em></label><div class="timeline-filter-values">${options.map(item => `<label class="timeline-filter-option" data-filter-search="${escapeHtml(item.label.toLowerCase())}"><input type="checkbox" value="${escapeHtml(item.value)}" ${selected.has(item.value) ? 'checked' : ''}><span>${escapeHtml(item.label)}</span><em>${item.count}</em></label>`).join('') || '<div class="timeline-filter-no-options">暂无可筛选项</div>'}</div><footer><button type="button" data-timeline-filter-clear>清除</button><span></span><button type="button" data-timeline-filter-close>取消</button><button type="button" class="primary-button" data-timeline-filter-apply>确认</button></footer>`;
  closeTimelineFilter();
  popover.classList.add('visible');
  popover.setAttribute('aria-hidden', 'false');
  trigger.setAttribute('aria-expanded', 'true');
  requestAnimationFrame(() => {
    const rect = trigger.getBoundingClientRect();
    const width = popover.offsetWidth, height = popover.offsetHeight;
    popover.style.left = `${Math.max(12, Math.min(rect.right - width, window.innerWidth - width - 12))}px`;
    const below = rect.bottom + 7;
    popover.style.top = `${below + height <= window.innerHeight - 12 ? below : Math.max(12, rect.top - height - 7)}px`;
    $('#timelineFilterSearch')?.focus();
  });
}

function workflowForProject(projectId) {
  const project = projects.find(item => item.id === projectId);
  const workflows = configData?.workflow_templates || [];
  return workflows.find(item => item.id === (project?.workflow_template || 'standard')) || workflows[0] || {statuses:configData?.status_templates || {}};
}

function statusesFor(recordType, projectId) {
  return workflowForProject(projectId).statuses?.[recordType] || configData?.status_templates?.[recordType] || [];
}

function typeIcon(record) {
  return `<span class="type-icon ${record.type}">${typeIcons[record.type]}</span>`;
}

function inlineMarkdownToHtml(text) {
  let output = text;
  output = output.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, source) => markdownImageHtml(unescapeHtml(alt), unescapeHtml(source)));
  output = output.replace(/\[\[([A-Za-z]+-\d+)\]\]/g, (_, id) => {
    const record = records.find(item => item.id.toLowerCase() === id.toLowerCase());
    const canonicalId = record?.id || id.toUpperCase();
    const label = record ? `${canonicalId} · ${record.title}` : canonicalId;
    return `<span class="internal-link" contenteditable="false" role="button" tabindex="0" data-reference-id="${escapeHtml(canonicalId)}" title="打开引用记录">${escapeHtml(label)}</span>&#8203;`;
  });
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

function markdownImageHtml(alt, source) {
  const normalized = String(source || '').trim().replace(/^<|>$/g, '');
  let filename = normalized.split(/[\\/]/).at(-1) || '';
  try { filename = decodeURIComponent(filename); } catch { /* 保留包含不完整百分号的原始文件名 */ }
  filename = filename.replace(/[?#].*$/, '');
  const attachment = currentRecord && parsedAttachments().find(item => item.name === filename || item.path === normalized);
  let url = normalized;
  if (attachment) url = `/api/attachments/${encodeURIComponent(currentRecord.id)}/${encodeURIComponent(attachment.name)}`;
  else if (!/^(?:https?:\/\/|\/api\/attachments\/|\.{0,2}\/)/i.test(normalized)) return `![${escapeHtml(alt)}](${escapeHtml(normalized)})`;
  return `<img class="editor-inline-image" src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" data-markdown-src="${escapeHtml(normalized)}">`;
}

function unescapeHtml(value) {
  return String(value).replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&amp;/g, '&');
}

function normalizeCodeLanguage(language = 'txt') {
  const value = String(language).toLowerCase().trim();
  const aliases = {text:'txt', plaintext:'txt', js:'javascript', ts:'typescript', py:'python', sh:'shell', bash:'shell', html:'html', xml:'html', yml:'yaml', csharp:'csharp', 'c#':'csharp', cpp:'cpp', 'c++':'cpp'};
  return aliases[value] || value.replace(/[^a-z0-9+#.-]/g, '') || 'txt';
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
  for (const match of code.matchAll(matcher)) {
    output += escapeHtml(code.slice(cursor, match.index));
    const captureIndex = match.slice(1).findIndex(value => value !== undefined);
    output += `<span class="code-token token-${patterns[captureIndex].type}">${escapeHtml(match[0])}</span>`;
    cursor = match.index + match[0].length;
  }
  return output + escapeHtml(code.slice(cursor));
}

function markdownToHtml(markdown = '', interactive = false) {
  const lines = escapeHtml(markdown).split('\n');
  const output = [];
  let listType = '';
  const closeList = () => { if (listType) output.push(`</${listType}>`); listType = ''; };
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    if (line.startsWith('```')) {
      closeList();
      const language = normalizeCodeLanguage(unescapeHtml(line.slice(3).trim()));
      const codeLines = [];
      index++;
      while (index < lines.length && !lines[index].startsWith('```')) {
        codeLines.push(lines[index]);
        index++;
      }
      const rawCode = unescapeHtml(codeLines.join('\n'));
      output.push(`<pre><code data-language="${language}">${rawCode ? syntaxHighlightCode(rawCode, language) : '<br>'}</code></pre>`);
      continue;
    }
    const task = line.match(/^- \[([ xX])\] (.*)$/);
    const unordered = line.match(/^- (.*)$/);
    const ordered = line.match(/^\d+\. (.*)$/);
    if (task || unordered || ordered) {
      const nextType = ordered ? 'ol' : 'ul';
      if (listType !== nextType) { closeList(); output.push(`<${nextType}>`); listType = nextType; }
      if (task) output.push(`<li class="task-item"><input type="checkbox" ${interactive ? '' : 'disabled'} ${task[1].toLowerCase() === 'x' ? 'checked' : ''}>${inlineMarkdownToHtml(task[2])}</li>`);
      else output.push(`<li>${inlineMarkdownToHtml((ordered || unordered)[1])}</li>`);
      continue;
    }
    closeList();
    if (line.startsWith('###### ')) output.push(`<h6>${inlineMarkdownToHtml(line.slice(7))}</h6>`);
    else if (line.startsWith('##### ')) output.push(`<h5>${inlineMarkdownToHtml(line.slice(6))}</h5>`);
    else if (line.startsWith('#### ')) output.push(`<h4>${inlineMarkdownToHtml(line.slice(5))}</h4>`);
    else if (line.startsWith('### ')) output.push(`<h3>${inlineMarkdownToHtml(line.slice(4))}</h3>`);
    else if (line.startsWith('## ')) output.push(`<h2>${inlineMarkdownToHtml(line.slice(3))}</h2>`);
    else if (line.startsWith('# ')) output.push(`<h1>${inlineMarkdownToHtml(line.slice(2))}</h1>`);
    else if (/^&gt;($|\s)/.test(line)) {
      const quoteLines = [];
      while (index < lines.length && /^&gt;($|\s)/.test(lines[index])) {
        quoteLines.push(lines[index].replace(/^&gt; ?/, ''));
        index++;
      }
      index--;
      output.push(`<blockquote>${quoteLines.map(value => `<p>${value ? inlineMarkdownToHtml(value) : '<br>'}</p>`).join('')}</blockquote>`);
    }
    else if (/^&lt;div align=&quot;(left|center|right)&quot;&gt;([\s\S]*)&lt;\/div&gt;$/.test(line)) {
      const match = line.match(/^&lt;div align=&quot;(left|center|right)&quot;&gt;([\s\S]*)&lt;\/div&gt;$/);
      output.push(`<div style="text-align:${match[1]}">${inlineMarkdownToHtml(match[2])}</div>`);
    }
    else if (line.trim()) output.push(`<p>${inlineMarkdownToHtml(line)}</p>`);
  }
  closeList();
  if (interactive && output.at(-1)?.includes('internal-link')) output.push('<p class="after-reference-paragraph"><br></p>');
  return output.join('');
}

function inlineNodeToMarkdown(node) {
  if (node.nodeType === Node.TEXT_NODE) return (node.nodeValue || '').replace(/\u200B/g, '');
  if (node.nodeType !== Node.ELEMENT_NODE) return '';
  const element = node;
  if (element.nodeName === 'SPAN' && element.dataset.documentColorBoundary) return [...element.childNodes].map(inlineNodeToMarkdown).join('').replace(/\u200b/g, '');
  if (element.matches('.internal-link[data-reference-id]')) return `[[${element.dataset.referenceId}]]`;
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
    const color = cssColorToHex(element.getAttribute('color') || element.style.color);
    const background = cssColorToHex(element.style.backgroundColor);
    if (color || background) return `<span style="${color ? `color:${color}` : ''}${color && background ? ';' : ''}${background ? `background-color:${background}` : ''}">${content}</span>`;
  }
  if (element.nodeName === 'SPAN') {
    const color = cssColorToHex(element.style.color);
    const background = cssColorToHex(element.style.backgroundColor);
    if (color || background) return `<span style="${color ? `color:${color}` : ''}${color && background ? ';' : ''}${background ? `background-color:${background}` : ''}">${content}</span>`;
  }
  if (element.nodeName === 'CODE') return `\`${content}\``;
  if (element.nodeName === 'A') return `[${content}](${element.getAttribute('href') || ''})`;
  return content;
}

function cssColorToHex(value = '') {
  const text = String(value).trim();
  if (!text || text.toLowerCase() === 'transparent' || (/^rgba\(/i.test(text) && /[,/]\s*0(?:\.0+)?\s*\)$/.test(text))) return '';
  if (/^#[0-9a-f]{6}$/i.test(text)) return text.toLowerCase();
  if (/^#[0-9a-f]{3}$/i.test(text)) return `#${[...text.slice(1)].map(char => char + char).join('')}`.toLowerCase();
  const rgb = text.match(/^rgba?\(\s*(\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)/i);
  if (!rgb) return '';
  return `#${rgb.slice(1, 4).map(value => Math.max(0, Math.min(255, Number(value))).toString(16).padStart(2, '0')).join('')}`;
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

function editorToMarkdown(editor) {
  const blocks = [];
  editor.childNodes.forEach(node => {
    if (node.nodeName === 'PRE') {
      const code = node.querySelector('code');
      const language = code?.dataset.language || '';
      blocks.push(`\`\`\`${language}\n${codeElementToText(code || node).replace(/\n$/, '')}\n\`\`\``);
      return;
    }
    if (node.nodeName === 'BLOCKQUOTE') {
      const quoteBlocks = [...node.childNodes].filter(child => child.nodeType === Node.ELEMENT_NODE && ['P', 'DIV'].includes(child.nodeName));
      const quoteLines = quoteBlocks.length
        ? quoteBlocks.map(child => inlineNodeToMarkdown(child).trim())
        : [inlineNodeToMarkdown(node).trim()];
      const content = quoteLines.filter(Boolean).map(line => `> ${line}`).join('\n');
      if (content) blocks.push(content);
      return;
    }
    const text = inlineNodeToMarkdown(node).trim();
    if (!text) return;
    if (node.nodeName === 'H1') blocks.push(`# ${text}`);
    else if (node.nodeName === 'H2') blocks.push(`## ${text}`);
    else if (node.nodeName === 'H3') blocks.push(`### ${text}`);
    else if (node.nodeName === 'H4') blocks.push(`#### ${text}`);
    else if (node.nodeName === 'H5') blocks.push(`##### ${text}`);
    else if (node.nodeName === 'H6') blocks.push(`###### ${text}`);
    else if (node.nodeName === 'UL') blocks.push([...node.children].map(item => `${item.classList.contains('task-item') ? `- [${$('input', item)?.checked ? 'x' : ' '}]` : '-'} ${inlineNodeToMarkdown(item).trim()}`).join('\n'));
    else if (node.nodeName === 'OL') blocks.push([...node.children].map((item, index) => `${index + 1}. ${inlineNodeToMarkdown(item).trim()}`).join('\n'));
    else if (node.nodeName === 'DIV' && ['left','center','right'].includes(node.style?.textAlign)) blocks.push(`<div align="${node.style.textAlign}">${text}</div>`);
    else blocks.push(text);
  });
  return blocks.join('\n\n');
}

function selectionInsideEditor(editor = $('.editor')) {
  const selection = window.getSelection();
  return selection?.rangeCount && editor.contains(selection.anchorNode) ? selection : null;
}

function closestEditorBlock(node, editor = $('.editor')) {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  return element?.closest('p, div, h1, h2, h3, h4, h5, h6, pre, blockquote, li') || editor;
}

function restoreLastEditorSelection() {
  if (!lastEditorRange || !$('.editor').contains(lastEditorRange.commonAncestorContainer)) return false;
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(lastEditorRange.cloneRange());
  return true;
}

function placeCaret(node, atStart = true) {
  const range = document.createRange();
  range.selectNodeContents(node);
  range.collapse(atStart);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}

function insertTextAtSelection(text, editor = $('.editor')) {
  const selection = selectionInsideEditor(editor);
  if (!selection) return false;
  const range = selection.getRangeAt(0);
  range.deleteContents();
  const textNode = document.createTextNode(text);
  range.insertNode(textNode);
  range.setStartAfter(textNode);
  range.collapse(true);
  selection.removeAllRanges();
  selection.addRange(range);
  return true;
}

function insertCodeLineBreakAtSelection(editor = $('.editor')) {
  const selection = selectionInsideEditor(editor);
  if (!selection) return false;
  const range = selection.getRangeAt(0);
  range.deleteContents();
  const lineBreak = document.createElement('br');
  const caretAnchor = document.createTextNode('\u200B');
  range.insertNode(lineBreak);
  lineBreak.after(caretAnchor);
  range.setStartAfter(caretAnchor);
  range.collapse(true);
  selection.removeAllRanges();
  selection.addRange(range);
  return true;
}

function isEmptyEditorBlock(node) {
  return !(node.textContent || '').replace(/[\u200B\s]/g, '') && !node.querySelector('img, input, .internal-link');
}

function markEditorChanged() {
  editorDirty = true;
  scheduleEditorSave();
  updateEditorToolbarState();
}

function insertCodeBlock(language = $('#codeLanguage')?.value || 'txt') {
  const editor = $('.editor');
  const selection = selectionInsideEditor(editor);
  const block = selection && closestEditorBlock(selection.anchorNode, editor);
  const pre = document.createElement('pre');
  const code = document.createElement('code');
  code.dataset.language = normalizeCodeLanguage(language);
  code.textContent = (block && block !== editor ? block.textContent : selection?.toString()) || '在这里输入代码';
  pre.appendChild(code);
  if (block && block !== editor) block.replaceWith(pre);
  else editor.appendChild(pre);
  if (!pre.nextElementSibling) pre.insertAdjacentHTML('afterend', '<p><br></p>');
  placeCaret(code, false);
  markEditorChanged();
}

function toggleBlockquote(editor = $('.editor'), onChange = markEditorChanged) {
  const selection = selectionInsideEditor(editor);
  if (!selection) return;
  const block = closestEditorBlock(selection.anchorNode, editor);
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
    placeCaret(last, false);
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
    placeCaret(paragraph, false);
  }
  onChange();
}

function handleQuoteEnter(event, onChange = markEditorChanged) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return false;
  const editor = event.currentTarget;
  const selection = selectionInsideEditor(editor);
  if (!selection) return false;
  const quote = (selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement)?.closest('blockquote');
  if (!quote) return false;
  event.preventDefault();
  if (!selection.isCollapsed) selection.getRangeAt(0).deleteContents();
  let block = closestEditorBlock(selection.anchorNode, editor);
  if (block === quote) {
    const paragraph = document.createElement('p');
    paragraph.append(...quote.childNodes);
    if (!paragraph.childNodes.length) paragraph.innerHTML = '<br>';
    quote.appendChild(paragraph);
    block = paragraph;
    placeCaret(block, false);
  }
  if (isEmptyEditorBlock(block)) {
    const paragraph = document.createElement('p');
    paragraph.innerHTML = '<br>';
    block.remove();
    quote.after(paragraph);
    if (!quote.textContent.trim() && !quote.querySelector('img, input, .internal-link')) quote.remove();
    placeCaret(paragraph);
  } else {
    const range = selection.getRangeAt(0);
    const tailRange = document.createRange();
    tailRange.setStart(range.startContainer, range.startOffset);
    tailRange.setEnd(block, block.childNodes.length);
    const tail = tailRange.extractContents();
    const paragraph = document.createElement('p');
    paragraph.appendChild(tail);
    if (isEmptyEditorBlock(paragraph)) paragraph.innerHTML = '<br>';
    block.after(paragraph);
    placeCaret(paragraph);
  }
  onChange();
  return true;
}

function handleCodeBlockEnter(event, onChange = markEditorChanged) {
  if (event.key !== 'Enter' || event.isComposing) return false;
  const editor = event.currentTarget;
  const selection = selectionInsideEditor(editor);
  if (!selection) return false;
  const element = selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement;
  const pre = element?.closest('pre');
  const code = pre?.querySelector('code');
  if (!pre || !code) return false;
  const range = selection.getRangeAt(0);
  if (!code.contains(range.startContainer) || !code.contains(range.endContainer)) return false;
  event.preventDefault();
  const beforeRange = document.createRange();
  beforeRange.selectNodeContents(code);
  beforeRange.setEnd(range.startContainer, range.startOffset);
  const afterRange = document.createRange();
  afterRange.selectNodeContents(code);
  afterRange.setStart(range.endContainer, range.endOffset);
  const before = codeElementToText(beforeRange.cloneContents());
  const after = codeElementToText(afterRange.cloneContents());
  const shouldExit = (event.ctrlKey || event.metaKey) || (!event.shiftKey && selection.isCollapsed && !after && before.endsWith('\n\n'));
  if (shouldExit) {
    const language = normalizeCodeLanguage(code.dataset.language);
    const content = codeElementToText(code).replace(/\n$/, '');
    code.innerHTML = syntaxHighlightCode(content, language) || '<br>';
    let paragraph = pre.nextElementSibling;
    if (!paragraph || paragraph.nodeName !== 'P' || !isEmptyEditorBlock(paragraph)) {
      paragraph = document.createElement('p');
      paragraph.innerHTML = '<br>';
      pre.after(paragraph);
    }
    placeCaret(paragraph);
  } else {
    insertCodeLineBreakAtSelection(editor);
  }
  onChange();
  return true;
}

function updateEditorToolbarState() {
  const editor = $('.editor');
  if (!editor || !selectionInsideEditor(editor)) return;
  $$('[data-editor-command]', $('.editor-toolbar')).forEach(button => {
    const command = button.dataset.editorCommand;
    const stateful = ['bold', 'italic', 'insertUnorderedList', 'insertOrderedList'].includes(command);
    if (stateful) button.setAttribute('aria-pressed', String(document.queryCommandState(command)));
  });
  const selection = window.getSelection();
  const block = closestEditorBlock(selection.anchorNode, editor);
  const headingLevel = ['H1','H2','H3','H4'].includes(block.nodeName) ? block.nodeName.toLowerCase() : 'p';
  if ($('#editorHeadingLevel')) $('#editorHeadingLevel').value = headingLevel;
  const code = block.nodeName === 'PRE' ? block.querySelector('code') : block.closest?.('pre')?.querySelector('code');
  if (code && [...$('#codeLanguage').options].some(option => option.value === normalizeCodeLanguage(code.dataset.language))) $('#codeLanguage').value = normalizeCodeLanguage(code.dataset.language);
  $$('[data-editor-block]', $('.editor-toolbar')).forEach(button => {
    const tag = button.dataset.editorBlock.toLowerCase();
    const active = tag === 'blockquote' ? Boolean(block.closest?.('blockquote')) : block.nodeName?.toLowerCase() === tag;
    button.setAttribute('aria-pressed', String(active));
  });
}

function readNavigationState() {
  try {
    const value = JSON.parse(localStorage.getItem('workbench-navigation-state') || 'null');
    return value && typeof value === 'object' ? value : {};
  } catch { return {}; }
}

function persistNavigationState() {
  try { localStorage.setItem('workbench-navigation-state', JSON.stringify({page:currentPage, projectId:selectedProjectId, projectTab})); }
  catch { /* 存储受限时仍允许继续导航 */ }
}

function setPage(page, options = {}) {
  const managePages = ['status_templates', 'archive', 'documents', 'timeline', 'tags', 'trash', 'settings'];
  if (!['home', 'project', 'concept_maps', ...managePages].includes(page)) page = 'home';
  if (page === 'project' && !projects.some(project => project.id === selectedProjectId)) page = 'home';
  currentPage = page;
  persistNavigationState();
  if (!options.preserveHash && location.hash) history.replaceState(null, '', `${location.pathname}${location.search}`);
  if (!['tags', 'status_templates', 'settings'].includes(page) || page !== activeManagePage) savedManageSnapshot = null;
  $$('.page').forEach(node => node.classList.remove('active'));
  $$('.nav-item').forEach(node => node.classList.toggle('active', page === 'project' ? node.dataset.projectId === selectedProjectId : node.dataset.page === page));
  if (page === 'home') $('#homePage').classList.add('active');
  else if (page === 'project') {
    $('#projectPage').classList.add('active');
    renderProjectPage();
  } else if (page === 'concept_maps') {
    $('#conceptMapPage').classList.add('active');
    renderConceptMapLibrary().catch(error => notify('概念图加载失败', error.message, true));
  } else if (managePages.includes(page)) {
    $('#managePage').classList.add('active');
    activeManagePage = page;
    renderManagePage(page).catch(error => {
      if (activeManagePage !== page) return;
      const titles = {tags:'标签管理', trash:'回收站'};
      $('#manageEyebrow').textContent = '本地数据连接';
      $('#manageTitle').textContent = titles[page] || '页面加载失败';
      $('#manageDescription').textContent = '页面已经打开，但本地数据服务未能响应。';
      $('#manageActions').innerHTML = '';
      const oldServer = error.message.includes('接口不存在');
      const startHint = location.protocol === 'file:'
        ? '请关闭当前页面，双击 start-workbench.cmd 后再使用工作台。直接双击 index.html 无法读取本地数据。'
        : oldServer
          ? '当前运行的是旧版工作台服务。请重新双击 start-workbench.cmd，它会自动关闭旧服务并启动最新版。'
          : '请确认本地工作台启动窗口仍在运行，然后重试。';
      $('#manageContent').innerHTML = `<div class="empty-state"><strong>数据加载失败</strong><p>${escapeHtml(startHint)}</p><button class="primary-button" data-retry-manage="${escapeHtml(page)}">重新加载</button></div>`;
      notify(`${titles[page] || '页面'}加载失败`, error.message, true);
    });
  } else {
    $('#placeholderTitle').textContent = '页面原型';
    $('#placeholderPage').classList.add('active');
  }
  sidebar.classList.remove('mobile-open');
}

function managePageSnapshot(page = activeManagePage) {
  if (page === 'tags') return JSON.stringify($$('.tag-edit').map(row => ({original:row.dataset.originalName || '', name:$('input[type="text"]', row)?.value || '', color:$('input[type="color"]', row)?.value || ''})));
  if (page === 'status_templates') return JSON.stringify({workflow:selectedWorkflowId, panels:$$('.template-panel').map(panel => ({type:panel.dataset.templateType, statuses:$$('.status-edit-row', panel).map(row => ({id:row.dataset.statusId || '', name:$('input[type="text"]', row)?.value || '', color:$('input[type="color"]', row)?.value || '', completed:Boolean($('.status-completed', row)?.checked)}))}))});
  if (page === 'settings') return JSON.stringify({dataDirectory:$('#dataDirectoryInput')?.value.trim() || ''});
  return null;
}

function captureManageSnapshot(page = activeManagePage) {
  savedManageSnapshot = managePageSnapshot(page);
}

function hasUnsavedManageChanges() {
  return ['tags', 'status_templates', 'settings'].includes(activeManagePage) && savedManageSnapshot !== null && managePageSnapshot() !== savedManageSnapshot;
}

function askUnsavedChanges(pageName = ({tags:'标签管理', status_templates:'状态模板管理', settings:'设置与数据'}[activeManagePage] || '当前页面')) {
  const dialog = $('#unsavedChangesDialog');
  if (unsavedPromptPromise) return unsavedPromptPromise;
  $('#unsavedChangesMessage').textContent = `“${pageName}”还有尚未保存的修改。保存后再离开，可以避免刚才的编辑丢失。`;
  dialog.returnValue = 'cancel';
  dialog.showModal();
  unsavedPromptPromise = new Promise(resolve => dialog.addEventListener('close', () => { const choice = dialog.returnValue || 'cancel'; unsavedPromptPromise = null; resolve(choice); }, {once:true}));
  return unsavedPromptPromise;
}

function currentProjectEditSnapshot() {
  return JSON.stringify({name:$('#projectEditName').value, description:$('#projectEditDescription').value, workflow:$('#projectWorkflow').value});
}

function hasUnsavedProjectEdit() {
  return $('#projectEditDialog').open && projectEditSnapshot !== null && currentProjectEditSnapshot() !== projectEditSnapshot;
}

async function confirmLeaveManagePage() {
  if (!hasUnsavedManageChanges()) return true;
  const choice = await askUnsavedChanges();
  if (choice === 'cancel') return false;
  if (choice === 'discard') { savedManageSnapshot = null; return true; }
  const saved = activeManagePage === 'tags' ? await saveTags() : activeManagePage === 'status_templates' ? await saveTemplates() : await applyDataDirectory();
  return Boolean(saved);
}

function renderNavigation() {
  const activeProjects = projects.filter(project => project.status !== 'archived');
  const manualProjectOrder = (configData?.project_sort?.mode || 'custom') === 'custom';
  $('#projectLinks').innerHTML = activeProjects.map((project, index) => {
    const count = records.filter(record => record.project_id === project.id && !record.completed).length;
    return `<button class="nav-item project-nav-item" draggable="${manualProjectOrder}" data-page="project" data-project-id="${escapeHtml(project.id)}" title="${manualProjectOrder ? '拖动调整项目顺序' : '当前使用自动排序'}"><span class="project-drag-grip" aria-hidden="true">⠿</span><span class="project-dot ${index % 2 ? 'violet' : 'blue'}"></span><b>${escapeHtml(project.name)}</b><em>${count}</em></button>`;
  }).join('');
  $('#projectSortButton').classList.toggle('active', !manualProjectOrder);
  bindProjectNavigationDrag();
  $('#projectSelect').innerHTML = projects.map(project => `<option value="${escapeHtml(project.id)}">${escapeHtml(project.name)}${project.status === 'archived' ? '（已归档）' : ''}</option>`).join('');
  $('.storage-path').textContent = window.workbenchDataDir || 'workbench-data';
}

async function persistProjectOrder() {
  const visible = $$('.project-nav-item', $('#projectLinks')).map(item => item.dataset.projectId);
  const order = [...visible, ...projects.map(project => project.id).filter(id => !visible.includes(id))];
  try {
    configData.project_sort = await api('/project-sort', {method:'PUT', body:JSON.stringify({mode:'custom', order})});
    const positions = new Map(order.map((id, index) => [id, index]));
    projects.sort((a, b) => (positions.get(a.id) ?? 999999) - (positions.get(b.id) ?? 999999));
    notify('项目顺序已保存', '当前使用手动排序');
  } catch (error) { notify('项目顺序保存失败', error.message, true); await refreshData(); }
}

function bindProjectNavigationDrag() {
  const links = $$('.project-nav-item', $('#projectLinks'));
  if ((configData?.project_sort?.mode || 'custom') !== 'custom') return;
  let changed = false;
  links.forEach(link => {
    link.addEventListener('dragstart', event => { draggedProjectLink = link; changed = false; link.classList.add('project-link-dragging'); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', link.dataset.projectId); });
    link.addEventListener('dragover', event => {
      event.preventDefault();
      if (!draggedProjectLink || draggedProjectLink === link) return;
      const rect = link.getBoundingClientRect();
      if (event.clientY < rect.top + rect.height / 2) link.before(draggedProjectLink); else link.after(draggedProjectLink);
      changed = true;
    });
    link.addEventListener('drop', async event => { event.preventDefault(); if (changed) await persistProjectOrder(); changed = false; });
    link.addEventListener('dragend', () => { link.classList.remove('project-link-dragging'); if (changed) persistProjectOrder(); draggedProjectLink = null; changed = false; });
  });
}

function renderDashboard() {
  const todos = records.filter(record => record.type === 'todo' && !record.completed).slice(0, 5);
  $('#todayTodoList').innerHTML = todos.length ? todos.map(record => `<label class="todo-row" data-record-id="${record.id}"><input type="checkbox"><span class="checkmark"></span><span class="todo-content"><strong>${escapeHtml(record.title)}</strong><small><i class="project-dot blue"></i>${escapeHtml(projectName(record.project_id))}</small></span><time>${formatDate(record.due)}</time><span class="priority ${record.priority === '紧急' ? 'urgent' : record.priority === '高' ? 'high' : 'normal'}">${escapeHtml(record.priority)}</span></label>`).join('') : '<div class="empty-state">暂无未完成待办</div>';
  $('#recentList').innerHTML = records.slice(0, 6).map(record => `<button class="activity-row" data-record-id="${record.id}">${typeIcon(record)}<span><strong>${escapeHtml(record.title)}</strong><small>${escapeHtml(projectName(record.project_id))} · ${typeNames[record.type]}</small></span><em class="status-pill blue-pill">${escapeHtml(record.type === 'info' ? '项目信息' : record.status)}</em><time>${new Date(record.updated).toLocaleDateString('zh-CN')}</time></button>`).join('');
  const panel = $('#activeProjectsPanel');
  $$('.project-card', panel).forEach(node => node.remove());
  $('.panel-header', panel).insertAdjacentHTML('afterend', projects.filter(project => project.status !== 'archived').map((project, index) => { const projectRecords = records.filter(item => item.project_id === project.id); const completed = projectRecords.filter(item => item.completed).length; const progress = projectRecords.length ? Math.round(completed / projectRecords.length * 100) : 0; return `<button class="project-card" data-page="project" data-project-id="${escapeHtml(project.id)}"><span class="project-avatar ${index % 2 ? 'violet-bg' : 'blue-bg'}">${escapeHtml(project.name.slice(0,1))}</span><span><strong>${escapeHtml(project.name)}</strong><small>${projectRecords.filter(item=>item.type==='issue').length} 个问题 · ${projectRecords.filter(item=>item.type==='todo'&&!item.completed).length} 个待办</small><i><b style="width:${progress}%"></b></i></span><em>${progress}%</em></button>`; }).join(''));
}

function markdownToPlainText(markdown = '', maxLength = 110, title = '') {
  let text = String(markdown)
    .replace(/```([^\n]*)\n[\s\S]*?```/g, (_, language) => language.trim() ? ` [${normalizeCodeLanguage(language)} 代码块] ` : ' [代码块] ')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\[\[([A-Za-z]+-\d+)\]\]/g, (_, id) => records.find(item => item.id.toLowerCase() === id.toLowerCase())?.title || id.toUpperCase())
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

function cardHtml(record, extraClass = '') {
  const priorityClass = record.priority === '紧急' ? 'urgent' : record.priority === '高' ? 'high' : 'normal';
  const summary = markdownToPlainText(record.body_preview ?? record.body, 110, record.title);
  return `<article class="kanban-card ${extraClass}" draggable="true" data-record-id="${record.id}"><div class="card-top"><span class="priority ${priorityClass}">${escapeHtml(record.priority)}</span><button type="button" class="card-menu-button" data-card-menu="${escapeHtml(record.id)}" aria-label="记录操作" title="记录操作">•••</button></div><h3>${escapeHtml(record.title)}</h3>${summary ? `<p>${escapeHtml(summary)}</p>` : ''}<div class="tag-row">${(record.tags || []).map(projectTagHtml).join('')}</div><footer><span class="${record.due ? 'overdue' : ''}">◷ ${formatDate(record.due)}</span><span>${record.id}</span></footer></article>`;
}

function recordSortKeys(tab = projectTab) {
  return {
    issues:{sort:'issue_record_sort', order:'issue_record_order', statusSorts:'issue_status_record_sorts'},
    todos:{sort:'todo_record_sort', order:'todo_record_order', statusSorts:'todo_status_record_sorts'},
    infos:{sort:'info_record_sort', order:'info_record_order', statusSorts:null},
    mixed:{sort:'mixed_record_sort', order:'mixed_record_order', statusSorts:'mixed_status_record_sorts'},
  }[tab] || null;
}

function sortRecordsByMode(items, mode, savedOrder = []) {
  const originalIndex = new Map(items.map((item, index) => [item.id, index]));
  const priorityRank = {紧急:0, 高:1, 普通:2, 低:3};
  const time = value => { const parsed = Date.parse(value || ''); return Number.isNaN(parsed) ? 0 : parsed; };
  return [...items].sort((a, b) => {
    if (mode === 'manual') {
      const ai = savedOrder.indexOf(a.id), bi = savedOrder.indexOf(b.id);
      return (ai < 0 ? savedOrder.length + originalIndex.get(a.id) : ai) - (bi < 0 ? savedOrder.length + originalIndex.get(b.id) : bi);
    }
    if (mode === 'updated') return time(b.updated) - time(a.updated);
    if (mode === 'priority') return (priorityRank[a.priority] ?? 9) - (priorityRank[b.priority] ?? 9) || time(b.updated) - time(a.updated);
    if (mode === 'due') return (a.due ? time(a.due) : Number.MAX_SAFE_INTEGER) - (b.due ? time(b.due) : Number.MAX_SAFE_INTEGER) || time(b.updated) - time(a.updated);
    if (mode === 'title') return String(a.title || '').localeCompare(String(b.title || ''), 'zh-CN');
    if (mode === 'created') return time(b.created) - time(a.created);
    return 0;
  });
}

function sortProjectRecords(items, project) {
  const keys = recordSortKeys();
  return keys ? sortRecordsByMode(items, project[keys.sort] || 'manual', Array.isArray(project[keys.order]) ? project[keys.order] : []) : items;
}

function formatFileSize(bytes = 0) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
}

function assetIcon(mime = '', name = '') {
  if (mime.startsWith('image/')) return '▧';
  if (mime.startsWith('audio/') || mime.startsWith('video/')) return '▶';
  if (/zip|rar|7z|tar|gzip/i.test(`${mime} ${name}`)) return '▦';
  if (/pdf|word|text|sheet|excel|presentation/i.test(mime)) return '▤';
  return '◇';
}

function recordAttachmentItems(projectRecords) {
  return projectRecords.flatMap(record => (record.attachments || []).map(raw => {
    try { const item = typeof raw === 'string' ? JSON.parse(raw) : raw; return {source:'record', record, item, category:item.category || ''}; }
    catch { return null; }
  }).filter(Boolean));
}

async function loadProjectAssets(projectId, {force = false} = {}) {
  if (!force && projectAssetProjectId === projectId) return projectAssetLibrary;
  projectAssetProjectId = projectId;
  try {
    [projectAssetLibrary, projectAssetCategories] = await Promise.all([
      api(`/projects/${encodeURIComponent(projectId)}/assets`),
      api(`/projects/${encodeURIComponent(projectId)}/asset-categories`),
    ]);
  }
  catch (error) { projectAssetLibrary = []; projectAssetCategories = []; notify('无法读取项目附件', error.message, true); }
  return projectAssetLibrary;
}

function assetCategoryMeta(name) {
  return projectAssetCategories.find(item => item.name === name) || {name:name || '无分类', tag:''};
}

function assetCategoryColor(name) {
  const linkedTag = assetCategoryMeta(name).tag;
  return safeColor((configData?.tags || []).find(tag => tag.name === linkedTag)?.color, '#64748b');
}

function assetSelectionAttributes(entry) {
  if (entry.source === 'project') return `data-asset-source="project" data-asset-id="${escapeHtml(entry.item.id)}"`;
  return `data-asset-source="record" data-record-id="${escapeHtml(entry.record.id)}" data-asset-name="${escapeHtml(entry.item.name)}"`;
}

function assetCategoryRowHtml(category = null) {
  const tagOptions = [`<option value="">不关联标签</option>`, ...(configData?.tags || []).map(tag => `<option value="${escapeHtml(tag.name)}" ${tag.name === category?.tag ? 'selected' : ''}>${escapeHtml(tag.name)}</option>`)].join('');
  return `<div class="asset-category-editor-row" data-asset-category-row ${category ? `data-category-name="${escapeHtml(category.name)}"` : 'data-new-category="true"'}><span class="asset-category-color" style="--asset-category-color:${category ? assetCategoryColor(category.name) : '#64748b'}"></span>${category ? `<strong>${escapeHtml(category.name)}</strong>` : '<input class="asset-new-category-name" placeholder="输入分类名称" maxlength="40">'}<label><span>关联标签</span><select class="asset-category-tag">${tagOptions}</select></label><button type="button" class="icon-button remove-asset-category" aria-label="删除分类" title="删除分类">×</button></div>`;
}

function openAssetCategoryManager() {
  $('#assetCategoryEditor').innerHTML = projectAssetCategories.length ? projectAssetCategories.map(assetCategoryRowHtml).join('') : '<div class="empty-state asset-category-empty">还没有分类，可以创建第一个分类。</div>';
  $('#assetCategoryDialog').showModal();
}

async function saveAssetCategories() {
  const categories = $$('[data-asset-category-row]', $('#assetCategoryEditor')).map(row => ({
    name:row.dataset.categoryName || $('.asset-new-category-name', row)?.value.trim() || '',
    tag:$('.asset-category-tag', row)?.value || '',
  })).filter(item => item.name);
  const button = $('#saveAssetCategories'); button.disabled = true; button.textContent = '正在保存…';
  try {
    projectAssetCategories = await api(`/projects/${encodeURIComponent(selectedProjectId)}/asset-categories`, {method:'PUT', body:JSON.stringify({categories})});
    $('#assetCategoryDialog').close();
    await refreshData(); await loadProjectAssets(selectedProjectId, {force:true}); renderProjectPage();
    notify('附件分类已保存', `当前共有 ${projectAssetCategories.length} 个分类`);
    return true;
  } catch (error) { notify('分类保存失败', error.message, true); return false; }
  finally { button.disabled = false; button.textContent = '保存分类'; }
}

function updateAssetBatchToolbar() {
  const selected = selectedAssetPayloads();
  const count = selected.length;
  const label = $('#assetSelectionCount'); if (label) label.textContent = count ? `已选择 ${count} 个附件` : '尚未选择附件';
  ['#batchAssetCategory','#applyBatchAssetCategory','#deleteSelectedAssets'].forEach(selector => { const element = $(selector); if (element) element.disabled = !count; });
  const all = $$('.project-asset-select');
  const selectAll = $('#selectAllProjectAssets');
  if (selectAll) { selectAll.checked = Boolean(all.length) && all.every(input => input.checked); selectAll.indeterminate = count > 0 && count < all.length; }
}

async function reloadProjectAssetPage() {
  await refreshData();
  await loadProjectAssets(selectedProjectId, {force:true});
  if (projectTab === 'assets') renderProjectPage();
}

async function applyAssetCategory(selections, category) {
  const normalized = category === '__uncategorized__' ? '' : category;
  const result = await api('/assets/batch', {method:'PATCH', body:JSON.stringify({project_id:selectedProjectId, selections, category:normalized})});
  await reloadProjectAssetPage();
  notify('附件分类已更新', `${result.updated} 个附件 → ${normalized || '无分类'}`);
}

async function deleteAssetsWithConfirmation(selections) {
  if (!selections.length) return false;
  const confirmed = await appConfirm({title:selections.length > 1 ? `删除所选 ${selections.length} 个附件？` : '删除这个附件？', message:'附件文件将从项目目录中永久删除。', detail:'记录附件对应的 Markdown 引用也会同步移除，此操作无法从回收站恢复。', confirmText:'确认删除', danger:true});
  if (!confirmed) return false;
  try {
    const result = await api('/assets/batch', {method:'DELETE', body:JSON.stringify({project_id:selectedProjectId, selections})});
    await reloadProjectAssetPage(); notify(`已删除 ${result.deleted} 个附件`, '附件文件和关联信息已同步更新'); return true;
  } catch (error) { notify('附件删除失败', error.message, true); return false; }
}

function selectedAssetPayloads() {
  return $$('.project-asset-select:checked').map(assetPayloadFromInput);
}

function assetPayloadFromInput(input) {
  return input.dataset.assetSource === 'project'
    ? {source:'project', id:input.dataset.assetId}
    : {source:'record', record_id:input.dataset.recordId, name:input.dataset.assetName};
}

function projectAssetCardHtml(entry, categories) {
  const item = entry.item;
  const category = entry.category || '';
  const color = assetCategoryColor(category);
  const options = [`<option value="" ${!category ? 'selected' : ''}>无分类</option>`, ...categories.map(meta => `<option value="${escapeHtml(meta.name)}" ${meta.name === category ? 'selected' : ''}>${escapeHtml(meta.name)}</option>`)].join('');
  const checkbox = `<input type="checkbox" class="project-asset-select" ${assetSelectionAttributes(entry)} aria-label="选择附件 ${escapeHtml(item.name)}">`;
  if (entry.source === 'project') {
    return `<article class="project-asset-card" data-project-asset-id="${escapeHtml(item.id)}" style="--asset-category-color:${color}">${checkbox}<div class="project-asset-icon">${assetIcon(item.mime, item.name)}</div><div class="project-asset-main"><strong title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</strong><div class="project-asset-meta"><span>项目附件</span><span>${formatFileSize(item.size)}</span><span title="${escapeHtml(item.mime || '未知类型')}">${escapeHtml(item.mime || '未知类型')}</span></div></div><select class="asset-category-select" data-project-asset-category="${escapeHtml(item.id)}" aria-label="附件分类">${options}<option value="__custom__">＋ 新建分类…</option></select><div class="asset-card-actions"><button type="button" class="secondary-button asset-open-button" data-open-project-asset="${escapeHtml(item.id)}">打开</button><button type="button" class="icon-button asset-delete-button" data-delete-single-asset aria-label="删除附件" title="删除附件">×</button></div></article>`;
  }
  return `<article class="project-asset-card record-source" data-record-id="${escapeHtml(entry.record.id)}" style="--asset-category-color:${color}">${checkbox}<div class="project-asset-icon">${assetIcon(item.mime, item.name)}</div><div class="project-asset-main"><strong title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</strong><div class="project-asset-meta"><span>记录附件</span><span>${formatFileSize(item.size)}</span><span title="${escapeHtml(entry.record.title)}">来自：${escapeHtml(entry.record.title)}</span></div></div><select class="asset-category-select" data-record-asset-category="${escapeHtml(entry.record.id)}" data-record-asset-name="${escapeHtml(item.name)}" aria-label="附件分类">${options}<option value="__custom__">＋ 新建分类…</option></select><div class="asset-card-actions"><button type="button" class="secondary-button asset-open-button" data-open-record-asset="${escapeHtml(entry.record.id)}" data-record-asset-name="${escapeHtml(item.name)}">打开</button><button type="button" class="icon-button asset-delete-button" data-delete-single-asset aria-label="删除附件" title="删除附件">×</button></div></article>`;
}

function renderProjectAssets(project, projectRecords) {
  const content = $('#kanban');
  const independent = projectAssetLibrary.map(item => ({source:'project', item, category:item.category || ''}));
  const recordItems = recordAttachmentItems(projectRecords);
  const allItems = [...independent, ...recordItems];
  const categories = projectAssetCategories;
  const query = projectAssetSearch.trim().toLocaleLowerCase('zh-CN');
  const visible = allItems.filter(entry => ((!projectAssetCategoryFilter || entry.category === projectAssetCategoryFilter) || (projectAssetCategoryFilter === '__uncategorized__' && !entry.category)) && (!query || `${entry.item.name} ${entry.category} ${entry.record?.title || ''}`.toLocaleLowerCase('zh-CN').includes(query)));
  const totalSize = allItems.reduce((sum, entry) => sum + Number(entry.item.size || 0), 0);
  const categoryOptions = categories.map(meta => `<option value="${escapeHtml(meta.name)}">${escapeHtml(meta.name)}</option>`).join('');
  const grouped = new Map();
  visible.forEach(entry => { const name = entry.category || ''; if (!grouped.has(name)) grouped.set(name, []); grouped.get(name).push(entry); });
  const groups = [...grouped.entries()].map(([name, items]) => {
    const label = name || '无分类';
    const meta = assetCategoryMeta(name);
    const color = assetCategoryColor(name);
    const size = items.reduce((sum, entry) => sum + Number(entry.item.size || 0), 0);
    return `<details class="project-asset-group" open style="--asset-category-color:${color}"><summary><span class="asset-group-chevron">›</span><i></i><strong>${escapeHtml(label)}</strong>${meta.tag ? `<em>关联标签：${escapeHtml(meta.tag)}</em>` : ''}<small>${items.length} 个 · ${formatFileSize(size)}</small></summary><div class="project-assets-list">${items.map(entry => projectAssetCardHtml(entry, categories)).join('')}</div></details>`;
  }).join('');
  content.innerHTML = `<section class="project-assets-page"><header class="project-assets-summary"><div><p class="eyebrow">项目文件库</p><h2>附件与资料</h2><p>附件按分类集中收纳，分类可以关联工作台标签。</p></div><div class="project-assets-stats"><span><strong>${allItems.length}</strong>全部附件</span><span><strong>${independent.length}</strong>项目附件</span><span><strong>${recordItems.length}</strong>记录附件</span><span><strong>${formatFileSize(totalSize)}</strong>总大小</span></div></header><div class="project-assets-toolbar"><label class="asset-search"><span>⌕</span><input id="projectAssetSearch" value="${escapeHtml(projectAssetSearch)}" placeholder="搜索附件名称或所属记录"></label><select id="projectAssetCategoryFilter"><option value="">全部分类</option><option value="" disabled>────────</option>${categories.map(meta => `<option value="${escapeHtml(meta.name)}" ${meta.name === projectAssetCategoryFilter ? 'selected' : ''}>${escapeHtml(meta.name)}</option>`).join('')}<option value="__uncategorized__" ${projectAssetCategoryFilter === '__uncategorized__' ? 'selected' : ''}>无分类</option></select><button type="button" class="secondary-button" id="manageAssetCategories">管理分类</button><span class="toolbar-spacer"></span><label class="asset-upload-category"><span>上传到</span><input id="projectAssetUploadCategory" value="" list="projectAssetCategorySuggestions" placeholder="可不分类"><datalist id="projectAssetCategorySuggestions">${categoryOptions}</datalist></label><button type="button" class="primary-button" id="uploadProjectAsset">＋ 上传附件</button><input type="file" id="projectAssetInput" multiple hidden></div><div class="asset-batch-toolbar"><label><input type="checkbox" id="selectAllProjectAssets"> 全选当前结果</label><span id="assetSelectionCount">尚未选择附件</span><select id="batchAssetCategory" disabled><option value="">批量设置分类</option>${categoryOptions}<option value="__uncategorized__">设为无分类</option></select><button type="button" class="secondary-button" id="applyBatchAssetCategory" disabled>应用分类</button><button type="button" class="secondary-button danger-button" id="deleteSelectedAssets" disabled>删除所选</button></div><div class="project-assets-result"><span>显示 ${visible.length} / ${allItems.length} 个附件</span>${projectAssetCategoryFilter || projectAssetSearch ? '<button type="button" id="clearProjectAssetFilters">清除筛选</button>' : ''}</div><div class="project-asset-groups">${groups || '<div class="empty-state asset-empty-state">没有符合条件的附件。可以上传附件，或清除当前筛选。</div>'}</div></section>`;
}

function renderProjectPage() {
  const firstActive = projects.find(item => item.status !== 'archived') || projects[0];
  if (!selectedProjectId && firstActive) selectedProjectId = firstActive.id;
  const project = projects.find(item => item.id === selectedProjectId);
  if (!project) return;
  $('#projectPage').dataset.projectId = project.id;
  $('.project-heading .breadcrumb span:last-child').textContent = project.name;
  $('.project-heading .title-with-avatar h1').textContent = project.name;
  $('.project-heading .title-with-avatar .project-avatar').textContent = project.name.slice(0, 1);
  $('.project-heading .title-with-avatar .status-pill').textContent = project.status === 'archived' ? '已归档' : project.status === 'paused' ? '已暂停' : '进行中';
  $('.project-title-row p').textContent = project.description || '暂无项目描述';
  $('#archiveProject').textContent = project.status === 'archived' ? '恢复项目' : '归档项目';
  const allProjectRecords = records.filter(record => record.project_id === project.id);
  const counts = {issues:allProjectRecords.filter(item => item.type === 'issue').length, todos:allProjectRecords.filter(item => item.type === 'todo').length, infos:allProjectRecords.filter(item => item.type === 'info').length};
  $$('.tabs [data-project-tab]').forEach(button => {
    button.classList.toggle('active', button.dataset.projectTab === projectTab);
    const count = button.querySelector('span'); if (count && counts[button.dataset.projectTab] !== undefined) count.textContent = counts[button.dataset.projectTab];
  });
  const typeForTab = {issues:'issue', todos:'todo', infos:'info'};
  let projectRecords = typeForTab[projectTab] ? allProjectRecords.filter(item => item.type === typeForTab[projectTab]) : allProjectRecords;
  if (projectTab === 'mixed') projectRecords = projectRecords.filter(item => item.type !== 'info');
  const toolbar = $('.board-toolbar');
  toolbar.style.display = ['overview', 'assets'].includes(projectTab) ? 'none' : 'flex';
  $$('.view-switch [data-view-mode]').forEach(button => button.classList.toggle('active', button.dataset.viewMode === projectViewMode));
  const createLabel = projectTab === 'todos' ? '待办' : projectTab === 'infos' ? '信息' : '问题';
  const createButton = $('.board-toolbar [data-create-type]');
  if (createButton) { createButton.dataset.createType = createLabel; createButton.textContent = `＋ 新建${createLabel}`; }
  const rawStatuses = [...new Set(projectRecords.map(item => item.status).filter(Boolean))];
  const rawTags = [...new Set(projectRecords.flatMap(item => item.tags || []))];
  $('#filterStatus').innerHTML = `<option value="">状态：全部</option>${rawStatuses.map(value => `<option ${value === projectFilters.status ? 'selected' : ''}>${escapeHtml(value)}</option>`).join('')}`;
  $('#filterTag').innerHTML = `<option value="">标签：全部</option>${rawTags.map(value => `<option ${value === projectFilters.tag ? 'selected' : ''}>${escapeHtml(value)}</option>`).join('')}`;
  $('#filterPriority').value = projectFilters.priority;
  $('#filterStatus').style.display = projectTab === 'infos' ? 'none' : '';
  $('#filterPriority').style.display = projectTab === 'infos' ? 'none' : '';
  $('.view-switch').style.display = projectTab === 'infos' ? 'none' : 'flex';
  projectRecords = projectRecords.filter(item => (projectTab === 'infos' || !projectFilters.status || item.status === projectFilters.status) && (!projectFilters.tag || (item.tags || []).includes(projectFilters.tag)) && (projectTab === 'infos' || !projectFilters.priority || item.priority === projectFilters.priority));
  projectRecords = sortProjectRecords(projectRecords, project);
  const recordKeys = recordSortKeys();
  const recordSortMode = recordKeys ? (project[recordKeys.sort] || 'manual') : 'manual';
  const recordSortButton = $('#recordSortButton');
  if (recordSortButton) {
    recordSortButton.style.display = projectTab === 'infos' ? 'none' : '';
    recordSortButton.classList.toggle('active', recordSortMode !== 'manual');
    recordSortButton.title = `记录排序：${{manual:'手动排序',updated:'最近更新优先',priority:'优先级',due:'截止日期',title:'标题',created:'最新创建优先'}[recordSortMode] || '手动排序'}`;
  }
  const content = $('#kanban');
  content.classList.toggle('list-layout', projectViewMode === 'list' || ['overview', 'assets', 'infos'].includes(projectTab));
  if (projectTab === 'overview') {
    content.innerHTML = `<div class="stat-grid"><div class="stat-card"><strong>${counts.issues}</strong><span>问题</span></div><div class="stat-card"><strong>${counts.todos}</strong><span>待办</span></div><div class="stat-card"><strong>${counts.infos}</strong><span>信息</span></div><div class="stat-card"><strong>${allProjectRecords.filter(item => item.completed).length}</strong><span>已完成</span></div></div>`;
    return;
  }
  if (projectTab === 'assets') {
    if (projectAssetProjectId !== project.id) {
      content.innerHTML = '<div class="empty-state">正在读取项目附件…</div>';
      loadProjectAssets(project.id).then(() => { if (selectedProjectId === project.id && projectTab === 'assets') renderProjectPage(); });
      return;
    }
    renderProjectAssets(project, allProjectRecords);
    return;
  }
  if (projectTab === 'infos') {
    const hasMore = projectRecords.length > PROJECT_LIST_COLLAPSE_LIMIT;
    const indexedRecords = projectRecords.map((record, index) => ({record, index}));
    const cardLayout = projectRecords.length ? `<div class="info-card-column" data-info-card-column>${indexedRecords.filter(item => item.index % 2 === 0).map(item => infoCardHtml(item.record, item.index)).join('')}</div><div class="info-card-column" data-info-card-column>${indexedRecords.filter(item => item.index % 2 === 1).map(item => infoCardHtml(item.record, item.index)).join('')}</div>` : '<div class="empty-state info-card-empty-state">这个项目还没有信息，点击右上角“新建信息”开始记录。</div>';
    content.innerHTML = `<section class="info-card-section"><div class="info-card-grid">${cardLayout}</div>${hasMore ? `<button type="button" class="records-expand-toggle" aria-expanded="false">展开其余 ${projectRecords.length - PROJECT_LIST_COLLAPSE_LIMIT} 条信息⌄</button>` : ''}</section>`;
    bindInfoCardDragAndDrop();
    return;
  }
  if (projectViewMode === 'list') {
    const hasMore = projectRecords.length > PROJECT_LIST_COLLAPSE_LIMIT;
    content.innerHTML = `<div class="collapsible-record-list"><table class="data-table"><thead><tr><th>类型</th><th>标题</th><th>状态</th><th>优先级</th><th>截止日期</th><th>标签</th></tr></thead><tbody>${projectRecords.map((record, index) => `<tr class="${index >= PROJECT_LIST_COLLAPSE_LIMIT ? 'auto-collapsed-record' : ''}" data-record-id="${record.id}"><td>${typeChipHtml(record)}</td><td><strong>${escapeHtml(record.title)}</strong></td><td>${statusChipHtml(record)}</td><td>${priorityChipHtml(record.priority)}</td><td>${formatDate(record.due)}</td><td><div class="tag-row">${(record.tags || []).map(projectTagHtml).join('')}</div></td></tr>`).join('')}</tbody></table>${hasMore ? `<button type="button" class="records-expand-toggle" aria-expanded="false">展开其余 ${projectRecords.length - PROJECT_LIST_COLLAPSE_LIMIT} 条记录⌄</button>` : ''}</div>`;
    return;
  }
  let statuses;
  if (projectTab === 'mixed') {
    statuses = [...new Set(projectRecords.map(item => item.status))].map((name, index) => ({name, color:['#87919e','#4d78e8','#e08b38','#2ba477','#7856c8'][index % 5]}));
  } else {
    const configuredStatuses = statusesFor(typeForTab[projectTab], project.id);
    const configuredNames = new Set(configuredStatuses.map(item => item.name));
    const unconfiguredStatuses = rawStatuses.filter(name => !configuredNames.has(name)).map(name => ({name, color:'#64748b', unconfigured:true}));
    statuses = [...configuredStatuses, ...unconfiguredStatuses];
  }
  const orderKey = {issues:'issue_status_order', todos:'todo_status_order', mixed:'mixed_status_order'}[projectTab];
  const savedOrder = orderKey && Array.isArray(project[orderKey]) ? project[orderKey] : [];
  if (savedOrder.length) statuses = [...statuses].sort((a, b) => { const ai = savedOrder.indexOf(a.name), bi = savedOrder.indexOf(b.name); return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi); });
  content.dataset.orderKey = orderKey || '';
  content.dataset.recordSortKey = recordKeys?.sort || '';
  content.dataset.recordOrderKey = recordKeys?.order || '';
  content.dataset.statusRecordSortsKey = recordKeys?.statusSorts || '';
  content.dataset.recordSortMode = recordSortMode;
  const statusSorts = recordKeys && project[recordKeys.statusSorts] && typeof project[recordKeys.statusSorts] === 'object' ? project[recordKeys.statusSorts] : {};
  const sortLabels = {manual:'手动',updated:'最近更新',priority:'优先级',due:'截止日期',title:'标题',created:'最新创建'};
  content.innerHTML = statuses.map(status => {
    const statusMode = statusSorts[status.name] || recordSortMode;
    const group = sortRecordsByMode(projectRecords.filter(record => record.status === status.name), statusMode, recordKeys && Array.isArray(project[recordKeys.order]) ? project[recordKeys.order] : []);
    const indicator = status.unconfigured ? '<span class="unconfigured-status-badge" title="此状态已不在当前模板中；记录仍被完整保留，可移动到其他状态">模板外</span>' : statusMode !== 'manual' ? `<span class="column-sort-indicator" title="当前按${sortLabels[statusMode]}排序">↕ ${sortLabels[statusMode]}</span>` : '';
    const color = safeColor(status.color);
    const hiddenCount = Math.max(0, group.length - PROJECT_CARD_COLLAPSE_LIMIT);
    const cards = group.map((record, index) => cardHtml(record, index >= PROJECT_CARD_COLLAPSE_LIMIT ? 'auto-collapsed-record' : '')).join('');
    return `<section class="kanban-column ${status.unconfigured ? 'unconfigured-status-column' : ''}" style="--status-color:${color}" data-status="${escapeHtml(status.name)}" data-completed="${Boolean(status.completed)}" data-record-sort-mode="${statusMode}"><header draggable="${!status.unconfigured}" title="${status.unconfigured ? '此状态已从模板移除，但其中记录仍被保留' : '拖动调整状态顺序'}"><span class="column-grip" aria-hidden="true">${status.unconfigured ? '!' : '⠿'}</span><span class="column-dot" style="background:${color}"></span><strong>${escapeHtml(status.name)}</strong><em>${group.length}</em>${indicator}<button type="button" draggable="false" class="column-menu-button" data-column-menu="${escapeHtml(status.name)}" aria-label="状态操作与排序" title="状态操作与排序">•••</button></header><div class="card-stack">${cards}</div>${hiddenCount ? `<button type="button" class="records-expand-toggle" aria-expanded="false">展开其余 ${hiddenCount} 条记录⌄</button>` : ''}${status.unconfigured ? '<div class="unconfigured-status-help">记录未被删除，请移动到现有状态</div>' : `<button class="add-card" data-create-type="${createLabel}">＋ 添加${createLabel}</button>`}</section>`;
  }).join('');
  bindDragAndDrop();
}

function showOverlay() { overlay.classList.add('visible'); }
function hideOverlayIfClear() {
  if (!searchPanel.classList.contains('visible') && !detailDrawer.classList.contains('visible') && !createDialog.open) overlay.classList.remove('visible');
}

function renderCreateStatusOptions(preferredStatus = '') {
  const field = $('#createStatusField');
  if (selectedType === '项目' || selectedType === '信息') { field.style.display = 'none'; return; }
  field.style.display = 'flex';
  const recordType = typeMap[selectedType];
  const projectId = $('#projectSelect').value || null;
  const fallback = {issue:['待处理'], todo:['待办']}[recordType] || [];
  const statuses = statusesFor(recordType, projectId);
  const options = statuses.length ? statuses : fallback.map(name => ({name, completed:false}));
  $('#createStatus').innerHTML = options.map(status => `<option value="${escapeHtml(status.name)}" data-completed="${Boolean(status.completed)}">${escapeHtml(status.name)}</option>`).join('');
  if (preferredStatus && options.some(status => status.name === preferredStatus)) $('#createStatus').value = preferredStatus;
}

function updateCreateFormForType() {
  const isProject = selectedType === '项目';
  const isInfo = selectedType === '信息';
  $('#createInfoFields').style.display = isInfo ? 'block' : 'none';
  $('#createPriorityField').style.display = isProject || isInfo ? 'none' : 'flex';
  $('#createBodyField span').textContent = isInfo ? '补充说明（可选）' : '补充说明（可选）';
  $('#createTitle').placeholder = isProject ? '输入项目名称' : isInfo ? '输入信息名称，如：生产环境配置' : '用一句话描述这条记录';
  if (isInfo && !$('#createInfoFieldList').children.length) renderCreateInfoFields();
}

function openCreate(type = '问题', options = {}) {
  selectedType = type;
  const isProject = type === '项目';
  const inProjectPage = $('#projectPage').classList.contains('active');
  createContext = {
    projectId: options.projectId || (inProjectPage ? selectedProjectId : ''),
    status: options.status || '',
  };
  $('.type-picker').style.display = isProject ? 'none' : 'grid';
  $$('.type-picker button').forEach(button => button.classList.toggle('active', button.dataset.type === selectedType));
  $('#projectSelect').closest('label').style.display = isProject ? 'none' : 'flex';
  $('#projectSelect').closest('label').style.opacity = '1';
  $('.create-dialog h2').textContent = isProject ? '新建项目' : '新建记录';
  updateCreateFormForType();
  renderNavigation();
  if (createContext.projectId && projects.some(project => project.id === createContext.projectId)) $('#projectSelect').value = createContext.projectId;
  renderCreateStatusOptions(createContext.status);
  createDialog.showModal();
  setTimeout(() => $('#createTitle').focus(), 60);
}

function closeSearch() {
  searchPanel.classList.remove('visible');
  searchPanel.setAttribute('aria-hidden', 'true');
  hideOverlayIfClear();
}
function updateSearchClearButton() {
  $('#clearSearchInput').hidden = !$('#searchInput').value;
}
function openSearch() { showOverlay(); searchPanel.classList.add('visible'); searchPanel.setAttribute('aria-hidden', 'false'); updateSearchClearButton(); if (apiAvailable) api(`/search?q=${encodeURIComponent($('#searchInput').value)}`).then(renderSearchResults); setTimeout(() => $('#searchInput').focus(), 50); }

function updateExternalEditorButton() {
  const name = externalEditorData?.selected_name || '外部编辑器';
  $('#externalEditorButtonLabel').textContent = `${name} 打开`;
  $('#openExternalEditor').title = `使用 ${name} 打开当前 Markdown`;
  if ($('#documentExternalEditorLabel')) $('#documentExternalEditorLabel').textContent = `${name} 打开`;
  if ($('#openDocumentExternal')) $('#openDocumentExternal').title = `使用 ${name} 打开当前知识库 Markdown`;
}

async function loadExternalEditors() {
  externalEditorData = await api('/external-editors');
  updateExternalEditorButton();
  return externalEditorData;
}

function renderExternalEditorOptions() {
  const editors = [...(externalEditorData?.editors || [])];
  if (!editors.some(editor => editor.id === 'custom')) editors.push({id:'custom', name:'自定义编辑器', path:'', kind:'custom'});
  const selected = externalEditorData?.selected || 'system';
  $('#externalEditorOptions').innerHTML = editors.map(editor => `<label class="external-editor-option ${editor.id === selected ? 'selected' : ''}"><input type="radio" name="externalEditor" value="${escapeHtml(editor.id)}" ${editor.id === selected ? 'checked' : ''}><span class="external-editor-icon">${editor.kind === 'system' ? 'OS' : editor.id === 'custom' ? '＋' : escapeHtml(editor.name.slice(0, 1).toUpperCase())}</span><span><strong>${escapeHtml(editor.name)}</strong><small>${escapeHtml(editor.path || '使用操作系统中的 Markdown 默认程序')}</small></span></label>`).join('');
  const custom = editors.find(editor => editor.id === 'custom');
  $('#customEditorPath').value = custom?.path || '';
  $('#customEditorPathField').classList.toggle('visible', selected === 'custom');
}

async function openExternalEditorDialog() {
  try {
    try { await loadExternalEditors(); }
    catch { externalEditorData = {selected:'system', selected_name:'外部编辑器', editors:[]}; updateExternalEditorButton(); }
    renderExternalEditorOptions();
    $('#externalEditorDialog').showModal();
  } catch (error) { notify('无法读取外部编辑器', error.message, true); }
}

async function openDrawer(recordId, options = {}) {
  if (!recordId || !apiAvailable) return;
  try {
    if (options.fromReference && currentRecord?.id && currentRecord.id !== recordId) recordNavigationStack.push(currentRecord.id);
    else if (!detailDrawer.classList.contains('visible')) {
      recordNavigationStack = [];
      if (!options.fromUsage) usageReturnContext = null;
    }
    currentRecord = await api(`/records/${encodeURIComponent(recordId)}`);
    editorDirty = false;
    editorContentExpanded = false;
    $('.editor-area').classList.remove('content-collapsed');
    const recoveryDraft = readEditorDraft(currentRecord.id);
    if (recoveryDraft && (recoveryDraft.body !== currentRecord.body || recoveryDraft.title !== currentRecord.title || (currentRecord.type === 'info' && (JSON.stringify(recoveryDraft.info_fields || []) !== JSON.stringify(currentRecord.info_fields || []) || recoveryDraft.info_color !== currentRecord.info_color)))) {
      currentRecord.body = recoveryDraft.body;
      currentRecord.title = recoveryDraft.title || currentRecord.title;
      if (currentRecord.type === 'info' && Array.isArray(recoveryDraft.info_fields)) {
        currentRecord.info_fields = recoveryDraft.info_fields;
        currentRecord.info_color = recoveryDraft.info_color || currentRecord.info_color;
      }
      editorDirty = true;
    } else if (recoveryDraft) clearEditorDraft(currentRecord.id);
    $('#drawerRecordId').textContent = currentRecord.id;
    $('#drawerRecordId').dataset.recordId = currentRecord.id;
    $('.detail-drawer .type-icon').className = `type-icon ${currentRecord.type}`;
    $('.detail-drawer .type-icon').textContent = typeIcons[currentRecord.type];
    updateRecordBackButton();
    $('.drawer-title').value = currentRecord.title;
    const isInfo = currentRecord.type === 'info';
    detailDrawer.classList.toggle('info-record', isInfo);
    $('#infoFieldsPanel').style.display = isInfo ? 'block' : 'none';
    if (isInfo) {
      renderDrawerInfoFields(currentRecord.info_fields || []);
      $('#infoColorPicker').innerHTML = colorPickerHtml(currentRecord.info_color || '#35a99a', '信息卡色条颜色');
    }
    else {
      const statusList = statusesFor(currentRecord.type, currentRecord.project_id);
      const statusNames = [...new Set([...statusList.map(item => item.name), currentRecord.status])];
      $('#drawerStatus').innerHTML = statusNames.map(name => `<option ${name === currentRecord.status ? 'selected' : ''}>${escapeHtml(name)}</option>`).join('');
      $('#drawerPriority').value = currentRecord.priority;
    }
    $('#drawerProject').textContent = projectName(currentRecord.project_id);
    $('#drawerDue').value = (currentRecord.due || '').slice(0, 10);
    $('#drawerTags').innerHTML = `${(currentRecord.tags || []).map(drawerTagHtml).join('')}<button id="addRecordTag">＋ 添加标签</button>`;
    $('.editor').innerHTML = markdownToHtml(currentRecord.body, true);
    $('.markdown-source').value = currentRecord.body;
    $('.markdown-preview').innerHTML = markdownToHtml(currentRecord.body);
    setEditorMode(editorMode);
    $('#saveOnLeave').checked = localStorage.getItem('workbench-save-on-leave') === 'true';
    updateSaveIndicator();
    $('#convertRecord').textContent = currentRecord.type === 'todo' ? '转换为问题' : '转换为待办';
    $('#convertRecord').style.display = isInfo ? 'none' : '';
    renderRelations();
    renderAttachments();
    closeSearch(); showOverlay(); detailDrawer.classList.add('visible'); detailDrawer.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(() => requestAnimationFrame(updateEditorAutoCollapse));
    if (editorDirty) notify('已恢复异常退出前的草稿', '草稿尚未写入 Markdown，请检查后手动保存');
  } catch (error) { notify('无法打开记录', error.message, true); }
}

function setEditorMode(mode) {
  editorMode = mode;
  const area = $('.editor-area');
  area.className = `editor-area ${mode === 'wysiwyg' ? '' : mode}`.trim();
  $$('.editor-tabs [data-editor-mode]').forEach(button => button.classList.toggle('active', button.dataset.editorMode === mode));
  $('.editor-toolbar').classList.toggle('hidden', mode !== 'wysiwyg');
  if (mode !== 'wysiwyg') {
    const markdown = currentRecord ? currentRecord.body : editorToMarkdown($('.editor'));
    $('.markdown-source').value = markdown;
    $('.markdown-preview').innerHTML = markdownToHtml(markdown);
  }
  requestAnimationFrame(updateEditorAutoCollapse);
}

function updateEditorAutoCollapse() {
  const area = $('.editor-area');
  if (!currentRecord || editorContentExpanded || editorExpanded) {
    area.classList.remove('content-collapsed');
    return;
  }
  area.classList.remove('content-collapsed');
  const activeContent = editorMode === 'wysiwyg' ? $('.editor') : editorMode === 'markdown' ? $('.markdown-source') : $('.markdown-preview');
  const body = String(currentRecord.body || '');
  const isLong = (activeContent?.scrollHeight || 0) > EDITOR_COLLAPSE_HEIGHT || body.length > 1200 || body.split('\n').length > 18;
  area.classList.toggle('content-collapsed', isLong);
}

function expandEditorContent({focus = false} = {}) {
  const area = $('.editor-area');
  if (!area.classList.contains('content-collapsed')) return;
  editorContentExpanded = true;
  area.classList.remove('content-collapsed');
  if (focus) (editorMode === 'wysiwyg' ? $('.editor') : $('.markdown-source')).focus();
}

function localEditorContent() {
  return editorMode === 'wysiwyg' ? editorToMarkdown($('.editor')) : $('.markdown-source').value;
}

function insertInfoFieldIntoEditor(row) {
  const name = $('[data-info-field-name]', row).value.trim() || '未命名字段';
  const value = $('[data-info-field-value]', row).value.trim() || '—';
  const note = $('[data-info-field-note]', row).value.trim();
  const markdown = `\n\n### ${name}\n\n**值：** ${value}${note ? `\n\n> 说明：${note}` : ''}\n`;
  if (row.closest('#createInfoFieldList')) {
    const source = $('#createBodyField textarea');
    const start = source.selectionStart ?? source.value.length;
    const end = source.selectionEnd ?? start;
    source.value = `${source.value.slice(0, start)}${markdown}${source.value.slice(end)}`.trimStart();
    source.focus();
    source.selectionStart = source.selectionEnd = Math.min(start + markdown.length, source.value.length);
    notify('键值对已插入补充说明', note ? '字段值和说明已生成 Markdown 内容块' : '字段值已生成 Markdown 内容块');
    return;
  }
  if (editorMode === 'wysiwyg') {
    $('.editor').focus();
    if (!restoreLastEditorSelection()) placeCaret($('.editor'), false);
    document.execCommand('insertHTML', false, markdownToHtml(markdown, true));
  } else {
    const source = $('.markdown-source');
    const start = source.selectionStart ?? source.value.length;
    const end = source.selectionEnd ?? start;
    source.value = `${source.value.slice(0, start)}${markdown}${source.value.slice(end)}`;
    source.selectionStart = source.selectionEnd = start + markdown.length;
    $('.markdown-preview').innerHTML = markdownToHtml(source.value);
    source.focus();
  }
  markEditorChanged();
  notify('键值对已插入正文', note ? '字段值和说明已生成正文块' : '字段值已生成正文块');
}

function showConflict(latest) {
  conflictRecord = latest;
  $('#localConflictContent').value = localEditorContent();
  $('#externalConflictContent').value = latest.body;
  const diff = lineDiff($('#localConflictContent').value, latest.body);
  $('#conflictDiff').innerHTML = diff.rows.map((row, index) => `<div class="diff-row ${row.type}"><span>${index + 1}</span><span>${escapeHtml(row.local ?? '')}</span><span>${escapeHtml(row.external ?? '')}</span></div>`).join('');
  $('#mergedConflictContent').value = diff.merged;
  if (!$('#conflictDialog').open) $('#conflictDialog').showModal();
}

function lineDiff(localText, externalText) {
  const a = localText.split('\n'), b = externalText.split('\n');
  if (a.length * b.length > 120000) {
    const rows = Array.from({length:Math.max(a.length,b.length)}, (_,i) => ({type:a[i] === b[i] ? 'same' : 'changed', local:a[i] ?? '', external:b[i] ?? ''}));
    return {rows, merged:`<<<<<<< 工作台\n${localText}\n=======\n${externalText}\n>>>>>>> 磁盘`};
  }
  const dp = Array.from({length:a.length + 1}, () => new Uint16Array(b.length + 1));
  for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i+1][j+1] + 1 : Math.max(dp[i+1][j], dp[i][j+1]);
  const rows = []; let i = 0, j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) { rows.push({type:'same', local:a[i], external:b[j]}); i++; j++; }
    else if (i < a.length && (j >= b.length || dp[i+1][j] >= dp[i][j+1])) { rows.push({type:'removed', local:a[i], external:''}); i++; }
    else { rows.push({type:'added', local:'', external:b[j]}); j++; }
  }
  const merged = []; let localChunk = [], externalChunk = [];
  const flush = () => { if (!localChunk.length && !externalChunk.length) return; if (localChunk.join('\n') === externalChunk.join('\n')) merged.push(...localChunk); else merged.push('<<<<<<< 工作台', ...localChunk, '=======', ...externalChunk, '>>>>>>> 磁盘'); localChunk = []; externalChunk = []; };
  rows.forEach(row => { if (row.type === 'same') { flush(); merged.push(row.local); } else { if (row.local) localChunk.push(row.local); if (row.external) externalChunk.push(row.external); } }); flush();
  return {rows, merged:merged.join('\n')};
}

function parsedAttachments() {
  return (currentRecord?.attachments || []).map(item => {
    if (typeof item !== 'string') return item;
    try { return JSON.parse(item); } catch { return null; }
  }).filter(Boolean);
}

function renderAttachments() {
  const attachments = parsedAttachments();
  $('#attachmentList').innerHTML = attachments.length ? attachments.map(item => `<button class="attachment-entry" data-attachment-name="${escapeHtml(item.name)}"><span class="attachment-icon">▧</span><span><strong>${escapeHtml(item.name)}</strong><small>${Math.max(1, Math.round((item.size || 0) / 1024))} KB · ${escapeHtml(item.mime)}</small></span><em>打开</em></button>`).join('') : '<div class="empty-state">暂无附件，可以粘贴截图或选择文件</div>';
}

function linkedRecordIds() {
  const markers = [...(currentRecord?.body || '').matchAll(/\[\[([A-Za-z]+-\d+)\]\]/g)].map(match => match[1]);
  return [...new Set([...(currentRecord?.links || []), ...markers])];
}

function renderRelations() {
  const linked = linkedRecordIds().map(id => records.find(item => item.id === id)).filter(Boolean);
  $('#relationList').innerHTML = linked.length ? linked.map(record => `<div class="attachment-entry"><span class="type-icon ${record.type}">${typeIcons[record.type]}</span><span><strong>${escapeHtml(record.title)}</strong><small>${record.id} · ${escapeHtml(projectName(record.project_id))}</small></span><button data-open-related="${record.id}">打开</button><button data-remove-relation="${record.id}">×</button></div>`).join('') : '<div class="empty-state">暂无关联记录，可通过稳定编号互相引用</div>';
}

function renderRelationResults(query = '') {
  const needle = query.trim().toLowerCase(); const linked = new Set(linkedRecordIds());
  const candidates = records.filter(record => record.id !== currentRecord?.id && !linked.has(record.id) && (!needle || `${record.id} ${record.title}`.toLowerCase().includes(needle)));
  $('#relationResults').innerHTML = candidates.slice(0,30).map(record => `<button class="relation-result" data-add-relation="${record.id}">${typeIcon(record)}<span><strong>${escapeHtml(record.title)}</strong><small>${record.id} · ${escapeHtml(projectName(record.project_id))}</small></span><em>＋ 关联</em></button>`).join('') || '<div class="empty-state">没有可关联的记录</div>';
}

async function renderManagePage(page) {
  if (page === 'status_templates') {
    $('#manageEyebrow').textContent = '全局配置';
    $('#manageTitle').textContent = '状态模板';
    $('#manageDescription').textContent = '创建多套工作流，并为每个项目选择适合的状态流程。';
    const workflows = configData?.workflow_templates || [];
    if (!workflows.some(item => item.id === selectedWorkflowId)) selectedWorkflowId = workflows[0]?.id;
    const selectedWorkflow = workflows.find(item => item.id === selectedWorkflowId) || workflows[0];
    $('#manageActions').innerHTML = `<select class="filter-button" id="workflowSelector">${workflows.map(item => `<option value="${escapeHtml(item.id)}" ${item.id === selectedWorkflowId ? 'selected' : ''}>${escapeHtml(item.name)}</option>`).join('')}</select><button class="secondary-button" id="statusUsageOverview">使用统计</button><button class="secondary-button" id="newWorkflow">＋ 新建</button><button class="secondary-button" id="duplicateWorkflow">复制</button><button class="secondary-button danger-button" id="deleteWorkflow">删除</button><button class="primary-button" id="saveTemplates">保存工作流</button>`;
    const names = {issue:'问题状态', todo:'待办状态'};
    $('#manageContent').innerHTML = `<div class="status-batch-bar"><label><input type="checkbox" id="selectAllStatuses"><span>全选</span></label><strong id="statusSelectionCount">已选择 0 个状态</strong><button type="button" class="secondary-button danger-button" id="batchDeleteStatuses" disabled>批量删除</button></div><div class="template-grid">${Object.entries(selectedWorkflow?.statuses || {}).filter(([type]) => type !== 'idea').map(([type, statuses]) => `<section class="template-panel" data-template-type="${type}"><header><h2>${names[type]}</h2><span class="count-badge">${statuses.length}</span></header><div class="status-edit-list">${statuses.map(status => statusEditorHtml(status, type)).join('')}</div><button class="add-status" data-add-status="${type}">＋ 添加状态</button></section>`).join('')}</div>`;
    captureManageSnapshot(page);
    return;
  }
  if (page === 'archive') {
    const archived = projects.filter(project => project.status === 'archived');
    $('#manageEyebrow').textContent = '项目管理'; $('#manageTitle').textContent = '已归档项目'; $('#manageDescription').textContent = '归档项目仍可查看、搜索和添加新记录。'; $('#manageActions').innerHTML = '';
    $('#manageContent').innerHTML = archived.length ? `<div class="management-grid">${archived.map(project => `<article class="management-card"><h3>${escapeHtml(project.name)}</h3><p>${escapeHtml(project.description || '暂无项目描述')}</p><footer><span>${records.filter(item => item.project_id === project.id).length} 条记录</span><div><button class="secondary-button" data-open-project="${escapeHtml(project.id)}">打开</button> <button class="secondary-button" data-restore-project="${escapeHtml(project.id)}">恢复</button></div></footer></article>`).join('')}</div>` : '<div class="empty-state">暂无已归档项目</div>';
    return;
  }
  if (page === 'documents') {
    $('#manageEyebrow').textContent = '知识沉淀'; $('#manageTitle').textContent = '知识库'; $('#manageDescription').textContent = '使用自定义分类集中收纳与维护文档。'; $('#manageActions').innerHTML = '<button class="secondary-button" id="importKnowledgeDocuments">导入文档</button><button class="secondary-button" id="startDocumentExport">导出</button><button class="secondary-button" id="newDocumentCategory">＋ 新建分类</button><button class="primary-button" id="newDocument">＋ 新建文档</button>';
    $('#manageContent').innerHTML = '<div class="empty-state">正在加载文档…</div>';
    try { documents = await api('/documents'); }
    catch {
      const index = documents.findIndex(item => item.id === saved.id);
      if (index >= 0) documents[index] = saved; else documents.unshift(saved);
    }
    if (activeManagePage !== page) return;
    renderDocumentsPage();
    return;
  }
  if (page === 'timeline') {
    let visibleRecords = records.filter(record => ['type','project','status','priority','tag'].every(field => recordMatchesTimelineFilter(record, field)));
    const priorityRank = {紧急:4, 高:3, 普通:2, 低:1};
    const sortValue = record => {
      if (timelineSort.field === 'updated' || timelineSort.field === 'created') return Date.parse(record[timelineSort.field] || '') || 0;
      if (timelineSort.field === 'priority') return priorityRank[record.priority] || 0;
      if (timelineSort.field === 'project') return projectName(record.project_id);
      if (timelineSort.field === 'type') return typeNames[record.type] || record.type;
      return String(record[timelineSort.field] || '');
    };
    const direction = timelineSort.direction === 'asc' ? 1 : -1;
    visibleRecords = visibleRecords.map((record, index) => ({record, index})).sort((a, b) => {
      const av = sortValue(a.record), bv = sortValue(b.record);
      const compared = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv), 'zh-CN');
      return compared * direction || a.index - b.index;
    }).map(item => item.record);
    $('#manageEyebrow').textContent = '全部工作'; $('#manageTitle').textContent = '全部记录'; $('#manageDescription').textContent = `当前显示 ${visibleRecords.length} / ${records.length} 条记录，可组合多个条件筛选。`;
    $('#manageActions').innerHTML = '<button class="primary-button" data-create-type="问题">＋ 新建记录</button>';
    const sortButton = (field, label) => `<button type="button" class="timeline-column-sort ${timelineSort.field === field ? 'active' : ''}" data-timeline-sort="${field}" title="按${label}排序">${escapeHtml(label)}<span>${timelineSort.field === field ? (timelineSort.direction === 'asc' ? '↑' : '↓') : '↕'}</span></button>`;
    const filterButton = (field, label) => `<button type="button" class="timeline-filter-trigger ${(timelineFilters[field] || []).length ? 'active' : ''}" data-timeline-filter="${field}" aria-label="筛选${label}" aria-expanded="false" title="筛选${label}"><i></i>${(timelineFilters[field] || []).length ? `<em>${timelineFilters[field].length}</em>` : ''}</button>`;
    const tableHeaders = `<tr><th><div class="timeline-column-head">${sortButton('type','类型')}${filterButton('type','类型')}</div></th><th><div class="timeline-column-head">${sortButton('title','标题')}</div></th><th><div class="timeline-column-head">${sortButton('project','项目')}${filterButton('project','项目')}</div></th><th><div class="timeline-column-head">${sortButton('status','状态')}${filterButton('status','状态')}</div></th><th><div class="timeline-column-head">${sortButton('priority','优先级')}${filterButton('priority','优先级')}</div></th><th><div class="timeline-column-head"><span class="timeline-column-label">标签</span>${filterButton('tag','标签')}${hasTimelineFilters() ? '<button type="button" class="timeline-filter-reset" id="resetTimelineFilters" title="清除全部筛选">清除</button>' : ''}</div></th><th><div class="timeline-column-head">${sortButton('updated','更新时间')}</div></th></tr>`;
    const rows = visibleRecords.map(record => `<tr data-record-id="${record.id}"><td>${typeChipHtml(record)}</td><td><strong>${escapeHtml(record.title)}</strong><small class="record-table-id">${escapeHtml(record.id)}</small></td><td>${projectChipHtml(record.project_id)}</td><td>${record.type === 'info' ? '<span class="no-field-value">—</span>' : statusChipHtml(record)}</td><td>${record.type === 'info' ? '<span class="no-field-value">—</span>' : priorityChipHtml(record.priority)}</td><td><div class="tag-row">${(record.tags || []).map(projectTagHtml).join('') || '<span class="no-field-value">—</span>'}</div></td><td>${new Date(record.updated).toLocaleString('zh-CN')}</td></tr>`).join('');
    $('#manageContent').innerHTML = records.length ? `<div class="timeline-table-wrap"><table class="data-table timeline-table"><thead>${tableHeaders}</thead><tbody>${rows || '<tr class="timeline-empty-row"><td colspan="7">没有符合当前筛选条件的记录</td></tr>'}</tbody></table></div>` : '<div class="empty-state">还没有任何记录</div>';
    return;
  }
  if (page === 'tags') {
    $('#manageEyebrow').textContent = '全局分类'; $('#manageTitle').textContent = '标签管理'; $('#manageDescription').textContent = '标签全局统一；正在被记录使用的标签需要先解除引用，才能删除。'; $('#manageActions').innerHTML = '<button class="secondary-button" id="tagUsageOverview">使用统计</button><button class="primary-button" id="saveTags">保存标签</button>';
    $('#manageContent').innerHTML = '<div class="empty-state">正在加载标签…</div>';
    const tags = await api('/tags');
    if (activeManagePage !== page) return;
    configData.tags = tags;
    $('#manageContent').innerHTML = `<div class="tag-batch-bar"><label><input type="checkbox" id="selectAllTags"><span>全选</span></label><strong id="tagSelectionCount">已选择 0 个标签</strong><button type="button" class="secondary-button danger-button" id="batchDeleteTags" disabled>批量删除</button></div><div class="tag-manager">${tags.map(tag => tagEditorHtml(tag)).join('')}<button type="button" class="add-config-card" id="addGlobalTag"><span>＋</span><strong>新建标签</strong></button></div>`;
    captureManageSnapshot(page);
    return;
  }
  if (page === 'trash') {
    $('#manageEyebrow').textContent = '数据保护'; $('#manageTitle').textContent = '回收站'; $('#manageDescription').textContent = '删除的项目和记录可以恢复，永久删除后无法找回。';
    $('#manageContent').innerHTML = '<div class="empty-state">正在加载回收站…</div>';
    trashItems = await api('/trash');
    if (activeManagePage !== page) return;
    trashSelection = new Set([...trashSelection].filter(token => trashItems.some(item => item.token === token)));
    renderTrashPage();
    return;
  }
  if (page === 'settings') {
    $('#manageEyebrow').textContent = '本地数据'; $('#manageTitle').textContent = '设置与数据'; $('#manageDescription').textContent = '查看数据位置，导入 Markdown 或导出完整备份。'; $('#manageActions').innerHTML = '';
    $('#manageContent').innerHTML = `<div class="settings-stack"><section class="settings-card"><h2>Markdown 数据目录</h2><p>可修改为当前电脑上的其他目录。切换成功后，新记录会自动保存到新位置。</p><label class="data-directory-field"><span>完整目录路径</span><input id="dataDirectoryInput" value="${escapeHtml(configData.data_dir)}" spellcheck="false" placeholder="例如 E:\\WorkBenchData"></label><div class="data-directory-actions"><select id="dataDirectoryMode"><option value="migrate">复制当前全部数据并切换（推荐）</option><option value="existing">直接使用已有工作台目录</option></select><button class="primary-button" id="saveDataDirectory">应用新目录</button></div><small class="settings-hint">复制模式要求目标目录为空，原目录会保留作为备份；直接使用模式不会删除或覆盖已有文件。</small></section><section class="settings-card"><h2>导入与导出</h2><p>导入单个 Markdown 文件、完整项目目录，或将整个工作台打包成 ZIP。</p><div class="settings-actions"><button class="primary-button" id="importMarkdown">导入 Markdown</button><input type="file" id="importMarkdownInput" accept=".md,text/markdown" hidden><button class="secondary-button" id="importDirectory">导入项目目录</button><input type="file" id="importDirectoryInput" accept=".md,text/markdown" webkitdirectory multiple hidden><button class="secondary-button" id="exportAll">导出全部数据</button></div></section><section class="settings-card"><h2>附件清理</h2><p>扫描没有被任何记录引用的附件，确认后再从磁盘删除。</p><div class="settings-actions"><button class="secondary-button" id="scanOrphanAssets">扫描无引用附件</button><span id="orphanAssetResult"></span></div></section><section class="settings-card"><h2>当前数据</h2><div class="stat-grid"><div class="stat-card"><strong>${projects.length}</strong><span>项目</span></div><div class="stat-card"><strong>${records.filter(item=>item.type==='issue').length}</strong><span>问题</span></div><div class="stat-card"><strong>${records.filter(item=>item.type==='todo').length}</strong><span>待办</span></div><div class="stat-card"><strong>${records.filter(item=>item.type==='info').length}</strong><span>信息</span></div></div></section></div>`;
    captureManageSnapshot(page);
  }
}

function renderDocumentsPage() {
  $$('.document-category-group', $('#manageContent')).forEach(group => {
    if (group.open) documentOpenCategories.add(group.dataset.documentCategory);
    else documentOpenCategories.delete(group.dataset.documentCategory);
  });
  const sortConfig = knowledgeSortConfig();
  const categoryQuery = documentFilters.categoryQuery.trim().toLowerCase();
  const categoryIndex = new Map(sortConfig.category_order.map((name, index) => [name, index]));
  let categoryEntries = [...new Set([...(configData?.document_categories || []), ...documents.map(item => item.category || '未分类')])].map(name => {
    const allItems = documents.filter(item => (item.category || '未分类') === name);
    return {name, allItems, updated:Math.max(0, ...allItems.map(item => Date.parse(item.updated || '') || 0))};
  }).filter(entry => !categoryQuery || entry.name.toLowerCase().includes(categoryQuery));
  categoryEntries.sort((a,b) => {
    if (a.name === '未分类') return 1;
    if (b.name === '未分类') return -1;
    if (sortConfig.category_mode === 'manual') return (categoryIndex.get(a.name) ?? 999999) - (categoryIndex.get(b.name) ?? 999999) || a.name.localeCompare(b.name, 'zh-CN');
    if (sortConfig.category_mode === 'count') return b.allItems.length - a.allItems.length || a.name.localeCompare(b.name, 'zh-CN');
    if (sortConfig.category_mode === 'updated') return b.updated - a.updated || a.name.localeCompare(b.name, 'zh-CN');
    return a.name.localeCompare(b.name, 'zh-CN');
  });
  categoryEntries = categoryEntries.map(entry => {
    const fileQuery = (documentCategoryFileQueries[entry.name] || '').trim().toLowerCase();
    const fileMode = sortConfig.file_modes[entry.name] || sortConfig.file_mode;
    const fileIndex = new Map((sortConfig.file_orders[entry.name] || []).map((id, index) => [id, index]));
    const items = entry.allItems.filter(item => !fileQuery || `${item.title} ${item.body} ${(item.tags || []).join(' ')}`.toLowerCase().includes(fileQuery)).sort((a,b) => {
      if (fileMode === 'manual') return (fileIndex.get(a.id) ?? 999999) - (fileIndex.get(b.id) ?? 999999) || String(a.title).localeCompare(String(b.title), 'zh-CN');
      if (fileMode === 'title') return String(a.title).localeCompare(String(b.title), 'zh-CN');
      const field = fileMode === 'created' ? 'created' : 'updated';
      return (Date.parse(b[field] || '') || 0) - (Date.parse(a[field] || '') || 0);
    });
    return {...entry, items, fileQuery, fileMode};
  });
  const visible = categoryEntries.flatMap(entry => entry.items);
  documentSelection = new Set([...documentSelection].filter(id => documents.some(item => item.id === id)));
  renderDocumentActions();
  const hasFileFilters = Object.values(documentCategoryFileQueries).some(value => value.trim());
  const categoryDrag = sortConfig.category_mode === 'manual' && !categoryQuery && !hasFileFilters && !documentExportMode;
  const documentDrag = !categoryQuery && !hasFileFilters && !documentExportMode;
  const cardHtml = item => `<article class="document-card ${documentSelection.has(item.id) ? 'selected' : ''}" data-document-card="${escapeHtml(item.id)}" data-document-sort-id="${escapeHtml(item.id)}" draggable="${documentDrag}" title="${documentDrag ? '拖到其他分类条目可更改分类' : '清除筛选后可拖动文档'}">${documentExportMode ? `<label class="document-card-select" title="选择文档"><input type="checkbox" data-document-select="${escapeHtml(item.id)}" ${documentSelection.has(item.id) ? 'checked' : ''}><span>选择</span></label>` : ''}<button type="button" class="document-card-open" data-document-id="${escapeHtml(item.id)}"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(markdownToPlainText(item.body, 110, item.title))}</p>${(item.tags || []).length ? `<div class="document-card-tags">${item.tags.map(tag => `<span style="--tag-color:${safeColor((configData.tags || []).find(item => item.name === tag)?.color, '#64748b')}">${escapeHtml(tag)}</span>`).join('')}</div>` : ''}<footer><span>${escapeHtml(item.id)}</span><time>${new Date(item.updated).toLocaleDateString('zh-CN')}</time></footer></button><button type="button" class="document-card-more" data-document-card-menu="${escapeHtml(item.id)}" title="更多操作" aria-label="${escapeHtml(item.title)}的更多操作" draggable="false">•••</button></article>`;
  const categoryLabels = {manual:'手动排序', name:'分类名称', count:'文档数量', updated:'最近更新'};
  const fileLabels = {manual:'手动排序', updated:'最近更新', title:'文档标题', created:'最新创建'};
  $('#manageContent').innerHTML = `<div class="knowledge-filter-panel category-only"><div class="knowledge-filter-row"><span class="knowledge-filter-level">分类</span><label class="document-search"><span>⌕</span><input id="documentCategorySearch" value="${escapeHtml(documentFilters.categoryQuery)}" placeholder="筛选分类名称"></label><button type="button" class="secondary-button document-sort-button ${sortConfig.category_mode === 'manual' ? '' : 'active'}" id="documentCategorySortButton" title="分类排序：${categoryLabels[sortConfig.category_mode]}">↕ <span>${categoryLabels[sortConfig.category_mode]}</span></button>${categoryQuery ? '<button type="button" class="knowledge-filter-clear" id="clearDocumentCategoryFilter">清除</button>' : ''}</div><p>分类条目支持新建、重命名和删除；删除分类后，其中的文档会移入“未分类”。</p></div>${documentExportMode ? `<div class="document-batch-bar"><label><input type="checkbox" id="selectVisibleDocuments" data-visible-ids="${escapeHtml(visible.map(item => item.id).join(','))}"> 全选当前结果</label><span id="documentSelectionCount">已选择 ${documentSelection.size} 篇</span><button type="button" class="secondary-button" id="clearDocumentSelection" ${documentSelection.size ? '' : 'disabled'}>清除选择</button></div>` : ''}<div class="document-result-count">显示 ${categoryEntries.length} 个分类 · ${visible.length} / ${documents.length} 篇文档</div><div class="document-category-list">${categoryEntries.map(entry => { const open = documentExportMode || Boolean(entry.fileQuery) || documentOpenCategories.has(entry.name); const actions = entry.name === '未分类' ? '<span class="category-entry-actions document-category-actions category-entry-actions-placeholder" aria-hidden="true"></span>' : `<span class="category-entry-actions document-category-actions"><button type="button" data-rename-document-category="${escapeHtml(entry.name)}">重命名</button><button type="button" class="danger" data-delete-document-category="${escapeHtml(entry.name)}">删除</button></span>`; const draggable = categoryDrag && entry.name !== '未分类'; return `<details class="category-entry document-category-group" data-document-category="${escapeHtml(entry.name)}" draggable="${draggable}" ${open ? 'open' : ''}><summary class="category-entry-summary"><span class="document-category-drag" title="${draggable ? '拖动分类调整顺序' : entry.name === '未分类' ? '未分类固定在最后' : '切换为手动排序后可拖动'}">⠿</span><span class="category-entry-chevron document-category-chevron">›</span><span class="category-entry-icon document-category-icon">▤</span><strong>${escapeHtml(entry.name)}</strong><em>${entry.items.length}${entry.fileQuery ? ` / ${entry.allItems.length}` : ''} 篇</em><div class="document-category-file-tools"><label><span>⌕</span><input data-document-file-search="${escapeHtml(entry.name)}" value="${escapeHtml(documentCategoryFileQueries[entry.name] || '')}" placeholder="筛选文档"></label>${entry.fileQuery ? `<button type="button" class="category-file-clear" data-clear-document-file-filter="${escapeHtml(entry.name)}" title="清除文档筛选">×</button>` : ''}<button type="button" class="category-file-sort ${entry.fileMode === 'manual' ? '' : 'active'}" data-document-file-sort="${escapeHtml(entry.name)}" title="文档排序：${fileLabels[entry.fileMode]}">↕ <span>${fileLabels[entry.fileMode]}</span></button></div><small class="document-category-drop-hint">拖入文档以分类</small>${actions}</summary><div class="document-grid" data-document-category-grid="${escapeHtml(entry.name)}">${entry.items.map(cardHtml).join('') || '<div class="empty-state document-empty">此分类中没有符合条件的文档</div>'}</div></details>`; }).join('') || '<div class="empty-state document-empty">没有符合当前条件的分类</div>'}</div>`;
  updateDocumentSelectionUI();
  bindKnowledgeDragAndDrop();
}

function renderDocumentActions() {
  if (documentExportMode) {
    $('#manageActions').innerHTML = `<span class="document-export-count" id="documentExportCount">已选 ${documentSelection.size} 篇</span><button class="primary-button" id="exportSelectedKnowledge" ${documentSelection.size ? '' : 'disabled'}>导出所选</button><button class="secondary-button" id="cancelDocumentExport">取消</button>`;
  } else {
    $('#manageActions').innerHTML = '<button class="secondary-button" id="importKnowledgeDocuments">导入文档</button><button class="secondary-button" id="startDocumentExport">导出</button><button class="secondary-button" id="newDocumentCategory">＋ 新建分类</button><button class="primary-button" id="newDocument">＋ 新建文档</button>';
  }
}

async function createDocumentCategory() {
  const name = await appPrompt({title:'新建知识库分类', message:'新分类可以先保持为空，也可以直接拖入文档。', confirmText:'创建分类', input:{label:'分类名称', placeholder:'例如：产品设计'}});
  const category = name?.trim();
  if (!category) return;
  const currentCategories = configData?.document_categories || [];
  if (currentCategories.includes(category)) { notify('分类已存在', `「${category}」已经在知识库中`, true); return; }
  try {
    configData.document_categories = await api('/document-categories', {method:'PUT', body:JSON.stringify({categories:[...currentCategories, category]})});
    const sort = knowledgeSortConfig();
    configData.document_sort = await api('/document-sort', {method:'PUT', body:JSON.stringify({...sort, category_order:[...sort.category_order.filter(item => item !== category), category]})});
    documentOpenCategories.add(category);
    renderDocumentsPage();
    notify('分类已创建', `「${category}」现在可以接收文档`);
  } catch (error) { notify('创建分类失败', error.message, true); }
}

async function renameDocumentCategory(oldName) {
  const value = await appPrompt({title:'重命名知识库分类', message:`分类中的文档会一起迁移，不会改变文档内容。`, confirmText:'保存名称', input:{label:'新分类名称', value:oldName}});
  const newName = value?.trim();
  if (!newName || newName === oldName) return;
  try {
    const result = await api('/document-categories/rename', {method:'PATCH', body:JSON.stringify({old_name:oldName, new_name:newName})});
    configData.document_categories = result.categories;
    configData.document_sort = result.document_sort;
    documents = await api('/documents');
    if (Object.hasOwn(documentCategoryFileQueries, oldName)) {
      documentCategoryFileQueries[newName] = documentCategoryFileQueries[oldName];
      delete documentCategoryFileQueries[oldName];
    }
    if (documentOpenCategories.delete(oldName)) documentOpenCategories.add(newName);
    if (documentFilters.categoryQuery && oldName.toLowerCase().includes(documentFilters.categoryQuery.toLowerCase()) && !newName.toLowerCase().includes(documentFilters.categoryQuery.toLowerCase())) documentFilters.categoryQuery = '';
    renderDocumentsPage();
    notify('分类已重命名', `${oldName} → ${newName} · 已同步 ${result.updated_documents} 篇文档`);
  } catch (error) { notify('分类重命名失败', error.message, true); }
}

async function deleteDocumentCategory(name) {
  const count = documents.filter(item => (item.category || '未分类') === name).length;
  const approved = await appConfirm({title:`删除分类「${name}」？`, message:count ? `其中 ${count} 篇文档将移动到“未分类”。` : '这是一个空分类。', detail:'只删除分类，不会删除任何文档。', confirmText:'删除分类', danger:true});
  if (!approved) return;
  try {
    const result = await api(`/document-categories/${encodeURIComponent(name)}`, {method:'DELETE'});
    configData.document_categories = result.categories;
    configData.document_sort = result.document_sort;
    documents = await api('/documents');
    delete documentCategoryFileQueries[name]; documentOpenCategories.delete(name);
    renderDocumentsPage();
    notify('分类已删除', result.updated_documents ? `${result.updated_documents} 篇文档已移动到“未分类”` : '文档内容未受影响');
  } catch (error) { notify('删除分类失败', error.message, true); }
}

function knowledgeSortConfig() {
  const value = configData?.document_sort || {};
  return {category_mode:value.category_mode || 'manual', category_order:Array.isArray(value.category_order) ? value.category_order : [], file_mode:value.file_mode || value.mode || 'updated', file_modes:value.file_modes && typeof value.file_modes === 'object' ? value.file_modes : {}, file_orders:value.file_orders && typeof value.file_orders === 'object' ? value.file_orders : {}};
}

function openDocumentCategorySortMenu(button) {
  const current = knowledgeSortConfig().category_mode;
  const rules = [['manual','⠿','手动拖动排序'],['name','A','按分类名称'],['count','#','文档数量多优先'],['updated','◷','最近更新优先']];
  showKanbanMenu(button, `<div class="context-menu-title">分类条目排序</div><div class="context-menu-label">仅调整分类条目的显示顺序</div>${rules.map(([mode, icon, label]) => `<button data-menu-action="sort-document-categories" data-sort-mode="${mode}"><i class="sort-rule-icon">${icon}</i>${label}${current === mode ? '<span>✓</span>' : ''}</button>`).join('')}<div class="context-menu-note">选择手动排序后，可上下拖动整个分类条目。</div>`);
}

function openDocumentSortMenu(button) {
  const category = button.dataset.documentFileSort;
  const config = knowledgeSortConfig();
  const current = config.file_modes[category] || config.file_mode;
  const rules = [['manual','⠿','手动拖动排序'],['updated','◷','最近更新优先'],['title','A','按标题名称'],['created','＋','最新创建优先']];
  showKanbanMenu(button, `<div class="context-menu-title">${escapeHtml(category)} · 文档排序</div><div class="context-menu-label">只调整这个分类中的文件顺序</div>${rules.map(([mode, icon, label]) => `<button data-menu-action="sort-documents" data-document-category="${escapeHtml(category)}" data-sort-mode="${mode}"><i class="sort-rule-icon">${icon}</i>${label}${current === mode ? '<span>✓</span>' : ''}</button>`).join('')}<div class="context-menu-note">选择手动排序后，可在该分类中拖动文档卡片。</div>`);
}

function openDocumentCardMenu(button, documentId) {
  const item = documents.find(document => document.id === documentId); if (!item) return;
  showKanbanMenu(button, `<button data-menu-action="open-document-card" data-document="${escapeHtml(documentId)}">打开文档</button><button data-menu-action="document-card-categories" data-document="${escapeHtml(documentId)}">所属分类</button><button class="danger-item" data-menu-action="delete-document-card" data-document="${escapeHtml(documentId)}">删除文档</button>`);
}

function showDocumentCategorySubmenu(trigger, documentId) {
  $('.document-card-submenu')?.remove();
  $('#kanbanContextMenu [data-menu-action="document-card-categories"]')?.classList.remove('submenu-open');
  const item = documents.find(document => document.id === documentId), parent = $('#kanbanContextMenu');
  if (!item || !parent.classList.contains('visible')) return;
  trigger.classList.add('submenu-open');
  const categories = [...new Set([...(configData?.document_categories || []), ...documents.map(document => document.category || '未分类')])];
  const category = item.category || '未分类', submenu = document.createElement('div');
  submenu.className = 'context-menu visible document-card-submenu'; submenu.setAttribute('aria-hidden', 'false');
  submenu.innerHTML = `<div class="context-menu-label">选择分类</div>${categories.map(name => `<button data-menu-action="set-document-category" data-document="${escapeHtml(documentId)}" data-category="${escapeHtml(name)}" ${name === category ? 'disabled' : ''}>${escapeHtml(name)}${name === category ? '<span>当前</span>' : ''}</button>`).join('')}`;
  document.body.appendChild(submenu);
  const parentRect = parent.getBoundingClientRect(), submenuRect = submenu.getBoundingClientRect(), gap = 7;
  const right = parentRect.right + gap;
  const left = right + submenuRect.width <= innerWidth - 12 ? right : Math.max(12, parentRect.left - submenuRect.width - gap);
  const top = Math.max(12, Math.min(parentRect.top, innerHeight - submenuRect.height - 12));
  submenu.style.left = `${left}px`; submenu.style.top = `${top}px`;
}

async function saveKnowledgeSort(patch, title, detail) {
  try {
    configData.document_sort = await api('/document-sort', {method:'PUT', body:JSON.stringify({...knowledgeSortConfig(), ...patch})});
    renderDocumentsPage();
    notify(title, detail);
  } catch (error) { notify('文档排序设置失败', error.message, true); }
}

function bindKnowledgeDragAndDrop() {
  const sortConfig = knowledgeSortConfig();
  const filtersActive = Boolean(documentFilters.categoryQuery || Object.values(documentCategoryFileQueries).some(value => value.trim()) || documentExportMode);
  let draggedDocument = null;
  let sourceDocumentCategory = '';
  if (!filtersActive) {
    $$('[data-document-sort-id]').forEach(card => {
      card.addEventListener('dragstart', event => {
        if (event.target.closest('.document-card-more')) { event.preventDefault(); return; }
        draggedDocument = card;
        sourceDocumentCategory = card.closest('[data-document-category-grid]')?.dataset.documentCategoryGrid || '';
        card.classList.add('dragging');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', card.dataset.documentSortId);
      });
      card.addEventListener('dragend', () => {
        card.classList.remove('dragging');
        $$('.document-category-drop-target').forEach(item => item.classList.remove('document-category-drop-target'));
        draggedDocument = null; sourceDocumentCategory = '';
      });
    });
  }

  const moveDocumentToCategory = async targetCategory => {
    if (!draggedDocument || !targetCategory || targetCategory === sourceDocumentCategory) return false;
    const documentId = draggedDocument.dataset.documentSortId;
    const item = documents.find(document => document.id === documentId);
    if (!item) return false;
    try {
      await api(`/documents/${encodeURIComponent(documentId)}`, {method:'PATCH', body:JSON.stringify({category:targetCategory})});
      documents = await api('/documents');
      const current = knowledgeSortConfig();
      const fileOrders = Object.fromEntries(Object.entries(current.file_orders).map(([category, order]) => [category, order.filter(id => id !== documentId)]));
      fileOrders[targetCategory] = [...(fileOrders[targetCategory] || []), documentId];
      configData.document_sort = await api('/document-sort', {method:'PUT', body:JSON.stringify({...current, file_orders:fileOrders})});
      documentOpenCategories.add(targetCategory);
      renderDocumentsPage();
      notify('文档分类已更新', `「${item.title}」已移动到「${targetCategory}」`);
      return true;
    } catch (error) {
      notify('文档分类移动失败', error.message, true);
      renderDocumentsPage();
      return false;
    }
  };

  if (!filtersActive) {
    $$('.document-category-group', $('#manageContent')).forEach(group => {
      group.addEventListener('toggle', () => {
        if (group.open) documentOpenCategories.add(group.dataset.documentCategory);
        else documentOpenCategories.delete(group.dataset.documentCategory);
      });
      const summary = $('summary', group);
      summary.addEventListener('dragover', event => {
        if (!draggedDocument || group.dataset.documentCategory === sourceDocumentCategory) return;
        event.preventDefault(); event.stopPropagation();
        group.classList.add('document-category-drop-target');
        event.dataTransfer.dropEffect = 'move';
      });
      summary.addEventListener('dragleave', event => {
        if (!summary.contains(event.relatedTarget)) group.classList.remove('document-category-drop-target');
      });
      summary.addEventListener('drop', async event => {
        if (!draggedDocument) return;
        event.preventDefault(); event.stopPropagation();
        group.classList.remove('document-category-drop-target');
        await moveDocumentToCategory(group.dataset.documentCategory);
      });
    });
  }

  if (sortConfig.category_mode === 'manual' && !filtersActive) {
    let draggedCategory = null;
    $$('.document-category-group', $('#manageContent')).forEach(group => {
      group.addEventListener('dragstart', event => {
        if (event.target.closest('[data-document-sort-id]')) return;
        draggedCategory = group; group.classList.add('dragging'); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', group.dataset.documentCategory);
      });
      group.addEventListener('dragend', () => { group.classList.remove('dragging'); draggedCategory = null; });
      group.addEventListener('dragover', event => {
        if (!draggedCategory || draggedCategory === group) return;
        event.preventDefault();
        if (group.dataset.documentCategory === '未分类') { group.parentElement.insertBefore(draggedCategory, group); return; }
        const rect = group.getBoundingClientRect();
        group.parentElement.insertBefore(draggedCategory, event.clientY < rect.top + rect.height / 2 ? group : group.nextSibling);
      });
      group.addEventListener('drop', async event => {
        if (!draggedCategory) return;
        event.preventDefault();
        const currentOrder = $$('.document-category-group', $('#manageContent')).map(item => item.dataset.documentCategory);
        const order = [...currentOrder.filter(name => name !== '未分类'), ...currentOrder.filter(name => name === '未分类')];
        await saveKnowledgeSort({category_mode:'manual', category_order:order}, '分类顺序已保存', '可继续拖动分类调整位置');
      });
    });
  }
  if (filtersActive) return;
  $$('[data-document-category-grid]', $('#manageContent')).forEach(grid => {
    const fileMode = sortConfig.file_modes[grid.dataset.documentCategoryGrid] || sortConfig.file_mode;
    grid.addEventListener('dragover', event => {
      if (!draggedDocument) return;
      if (sourceDocumentCategory !== grid.dataset.documentCategoryGrid) {
        event.preventDefault();
        grid.closest('.document-category-group')?.classList.add('document-category-drop-target');
        return;
      }
      if (fileMode !== 'manual' || draggedDocument.parentElement !== grid) return;
      event.preventDefault();
      const target = event.target.closest('[data-document-sort-id]');
      if (!target || target === draggedDocument) return;
      const rect = target.getBoundingClientRect();
      const before = event.clientY < rect.top + rect.height / 2 || (Math.abs(event.clientY - (rect.top + rect.height / 2)) < rect.height / 4 && event.clientX < rect.left + rect.width / 2);
      grid.insertBefore(draggedDocument, before ? target : target.nextSibling);
    });
    grid.addEventListener('drop', async event => {
      if (!draggedDocument) return;
      event.preventDefault();
      const category = grid.dataset.documentCategoryGrid;
      if (category !== sourceDocumentCategory) { await moveDocumentToCategory(category); return; }
      if (fileMode !== 'manual' || draggedDocument.parentElement !== grid) return;
      const order = $$('[data-document-sort-id]', grid).map(card => card.dataset.documentSortId);
      await saveKnowledgeSort({file_modes:{...sortConfig.file_modes, [category]:'manual'}, file_orders:{...sortConfig.file_orders, [category]:order}}, '文档顺序已保存', `已更新「${category}」内的文件顺序`);
    });
  });
}

function updateDocumentSelectionUI() {
  const count = documentSelection.size;
  if ($('#documentSelectionCount')) $('#documentSelectionCount').textContent = `已选择 ${count} 篇`;
  if ($('#documentExportCount')) $('#documentExportCount').textContent = `已选 ${count} 篇`;
  if ($('#exportSelectedKnowledge')) $('#exportSelectedKnowledge').disabled = !count;
  if ($('#clearDocumentSelection')) $('#clearDocumentSelection').disabled = !count;
  $$('[data-document-card]').forEach(card => card.classList.toggle('selected', documentSelection.has(card.dataset.documentCard)));
  const visibleToggle = $('#selectVisibleDocuments');
  if (visibleToggle) {
    const ids = (visibleToggle.dataset.visibleIds || '').split(',').filter(Boolean);
    const selected = ids.filter(id => documentSelection.has(id)).length;
    visibleToggle.checked = Boolean(ids.length) && selected === ids.length;
    visibleToggle.indeterminate = selected > 0 && selected < ids.length;
  }
}

function documentOutlineItems() {
  if (documentMode === 'markdown') {
    const source = $('#documentBody').value;
    const items = [];
    const pattern = /^(#{1,4})\s+(.+)$/gm;
    let match;
    while ((match = pattern.exec(source))) items.push({level:match[1].length, text:match[2].replace(/[*_`~\[\]]/g, '').trim(), offset:match.index});
    return items;
  }
  const container = documentMode === 'read' ? $('#documentReadPane') : $('#documentVisualEditor');
  return $$('h1,h2,h3,h4', container).map((heading, index) => {
    heading.dataset.documentOutlineIndex = String(index);
    heading.id = `document-section-${index}`;
    return {level:Number(heading.nodeName.slice(1)), text:heading.textContent.trim(), index};
  }).filter(item => item.text);
}

function updateDocumentOutline() {
  const outline = $('#documentOutline');
  if (!outline) return;
  outline.classList.toggle('collapsed', documentOutlineCollapsed);
  $('#documentDialog').classList.toggle('outline-collapsed', documentOutlineCollapsed);
  $('#toggleDocumentOutline').textContent = documentOutlineCollapsed ? '›' : '‹';
  $('#toggleDocumentOutline').title = documentOutlineCollapsed ? '展开导航' : '收起导航';
  $('#toggleDocumentOutline').setAttribute('aria-label', documentOutlineCollapsed ? '展开文档导航' : '收起文档导航');
  $('#documentOutlineTitle').textContent = $('#documentTitle').value.trim() || currentDocument?.title || '新建文档';
  const items = documentOutlineItems();
  $('#documentOutlineNav').innerHTML = items.length ? items.map((item, index) => `<button type="button" data-document-outline-index="${item.index ?? index}" data-document-outline-offset="${item.offset ?? ''}" style="--outline-indent:${Math.max(0, item.level - 1) * 13}px" title="${escapeHtml(item.text)}"><span>${escapeHtml(item.text)}</span></button>`).join('') : '<p>添加标题后将自动生成导航</p>';
}

function scheduleDocumentOutlineUpdate() {
  clearTimeout(documentOutlineTimer);
  documentOutlineTimer = setTimeout(updateDocumentOutline, 120);
}

function navigateDocumentOutline(button) {
  const index = Number(button.dataset.documentOutlineIndex);
  if (documentMode === 'markdown') {
    const textarea = $('#documentBody');
    const offset = Number(button.dataset.documentOutlineOffset || 0);
    textarea.focus(); textarea.setSelectionRange(offset, offset);
    textarea.scrollTop = textarea.scrollHeight * (offset / Math.max(1, textarea.value.length));
    return;
  }
  const container = documentMode === 'read' ? $('#documentReadPane') : $('#documentVisualEditor');
  const heading = $(`[data-document-outline-index="${index}"]`, container);
  heading?.scrollIntoView({behavior:'smooth', block:'start'});
}

function setDocumentMode(mode) {
  if (documentMode === 'visual' && mode !== 'visual') $('#documentBody').value = editorToMarkdown($('#documentVisualEditor'));
  if (documentMode === 'markdown' && mode !== 'markdown') $('#documentVisualEditor').innerHTML = markdownToHtml($('#documentBody').value, true);
  documentMode = mode;
  $('#documentSelectionToolbar').classList.remove('visible');
  $('#documentColorPalette').hidden = true;
  const reading = mode === 'read';
  $('#documentEditPane').hidden = reading;
  $('#documentReadPane').style.display = reading ? 'block' : 'none';
  $('.document-editor-shell').style.display = reading ? 'none' : '';
  $('#saveDocument').style.display = reading ? 'none' : '';
  $('#toggleDocumentMode').textContent = reading ? '编辑模式' : '阅读模式';
  $('#documentVisualEditor').style.display = mode === 'visual' ? 'block' : 'none';
  $('#documentBody').style.display = mode === 'markdown' ? 'block' : 'none';
  $('#documentInlinePreview').style.display = 'none';
  $('#documentFormatToolbar').style.display = mode === 'visual' ? 'flex' : 'none';
  $$('.document-editor-tabs [data-document-mode]').forEach(button => button.classList.toggle('active', button.dataset.documentMode === mode));
  if (reading) $('#documentReadPane').innerHTML = markdownToHtml($('#documentBody').value || currentDocument?.body || '');
  requestAnimationFrame(updateDocumentOutline);
}

function documentMarkdownContent() {
  if (documentMode === 'visual') $('#documentBody').value = editorToMarkdown($('#documentVisualEditor'));
  return $('#documentBody').value;
}

function restoreDocumentSelection() {
  const editor = $('#documentVisualEditor');
  if (!documentLastRange || !editor.contains(documentLastRange.commonAncestorContainer)) return false;
  const selection = window.getSelection();
  selection.removeAllRanges(); selection.addRange(documentLastRange.cloneRange());
  return true;
}

function captureDocumentSelection() {
  const editor = $('#documentVisualEditor');
  const selection = window.getSelection();
  if (!selection?.rangeCount || !editor.contains(selection.anchorNode)) return false;
  documentLastRange = selection.getRangeAt(0).cloneRange();
  return true;
}

function insertDocumentCodeBlock() {
  const editor = $('#documentVisualEditor');
  editor.focus();
  if (!restoreDocumentSelection()) placeCaret(editor, false);
  const selection = window.getSelection();
  if (!selection?.rangeCount) return;
  const selectedText = selection.toString();
  const range = selection.getRangeAt(0);
  range.deleteContents();
  const marker = document.createElement('span');
  marker.dataset.documentCodeMarker = 'true';
  range.insertNode(marker);
  const pre = document.createElement('pre');
  const code = document.createElement('code');
  const language = normalizeCodeLanguage($('#documentCodeLanguage')?.value || 'txt');
  code.dataset.language = language;
  const initialCode = selectedText || '在这里输入代码';
  code.innerHTML = syntaxHighlightCode(initialCode, language) || '<br>';
  pre.appendChild(code);
  const nearestBlock = closestEditorBlock(marker, editor);
  let topBlock = nearestBlock;
  while (topBlock !== editor && topBlock.parentElement !== editor) topBlock = topBlock.parentElement;
  if (nearestBlock !== editor && topBlock === nearestBlock) {
    const trailing = document.createRange();
    trailing.setStartAfter(marker);
    trailing.setEnd(nearestBlock, nearestBlock.childNodes.length);
    const remainder = trailing.extractContents();
    marker.remove();
    const after = document.createElement(['P','DIV'].includes(nearestBlock.nodeName) ? nearestBlock.nodeName.toLowerCase() : 'p');
    after.appendChild(remainder);
    if (!after.textContent && !after.querySelector('img,br')) after.appendChild(document.createElement('br'));
    if (!nearestBlock.textContent && !nearestBlock.querySelector('img,br')) nearestBlock.replaceWith(pre);
    else nearestBlock.after(pre);
    pre.after(after);
  } else {
    marker.remove();
    const after = document.createElement('p');
    after.appendChild(document.createElement('br'));
    if (topBlock === editor) editor.append(pre, after);
    else topBlock.after(pre, after);
  }
  const codeRange = document.createRange();
  codeRange.selectNodeContents(code);
  if (selectedText) codeRange.collapse(false);
  selection.removeAllRanges(); selection.addRange(codeRange);
  captureDocumentSelection();
  markDocumentChanged();
}

function renderDocumentTagOptions(selectedTags = []) {
  const selected = new Set(selectedTags || []);
  const tags = configData?.tags || [];
  $('#documentTagOptions').innerHTML = tags.length
    ? tags.map(tag => `<label class="document-tag-option" style="--tag-color:${safeColor(tag.color, '#64748b')}"><input type="checkbox" value="${escapeHtml(tag.name)}" ${selected.has(tag.name) ? 'checked' : ''}><span>${escapeHtml(tag.name)}</span></label>`).join('')
    : '<em>标签管理中还没有标签</em>';
  $('#documentTagOptions').hidden = true;
  updateDocumentTagSummary();
}

function selectedDocumentTags() {
  return $$('#documentTagOptions input:checked').map(input => input.value);
}

let documentColorDefaults = {
  foreColor: localStorage.getItem('workbench-document-text-color') || '#2563eb',
  hiliteColor: localStorage.getItem('workbench-document-background-color') || '#fef9c3',
};

function updateDocumentColorButtons() {
  $$('[data-document-color-apply]').forEach(button => {
    const value = documentColorDefaults[button.dataset.documentColorApply];
    button.style.setProperty('--current-color', ['transparent','inherit'].includes(value) ? 'transparent' : value);
  });
}

function openDocumentColorPalette(trigger, command) {
  const palette = $('#documentColorPalette');
  const clearValue = command === 'hiliteColor' ? 'transparent' : 'inherit';
  const recent = recentColors(`workbench-document-recent-${command}`);
  const swatch = value => `<button type="button" data-document-color-value="${value}" title="${value.toUpperCase()}" aria-label="颜色 ${value}" class="${documentColorDefaults[command] === value ? 'selected' : ''}" style="--swatch:${value}"></button>`;
  palette.dataset.command = command;
  palette.innerHTML = `<div class="document-theme-colors"><button type="button" data-document-color-value="${clearValue}" title="${command === 'hiliteColor' ? '无填充' : '默认色'}" aria-label="${command === 'hiliteColor' ? '无填充' : '默认色'}" class="clear-color ${documentColorDefaults[command] === clearValue ? 'selected' : ''}"></button>${COLOR_THEME_PALETTE.slice(1).map(swatch).join('')}</div><div class="document-shade-colors">${COLOR_SHADE_PALETTE.flat().map(swatch).join('')}</div>${recent.length ? `<span class="color-section-label">最近使用</span><div class="document-recent-colors">${recent.map(swatch).join('')}</div>` : ''}<label class="document-more-color"><input type="color" value="${/^#[0-9a-f]{6}$/i.test(documentColorDefaults[command]) ? documentColorDefaults[command] : '#2563eb'}" data-document-custom-color="${command}"><i></i><span>更多颜色</span><b>›</b></label>`;
  palette.hidden = false;
  const rect = trigger.getBoundingClientRect();
  const width = palette.offsetWidth || 306;
  const height = palette.offsetHeight || 410;
  palette.style.left = `${Math.max(10, Math.min(window.innerWidth - width - 10, rect.left))}px`;
  palette.style.top = `${rect.bottom + height + 10 <= window.innerHeight ? rect.bottom + 7 : Math.max(10, rect.top - height - 7)}px`;
}

function documentColorElement(node, command, editor = $('#documentVisualEditor')) {
  let element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  while (element && element !== editor) {
    const matches = command === 'hiliteColor'
      ? Boolean(element.style?.backgroundColor || element.getAttribute?.('bgcolor'))
      : Boolean(element.style?.color || (element.nodeName === 'FONT' && element.getAttribute('color')));
    if (matches) return element;
    element = element.parentElement;
  }
  return null;
}

function moveCaretOutsideDocumentColor(command) {
  const editor = $('#documentVisualEditor');
  const selection = window.getSelection();
  if (!selection?.rangeCount) return;
  selection.collapseToEnd();
  let probe = selection.focusNode;
  if (probe?.nodeType === Node.ELEMENT_NODE) {
    probe = probe.childNodes[Math.max(0, selection.focusOffset - 1)] || probe;
    while (probe?.lastChild) probe = probe.lastChild;
  }
  const colorElement = documentColorElement(probe, command, editor);
  if (!colorElement || !editor.contains(colorElement)) return;
  const marker = document.createElement('span');
  marker.dataset.documentColorBoundary = command;
  if (command === 'hiliteColor') marker.style.backgroundColor = 'transparent';
  else marker.style.color = 'inherit';
  marker.appendChild(document.createTextNode('\u200b'));
  colorElement.after(marker);
  const range = document.createRange();
  range.setStart(marker.firstChild, 1); range.collapse(true);
  selection.removeAllRanges(); selection.addRange(range);
  documentLastRange = range.cloneRange();
}

function finishDocumentColorBoundaryInput() {
  const selection = window.getSelection();
  if (!selection?.rangeCount) return;
  const marker = (selection.anchorNode?.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode?.parentElement)?.closest?.('[data-document-color-boundary]');
  if (!marker) return;
  const text = marker.firstChild?.nodeType === Node.TEXT_NODE ? marker.firstChild : marker.appendChild(document.createTextNode(''));
  text.data = text.data.replace(/\u200b/g, '');
  marker.removeAttribute('data-document-color-boundary');
  const range = document.createRange();
  range.setStart(text, text.length); range.collapse(true);
  selection.removeAllRanges(); selection.addRange(range);
  documentLastRange = range.cloneRange();
}

function applyDocumentColor(value, command = $('#documentColorPalette').dataset.command || 'foreColor', remember = true) {
  const palette = $('#documentColorPalette');
  const editor = $('#documentVisualEditor');
  editor.focus(); restoreDocumentSelection();
  const selection = window.getSelection();
  const hadSelectedText = Boolean(selection?.rangeCount && !selection.getRangeAt(0).collapsed);
  const clearing = ['transparent','inherit'].includes(value);
  if (clearing && !hadSelectedText) moveCaretOutsideDocumentColor(command);
  else {
    const applied = document.execCommand(command, false, value);
    if (!applied && command === 'hiliteColor') document.execCommand('backColor', false, value);
  }
  if (remember) {
    documentColorDefaults[command] = value;
    localStorage.setItem(command === 'hiliteColor' ? 'workbench-document-background-color' : 'workbench-document-text-color', value);
    rememberRecentColor(`workbench-document-recent-${command}`, value);
    updateDocumentColorButtons();
  }
  palette.hidden = true;
  if (hadSelectedText) moveCaretOutsideDocumentColor(command);
  else captureDocumentSelection();
  markDocumentChanged();
}

function documentDraftKey(documentId = currentDocument?.id || 'new') {
  return `workbench-document-draft:${documentId}`;
}

function clearDocumentDraft(documentId = currentDocument?.id || 'new') {
  try { localStorage.removeItem(documentDraftKey(documentId)); }
  catch { /* 存储受限时仍允许继续编辑 */ }
}

function persistDocumentDraft() {
  if (!documentDirty || !$('#documentDialog')?.open) return;
  try {
    localStorage.setItem(documentDraftKey(), JSON.stringify({
      title:$('#documentTitle').value,
      category:$('#documentCategory').value,
      tags:selectedDocumentTags(),
      body:documentMarkdownContent(),
      savedAt:new Date().toISOString(),
    }));
  } catch { /* 页面离开提示继续兜底 */ }
}

function readDocumentDraft(documentId = currentDocument?.id || 'new') {
  try { return JSON.parse(localStorage.getItem(documentDraftKey(documentId)) || 'null'); }
  catch { return null; }
}

function updateDocumentSaveState(message = '') {
  const state = $('#documentSaveState');
  if (state) state.textContent = message || (documentDirty ? '● 有未保存的修改' : '✓ 已保存');
  if (state) state.classList.toggle('saving', documentDirty || documentSaving || /正在|失败/.test(message));
  const button = $('#saveDocument');
  if (button) button.disabled = !documentDirty || documentSaving;
}

function markDocumentChanged() {
  documentDirty = true;
  persistDocumentDraft();
  updateDocumentSaveState();
  updateDocumentToolbarState();
  scheduleDocumentOutlineUpdate();
}

function updateDocumentToolbarState() {
  const editor = $('#documentVisualEditor');
  const selection = selectionInsideEditor(editor);
  if (!selection) return;
  $$('[data-document-command]', $('#documentFormatToolbar')).forEach(button => {
    const command = button.dataset.documentCommand;
    if (['bold','italic','underline','strikeThrough','insertUnorderedList','insertOrderedList','justifyLeft','justifyCenter','justifyRight'].includes(command)) {
      try { button.setAttribute('aria-pressed', String(document.queryCommandState(command))); } catch { button.setAttribute('aria-pressed', 'false'); }
    }
  });
  const block = closestEditorBlock(selection.anchorNode, editor);
  const heading = ['H1','H2','H3','H4'].includes(block.nodeName) ? block.nodeName.toLowerCase() : 'p';
  $('#documentHeading').value = heading;
  const code = block.nodeName === 'PRE' ? block.querySelector('code') : block.closest?.('pre')?.querySelector('code');
  const codeLanguage = normalizeCodeLanguage(code?.dataset.language || 'txt');
  if (code && [...$('#documentCodeLanguage').options].some(option => option.value === codeLanguage)) $('#documentCodeLanguage').value = codeLanguage;
  const quoteButton = $('[data-document-block="blockquote"]', $('#documentFormatToolbar'));
  if (quoteButton) quoteButton.setAttribute('aria-pressed', String(Boolean(block.closest?.('blockquote'))));
}

function handleDocumentTaskListEnter(event) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return false;
  const editor = event.currentTarget;
  const selection = selectionInsideEditor(editor);
  if (!selection?.isCollapsed) return false;
  const element = selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement;
  const item = element?.closest('li.task-item');
  if (!item) return false;
  event.preventDefault();
  const list = item.parentElement;
  if (!(item.textContent || '').trim()) {
    const paragraph = document.createElement('p'); paragraph.innerHTML = '<br>';
    const anchor = list;
    item.remove();
    anchor.after(paragraph);
    if (!anchor.children.length) anchor.remove();
    placeCaret(paragraph);
  } else {
    const range = selection.getRangeAt(0);
    const tailRange = document.createRange();
    tailRange.setStart(range.startContainer, range.startOffset);
    tailRange.setEnd(item, item.childNodes.length);
    const tail = tailRange.extractContents();
    const next = document.createElement('li'); next.className = 'task-item';
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox';
    next.append(checkbox, document.createTextNode(' '), tail);
    item.after(next); placeCaret(next, false);
  }
  markDocumentChanged();
  return true;
}

function updateDocumentTagSummary() {
  const selected = selectedDocumentTags();
  $('#documentSelectedTags').innerHTML = selected.map(name => {
    const color = safeColor((configData?.tags || []).find(tag => tag.name === name)?.color, '#64748b');
    return `<button type="button" class="document-selected-tag" data-remove-document-tag="${escapeHtml(name)}" style="--tag-color:${color}" title="移除标签"><i></i>${escapeHtml(name)}<b>×</b></button>`;
  }).join('');
  $('#toggleDocumentTags').textContent = selected.length ? `＋ 继续选择 (${selected.length})` : '＋ 选择标签';
}

function updateDocumentSelectionToolbar() {
  const toolbar = $('#documentSelectionToolbar');
  const selection = window.getSelection();
  if (documentMode !== 'visual' || !selection?.rangeCount || !$('#documentVisualEditor').contains(selection.anchorNode)) {
    toolbar.classList.remove('visible'); toolbar.setAttribute('aria-hidden', 'true'); return;
  }
  documentLastRange = selection.getRangeAt(0).cloneRange();
  if (selection.isCollapsed) {
    toolbar.classList.remove('visible'); toolbar.setAttribute('aria-hidden', 'true'); return;
  }
  const rect = documentLastRange.getBoundingClientRect();
  const width = toolbar.offsetWidth || 310;
  toolbar.style.left = `${Math.max(12, Math.min(window.innerWidth - width - 12, rect.left + rect.width / 2 - width / 2))}px`;
  toolbar.style.top = `${Math.max(12, rect.top - 50)}px`;
  toolbar.classList.add('visible'); toolbar.setAttribute('aria-hidden', 'false');
}

function openDocument(documentId = '') {
  currentDocument = documents.find(item => item.id === documentId) || null;
  documentDirty = false;
  documentSaving = false;
  const draft = readDocumentDraft(currentDocument?.id || 'new');
  const base = {title:currentDocument?.title || '', category:currentDocument?.category || '', tags:currentDocument?.tags || [], body:currentDocument?.body || ''};
  const hasRecoveryDraft = Boolean(draft && (draft.title !== base.title || draft.category !== base.category || draft.body !== base.body || JSON.stringify(draft.tags || []) !== JSON.stringify(base.tags || [])));
  const content = hasRecoveryDraft ? {...base, ...draft} : base;
  if (draft && !hasRecoveryDraft) clearDocumentDraft(currentDocument?.id || 'new');
  documentDirty = hasRecoveryDraft;
  $('#documentDialogTitle').textContent = currentDocument ? currentDocument.title : '新建文档';
  $('#documentTitle').value = content.title;
  $('#documentCategory').value = content.category;
  renderDocumentTagOptions(content.tags || []);
  $('#documentBody').value = content.body;
  $('#documentVisualEditor').innerHTML = markdownToHtml(content.body || '', true);
  $('#documentCategoryOptions').innerHTML = [...new Set([...(configData?.document_categories || []), ...documents.map(item => item.category).filter(Boolean)])].map(value => `<option value="${escapeHtml(value)}"></option>`).join('');
  $('#deleteDocument').style.display = currentDocument ? '' : 'none';
  $('#exportDocument').style.display = currentDocument ? '' : 'none';
  $('.document-external-editor').style.display = currentDocument ? 'inline-flex' : 'none';
  updateDocumentSaveState(documentDirty ? '' : currentDocument ? `✓ 已保存 · ${new Date(currentDocument.updated).toLocaleString('zh-CN')}` : '将保存为本地 Markdown');
  documentExpanded = false;
  $('#documentDialog').classList.remove('expanded');
  $('#documentDialog').classList.toggle('outline-collapsed', documentOutlineCollapsed);
  $('#toggleDocumentExpand span').textContent = '展开编辑';
  setDocumentMode(currentDocument ? 'read' : 'visual');
  $('#documentDialog').showModal();
  requestAnimationFrame(updateDocumentOutline);
  if (!currentDocument) setTimeout(() => $('#documentTitle').focus(), 30);
  if (hasRecoveryDraft) notify('已恢复未保存的文档草稿', '草稿尚未写入 Markdown，请检查后手动保存');
}

async function saveDocument({readAfterSave = false, notifyUser = true} = {}) {
  if (documentSaving) return null;
  if (!documentDirty && currentDocument) return currentDocument;
  const title = $('#documentTitle').value.trim();
  if (!title) { $('#documentTitle').focus(); notify('文档标题不能为空', '请输入标题后再保存', true); return null; }
  const payload = {title, category:$('#documentCategory').value.trim() || '未分类', tags:selectedDocumentTags(), body:documentMarkdownContent()};
  const previousDraftId = currentDocument?.id || 'new';
  documentSaving = true;
  updateDocumentSaveState('正在保存…');
  try {
    const saved = await api(currentDocument ? `/documents/${encodeURIComponent(currentDocument.id)}` : '/documents', {method:currentDocument ? 'PATCH' : 'POST', body:JSON.stringify(payload)});
    currentDocument = saved;
    documentDirty = false;
    clearDocumentDraft(previousDraftId);
    clearDocumentDraft(saved.id);
    documents = await api('/documents');
    renderDocumentsPage();
    if (readAfterSave) setDocumentMode('read');
    $('#documentDialogTitle').textContent = saved.title;
    $('#documentOutlineTitle').textContent = saved.title;
    $('#deleteDocument').style.display = '';
    $('#exportDocument').style.display = '';
    $('.document-external-editor').style.display = 'inline-flex';
    updateDocumentSaveState('✓ 已保存 · 刚刚');
    if (notifyUser) notify('文档已保存', saved.category);
    return saved;
  } catch (error) {
    documentDirty = true;
    persistDocumentDraft();
    updateDocumentSaveState('保存失败，请重试');
    notify('文档保存失败', error.message, true);
    return null;
  } finally {
    documentSaving = false;
    updateDocumentSaveState($('#documentSaveState').textContent);
  }
}

async function openCurrentDocumentExternal() {
  if (!currentDocument) return;
  if (documentDirty && !await saveDocument({readAfterSave:false, notifyUser:false})) return;
  const button = $('#openDocumentExternal');
  const label = $('#documentExternalEditorLabel');
  const original = label.textContent;
  button.disabled = true; label.textContent = '正在打开…';
  try {
    const result = await api(`/documents/${encodeURIComponent(currentDocument.id)}/open-external`, {method:'POST'});
    notify(`已使用${result.editor}打开`, `${result.file} · 外部保存后工作台会自动检测修改`);
  } catch (error) { notify('无法打开外部编辑器', error.message, true); }
  finally { button.disabled = false; label.textContent = original; }
}

function documentHasUnsavedChanges() {
  return documentDirty;
}

async function closeDocumentEditor() {
  if (documentHasUnsavedChanges()) {
    const choice = await askUnsavedChanges(`文档「${$('#documentTitle').value.trim() || '未命名文档'}」`);
    if (choice === 'cancel') return false;
    if (choice === 'save' && !await saveDocument({readAfterSave:false, notifyUser:false})) return false;
    if (choice === 'discard') { clearDocumentDraft(); documentDirty = false; }
  }
  $('#documentDialog').close();
  $('#documentColorPalette').hidden = true;
  documentLastRange = null;
  return true;
}

function reloadCurrentDocumentFromDisk(latest) {
  if (!latest || !currentDocument || latest.id !== currentDocument.id) return;
  currentDocument = latest;
  documentDirty = false;
  clearDocumentDraft(latest.id);
  $('#documentDialogTitle').textContent = latest.title;
  $('#documentTitle').value = latest.title;
  $('#documentCategory').value = latest.category || '';
  renderDocumentTagOptions(latest.tags || []);
  $('#documentBody').value = latest.body || '';
  $('#documentVisualEditor').innerHTML = markdownToHtml(latest.body || '', true);
  if (documentMode === 'read') $('#documentReadPane').innerHTML = markdownToHtml(latest.body || '');
  scheduleDocumentOutlineUpdate();
  updateDocumentSaveState(`✓ 已同步外部修改 · ${new Date(latest.updated).toLocaleTimeString('zh-CN')}`);
  delete $('#documentDialog').dataset.pendingExternalMtime;
  notify('已同步外部 Markdown 修改', latest.title);
}

async function deleteDocument() {
  if (!currentDocument || !await appConfirm({title:'将文档移入回收站？', message:`「${currentDocument.title}」`, detail:'稍后可以在回收站中恢复。', confirmText:'移入回收站', danger:true})) return;
  try {
    await api(`/documents/${encodeURIComponent(currentDocument.id)}`, {method:'DELETE'});
    clearDocumentDraft(currentDocument.id); documentDirty = false;
    $('#documentDialog').close(); currentDocument = null; documents = await api('/documents'); renderDocumentsPage(); notify('文档已移入回收站');
  } catch (error) { notify('文档删除失败', error.message, true); }
}

function downloadKnowledgeFile(path) {
  const link = document.createElement('a');
  link.href = `/api${path}`;
  link.download = '';
  document.body.appendChild(link);
  link.click();
  link.remove();
}

async function exportSelectedDocuments() {
  const documentIds = [...documentSelection];
  if (!documentIds.length) return;
  try {
    const response = await fetch('/api/documents/export', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({document_ids:documentIds})});
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || `导出失败 (${response.status})`);
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a'); link.href = url; link.download = 'knowledge-documents.zip'; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify(`正在导出 ${documentIds.length} 篇文档`, '所选文档将打包为 ZIP');
    documentSelection.clear(); documentExportMode = false; renderDocumentsPage();
  } catch (error) { notify('文档导出失败', error.message, true); }
}

async function importKnowledgeDocuments(files) {
  const markdownFiles = [...files].filter(file => file.name.toLowerCase().endsWith('.md'));
  if (!markdownFiles.length) return notify('没有可导入的 Markdown 文档', '请选择 .md 文件', true);
  let imported = 0;
  try {
    for (const file of markdownFiles) {
      await api('/documents/import', {method:'POST', body:JSON.stringify({name:file.name, content:await file.text()})});
      imported += 1;
    }
    documents = await api('/documents');
    renderDocumentsPage();
    notify(`已导入 ${imported} 篇文档`, '分类会优先读取 Markdown 元数据，也可以在编辑时自定义');
  } catch (error) {
    documents = await api('/documents'); renderDocumentsPage();
    notify('文档导入未全部完成', `${imported ? `已导入 ${imported} 篇；` : ''}${error.message}`, true);
  }
}

function renderTrashPage() {
  const selectedCount = trashSelection.size;
  $('#manageActions').innerHTML = trashItems.length ? `<span class="trash-selection-count" id="trashSelectionCount">已选择 ${selectedCount} 项</span><button class="secondary-button" id="batchRestoreTrash" ${selectedCount ? '' : 'disabled'}>批量恢复</button><button class="secondary-button danger-button" id="batchPurgeTrash" ${selectedCount ? '' : 'disabled'}>批量永久删除</button>` : '';
  $('#manageContent').innerHTML = trashItems.length ? `<div class="trash-table-wrap"><table class="data-table trash-table"><thead><tr><th class="trash-select-cell"><input type="checkbox" id="selectAllTrash" aria-label="全选回收站内容" ${selectedCount === trashItems.length ? 'checked' : ''}></th><th>名称</th><th>类型</th><th>删除时间</th><th>操作</th></tr></thead><tbody>${trashItems.map(item => `<tr data-trash-row="${escapeHtml(item.token)}" class="${trashSelection.has(item.token) ? 'selected' : ''}"><td class="trash-select-cell"><input type="checkbox" data-trash-select="${escapeHtml(item.token)}" aria-label="选择 ${escapeHtml(item.title)}" ${trashSelection.has(item.token) ? 'checked' : ''}></td><td><strong>${escapeHtml(item.title)}</strong><br><small>${escapeHtml(item.id)}</small></td><td>${item.kind === 'project' ? '项目' : item.kind === 'document' ? '文档' : item.kind === 'concept-map' ? '概念图' : '记录'}</td><td>${new Date(item.deleted_at).toLocaleString('zh-CN')}</td><td class="trash-row-actions"><button class="secondary-button" data-restore-trash="${escapeHtml(item.token)}">恢复</button><button class="secondary-button danger-button" data-purge-trash="${escapeHtml(item.token)}">永久删除</button></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty-state">回收站为空</div>';
  updateTrashSelectionUI();
}

function updateTrashSelectionUI() {
  const count = trashSelection.size;
  const selectAll = $('#selectAllTrash');
  if (selectAll) {
    selectAll.checked = Boolean(trashItems.length) && count === trashItems.length;
    selectAll.indeterminate = count > 0 && count < trashItems.length;
  }
  if ($('#trashSelectionCount')) $('#trashSelectionCount').textContent = `已选择 ${count} 项`;
  if ($('#batchRestoreTrash')) $('#batchRestoreTrash').disabled = !count;
  if ($('#batchPurgeTrash')) $('#batchPurgeTrash').disabled = !count;
  $$('[data-trash-row]').forEach(row => row.classList.toggle('selected', trashSelection.has(row.dataset.trashRow)));
}

async function batchRestoreTrash() {
  const tokens = [...trashSelection];
  if (!tokens.length) return;
  try {
    const result = await api('/trash/batch/restore', {method:'POST', body:JSON.stringify({tokens})});
    trashSelection.clear();
    await refreshData();
    await renderManagePage('trash');
    notify(`已恢复 ${result.count} 项内容`);
  } catch (error) { notify('批量恢复失败', error.message, true); }
}

async function batchPurgeTrash() {
  const tokens = [...trashSelection];
  if (!tokens.length || !await appConfirm({title:`永久删除所选 ${tokens.length} 项？`, message:'此操作无法撤销，删除后不能从回收站恢复。', confirmText:'批量永久删除', danger:true})) return;
  try {
    const result = await api('/trash/batch', {method:'DELETE', body:JSON.stringify({tokens})});
    trashSelection.clear();
    await renderManagePage('trash');
    notify(`已永久删除 ${result.count} 项内容`);
  } catch (error) { notify('批量删除失败', error.message, true); }
}

function tagUsageRecords(tagName) {
  return [
    ...records.filter(record => (record.tags || []).includes(tagName)),
    ...documents.filter(item => (item.tags || []).includes(tagName)).map(item => ({...item, type:'document'})),
  ];
}

function statusUsageRecords(recordType, statusName, statusId = '') {
  const workflow = (configData?.workflow_templates || []).find(item => item.id === selectedWorkflowId);
  const originalName = workflow?.statuses?.[recordType]?.find(item => item.id === statusId)?.name || statusName;
  return records.filter(record => record.type === recordType && record.status === originalName && workflowForProject(record.project_id)?.id === selectedWorkflowId);
}

function statusTemplateColor(recordType, statusId, statusName) {
  const workflow = (configData?.workflow_templates || []).find(item => item.id === selectedWorkflowId);
  return safeColor(workflow?.statuses?.[recordType]?.find(item => item.id === statusId || item.name === statusName)?.color);
}

function usageRecordRowsHtml(items) {
  return items.length ? `<div class="usage-record-list">${items.map(record => `<button type="button" class="usage-record-row" ${record.type === 'document' ? `data-usage-document="${escapeHtml(record.id)}"` : `data-usage-record="${escapeHtml(record.id)}"`}><span class="type-icon ${escapeHtml(record.type)}">${record.type === 'document' ? '▤' : escapeHtml(typeIcons[record.type] || '•')}</span><span><strong>${escapeHtml(record.title)}</strong><small>${escapeHtml(record.id)} · ${record.type === 'document' ? `知识库文档 · ${escapeHtml(record.category || '未分类')}` : `${escapeHtml(typeNames[record.type] || record.type)} · ${escapeHtml(projectName(record.project_id))}${record.status ? ` · ${escapeHtml(record.status)}` : ''}`}</small></span><em>打开</em></button>`).join('')}</div>` : '<div class="usage-empty"><span>✓</span><strong>暂无内容使用</strong><small>当前可以安全删除这项配置</small></div>';
}

function updateRecordBackButton() {
  const button = $('#recordBack');
  const returnsToUsage = recordNavigationStack.length === 0 && Boolean(usageReturnContext);
  button.classList.toggle('available', recordNavigationStack.length > 0 || Boolean(usageReturnContext));
  button.classList.toggle('usage-return', returnsToUsage);
  button.innerHTML = returnsToUsage ? '<span aria-hidden="true">←</span><b>使用统计</b>' : '←';
  const label = returnsToUsage ? '返回使用统计' : '返回上一条记录';
  button.setAttribute('aria-label', label);
  button.title = label;
}

function updateUsageDialogBackButton() {
  const button = $('#usageDialogBack');
  const hasParent = usageNavigationStack.length > 0;
  const available = hasParent || currentUsageView?.view === 'detail';
  button.classList.toggle('available', available);
  button.tabIndex = available ? 0 : -1;
  const destination = hasParent ? '使用统计' : currentUsageView?.kind === 'status' ? '状态模板' : '标签管理';
  button.setAttribute('aria-label', `返回${destination}`);
  button.title = `返回${destination}`;
}

function openUsageDetail({kind, name, recordType = '', statusId = ''}, options = {}) {
  if (!options.preserveStack) usageNavigationStack = [];
  currentUsageView = {view:'detail', kind, name, recordType, statusId};
  const items = kind === 'tag' ? tagUsageRecords(name) : statusUsageRecords(recordType, name, statusId);
  $('#usageDialogEyebrow').textContent = kind === 'tag' ? '标签使用情况' : `${typeNames[recordType] || recordType}状态使用情况`;
  $('#usageDialogTitle').textContent = `「${name}」`;
  $('#usageDialogSummary').innerHTML = `<strong>${items.length}</strong><span>条内容正在使用</span>${items.length ? '<small>需要先在下列记录或文档中移除或更改，才能删除此配置。</small>' : '<small>这项配置目前未被使用，可以安全删除。</small>'}`;
  $('#usageDialogContent').innerHTML = usageRecordRowsHtml(items);
  updateUsageDialogBackButton();
  if (!$('#usageDialog').open) $('#usageDialog').showModal();
}

function openUsageOverview(kind, options = {}) {
  if (!options.preserveStack) usageNavigationStack = [];
  currentUsageView = {view:'overview', kind};
  const isTag = kind === 'tag';
  const items = isTag
    ? $$('.tag-edit').map(row => { const name = row.dataset.originalName || $('input[type="text"]', row).value.trim(); return {name, count:tagUsageRecords(name).length}; })
    : $$('.status-edit-row').map(row => { const recordType = row.closest('.template-panel').dataset.templateType; const name = $('input[type="text"]', row).value.trim(); const statusId = row.dataset.statusId || ''; return {name, recordType, statusId, count:statusUsageRecords(recordType, name, statusId).length}; });
  const totalUsage = items.reduce((sum, item) => sum + item.count, 0);
  $('#usageDialogEyebrow').textContent = isTag ? '标签使用统计' : '状态使用统计';
  $('#usageDialogTitle').textContent = isTag ? '全部标签' : '当前工作流状态';
  $('#usageDialogSummary').innerHTML = `<strong>${items.length}</strong><span>项配置</span><small>合计 ${totalUsage} 次内容引用；点击任一项查看具体记录或文档。</small>`;
  $('#usageDialogContent').innerHTML = `<div class="usage-overview-list">${items.map(item => `<button type="button" data-usage-detail-kind="${kind}" data-usage-detail-name="${escapeHtml(item.name)}" ${item.recordType ? `data-usage-detail-type="${escapeHtml(item.recordType)}" data-usage-detail-status-id="${escapeHtml(item.statusId)}"` : ''}><span><i style="background:${isTag ? tagColor(item.name) : statusTemplateColor(item.recordType, item.statusId, item.name)}"></i><strong>${escapeHtml(item.name)}</strong>${item.recordType ? `<small>${escapeHtml(typeNames[item.recordType] || item.recordType)}</small>` : ''}</span><em class="${item.count ? 'in-use' : ''}">${item.count} 条</em><b>查看 ›</b></button>`).join('') || '<div class="usage-empty"><strong>暂无配置</strong></div>'}</div>`;
  updateUsageDialogBackButton();
  if (!$('#usageDialog').open) $('#usageDialog').showModal();
}

function returnWithinUsageDialog() {
  const previous = usageNavigationStack.pop();
  if (!previous) { closeUsageDialog(); return; }
  if (previous.view === 'overview') openUsageOverview(previous.kind, {preserveStack:true});
  else openUsageDetail(previous, {preserveStack:true});
  requestAnimationFrame(() => { $('#usageDialogContent').scrollTop = previous.scrollTop || 0; });
}

function closeUsageDialog() {
  currentUsageView = null;
  usageNavigationStack = [];
  usageReturnContext = null;
  $('#usageDialog').close('cancel');
}

function tagEditorHtml(tag) {
  const usageName = tag.original_name ?? tag.name ?? '';
  const originalColor = safeColor(tag.color || '#64748b');
  const count = usageName ? tagUsageRecords(usageName).length : 0;
  const actions = usageName
    ? `<button type="button" class="usage-button tag-usage-button ${count ? 'in-use' : ''}" title="查看使用此标签的记录">${count} 条</button><button class="remove-global-tag" aria-label="删除标签" title="删除标签">✕</button>`
    : '<button type="button" class="tag-row-save" data-save-tag-row title="保存新标签">保存</button><button type="button" class="tag-row-cancel" data-cancel-tag-row title="取消新建">取消</button>';
  return `<div class="tag-edit ${usageName ? '' : 'tag-row-dirty'}" data-original-name="${escapeHtml(usageName)}" data-original-color="${originalColor}"><label class="tag-select" title="选择标签"><input type="checkbox" data-tag-select aria-label="选择标签 ${escapeHtml(tag.name)}"><span></span></label>${colorPickerHtml(originalColor, '标签颜色')}<input type="text" value="${escapeHtml(tag.name)}" aria-label="标签名称"><div class="tag-edit-actions">${actions}</div></div>`;
}

function updateTagBatchUI() {
  const inputs = $$('[data-tag-select]');
  const selected = inputs.filter(input => input.checked);
  const selectAll = $('#selectAllTags');
  if (selectAll) {
    selectAll.checked = Boolean(inputs.length) && selected.length === inputs.length;
    selectAll.indeterminate = selected.length > 0 && selected.length < inputs.length;
  }
  if ($('#tagSelectionCount')) $('#tagSelectionCount').textContent = `已选择 ${selected.length} 个标签`;
  if ($('#batchDeleteTags')) $('#batchDeleteTags').disabled = !selected.length;
}

async function deleteSelectedTags() {
  const rows = $$('[data-tag-select]:checked').map(input => input.closest('.tag-edit'));
  if (!rows.length) return;
  const blocked = rows.filter(row => tagUsageRecords(row.dataset.originalName || $('input[type="text"]', row).value.trim()).length);
  const removable = rows.filter(row => !blocked.includes(row));
  if (!removable.length) {
    notify('所选标签均在使用中', '请先从相关记录或知识库文档中移除引用', true);
    return;
  }
  const names = removable.map(row => row.dataset.originalName || $('input[type="text"]', row).value.trim()).filter(Boolean);
  const detail = blocked.length ? `另有 ${blocked.length} 个正在使用的标签将被跳过。` : '删除后会立即更新标签库，此操作无法撤销。';
  if (!await appConfirm({title:`删除所选 ${removable.length} 个标签？`, message:names.join('、'), detail, confirmText:'批量删除', danger:true})) return;
  removable.forEach(row => row.remove());
  await saveTags();
}

function updateTagRowDirtyState(row) {
  if (!row) return;
  const originalName = row.dataset.originalName || '';
  const originalColor = (row.dataset.originalColor || '#64748b').toLowerCase();
  const name = $('input[type="text"]', row).value;
  const color = $('input[type="color"]', row).value.toLowerCase();
  const dirty = !originalName || name !== originalName || color !== originalColor;
  row.classList.toggle('tag-row-dirty', dirty);
  const actions = $('.tag-edit-actions', row);
  if (!actions) return;
  if (dirty) {
    actions.innerHTML = '<button type="button" class="tag-row-save" data-save-tag-row title="保存此标签修改">保存</button><button type="button" class="tag-row-cancel" data-cancel-tag-row title="取消此标签修改">取消</button>';
    return;
  }
  const count = tagUsageRecords(originalName).length;
  actions.innerHTML = `<button type="button" class="usage-button tag-usage-button ${count ? 'in-use' : ''}" title="查看使用此标签的记录">${count} 条</button><button class="remove-global-tag" aria-label="删除标签" title="删除标签">✕</button>`;
}

async function saveTags() {
  const rows = $$('.tag-edit');
  const tags = rows.map(row => ({name:$('input[type="text"]', row).value.trim(), color:$('input[type="color"]', row).value, original:row.dataset.originalName})).filter(item => item.name);
  const renames = Object.fromEntries(tags.filter(item => item.original && item.original !== item.name).map(item => [item.original,item.name]));
  const remainingOriginals = new Set(tags.map(item => item.original).filter(Boolean));
  const removed = (configData.tags || []).map(item => item.name).filter(name => !remainingOriginals.has(name) && !renames[name]);
  try {
    configData.tags = await api('/tags', {method:'PUT', body:JSON.stringify({tags:tags.map(({name,color}) => ({name,color})), renames, removed})});
    const [recordsResult, documentsResult] = await Promise.allSettled([api('/records?summary=1'), api('/documents')]);
    if (recordsResult.status === 'fulfilled') {
      records = recordsResult.value.filter(record => record.type !== 'idea');
      lastRecordSignature = recordSignature(records);
    }
    if (documentsResult.status === 'fulfilled') documents = documentsResult.value;
    if (activeManagePage === 'tags') {
      const savedByName = new Map(configData.tags.map(tag => [tag.name, tag]));
      const seen = new Set();
      $$('.tag-edit').forEach(row => {
        const name = $('input[type="text"]', row).value.trim();
        const saved = savedByName.get(name);
        if (!saved || seen.has(saved.name)) { row.remove(); return; }
        seen.add(saved.name);
        row.dataset.originalName = saved.name;
        row.dataset.originalColor = safeColor(saved.color || '#64748b');
        $('input[type="text"]', row).value = saved.name;
        syncColorPicker($('[data-color-picker]', row), row.dataset.originalColor);
        row.classList.remove('new-config-row');
        updateTagRowDirtyState(row);
      });
      const addButton = $('#addGlobalTag');
      configData.tags.filter(tag => !seen.has(tag.name)).forEach(tag => addButton?.insertAdjacentHTML('beforebegin', tagEditorHtml(tag)));
      updateTagBatchUI();
      captureManageSnapshot('tags');
    }
    notify('标签库已保存', '标签重命名、合并或删除已同步到记录和知识库文档');
    return true;
  }
  catch (error) { notify('标签保存失败', error.message, true); return false; }
}

function statusEditorHtml(status, recordType = '', options = {}) {
  const count = recordType ? statusUsageRecords(recordType, status.name, status.id).length : 0;
  const color = safeColor(status.color || '#64748b');
  const actions = options.newItem
    ? '<button type="button" class="status-row-save" data-save-status-row title="保存新状态">保存</button><button type="button" class="status-row-cancel" data-cancel-status-row title="取消新建">取消</button>'
    : `<button type="button" class="usage-button status-usage-button ${count ? 'in-use' : ''}" title="查看使用此状态的记录">${count} 条</button><button class="remove-status" aria-label="删除状态" title="删除状态">✕</button>`;
  return `<div class="status-edit-row ${options.newItem ? 'status-row-dirty' : ''}" data-status-id="${escapeHtml(status.id)}" data-original-name="${escapeHtml(options.newItem ? '' : status.name)}" data-original-color="${color}" data-original-completed="${Boolean(status.completed)}"><label class="status-select" title="选择状态"><input type="checkbox" data-status-select aria-label="选择状态 ${escapeHtml(status.name)}"><span></span></label>${colorPickerHtml(color, '状态颜色')}<input type="text" value="${escapeHtml(status.name)}" aria-label="状态名称"><label class="status-completed-label" title="完成状态"><input class="status-completed" type="checkbox" ${status.completed ? 'checked' : ''}></label><div class="status-edit-actions">${actions}</div></div>`;
}

function updateStatusRowDirtyState(row) {
  if (!row) return;
  const dirty = !row.dataset.originalName
    || $('input[type="text"]', row).value !== row.dataset.originalName
    || $('input[type="color"]', row).value.toLowerCase() !== (row.dataset.originalColor || '#64748b').toLowerCase()
    || $('.status-completed', row).checked !== (row.dataset.originalCompleted === 'true');
  row.classList.toggle('status-row-dirty', dirty);
  const actions = $('.status-edit-actions', row);
  if (!actions) return;
  if (dirty) {
    actions.innerHTML = '<button type="button" class="status-row-save" data-save-status-row title="保存此状态修改">保存</button><button type="button" class="status-row-cancel" data-cancel-status-row title="取消此状态修改">取消</button>';
    return;
  }
  const type = row.closest('.template-panel')?.dataset.templateType || '';
  const count = statusUsageRecords(type, row.dataset.originalName, row.dataset.statusId || '').length;
  actions.innerHTML = `<button type="button" class="usage-button status-usage-button ${count ? 'in-use' : ''}" title="查看使用此状态的记录">${count} 条</button><button class="remove-status" aria-label="删除状态" title="删除状态">✕</button>`;
}

function updateStatusBatchUI() {
  const inputs = $$('[data-status-select]');
  const selected = inputs.filter(input => input.checked);
  const selectAll = $('#selectAllStatuses');
  if (selectAll) { selectAll.checked = Boolean(inputs.length) && selected.length === inputs.length; selectAll.indeterminate = selected.length > 0 && selected.length < inputs.length; }
  if ($('#statusSelectionCount')) $('#statusSelectionCount').textContent = `已选择 ${selected.length} 个状态`;
  if ($('#batchDeleteStatuses')) $('#batchDeleteStatuses').disabled = !selected.length;
}

async function deleteSelectedStatuses() {
  const rows = $$('[data-status-select]:checked').map(input => input.closest('.status-edit-row'));
  if (!rows.length) return;
  const usage = row => statusUsageRecords(row.closest('.template-panel')?.dataset.templateType, row.dataset.originalName || $('input[type="text"]', row).value.trim(), row.dataset.statusId || '');
  const blocked = rows.filter(row => usage(row).length);
  const removable = rows.filter(row => !blocked.includes(row));
  if (!removable.length) { notify('所选状态均在使用中', '请先把相关记录移动到其他状态', true); return; }
  const names = removable.map(row => $('input[type="text"]', row).value.trim()).filter(Boolean);
  const detail = blocked.length ? `另有 ${blocked.length} 个正在使用的状态将被跳过。` : '删除后会立即更新当前工作流，此操作无法撤销。';
  if (!await appConfirm({title:`删除所选 ${removable.length} 个状态？`, message:names.join('、'), detail, confirmText:'批量删除', danger:true})) return;
  removable.forEach(row => row.remove());
  await saveTemplates();
}

function colorPickerHtml(color, label) {
  const value = /^#[0-9a-f]{6}$/i.test(color || '') ? color.toLowerCase() : '#64748b';
  const recent = recentColors('workbench-recent-management-colors');
  const swatch = colorValue => `<button type="button" data-color-value="${colorValue}" aria-label="颜色 ${colorValue}" title="${colorValue.toUpperCase()}"><i style="background:${colorValue}"></i></button>`;
  return `<div class="color-picker" data-color-picker><button type="button" class="color-picker-trigger" aria-label="选择${escapeHtml(label)}" aria-expanded="false" title="${escapeHtml(label)}：${value}"><i style="background:${value}"></i></button><div class="color-picker-popover" role="dialog" aria-label="${escapeHtml(label)}选项"><div class="color-palette color-theme-palette">${COLOR_THEME_PALETTE.map(swatch).join('')}</div><div class="color-palette color-shade-palette">${COLOR_SHADE_PALETTE.flat().map(swatch).join('')}</div>${recent.length ? `<span class="color-section-label">最近使用</span><div class="color-palette color-recent-palette">${recent.map(swatch).join('')}</div>` : ''}<label class="custom-color-row"><input type="color" value="${value}" aria-label="自定义${escapeHtml(label)}"><i></i><span>更多颜色</span><code>${value.toUpperCase()}</code><b>›</b></label></div></div>`;
}

function syncColorPicker(picker, value) {
  if (!picker) return;
  const normalized = value.toLowerCase();
  const input = $('input[type="color"]', picker);
  input.value = normalized;
  $('.color-picker-trigger i', picker).style.background = normalized;
  $('.color-picker-trigger', picker).title = `${input.getAttribute('aria-label').replace(/^自定义/, '')}：${normalized}`;
  $('code', picker).textContent = normalized.toUpperCase();
  $$('[data-color-value]', picker).forEach(button => button.classList.toggle('selected', button.dataset.colorValue === normalized));
}

async function saveTemplates() {
  const workflow = configData.workflow_templates.find(item => item.id === selectedWorkflowId);
  const statuses = {idea:workflow?.statuses?.idea || []};
  $$('.template-panel').forEach(panel => {
    statuses[panel.dataset.templateType] = $$('.status-edit-row', panel).map((row, index) => ({id:row.dataset.statusId || `${panel.dataset.templateType}_${Date.now()}_${index}`, name:$('input[type="text"]', row).value.trim(), color:$('input[type="color"]', row).value, completed:$('.status-completed', row).checked})).filter(item => item.name);
  });
  try {
    workflow.statuses = statuses;
    configData.workflow_templates = await api('/workflow-templates', {method:'PUT', body:JSON.stringify(configData.workflow_templates)});
    const recordsResult = await Promise.allSettled([api('/records?summary=1')]);
    if (recordsResult[0].status === 'fulfilled') {
      records = recordsResult[0].value.filter(record => record.type !== 'idea');
      lastRecordSignature = recordSignature(records);
    }
    if (activeManagePage === 'status_templates') {
      const savedWorkflow = configData.workflow_templates.find(item => item.id === selectedWorkflowId);
      $$('.template-panel').forEach(panel => {
        const savedStatuses = savedWorkflow?.statuses?.[panel.dataset.templateType] || [];
        const savedById = new Map(savedStatuses.map(status => [status.id, status]));
        const seen = new Set();
        $$('.status-edit-row', panel).forEach(row => {
          const saved = savedById.get(row.dataset.statusId);
          if (!saved || seen.has(saved.id)) { row.remove(); return; }
          seen.add(saved.id);
          row.dataset.originalName = saved.name;
          row.dataset.originalColor = safeColor(saved.color || '#64748b');
          row.dataset.originalCompleted = String(Boolean(saved.completed));
          $('input[type="text"]', row).value = saved.name;
          $('.status-completed', row).checked = Boolean(saved.completed);
          syncColorPicker($('[data-color-picker]', row), row.dataset.originalColor);
          row.classList.remove('new-config-row');
          updateStatusRowDirtyState(row);
        });
        const list = $('.status-edit-list', panel);
        savedStatuses.filter(status => !seen.has(status.id)).forEach(status => list?.insertAdjacentHTML('beforeend', statusEditorHtml(status, panel.dataset.templateType)));
        $('.count-badge', panel).textContent = savedStatuses.length;
      });
      updateStatusBatchUI();
      captureManageSnapshot('status_templates');
    }
    notify('工作流已保存', '使用此模板的项目会立即采用新状态');
    return true;
  } catch (error) { notify('模板保存失败', error.message, true); return false; }
}

async function applyDataDirectory() {
  const path = $('#dataDirectoryInput')?.value.trim() || '';
  const mode = $('#dataDirectoryMode')?.value || 'migrate';
  if (!path) { $('#dataDirectoryInput')?.focus(); notify('目录不能为空', '请输入当前电脑上的完整目录路径', true); return false; }
  if (path === configData.data_dir) { captureManageSnapshot('settings'); notify('目录没有变化', path); return true; }
  const description = mode === 'migrate'
    ? '工作台会把当前全部数据复制到新目录，原目录将保留作为备份。确定继续吗？'
    : '工作台将立即读取该目录中的内容，不会复制当前数据。确定继续吗？';
  if (!await appConfirm({title:'切换数据目录？', message:description, detail:'切换前请确认目标目录与当前工作台数据均已妥善备份。', confirmText:'确认切换'})) return false;
  const button = $('#saveDataDirectory');
  if (button) { button.disabled = true; button.textContent = '正在切换…'; }
  try {
    configData = await api('/data-directory', {method:'PUT', body:JSON.stringify({path, mode})});
    window.workbenchDataDir = configData.data_dir;
    selectedProjectId = '';
    await refreshData();
    await renderManagePage('settings');
    notify('数据目录已切换', configData.data_dir);
    return true;
  } catch (error) {
    if (button) { button.disabled = false; button.textContent = '应用新目录'; }
    notify('目录切换失败', error.message, true);
    return false;
  }
}

async function showHistory() {
  if (!currentRecord) return;
  try {
    const versions = await api(`/records/${currentRecord.id}/history`);
    $('#historyList').innerHTML = versions.length ? versions.map(version => `<div class="history-row"><div><strong>${escapeHtml(version.title || currentRecord.title)}</strong><small>${escapeHtml(version.updated || version.version)} · ${escapeHtml(version.status || '')}</small></div><button data-restore-version="${version.version}">恢复此版</button><p>${escapeHtml(version.preview || '')}</p></div>`).join('') : '<div class="empty-state">这条记录还没有历史版本；首次修改后会自动生成。</div>';
    $('#historyDialog').showModal();
  } catch (error) { notify('历史记录加载失败', error.message, true); }
}

function createPastedImageInsertion(target) {
  if (target.closest('.editor')) {
    const editor = $('.editor');
    editor.focus();
    const selection = selectionInsideEditor(editor);
    if (!selection) placeCaret(editor, false);
    const activeSelection = selectionInsideEditor(editor), range = activeSelection.getRangeAt(0);
    const placeholder = document.createElement('span');
    placeholder.className = 'editor-image-uploading'; placeholder.contentEditable = 'false'; placeholder.textContent = '图片上传中…';
    range.deleteContents(); range.insertNode(placeholder); range.setStartAfter(placeholder); range.collapse(true);
    activeSelection.removeAllRanges(); activeSelection.addRange(range);
    return {mode:'visual', placeholder};
  }
  const source = $('.markdown-source'), token = `{{WORKBENCH_IMAGE_${Date.now()}_${Math.random().toString(36).slice(2)}}}`;
  const start = source.selectionStart ?? source.value.length, end = source.selectionEnd ?? start;
  source.value = `${source.value.slice(0, start)}${token}${source.value.slice(end)}`;
  source.selectionStart = source.selectionEnd = start + token.length;
  return {mode:'markdown', source, token};
}

function finishPastedImageInsertion(insertion, attachment) {
  const markdown = `![${attachment.name}](${attachment.path})`;
  if (insertion.mode === 'visual') {
    const wrapper = document.createElement('div'); wrapper.innerHTML = markdownToHtml(markdown, true);
    insertion.placeholder.replaceWith(wrapper.querySelector('img'));
  } else {
    insertion.source.value = insertion.source.value.replace(insertion.token, markdown);
    $('.markdown-preview').innerHTML = markdownToHtml(insertion.source.value);
    const position = insertion.source.value.indexOf(markdown) + markdown.length;
    insertion.source.selectionStart = insertion.source.selectionEnd = position;
  }
  markEditorChanged();
}

function cancelPastedImageInsertion(insertion) {
  if (!insertion) return;
  if (insertion.mode === 'visual') insertion.placeholder.remove();
  else insertion.source.value = insertion.source.value.replace(insertion.token, '');
}

async function uploadAttachment(file, options = {}) {
  if (!currentRecord || !file) return;
  const insertion = options.insertion || null;
  if (!insertion && editorDirty && !await saveEditorNow()) return;
  try {
    const append = insertion ? '0' : '1';
    const response = await fetch(`/api/records/${encodeURIComponent(currentRecord.id)}/attachments/upload?name=${encodeURIComponent(file.name)}&append=${append}`, {method:'POST', headers:{'Content-Type':file.type || 'application/octet-stream'}, body:file});
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `上传失败 (${response.status})`);
    const latest = await api(`/records/${currentRecord.id}`);
    if (insertion) {
      currentRecord.attachments = latest.attachments;
      finishPastedImageInsertion(insertion, result);
    } else {
      currentRecord = latest;
      $('.editor').innerHTML = markdownToHtml(currentRecord.body, true);
      $('.markdown-source').value = currentRecord.body;
      $('.markdown-preview').innerHTML = markdownToHtml(currentRecord.body);
    }
    renderAttachments();
    notify(`附件已保存：${file.name}`, insertion ? '图片已插入当前光标位置，保存正文后写入 Markdown' : 'Markdown 正文已加入相对路径引用');
  } catch (error) { cancelPastedImageInsertion(insertion); notify('附件上传失败', error.message, true); }
}

async function uploadProjectAssets(files) {
  const project = projects.find(item => item.id === selectedProjectId);
  if (!project || !files?.length) return false;
  const category = ($('#projectAssetUploadCategory')?.value || '').trim();
  const validFiles = [...files];
  if (!validFiles.length) return false;
  const uploadButton = $('#uploadProjectAsset');
  if (uploadButton) { uploadButton.disabled = true; uploadButton.textContent = `上传中 0/${validFiles.length}`; }
  let completed = 0;
  try {
    for (const file of validFiles) {
      const response = await fetch(`/api/projects/${encodeURIComponent(project.id)}/assets/upload?name=${encodeURIComponent(file.name)}&category=${encodeURIComponent(category)}`, {method:'POST', headers:{'Content-Type':file.type || 'application/octet-stream'}, body:file});
      const item = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(item.error || `上传失败 (${response.status})`);
      projectAssetLibrary.unshift(item);
      completed += 1;
      if (uploadButton) uploadButton.textContent = `上传中 ${completed}/${validFiles.length}`;
    }
    await loadProjectAssets(project.id, {force:true}); renderProjectPage();
    notify(`已上传 ${completed} 个项目附件`, category ? `分类：${category}` : '未设置分类');
    return true;
  } catch (error) {
    await loadProjectAssets(project.id, {force:true});
    renderProjectPage();
    notify('项目附件上传失败', `${completed ? `已完成 ${completed} 个；` : ''}${error.message}`, true);
    return false;
  } finally {
    if (uploadButton?.isConnected) { uploadButton.disabled = false; uploadButton.textContent = '＋ 上传附件'; }
  }
}

function editorDraftKey(recordId) {
  return `workbench-editor-draft:${recordId}`;
}

function readEditorDraft(recordId) {
  try { return JSON.parse(localStorage.getItem(editorDraftKey(recordId)) || 'null'); }
  catch { return null; }
}

function clearEditorDraft(recordId = currentRecord?.id) {
  try { if (recordId) localStorage.removeItem(editorDraftKey(recordId)); }
  catch { /* 隐私模式或存储受限时仍允许继续编辑 */ }
}

function persistEditorDraft() {
  if (!currentRecord || !editorDirty) return;
  try {
    localStorage.setItem(editorDraftKey(currentRecord.id), JSON.stringify({
      title:$('.drawer-title').value,
      body:localEditorContent(),
      info_fields:currentRecord.type === 'info' ? infoFieldsFrom($('#drawerInfoFieldList')) : undefined,
      info_color:currentRecord.type === 'info' ? drawerInfoColor() : undefined,
      savedAt:new Date().toISOString()
    }));
  } catch { /* 存储不可用时由离开页面提示继续兜底 */ }
}

function updateSaveIndicator(message = '') {
  const indicator = $('.save-indicator');
  indicator.textContent = message || (editorDirty ? '● 有未保存的修改' : '✓ 已保存');
  indicator.classList.toggle('saving', editorDirty || /正在|失败/.test(message));
  $('#saveRecord').disabled = !editorDirty;
}

function scheduleEditorSave() {
  clearTimeout(editorSaveTimer);
  persistEditorDraft();
  updateSaveIndicator();
}

async function saveEditorNow() {
  clearTimeout(editorSaveTimer);
  if (!currentRecord || !editorDirty || conflictRecord) return !editorDirty;
  const recordId = currentRecord.id;
  const title = $('.drawer-title').value.trim();
  if (!title) {
    notify('标题不能为空', '请输入标题后再保存', true);
    $('.drawer-title').focus();
    return false;
  }
  const changes = {title, body:localEditorContent()};
  if (currentRecord.type === 'info') {
    changes.info_fields = infoFieldsFrom($('#drawerInfoFieldList'));
    changes.info_color = drawerInfoColor();
  }
  $('.save-indicator').textContent = '正在保存…';
  $('.save-indicator').classList.add('saving');
  $('#saveRecord').disabled = true;
  try {
    await updateRecord(recordId, changes);
    editorDirty = false;
    clearEditorDraft(recordId);
    updateSaveIndicator('✓ 已保存 · 刚刚');
    return true;
  } catch {
    editorDirty = true;
    persistEditorDraft();
    updateSaveIndicator('保存失败，请重试');
    return false;
  }
}

function autoSaveOnLeaveEnabled() {
  return Boolean($('#saveOnLeave')?.checked);
}

async function confirmLeaveRecord() {
  if (!editorDirty) return true;
  if (autoSaveOnLeaveEnabled()) return saveEditorNow();
  const choice = await askUnsavedChanges(`记录「${$('.drawer-title').value.trim() || currentRecord?.id}」`);
  if (choice === 'cancel') return false;
  if (choice === 'save') return saveEditorNow();
  clearEditorDraft();
  editorDirty = false;
  return true;
}

async function closeDrawer(options = {}) {
  if (!await confirmLeaveRecord()) return false;
  detailDrawer.classList.remove('visible'); detailDrawer.setAttribute('aria-hidden', 'true');
  detailDrawer.classList.remove('editor-expanded');
  editorExpanded = false;
  $('#toggleEditorExpand').setAttribute('aria-pressed', 'false');
  $('#toggleEditorExpand').textContent = '⛶ 展开编辑';
  $('#toggleEditorExpand').title = '展开编辑区域';
  recordNavigationStack = [];
  if (!options.preserveUsageContext) usageReturnContext = null;
  updateRecordBackButton();
  hideOverlayIfClear();
  return true;
}

async function returnToUsage() {
  if (!usageReturnContext) return closeDrawer();
  const context = usageReturnContext;
  if (!await closeDrawer({preserveUsageContext:true})) return false;
  usageReturnContext = null;
  usageNavigationStack = (context.navigationStack || []).map(item => ({...item}));
  if (context.view?.view === 'overview') openUsageOverview(context.view.kind, {preserveStack:true});
  else if (context.view) openUsageDetail(context.view, {preserveStack:true});
  requestAnimationFrame(() => { $('#usageDialogContent').scrollTop = context.scrollTop || 0; });
  return true;
}

async function closeRecordView() {
  return usageReturnContext ? returnToUsage() : closeDrawer();
}

async function refreshData() {
  const loaded = await Promise.all([api('/projects'), api('/records?summary=1')]);
  projects = loaded[0];
  records = loaded[1].filter(record => record.type !== 'idea');
  lastRecordSignature = recordSignature(records);
  if (!projects.some(project => project.id === selectedProjectId)) selectedProjectId = projects.find(project => project.status !== 'archived')?.id || projects[0]?.id || '';
  renderNavigation(); renderDashboard();
  if ($('#projectPage').classList.contains('active')) renderProjectPage();
  persistNavigationState();
}

function recordSignature(items) {
  return items.map(item => `${item.id}:${item.file_mtime || item.updated}`).sort().join('|');
}

async function updateRecord(recordId, changes, successMessage) {
  try {
    const updated = await api(`/records/${encodeURIComponent(recordId)}`, {method:'PATCH', body:JSON.stringify(changes)});
    const index = records.findIndex(item => item.id === recordId);
    if (index >= 0) records[index] = updated;
    lastRecordSignature = recordSignature(records);
    if (currentRecord?.id === recordId) currentRecord = updated;
    renderDashboard();
    if ($('#projectPage').classList.contains('active')) renderProjectPage();
    if (successMessage) notify(successMessage);
    return updated;
  } catch (error) { notify('保存失败', error.message, true); throw error; }
}

async function createItem() {
  const title = $('#createTitle').value.trim();
  if (!title) { $('#createTitle').focus(); $('#createTitle').style.borderColor = '#df4b4b'; return; }
  $('#createTitle').style.borderColor = '';
  try {
    if (selectedType === '项目') {
      const project = await api('/projects', {method:'POST', body:JSON.stringify({name:title, description:$('#createBodyField textarea').value})});
      selectedProjectId = project.id;
    } else {
      const recordType = typeMap[selectedType];
      const statusOption = $('#createStatus').selectedOptions[0];
      const payload = {type:recordType, title, project_id:$('#projectSelect').value || null, body:$('#createBodyField textarea').value};
      if (recordType === 'info') {
        payload.info_fields = infoFieldsFrom($('#createInfoFieldList'));
        if (!payload.info_fields.length) { notify('请填写至少一个信息字段', '输入字段名称和对应内容后再创建', true); $('[data-info-field-name]', $('#createInfoFieldList')).focus(); return; }
      }
      else Object.assign(payload, {status:$('#createStatus').value, completed:statusOption?.dataset.completed === 'true', priority:$('#createPriority').value});
      await api('/records', {method:'POST', body:JSON.stringify(payload)});
    }
    createDialog.close();
    $('#createTitle').value = ''; $('#createBodyField textarea').value = ''; renderCreateInfoFields();
    await refreshData();
    notify(`已创建${selectedType}：${title}`, selectedType === '项目' ? '项目目录与 README.md 已生成' : 'Markdown 文件已保存到本地目录');
  } catch (error) { notify('创建失败', error.message, true); }
}

function prepareImportPreview(name, content) {
  const normalized = content.replace(/\r\n/g, '\n');
  const frontmatterEnd = normalized.indexOf('\n---\n', 4);
  const frontmatter = normalized.startsWith('---\n') && frontmatterEnd >= 0 ? normalized.slice(4, frontmatterEnd) : '';
  const body = frontmatter ? normalized.slice(frontmatterEnd + 5).trim() : normalized.trim();
  const readMeta = key => { const match = frontmatter.match(new RegExp(`^${key}:\\s*["']?([^"'\\n]+)`, 'm')); return match?.[1]?.trim(); };
  const detectedType = ['issue','todo','info'].includes(readMeta('type')) ? readMeta('type') : 'issue';
  const heading = body.match(/^#\s+(.+)$/m)?.[1]?.trim();
  pendingImport = {name, content};
  $('#importType').value = detectedType;
  $('#importTitle').value = readMeta('title') || heading || name.replace(/\.md$/i, '');
  $('#importProject').innerHTML = `<option value="">不属于项目</option>${projects.map(project => `<option value="${escapeHtml(project.id)}">${escapeHtml(project.name)}</option>`).join('')}`;
  const detectedProject = readMeta('project_id');
  $('#importProject').value = projects.some(item => item.id === detectedProject) ? detectedProject : (selectedProjectId || '');
  $('#importContentPreview').value = body.slice(0, 4000);
  $('#importSourceName').textContent = name;
  $('#importPreviewDialog').showModal();
}

function renderSearchResults(results) {
  results = results.filter(record => record.type !== 'idea');
  lastSearchResults = results;
  $$('[data-search-type]').forEach(button => { button.classList.toggle('active', button.dataset.searchType === searchTypeFilter); const count = $('span', button); if (count) count.textContent = results.filter(item => !button.dataset.searchType || item.type === button.dataset.searchType).length; });
  const selectOptions = (selector, values, emptyLabel) => { const select = $(selector); const current = searchFilters[select.dataset.filterKey]; select.innerHTML = `<option value="">${emptyLabel}</option>${values.map(([value,label]) => `<option value="${escapeHtml(value)}" ${value === current ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}`; };
  $('#searchProjectFilter').dataset.filterKey = 'project'; $('#searchTagFilter').dataset.filterKey = 'tag'; $('#searchStatusFilter').dataset.filterKey = 'status';
  selectOptions('#searchProjectFilter', [["__none__","未归属"], ...projects.map(item => [item.id, item.name])], '全部项目');
  selectOptions('#searchTagFilter', [...new Set(results.flatMap(item => item.tags || []))].map(value => [value,value]), '全部标签');
  selectOptions('#searchStatusFilter', [...new Set(results.map(item => item.status).filter(Boolean))].map(value => [value,value]), '全部状态');
  $('#searchPriorityFilter').value = searchFilters.priority;
  results = results.filter(record => (!searchTypeFilter || record.type === searchTypeFilter) && (!searchFilters.project || (searchFilters.project === '__none__' ? !record.project_id : record.project_id === searchFilters.project)) && (!searchFilters.tag || (record.tags || []).includes(searchFilters.tag)) && (!searchFilters.status || record.status === searchFilters.status) && (!searchFilters.priority || record.priority === searchFilters.priority));
  const section = $('.search-body section');
  section.innerHTML = `<div class="search-caption">找到 ${results.length} 条记录</div>${results.map(record => `<button class="search-result" data-record-id="${record.id}">${typeIcon(record)}<span><strong>${escapeHtml(record.title)}</strong><small>${escapeHtml(record.project_name || projectName(record.project_id))} · ${typeNames[record.type]} · ${escapeHtml(record.type === 'info' ? (record.info_fields || []).map(field => `${field.name}：${field.value}`).join(' · ').slice(0, 65) : markdownToPlainText(record.body, 65, record.title))}</small></span><em>${escapeHtml(record.type === 'info' ? '信息' : record.status)}</em></button>`).join('') || '<div class="empty-state">没有找到匹配记录</div>'}`;
}

function closeKanbanMenu() {
  const menu = $('#kanbanContextMenu');
  menu.classList.remove('visible'); menu.setAttribute('aria-hidden', 'true'); menu.innerHTML = '';
  $('.document-card-submenu')?.remove();
}

function showKanbanMenu(anchor, html) {
  $('.document-card-submenu')?.remove();
  const menu = $('#kanbanContextMenu');
  menu.innerHTML = html; menu.classList.add('visible'); menu.setAttribute('aria-hidden', 'false');
  const anchorRect = anchor.getBoundingClientRect();
  const menuRect = menu.getBoundingClientRect();
  const left = Math.min(window.innerWidth - menuRect.width - 12, Math.max(12, anchorRect.right - menuRect.width));
  const below = anchorRect.bottom + 6;
  const top = below + menuRect.height <= window.innerHeight - 12 ? below : Math.max(12, anchorRect.top - menuRect.height - 6);
  menu.style.left = `${left}px`; menu.style.top = `${top}px`;
}

function openProjectSortMenu(button) {
  const current = configData?.project_sort?.mode || 'custom';
  const rules = [
    ['custom', '⠿', '手动拖动排序'],
    ['updated', '◷', '最近更新优先'],
    ['name', 'A', '按项目名称'],
    ['created', '＋', '最新创建优先'],
    ['record_count', '#', '记录数量多优先'],
  ];
  showKanbanMenu(button, `<div class="context-menu-title">项目排序</div><div class="context-menu-label">选择排序规则</div>${rules.map(([mode, icon, label]) => `<button data-menu-action="sort-projects" data-sort-mode="${mode}"><i class="sort-rule-icon">${icon}</i>${label}${current === mode ? '<span>✓</span>' : ''}</button>`).join('')}<div class="context-menu-note">选择“手动拖动排序”后，可直接上下拖动侧边栏项目。</div>`);
}

function openRecordSortMenu(button) {
  const project = projects.find(item => item.id === selectedProjectId);
  const keys = recordSortKeys();
  if (!project || !keys) return;
  const current = project[keys.sort] || 'manual';
  const rules = [
    ['manual', '⠿', '手动拖动排序'],
    ['updated', '◷', '最近更新优先'],
    ['priority', '!', '按优先级'],
    ['due', '▣', '截止日期临近优先'],
    ['title', 'A', '按标题名称'],
    ['created', '＋', '最新创建优先'],
  ];
  showKanbanMenu(button, `<div class="context-menu-title">记录排序</div><div class="context-menu-label">当前记录类型的排序规则</div>${rules.map(([mode, icon, label]) => `<button data-menu-action="sort-records" data-sort-mode="${mode}"><i class="sort-rule-icon">${icon}</i>${label}${current === mode ? '<span>✓</span>' : ''}</button>`).join('')}<div class="context-menu-note">手动模式下，可在状态内调整位置，也可拖到其他状态的指定位置。</div>`);
}

function openCardMenu(button, recordId) {
  const record = records.find(item => item.id === recordId);
  if (!record) return;
  const statuses = statusesFor(record.type, record.project_id);
  showKanbanMenu(button, `<div class="context-menu-title">${escapeHtml(record.id)}</div><button data-menu-action="open-record" data-record="${escapeHtml(record.id)}">打开编辑</button><button data-menu-action="copy-record-id" data-record="${escapeHtml(record.id)}">复制记录 ID</button><div class="context-menu-separator"></div><div class="context-menu-label">移动到状态</div>${statuses.map(status => `<button data-menu-action="move-record" data-record="${escapeHtml(record.id)}" data-status="${escapeHtml(status.name)}" data-completed="${Boolean(status.completed)}" ${status.name === record.status ? 'disabled' : ''}><i class="column-dot" style="background:${escapeHtml(status.color || '#87919e')}"></i>${escapeHtml(status.name)}${status.name === record.status ? '<span>当前</span>' : ''}</button>`).join('')}<div class="context-menu-separator"></div><button class="danger-item" data-menu-action="delete-record" data-record="${escapeHtml(record.id)}">移入回收站</button>`);
}

function openColumnMenu(button) {
  const column = button.closest('.kanban-column');
  const columns = $$('.kanban-column', $('#kanban'));
  const index = columns.indexOf(column);
  const rules = [['manual','⠿','手动拖动'],['updated','◷','最近更新'],['priority','!','优先级'],['due','▣','截止日期'],['title','A','标题名称'],['created','＋','最新创建']];
  showKanbanMenu(button, `<div class="context-menu-title">${escapeHtml(column.dataset.status)}</div><button data-menu-action="new-in-column" data-status="${escapeHtml(column.dataset.status)}">＋ 在此状态中新建</button><div class="context-menu-separator"></div><div class="context-menu-label">此状态内的记录排序</div>${rules.map(([mode, icon, label]) => `<button data-menu-action="sort-status-records" data-status="${escapeHtml(column.dataset.status)}" data-sort-mode="${mode}"><i class="sort-rule-icon">${icon}</i>${label}${column.dataset.recordSortMode === mode ? '<span>✓</span>' : ''}</button>`).join('')}<div class="context-menu-separator"></div><button data-menu-action="move-column-left" data-status="${escapeHtml(column.dataset.status)}" ${index <= 0 ? 'disabled' : ''}>← 向左移动状态</button><button data-menu-action="move-column-right" data-status="${escapeHtml(column.dataset.status)}" ${index >= columns.length - 1 ? 'disabled' : ''}>→ 向右移动状态</button><div class="context-menu-separator"></div><button data-menu-action="manage-statuses">管理状态与颜色</button>`);
}

async function persistColumnOrder() {
  const board = $('#kanban');
  const orderKey = board.dataset.orderKey;
  if (!orderKey || !selectedProjectId) return;
  const order = $$('.kanban-column', board).map(column => column.dataset.status);
  try {
    const updated = await api(`/projects/${encodeURIComponent(selectedProjectId)}`, {method:'PATCH', body:JSON.stringify({[orderKey]:order})});
    const index = projects.findIndex(item => item.id === selectedProjectId);
    if (index >= 0) projects[index] = updated;
    notify('状态顺序已保存', order.join(' → '));
  } catch (error) { notify('状态顺序保存失败', error.message, true); renderProjectPage(); }
}

async function persistRecordOrder(visibleOrder, manualStatuses = [], quiet = false) {
  const board = $('#kanban');
  const project = projects.find(item => item.id === selectedProjectId);
  const sortKey = board.dataset.recordSortKey;
  const orderKey = board.dataset.recordOrderKey;
  const statusSortsKey = board.dataset.statusRecordSortsKey;
  if (!project || !sortKey || !orderKey || !statusSortsKey) return;
  const displayed = visibleOrder || $$('.kanban-card', board).map(card => card.dataset.recordId);
  const visibleSet = new Set(displayed);
  const tabType = {issues:'issue', todos:'todo'}[projectTab];
  const eligible = records.filter(record => record.project_id === selectedProjectId && (!tabType || record.type === tabType)).map(record => record.id);
  const eligibleSet = new Set(eligible);
  const base = [...(Array.isArray(project[orderKey]) ? project[orderKey] : []), ...eligible].filter((id, index, list) => eligibleSet.has(id) && list.indexOf(id) === index);
  let cursor = 0;
  const merged = base.map(id => visibleSet.has(id) ? displayed[cursor++] : id);
  while (cursor < displayed.length) merged.push(displayed[cursor++]);
  const statusSorts = {...(project[statusSortsKey] || {})};
  manualStatuses.filter(Boolean).forEach(status => { statusSorts[status] = 'manual'; });
  const updated = await api(`/projects/${encodeURIComponent(selectedProjectId)}`, {method:'PATCH', body:JSON.stringify({[orderKey]:merged, [statusSortsKey]:statusSorts})});
  const index = projects.findIndex(item => item.id === selectedProjectId);
  if (index >= 0) projects[index] = updated;
  if (!quiet) notify('记录顺序已保存');
}

function currentInfoCardOrder() {
  const columns = $$('[data-info-card-column]', $('#kanban')).map(column => $$('.info-display-card', column).map(card => card.dataset.recordId));
  const order = [];
  const length = Math.max(0, ...columns.map(column => column.length));
  for (let index = 0; index < length; index += 1) columns.forEach(column => { if (column[index]) order.push(column[index]); });
  return order;
}

async function persistInfoCardOrder() {
  const project = projects.find(item => item.id === selectedProjectId);
  if (!project) return;
  const displayed = currentInfoCardOrder();
  const visibleSet = new Set(displayed);
  const eligible = records.filter(record => record.project_id === selectedProjectId && record.type === 'info').map(record => record.id);
  const eligibleSet = new Set(eligible);
  const base = [...(Array.isArray(project.info_record_order) ? project.info_record_order : []), ...eligible].filter((id, index, list) => eligibleSet.has(id) && list.indexOf(id) === index);
  let cursor = 0;
  const merged = base.map(id => visibleSet.has(id) ? displayed[cursor++] : id);
  while (cursor < displayed.length) merged.push(displayed[cursor++]);
  try {
    const updated = await api(`/projects/${encodeURIComponent(selectedProjectId)}`, {method:'PATCH', body:JSON.stringify({info_record_sort:'manual', info_record_order:merged})});
    const projectIndex = projects.findIndex(item => item.id === selectedProjectId);
    if (projectIndex >= 0) projects[projectIndex] = updated;
    notify('信息卡片顺序已保存');
    renderProjectPage();
  } catch (error) { notify('信息卡片排序保存失败', error.message, true); renderProjectPage(); }
}

function bindInfoCardDragAndDrop() {
  const section = $('.info-card-section', $('#kanban'));
  if (!section) return;
  $$('.info-display-card', section).forEach(card => {
    card.addEventListener('dragstart', event => {
      if (event.target.closest('button')) { event.preventDefault(); return; }
      draggedInfoCard = card;
      card.classList.add('dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', card.dataset.recordId);
    });
    card.addEventListener('dragover', event => {
      if (!draggedInfoCard || draggedInfoCard === card) return;
      event.preventDefault();
      const rect = card.getBoundingClientRect();
      if (event.clientY < rect.top + rect.height / 2) card.before(draggedInfoCard); else card.after(draggedInfoCard);
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      $$('[data-info-card-column]', section).forEach(column => column.classList.remove('drag-over'));
      draggedInfoCard = null;
    });
  });
  $$('[data-info-card-column]', section).forEach(column => {
    column.addEventListener('dragover', event => {
      if (!draggedInfoCard) return;
      event.preventDefault();
      column.classList.add('drag-over');
      if (!event.target.closest('.info-display-card')) column.appendChild(draggedInfoCard);
    });
    column.addEventListener('dragleave', event => { if (!column.contains(event.relatedTarget)) column.classList.remove('drag-over'); });
    column.addEventListener('drop', event => {
      if (!draggedInfoCard) return;
      event.preventDefault();
      const card = draggedInfoCard;
      card.classList.remove('dragging');
      draggedInfoCard = null;
      column.classList.remove('drag-over');
      persistInfoCardOrder();
    });
  });
}

function bindDragAndDrop() {
  $$('.kanban-card').forEach(card => {
    card.addEventListener('dragstart', event => { draggedCard = card; draggedCardSourceStatus = card.closest('.kanban-column')?.dataset.status || ''; draggedColumn = null; cardOrderChanged = false; cardDropHandled = false; card.classList.add('dragging'); event.dataTransfer.effectAllowed = 'move'; event.stopPropagation(); });
    card.addEventListener('dragover', event => {
      if (!draggedCard || draggedCard === card) return;
      event.preventDefault(); event.stopPropagation();
      const rect = card.getBoundingClientRect();
      if (event.clientY < rect.top + rect.height / 2) card.before(draggedCard); else card.after(draggedCard);
      cardOrderChanged = true;
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging'); $$('.kanban-column').forEach(column => column.classList.remove('drag-over'));
      const shouldRestore = cardOrderChanged && !cardDropHandled;
      draggedCard = null;
      if (shouldRestore) renderProjectPage();
    });
  });
  let columnOrderChanged = false;
  $$('.kanban-column').forEach(column => {
    const header = $('header', column);
    header.addEventListener('dragstart', event => {
      if (event.target.closest('button')) { event.preventDefault(); return; }
      draggedColumn = column; draggedCard = null; columnOrderChanged = false;
      column.classList.add('column-dragging'); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', column.dataset.status);
    });
    header.addEventListener('dragend', () => {
      column.classList.remove('column-dragging'); $$('.kanban-column').forEach(item => item.classList.remove('column-drop-target'));
      if (columnOrderChanged) persistColumnOrder();
      draggedColumn = null; columnOrderChanged = false;
    });
    column.addEventListener('dragover', event => {
      event.preventDefault();
      if (draggedColumn) {
        if (draggedColumn === column) return;
        column.classList.add('column-drop-target');
        const rect = column.getBoundingClientRect();
        if (event.clientX < rect.left + rect.width / 2) column.before(draggedColumn); else column.after(draggedColumn);
        columnOrderChanged = true;
        return;
      }
      if (!draggedCard) return;
      column.classList.add('drag-over');
      const stack = $('.card-stack', column);
      if (event.target === stack) {
        stack.appendChild(draggedCard); cardOrderChanged = true;
      }
    });
    column.addEventListener('dragleave', event => { if (!column.contains(event.relatedTarget)) column.classList.remove('drag-over'); });
    column.addEventListener('drop', async event => {
      event.preventDefault(); column.classList.remove('drag-over', 'column-drop-target');
      if (draggedColumn) { if (columnOrderChanged) await persistColumnOrder(); columnOrderChanged = false; return; }
      if (!draggedCard) return;
      const id = draggedCard.dataset.recordId;
      cardDropHandled = true;
      const stack = $('.card-stack', column);
      if (!stack.contains(draggedCard)) stack.appendChild(draggedCard);
      const visibleOrder = $$('.kanban-card', $('#kanban')).map(card => card.dataset.recordId);
      try {
        await persistRecordOrder(visibleOrder, [draggedCardSourceStatus, column.dataset.status], true);
        await updateRecord(id, {status:column.dataset.status, completed:column.dataset.completed === 'true'}, `位置与状态已更新为「${column.dataset.status}」`);
      } catch (error) { notify('记录排序保存失败', error.message, true); renderProjectPage(); }
    });
  });
}

document.addEventListener('click', async event => {
  const documentColorMenu = event.target.closest('[data-document-color-menu]');
  if (documentColorMenu) { openDocumentColorPalette(documentColorMenu, documentColorMenu.dataset.documentColorMenu); return; }
  const documentColorApply = event.target.closest('[data-document-color-apply]');
  if (documentColorApply) { const command = documentColorApply.dataset.documentColorApply; applyDocumentColor(documentColorDefaults[command], command, false); return; }
  const documentColorValue = event.target.closest('[data-document-color-value]');
  if (documentColorValue) { applyDocumentColor(documentColorValue.dataset.documentColorValue); return; }
  if (!event.target.closest('#documentColorPalette')) $('#documentColorPalette').hidden = true;
  if (event.target.closest('#toggleDocumentTags')) { $('#documentTagOptions').hidden = !$('#documentTagOptions').hidden; return; }
  const removeDocumentTag = event.target.closest('[data-remove-document-tag]');
  if (removeDocumentTag) {
    const input = $$('#documentTagOptions input').find(item => item.value === removeDocumentTag.dataset.removeDocumentTag);
    if (input) input.checked = false;
    updateDocumentTagSummary();
    markDocumentChanged();
    return;
  }
  if (!event.target.closest('.document-tag-picker') && $('#documentTagOptions')) $('#documentTagOptions').hidden = true;
  if (event.target.closest('#openDocumentExternal')) { await openCurrentDocumentExternal(); return; }
  if (event.target.closest('#chooseDocumentExternal')) { await openExternalEditorDialog(); return; }
  if (event.target.closest('#newDocument')) { openDocument(); return; }
  if (event.target.closest('#newDocumentCategory')) { await createDocumentCategory(); return; }
  const renameDocumentCategoryButton = event.target.closest('[data-rename-document-category]');
  if (renameDocumentCategoryButton) { event.preventDefault(); await renameDocumentCategory(renameDocumentCategoryButton.dataset.renameDocumentCategory); return; }
  const deleteDocumentCategoryButton = event.target.closest('[data-delete-document-category]');
  if (deleteDocumentCategoryButton) { event.preventDefault(); await deleteDocumentCategory(deleteDocumentCategoryButton.dataset.deleteDocumentCategory); return; }
  if (event.target.closest('#importKnowledgeDocuments')) { $('#knowledgeImportInput').click(); return; }
  if (event.target.closest('#startDocumentExport')) { documentExportMode = true; documentSelection.clear(); renderDocumentsPage(); return; }
  if (event.target.closest('#cancelDocumentExport')) { documentExportMode = false; documentSelection.clear(); renderDocumentsPage(); return; }
  if (event.target.closest('#exportSelectedKnowledge')) { await exportSelectedDocuments(); return; }
  if (event.target.closest('#clearDocumentSelection')) { documentSelection.clear(); $$('[data-document-select]').forEach(input => { input.checked = false; }); updateDocumentSelectionUI(); return; }
  if (event.target.closest('#exportDocument') && currentDocument) { downloadKnowledgeFile(`/documents/${encodeURIComponent(currentDocument.id)}/export`); notify('正在导出文档', `${currentDocument.title}.md`); return; }
  const documentCardMenu = event.target.closest('[data-document-card-menu]');
  if (documentCardMenu) { event.preventDefault(); event.stopPropagation(); openDocumentCardMenu(documentCardMenu, documentCardMenu.dataset.documentCardMenu); return; }
  const documentCard = event.target.closest('[data-document-id]');
  if (documentCard) {
    if (documentExportMode) {
      const id = documentCard.dataset.documentId;
      if (documentSelection.has(id)) documentSelection.delete(id); else documentSelection.add(id);
      const input = $(`[data-document-select="${id}"]`); if (input) input.checked = documentSelection.has(id);
      updateDocumentSelectionUI(); return;
    }
    openDocument(documentCard.dataset.documentId); return;
  }
  if (event.target.closest('#toggleDocumentOutline')) {
    documentOutlineCollapsed = !documentOutlineCollapsed;
    localStorage.setItem('workbench-document-outline-collapsed', String(documentOutlineCollapsed));
    updateDocumentOutline();
    return;
  }
  const documentOutlineLink = event.target.closest('[data-document-outline-index]');
  if (documentOutlineLink) { navigateDocumentOutline(documentOutlineLink); return; }
  if (event.target.closest('#closeDocumentDialog')) { await closeDocumentEditor(); return; }
  if (event.target.closest('#toggleDocumentExpand')) {
    if (documentMode === 'read') setDocumentMode('visual');
    documentExpanded = !documentExpanded;
    $('#documentDialog').classList.toggle('expanded', documentExpanded);
    $('#toggleDocumentExpand span').textContent = documentExpanded ? '退出展开' : '展开编辑';
    return;
  }
  if (event.target.closest('#toggleDocumentMode')) { setDocumentMode(documentMode === 'read' ? 'visual' : 'read'); return; }
  const documentModeButton = event.target.closest('[data-document-mode]');
  if (documentModeButton) { setDocumentMode(documentModeButton.dataset.documentMode); return; }
  const documentCommand = event.target.closest('[data-document-command]');
  if (documentCommand) { $('#documentVisualEditor').focus(); restoreDocumentSelection(); document.execCommand(documentCommand.dataset.documentCommand, false); markDocumentChanged(); return; }
  if (event.target.closest('[data-document-block="blockquote"]')) { $('#documentVisualEditor').focus(); restoreDocumentSelection(); toggleBlockquote($('#documentVisualEditor'), markDocumentChanged); return; }
  if (event.target.closest('#documentChecklist')) { $('#documentVisualEditor').focus(); restoreDocumentSelection(); document.execCommand('insertHTML', false, '<ul><li class="task-item"><input type="checkbox"> 待办项</li></ul><p><br></p>'); markDocumentChanged(); return; }
  if (event.target.closest('#documentCodeBlock')) {
    insertDocumentCodeBlock(); return;
  }
  if (event.target.closest('#documentLink')) {
    const url = await appPrompt({title:'插入链接', confirmText:'插入', input:{label:'链接地址', placeholder:'https://example.com'}});
    if (url?.trim()) { $('#documentVisualEditor').focus(); restoreDocumentSelection(); document.execCommand('createLink', false, /^(https?:|mailto:)/i.test(url.trim()) ? url.trim() : `https://${url.trim()}`); markDocumentChanged(); }
    return;
  }
  if (event.target.closest('#documentSelectionLink')) {
    const url = await appPrompt({title:'插入链接', confirmText:'插入', input:{label:'链接地址', placeholder:'https://example.com'}});
    if (url?.trim()) { $('#documentVisualEditor').focus(); restoreDocumentSelection(); document.execCommand('createLink', false, /^(https?:|mailto:)/i.test(url.trim()) ? url.trim() : `https://${url.trim()}`); markDocumentChanged(); }
    return;
  }
  if (event.target.closest('#documentSelectionCode')) {
    const text = documentLastRange?.toString() || '代码'; $('#documentVisualEditor').focus(); restoreDocumentSelection(); document.execCommand('insertHTML', false, `<code>${escapeHtml(text)}</code>`); markDocumentChanged(); return;
  }
  if (event.target.closest('#saveDocument')) { await saveDocument(); return; }
  if (event.target.closest('#deleteDocument')) { await deleteDocument(); return; }
  if (event.target.id === 'selectAllTrash') {
    trashSelection = event.target.checked ? new Set(trashItems.map(item => item.token)) : new Set();
    $$('[data-trash-select]').forEach(input => { input.checked = event.target.checked; });
    updateTrashSelectionUI();
    return;
  }
  if (event.target.matches('[data-trash-select]')) {
    const token = event.target.dataset.trashSelect;
    if (event.target.checked) trashSelection.add(token); else trashSelection.delete(token);
    updateTrashSelectionUI();
    return;
  }
  if (event.target.closest('#batchRestoreTrash')) { await batchRestoreTrash(); return; }
  if (event.target.closest('#batchPurgeTrash')) { await batchPurgeTrash(); return; }
  const manageSave = event.target.closest('[data-save-manage]');
  if (manageSave) {
    if (manageSave.disabled) return;
    const originalText = manageSave.textContent;
    manageSave.disabled = true;
    manageSave.textContent = '保存中…';
    let saved = false;
    if (manageSave.dataset.saveManage === 'tags') saved = await saveTags();
    else if (manageSave.dataset.saveManage === 'status_templates') saved = await saveTemplates();
    if (!saved && manageSave.isConnected) {
      manageSave.disabled = false;
      manageSave.textContent = originalText;
    }
    return;
  }
  if (event.target.closest('#uploadProjectAsset')) { $('#projectAssetInput')?.click(); return; }
  if (event.target.closest('#manageAssetCategories')) { openAssetCategoryManager(); return; }
  if (event.target.closest('#addAssetCategory')) {
    const editor = $('#assetCategoryEditor');
    $('.asset-category-empty', editor)?.remove();
    editor.insertAdjacentHTML('beforeend', assetCategoryRowHtml());
    $('.asset-new-category-name', editor.lastElementChild)?.focus();
    return;
  }
  const removeAssetCategory = event.target.closest('.remove-asset-category');
  if (removeAssetCategory) {
    const row = removeAssetCategory.closest('[data-asset-category-row]');
    const name = row.dataset.categoryName;
    if (name && !await appConfirm({title:`删除分类「${name}」？`, message:'分类中的附件不会被删除，将自动变为“无分类”。', confirmText:'删除分类', danger:true})) return;
    row.remove();
    if (!$('#assetCategoryEditor').children.length) $('#assetCategoryEditor').innerHTML = '<div class="empty-state asset-category-empty">还没有分类，可以创建第一个分类。</div>';
    return;
  }
  if (event.target.closest('#saveAssetCategories')) { await saveAssetCategories(); return; }
  if (event.target.closest('#applyBatchAssetCategory')) {
    const selections = selectedAssetPayloads(), category = $('#batchAssetCategory').value;
    if (!category && category !== '__uncategorized__') { notify('请选择目标分类', '也可以选择“设为无分类”', true); return; }
    try { await applyAssetCategory(selections, category); } catch (error) { notify('批量分类失败', error.message, true); }
    return;
  }
  if (event.target.closest('#deleteSelectedAssets')) { await deleteAssetsWithConfirmation(selectedAssetPayloads()); return; }
  const deleteSingleAsset = event.target.closest('[data-delete-single-asset]');
  if (deleteSingleAsset) {
    event.preventDefault(); event.stopPropagation();
    const input = $('.project-asset-select', deleteSingleAsset.closest('.project-asset-card'));
    if (input) await deleteAssetsWithConfirmation([assetPayloadFromInput(input)]);
    return;
  }
  if (event.target.closest('#clearProjectAssetFilters')) {
    projectAssetCategoryFilter = ''; projectAssetSearch = ''; renderProjectPage(); return;
  }
  const openProjectAsset = event.target.closest('[data-open-project-asset]');
  if (openProjectAsset) {
    event.preventDefault(); event.stopPropagation();
    window.open(`/api/project-assets/${encodeURIComponent(selectedProjectId)}/${encodeURIComponent(openProjectAsset.dataset.openProjectAsset)}`, '_blank');
    return;
  }
  const openRecordAsset = event.target.closest('[data-open-record-asset]');
  if (openRecordAsset) {
    event.preventDefault(); event.stopPropagation();
    window.open(`/api/attachments/${encodeURIComponent(openRecordAsset.dataset.openRecordAsset)}/${encodeURIComponent(openRecordAsset.dataset.recordAssetName)}`, '_blank');
    return;
  }
  const timelineFilterTrigger = event.target.closest('[data-timeline-filter]');
  if (timelineFilterTrigger) {
    event.preventDefault();
    const popover = $('#timelineFilterPopover');
    if (popover.classList.contains('visible') && popover.dataset.field === timelineFilterTrigger.dataset.timelineFilter) closeTimelineFilter();
    else openTimelineFilter(timelineFilterTrigger);
    return;
  }
  const timelinePopover = event.target.closest('#timelineFilterPopover');
  if (timelinePopover) {
    if (event.target.closest('[data-timeline-filter-apply]')) {
      const field = timelinePopover.dataset.field;
      const options = $$('.timeline-filter-values input[type="checkbox"]', timelinePopover);
      const selected = options.filter(input => input.checked).map(input => input.value);
      timelineFilters[field] = selected.length === options.length ? [] : selected;
      closeTimelineFilter();
      renderManagePage('timeline');
    } else if (event.target.closest('[data-timeline-filter-clear]')) {
      timelineFilters[timelinePopover.dataset.field] = [];
      closeTimelineFilter();
      renderManagePage('timeline');
    } else if (event.target.closest('[data-timeline-filter-close]')) closeTimelineFilter();
    return;
  }
  closeTimelineFilter();
  const colorTrigger = event.target.closest('.color-picker-trigger');
  if (colorTrigger) {
    event.preventDefault();
    const picker = colorTrigger.closest('[data-color-picker]');
    const willOpen = !picker.classList.contains('open');
    $$('[data-color-picker].open').forEach(item => { item.classList.remove('open'); $('.color-picker-trigger', item).setAttribute('aria-expanded', 'false'); });
    picker.classList.toggle('open', willOpen);
    colorTrigger.setAttribute('aria-expanded', String(willOpen));
    if (willOpen) syncColorPicker(picker, $('input[type="color"]', picker).value);
    return;
  }
  const paletteColor = event.target.closest('[data-color-value]');
  if (paletteColor) {
    event.preventDefault();
    const picker = paletteColor.closest('[data-color-picker]');
    syncColorPicker(picker, paletteColor.dataset.colorValue);
    rememberRecentColor('workbench-recent-management-colors', paletteColor.dataset.colorValue);
    updateTagRowDirtyState(picker.closest('.tag-edit'));
    updateStatusRowDirtyState(picker.closest('.status-edit-row'));
    picker.classList.remove('open');
    $('.color-picker-trigger', picker).setAttribute('aria-expanded', 'false');
    if (picker.closest('#infoColorPicker')) markEditorChanged();
    return;
  }
  if (!event.target.closest('[data-color-picker]')) {
    $$('[data-color-picker].open').forEach(item => { item.classList.remove('open'); $('.color-picker-trigger', item).setAttribute('aria-expanded', 'false'); });
  }
  const recordSortButton = event.target.closest('#recordSortButton');
  if (recordSortButton) { event.preventDefault(); openRecordSortMenu(recordSortButton); return; }
  const projectSortButton = event.target.closest('#projectSortButton');
  if (projectSortButton) { event.preventDefault(); openProjectSortMenu(projectSortButton); return; }
  const documentCategorySortButton = event.target.closest('#documentCategorySortButton');
  if (documentCategorySortButton) { event.preventDefault(); openDocumentCategorySortMenu(documentCategorySortButton); return; }
  const documentSortButton = event.target.closest('[data-document-file-sort]');
  if (documentSortButton) { event.preventDefault(); openDocumentSortMenu(documentSortButton); return; }
  if (event.target.closest('#clearDocumentCategoryFilter')) { documentFilters.categoryQuery = ''; renderDocumentsPage(); $('#documentCategorySearch')?.focus(); return; }
  const clearDocumentFileFilter = event.target.closest('[data-clear-document-file-filter]');
  if (clearDocumentFileFilter) { const category = clearDocumentFileFilter.dataset.clearDocumentFileFilter; documentCategoryFileQueries[category] = ''; renderDocumentsPage(); $(`[data-document-file-search="${CSS.escape(category)}"]`)?.focus(); return; }
  const cardMenuButton = event.target.closest('[data-card-menu]');
  if (cardMenuButton) { event.preventDefault(); event.stopPropagation(); openCardMenu(cardMenuButton, cardMenuButton.dataset.cardMenu); return; }
  const columnMenuButton = event.target.closest('[data-column-menu]');
  if (columnMenuButton) { event.preventDefault(); event.stopPropagation(); openColumnMenu(columnMenuButton); return; }
  const menuAction = event.target.closest('[data-menu-action]');
  if (menuAction) {
    const action = menuAction.dataset.menuAction;
    const recordId = menuAction.dataset.record;
    const menuDocumentId = menuAction.dataset.document;
    if (action === 'document-card-categories') { showDocumentCategorySubmenu(menuAction, menuDocumentId); return; }
    closeKanbanMenu();
    if (action === 'open-document-card') { openDocument(menuDocumentId); return; }
    if (action === 'set-document-category') {
      const category = menuAction.dataset.category;
      try {
        await api(`/documents/${encodeURIComponent(menuDocumentId)}`, {method:'PATCH', body:JSON.stringify({category})});
        documents = await api('/documents'); documentOpenCategories.add(category); renderDocumentsPage(); notify('文档分类已更新', `已移动到「${category}」`);
      } catch (error) { notify('文档分类更新失败', error.message, true); }
      return;
    }
    if (action === 'delete-document-card') {
      const item = documents.find(document => document.id === menuDocumentId);
      if (item && await appConfirm({title:'将文档移入回收站？', message:`「${item.title}」`, detail:'稍后可以在回收站中恢复。', confirmText:'移入回收站', danger:true})) {
        try { await api(`/documents/${encodeURIComponent(menuDocumentId)}`, {method:'DELETE'}); documentSelection.delete(menuDocumentId); documents = await api('/documents'); renderDocumentsPage(); notify('文档已移入回收站'); }
        catch (error) { notify('文档删除失败', error.message, true); }
      }
      return;
    }
    if (action === 'sort-projects') {
      const mode = menuAction.dataset.sortMode;
      const existingOrder = configData?.project_sort?.order?.length ? configData.project_sort.order : projects.map(project => project.id);
      try {
        configData.project_sort = await api('/project-sort', {method:'PUT', body:JSON.stringify({mode, order:existingOrder})});
        await refreshData();
        const labels = {custom:'手动拖动排序', updated:'最近更新优先', name:'按项目名称', created:'最新创建优先', record_count:'记录数量多优先'};
        notify('项目排序规则已更新', labels[mode]);
      } catch (error) { notify('项目排序设置失败', error.message, true); }
    }
    if (action === 'sort-documents') {
      const mode = menuAction.dataset.sortMode;
      const category = menuAction.dataset.documentCategory;
      const labels = {manual:'手动拖动排序', updated:'最近更新优先', title:'按标题名称', created:'最新创建优先'};
      const config = knowledgeSortConfig();
      documentOpenCategories.add(category);
      await saveKnowledgeSort({file_modes:{...config.file_modes, [category]:mode}}, `「${category}」文档排序已更新`, labels[mode]);
    }
    if (action === 'sort-document-categories') {
      const mode = menuAction.dataset.sortMode;
      const labels = {manual:'手动拖动排序', name:'按分类名称', count:'文档数量多优先', updated:'最近更新优先'};
      await saveKnowledgeSort({category_mode:mode}, '分类条目排序已更新', labels[mode]);
    }
    if (action === 'sort-records') {
      const project = projects.find(item => item.id === selectedProjectId);
      const keys = recordSortKeys();
      const mode = menuAction.dataset.sortMode;
      if (project && keys) {
        const tabType = {issues:'issue', todos:'todo'}[projectTab];
        const existingOrder = Array.isArray(project[keys.order]) && project[keys.order].length
          ? project[keys.order]
          : records.filter(record => record.project_id === selectedProjectId && (!tabType || record.type === tabType)).map(record => record.id);
        try {
          const updated = await api(`/projects/${encodeURIComponent(selectedProjectId)}`, {method:'PATCH', body:JSON.stringify({[keys.sort]:mode, [keys.order]:existingOrder, [keys.statusSorts]:{}})});
          const index = projects.findIndex(item => item.id === selectedProjectId);
          if (index >= 0) projects[index] = updated;
          renderProjectPage();
          const labels = {manual:'手动拖动排序', updated:'最近更新优先', priority:'按优先级', due:'截止日期临近优先', title:'按标题名称', created:'最新创建优先'};
          notify('记录排序规则已更新', labels[mode]);
        } catch (error) { notify('记录排序设置失败', error.message, true); }
      }
    }
    if (action === 'sort-status-records') {
      const project = projects.find(item => item.id === selectedProjectId);
      const keys = recordSortKeys();
      const status = menuAction.dataset.status;
      const mode = menuAction.dataset.sortMode;
      if (project && keys && status) {
        const statusSorts = {...(project[keys.statusSorts] || {}), [status]:mode};
        try {
          const updated = await api(`/projects/${encodeURIComponent(selectedProjectId)}`, {method:'PATCH', body:JSON.stringify({[keys.statusSorts]:statusSorts})});
          const index = projects.findIndex(item => item.id === selectedProjectId);
          if (index >= 0) projects[index] = updated;
          renderProjectPage();
          const labels = {manual:'手动拖动',updated:'最近更新',priority:'优先级',due:'截止日期',title:'标题名称',created:'最新创建'};
          notify(`「${status}」排序已更新`, labels[mode]);
        } catch (error) { notify('状态排序设置失败', error.message, true); }
      }
    }
    if (action === 'open-record') await openDrawer(recordId);
    if (action === 'copy-record-id') {
      try { await navigator.clipboard.writeText(recordId); notify('记录 ID 已复制', recordId); }
      catch { await appPrompt({title:'复制记录 ID', message:'浏览器未授权自动复制，请手动复制下面的编号。', confirmText:'完成', cancelText:'关闭', input:{label:'记录编号', value:recordId, readOnly:true}}); }
    }
    if (action === 'move-record') await updateRecord(recordId, {status:menuAction.dataset.status, completed:menuAction.dataset.completed === 'true'}, `已移动到「${menuAction.dataset.status}」`);
    if (action === 'delete-record') {
      const record = records.find(item => item.id === recordId);
      if (record && await appConfirm({title:'将记录移入回收站？', message:`「${record.title}」`, detail:'记录文件不会立即永久删除，可稍后从回收站恢复。', confirmText:'移入回收站', danger:true})) {
        try { await api(`/records/${encodeURIComponent(recordId)}`, {method:'DELETE'}); await refreshData(); notify('记录已移入回收站'); }
        catch (error) { notify('删除失败', error.message, true); }
      }
    }
    if (action === 'new-in-column') {
      const type = projectTab === 'todos' ? '待办' : '问题';
      openCreate(type, {projectId:selectedProjectId, status:menuAction.dataset.status});
    }
    if (action === 'move-column-left' || action === 'move-column-right') {
      const column = $$('.kanban-column', $('#kanban')).find(item => item.dataset.status === menuAction.dataset.status);
      if (column) {
        if (action === 'move-column-left' && column.previousElementSibling) column.previousElementSibling.before(column);
        if (action === 'move-column-right' && column.nextElementSibling) column.nextElementSibling.after(column);
        await persistColumnOrder();
      }
    }
    if (action === 'manage-statuses') {
      const project = projects.find(item => item.id === selectedProjectId);
      selectedWorkflowId = project?.workflow_template || 'standard'; setPage('status_templates');
    }
    return;
  }
  if (!event.target.closest('#kanbanContextMenu,.document-card-submenu')) closeKanbanMenu();
  const pageButton = event.target.closest('[data-page]');
  if (pageButton) {
    if ($('#managePage').classList.contains('active') && pageButton.dataset.page === activeManagePage && !pageButton.dataset.projectId) return;
    if (!await confirmLeaveManagePage()) return;
    if (pageButton.dataset.projectId) selectedProjectId = pageButton.dataset.projectId;
    setPage(pageButton.dataset.page);
    return;
  }
  const pageLink = event.target.closest('[data-page-link]');
  if (pageLink) { if (await confirmLeaveManagePage()) setPage(pageLink.dataset.pageLink); return; }
  const retryManage = event.target.closest('[data-retry-manage]');
  if (retryManage) { if (await confirmLeaveManagePage()) setPage(retryManage.dataset.retryManage); return; }
  const createButton = event.target.closest('[data-create-type]');
  if (createButton) {
    const column = createButton.closest('.kanban-column');
    const projectPage = createButton.closest('#projectPage');
    openCreate(createButton.dataset.createType, {
      projectId: projectPage ? selectedProjectId : '',
      status: column?.dataset.status || '',
    });
  }
  const removeInfoField = event.target.closest('[data-remove-info-field]');
  if (removeInfoField) {
    const list = removeInfoField.closest('#createInfoFieldList, #drawerInfoFieldList');
    removeInfoField.closest('[data-info-field-row]').remove();
    if (!list.children.length) list.insertAdjacentHTML('beforeend', infoFieldRowHtml());
    if (list.id === 'drawerInfoFieldList') markEditorChanged();
    return;
  }
  const insertInfoField = event.target.closest('[data-insert-info-field]');
  if (insertInfoField) {
    insertInfoFieldIntoEditor(insertInfoField.closest('[data-info-field-row]'));
    return;
  }
  const recordsToggle = event.target.closest('.records-expand-toggle');
  if (recordsToggle) {
    const container = recordsToggle.closest('.kanban-column, .collapsible-record-list, .info-card-section');
    const expanded = !container.classList.contains('records-expanded');
    container.classList.toggle('records-expanded', expanded);
    recordsToggle.setAttribute('aria-expanded', String(expanded));
    const hiddenCount = $$('.auto-collapsed-record', container).length;
    recordsToggle.textContent = expanded ? '收起记录⌃' : `展开其余 ${hiddenCount} 条记录⌄`;
    return;
  }
  const copyInfoValue = event.target.closest('[data-copy-info-value]');
  if (copyInfoValue) {
    event.preventDefault();
    event.stopPropagation();
    const value = decodeURIComponent(copyInfoValue.dataset.copyInfoValue || '');
    try {
      await navigator.clipboard.writeText(value);
      notify('字段内容已复制', value || '空内容');
    } catch {
      await appPrompt({title:'复制字段内容', message:'浏览器未允许自动复制，请从下方复制：', value});
    }
    return;
  }
  if (event.target.closest('#resetTimelineFilters')) {
    timelineFilters = {type:[], project:[], status:[], priority:[], tag:[]};
    renderManagePage('timeline');
    return;
  }
  const timelineSortButton = event.target.closest('[data-timeline-sort]');
  if (timelineSortButton) {
    const field = timelineSortButton.dataset.timelineSort;
    if (timelineSort.field === field) timelineSort.direction = timelineSort.direction === 'asc' ? 'desc' : 'asc';
    else {
      timelineSort.field = field;
      timelineSort.direction = ['updated','created','priority'].includes(field) ? 'desc' : 'asc';
    }
    renderManagePage('timeline');
    return;
  }
  const internalReference = event.target.closest('[data-reference-id]');
  if (internalReference) {
    event.preventDefault();
    if (!await confirmLeaveRecord()) return;
    await openDrawer(internalReference.dataset.referenceId, {fromReference:true});
  }
  const recordButton = event.target.closest('[data-record-id]:not(.todo-row)');
  if (recordButton && !internalReference && !event.target.closest('input') && !event.target.closest('#drawerRecordId') && !event.target.closest('.card-menu-button')) {
    if (detailDrawer.classList.contains('visible') && recordButton.dataset.recordId !== currentRecord?.id && !await confirmLeaveRecord()) return;
    openDrawer(recordButton.dataset.recordId);
  }
  const attachment = event.target.closest('[data-attachment-name]');
  if (attachment && currentRecord) window.open(`/api/attachments/${encodeURIComponent(currentRecord.id)}/${encodeURIComponent(attachment.dataset.attachmentName)}`, '_blank');
  const addStatus = event.target.closest('[data-add-status]');
  if (addStatus) {
    const list = $('.status-edit-list', addStatus.closest('.template-panel'));
    list.insertAdjacentHTML('beforeend', statusEditorHtml({id:`${addStatus.dataset.addStatus}_${Date.now()}`, name:'新状态', color:'#87919e'}, addStatus.dataset.addStatus, {newItem:true}));
    const row = list.lastElementChild;
    row.classList.add('new-config-row');
    $('input[type="text"]', row)?.select();
    row.scrollIntoView({block:'center', behavior:'smooth'});
    return;
  }
  const statusUsageButton = event.target.closest('.status-usage-button');
  if (statusUsageButton) {
    const row = statusUsageButton.closest('.status-edit-row');
    openUsageDetail({kind:'status', name:$('input[type="text"]', row).value.trim(), recordType:row.closest('.template-panel').dataset.templateType, statusId:row.dataset.statusId || ''});
    return;
  }
  const saveStatusRow = event.target.closest('[data-save-status-row]');
  if (saveStatusRow) {
    const row = saveStatusRow.closest('.status-edit-row');
    if (!$('input[type="text"]', row).value.trim()) { notify('请输入状态名称', '状态名称不能为空', true); $('input[type="text"]', row).focus(); return; }
    saveStatusRow.disabled = true; saveStatusRow.textContent = '保存中…';
    if (!await saveTemplates() && saveStatusRow.isConnected) { saveStatusRow.disabled = false; saveStatusRow.textContent = '保存'; }
    return;
  }
  const cancelStatusRow = event.target.closest('[data-cancel-status-row]');
  if (cancelStatusRow) {
    const row = cancelStatusRow.closest('.status-edit-row');
    if (!row.dataset.originalName) { row.remove(); updateStatusBatchUI(); return; }
    $('input[type="text"]', row).value = row.dataset.originalName;
    $('.status-completed', row).checked = row.dataset.originalCompleted === 'true';
    syncColorPicker($('[data-color-picker]', row), row.dataset.originalColor || '#64748b');
    updateStatusRowDirtyState(row);
    return;
  }
  const removeStatus = event.target.closest('.remove-status');
  if (removeStatus) {
    const row = removeStatus.closest('.status-edit-row');
    const type = removeStatus.closest('.template-panel')?.dataset.templateType;
    const name = $('input[type="text"]', row)?.value.trim();
    const affected = statusUsageRecords(type, name, row.dataset.statusId || '');
    if (affected.length) {
      openUsageDetail({kind:'status', name, recordType:type, statusId:row.dataset.statusId || ''});
      notify('无法删除正在使用的状态', `仍有 ${affected.length} 条记录，请先移动到其他状态`, true);
    } else if (await appConfirm({title:`删除状态「${name}」？`, message:'状态将从当前工作流中移除。', detail:'删除后无法撤销。', confirmText:'删除状态', danger:true})) {
      row.remove();
      await saveTemplates();
    }
    return;
  }
  if (event.target.closest('#batchDeleteStatuses')) { await deleteSelectedStatuses(); return; }
  if (event.target.closest('#statusUsageOverview')) { openUsageOverview('status'); return; }
  if (event.target.closest('#saveTemplates')) { await saveTemplates(); return; }
  if (event.target.closest('#newWorkflow')) {
    if (!await confirmLeaveManagePage()) return;
    const name = await appPrompt({title:'新建工作流', message:'创建一套独立的状态流程。', confirmText:'创建', input:{label:'工作流名称', placeholder:'例如：产品研发流程'}});
    if (name?.trim()) { const base = configData.workflow_templates.find(item => item.id === selectedWorkflowId) || configData.workflow_templates[0]; const workflow = {id:`workflow_${Date.now()}`, name:name.trim(), statuses:JSON.parse(JSON.stringify(base.statuses))}; configData.workflow_templates.push(workflow); selectedWorkflowId = workflow.id; api('/workflow-templates', {method:'PUT', body:JSON.stringify(configData.workflow_templates)}).then(saved => { configData.workflow_templates = saved; renderManagePage('status_templates'); notify('已创建工作流'); }); }
  }
  if (event.target.closest('#duplicateWorkflow')) {
    if (!await confirmLeaveManagePage()) return;
    const base = configData.workflow_templates.find(item => item.id === selectedWorkflowId); const name = await appPrompt({title:'复制工作流', message:'复制当前工作流的全部状态与颜色。', confirmText:'创建副本', input:{label:'副本名称', value:`${base?.name || '工作流'} 副本`}});
    if (base && name?.trim()) { const workflow = {id:`workflow_${Date.now()}`, name:name.trim(), statuses:JSON.parse(JSON.stringify(base.statuses))}; configData.workflow_templates.push(workflow); selectedWorkflowId = workflow.id; api('/workflow-templates', {method:'PUT', body:JSON.stringify(configData.workflow_templates)}).then(saved => { configData.workflow_templates = saved; renderManagePage('status_templates'); notify('工作流已复制'); }); }
  }
  if (event.target.closest('#deleteWorkflow')) {
    if (!await confirmLeaveManagePage()) return;
    const used = projects.some(project => (project.workflow_template || 'standard') === selectedWorkflowId);
    if (used) notify('无法删除', '仍有项目正在使用这套工作流', true);
    else if (configData.workflow_templates.length <= 1) notify('无法删除', '至少需要保留一套工作流', true);
    else if (await appConfirm({title:'删除这套工作流？', message:'删除后无法恢复这套工作流配置。', detail:'只有未被任何项目使用的工作流才能删除。', confirmText:'删除工作流', danger:true})) { configData.workflow_templates = configData.workflow_templates.filter(item => item.id !== selectedWorkflowId); selectedWorkflowId = configData.workflow_templates[0].id; api('/workflow-templates', {method:'PUT', body:JSON.stringify(configData.workflow_templates)}).then(saved => { configData.workflow_templates = saved; renderManagePage('status_templates'); notify('工作流已删除'); }); }
  }
  const restoreButton = event.target.closest('[data-restore-version]');
  if (restoreButton && currentRecord) {
    api(`/records/${currentRecord.id}/restore`, {method:'POST', body:JSON.stringify({version:restoreButton.dataset.restoreVersion})}).then(async restored => {
      currentRecord = restored; $('#historyDialog').close(); await refreshData(); await openDrawer(restored.id); notify('历史版本已恢复');
    }).catch(error => notify('恢复失败', error.message, true));
  }
  const projectTabButton = event.target.closest('[data-project-tab]');
  if (projectTabButton) { projectTab = projectTabButton.dataset.projectTab; persistNavigationState(); renderProjectPage(); }
  const viewButton = event.target.closest('[data-view-mode]');
  if (viewButton) { projectViewMode = viewButton.dataset.viewMode; renderProjectPage(); }
  const editorButton = event.target.closest('[data-editor-mode]');
  if (editorButton) {
    if (editorMode === 'wysiwyg') { currentRecord.body = editorToMarkdown($('.editor')); $('.markdown-source').value = currentRecord.body; }
    else { currentRecord.body = $('.markdown-source').value; $('.editor').innerHTML = markdownToHtml(currentRecord.body, true); }
    setEditorMode(editorButton.dataset.editorMode);
  }
  const editorCommand = event.target.closest('[data-editor-command]');
  if (editorCommand) {
    $('.editor').focus();
    document.execCommand(editorCommand.dataset.editorCommand, false);
    markEditorChanged();
  }
  const editorBlock = event.target.closest('[data-editor-block]');
  if (editorBlock) {
    $('.editor').focus();
    if (editorBlock.dataset.editorBlock === 'blockquote') toggleBlockquote();
    else {
      const selection = selectionInsideEditor();
      const currentBlock = selection && closestEditorBlock(selection.anchorNode);
      const nextBlock = currentBlock?.nodeName.toLowerCase() === editorBlock.dataset.editorBlock.toLowerCase() ? 'p' : editorBlock.dataset.editorBlock;
      document.execCommand('formatBlock', false, nextBlock);
      markEditorChanged();
    }
  }
  if (event.target.closest('#insertChecklist')) {
    $('.editor').focus();
    document.execCommand('insertHTML', false, '<ul><li class="task-item"><input type="checkbox"> 待办项</li></ul><p><br></p>');
    markEditorChanged();
  }
  if (event.target.closest('#insertCodeBlock')) {
    $('.editor').focus();
    insertCodeBlock();
  }
  if (event.target.closest('#toggleEditorExpand')) {
    editorExpanded = !editorExpanded;
    detailDrawer.classList.toggle('editor-expanded', editorExpanded);
    $('#toggleEditorExpand').setAttribute('aria-pressed', String(editorExpanded));
    $('#toggleEditorExpand').textContent = editorExpanded ? '⤢ 收起编辑' : '⛶ 展开编辑';
    $('#toggleEditorExpand').title = editorExpanded ? '收起编辑区域' : '展开编辑区域';
    requestAnimationFrame(updateEditorAutoCollapse);
  }
  if (event.target.closest('#insertEditorLink')) {
    const url = await appPrompt({title:'添加网页链接', message:'为当前选中的文字设置链接地址，可省略 https://。', confirmText:'添加链接', input:{label:'网页地址', placeholder:'example.com'}});
    if (url?.trim()) {
      const normalized = /^https?:\/\/|^mailto:/i.test(url.trim()) ? url.trim() : `https://${url.trim()}`;
      $('.editor').focus(); restoreLastEditorSelection(); document.execCommand('createLink', false, normalized);
      markEditorChanged();
    }
  }
  if (event.target.closest('#insertRecordReference')) {
    $('#relationSearch').value = ''; renderRelationResults(); $('#relationDialog').showModal(); setTimeout(() => $('#relationSearch').focus(), 30);
  }
  if (event.target.closest('#copyRecordId') || event.target.closest('#drawerRecordId')) {
    const id = currentRecord?.id;
    if (id) {
      try { await navigator.clipboard.writeText(id); notify('记录 ID 已复制', id); }
      catch { await appPrompt({title:'复制记录 ID', message:'浏览器未授权自动复制，请手动复制下面的编号。', confirmText:'完成', cancelText:'关闭', input:{label:'记录编号', value:id, readOnly:true}}); }
    }
  }
  if (event.target.closest('#recordBack')) {
    if (recordNavigationStack.length) {
      if (!await confirmLeaveRecord()) return;
      const previousId = recordNavigationStack.pop();
      await openDrawer(previousId, {preserveStack:true});
    } else if (usageReturnContext) await returnToUsage();
    return;
  }
  const openProject = event.target.closest('[data-open-project]');
  if (openProject) { selectedProjectId = openProject.dataset.openProject; setPage('project'); }
  const restoreProject = event.target.closest('[data-restore-project]');
  if (restoreProject) api(`/projects/${encodeURIComponent(restoreProject.dataset.restoreProject)}`, {method:'PATCH', body:JSON.stringify({status:'active'})}).then(async () => { await refreshData(); renderManagePage('archive'); notify('项目已恢复'); }).catch(error => notify('恢复失败', error.message, true));
  const restoreTrash = event.target.closest('[data-restore-trash]');
  if (restoreTrash) api(`/trash/${encodeURIComponent(restoreTrash.dataset.restoreTrash)}/restore`, {method:'POST'}).then(async () => { await refreshData(); renderManagePage('trash'); notify('已从回收站恢复'); }).catch(error => notify('恢复失败', error.message, true));
  const purgeTrash = event.target.closest('[data-purge-trash]');
  if (purgeTrash && await appConfirm({title:'永久删除这条内容？', message:'此操作无法撤销，删除后不能从回收站恢复。', confirmText:'永久删除', danger:true})) api(`/trash/${encodeURIComponent(purgeTrash.dataset.purgeTrash)}`, {method:'DELETE'}).then(() => { renderManagePage('trash'); notify('已永久删除'); }).catch(error => notify('删除失败', error.message, true));
  if (event.target.closest('#addGlobalTag')) {
    const manager = $('.tag-manager');
    $('#addGlobalTag').insertAdjacentHTML('beforebegin', tagEditorHtml({name:'新标签', color:'#60748a', original_name:''}));
    const row = $('#addGlobalTag').previousElementSibling;
    row.classList.add('new-config-row');
    $('input[type="text"]', row)?.select();
    row.scrollIntoView({block:'center', behavior:'smooth'});
    return;
  }
  const tagUsageButton = event.target.closest('.tag-usage-button');
  if (tagUsageButton) {
    const row = tagUsageButton.closest('.tag-edit');
    openUsageDetail({kind:'tag', name:row.dataset.originalName || $('input[type="text"]', row).value.trim()});
    return;
  }
  const saveTagRow = event.target.closest('[data-save-tag-row]');
  if (saveTagRow) {
    const row = saveTagRow.closest('.tag-edit');
    if (!$('input[type="text"]', row).value.trim()) { notify('请输入标签名称', '标签名称不能为空', true); $('input[type="text"]', row).focus(); return; }
    saveTagRow.disabled = true;
    saveTagRow.textContent = '保存中…';
    if (!await saveTags() && saveTagRow.isConnected) { saveTagRow.disabled = false; saveTagRow.textContent = '保存'; }
    return;
  }
  const cancelTagRow = event.target.closest('[data-cancel-tag-row]');
  if (cancelTagRow) {
    const row = cancelTagRow.closest('.tag-edit');
    if (!row.dataset.originalName) { row.remove(); return; }
    $('input[type="text"]', row).value = row.dataset.originalName;
    syncColorPicker($('[data-color-picker]', row), row.dataset.originalColor || '#64748b');
    updateTagRowDirtyState(row);
    return;
  }
  const removeGlobalTag = event.target.closest('.remove-global-tag');
  if (removeGlobalTag) {
    const row = removeGlobalTag.closest('.tag-edit');
    const name = row.dataset.originalName || $('input[type="text"]', row).value.trim();
    const affected = tagUsageRecords(name);
    if (affected.length) {
      openUsageDetail({kind:'tag', name});
      notify('无法删除正在使用的标签', `仍有 ${affected.length} 条内容，请先从记录或知识库文档中移除此标签`, true);
    } else if (await appConfirm({title:`删除标签「${name}」？`, message:'标签将从全局标签库中移除。', detail:'删除后无法撤销。', confirmText:'删除标签', danger:true})) {
      row.remove();
      await saveTags();
    }
    return;
  }
  if (event.target.closest('#batchDeleteTags')) { await deleteSelectedTags(); return; }
  if (event.target.closest('#tagUsageOverview')) { openUsageOverview('tag'); return; }
  const usageDetail = event.target.closest('[data-usage-detail-kind]');
  if (usageDetail) {
    if (currentUsageView) usageNavigationStack.push({...currentUsageView, scrollTop:$('#usageDialogContent').scrollTop});
    openUsageDetail({kind:usageDetail.dataset.usageDetailKind, name:usageDetail.dataset.usageDetailName, recordType:usageDetail.dataset.usageDetailType || '', statusId:usageDetail.dataset.usageDetailStatusId || ''}, {preserveStack:true});
    return;
  }
  const usageRecord = event.target.closest('[data-usage-record]');
  if (usageRecord) {
    usageReturnContext = {view:{...currentUsageView}, navigationStack:usageNavigationStack.map(item => ({...item})), scrollTop:$('#usageDialogContent').scrollTop};
    $('#usageDialog').close();
    await openDrawer(usageRecord.dataset.usageRecord, {fromUsage:true});
    return;
  }
  const usageDocument = event.target.closest('[data-usage-document]');
  if (usageDocument) {
    $('#usageDialog').close();
    openDocument(usageDocument.dataset.usageDocument);
    return;
  }
  if (event.target.closest('#saveTags')) { await saveTags(); return; }
  const searchType = event.target.closest('[data-search-type]');
  if (searchType) { searchTypeFilter = searchType.dataset.searchType; renderSearchResults(lastSearchResults); }
  if (event.target.closest('#saveDataDirectory')) {
    await applyDataDirectory();
    return;
  }
  if (event.target.closest('#exportAll')) await exportArchive();
  if (event.target.closest('#importMarkdown')) $('#importMarkdownInput').click();
  if (event.target.closest('#importDirectory')) $('#importDirectoryInput').click();
  if (event.target.closest('#scanOrphanAssets')) api('/orphan-assets').then(items => { $('#orphanAssetResult').innerHTML = items.length ? `发现 ${items.length} 个，共 ${Math.max(1,Math.round(items.reduce((sum,item)=>sum+item.size,0)/1024))} KB　<button class="secondary-button danger-button" id="cleanupOrphanAssets">确认清理</button>` : '未发现无引用附件'; }).catch(error => notify('附件扫描失败', error.message, true));
  if (event.target.closest('#cleanupOrphanAssets') && await appConfirm({title:'永久清理无引用附件？', message:'这些附件当前没有被任何记录引用。', detail:'清理后文件将从磁盘永久删除，无法通过回收站恢复。', confirmText:'确认清理', danger:true})) api('/orphan-assets', {method:'DELETE'}).then(result => { $('#orphanAssetResult').textContent = `已清理 ${result.removed} 个附件`; notify('无引用附件已清理'); }).catch(error => notify('清理失败', error.message, true));
  if (event.target.closest('#exportProject')) {
    const project = projects.find(item => item.id === selectedProjectId);
    if (project) await exportArchive({project});
  }
  if (event.target.closest('#editProject')) {
    const project = projects.find(item => item.id === selectedProjectId);
    if (project) { $('#projectEditName').value = project.name; $('#projectEditDescription').value = project.description || ''; $('#projectWorkflow').innerHTML = (configData.workflow_templates || []).map(item => `<option value="${escapeHtml(item.id)}" ${item.id === (project.workflow_template || 'standard') ? 'selected' : ''}>${escapeHtml(item.name)}</option>`).join(''); projectEditSnapshot = currentProjectEditSnapshot(); $('#projectEditDialog').showModal(); }
  }
  if (event.target.closest('#archiveProject')) {
    const project = projects.find(item => item.id === selectedProjectId);
    const status = project?.status === 'archived' ? 'active' : 'archived';
    api(`/projects/${encodeURIComponent(selectedProjectId)}`, {method:'PATCH', body:JSON.stringify({status})}).then(async () => { await refreshData(); renderProjectPage(); notify(status === 'archived' ? '项目已归档' : '项目已恢复'); }).catch(error => notify('项目更新失败', error.message, true));
  }
  const removeTag = event.target.closest('[data-remove-tag]');
  if (removeTag && currentRecord) updateRecord(currentRecord.id, {tags:(currentRecord.tags || []).filter(tag => tag !== removeTag.dataset.removeTag)}, '标签已移除').then(() => openDrawer(currentRecord.id));
  if (event.target.closest('#addRecordTag') && currentRecord) {
    try { configData.tags = await api('/tags'); }
    catch (error) { notify('无法读取标签库', error.message, true); }
    const selected = new Set(currentRecord.tags || []);
    const choices = (configData?.tags || []).filter(tag => !selected.has(tag.name)).map(tag => ({label:tag.name, value:tag.name, color:tag.color}));
    const value = await appPrompt({title:'添加标签', message:choices.length ? '选择已有标签，或输入一个新标签。' : '当前没有其他可选标签，也可以直接创建新标签。', detail:choices.length ? '点击标签即可立即添加；输入新名称后按 Enter 或点击“添加”。' : '取消、右上角关闭和 Esc 均可直接退出。', confirmText:'添加', input:{label:'新标签名称（可选）', placeholder:'例如：前端、紧急、待确认', choices}});
    if (value?.trim()) updateRecord(currentRecord.id, {tags:[...new Set([...(currentRecord.tags || []), value.trim()])]}, '标签已添加').then(async () => { configData.tags = await api('/tags'); await openDrawer(currentRecord.id); });
  }
  if (event.target.closest('#addRelation') && currentRecord) { $('#relationSearch').value = ''; renderRelationResults(); $('#relationDialog').showModal(); setTimeout(() => $('#relationSearch').focus(), 30); }
  const openRelated = event.target.closest('[data-open-related]');
  if (openRelated) { if (await confirmLeaveRecord()) await openDrawer(openRelated.dataset.openRelated, {fromReference:true}); }
  const addRelated = event.target.closest('[data-add-relation]');
  if (addRelated && currentRecord) {
    await saveEditorNow();
    const id = addRelated.dataset.addRelation; const links = [...new Set([...(currentRecord.links || []), id])]; let body = currentRecord.body;
    if (!body.includes(`[[${id}]]`)) body = `${body.trim()}\n\n关联记录：[[${id}]]\n`;
    updateRecord(currentRecord.id, {links, body}, '关联记录已添加').then(async () => { $('#relationDialog').close(); await openDrawer(currentRecord.id); });
  }
  const removeRelated = event.target.closest('[data-remove-relation]');
  if (removeRelated && currentRecord) {
    const id = removeRelated.dataset.removeRelation; const links = (currentRecord.links || []).filter(item => item !== id); const body = currentRecord.body.replace(new RegExp(`\\s*关联记录：?\\[\\[${id}\\]\\]\\s*`, 'g'), '\n\n').trim();
    updateRecord(currentRecord.id, {links, body}, '关联记录已移除').then(() => openDrawer(currentRecord.id));
  }
});

$('#sidebarToggle').addEventListener('click', () => {
  const collapsed = sidebar.classList.toggle('collapsed');
  main.classList.toggle('sidebar-collapsed', collapsed);
  $('#sidebarToggle').textContent = collapsed ? '›' : '‹';
  $('#sidebarToggle').setAttribute('aria-label', collapsed ? '展开侧栏' : '折叠侧栏');
  $('#sidebarToggle').title = collapsed ? '展开侧栏' : '折叠侧栏';
});
$('#mobileMenu').addEventListener('click', () => { sidebar.classList.add('mobile-open'); showOverlay(); });
$('#themeToggle').addEventListener('click', () => {
  document.body.classList.toggle('dark');
  $('#themeToggle').textContent = document.body.classList.contains('dark') ? '☀' : '☾';
  localStorage.setItem('workbench-theme', document.body.classList.contains('dark') ? 'dark' : 'light');
});
if (localStorage.getItem('workbench-theme') === 'dark') { document.body.classList.add('dark'); $('#themeToggle').textContent = '☀'; }

$('#quickCreate').addEventListener('click', () => openCreate());
$$('.type-picker button').forEach(button => button.addEventListener('click', () => {
  const currentProject = $('#projectSelect').value || createContext.projectId;
  selectedType = button.dataset.type;
  $$('.type-picker button').forEach(item => item.classList.toggle('active', item === button));
  $('#projectSelect').closest('label').style.opacity = '1';
  updateCreateFormForType();
  renderNavigation();
  if (currentProject && projects.some(project => project.id === currentProject)) $('#projectSelect').value = currentProject;
  renderCreateStatusOptions();
}));
$('#addCreateInfoField').addEventListener('click', () => $('#createInfoFieldList').insertAdjacentHTML('beforeend', infoFieldRowHtml({}, 'create')));
$('#addDrawerInfoField').addEventListener('click', () => { $('#drawerInfoFieldList').insertAdjacentHTML('beforeend', infoFieldRowHtml()); markEditorChanged(); });
$('#drawerInfoFieldList').addEventListener('input', markEditorChanged);
document.addEventListener('dragstart', event => {
  const handle = event.target.closest('.info-field-drag');
  if (!handle) return;
  draggedInfoField = handle.closest('[data-info-field-row]');
  draggedInfoField.classList.add('dragging');
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', 'info-field');
});
document.addEventListener('dragover', event => {
  if (!draggedInfoField) return;
  const row = event.target.closest('[data-info-field-row]');
  const list = event.target.closest('#createInfoFieldList, #drawerInfoFieldList');
  if (!list) return;
  event.preventDefault();
  if (row && row !== draggedInfoField) {
    const rect = row.getBoundingClientRect();
    if (event.clientY < rect.top + rect.height / 2) row.before(draggedInfoField); else row.after(draggedInfoField);
  } else if (!row) list.appendChild(draggedInfoField);
});
document.addEventListener('drop', event => {
  if (!draggedInfoField || !event.target.closest('#createInfoFieldList, #drawerInfoFieldList')) return;
  event.preventDefault();
  const list = draggedInfoField.closest('#createInfoFieldList, #drawerInfoFieldList');
  draggedInfoField.classList.remove('dragging');
  draggedInfoField = null;
  if (list?.id === 'drawerInfoFieldList') markEditorChanged();
});
document.addEventListener('dragend', () => {
  if (!draggedInfoField) return;
  draggedInfoField.classList.remove('dragging');
  draggedInfoField = null;
});
$('#projectSelect').addEventListener('change', () => renderCreateStatusOptions());
createDialog.addEventListener('close', hideOverlayIfClear);
$('#createSubmit').addEventListener('click', createItem);
$('#searchTrigger').addEventListener('click', openSearch);
$('#appDialogInput').addEventListener('keydown', event => {
  if (event.key !== 'Enter' || event.isComposing) return;
  event.preventDefault();
  if (event.currentTarget.reportValidity()) $('#appDialog').close('confirm');
});

$('#chooseExportLocation').addEventListener('click', chooseExportDirectory);
$('#saveExportLocation').addEventListener('click', saveChosenExportDirectory);
$('#browseExportLocation').addEventListener('click', browseExportDirectory);
$('#exportLocationChoices').addEventListener('click', event => {
  const choice = event.target.closest('[data-export-path]');
  if (!choice) return;
  $$('.export-location-choice', $('#exportLocationChoices')).forEach(button => button.classList.toggle('selected', button === choice));
  loadExportDirectoryBrowser(choice.dataset.exportPath);
});
$('#exportLocationPath').addEventListener('keydown', event => {
  if (event.key === 'Enter') { event.preventDefault(); browseExportDirectory(); }
});
$('#exportDirectoryUp').addEventListener('click', () => {
  if (exportDirectoryBrowserData?.parent) loadExportDirectoryBrowser(exportDirectoryBrowserData.parent);
});
$('#exportDirectoryList').addEventListener('click', event => {
  const directory = event.target.closest('[data-directory-path]');
  if (directory) loadExportDirectoryBrowser(directory.dataset.directoryPath);
});
$('#closeDrawer').addEventListener('click', closeRecordView);
$('#saveRecord').addEventListener('click', async () => {
  if (await saveEditorNow()) notify('记录内容已保存', '标题和正文已写入 Markdown 文件');
});
$('#openExternalEditor').addEventListener('click', async () => {
  if (!currentRecord) return;
  if (editorDirty && !await saveEditorNow()) return;
  const button = $('#openExternalEditor');
  const label = $('#externalEditorButtonLabel');
  button.disabled = true;
  const originalText = label.textContent;
  label.textContent = '正在打开…';
  try {
    const result = await api(`/records/${encodeURIComponent(currentRecord.id)}/open-external`, {method:'POST'});
    notify(`已使用${result.editor}打开`, `${result.file} · 保存后工作台会自动同步修改`);
  } catch (error) { notify('无法打开外部编辑器', error.message, true); }
  finally { button.disabled = false; label.textContent = originalText; }
});
$('#chooseExternalEditor').addEventListener('click', openExternalEditorDialog);
$('#closeExternalEditorDialog').addEventListener('click', () => $('#externalEditorDialog').close());
$('#cancelExternalEditor').addEventListener('click', () => $('#externalEditorDialog').close());
$('#externalEditorOptions').addEventListener('change', event => {
  if (!event.target.matches('input[name="externalEditor"]')) return;
  $$('.external-editor-option', $('#externalEditorOptions')).forEach(option => option.classList.toggle('selected', Boolean($('input', option)?.checked)));
  $('#customEditorPathField').classList.toggle('visible', event.target.value === 'custom');
  if (event.target.value === 'custom') $('#customEditorPath').focus();
});
$('#saveExternalEditor').addEventListener('click', async () => {
  const selected = $('input[name="externalEditor"]:checked', $('#externalEditorOptions'))?.value;
  if (!selected) return;
  const button = $('#saveExternalEditor');
  button.disabled = true;
  try {
    externalEditorData = await api('/external-editor', {method:'PUT', body:JSON.stringify({id:selected, path:$('#customEditorPath').value.trim()})});
    updateExternalEditorButton();
    $('#externalEditorDialog').close();
    notify(`默认编辑器已设为 ${externalEditorData.selected_name}`);
  } catch (error) { notify('外部编辑器设置失败', error.message, true); }
  finally { button.disabled = false; }
});
$('#saveOnLeave').addEventListener('change', event => {
  localStorage.setItem('workbench-save-on-leave', String(event.target.checked));
  notify(event.target.checked ? '已开启离开时自动保存' : '已关闭离开时自动保存', event.target.checked ? '关闭记录或切换记录时会自动保存修改' : '未保存修改离开前会询问你');
});
$('#showHistory').addEventListener('click', showHistory);
$('#closeHistory').addEventListener('click', () => $('#historyDialog').close());
$('#usageDialogBack').addEventListener('click', returnWithinUsageDialog);
$('#closeUsageDialog').addEventListener('click', closeUsageDialog);
$('#closeRelation').addEventListener('click', () => $('#relationDialog').close());
$('#relationSearch').addEventListener('input', event => renderRelationResults(event.target.value));
$('#addAttachment').addEventListener('click', () => $('#attachmentInput').click());
$('#attachmentInput').addEventListener('change', event => { uploadAttachment(event.target.files[0]); event.target.value = ''; });
$('#drawerStatus').addEventListener('change', event => { if (currentRecord) { const statusMeta = statusesFor(currentRecord.type, currentRecord.project_id).find(item => item.name === event.target.value); updateRecord(currentRecord.id, {status:event.target.value, completed:Boolean(statusMeta?.completed)}, '状态已保存'); } });
$('#drawerPriority').addEventListener('change', event => { if (currentRecord) updateRecord(currentRecord.id, {priority:event.target.value}, '优先级已保存'); });
$('#drawerDue').addEventListener('change', event => { if (currentRecord) updateRecord(currentRecord.id, {due:event.target.value || null}, '截止日期已保存'); });
$('#convertRecord').addEventListener('click', async () => {
  if (!currentRecord) return;
  const targetType = currentRecord.type === 'todo' ? 'issue' : 'todo';
  const projectId = currentRecord.project_id || projects.find(item => item.status !== 'archived')?.id;
  if (!projectId) return notify('无法转换', '请先创建一个项目', true);
  try {
    const converted = await api('/records', {method:'POST', body:JSON.stringify({type:targetType, title:currentRecord.title, project_id:projectId, priority:currentRecord.priority, tags:currentRecord.tags || [], body:currentRecord.body, links:[currentRecord.id]})});
    await updateRecord(currentRecord.id, {links:[...new Set([...(currentRecord.links || []), converted.id])]}, `已转换为${typeNames[targetType]}`);
    await refreshData(); await openDrawer(converted.id);
  } catch (error) { notify('转换失败', error.message, true); }
});
$('#deleteRecord').addEventListener('click', async () => {
  if (!currentRecord || !await appConfirm({title:'将记录移入回收站？', message:`「${currentRecord.title}」`, detail:'记录文件不会立即永久删除，可稍后从回收站恢复。', confirmText:'移入回收站', danger:true})) return;
  try { const deletedId = currentRecord.id; await api(`/records/${deletedId}`, {method:'DELETE'}); clearEditorDraft(deletedId); editorDirty = false; await closeDrawer(); currentRecord = null; await refreshData(); notify('记录已移入回收站'); }
  catch (error) { notify('删除失败', error.message, true); }
});
$('#deleteProject').addEventListener('click', async () => {
  const project = projects.find(item => item.id === selectedProjectId);
  if (!project || !await appConfirm({title:'删除整个项目？', message:`项目「${project.name}」及其中的全部记录将移入回收站。`, detail:'项目目录不会立即永久删除，可在回收站中恢复。', confirmText:'删除项目', danger:true})) return;
  try { await api(`/projects/${encodeURIComponent(project.id)}`, {method:'DELETE'}); selectedProjectId = ''; await refreshData(); setPage('home'); notify('项目已移入回收站'); }
  catch (error) { notify('项目删除失败', error.message, true); }
});
async function saveProjectEdit() {
  try {
    await api(`/projects/${encodeURIComponent(selectedProjectId)}`, {method:'PATCH', body:JSON.stringify({name:$('#projectEditName').value.trim(), description:$('#projectEditDescription').value, workflow_template:$('#projectWorkflow').value})});
    projectEditSnapshot = currentProjectEditSnapshot();
    $('#projectEditDialog').close(); await refreshData(); renderProjectPage(); notify('项目资料已保存'); return true;
  } catch (error) { notify('项目保存失败', error.message, true); return false; }
}
$('#saveProjectEdit').addEventListener('click', saveProjectEdit);
$('#projectEditDialog').addEventListener('click', async event => {
  const cancelButton = event.target.closest('button[value="cancel"]');
  if (!cancelButton || !hasUnsavedProjectEdit()) return;
  event.preventDefault();
  const choice = await askUnsavedChanges('项目资料');
  if (choice === 'save') await saveProjectEdit();
  else if (choice === 'discard') { projectEditSnapshot = null; $('#projectEditDialog').close(); }
});
$('#projectEditDialog').addEventListener('cancel', async event => {
  if (!hasUnsavedProjectEdit()) return;
  event.preventDefault();
  const choice = await askUnsavedChanges('项目资料');
  if (choice === 'save') await saveProjectEdit();
  else if (choice === 'discard') { projectEditSnapshot = null; $('#projectEditDialog').close(); }
});

async function dismissDialogFromBackdrop(dialog) {
  // 冲突合并必须明确选择处理方式，避免误点遮罩丢失尚未合并的内容。
  if (dialog.id === 'conflictDialog') return;
  if (dialog.id === 'projectEditDialog' && hasUnsavedProjectEdit()) {
    const choice = await askUnsavedChanges('项目资料');
    if (choice === 'save') await saveProjectEdit();
    else if (choice === 'discard') { projectEditSnapshot = null; dialog.close('cancel'); }
    return;
  }
  if (dialog.id === 'documentDialog') { await closeDocumentEditor(); return; }
  if (dialog.id === 'usageDialog') closeUsageDialog();
  else dialog.close('cancel');
}

$$('dialog').forEach(dialog => dialog.addEventListener('click', event => {
  if (event.target !== dialog || !dialog.open) return;
  const rect = dialog.getBoundingClientRect();
  const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
  if (outside) dismissDialogFromBackdrop(dialog);
}));
$('#conflictExternal').addEventListener('click', async () => {
  if (!conflictRecord) return; const id = conflictRecord.id; editorDirty = false; $('#conflictDialog').close(); conflictRecord = null; await refreshData(); openDrawer(id); notify('已载入磁盘版本');
});
$('#conflictLocal').addEventListener('click', async () => {
  if (!conflictRecord || !currentRecord) return; const id = currentRecord.id; const body = $('#localConflictContent').value; const changes = {body, ...(currentRecord.type === 'info' ? {info_fields:infoFieldsFrom($('#drawerInfoFieldList')), info_color:drawerInfoColor()} : {})}; $('#conflictDialog').close(); conflictRecord = null; editorDirty = false; await updateRecord(id, changes, '已保留工作台版本'); openDrawer(id);
});
$('#conflictCopy').addEventListener('click', async () => {
  if (!conflictRecord || !currentRecord) return;
  try {
    const copyPayload = {type:currentRecord.type, title:`${currentRecord.title}（冲突副本）`, project_id:currentRecord.project_id, tags:currentRecord.tags || [], body:$('#localConflictContent').value, links:[currentRecord.id], ...(currentRecord.type === 'info' ? {info_fields:infoFieldsFrom($('#drawerInfoFieldList')), info_color:drawerInfoColor()} : {status:currentRecord.status, priority:currentRecord.priority})};
    const copy = await api('/records', {method:'POST', body:JSON.stringify(copyPayload)});
    const originalId = conflictRecord.id; editorDirty = false; $('#conflictDialog').close(); conflictRecord = null; await refreshData(); openDrawer(originalId); notify(`已保留两个版本`, `工作台内容已另存为 ${copy.id}`);
  } catch (error) { notify('副本保存失败', error.message, true); }
});
$('#conflictMerged').addEventListener('click', async () => {
  if (!conflictRecord || !currentRecord) return; const id = currentRecord.id; const body = $('#mergedConflictContent').value; const changes = {body, ...(currentRecord.type === 'info' ? {info_fields:infoFieldsFrom($('#drawerInfoFieldList')), info_color:drawerInfoColor()} : {})}; $('#conflictDialog').close(); conflictRecord = null; editorDirty = false; await updateRecord(id, changes, '合并结果已保存'); openDrawer(id);
});
$('#confirmImport').addEventListener('click', async () => {
  if (!pendingImport) return;
  const type = $('#importType').value, projectId = $('#importProject').value || null;
  if (!projectId) return notify('请选择项目', '问题、待办和信息必须属于一个项目', true);
  try { const imported = await api('/import', {method:'POST', body:JSON.stringify({name:pendingImport.name, content:pendingImport.content, type, title:$('#importTitle').value.trim(), project_id:projectId})}); $('#importPreviewDialog').close(); pendingImport = null; await refreshData(); notify(`已导入：${imported.title}`); openDrawer(imported.id); }
  catch (error) { notify('导入失败', error.message, true); }
});
overlay.addEventListener('click', async () => {
  closeSearch();
  if (detailDrawer.classList.contains('visible') && !await closeRecordView()) return;
  sidebar.classList.remove('mobile-open');
  if (createDialog.open) createDialog.close();
  hideOverlayIfClear();
});

document.addEventListener('keydown', event => {
  if (event.defaultPrevented) return;
  if ($('#documentDialog').open && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); saveDocument(); return; }
  if (event.target.id === 'documentVisualEditor' && (event.ctrlKey || event.metaKey) && ['b','i'].includes(event.key.toLowerCase())) {
    event.preventDefault(); document.execCommand(event.key.toLowerCase() === 'b' ? 'bold' : 'italic', false); return;
  }
  if (event.key === 'Enter' && !event.isComposing && event.target.matches('.new-config-row input[type="text"]')) {
    const saveButton = event.target.closest('.new-config-row')?.querySelector('[data-save-manage]');
    if (saveButton && !saveButton.disabled) {
      event.preventDefault();
      saveButton.click();
      return;
    }
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); openSearch(); }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'n') { event.preventDefault(); openCreate(); }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's' && detailDrawer.classList.contains('visible')) { event.preventDefault(); saveEditorNow().then(saved => { if (saved) notify('记录内容已保存', '标题和正文已写入 Markdown 文件'); }); }
  if (event.key === 'Escape') { closeSearch(); if (detailDrawer.classList.contains('visible')) closeRecordView(); sidebar.classList.remove('mobile-open'); }
});

$('#todayTodoList').addEventListener('change', async event => {
  const row = event.target.closest('[data-record-id]');
  if (event.target.matches('input[type="checkbox"]') && row) await updateRecord(row.dataset.recordId, {completed:event.target.checked, status:event.target.checked ? '已完成' : '待办'}, event.target.checked ? '待办已完成' : '待办已恢复');
});

let searchTimer;
$('#searchInput').addEventListener('input', event => {
  updateSearchClearButton();
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    if (!apiAvailable) return;
    try { renderSearchResults(await api(`/search?q=${encodeURIComponent(event.target.value)}`)); }
    catch (error) { notify('搜索失败', error.message, true); }
  }, 180);
});
$('#clearSearchInput').addEventListener('click', async () => {
  clearTimeout(searchTimer);
  const input = $('#searchInput');
  input.value = '';
  updateSearchClearButton();
  input.focus();
  if (!apiAvailable) return;
  try { renderSearchResults(await api('/search?q=')); }
  catch (error) { notify('搜索失败', error.message, true); }
});

$('.drawer-title').addEventListener('input', markEditorChanged);
$('.editor-toolbar').addEventListener('mousedown', event => { if (event.target.closest('button')) event.preventDefault(); });
$('#editorHeadingLevel').addEventListener('change', event => {
  $('.editor').focus();
  restoreLastEditorSelection();
  document.execCommand('formatBlock', false, event.target.value);
  markEditorChanged();
});
$('#codeLanguage').addEventListener('change', event => {
  $('.editor').focus();
  restoreLastEditorSelection();
  const selection = selectionInsideEditor();
  const element = selection && (selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement);
  const code = element?.closest('pre')?.querySelector('code');
  if (!code) return;
  const language = normalizeCodeLanguage(event.target.value);
  const rawCode = codeElementToText(code);
  code.dataset.language = language;
  code.innerHTML = syntaxHighlightCode(rawCode, language) || '<br>';
  placeCaret(code, false);
  markEditorChanged();
});
$('.editor').addEventListener('keydown', event => {
  if (handleCodeBlockEnter(event)) return;
  if (handleQuoteEnter(event)) return;
  if (event.key === 'Tab' && !event.isComposing) {
    const selection = selectionInsideEditor();
    const element = selection && (selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement);
    if (element?.closest('pre')) {
      event.preventDefault();
      insertTextAtSelection('  ');
      markEditorChanged();
      return;
    }
    if (element?.closest('li')) {
      event.preventDefault();
      document.execCommand(event.shiftKey ? 'outdent' : 'indent', false);
      markEditorChanged();
      return;
    }
  }
  if (!(event.ctrlKey || event.metaKey) || event.isComposing) return;
  const key = event.key.toLowerCase();
  const commands = {
    b:'bold',
    i:'italic',
    '7':event.shiftKey ? 'insertOrderedList' : '',
    '8':event.shiftKey ? 'insertUnorderedList' : ''
  };
  if (event.shiftKey && key === 'q') {
    event.preventDefault();
    toggleBlockquote();
  } else if (commands[key]) {
    event.preventDefault();
    document.execCommand(commands[key], false);
    markEditorChanged();
  }
});
$('.editor').addEventListener('input', markEditorChanged);
$('.editor').addEventListener('change', event => { if (event.target.matches('input[type="checkbox"]')) { editorDirty = true; scheduleEditorSave(); } });
$('.markdown-source').addEventListener('input', event => { editorDirty = true; $('.markdown-preview').innerHTML = markdownToHtml(event.target.value); scheduleEditorSave(); });
$('.editor-area').addEventListener('focusin', event => {
  if (event.target.matches('.editor, .markdown-source')) expandEditorContent();
});
$('.editor-area').addEventListener('click', event => {
  if (event.target.closest('.editor-auto-expand, .editor, .markdown-source, .markdown-preview')) expandEditorContent({focus:Boolean(event.target.closest('.editor-auto-expand'))});
});
$('.editor-area').addEventListener('dragover', event => { event.preventDefault(); event.currentTarget.classList.add('drop-active'); });
$('.editor-area').addEventListener('dragleave', event => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.classList.remove('drop-active'); });
$('.editor-area').addEventListener('drop', event => { event.preventDefault(); event.currentTarget.classList.remove('drop-active'); if (event.dataTransfer.files[0]) uploadAttachment(event.dataTransfer.files[0]); });
$('.editor-area').addEventListener('paste', event => {
  const image = [...(event.clipboardData?.items || [])].find(item => item.type.startsWith('image/'))?.getAsFile();
  if (image) {
    event.preventDefault();
    const named = new File([image], `screenshot-${Date.now()}.${image.type.split('/')[1] || 'png'}`, {type:image.type});
    uploadAttachment(named, {insertion:createPastedImageInsertion(event.target)});
  } else if (event.target.closest('.editor') && event.clipboardData?.types.includes('text/html')) {
    event.preventDefault();
    document.execCommand('insertText', false, event.clipboardData.getData('text/plain'));
  }
});
$('#documentCodeLanguage').addEventListener('change', event => {
  const editor = $('#documentVisualEditor');
  editor.focus();
  restoreDocumentSelection();
  const selection = selectionInsideEditor(editor);
  const element = selection && (selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement);
  const code = element?.closest('pre')?.querySelector('code');
  if (!code) return;
  const language = normalizeCodeLanguage(event.target.value);
  const rawCode = codeElementToText(code);
  code.dataset.language = language;
  code.innerHTML = syntaxHighlightCode(rawCode, language) || '<br>';
  placeCaret(code, false);
  captureDocumentSelection();
  markDocumentChanged();
});
$('#documentVisualEditor').addEventListener('keydown', event => {
  if (handleDocumentTaskListEnter(event)) return;
  if (handleCodeBlockEnter(event, markDocumentChanged)) return;
  if (handleQuoteEnter(event, markDocumentChanged)) return;
  if (event.key === 'Tab' && !event.isComposing) {
    const editor = event.currentTarget;
    const selection = selectionInsideEditor(editor);
    const element = selection && (selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement);
    if (element?.closest('pre')) {
      event.preventDefault(); insertTextAtSelection('  ', editor); markDocumentChanged(); return;
    }
    if (element?.closest('li')) {
      event.preventDefault(); document.execCommand(event.shiftKey ? 'outdent' : 'indent', false); markDocumentChanged(); return;
    }
  }
  if (!(event.ctrlKey || event.metaKey) || event.isComposing) return;
  const key = event.key.toLowerCase();
  const commands = {b:'bold', i:'italic', u:'underline'};
  if (event.shiftKey && key === 'q') {
    event.preventDefault(); toggleBlockquote(event.currentTarget, markDocumentChanged);
  } else if (commands[key]) {
    event.preventDefault(); document.execCommand(commands[key], false); markDocumentChanged();
  }
});
$('#documentVisualEditor').addEventListener('input', () => { finishDocumentColorBoundaryInput(); markDocumentChanged(); });
$('#documentVisualEditor').addEventListener('change', event => { if (event.target.matches('input[type="checkbox"]')) markDocumentChanged(); });
document.addEventListener('selectionchange', () => {
  const selection = selectionInsideEditor();
  if (!selection) return;
  lastEditorRange = selection.getRangeAt(0).cloneRange();
  updateEditorToolbarState();
});
document.addEventListener('selectionchange', () => requestAnimationFrame(() => { updateDocumentSelectionToolbar(); updateDocumentToolbarState(); }));
$('#documentFormatToolbar').addEventListener('mousedown', event => { if (event.target.closest('button')) event.preventDefault(); });
$('#documentSelectionToolbar').addEventListener('mousedown', event => { if (event.target.closest('button')) event.preventDefault(); });
$('#documentColorPalette').addEventListener('mousedown', event => { if (event.target.closest('button')) event.preventDefault(); });
$('#documentDialog').addEventListener('cancel', event => { event.preventDefault(); closeDocumentEditor(); });
document.addEventListener('change', async event => {
  if (event.target.id === 'knowledgeImportInput') { const files = [...event.target.files]; event.target.value = ''; await importKnowledgeDocuments(files); return; }
  if (event.target.id === 'selectAllStatuses') { $$('[data-status-select]').forEach(input => { input.checked = event.target.checked; }); updateStatusBatchUI(); return; }
  if (event.target.matches('[data-status-select]')) { updateStatusBatchUI(); return; }
  if (event.target.matches('.status-edit-row .status-completed')) { updateStatusRowDirtyState(event.target.closest('.status-edit-row')); return; }
  if (event.target.id === 'selectAllTags') { $$('[data-tag-select]').forEach(input => { input.checked = event.target.checked; }); updateTagBatchUI(); return; }
  if (event.target.matches('[data-tag-select]')) { updateTagBatchUI(); return; }
  if (event.target.matches('[data-document-custom-color]')) { applyDocumentColor(event.target.value, event.target.dataset.documentCustomColor); return; }
  if (event.target.id === 'selectVisibleDocuments') {
    const ids = (event.target.dataset.visibleIds || '').split(',').filter(Boolean);
    ids.forEach(id => event.target.checked ? documentSelection.add(id) : documentSelection.delete(id));
    $$('[data-document-select]').forEach(input => { input.checked = documentSelection.has(input.dataset.documentSelect); }); updateDocumentSelectionUI(); return;
  }
  if (event.target.matches('[data-document-select]')) {
    const id = event.target.dataset.documentSelect;
    if (event.target.checked) documentSelection.add(id); else documentSelection.delete(id);
    updateDocumentSelectionUI(); return;
  }
  if (event.target.id === 'documentHeading') { $('#documentVisualEditor').focus(); restoreDocumentSelection(); document.execCommand('formatBlock', false, event.target.value); markDocumentChanged(); return; }
  if (event.target.matches('[data-selection-heading]')) { $('#documentVisualEditor').focus(); restoreDocumentSelection(); document.execCommand('formatBlock', false, event.target.value); markDocumentChanged(); return; }
  if (event.target.matches('#documentTagOptions input')) { updateDocumentTagSummary(); markDocumentChanged(); return; }
  if (event.target.id === 'projectAssetInput') {
    const files = [...event.target.files]; event.target.value = '';
    await uploadProjectAssets(files); return;
  }
  if (event.target.id === 'projectAssetCategoryFilter') {
    projectAssetCategoryFilter = event.target.value; renderProjectPage(); return;
  }
  if (event.target.id === 'selectAllProjectAssets') {
    $$('.project-asset-select').forEach(input => { input.checked = event.target.checked; }); updateAssetBatchToolbar(); return;
  }
  if (event.target.matches('.project-asset-select')) { updateAssetBatchToolbar(); return; }
  if (event.target.matches('[data-project-asset-category],[data-record-asset-category]')) {
    const select = event.target;
    const isProjectAsset = Boolean(select.dataset.projectAssetCategory);
    const asset = isProjectAsset
      ? projectAssetLibrary.find(item => item.id === select.dataset.projectAssetCategory)
      : {name:select.dataset.recordAssetName};
    if (!asset?.name) return;
    let category = select.value;
    if (category === '__custom__') {
      category = await appPrompt({title:'新建附件分类', message:`为「${asset.name}」设置新的分类。`, confirmText:'保存分类', input:{label:'分类名称', placeholder:'例如：会议纪要'}});
      if (!category?.trim()) { renderProjectPage(); return; }
    }
    try {
      const selection = isProjectAsset
        ? {source:'project', id:asset.id}
        : {source:'record', record_id:select.dataset.recordAssetCategory, name:select.dataset.recordAssetName};
      await applyAssetCategory([selection], category);
    } catch (error) { renderProjectPage(); notify('分类更新失败', error.message, true); }
    return;
  }
  if (event.target.id === 'timelineFilterSelectAll') {
    $$('.timeline-filter-values input[type="checkbox"]', $('#timelineFilterPopover')).forEach(input => { input.checked = event.target.checked; });
    return;
  }
  if (event.target.matches('#timelineFilterPopover .timeline-filter-values input[type="checkbox"]')) {
    const options = $$('.timeline-filter-values input[type="checkbox"]', $('#timelineFilterPopover'));
    $('#timelineFilterSelectAll').checked = options.length > 0 && options.every(input => input.checked);
    return;
  }
  if (event.target.id === 'workflowSelector') {
    const nextWorkflowId = event.target.value;
    if (!await confirmLeaveManagePage()) { event.target.value = selectedWorkflowId; return; }
    selectedWorkflowId = nextWorkflowId;
    renderManagePage('status_templates');
    return;
  }
  if (['searchProjectFilter','searchTagFilter','searchStatusFilter','searchPriorityFilter'].includes(event.target.id)) {
    searchFilters = {project:$('#searchProjectFilter').value, tag:$('#searchTagFilter').value, status:$('#searchStatusFilter').value, priority:$('#searchPriorityFilter').value}; renderSearchResults(lastSearchResults); return;
  }
  if (event.target.id === 'filterStatus' || event.target.id === 'filterTag' || event.target.id === 'filterPriority') {
    projectFilters = {status:$('#filterStatus').value, tag:$('#filterTag').value, priority:$('#filterPriority').value}; renderProjectPage(); return;
  }
  if (event.target.id === 'importDirectoryInput' && event.target.files.length) {
    const files = [...event.target.files].filter(file => file.name.toLowerCase().endsWith('.md'));
    const suggested = files[0]?.webkitRelativePath?.split('/')[0] || '导入项目'; const name = await appPrompt({title:'导入 Markdown 项目', message:`检测到 ${files.length} 个 Markdown 文件。`, confirmText:'开始导入', input:{label:'导入后的项目名称', value:suggested}});
    if (name?.trim()) (async () => { try { const project = await api('/projects', {method:'POST', body:JSON.stringify({name:name.trim(), description:'从本地 Markdown 目录导入'})}); let count = 0; for (const file of files) { await api('/import', {method:'POST', body:JSON.stringify({name:file.name, content:await file.text(), project_id:project.id})}); count += 1; } selectedProjectId = project.id; await refreshData(); notify(`已导入项目：${name.trim()}`, `共导入 ${count} 个 Markdown 文件`); setPage('project'); } catch (error) { notify('目录导入失败', error.message, true); } })();
    event.target.value = ''; return;
  }
  if (event.target.id !== 'importMarkdownInput' || !event.target.files[0]) return;
  const file = event.target.files[0];
  file.text().then(content => prepareImportPreview(file.name, content)).catch(error => notify('文件读取失败', error.message, true));
  event.target.value = '';
});

async function initialize() {
  try {
    const [health, config] = await Promise.all([api('/health'), api('/config')]);
    apiAvailable = health.ok;
    configData = config;
    window.workbenchDataDir = config.data_dir;
    const navigation = readNavigationState();
    selectedProjectId = typeof navigation.projectId === 'string' ? navigation.projectId : '';
    const storedProjectId = selectedProjectId;
    if (['overview','issues','todos','mixed','infos','assets'].includes(navigation.projectTab)) projectTab = navigation.projectTab;
    await refreshData();
    await loadExternalEditors();
    updateDocumentColorButtons();
    const requestedPage = location.hash.replace('#', '');
    if (requestedPage.startsWith('record/')) { setPage('home', {preserveHash:true}); openDrawer(requestedPage.slice(7)); }
    else if (requestedPage) setPage(requestedPage);
    else {
      const storedPage = typeof navigation.page === 'string' ? navigation.page : 'home';
      const missingStoredProject = storedPage === 'project' && storedProjectId && !projects.some(project => project.id === storedProjectId);
      setPage(missingStoredProject ? 'home' : storedPage);
    }
    setInterval(async () => {
      if (!apiAvailable || document.hidden) return;
      try {
        const signatures = (await api('/record-signatures')).filter(record => record.type !== 'idea');
        const signature = recordSignature(signatures);
        if (signature !== lastRecordSignature) {
          const latest = (await api('/records?summary=1')).filter(record => record.type !== 'idea');
          const latestOpen = currentRecord ? latest.find(item => item.id === currentRecord.id) : null;
          const openChanged = latestOpen && latestOpen.file_mtime !== currentRecord.file_mtime;
          if (openChanged && detailDrawer.classList.contains('visible') && editorDirty) showConflict(latestOpen);
          else if (openChanged && detailDrawer.classList.contains('visible')) openDrawer(latestOpen.id);
          records = latest; lastRecordSignature = signature; renderDashboard();
          if ($('#projectPage').classList.contains('active')) renderProjectPage();
          if (!detailDrawer.classList.contains('visible')) notify('检测到外部 Markdown 修改', '工作台内容已重新载入');
        }
        if ($('#documentDialog').open || activeManagePage === 'documents') {
          const latestDocuments = await api('/documents');
          const latestOpenDocument = currentDocument ? latestDocuments.find(item => item.id === currentDocument.id) : null;
          const documentChanged = latestOpenDocument && latestOpenDocument.file_mtime !== currentDocument.file_mtime;
          if (documentChanged && $('#documentDialog').open) {
            if (documentHasUnsavedChanges()) {
              const mtime = String(latestOpenDocument.file_mtime || '');
              if ($('#documentDialog').dataset.pendingExternalMtime !== mtime) {
                $('#documentDialog').dataset.pendingExternalMtime = mtime;
                notify('检测到外部文档修改', '当前还有未保存编辑，请先保存或放弃后重新打开文档', true);
              }
            } else reloadCurrentDocumentFromDisk(latestOpenDocument);
          }
          documents = latestDocuments;
          if (activeManagePage === 'documents') renderDocumentsPage();
        }
      } catch { /* 保持当前内容，下一次轮询重试 */ }
    }, 15_000);
  } catch (error) {
    apiAvailable = false;
    notify('当前为静态预览模式', '请运行 python server.py --seed-demo 启用 Markdown 文件保存', true);
  } finally {
    requestAnimationFrame(() => document.documentElement.classList.remove('navigation-restoring'));
  }
}

document.addEventListener('input', event => {
  if (event.target.matches('.tag-edit input[type="text"]')) { updateTagRowDirtyState(event.target.closest('.tag-edit')); return; }
  if (event.target.matches('.status-edit-row input[type="text"]')) { updateStatusRowDirtyState(event.target.closest('.status-edit-row')); return; }
  if (event.target.id === 'documentCategorySearch') { documentFilters.categoryQuery = event.target.value; renderDocumentsPage(); const input = $('#documentCategorySearch'); input?.focus(); input?.setSelectionRange(input.value.length, input.value.length); return; }
  if (event.target.matches('[data-document-file-search]')) { const category = event.target.dataset.documentFileSearch; documentCategoryFileQueries[category] = event.target.value; documentOpenCategories.add(category); renderDocumentsPage(); const input = $(`[data-document-file-search="${CSS.escape(category)}"]`); input?.focus(); input?.setSelectionRange(input.value.length, input.value.length); return; }
  if (['documentVisualEditor','documentBody','documentTitle','documentCategory'].includes(event.target.id)) {
    markDocumentChanged();
    if (event.target.id === 'documentTitle') $('#documentOutlineTitle').textContent = event.target.value.trim() || '新建文档';
    if (['documentVisualEditor','documentBody'].includes(event.target.id)) scheduleDocumentOutlineUpdate();
    return;
  }
  if (event.target.id === 'projectAssetSearch') {
    projectAssetSearch = event.target.value;
    clearTimeout(projectAssetSearchTimer);
    projectAssetSearchTimer = setTimeout(() => { if (projectTab === 'assets') renderProjectPage(); }, 120);
    return;
  }
  if (event.target.matches('[data-info-field-value]')) autoSizeInfoFieldTextareas(event.target.closest('[data-info-field-row]'));
  if (event.target.matches('[data-color-picker] input[type="color"]')) {
    syncColorPicker(event.target.closest('[data-color-picker]'), event.target.value);
    rememberRecentColor('workbench-recent-management-colors', event.target.value);
    updateTagRowDirtyState(event.target.closest('.tag-edit'));
    updateStatusRowDirtyState(event.target.closest('.status-edit-row'));
    if (event.target.closest('#infoColorPicker')) markEditorChanged();
  }
  if (event.target.id === 'timelineFilterSearch') {
    const needle = event.target.value.trim().toLowerCase();
    $$('.timeline-filter-values .timeline-filter-option', $('#timelineFilterPopover')).forEach(option => { option.hidden = Boolean(needle) && !option.dataset.filterSearch.includes(needle); });
  }
});

window.addEventListener('beforeunload', event => {
  persistEditorDraft();
  persistDocumentDraft();
  if (editorDirty && autoSaveOnLeaveEnabled() && currentRecord) {
    fetch(`/api/records/${encodeURIComponent(currentRecord.id)}`, {
      method:'PATCH',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({title:$('.drawer-title').value.trim() || currentRecord.title, body:localEditorContent(), ...(currentRecord.type === 'info' ? {info_fields:infoFieldsFrom($('#drawerInfoFieldList')), info_color:drawerInfoColor()} : {})}),
      keepalive:true
    }).catch(() => {});
  }
  if (!(editorDirty && !autoSaveOnLeaveEnabled()) && !documentDirty && !hasUnsavedManageChanges() && !hasUnsavedProjectEdit()) return;
  event.preventDefault();
  event.returnValue = '';
});

window.addEventListener('pagehide', () => { persistEditorDraft(); persistDocumentDraft(); });

initialize();
