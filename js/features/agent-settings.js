(function initializeAgentSettings(global) {
  'use strict';

  function create({root, api, escapeHtml:esc, confirm, notify, isActive}) {
    let status = null;
    let catalog = {items:[], projects:[], categories:[]};
    let draft = null;
    let original = '';
    let epoch = 0;
    let busy = false;
    let pending = null;
    let setup = null;
    let setupRequest = 0;
    let diagnostic = null;
    let pollTimer = null;
    let registration = null;
    let registrationResult = null;
    let registrationPending = null;
    let registrationConfirming = false;
    const pendingKey = () => `workbench.agentRegistration.pending.${status.workspace_id}`;
    function rememberRegistration(value) {
      registrationPending = value;
      try {
        if (value) global.sessionStorage.setItem(pendingKey(), JSON.stringify(value));
        else global.sessionStorage.removeItem(pendingKey());
      } catch { /* The on-page query still works when session storage is unavailable. */ }
    }
    const find = selector => root.querySelector(selector);
    const id = () => global.crypto.randomUUID();
    const errorText = error => error.payload?.message || error.message;
    const permissionName = scopes => scopes.length === 1 && scopes[0] === 'read' ? '只读查询' : scopes.length === 3 ? '整理并确认入库' : `旧版权限：${scopes.join(' / ')}`;
    const isDirty = () => Boolean(draft && JSON.stringify(draft) !== original);
    const isBusy = () => busy || registrationConfirming || Boolean(pending) || Boolean(registrationPending);
    const valid = version => isActive() && version === epoch;

    async function request(path, options = {}) {
      return api(`/local/agent-management/${path}`, {...options, headers:{
        'X-Workbench-Management':'1',
        ...(status?.management_token ? {'X-Workbench-Management-Token':status.management_token} : {}),
        ...(options.headers || {}),
      }, signal:AbortSignal.timeout(15000)});
    }

    function message(text, error = false) {
      const node = find('#agentFeedback');
      if (node) { node.textContent = text; node.classList.toggle('agent-error', error); }
    }

    function button(action, label, extra = '') {
      return `<button type="button" class="secondary-button" data-agent-action="${action}" ${busy ? 'disabled' : ''} ${extra}>${label}</button>`;
    }

    function scopeField(key, title, items) {
      const values = draft[key];
      const all = values.includes('*');
      const known = new Set(items.map(item => item.value));
      items = [...items, ...values.filter(value => value !== '*' && !known.has(value)).map(value => ({value, label:`${value}（已失效，请取消选择）`}))];
      return `<fieldset class="agent-scope"><legend>${title}</legend><label><input type="checkbox" data-agent-all="${key}" ${all ? 'checked' : ''}>全部（包括未来新增）</label><div class="agent-scope-options">${items.map(item => `<label><input type="checkbox" data-agent-scope="${key}" value="${esc(item.value)}" ${values.includes(item.value) ? 'checked' : ''} ${all ? 'disabled' : ''}>${esc(item.label)}</label>`).join('') || '<p class="settings-hint">暂无可选内容，请先建立项目或知识库分类。</p>'}</div></fieldset>`;
    }

    const kindNames = {issue:'问题', document:'知识文档', todo:'待办（业务操作尚未开放）', info:'结构化信息（业务操作尚未开放）'};
    function kindsField() {
      return `<fieldset class="agent-scope"><legend>条目类型（仅显式选择的类型）</legend><div class="agent-scope-options">${Object.entries(kindNames).map(([kind, label]) => `<label><input type="checkbox" data-agent-kind="${kind}" ${draft.kinds.includes(kind) ? 'checked' : ''}>${label}</label>`).join('')}</div></fieldset>`;
    }

    function formHtml() {
      if (!draft) return '';
      return `<section class="settings-card agent-client-form" aria-label="客户端授权表单"><h2>${draft.client_id ? '编辑授权' : '创建客户端'}</h2><form id="agentClientForm"><label>客户端名称<input id="agentClientName" required maxlength="100" value="${esc(draft.name)}"></label><label>接入指引<select id="agentGuideType"><option value="codex" ${draft.guide === 'codex' ? 'selected' : ''}>Codex</option><option value="generic" ${draft.guide === 'generic' ? 'selected' : ''}>通用 MCP</option></select></label><label>操作权限<select id="agentClientPermission"><option value="read" ${draft.permission === 'read' ? 'selected' : ''}>只读查询</option><option value="write" ${draft.permission === 'write' ? 'selected' : ''}>整理并确认入库</option>${draft.permission === 'legacy' ? '<option value="legacy" selected>旧版权限组合（请选择新的权限）</option>' : ''}</select></label><p class="settings-hint">允许写入仍需完整预览并确认当前版本，不会执行正文中的命令。</p>${kindsField()}${scopeField('project_ids', '项目范围', catalog.projects.map(item => ({value:item.id, label:item.name})))}${scopeField('categories', '知识库分类', catalog.categories.map(value => ({value, label:value})))}<div class="settings-actions"><button class="primary-button" type="submit" ${busy ? 'disabled' : ''}>保存授权</button>${button('cancel-form', '取消')}</div></form></section>`;
    }

    function paint() {
      const names = new Map(catalog.projects.map(item => [item.id, item.name]));
      const rangeText = (values, projects = false) => values.includes('*') ? '全部（含未来新增）' : values.map(value => projects ? names.get(value) || `${value}（已失效）` : value).join('、') || '未授权';
      const stateText = {enabled:'已开启', disabled:'已关闭', uninitialized:'尚未初始化'}[status.runtime_state] || '异常';
      root.innerHTML = `<div class="settings-stack agent-settings"><section class="settings-card"><div class="agent-section-head"><div><h2>AI Agent 接入</h2><p>当前状态：<strong id="agentRuntimeState">${stateText}</strong></p></div>${button('refresh', '刷新')}</div><dl class="agent-status"><dt>工作空间</dt><dd>${esc(status.workspace_id || '开启接入后初始化')}</dd><dt>服务地址</dt><dd>${esc(status.origin)}</dd><dt>运行设置来源</dt><dd>${esc({cli:'启动参数（本次覆盖）', preference:'本机启动偏好', ui:'本次界面设置'}[status.effective_source] || status.effective_source)}</dd></dl><div class="settings-actions">${button('toggle', status.enabled ? '关闭接入' : '开启接入')}<label><input id="agentStartupPreference" type="checkbox" ${status.startup_preference ? 'checked' : ''}>下次普通启动时开启</label>${button('preference', '保存启动偏好')}</div><p class="settings-hint">关闭接入保留授权与提案。显式启动参数只影响本次，保存的偏好用于下次普通启动。</p>${status.preference_error ? `<p class="agent-error">${esc(status.preference_error)}</p>` : ''}</section><p id="agentFeedback" class="agent-feedback" role="status" aria-live="polite"></p>${pending ? `<section class="settings-card"><p>上次操作结果尚未确定，请先查询，避免重复创建授权。</p>${button('resolve', '查询上次操作')}</section>` : ''}<section class="settings-card"><div class="agent-section-head"><h2>客户端授权</h2>${button('new', '添加客户端', !status.workspace_id ? 'disabled' : '')}</div><p class="settings-hint">授权只作用于当前工作空间；令牌保存在本机私人目录，页面不显示。</p><div class="agent-client-list">${catalog.items.map(client => `<article class="agent-client"><div><strong>${esc(client.name)}</strong><span class="agent-client-state">${client.recovery_required ? '需要恢复' : client.enabled ? '授权有效' : '已撤销'}</span><small>${esc(client.client_id)}</small><p>权限：${esc(permissionName(client.scopes))}</p><p>类型：${esc((client.kinds || ['issue', 'document']).map(kind => kindNames[kind]).join('、'))}</p><p>项目：${esc(rangeText(client.project_ids, true))}</p><p>知识库：${esc(rangeText(client.categories))}</p><p>最近客户端请求：${esc(client.last_client_request_at ? new Date(client.last_client_request_at).toLocaleString() : "暂无记录")}（来源未独立验证）</p><p>最近自检请求：${esc(client.last_diagnostic_request_at ? new Date(client.last_diagnostic_request_at).toLocaleString() : "暂无记录")}</p>${client.invalid_categories.length || client.invalid_project_ids.length ? '<p class="agent-error">部分授权范围已失效，请编辑后重新核对。</p>' : ''}</div><div class="settings-actions">${client.enabled && !client.recovery_required ? `${button('edit', '编辑', `data-client-id="${esc(client.client_id)}"`)}${button('setup', '接入向导', `data-client-id="${esc(client.client_id)}"`)}${button('diagnose', '检查连接', `data-client-id="${esc(client.client_id)}"`)}${button('rotate', '轮换凭据', `data-client-id="${esc(client.client_id)}"`)}${button('repair', '更新服务地址', `data-client-id="${esc(client.client_id)}"`)}${button('revoke', '撤销', `data-client-id="${esc(client.client_id)}"`)}` : ''}</div></article>`).join('') || '<p class="empty-state">暂无客户端。先开启接入，再添加并选择授权范围。</p>'}</div></section>${formHtml()}<div id="agentSetupPanel"></div><div id="agentDiagnosticsPanel"></div></div>`;
      if (setup) paintSetup();
      if (diagnostic) paintDiagnostic();
      if (registrationPending) {
        const panel = global.document.createElement('section');
        panel.className = 'settings-card';
        panel.innerHTML = `<p>Codex 接入结果待查询；请求编号：${esc(registrationPending.request_id)}</p>${button('registration-resolve', '查询上次接入结果')}`;
        root.prepend(panel);
      }
      if (busy) root.querySelectorAll('input, select, textarea, button').forEach(node => { node.disabled = true; });
    }

    async function load({preserveDraft = false} = {}) {
      const version = ++epoch;
      busy = true;
      if (!status || !find('.agent-settings')) root.innerHTML = '<div class="empty-state">正在加载接入设置…</div>';
      try {
        const loaded = await request('status');
        if (!valid(version)) return false;
        if (status && status.workspace_id !== loaded.workspace_id) {
          draft = null; original = ''; setup = null; pending = null; diagnostic = null;
          registration = null; registrationResult = null; registrationPending = null;
          root.innerHTML = '<div class="empty-state">工作空间已变化，正在重新加载授权…</div>';
        }
        status = loaded;
        if (!registrationPending && status.workspace_id) {
          try { registrationPending = JSON.parse(global.sessionStorage.getItem(pendingKey()) || 'null'); } catch { registrationPending = null; }
        }
        const clients = await request('clients');
        if (!valid(version)) return false;
        catalog = clients;
        if (!preserveDraft) { draft = null; original = ''; }
        busy = false;
        paint();
        return true;
      } catch (error) {
        if (valid(version)) {
          busy = false;
          if (status && find('#agentFeedback')) message(errorText(error), true);
          else root.innerHTML = `<div class="settings-card"><p class="agent-error" role="alert">${esc(errorText(error))}</p>${button('refresh', '重新加载')}</div>`;
        }
        return false;
      } finally { if (version === epoch) busy = false; }
    }

    async function canReplaceForm() {
      return !isDirty() || confirm({title:'放弃尚未保存的授权？', message:'当前表单尚未保存，继续后将丢弃这些修改。', confirmText:'放弃修改'});
    }

    async function openForm(client = null) {
      if (!await canReplaceForm()) return;
      draft = {client_id:client?.client_id || '', expected_version:client?.version || '', name:client?.name || '', guide:'codex',
        permission:client ? client.scopes.length === 1 && client.scopes[0] === 'read' ? 'read' : client.scopes.length === 3 ? 'write' : 'legacy' : 'read',
        kinds:[...(client?.kinds || ['issue', 'document'])], project_ids:[...(client?.project_ids || [])], categories:[...(client?.categories || [])]};
      original = JSON.stringify(draft);
      setup = null;
      paint();
      find('#agentClientName')?.focus();
    }

    async function perform(route, method, payload) {
      if (pending) { message('请先查询上次操作结果。', true); return null; }
      const version = epoch;
      let failure = '';
      busy = true;
      pending = {route, method, payload:{...payload, request_id:id()}};
      paint();
      try {
        const result = await request(route, {method, body:JSON.stringify(pending.payload)});
        if (!valid(version)) return null;
        pending = null;
        return result;
      } catch (error) {
        if (valid(version)) {
          if (error.status && error.status < 500) pending = null;
          failure = `${errorText(error)}${pending ? '；请查询上次操作结果。' : '；输入已保留。'}`;
        }
        return null;
      } finally {
        if (valid(version)) {
          busy = false;
          paint();
          if (failure) message(failure, true);
        }
      }
    }

    async function saveClient() {
      if (!draft || busy) return false;
      if (!draft.name.trim() || draft.permission === 'legacy' || !draft.kinds.length || !(draft.project_ids.length || draft.categories.length)) { message('请填写名称、选择权限并至少授权一个项目或知识库分类。', true); return false; }
      if (!await confirm({title:'保存当前授权？', message:`${draft.name.trim()}：${draft.permission === 'write' ? '整理并确认入库' : '只读查询'}`, detail:`类型：${draft.kinds.map(kind => kindNames[kind]).join('、')}；项目：${draft.project_ids.join('、') || '未授权'}；分类：${draft.categories.join('、') || '未授权'}。范围变更会对后续请求和提交生效。`, confirmText:'保存授权'})) return false;
      const guide = draft.guide;
      const result = await perform(draft.client_id ? `clients/${draft.client_id}` : 'clients', draft.client_id ? 'PATCH' : 'POST', {
        workspace_id:status.workspace_id, ...(draft.client_id ? {expected_version:draft.expected_version} : {}), name:draft.name.trim(),
        kinds:draft.kinds, scopes:draft.permission === 'write' ? ['read', 'propose', 'commit'] : ['read'], project_ids:draft.project_ids, categories:draft.categories,
      });
      if (!result) return false;
      await load();
      notify('授权已保存', '客户端配置已保存到本机私人目录');
      await showSetup(result.client_id, guide);
      return true;
    }

    function paintSetup() {
      const node = find('#agentSetupPanel');
      if (!node) return;
      const terminal = setup.terminal || setup.default_terminal || 'powershell';
      const terminalName = terminal === 'cmd' ? 'CMD（命令提示符）' : 'PowerShell';
      const command = terminal === 'cmd' ? setup.cmd_command : setup.powershell_command;
      node.innerHTML = `<section class="settings-card agent-setup"><h2>接入向导</h2><p>Python ${esc(setup.python_version)} · 桥接脚本${setup.bridge_exists ? '已找到' : '未找到'} · Codex CLI ${setup.codex_executable ? '已找到' : '未在服务环境中找到'}</p>${!setup.origin_matches ? '<p class="agent-error">配置中的服务地址已过期，请先在该客户端点击“更新服务地址”。</p>' : ''}<label>接入方式<select id="agentSetupType"><option value="codex" ${setup.guide !== 'generic' ? 'selected' : ''}>Codex</option><option value="generic" ${setup.guide === 'generic' ? 'selected' : ''}>通用 MCP</option></select></label><label>MCP 登记名称<input id="agentRegistrationName" maxlength="64" value="${esc(setup.registrationName || setup.default_name)}"></label>${registrationHtml()}<details data-agent-manual ${setup.manualOpen || setup.guide === 'generic' ? 'open' : ''}><summary>高级：手工接入（CMD / PowerShell）</summary><div class="agent-setup"><label>执行终端<select id="agentTerminal"><option value="cmd" ${terminal === 'cmd' ? 'selected' : ''}>CMD（命令提示符）</option><option value="powershell" ${terminal === 'powershell' ? 'selected' : ''}>PowerShell</option></select></label><p class="settings-hint">C:\\Users\\…&gt; 通常是 CMD；PS C:\\Users\\…&gt; 是 PowerShell。请与实际终端一致。</p>${!setup.codex_executable ? '<p class="agent-error">未找到 Codex：请安装或从能找到 Codex 的环境重新启动工作台，再打开向导。当前命令仍依赖终端 PATH。</p>' : `<p class="settings-hint">Codex 程序：${esc(setup.codex_executable)}（使用绝对路径，无需修改 PATH）</p>`}<p class="settings-hint">先检查同名登记，避免覆盖另一工作空间；名称可改为 workbench_personal 等。</p>${button('generate', '生成命令')}<label>${terminalName} 登记命令<textarea id="agentSetupCommand" rows="5" readonly spellcheck="false">${esc(command || '')}</textarea></label>${terminal === 'cmd' && setup.cmd_error ? `<p class="agent-error">${esc(setup.cmd_error)}</p>` : ''}${button('copy', '复制命令', !command ? 'disabled' : '')}<details ${setup.guide === 'generic' ? 'open' : ''}><summary>通用 MCP 程序与参数</summary><pre>${esc(JSON.stringify({command:setup.command, args:setup.args}, null, 2))}</pre></details><ol><li>在 ${terminalName} 中执行上方命令，不要复制终端提示符。</li><li>重启 Codex 或开启新聊天。</li><li>要求调用工作台 capabilities、项目和分类，先做只读验证。</li></ol><p class="settings-hint">仅生成或复制命令不会修改 Codex 配置。</p></div></details></section>`;
    }

    function registrationHtml() {
      const result = registrationResult;
      const preview = registration;
      const stateNames = {absent:'将新增登记', identical:'已经是相同登记，无需重复写入', conflict:'同名登记不同，请改名或明确选择替换'};
      const resultNames = {completed:'配置已登记', not_applied:'确认未写入，可重新检查后接入', recovery_required:'配置有外部变更，请核查备份与维护说明'};
      return `<div class="agent-setup"><p>直接接入服务当前用户的 Codex，无需打开终端。</p>${button('registration-preview', '检查并接入本机 Codex', !setup.codex_executable || !setup.origin_matches || !status.enabled ? 'disabled' : '')}${preview ? `<div id="agentRegistrationPreview" class="agent-setup"><p><strong>${esc(stateNames[preview.state])}</strong></p><p>目标配置：${esc(preview.config_path)}</p><p>登记名称：${esc(preview.name)}</p>${preview.existing ? `<p>原登记（敏感值已隐藏）：${esc(preview.existing.transport)}，${preview.existing.argument_count} 个参数；字段：${esc(preview.existing.fields.join('、'))}。替换会移除原项中的其他设置。</p>` : ''}<label>完整新登记<pre>${esc(JSON.stringify(preview.desired, null, 2))}</pre></label>${preview.state === 'conflict' ? '<div class="settings-actions"><label><input id="agentReplaceRegistration" type="checkbox">替换同名登记（写入前保留原配置备份）</label></div>' : ''}${button('registration-confirm', preview.state === 'identical' ? '确认并检查连接' : '确认接入')}${button('registration-cancel', '取消')}</div>` : ''}${result ? `<div id="agentRegistrationResult" role="status"><strong>${esc(resultNames[result.state] || result.state)}</strong><p>${esc(result.config_path)}</p>${result.backup_path ? `<p>原配置备份：${esc(result.backup_path)}</p>` : ''}${result.registered && !result.configuration_unchanged ? '<p class="agent-error">登记后配置已有变化，请重新检查。</p>' : ''}<p>请求编号：${esc(result.request_id)}</p><p>配置登记与连接自检分别显示；当前 Codex 聊天可能仍需重启或开启新聊天才能加载工具。</p></div>` : ''}</div>`;
    }

    async function previewRegistration() {
      const version = epoch;
      const requestVersion = ++setupRequest;
      const name = find('#agentRegistrationName').value;
      const clientId = setup.client_id;
      busy = true;
      setup.registrationName = name;
      registration = null; registrationResult = null;
      paint();
      let failure = '';
      try {
        const value = await request(`clients/${clientId}/registration-preview`, {method:'POST', body:JSON.stringify({workspace_id:status.workspace_id, name})});
        if (valid(version) && requestVersion === setupRequest) registration = value;
      } catch (error) { if (valid(version)) failure = errorText(error); }
      finally { if (valid(version)) { busy = false; paint(); if (failure) message(failure, true); find('#agentRegistrationPreview')?.scrollIntoView({block:'nearest'}); } }
    }

    async function finishRegistration(result, version) {
      rememberRegistration(null);
      registrationResult = result;
      registration = null;
      busy = false;
      paint();
      if (!setup) message(result.registered ? '配置已登记；客户端可能已撤销，请重新核对授权。' : '已查到接入结果，请按维护说明核查私人回执。', !result.registered);
      if (result.registered && result.configuration_unchanged && valid(version)) await action('diagnose', result.client_id);
    }

    async function registerCodex() {
      if (!registration) return;
      if (find('#agentRegistrationName').value !== registration.name) { registration = null; paintSetup(); message('登记名称已变化，请重新检查。', true); return; }
      const replaceExisting = Boolean(find('#agentReplaceRegistration')?.checked);
      if (registration.state === 'conflict' && !replaceExisting) { message('请改名重新检查，或勾选替换同名登记。', true); return; }
      registrationConfirming = true;
      let approved;
      try { approved = await confirm({title:replaceExisting ? '替换同名 Codex 登记？' : '接入本机 Codex？', message:`${registration.name} → ${registration.config_path}`, detail:'将按当前预览写入本机配置并保留备份，然后自动执行只读连接检查。', confirmText:replaceExisting ? '替换并接入' : '接入并检查', danger:replaceExisting}); }
      finally { registrationConfirming = false; }
      if (!approved) return;
      const version = epoch;
      const clientId = registration.client_id;
      const payload = {workspace_id:status.workspace_id, name:registration.name, expected_version:registration.expected_version, replace_existing:replaceExisting, request_id:id()};
      rememberRegistration({request_id:payload.request_id, client_id:clientId});
      busy = true;
      paint();
      try {
        const value = await request(`clients/${clientId}/registration`, {method:'POST', body:JSON.stringify(payload)});
        if (valid(version)) await finishRegistration(value, version);
      } catch (error) {
        if (valid(version)) {
          // Even a 409 may follow a durable prepare. Always query this request first.
          busy = false;
          paint();
          message(`${errorText(error)}；请查询上次接入结果。`, true);
        }
      }
    }

    async function showSetup(clientId, guide = 'codex') {
      const version = epoch;
      const requestVersion = ++setupRequest;
      try {
        const value = await request(`clients/${clientId}/setup`);
        if (!valid(version) || requestVersion !== setupRequest) return;
        setup = {...value, guide};
        registration = null; registrationResult = null;
        paintSetup();
        find('#agentSetupPanel')?.scrollIntoView({block:'nearest'});
      } catch (error) { if (valid(version)) message(errorText(error), true); }
    }

    function paintDiagnostic() {
      const panel = find('#agentDiagnosticsPanel');
      if (!panel || !diagnostic) return;
      const labels = {service:'服务', authorization:'授权', configuration:'配置', python:'Python 与桥接', codex:'Codex 环境', mcp:'MCP 握手与工具', read:'只读请求'};
      const states = {passed:'通过', failed:'失败', skipped:'未执行', warning:'需核对'};
      panel.innerHTML = `<section class="settings-card agent-diagnostic"><h2>连接检查 · ${diagnostic.state === 'running' ? '检查中…' : '检查完成'}</h2><p class="settings-hint">本机自检不会写入业务内容；握手成功不表示当前 Codex 聊天已加载工具。</p><p>开始时间：${esc(new Date(diagnostic.started_at).toLocaleString())}</p><ol>${diagnostic.steps.map(step => `<li><strong>${esc(labels[step.name] || step.name)}：${esc(states[step.state] || step.state)}</strong><p>${esc(step.message)}</p><small>${esc(new Date(step.checked_at).toLocaleString())}</small></li>`).join('') || '<li>正在运行有超时限制的环境与桥接检查…</li>'}</ol><p id="agentDiagnosticPolling" role="status"></p></section>`;
    }

    async function pollDiagnostic(operationId, version, attempt = 0) {
      if (!valid(version)) return;
      try {
        const result = await request(`diagnostics/${operationId}`);
        if (!valid(version)) return;
        diagnostic = result;
        paintDiagnostic();
        if (result.state === 'running' && attempt < 60) pollTimer = global.setTimeout(() => pollDiagnostic(operationId, version, attempt + 1), 300);
        else if (result.state === 'running') find('#agentDiagnosticPolling').textContent = '检查仍在运行，请稍后再次点击检查连接查询。';
      } catch (error) {
        if (valid(version)) {
          const node = find('#agentDiagnosticPolling');
          if (node) node.textContent = `${errorText(error)}；可重新发起检查。`;
        }
      }
    }

    async function action(name, clientId) {
      if (busy || registrationConfirming) return;
      if (name === 'registration-resolve' && registrationPending) {
        const version = epoch;
        try {
          const result = await request(`registrations/${encodeURIComponent(registrationPending.request_id)}`);
          if (!valid(version)) return;
          if (!setup || setup.client_id !== result.client_id) await showSetup(result.client_id);
          if (valid(version)) await finishRegistration(result, version);
        } catch (error) {
          if (!valid(version)) return;
          if (error.status === 404) { rememberRegistration(null); registration = null; paint(); message('未找到已接受的接入操作，请重新检查配置后接入。'); }
          else message(errorText(error), true);
        }
        return;
      }
      if (registrationPending && name !== 'refresh') { message('请先查询上次接入结果。', true); return; }
      if (name === 'registration-preview') return previewRegistration();
      if (name === 'registration-confirm') return registerCodex();
      if (name === 'registration-cancel') { registration = null; paintSetup(); return; }
      const client = catalog.items.find(item => item.client_id === clientId);
      if (name === 'new') return openForm();
      if (name === 'edit') return openForm(client);
      if (name === 'cancel-form') { if (await canReplaceForm()) { draft = null; original = ''; paint(); } return; }
      if (name === 'refresh') { if (await canReplaceForm()) await load(); return; }
      if (name === 'setup') return showSetup(clientId);
      if (name === 'diagnose') {
        const version = epoch;
        global.clearTimeout(pollTimer);
        try {
          const result = await request('diagnostics', {method:'POST', body:JSON.stringify({workspace_id:status.workspace_id, client_id:clientId, request_id:id()})});
          if (!valid(version)) return;
          diagnostic = result;
          paintDiagnostic();
          find('#agentDiagnosticsPanel')?.scrollIntoView({block:'nearest'});
          await pollDiagnostic(result.operation_id, version);
        } catch (error) { if (valid(version)) message(errorText(error), true); }
        return;
      }
      if (name === 'copy') {
        try { await global.navigator.clipboard.writeText(find('#agentSetupCommand').value); message('命令已复制。'); }
        catch { find('#agentSetupCommand')?.select(); message('无法自动复制，已选中命令，请按 Ctrl+C。', true); }
        return;
      }
      if (name === 'generate') {
        const version = epoch;
        const requestVersion = ++setupRequest;
        const registrationName = find('#agentRegistrationName').value;
        const guide = find('#agentSetupType').value;
        const terminal = find('#agentTerminal').value;
        const manualOpen = find('[data-agent-manual]').open;
        try {
          const value = await request(`clients/${setup.client_id}/setup`, {method:'POST', body:JSON.stringify({workspace_id:status.workspace_id, name:registrationName, terminal})});
          if (valid(version) && requestVersion === setupRequest) { setup = {...value, registrationName, guide, terminal, manualOpen}; paintSetup(); message('命令已生成，请核对登记名称。'); }
        } catch (error) { if (valid(version) && requestVersion === setupRequest) message(errorText(error), true); }
        return;
      }
      if (name === 'resolve') {
        if (!pending) return;
        try {
          const result = await request(`operations/${encodeURIComponent(pending.payload.request_id)}`);
          if (result.state && result.state !== 'completed') { message('上次操作需要恢复，请按维护说明检查管理日志。', true); return; }
          const created = pending.route === 'clients' && pending.method === 'POST';
          const clientId = result.result?.client_id;
          pending = null;
          await load({preserveDraft:!created});
          if (created && clientId) await showSetup(clientId);
          message('已查到上次操作结果，请核对列表；编辑表单请重新读取客户端后再保存。');
        } catch (error) {
          if (error.status === 404) { pending = null; message('未找到已接受的操作，可重新核对后提交。'); }
          else message(errorText(error), true);
        }
        return;
      }
      if (pending) { message('请先查询上次操作结果。', true); return; }
      if (name === 'toggle' || name === 'preference') {
        const preferred = find('#agentStartupPreference').checked;
        if (name === 'toggle' && !await confirm({title:status.enabled ? '关闭 Agent 接入？' : '开启 Agent 接入？', message:status.enabled ? '新 Agent 请求将停止，授权与提案保留，已接受提交不会撤销。' : '允许已授权的本机客户端访问当前工作空间。', confirmText:status.enabled ? '关闭接入' : '开启接入'})) return;
        const result = await perform('runtime', 'PATCH', {workspace_id:status.workspace_id, expected_version:status.version, ...(name === 'toggle' ? {enabled:!status.enabled} : {startup_preference:preferred})});
        if (result) { await load({preserveDraft:true}); message(result.preference_error || '设置已更新。', Boolean(result.preference_error)); }
        return;
      }
      if (['rotate', 'revoke', 'repair'].includes(name) && client) {
        const titles = {rotate:'轮换客户端凭据？', revoke:'撤销客户端授权？', repair:'更新客户端服务地址？'};
        const messages = {rotate:'旧令牌将失效。桥接每次重读配置，路径未变通常无需重新登记。', revoke:'客户端将失去访问权限；Codex 中的 MCP 登记不会自动移除。', repair:'将该客户端配置更新为当前工作台地址，保留令牌，不修改 Codex 登记。'};
        if (!await confirm({title:titles[name], message:messages[name], detail:client.name, confirmText:{rotate:'轮换凭据', revoke:'撤销授权', repair:'更新地址'}[name], danger:name === 'revoke'})) return;
        const result = await perform(`clients/${clientId}/${name}`, 'POST', {workspace_id:status.workspace_id, expected_version:client.version});
        if (result) { setup = null; await load({preserveDraft:true}); message('客户端设置已更新。'); }
      }
    }

    root.addEventListener('click', event => {
      if (!isActive()) return;
      const trigger = event.target.closest('[data-agent-action]');
      if (trigger) { event.preventDefault(); action(trigger.dataset.agentAction, trigger.dataset.clientId).catch(error => message(errorText(error), true)); }
    });
    root.addEventListener('submit', event => {
      if (isActive() && event.target.id === 'agentClientForm') { event.preventDefault(); saveClient().catch(error => message(errorText(error), true)); }
    });
    root.addEventListener('input', event => {
      if (!isActive() || busy) return;
      if (event.target.id === 'agentRegistrationName' && setup) {
        setup.registrationName = event.target.value;
        registration = null;
        find('#agentRegistrationPreview')?.remove();
      }
      if (!draft) return;
      if (event.target.id === 'agentClientName') draft.name = event.target.value;
    });
    root.addEventListener('toggle', event => {
      if (setup && event.target.hasAttribute?.('data-agent-manual')) setup.manualOpen = event.target.open;
    }, true);
    root.addEventListener('change', event => {
      if (!isActive() || busy) return;
      const node = event.target;
      if (node.id === 'agentSetupType' && setup) {
        setup.guide = node.value;
        paintSetup();
        return;
      }
      if (node.id === 'agentTerminal' && setup) {
        setup.registrationName = find('#agentRegistrationName').value;
        setup.guide = find('#agentSetupType').value;
        setup.terminal = node.value;
        paintSetup();
        action('generate').catch(error => message(errorText(error), true));
        return;
      }
      if (!draft) return;
      if (node.id === 'agentClientPermission') draft.permission = node.value;
      if (node.id === 'agentGuideType') draft.guide = node.value;
      if (node.dataset.agentKind) draft.kinds = [...root.querySelectorAll('[data-agent-kind]:checked')].map(input => input.dataset.agentKind);
      if (node.dataset.agentAll) { draft[node.dataset.agentAll] = node.checked ? ['*'] : []; paint(); }
      if (node.dataset.agentScope) draft[node.dataset.agentScope] = [...root.querySelectorAll(`[data-agent-scope="${node.dataset.agentScope}"]:checked`)].map(input => input.value);
    });
    return {load, isDirty, isBusy, saveClient, deactivate:() => { epoch += 1; busy = false; global.clearTimeout(pollTimer); }, discard:() => { draft = null; original = ''; }};
  }

  global.Workbench = global.Workbench || {};
  global.Workbench.agentSettings = {create};
})(typeof window !== 'undefined' ? window : globalThis);
