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
    let diagnostic = null;
    let pollTimer = null;
    const find = selector => root.querySelector(selector);
    const id = () => global.crypto.randomUUID();
    const errorText = error => error.payload?.message || error.message;
    const permissionName = scopes => scopes.length === 1 && scopes[0] === 'read' ? '只读查询' : scopes.length === 3 ? '整理并确认入库' : `旧版权限：${scopes.join(' / ')}`;
    const isDirty = () => Boolean(draft && JSON.stringify(draft) !== original);
    const isBusy = () => busy || Boolean(pending);
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

    function formHtml() {
      if (!draft) return '';
      return `<section class="settings-card agent-client-form" aria-label="客户端授权表单"><h2>${draft.client_id ? '编辑授权' : '创建客户端'}</h2><form id="agentClientForm"><label>客户端名称<input id="agentClientName" required maxlength="100" value="${esc(draft.name)}"></label><label>接入指引<select id="agentGuideType"><option value="codex" ${draft.guide === 'codex' ? 'selected' : ''}>Codex</option><option value="generic" ${draft.guide === 'generic' ? 'selected' : ''}>通用 MCP</option></select></label><label>操作权限<select id="agentClientPermission"><option value="read" ${draft.permission === 'read' ? 'selected' : ''}>只读查询</option><option value="write" ${draft.permission === 'write' ? 'selected' : ''}>整理并确认入库</option>${draft.permission === 'legacy' ? '<option value="legacy" selected>旧版权限组合（请选择新的权限）</option>' : ''}</select></label><p class="settings-hint">允许写入仍需完整预览并确认当前版本，不会执行正文中的命令。</p>${scopeField('project_ids', '项目范围', catalog.projects.map(item => ({value:item.id, label:item.name})))}${scopeField('categories', '知识库分类', catalog.categories.map(value => ({value, label:value})))}<div class="settings-actions"><button class="primary-button" type="submit" ${busy ? 'disabled' : ''}>保存授权</button>${button('cancel-form', '取消')}</div></form></section>`;
    }

    function paint() {
      const names = new Map(catalog.projects.map(item => [item.id, item.name]));
      const rangeText = (values, projects = false) => values.includes('*') ? '全部（含未来新增）' : values.map(value => projects ? names.get(value) || `${value}（已失效）` : value).join('、') || '未授权';
      const stateText = {enabled:'已开启', disabled:'已关闭', uninitialized:'尚未初始化'}[status.runtime_state] || '异常';
      root.innerHTML = `<div class="settings-stack agent-settings"><section class="settings-card"><div class="agent-section-head"><div><h2>AI Agent 接入</h2><p>当前状态：<strong id="agentRuntimeState">${stateText}</strong></p></div>${button('refresh', '刷新')}</div><dl class="agent-status"><dt>工作空间</dt><dd>${esc(status.workspace_id || '开启接入后初始化')}</dd><dt>服务地址</dt><dd>${esc(status.origin)}</dd><dt>运行设置来源</dt><dd>${esc({cli:'启动参数（本次覆盖）', preference:'本机启动偏好', ui:'本次界面设置'}[status.effective_source] || status.effective_source)}</dd></dl><div class="settings-actions">${button('toggle', status.enabled ? '关闭接入' : '开启接入')}<label><input id="agentStartupPreference" type="checkbox" ${status.startup_preference ? 'checked' : ''}>下次普通启动时开启</label>${button('preference', '保存启动偏好')}</div><p class="settings-hint">关闭接入保留授权与提案。显式启动参数只影响本次，保存的偏好用于下次普通启动。</p>${status.preference_error ? `<p class="agent-error">${esc(status.preference_error)}</p>` : ''}</section><p id="agentFeedback" class="agent-feedback" role="status" aria-live="polite"></p>${pending ? `<section class="settings-card"><p>上次操作结果尚未确定，请先查询，避免重复创建授权。</p>${button('resolve', '查询上次操作')}</section>` : ''}<section class="settings-card"><div class="agent-section-head"><h2>客户端授权</h2>${button('new', '添加客户端', !status.workspace_id ? 'disabled' : '')}</div><p class="settings-hint">授权只作用于当前工作空间；令牌保存在本机私人目录，页面不显示。</p><div class="agent-client-list">${catalog.items.map(client => `<article class="agent-client"><div><strong>${esc(client.name)}</strong><span class="agent-client-state">${client.recovery_required ? '需要恢复' : client.enabled ? '授权有效' : '已撤销'}</span><small>${esc(client.client_id)}</small><p>权限：${esc(permissionName(client.scopes))}</p><p>项目：${esc(rangeText(client.project_ids, true))}</p><p>知识库：${esc(rangeText(client.categories))}</p><p>最近客户端请求：${esc(client.last_client_request_at ? new Date(client.last_client_request_at).toLocaleString() : "暂无记录")}（来源未独立验证）</p><p>最近自检请求：${esc(client.last_diagnostic_request_at ? new Date(client.last_diagnostic_request_at).toLocaleString() : "暂无记录")}</p>${client.invalid_categories.length || client.invalid_project_ids.length ? '<p class="agent-error">部分授权范围已失效，请编辑后重新核对。</p>' : ''}</div><div class="settings-actions">${client.enabled && !client.recovery_required ? `${button('edit', '编辑', `data-client-id="${esc(client.client_id)}"`)}${button('setup', '接入向导', `data-client-id="${esc(client.client_id)}"`)}${button('diagnose', '检查连接', `data-client-id="${esc(client.client_id)}"`)}${button('rotate', '轮换凭据', `data-client-id="${esc(client.client_id)}"`)}${button('repair', '更新服务地址', `data-client-id="${esc(client.client_id)}"`)}${button('revoke', '撤销', `data-client-id="${esc(client.client_id)}"`)}` : ''}</div></article>`).join('') || '<p class="empty-state">暂无客户端。先开启接入，再添加并选择授权范围。</p>'}</div></section>${formHtml()}<div id="agentSetupPanel"></div><div id="agentDiagnosticsPanel"></div></div>`;
      if (setup) paintSetup();
      if (diagnostic) paintDiagnostic();
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
          root.innerHTML = '<div class="empty-state">工作空间已变化，正在重新加载授权…</div>';
        }
        status = loaded;
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
        project_ids:[...(client?.project_ids || [])], categories:[...(client?.categories || [])]};
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
      if (!draft.name.trim() || draft.permission === 'legacy' || !(draft.project_ids.length || draft.categories.length)) { message('请填写名称、选择权限并至少授权一个项目或知识库分类。', true); return false; }
      if (!await confirm({title:'保存当前授权？', message:`${draft.name.trim()}：${draft.permission === 'write' ? '整理并确认入库' : '只读查询'}`, detail:`项目：${draft.project_ids.join('、') || '未授权'}；分类：${draft.categories.join('、') || '未授权'}。范围变更会对后续请求和提交生效。`, confirmText:'保存授权'})) return false;
      const guide = draft.guide;
      const result = await perform(draft.client_id ? `clients/${draft.client_id}` : 'clients', draft.client_id ? 'PATCH' : 'POST', {
        workspace_id:status.workspace_id, ...(draft.client_id ? {expected_version:draft.expected_version} : {}), name:draft.name.trim(),
        scopes:draft.permission === 'write' ? ['read', 'propose', 'commit'] : ['read'], project_ids:draft.project_ids, categories:draft.categories,
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
      node.innerHTML = `<section class="settings-card agent-setup"><h2>接入向导</h2><p>Python ${esc(setup.python_version)} · 桥接脚本${setup.bridge_exists ? '已找到' : '未找到'} · Codex CLI ${setup.codex_executable ? '已找到' : '未在服务环境中找到'}</p>${!setup.origin_matches ? '<p class="agent-error">配置中的服务地址已过期，请先在该客户端点击“更新服务地址”。</p>' : ''}<label>接入方式<select id="agentSetupType"><option value="codex" ${setup.guide !== 'generic' ? 'selected' : ''}>Codex</option><option value="generic" ${setup.guide === 'generic' ? 'selected' : ''}>通用 MCP</option></select></label><label>MCP 登记名称<input id="agentRegistrationName" maxlength="64" value="${esc(setup.registrationName || setup.default_name)}"></label><p class="settings-hint">先检查同名登记，避免覆盖另一工作空间；名称可改为 workbench_personal 等。</p>${button('generate', '生成命令')}<label>PowerShell 登记命令<textarea id="agentSetupCommand" rows="5" readonly spellcheck="false">${esc(setup.powershell_command)}</textarea></label>${button('copy', '复制命令')}<details ${setup.guide === 'generic' ? 'open' : ''}><summary>通用 MCP 程序与参数</summary><pre>${esc(JSON.stringify({command:setup.command, args:setup.args}, null, 2))}</pre></details><ol><li>在 PowerShell 执行登记命令。</li><li>重启 Codex 或开启新聊天。</li><li>要求调用工作台 capabilities、项目和分类，先做只读验证。</li></ol><p class="settings-hint">配置命令已生成不代表当前聊天已接入；本页不会修改 Codex 配置。</p></section>`;
    }

    async function showSetup(clientId, guide = 'codex') {
      const version = epoch;
      try {
        const value = await request(`clients/${clientId}/setup`);
        if (!valid(version)) return;
        setup = {...value, guide};
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
      if (busy) return;
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
        const registrationName = find('#agentRegistrationName').value;
        const guide = find('#agentSetupType').value;
        try {
          const value = await request(`clients/${setup.client_id}/setup`, {method:'POST', body:JSON.stringify({workspace_id:status.workspace_id, name:registrationName})});
          if (valid(version)) { setup = {...value, registrationName, guide}; paintSetup(); message('命令已生成，请核对登记名称。'); }
        } catch (error) { if (valid(version)) message(errorText(error), true); }
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
      if (!isActive() || !draft || busy) return;
      if (event.target.id === 'agentClientName') draft.name = event.target.value;
    });
    root.addEventListener('change', event => {
      if (!isActive() || !draft || busy) return;
      const node = event.target;
      if (node.id === 'agentClientPermission') draft.permission = node.value;
      if (node.id === 'agentGuideType') draft.guide = node.value;
      if (node.dataset.agentAll) { draft[node.dataset.agentAll] = node.checked ? ['*'] : []; paint(); }
      if (node.dataset.agentScope) draft[node.dataset.agentScope] = [...root.querySelectorAll(`[data-agent-scope="${node.dataset.agentScope}"]:checked`)].map(input => input.value);
    });
    return {load, isDirty, isBusy, saveClient, deactivate:() => { epoch += 1; busy = false; global.clearTimeout(pollTimer); }, discard:() => { draft = null; original = ''; }};
  }

  global.Workbench = global.Workbench || {};
  global.Workbench.agentSettings = {create};
})(typeof window !== 'undefined' ? window : globalThis);
