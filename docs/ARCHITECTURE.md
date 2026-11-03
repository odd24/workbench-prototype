# 架构说明

## 技术边界

本地工作台是单进程、单用户、本地优先应用：

```text
浏览器原生 UI
  → /api/* JSON 或字节流
Python ThreadingHTTPServer
  → Repository 兼容门面
领域仓储
  → Markdown / JSON / 附件文件
```

没有第三方运行时依赖、包管理器、打包器或数据库。磁盘文件是业务事实源；DOM、JavaScript 状态、缓存和 `localStorage` 只服务交互。

## 后端

- `server.py`：CLI、旧进程替换、服务生命周期与兼容导出。`server.Repository` 是轻量装配子类，用回调保留现有测试和本地调用对 `server.load_markdown`、`server.open_markdown_external` 的 patch 点。
- `workbench/http_api.py`：HTTP Server、协议解析、状态码和路由；不直接实现领域规则。
- `workbench/repository.py`：组合领域仓储的兼容门面，协调回收站、整库导出和演示数据。
- `workbench/projects.py`、`records.py`、`documents.py`、`concept_maps.py`、`assets.py`：领域文件、校验、缓存和 CRUD。
- `workbench/configuration.py`：工作流、标签、分类和排序配置。
- `workbench/markdown_io.py`：轻量 front matter 与 Markdown I/O。
- `workbench/write_coordinator.py`：Repository 共享可重入写锁、SHA-256 内容版本检查及服务数据目录独占锁；服务取得目录锁后才装配仓储。
- `workbench/history.py`：记录与知识库共用的原子 Markdown 历史快照、读取和保留规则。
- `workbench/persistence.py`：同目录临时文件、flush/fsync 和 `os.replace` 原子覆盖。
- `workbench/security.py`：文件名、分类、ZIP 成员和归档边界校验。
- `workbench/paths.py`、`external_editor.py`：数据目录、导出位置、Markdown 编辑器和附件默认应用的进程边界。

公开调用目前仍经 `Repository` 门面。兼容门面不是第二套实现；它只委托到组合仓储。删除它需要单独迁移所有导入和 patch 点，不能在日常维护中顺手移除。

## 前端

`index.html` 是唯一静态入口和脚本加载顺序事实源。普通脚本共享显式 `window.Workbench` 命名空间：

- `js/core/`：DOM、安全 API、对话框、状态分组、增量刷新、导航和应用生命周期。
- `js/editor/`：Markdown、文档模型、选区、结构块和共享编辑器宿主。
- `js/features/`：搜索、回收站、管理页、首页/项目模型、编辑会话、冲突和知识库模型。
- `concept-map.js`：概念图工厂实现；先加载定义 `Workbench.conceptMap`。
- `app.js`：最后加载，装配模块、持有页面 DOM 适配和仍需跨功能协调的渲染/事件入口。

`app.js` 仍较大，但共享算法、状态边界和生命周期已提取并具有独立契约。继续拆分 DOM 模板属于后续工作，不是以复制实现换取文件变小。

## 编辑器契约

记录和知识库分别持有独立会话状态，但共享同一条转换链：

```text
Markdown
→ markdownToHtml
→ hydrateEditorBlocks
→ 编辑器 DOM
→ editorToDocumentModel
→ documentModelToMarkdown
→ 保存并重新加载
```

标题、列表、任务列表、引用、代码、表格和分隔线都是直接结构块。代码高亮 DOM、选择工具栏和阅读视图不能污染保存结果。

## 状态与并发

`Workbench.appState` 将服务器数据、UI、编辑器和草稿状态分组。请求注册表按通道和资源身份拒绝过期异步结果。记录与文档轮询先比较轻量签名，只下载变化资源；脏编辑进入冲突流程，不能静默覆盖。记录和文档保存携带 `expected_revision`，服务端在共享写锁内比较实际文件 SHA-256；不匹配返回 409 并保留草稿。旧调用方省略版本时保持兼容，但不具备条件写入保护。外部编辑器不受服务锁控制，校验与替换间仍存在跨程序竞态；更新前历史保留旧内容。

## 样式

CSS 按以下固定次序加载：令牌、基础、组件、布局、记录、管理、编辑器、知识库、概念图、响应式。所有媒体查询集中在 `css/responsive.css`，按宽到窄排列。修改 CSS 或 JavaScript 后必须同步 `index.html` 的 `?v=` 缓存版本。

## Agent 接入（AG-102）

显式 --enable-agent 后装配 AgentSecurity 和 AgentService，/api/agent/v1/* 由 agent_http.py 分派；不在桥接进程装配 Repository。当前只开放授权范围内的读取。Agent 凭据在仓库/数据目录外保存，工作空间身份在 .agent/workspace.json；迁移后重新装配服务。写入流程仍在后续阶段实施。

静态服务只允许 index.html 和其显式版本化资源，拒绝目录与源码访问。Host/Origin 校验和旧接口拒绝 Agent Authorization 在协议层处理；HTTP 写入与目录切换串行化，领域写入仍使用 Repository 的可重入锁。
