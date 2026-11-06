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

## Agent 接入与本机管理（AG-102～111）

AG-107 增加 `agent_runtime.py` 和 `agent_management_http.py`：只读发现、私人目录 runtime.json 启动偏好、显式 CLI 覆盖、当前 Repository 上的运行时启停。管理接口位于 `/api/local/agent-management/`，仅 loopback，独立同源管理会话，不接受 Agent 凭据；提供 status/runtime/operations 基础路由。锁序为空间切换锁 → 仓储锁 → 私人配置目录锁。空间切换重新建立管理会话；状态查询不创建身份或凭据。

AG-108 增加 `agent_management.py`，CLI 和管理 HTTP 共同调用 CredentialManager；客户端创建/编辑/轮换/撤销/服务地址修复采用持久日志、配置目录跨进程锁与重读恢复。HTTP 的 Agent 请求也在相同凭据锁内鉴权并执行，管理操作不能在已接受的业务请求中途更换授权；待锁最多 3 秒后返回可重试冲突。分类变更前收窄旧名称授权，成功重命名后恢复为新名称；跨业务/私人配置失败时保留收窄，不自动扩大权限。客户端列表与操作查询脱敏，管理 UI 和诊断分别由 AG-109/110 实现。

AG-109 提供 `js/features/agent-settings.js` 独立 feature，通过统一 API/对话框接入现有管理页与未保存提示，导航新增 agent_settings 并保持设置侧栏选中。状态和授权属于服务端；表单、管理会话、待查询操作仅在交互内存，不存 localStorage。`agent_setup.py` 从可信安装/凭据路径派生指引，生成正确转义的 PowerShell 命令，GET/POST clients/<id>/setup 不执行命令、不修改 Codex；仅同源管理页面可获必要本机路径。诊断握手和请求证据见 AG-110 模块。

AG-110 的 `agent_diagnostics.py` 在服务内存登记后台任务，线程在业务锁外启动固定探测/桥接子进程并等待 HTTP；有总时限、输出限制和进程清理。诊断执行 initialize/tools/list/capabilities；一次性环境 nonce 传至桥接的专用 HTTP 头，只有服务内存匹配 nonce/client/有效期才归为自检。普通请求与自检时间分开记录，均不证明聊天身份。管理 API 增加 POST diagnostics、GET diagnostics/<operation_id>；任务及观察值只在本次服务/空间内有效，不扩展 Agent MCP 工具权限。

AG-112 的 agent_setup 为 CMD/PowerShell 分别引用参数；UI Windows 默认 CMD，旧 API 未传 terminal 仍生成 PowerShell。检测函数共享给向导与诊断：优先 PATH，Windows 后备当前用户 LOCALAPPDATA/OpenAI/Codex/bin 下存在的版本化 exe，返回绝对路径，不修改系统环境。CMD 不安全字符拒绝生成；PowerShell 保持单引号字面量规则。手工命令入口继续保留。

AG-113 的 agent_registration 独立处理明确确认后的本机 Codex 登记，管理 HTTP 只负责同源会话/路由，不向 MCP 增加权限。POST clients/<id>/registration-preview 返回目标、脱敏原项、完整新项和版本摘要；POST clients/<id>/registration 接受名称/版本/替换选择/request_id，不接受路径或命令。目标由服务 CODEX_HOME/当前用户目录确定，预览绑定整份文件和客户端版本。固定参数的 Codex mcp add/get 在私人临时 CODEX_HOME 中执行，校验仅目标 MCP 项变化，之后备份、准备回执、版本复查并原子安装。持仓储/凭据/目标目录锁时不运行 HTTP 自检，写入结果返回后由页面调用既有后台诊断，避免锁内等待自己。

GET registrations/<request_id> 比较准备日志的前后摘要与当前文件，不自动重放或回滚；回执和私密快照长期保留。sessionStorage 只保存当前标签页未决请求/客户端 ID，不保存管理令牌。目标目录跨进程锁可协调不同空间的工作台登记，不能阻止外部 Codex/编辑器在版本检查与替换间竞争。这里只保证单文件原子替换与可核查恢复，不宣称跨程序事务。

显式 --enable-agent 后装配 AgentSecurity 和 AgentService，/api/agent/v1/* 由 agent_http.py 分派；不在桥接进程装配 Repository。业务逻辑位于 agent_service.py，提案和恢复位于 agent_proposals.py；正式写入复用领域仓储的 PreparedMarkdownWrite，不在协议层复制 CRUD。Agent 凭据在仓库/数据目录外保存，工作空间身份在 .agent/workspace.json；迁移后重新装配服务。提案独立于业务文件；提交持久操作日志后应用正式 Markdown，最后写入回执。未决日志会阻止普通写入，重启即使关闭 Agent 接入仍要执行恢复。

静态服务只允许 index.html 和其显式版本化资源，拒绝目录与源码访问。Host/Origin 校验和旧接口拒绝 Agent Authorization 在协议层处理；HTTP 写入与目录切换串行化，领域写入仍使用 Repository 的可重入锁。

stdio MCP 入口为 agent_bridge.py，workbench/mcp_stdio.py 只负责协议和本机 HTTP 调用，agent_tools.py 定义公开工具及 Schema/使用规则；不会装配 Repository 或调用模型。协议/凭据错误输出脱敏，stdout 只含 JSON-RPC。真实 Codex 联调脚本使用隔离配置和临时工作空间，不更改用户现有设置。

提交回执包含稳定 ID 的 `web_path`，HTTP 层按可信本机 Host 补全 `web_url`。导航模块只解析 issue/document 深链接，app.js 在处理已有草稿后打开原编辑器。旧回执缺少链接时兼容生成展示字段。两个编辑器在保存响应返回时比较当前输入和已发送内容；后续输入保留 dirty/草稿并使用返回 revision 继续保存，旧会话响应不得修改新会话。

### AG-116 类型授权与流程兼容

AgentSecurity 统一计算 kinds 与 scopes、项目/分类的交集，引用和提案归属复用同一规则。CredentialManager 的跨进程日志同时写入私人配置和服务端授权，轮换、旧编辑请求、分类迁移均保留有效类型。新提案和事务使用 schema=2，ProposalStore 分版本生成摘要；schema=1 保留旧算法，不静默重算已预览摘要。AG-117 起 issue/document/todo 可用，info 已于 AG-118 开放。

### AG-117 待办接入

AgentService 对 todo 复用记录领域的预备写入/历史/缓存失效，catalog(kind=todo) 使用所属项目工作流。completed 从状态推导，append 只接受正文；事务仅放开 projects/<id>/todos 下合法稳定编号。navigation 识别 todo/TODO 深链接，装配进入既有待办抽屉与共享编辑器。

### AG-118 结构化信息

info 复用 RecordRepository 和共享 Markdown 序列化，AgentService 严格校验新请求后调用 normalize_info_fields；兼容旧字典解析保持。字段是有序 name/value/note 列表，不增加 ID 或平行存储。只读摘要不携带全部字段，完整读取和预览含全部字段，字段差异显示 before/after 有序列表。Agent 不能修改 info_color，也不执行字段命令。
