(function initializeAgentProposals(global) {
  'use strict';

  function create({root, api, escapeHtml:esc, confirm, notify, renderMarkdown, isActive, openItemLink}) {
    let status = null;
    let listing = {items:[], clients:[], next_cursor:null};
    let filters = {client_id:'', kind:'', state:'', operation:''};
    let cursors = ['0'];
    let detail = null;
    let busy = false;
    let pending = null;
    let confirming = false;
    let epoch = 0;
    let previewId = null;
    let returnId = null;
    let listScroll = 0;
    let feedback = '';
    let feedbackError = false;
    let savedOverflow = null;
    let savedRootStyle = null;
    let graphView = null;
    let graphReady = null;
    let deletionReady = null;
    let projectReady = null;
    let categoryReady = null;
    let projectAccess = null;
    let deletionViews = [];
    const graphKey = value => value?.preview ? `${value.proposal_id}:${value.version}:${value.preview.preview_digest}` : null;
    function disposeGraph() { graphView?.dispose(); graphView = null; graphReady = null; deletionViews.forEach(view => view.dispose()); deletionViews = []; deletionReady = null; projectReady = null; categoryReady = null; }
    function approvalEnabled() {
      return !busy && !pending && detail?.preview_ticket && detail.authorization_available && !detail.content_cleaned && detail.confirmation_mode === 'local_web' && (detail.kind === 'category' ? categoryReady === graphKey(detail) : detail.operation === 'delete' ? deletionReady === graphKey(detail) : detail.kind === 'project' ? projectReady === graphKey(detail) : detail.kind !== 'concept_map' || graphReady === graphKey(detail));
    }
    const dialog = () => root.querySelector('#proposalPreviewDialog');
    function closePreview({force = false} = {}) {
      if ((!force && confirming) || !dialog() || (!dialog().open && !previewId)) return;
      epoch += 1;
      busy = false;
      detail = null; projectAccess = null;
      disposeGraph();
      previewId = null;
      dialog().close();
      dialog().innerHTML = '';
      if (savedOverflow !== null) { global.document.body.style.overflow = savedOverflow; savedOverflow = null; }
      if (savedRootStyle) {
        Object.assign(global.document.documentElement.style, savedRootStyle);
        savedRootStyle = null;
      }
      paint();
      const trigger = [...root.querySelectorAll('.agent-client [data-proposal-action="review"]')].find(node => node.dataset.proposalId === returnId);
      trigger?.focus({preventScroll:true});
      global.scrollTo({top:listScroll, behavior:'instant'});
    }
    const states = {draft:'草案', previewed:'已预览', committing:'提交恢复中', committed:'已入库', conflicted:'有冲突', cancelled:'已取消', expired:'已过期', recovery_required:'需要恢复'};
    const kinds = {issue:'问题', todo:'待办', info:'信息', document:'知识文档', attachment:'附件', concept_map:'概念图', project:'项目', category:'分类'};
    const operations = {create:'新建', append:'追加', update:'更新', delete:'移入回收站', rename:'重命名', reorder:'调整顺序'};
    const key = () => `workbench.proposalAction.pending.${status?.workspace_id}`;
    const current = version => version === epoch && isActive();
    function remember(value) {
      pending = value;
      try { if (value) global.sessionStorage.setItem(key(), JSON.stringify(value)); else global.sessionStorage.removeItem(key()); } catch { /* Query remains available in this page. */ }
    }
    async function request(route, options = {}) {
      return api(`/local/agent-management/${route}`, {...options, headers:{'X-Workbench-Management':'1', ...(status?.management_token ? {'X-Workbench-Management-Token':status.management_token} : {})}, signal:AbortSignal.timeout(15000)});
    }
    function message(text, error = false) {
      feedback = text;
      feedbackError = error;
      for (const node of root.querySelectorAll('[data-proposal-feedback]')) {
        node.textContent = text;
        node.classList.toggle('agent-error', error);
      }
    }
    const button = (action, label, extra = '') => `<button type="button" class="secondary-button" data-proposal-action="${action}" ${busy ? 'disabled' : ''} ${extra}>${label}</button>`;
    function filter(key, label, items) {
      return `<label>${label}<select data-proposal-filter="${key}" ${busy ? 'disabled' : ''}><option value="">全部</option>${Object.entries(items).map(([value, name]) => `<option value="${esc(value)}" ${filters[key] === value ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select></label>`;
    }
    function detailHtml() {
      if (!detail) return `<p class="empty-state">${busy ? '正在加载完整预览…' : '完整预览未加载，请重新读取。'}</p>`;
      const preview = detail.preview;
      if (detail.kind === 'category') {
        if (!preview || !detail.local_category_plan) return '<p>完整分类预览尚未载入或已清理。</p>';
        return `<section class="agent-proposal-detail"><h3>完整分类与成员影响</h3><pre class="agent-proposal-full-text" data-category-impact>${esc(JSON.stringify(preview.content, null, 2))}</pre><h3>配置、排序与脱敏授权迁移</h3><pre class="agent-proposal-full-text" data-category-local-plan>${esc(JSON.stringify(detail.local_category_plan, null, 2))}</pre><p>预览摘要：${esc(preview.preview_digest)}</p></section>`;
      }
      if (detail.operation === 'delete') return deletionDetailHtml();
      if (detail.kind === 'concept_map') return graphDetailHtml();
      if (detail.kind === 'project') return projectDetailHtml();
      const content = preview?.content;
      const labels = {title:'标题', project_id:'所属项目', category:'分类', status:'状态', priority:'优先级', tags:'标签', due:'到期日', completed:'已完成', owner_kind:'归属类型', owner_id:'归属ID', upload_id:'源暂存ID', display_name:'请求名称', attachment:'正式附件元数据', source:'来源证据', metadata_before:'原元数据', metadata_after:'拟保存元数据', insert_link:'插入正文链接', binary_relative:'最终相对文件', metadata_relative:'目标元数据文件', unparsed_binary:'未解析二进制内容'};
      const fieldValue = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
      return `<section class="agent-proposal-detail" aria-label="提案详情"><p>客户端：${esc(detail.client_name)}（${esc(detail.client_id)}）</p><p>提案：${esc(detail.proposal_id)} · 版本 ${detail.version} · ${esc(states[detail.state] || detail.state)}</p><p>归属：${esc(detail.access_target.project_id || detail.access_target.category || '—')} · ${esc(kinds[detail.kind] || detail.kind)} · ${esc(operations[detail.operation] || detail.operation)}</p><p>确认方式：${detail.confirmation_mode === 'local_web' ? '本机网页独立批准' : '对话内确认'}；当前写入授权：${detail.authorization_available ? '可用' : '不可用'}</p>${detail.recovery_in_progress ? '<p class="agent-error">原提交正在恢复或需要本机核查；查看详情不会发起新提交，请按维护说明处理。</p>' : ''}${detail.content_cleaned ? '<p>正文已按保留规则清理；不能批准残缺预览。</p>' : preview ? `<h3>警告</h3>${preview.warnings.length ? `<ul class="agent-error">${preview.warnings.map(text => `<li>${esc(text)}</li>`).join('')}</ul>` : '<p>无警告</p>'}<h3>字段内容</h3><dl class="agent-proposal-fields">${Object.entries(content).filter(([key]) => !['body', 'info_fields'].includes(key)).map(([key, value]) => `<dt>${esc(labels[key] || key)}</dt><dd><pre>${esc(fieldValue(value))}</pre></dd>`).join('')}</dl>${content.info_fields ? `<h3>有序信息字段</h3><ol>${content.info_fields.map(field => `<li><strong>${esc(field.name)}</strong><pre>${esc(field.value)}</pre>${field.note !== undefined ? `<p>说明</p><pre>${esc(field.note)}</pre>` : ''}</li>`).join('')}</ol>` : ''}<h3>完整正文</h3><div class="markdown-preview agent-proposal-markdown">${renderMarkdown(content.body || '', {type:detail.kind, project_id:detail.access_target.project_id})}</div><h3>字段差异</h3><pre>${esc(JSON.stringify(preview.changes, null, 2))}</pre><h3>正文差异</h3><pre>${esc(preview.body_diff || '无正文变化')}</pre>${preview.execution_plan ? `<h3>保存范围</h3><p>${detail.kind === 'attachment' ? '先持久接受计划，再校验并发布二进制、保留记录历史、写正文或项目索引、消费源暂存及保存回执。预览中的服务端时间占位在接受确认时生成。' : '先保留历史快照，再保存正文；新建条目不写旧内容快照。'}相关依赖或授权变化后须重新整理和确认。</p><details data-proposal-execution><summary>查看执行依据和版本</summary><pre>${esc(JSON.stringify({authorization_revision:preview.authorization_revision, dependencies:preview.dependencies, execution_plan:preview.execution_plan, plan_digest:preview.plan_digest}, null, 2))}</pre></details>` : ''}<h3>来源说明</h3><pre>${esc(preview.source_note || '未提供来源说明')}</pre><details><summary>查看全部原始字段（JSON）</summary><pre data-proposal-fields>${esc(JSON.stringify(content, null, 2))}</pre></details><p>摘要：${esc(preview.preview_digest)}</p>` : ''}<p>创建：${esc(detail.created_at)}；过期：${esc(detail.expires_at)}</p><p class="settings-hint">提案管理不编辑正文；需要修改时请回原客户端生成新版本。</p></section>`;
    }
    function projectDetailHtml() {
      const preview = detail.preview;
      const content = preview?.content;
      const order = detail.local_project_plan;
      const json = value => esc(JSON.stringify(value, null, 2));
      const showAccess = detail.receipt ? `<section><h3>项目访问授权（独立操作）</h3><p>项目已创建。访问授权可独立预览、批准或查询。</p>${button('project-access-preview', '预览追加此项目访问范围', pending ? 'disabled' : '')}${projectAccess?.proposal_id === detail.proposal_id ? `<p>${esc(projectAccess.disclosure)}</p><pre class="agent-proposal-full-text" data-project-access-full>${json(projectAccess)}</pre>${projectAccess.already_covered ? '<p>原客户端已覆盖该项目，无需新增授权。</p>' : button('project-access-approve', '独立批准此项目范围')}</section>` : '</section>'}` : '';
      if (!content || !order) return '<p>完整候选已清理或尚未加载，不能批准创建。</p>' + showAccess;
      return `<section class="agent-proposal-detail"><p>固定项目：${esc(content.project_id)} · 版本 ${detail.version}</p><p>客户端：${esc(detail.client_name)}</p><ul class="agent-error">${preview.warnings.map(value => `<li>${esc(value)}</li>`).join('')}</ul><h3>完整元数据、说明、模板和空目录</h3><pre class="agent-proposal-full-text" data-project-content>${json(content)}</pre><h3>完整 README 预览</h3><pre class="agent-proposal-full-text">${esc(content.readme)}</pre><h3>本机排序前后及原配置</h3><pre class="agent-proposal-full-text" data-project-order>${json(order)}</pre><h3>来源与完整执行依据</h3><pre class="agent-proposal-full-text">${json({source_note:preview.source_note, dependencies:preview.dependencies, authorization_revision:preview.authorization_revision, execution_plan:preview.execution_plan, plan_digest:preview.plan_digest, preview_digest:preview.preview_digest})}</pre>${!detail.receipt ? '<label><input type="checkbox" data-project-access-after> 创建成功后打开独立访问授权预览（仍须另行批准）</label>' : ''}</section>${showAccess}`;
    }
    function mountProjectPreview(modal) {
      if (detail?.kind !== 'project' || detail.operation !== 'create' || !detail.preview || !detail.local_project_plan) return;
      const {preview} = detail;
      if (preview.proposal_id !== detail.proposal_id || preview.version !== detail.version || preview.content?.project_id !== detail.target_id ||
          modal.querySelector('[data-project-content]')?.textContent !== JSON.stringify(preview.content, null, 2) ||
          modal.querySelector('[data-project-order]')?.textContent !== JSON.stringify(detail.local_project_plan, null, 2)) return;
      projectReady = graphKey(detail);
      const approve = modal.querySelector('[data-proposal-action="approve"]');
      if (approve) approve.disabled = !approvalEnabled();
    }
    function graphDetailHtml() {
      const preview = detail.preview;
      if (!preview || detail.content_cleaned) return '<p>完整图内容已清理或尚未加载，不能批准。</p>';
      const labels = {id:'稳定ID', version:'图格式版本', title:'图标题', project_id:'所属项目', category:'分类', focus_question:'焦点问题', theme:'主题', viewport:'保存的视口', created:'创建时间', updated:'修改时间', type:'类型', text:'完整文字', note:'完整说明', x:'横坐标', y:'纵坐标', width:'宽度', height:'高度', color:'背景或关系颜色', border_color:'边框颜色', text_color:'文字颜色', font_size:'字体大小', font_weight:'字体粗细', shape:'形状', from:'起点ID', to:'终点ID', label:'完整关系文字', dashed:'虚线', arrowhead:'箭头方向'};
      const value = item => esc(typeof item === 'string' ? item : JSON.stringify(item, null, 2));
      const fields = object => `<dl class="agent-proposal-fields">${Object.entries(object).map(([key, item]) => `<dt>${esc(labels[key] || key)}</dt><dd><pre>${value(item)}</pre></dd>`).join('')}</dl>`;
      const graph = preview.prepared_graph;
      return `<section class="agent-proposal-detail"><p>客户端：${esc(detail.client_name)}（${esc(detail.client_id)}）</p><p>提案：${esc(detail.proposal_id)} · 版本 ${detail.version} · ${esc(states[detail.state])}</p><p>图ID：${esc(detail.target_id)} · ${esc(operations[detail.operation])} · 确认方式：${detail.confirmation_mode === 'local_web' ? '本机网页独立批准' : '对话内确认'} · 当前写入授权：${detail.authorization_available ? '可用' : '不可用'}</p><h3>警告</h3><ul class="agent-error">${preview.warnings.map(text => `<li>${esc(text)}</li>`).join('')}</ul><h3>完整拟保存图</h3><p>拖动平移、滚轮缩放；下方列出每个节点和关系的全部字段。画布操作只用于查看。</p><div data-proposal-graph-canvas></div><p data-proposal-graph-state role="status">正在载入完整画布和明细，完成前不能批准。</p><h3>图信息和视口</h3>${fields(Object.fromEntries(Object.entries(graph).filter(([key]) => !['nodes', 'edges'].includes(key))))}<h3>全部节点（${graph.nodes.length}）</h3><ol>${graph.nodes.map(node => `<li data-graph-node-details="${esc(node.id)}">${fields(node)}</li>`).join('') || '<li>无节点。</li>'}</ol><h3>全部关系（${graph.edges.length}）</h3><ol>${graph.edges.map(edge => `<li data-graph-edge-details="${esc(edge.id)}">${fields(edge)}</li>`).join('') || '<li>无关系。</li>'}</ol><h3>完整原图</h3><pre data-graph-base>${value(preview.base_graph)}</pre><h3>按稳定ID比较的全部差异及顺序</h3><pre data-graph-diff>${value(preview.graph_diff)}</pre><h3>来源说明</h3><pre>${esc(preview.source_note || '未提供来源说明')}</pre><p>原始字节版本：${esc(preview.base_revision || '新建')}；预览摘要：${esc(preview.preview_digest)}</p><details><summary>查看完整保存依据</summary><pre>${value({identity:preview.identity, authorization_revision:preview.authorization_revision, dependencies:preview.dependencies, execution_plan:preview.execution_plan, plan_digest:preview.plan_digest})}</pre></details><p>过期：${esc(detail.expires_at)}。修改后需重新完整预览并确认当前版本。</p></section>`;
    }

    function deletionSources() {
      const content = detail?.preview?.content;
      return content ? [content.target, ...(content.children || []), ...content.impacts.map(impact => impact.source)] : [];
    }
    function projectDeletionFields(content) {
      return {tree:content.tree, standalone_assets:content.standalone_assets,
        child_paths:content.children.map(child => ({id:child.item.id, path:child.relative_path})),
        associated_graphs:content.impacts.filter(impact => impact.associated_graph).map(impact => impact.source.item.id)};
    }
    function deletionDetailHtml() {
      const preview = detail.preview;
      if (!preview || detail.content_cleaned) return '<p>完整删除影响尚未载入或已清理，不能批准。</p>';
      const json = value => esc(JSON.stringify(value, null, 2));
      const sources = deletionSources();
      const cascade = detail.kind === 'project';
      const content = preview.content;
      const cascadeDetails = cascade ? `<section data-project-deletion-inventory><h3>完整目录树、独立附件和保留的关联图</h3><pre class="agent-proposal-full-text" data-project-deletion-fields>${json(projectDeletionFields(content))}</pre></section>` : '';
      const label = index => index === 0 ? '将移入回收站的完整目标' :
        index <= (content.children?.length || 0) ? '随项目移动的子记录' :
        content.impacts[index - 1 - (content.children?.length || 0)].associated_graph ? '保留原项目归属的关联图' : '潜在活动断链来源';
      return `<section class="agent-proposal-detail"><p class="agent-error">此操作将正式条目移入回收站，请核对完整删除影响。</p><p>目标：${esc(detail.target_id)} · 提案 ${esc(detail.proposal_id)} · 版本 ${detail.version}</p><p>固定回收身份：${esc(preview.trash_token)}</p><ul class="agent-error">${preview.warnings.map(warning => `<li>${esc(warning)}</li>`).join('')}</ul><p data-deletion-state role="status">正在载入完整内容和全部图画布，完成前不能批准。</p>${sources.map((source, index) => `<article data-deletion-source="${index}"><h3>${label(index)}：${esc(source.item.title || source.item.id)}（${esc(source.item.id)}）</h3><p>原始字节版本：${esc(source.revision)}</p>${source.item.body !== undefined ? `<h4>完整正文</h4><div class="markdown-preview agent-proposal-markdown">${renderMarkdown(source.item.body, source.item)}</div>` : ''}<h4>全部元数据与有序结构字段</h4><pre data-deletion-structure>${json(source.item)}</pre><h4>完整原始文件</h4><pre data-deletion-raw>${esc(source.raw_source)}</pre><h4>完整附件清单</h4><pre data-deletion-assets>${json(source.attachments || [])}</pre>${source.graph ? `<h4>完整只读图画布</h4><div data-deletion-canvas="${index}"></div><ul>${source.graph_warnings.map(warning => `<li>${esc(warning)}</li>`).join('')}</ul><h4>全部节点</h4><ol>${source.graph.nodes.map(node => `<li data-deletion-node><pre>${json(node)}</pre></li>`).join('')}</ol><h4>全部关系</h4><ol>${source.graph.edges.map(edge => `<li data-deletion-edge><pre>${json(edge)}</pre></li>`).join('')}</ol>` : ''}</article>`).join('')}${cascadeDetails}<h3>全部潜在引用与保留规则</h3><pre data-deletion-impact>${json({references:preview.content.impacts.map(impact => ({id:impact.source.item.id, references:impact.references})), retention:preview.content.retention})}</pre><h3>来源说明</h3><pre>${esc(preview.source_note || '未提供来源说明')}</pre><h3>完整执行依据</h3><pre>${json({authorization_revision:preview.authorization_revision, dependencies:preview.dependencies, execution_plan:preview.execution_plan, plan_digest:preview.plan_digest})}</pre><p>预览摘要：${esc(preview.preview_digest)}</p>${detail.receipt ? '<p>这是原删除回执；后续恢复或清理不会重放删除，当前回收站状态以打开后为准。</p>' : ''}</section>`;
    }
    function mountDeletionPreview(modal) {
      if (detail?.operation !== 'delete' || detail.kind === 'category' || !detail.preview || detail.content_cleaned) return;
      const shown = detail, key = graphKey(shown), sources = deletionSources(), generation = deletionViews;
      const state = modal.querySelector('[data-deletion-state]');
      const fail = () => {
        if (detail !== shown || deletionViews !== generation) return;
        deletionReady = null; shown.preview_ticket = null;
        state.textContent = '完整删除影响载入失败，不能批准。请重新读取当前版本。';
        state.classList.add('agent-error');
        const approve = modal.querySelector('[data-proposal-action="approve"]');
        if (approve) approve.disabled = true;
      };
      try {
        if (shown.preview.proposal_id !== shown.proposal_id || shown.preview.version !== shown.version || sources[0].item.id !== shown.target_id || modal.querySelectorAll('[data-deletion-source]').length !== sources.length) throw new Error('Incomplete deletion identity');
        if (shown.kind === 'project' && modal.querySelector('[data-project-deletion-fields]')?.textContent !== JSON.stringify(projectDeletionFields(shown.preview.content), null, 2)) throw new Error('Incomplete project cascade fields');
        const waits = sources.map((source, index) => {
          const block = modal.querySelector(`[data-deletion-source="${index}"]`);
          if (block.querySelector('[data-deletion-raw]')?.textContent !== source.raw_source.replace(/\r\n?/g, '\n') || block.querySelector('[data-deletion-structure]')?.textContent !== JSON.stringify(source.item, null, 2) || block.querySelector('[data-deletion-assets]')?.textContent !== JSON.stringify(source.attachments || [], null, 2)) throw new Error('Incomplete source fields');
          if (!source.graph) return Promise.resolve(true);
          if (block.querySelectorAll('[data-deletion-node]').length !== source.graph.nodes.length || block.querySelectorAll('[data-deletion-edge]').length !== source.graph.edges.length) throw new Error('Incomplete graph fields');
          const view = global.Workbench.conceptMap.create({readOnly:true, root:block.querySelector('[data-deletion-canvas]'), graph:{...source.graph, id:source.item.id}, escapeHtml:esc});
          deletionViews.push(view);
          return view.ready;
        });
        Promise.all(waits).then(results => {
          if (detail !== shown || deletionViews !== generation || !isActive() || !modal.open || graphKey(detail) !== key) return;
          if (!results.every(Boolean)) { fail(); return; }
          deletionReady = key;
          state.textContent = '目标、全部潜在断链来源、附件、保留规则和图画布已完整载入。';
          const approve = modal.querySelector('[data-proposal-action="approve"]');
          if (approve) approve.disabled = !approvalEnabled();
        }).catch(fail);
      } catch { fail(); }
    }

    function mountGraphPreview(modal) {
      if (detail?.operation === 'delete' || detail?.kind !== 'concept_map' || !detail.preview || detail.content_cleaned) return;
      const shown = detail, key = graphKey(shown);
      const state = modal.querySelector('[data-proposal-graph-state]');
      const fail = () => {
        if (detail !== shown) return;
        graphReady = null; shown.preview_ticket = null;
        state.textContent = '完整图预览载入失败，不能批准。请重新读取当前版本。';
        state.classList.add('agent-error');
        const approve = modal.querySelector('[data-proposal-action="approve"]');
        if (approve) approve.disabled = true;
      };
      try {
        const graph = shown.preview.prepared_graph;
        const candidate = shown.preview.content?.graph;
        if (!candidate || shown.preview.proposal_id !== shown.proposal_id || shown.preview.version !== shown.version || graph.id !== shown.target_id || !/^[a-f0-9]{64}$/.test(shown.preview.preview_digest) || Object.keys(candidate).some(field => JSON.stringify(candidate[field]) !== JSON.stringify(graph[field]))) throw new Error('Graph preview identity/content mismatch');
        if (modal.querySelectorAll('[data-graph-node-details]').length !== graph.nodes.length || modal.querySelectorAll('[data-graph-edge-details]').length !== graph.edges.length || !modal.querySelector('[data-graph-base]') || !modal.querySelector('[data-graph-diff]')) throw new Error('Incomplete graph details');
        const view = global.Workbench.conceptMap.create({readOnly:true, root:modal.querySelector('[data-proposal-graph-canvas]'), graph, escapeHtml:esc});
        graphView = view;
        view.ready.then(complete => {
          if (detail !== shown || graphView !== view || !isActive() || !modal.open || graphKey(detail) !== key) return;
          if (!complete) { fail(); return; }
          graphReady = key;
          state.textContent = `完整画布及 ${graph.nodes.length} 个节点、${graph.edges.length} 条关系的全部明细已载入。`;
          const approve = modal.querySelector('[data-proposal-action="approve"]');
          if (approve) approve.disabled = !approvalEnabled();
        }).catch(fail);
      } catch { fail(); }
    }

    function paintPreview() {
      const modal = dialog();
      if (!modal) return;
      disposeGraph();
      const body = modal.querySelector('.agent-proposal-preview-body');
      const scroll = body?.scrollTop || 0;
      const focused = modal.contains(global.document.activeElement) ? global.document.activeElement.dataset.proposalAction : null;
      const index = listing.items.findIndex(item => item.proposal_id === previewId);
      const receipt = detail?.receipt;
      const projectResult = receipt?.kind === 'project' && /^\/\?item=project&itemId=[^&]+$/.test(receipt.web_path || '') &&
        new URLSearchParams(receipt.web_path.slice(2)).get('itemId') === receipt.item_id;
      const projectLink = projectResult ? `<a class="secondary-button" href="${esc(receipt.web_path)}" data-proposal-project-result="${esc(receipt.item_id)}">打开新项目</a>` : '';
      modal.innerHTML = `<header><div><p class="eyebrow">提案完整预览</p><h2 id="proposalPreviewTitle">${esc(detail?.title || '加载提案')}</h2><small>${detail ? `${esc(kinds[detail.kind] || detail.kind)} · ${esc(operations[detail.operation] || detail.operation)} · ${esc(states[detail.state] || detail.state)} · 版本 ${detail.version}` : ''}</small></div><button type="button" class="icon-button dialog-close" data-proposal-action="close-preview" aria-label="关闭预览" ${confirming ? 'disabled' : ''}>✕</button></header><div class="agent-proposal-preview-body" tabindex="0">${detailHtml()}</div><footer><p class="agent-feedback" data-proposal-feedback role="status" aria-live="polite"></p>${pending ? `<div class="settings-actions">上次操作结果尚未确定。${button('resolve', '查询提案操作结果')}</div>` : ''}<div class="settings-actions"><nav aria-label="本页提案切换">${button('preview-previous', '上一条', index <= 0 || pending ? 'disabled' : '')}<span>${index < 0 ? '当前提案不在本页' : `本页第 ${index + 1} / ${listing.items.length} 条`}</span>${button('preview-next', '下一条', index < 0 || index >= listing.items.length - 1 || pending ? 'disabled' : '')}</nav><div class="settings-actions">${button('review', '重新读取完整预览', `data-proposal-id="${esc(previewId || '')}" ${pending ? 'disabled' : ''}`)}${button('cancel', '取消当前版本', `data-proposal-id="${esc(detail?.proposal_id || '')}" ${!pending && detail && ['draft', 'previewed', 'conflicted'].includes(detail.state) && !detail.content_cleaned ? '' : 'disabled'}`)}<button type="button" class="primary-button" data-proposal-action="approve" ${!approvalEnabled() ? 'disabled' : ''}>${detail?.kind === 'category' ? '批准分类变更' : detail?.operation === 'delete' ? '批准移入回收站' : detail?.kind === 'project' ? '批准创建项目' : '批准并入库'}</button>${projectLink}${receipt?.web_path && ((receipt.deleted && /^\/\?item=trash&itemId=(?:record|document|concept-map|project)-agent-[a-f0-9-]{36}-[1-9][0-9]*$/.test(receipt.web_path)) || /^\/\?item=(issue|todo|info|document)&itemId=[A-Z]+-\d+$/.test(receipt.web_path) || /^\/\?item=concept_map&itemId=CMAP-\d+$/.test(receipt.web_path) || /^\/\?item=project&itemId=[^&]+&assetId=ASSET-[a-f0-9]{32}$/.test(receipt.web_path)) ? `<a class="secondary-button" href="${esc(receipt.web_path)}" ${receipt.deleted ? `data-proposal-trash-result="${esc(receipt.trash_token)}"` : receipt.kind === 'concept_map' ? `data-proposal-concept-result="${esc(receipt.item_id)}"` : ''}>${receipt.deleted ? '打开回收站结果' : '打开入库结果'}</a>` : ''}</div></div></footer>`;
      modal.querySelector('.agent-proposal-preview-body').scrollTop = scroll;
      mountGraphPreview(modal);
      mountDeletionPreview(modal);
      mountProjectPreview(modal);
      if (detail?.kind === 'category' && detail.preview?.version === detail.version && detail.preview?.proposal_id === detail.proposal_id &&
          modal.querySelector('[data-category-impact]')?.textContent === JSON.stringify(detail.preview.content, null, 2) &&
          modal.querySelector('[data-category-local-plan]')?.textContent === JSON.stringify(detail.local_category_plan, null, 2)) {
        categoryReady = graphKey(detail);
        modal.querySelector('[data-proposal-action="approve"]').disabled = !approvalEnabled();
      }
      if (focused) modal.querySelector(`[data-proposal-action="${focused}"]`)?.focus({preventScroll:true});
    }
    function paint() {
      const scroll = global.scrollY;
      if (!root.querySelector('#proposalListShell')) {
        root.innerHTML = '<div id="proposalListShell"></div><dialog id="proposalPreviewDialog" class="history-dialog agent-proposal-dialog agent-settings" aria-labelledby="proposalPreviewTitle"></dialog>';
        dialog().addEventListener('cancel', event => { event.preventDefault(); closePreview(); });
        dialog().addEventListener('close', () => {
          if (previewId && !dialog().open) closePreview({force:true});
        });
      }
      root.querySelector('#proposalListShell').innerHTML = `<div class="settings-stack agent-settings"><section class="settings-card"><div class="agent-section-head"><h2>提案管理</h2>${button('refresh', '刷新列表')}</div><p>仅本机管理会话可查看当前空间各客户端的候选内容。</p><div class="agent-proposal-filters">${filter('client_id', '客户端', Object.fromEntries(listing.clients.map(client => [client.client_id, client.name])))}${filter('kind', '类型', kinds)}${filter('state', '状态', states)}${filter('operation', '操作', operations)}</div></section><p id="proposalFeedback" data-proposal-feedback class="agent-feedback" role="status" aria-live="polite"></p>${pending ? `<section class="settings-card"><p>上次提案操作结果尚未确定，请先查询同一操作。</p>${button('resolve', '查询提案操作结果')}</section>` : ''}<section class="settings-card"><div class="agent-client-list">${listing.items.map(item => `<article class="agent-client"><strong>${esc(item.title)}</strong><small>${esc(item.client_name)} · ${esc(kinds[item.kind])} · ${esc(operations[item.operation])} · ${esc(states[item.state])}</small><small>归属：${esc(item.access_target.project_id || item.access_target.category || '—')} · 版本 ${item.version}</small><small>${esc(item.proposal_id)}</small>${button('review', '查看完整预览', `data-proposal-id="${esc(item.proposal_id)}"`)}</article>`).join('') || '<p class="empty-state">当前筛选下暂无提案。</p>'}</div><div class="settings-actions">${button('previous', '上一页', cursors.length < 2 ? 'disabled' : '')}<span>第 ${cursors.length} 页 · 每页 20 项</span>${button('next', '下一页', !listing.next_cursor ? 'disabled' : '')}</div></section></div>`;
      if (previewId) paintPreview();
      message(feedback, feedbackError);
      global.scrollTo({top:scroll, behavior:'instant'});
    }
    async function load({preservePreview = false} = {}) {
      if (!preservePreview && dialog()?.open) closePreview();
      message('');
      const version = ++epoch;
      busy = true;
      paint();
      try {
        const fresh = await request('status');
        if (!current(version)) return;
        if (status?.workspace_id !== fresh.workspace_id) { detail = null; pending = null; filters = {client_id:'', kind:'', state:'', operation:''}; cursors = ['0']; }
        status = fresh;
        if (!pending) { try { pending = JSON.parse(global.sessionStorage.getItem(key()) || 'null'); } catch { pending = null; } }
        const params = new URLSearchParams({...filters, cursor:cursors.at(-1), limit:20});
        const result = await request(`proposals?${params}`);
        if (!current(version)) return;
        if (result.workspace_id !== status.workspace_id) throw new Error('工作空间已变化，请刷新');
        listing = result;
        if (!preservePreview) detail = null;
        busy = false;
        paint();
        return true;
      } catch (error) { if (current(version)) { busy = false; paint(); message(error.payload?.message || error.message, true); } }
      return false;
    }
    async function review(proposalId) {
      if (!isActive()) return;
      const opening = !dialog()?.open;
      if (opening) { listScroll = global.scrollY; returnId = proposalId; }
      previewId = proposalId;
      detail = null; projectAccess = null;
      message('');
      const version = ++epoch;
      busy = true; paint();
      dialog().querySelector('.agent-proposal-preview-body').scrollTop = 0;
      if (opening) {
        savedOverflow = global.document.body.style.overflow;
        global.document.body.style.overflow = 'hidden';
        const style = global.document.documentElement.style;
        savedRootStyle = {overflow:style.overflow, scrollbarGutter:style.scrollbarGutter};
        style.overflow = 'hidden';
        style.scrollbarGutter = 'auto';
        dialog().showModal();
        dialog().querySelector('[data-proposal-action="close-preview"]').focus({preventScroll:true});
      }
      try {
        const value = await request(`proposals/${encodeURIComponent(proposalId)}/preview`);
        if (!current(version)) return;
        if (value.workspace_id !== status.workspace_id) throw new Error('工作空间已变化，请刷新');
        detail = value;
        busy = false; paint();
      } catch (error) { if (current(version)) { busy = false; paint(); message(error.payload?.message || error.message, true); } }
    }
    async function cancel() {
      if (!pending) {
        const shown = detail;
        if (!shown || confirming) return;
        confirming = true;
        let approved;
        try { approved = await confirm({title:'取消当前提案版本？', message:`${shown.title} · 版本 ${shown.version}`, detail:'候选内容不再提交，已存在的正式记录不受影响。', confirmText:'取消提案', danger:true}); } finally { confirming = false; }
        if (!approved) return;
        if (shown !== detail || !isActive()) return;
        remember({proposal_id:detail.proposal_id, payload:{workspace_id:status.workspace_id, expected_version:detail.version, request_id:global.crypto.randomUUID()}});
      }
      const version = ++epoch;
      busy = true; paint();
      try {
        const result = await request(`proposals/${encodeURIComponent(pending.proposal_id)}/cancel`, {method:'POST', body:JSON.stringify(pending.payload)});
        if (!current(version)) return;
        remember(null);
        busy = false;
        if (!await load({preservePreview:true})) return;
        await review(result.proposal_id);
        message('提案已取消。');
      } catch (error) {
        if (current(version)) {
          if (error.status && error.status < 500) remember(null);
          busy = false; paint(); message(`${error.payload?.message || error.message}${pending ? '；请查询同一取消操作。' : '；请重新核对当前版本。'}`, true);
        }
      }
    }
    async function approve() {
      const shown = detail;
      if (!approvalEnabled() || confirming) return;
      const offerAccess = shown.kind === 'project' && dialog()?.querySelector('[data-project-access-after]')?.checked;
      confirming = true;
      let approved;
      try { approved = await confirm({title:shown.kind === 'category' ? '批准当前完整分类变更？' : shown.operation === 'delete' ? '批准当前完整影响并移入回收站？' : shown.kind === 'project' ? '批准创建这个固定项目？' : '批准当前完整预览并入库？', message:`${shown.title} · 版本 ${shown.version}`, detail:shown.kind === 'category' ? '按完整计划迁移分类及等价授权。原条目和附件文件保留。' : shown.operation === 'delete' ? shown.kind === 'project' ? '将原项目目录及所列子记录和项目内附件一起移入回收站。项目外关联图保留原项目归属。' : '只删除当前固定版本；附件、历史及其他正文保留。默认保留30天，本机可提前永久删除。修改后必须重新完整预览批准。' : '将以原客户端当前权限写入此版本；修改后必须重新预览批准。', confirmText:shown.kind === 'category' ? '批准分类变更' : shown.operation === 'delete' ? '批准移入回收站' : shown.kind === 'project' ? '批准创建项目' : '批准并入库', danger:shown.operation === 'delete'}); }
      finally { confirming = false; }
      if (!approved || shown !== detail || !isActive() || !approvalEnabled()) return;
      const payload = {workspace_id:status.workspace_id, version:shown.version, preview_digest:shown.preview.preview_digest, preview_ticket:shown.preview_ticket, request_id:global.crypto.randomUUID()};
      remember({operation:'approve', proposal_id:shown.proposal_id, request_id:payload.request_id});
      const version = ++epoch;
      busy = true; paint();
      try {
        const result = await request(`proposals/${shown.proposal_id}/approve`, {method:'POST', body:JSON.stringify(payload)});
        if (!current(version)) return;
        remember(null); busy = false;
        if (!await load({preservePreview:true})) return;
        await review(result.proposal_id);
        message(result.state === 'completed' ? (detail?.kind === 'category' ? '分类变更已完成。' : detail?.operation === 'delete' ? '已批准并移入回收站。' : detail?.kind === 'project' ? '项目已创建；访问范围单独处理。' : '已批准并入库。') : '原操作尚未完成，请重新核查。', result.state !== 'completed');
        if (result.state === 'completed' && offerAccess && detail?.proposal_id === shown.proposal_id) await previewProjectAccess();
      } catch (error) {
        if (current(version)) {
          if (error.status && error.status < 500) { remember(null); detail = null; }
          busy = false; paint(); message(`${error.payload?.message || error.message}${pending ? '；请先查询原操作结果。' : '；请重新完整预览。'}`, true);
        }
      }
    }
    async function previewProjectAccess() {
      const proposalId = detail?.proposal_id;
      if (detail?.kind !== 'project' || !detail.receipt || pending) return;
      const version = ++epoch;
      busy = true; projectAccess = null; paint();
      try {
        const result = await request(`proposals/${encodeURIComponent(proposalId)}/project-access/preview`);
        if (!current(version) || detail?.proposal_id !== proposalId) return;
        if (result.proposal_id !== proposalId || result.workspace_id !== status.workspace_id || result.project_id !== detail.target_id) throw new Error('授权预览身份不一致');
        projectAccess = result; busy = false; paint();
      } catch (error) {
        if (current(version)) { busy = false; paint(); message(`项目已创建；访问授权预览失败：${error.payload?.message || error.message}`, true); }
      }
    }
    async function approveProjectAccess() {
      const preview = projectAccess;
      if (!preview?.preview_id || detail?.proposal_id !== preview.proposal_id || pending ||
          dialog()?.querySelector('[data-project-access-full]')?.textContent !== JSON.stringify(preview, null, 2)) return;
      confirming = true;
      let approved;
      try { approved = await confirm({title:'独立批准此项目访问范围？', message:preview.project_id,
        detail:preview.disclosure, confirmText:'批准追加此项目范围'}); } finally { confirming = false; }
      if (!approved || !isActive() || preview !== projectAccess || detail?.proposal_id !== preview.proposal_id) return;
      const payload = {workspace_id:status.workspace_id, expected_version:preview.expected_version, preview_id:preview.preview_id,
                       preview_digest:preview.preview_digest, approved:true, request_id:global.crypto.randomUUID()};
      remember({operation:'project-access', proposal_id:preview.proposal_id, request_id:payload.request_id});
      const version = ++epoch;
      busy = true; paint();
      try {
        const result = await request(`proposals/${encodeURIComponent(preview.proposal_id)}/project-access/confirm`, {method:'POST',body:JSON.stringify(payload)});
        if (!current(version)) return;
        if (result.proposal_id !== preview.proposal_id || result.project_id !== preview.project_id) throw new Error('授权回执身份不一致');
        remember(null); projectAccess = null; busy = false; paint(); message('项目访问范围已独立授权。');
      } catch (error) {
        if (current(version)) {
          if (error.status && error.status < 500) { remember(null); projectAccess = null; }
          busy = false; paint(); message(`项目已创建；访问授权未确认：${error.payload?.message || error.message}`, true);
        }
      }
    }
    async function resolveProjectAccess() {
      const original = pending;
      const version = ++epoch;
      busy = true; paint();
      try {
        const result = await request(`operations/${encodeURIComponent(original.request_id)}`);
        if (!current(version)) return;
        if (result.state === 'completed' && result.result?.proposal_id === original.proposal_id || result.state === 'abandoned') {
          remember(null); projectAccess = null; busy = false; paint();
          message(result.state === 'completed' ? '已查到独立项目访问授权回执。' : '访问授权已放弃；项目创建结果保留。');
        } else { busy = false; paint(); message('原访问授权操作需要核查；项目创建结果保留。', true); }
      } catch (error) {
        if (current(version)) {
          if (error.status === 404) { remember(null); projectAccess = null; }
          busy = false; paint(); message(`项目创建结果保留：${error.payload?.message || error.message}`, true);
        }
      }
    }
    async function resolve() {
      if (pending?.operation === 'project-access') return resolveProjectAccess();
      if (pending?.operation !== 'approve') return cancel();
      const version = ++epoch;
      busy = true; paint();
      try {
        const result = await request(`proposal-actions/${encodeURIComponent(pending.request_id)}`);
        if (!current(version)) return;
        if (['completed', 'not_applied', 'abandoned'].includes(result.state)) {
          remember(null); busy = false;
          if (!await load({preservePreview:true})) return;
          await review(result.proposal_id);
          message(result.state === 'completed' ? (detail?.operation === 'delete' ? '已查到原删除回执。' : detail?.kind === 'project' ? '已查到原项目创建回执。' : '已查到原入库回执。') : result.state === 'abandoned' ? '原操作已接受当前盘态并放弃；这不撤销删除或恢复文件，残留仍需人工核查。' : '原批准未应用；请重新完整预览后批准。');
        } else { busy = false; paint(); message('原事务需要恢复核查，请按维护说明处理。', true); }
      } catch (error) {
        if (current(version)) { busy = false; paint(); message(error.payload?.message || error.message, true); }
      }
    }
    root.addEventListener('click', event => {
      if (!isActive()) return;
      const result = event.target.closest('[data-proposal-concept-result], [data-proposal-trash-result], [data-proposal-project-result]');
      if (result) {
        event.preventDefault();
        if (busy || confirming || pending) return;
        if (typeof openItemLink !== 'function') { message('结果导航尚未就绪，请刷新后重试。', true); return; }
        openItemLink(result.dataset.proposalTrashResult ? {kind:'trash', itemId:result.dataset.proposalTrashResult} : result.dataset.proposalProjectResult ? {kind:'project', itemId:result.dataset.proposalProjectResult} : {kind:'concept_map', itemId:result.dataset.proposalConceptResult}).catch(error => notify('打开操作结果失败', error.message, true));
        return;
      }
      const node = event.target.closest('[data-proposal-action]');
      if (!node) return;
      event.preventDefault();
      const action = node.dataset.proposalAction;
      if (action === 'close-preview') { closePreview(); return; }
      if (busy || confirming) return;
      if (action === 'preview-previous' || action === 'preview-next') {
        if (pending) { message('请先查询提案操作结果。', true); return; }
        const index = listing.items.findIndex(item => item.proposal_id === previewId);
        const target = index < 0 ? null : listing.items[index + (action === 'preview-next' ? 1 : -1)];
        if (target) review(target.proposal_id);
        return;
      }
      if (pending && action !== 'resolve') { message('请先查询提案操作结果。', true); return; }
      if (action === 'review') review(node.dataset.proposalId).catch(error => notify('提案加载失败', error.message, true));
      if (action === 'refresh') load();
      if (action === 'next' && listing.next_cursor) { cursors.push(listing.next_cursor); load(); }
      if (action === 'previous' && cursors.length > 1) { cursors.pop(); load(); }
      if (action === 'cancel') cancel().catch(error => message(error.message, true));
      if (action === 'resolve') resolve().catch(error => message(error.message, true));
      if (action === 'project-access-preview') previewProjectAccess();
      if (action === 'project-access-approve') approveProjectAccess().catch(error => message(error.message,true));
      if (action === 'approve') approve().catch(error => message(error.message, true));
    });
    root.addEventListener('change', event => {
      if (!isActive() || busy || pending || !event.target.dataset.proposalFilter) return;
      filters[event.target.dataset.proposalFilter] = event.target.value; cursors = ['0']; load();
    });
    return {load, deactivate:() => { closePreview({force:true}); epoch += 1; busy = false; detail = null; }, isBusy:() => busy || confirming || Boolean(pending)};
  }
  global.Workbench = global.Workbench || {};
  global.Workbench.agentProposals = {create};
})(typeof window !== 'undefined' ? window : globalThis);
