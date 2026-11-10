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
- `workbench/history.py`：记录与知识库共用的原子 Markdown 历史快照、读取和保留规则，以及概念图原字节 JSON 历史（保留全部）。
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

提交回执包含稳定 ID 的 `web_path`，HTTP 层按可信本机 Host 补全 `web_url`。首期导航解析 issue/document 深链接，当前已按 AG-117/118 扩展至 issue/document/todo/info；app.js 在处理已有草稿后打开原编辑器。旧回执缺少链接时兼容生成展示字段。两个编辑器在保存响应返回时比较当前输入和已发送内容；后续输入保留 dirty/草稿并使用返回 revision 继续保存，旧会话响应不得修改新会话。

### AG-116 类型授权与流程兼容

AgentSecurity 统一计算 kinds 与 scopes、项目/分类的交集，引用和提案归属复用同一规则。CredentialManager 的跨进程日志同时写入私人配置和服务端授权，轮换、旧编辑请求、分类迁移均保留有效类型。新提案和事务使用 schema=2，ProposalStore 分版本生成摘要；schema=1 保留旧算法，不静默重算已预览摘要。AG-117 起 issue/document/todo 可用，info 已于 AG-118 开放。

### AG-117 待办接入

AgentService 对 todo 复用记录领域的预备写入/历史/缓存失效，catalog(kind=todo) 使用所属项目工作流。completed 从状态推导，append 只接受正文；事务仅放开 projects/<id>/todos 下合法稳定编号。navigation 识别 todo/TODO 深链接，装配进入既有待办抽屉与共享编辑器。

### AG-118 结构化信息

info 复用 RecordRepository 和共享 Markdown 序列化，AgentService 严格校验新请求后调用 normalize_info_fields；兼容旧字典解析保持。字段是有序 name/value/note 列表，不增加 ID 或平行存储。只读摘要不携带全部字段，完整读取和预览含全部字段，字段差异显示 before/after 有序列表。Agent 不能修改 info_color，也不执行字段命令。

### AG-119 本机提案管理

ProposalManagement 复用 ProposalStore 的只读完整预览构造与取消状态机，管理路由沿用 loopback/同源/短期会话，Agent Authorization 一律拒绝。独立 agent-proposals feature 使用统一 API 和只读 Markdown 渲染；列表不返回正文，详情按需加载。读取不发起新提交或业务恢复。取消使用独立 proposal-actions 持久日志，不混用凭据操作日志。

### AG-120 独立批准

客户端 minimum_confirmation_mode 缺省 agent_attested；提案记录不可自动降低的有效 confirmation_mode。策略收紧将未终结旧提案升级版本、清空旧摘要并要求重新预览。管理预览生成仅内存10分钟票据，绑定会话/空间/版本/摘要/策略/授权版本；MCP不返回票据。

网页批准在共享业务锁及凭据跨进程锁内重查权限、目标revision、配置和归一化，复用 AgentService.prepare_submission 与 ProposalStore.commit。持久批准记录先于事务准备；事务恢复核查批准关联，未应用时重查撤销/范围，已进入应用按磁盘事实完成原回执。凭据锁同线程可重入，覆盖恢复核查至应用，不把单文件替换宣称多文件事务。

当前AG-116～121及AG-126本机扩展已验收交付，含WorkBuddy5.9.3独立真实客户端矩阵；AG-122～125按用户单机范围取消，独立远程适配器未实现。可用边界、限制及恢复入口见[扩展验收](AI_AGENT_EXTENSION_ACCEPTANCE.md)，不能把远程候选架构当成代码事实。

用户用途更新（2026-11-06）：当前交付仅单机本地接入，远程AG-122～125已取消；不新增远程入口或身份基础设施。是否验收其他本机客户端与是否远程使用分别判断。


### AG-128 新授权与格式门槛

AgentSecurity在原模块内严格归一化休眠能力，CredentialManager仍是UI/CLI唯一写入和恢复入口，无第二仓储或业务CRUD。新授权3允许空旧kinds/范围；管理页面可配置明确资源的休眠能力，显示尚未实现不可使用，具体文件授权尚未开放。详细grants仅私人注册表/管理快照，桥接transport2不镜像。

capabilities.capability_authorization区分configured配置、静态已实现处理器提供的implemented及有效授权effective；当前新增能力两者均空，原四类型三操作和12个MCP工具保持。持久dormant状态不能被Agent/管理请求激活，后续上线仍须管理员重新授权，AG-129与各业务能力须承接此不变量。新schema的catalog仅返回可见条目使用的标签，分类按范围过滤；有权空项目仍返回工作流，休眠客户端无旧数据元信息。legacy全局标签行为保留。

根registry2/client授权3/log3/transport2职责与落盘顺序见DATA_FORMAT的AG-128节。根/日志双门槛拒绝旧二进制接入管理和鉴权，读取旧库不自动升级。完成/失败/abandon不降格式；未知日志先全量预检再恢复，避免按文件名先应用旧快照。普通网页可在关闭Agent时读取业务内容，这不代表旧版能安全读取新授权。所有后续业务工具仍未开放。


### AG-129 执行计划与恢复

agent_execution.py是ProposalStore内部的静态契约/校验模块，仅markdown@1和现有12组合，不是动态执行器或平行CRUD。ProposalStore仍负责提案/执行状态及回执，领域Prepared仍负责历史和正文写入。新3绑定实际依赖、授权revision及完整保存计划；旧1/2原分支保留。计划/manifest/快照/批准/receipt交叉校验，目标仅四类型受控路径；预检零写后才恢复，已完成匹配回执无需重复读Markdown快照。pending步骤仍逐字验快照，history/target写后和进度记录之间均有故障接点。

依赖粒度及保守状态集合绑定见本机方案AG-LOCAL-DEC-015；不绑定整个配置或所有可见资源。正文发布前重查权限/版本/依赖，历史已写不算正文已应用；正文已after则补原回执，不能重写后来已编辑或删除目标。server现有runtime挂载后的第二阶段恢复覆盖关闭接入启动，缺失私人授权保持写保护；状态读取仍不初始化空间。锁序保持空间切换→业务→凭据，不在锁内等待HTTP或子进程。休眠新能力仍不可用。
### AG-130 本机文件边界

agent_file_handles使用标准库ctypes封装Windows句柄属性/最终路径/卷类型/文件身份，元数据句柄不能读正文；agent_files负责管理票据、私人授权表、用途交集、流式hash与编码/原始字节分段。无任意路径MCP、目录授权或源文件写入。agent_management复用跨进程锁、CAS及日志4快照恢复，不另建凭据或业务仓储。

files HTTP单独捕获原repository/service及授权版本，长I/O不持业务/凭据/换库锁；结束短锁重验仍是原空间与服务、当前授权/期限后授予响应许可，socket限时写在锁外。撤销与许可的先后决定结果，无法撤回先获许可的数据。管理批准hash同样锁外，发布前重查同管理会话/票据/CAS；源内容不进入提案、草稿、搜索、历史、普通导出或管理日志。

### AG-131 暂存边界

agent_upload_policy管理独立的具体目标/来源策略，复用CredentialManager的日志4新upload_policy家族；agent_uploads仅管理私人暂存字节和会话，不是附件仓储，不写业务事实源。agent_upload_http为专用控制/字节通道及管理维护，源file_id复用130安全句柄。Agent分派在外层serialized_write锁外，各dispatcher仍显式短锁；普通网页锁不变，相关修复5abd6f2见验收补充。

持空间/业务/凭据锁的授权检查和ready元数据发布，与锁外流/hash分离；单会话OS锁持I/O，短目录配额锁只保护预留、part/blob切换、已验证句柄删除和预算发布。quota扫描与物理变化同锁，长hash在外；原始流header/body/socket发送不持业务锁。未知对象全量预检保留，原历史收据与当前可绑定性分开，正式消费接口占位拒绝，132/133承接正式附件。


### AG-132 附件正式提案边界

assets/attachment_prepared与Repository门面提供无写prepare和metadata apply；旧网页上传与Agent共享附件元数据/Markdown链接构造，记录复用原PreparedMarkdownWrite/历史，项目只改独立索引。agent_attachments负责严格候选、具体owner许可/依赖与source绑定；agent_attachment_execution是ProposalStore内静态attachment@1处理器，不建立第二套提案状态机或CRUD；agent_attachment_http只负责捕获会话/空间和锁外执行分派。

ProposalStore原预检/确认/版本/批准/回执复用，新增execution_schema2；普通Markdown恢复仍原短元数据路径，新二进制恢复从专用Agent查询/管理批准或action查询/服务启动/停服CLI进入，hash不会被旧外层业务/凭据/切换锁包住。copy接受意图后write_guard阻止普通写与孤儿清理，operation/session OS锁持IO；空间→业务→凭据仅最终短检查/原子发布/有界metadata，socket发送在锁外。源保护始终查询提案事实再修复镜像，未知引用不释放；退休另核完整正式回执。新项目结果链接只打开既有附件页并聚焦，不自动执行/打开文件。

共享Markdown仅增加受控相对附件链接和转义标签/URL往返，保留普通URL强调、行内code、引用及代码块。record/doc继续同一内核；知识库本项只回归已有外部图片能力，正式文档附件留133。

### AG-133：文档附件与普通网页上传

DocumentRepository继续拥有唯一document Markdown；AttachmentRepository的PreparedAttachment支持document，以全局assets/images或files承载字节，Markdown有序attachments为唯一目录。历史恢复同时恢复附件元数据；分类迁移更新附件category，未知meta保留。document_attachments提供严格metadata解析、受控路径和引用清单，现有/api/attachments按DOC-ID+真实metadata查找，无通用文件路径接口。共享document-model透传renderLink，两编辑器仍用同一Markdown/序列化宿主；文档附件链接不暴露原始Markdown标记。

DocumentUploads是普通网页操作证据组件，不是第二业务仓储或附件索引，独立于Agent启用/凭据。稳定UUID、stream身份与真实SHA、固定Prepared候选/快照/历史版本及幂等receipt驱动接收、提交、恢复、回收；复用132的native流验证/同句柄无覆盖rename与领域PreparedMarkdownWrite应用。单操作OS锁覆盖长流/hash，repository_switch/write锁仅短检查/预留与最终发布；receiving允许其他编辑，prepared/applying阻止冲突正式写。先验证平台/卷再读body，前端上传阶段独立于documentSession.saving，暂停autosave但持续草稿，成功仅合并新metadata/revision与当前body的一次链接，后续保存独立判断dirty，不把旧签名标为已保存。

普通上传全目录报告/预检/恢复/回收/明确放弃由document_attachment_http协议适配，未知先保留，无Agent依赖。completed墓碑先于快照DELETE，partial身份/SHA验证及实际DELETE先于预算释放；同UUID只回原结果。私人.workbench-document-uploads不进静态、业务搜索或ZIP，迁移未决拒绝；终结日志随本机目录迁移保留幂等。旧外部编辑器图片入口保持兼容，新metadata下载以受控原生句柄流式发送、主动内容强制下载及nosniff/sandbox。

asset_references只枚举白名单roots，扫描正式记录/文档/项目正文与meta、history及trash按原owner语义、在途manifest；共享任一有效引用保留，未知/损坏/别名报告并保守不删。document_export生成平铺MD及去重assets副本，解析metadata/body/现有附件token，严格成员/路径/链接校验和句柄流读；不修改源文件或创建新引用语法。

## AG-134 概念图条件写入与历史

ConceptMapRepository负责原JSON字节版本及PreparedConceptMapWrite；Repository只提供共享coordinated锁门面，HTTP负责expected_revision强制边界/400、404、409映射。原normalize仍是图的领域可信边界，create/update/分类迁移/历史恢复走同域实现，未开放Agent concept_map处理器。history.py扩展受控CMAP JSON快照，无第二索引、日志或自动恢复执行器；快照→目标两文件不是事务，失败后读取实际revision判断。

concept-map.js仍唯一画布控制器，统一持有base revision、本地编辑序号/保存Promise、撤销栈、冲突状态、同一个open请求世代及恢复中保护。app.setPage等待feature.leave成功后才改变路由；leave只在flush成功时使未决open失效。请求返回还核对世代/空间与等待期间的未保存内容；不会用迟到图覆盖当前画布。冲突选择与历史恢复复用既有对话框和API，草稿只恢复交互，不代替JSON；保存成功只推进base/保存序号，保留期间继续输入。

## AG-135图接点（已完成）

concept_maps仍是JSON归一化/Prepared/历史的唯一领域实现；新增纯prepare_create及可固定managed_time的prepare_update，预览不创建分类/正式图/历史。concept_map_ids为共享单调分配器，合并正式/历史/回收/全部提案证据；Repository注入库存并与既有RLock协调。config/concept-map-ids.json仅是分配游标，Agent预留仍只由唯一proposal原子记录绑定，不另建预留日志。

agent_concept_maps严格验证完整Agent候选、字节预算、稳定ID证明和受控读取；agent_concept_authorization承载独立新鲜图grant、资源集合依赖及本机管理预览批准/收窄；agent_concept_service组合既有领域准备与读写授权；agent_concept_execution仅提供静态concept_map@1的逻辑/具体计划、完整预览与JSON快照验证。它们接入原AgentService、ProposalStore、CredentialManager和HTTP/MCP适配，不复制CRUD或恢复状态机。新外层manifest3的execution_schema3与旧markdown@1/schema1及attachment@1/schema2静态分支并存；全量预检先于恢复/到期/清理的任何写入。

concept-map.js同一工厂新增readOnly选项：共享几何/节点/边markup，独立root和局部视口，pan/zoom只影响该实例；dispose中断root监听器、取消frame并清除DOM。原主画布全局事件忽略readonly根，键盘/粘贴还检查当前页面；主画布排队frame检查原current/open世代，主节点查询限主root。agent-proposals展示完整候选画布、全部字段/原图/差异/警告，成功加载同一proposal/version/digest后才启用本机批准，失败/关闭/切换/迟到结果清除旧前端许可。结果回调复用app.openItemLink及AG-134 leave/flush/open/request保护；不会通过新平行画布打开正式结果。

v2带edge.label的原自动拆边会改变Agent稳定身份，本项明确改为保留v2结构并用原标签编辑宿主显示/编辑；仅v1或历史缺version执行旧迁移，未来版本不迁移。图同ID回收恢复冲突409，其它资源原恢复策略保持。完整数据ZIP与迁移自然携带单调游标，私人Agent状态仍排除可移植ZIP。最终实现状态与验收证据以独立台账为准。

## AG-136 删除接点（已完成）

records/documents/concept_maps定位并产生deletion_prepared.PreparedDelete，由repository门面装配；它只核受控来源/身份/原字节及同NTFS句柄不覆盖移动，不自行管理事务。agent_delete_service生成完整服务端影响候选，deletion_inventory增量严格扫描活动全集，references复用既有引用识别并补知识库对info反链。HTTP仍只负责协议与严格回执链接，新增业务没有回填server.py。

独立agent_delete_authorization复用CredentialManager的快照/日志/围栏/幂等与管理会话。agent_delete_execution仅静态trash_delete@1计划/证据/步骤，恢复分支仍在唯一ProposalStore；不另建恢复循环或CRUD。原索引快照、NTFS身份、raw SHA、完整活动/排序/索引摘要一起约束移动；同句柄最终许可不复开被DELETE锁住的源。已移动只补原回执，不触碰后来出现的源。Repository守卫统一普通写/恢复/purge/清理，回收站读列表只展示保护，不产生恢复。

设置页复用既有范围组件和持久请求查询，提案页全量目标/引用原文与多个独立readonly概念图实例，全部ready且同版本/摘要才启用批准；关闭/切换/失败清除前端许可。结果导航走既有dirty/flush/leave链路，再定位原token；工厂/选择器隔离不写主图草稿或撤销。

## AG-137 项目创建（已完成）

projects 共享 README 序列化和 slug 分配；project_identity 核实际目录、回收、持久身份与显式范围，project_prepared 纯生成严格五字段、模板、项目集合及排序计划。普通创建仍用原领域入口和排序，但独占创建目录，不能接管残留。ConfigurationRepository 的纯排序归一化由普通写与 Agent 共用。

agent_project_execution 只提供静态 project_create@1 及阶段证据，状态循环、持久批准和回执仍由唯一 ProposalStore 管理。project_directory 复用原生句柄底座，目录叶能力仅内部使用，不扩展 Agent 任意文件读取；私人同卷暂存完整树后按同句柄无覆盖发布。agent_project_authorization 与 agent_project_access 复用 CredentialManager，项目访问独立检查原提交和当前客户端版本，保持目录及 README 句柄至 registry 发布。HTTP/MCP 层只做路由和受控链接返回。

## AG-138 项目级联删除

`project_delete_tree` 核验原始树与归属并复用 NTFS 目录句柄。`project_delete_impact` 在原有活动来源盘点中选择匹配影响，再检查全文读取权限。`agent_project_delete_service` 用同一逻辑准备候选及最终校验，`agent_project_delete_execution` 在唯一 ProposalStore 内提供静态 `project_trash@1` 执行步骤。项目、子资源、活动集合、排序和回收索引均绑定原计划。正常本机回收站操作复用已提交证据及目录原语恢复固定身份。

`agent_project_delete_authorization` 复用本机管理票据、CredentialManager 日志和客户端 CAS。浏览器复用授权管理流程、删除预览及概念图只读工厂。项目外关联图保留原 `project_id` 和原始字节。已有编辑器、历史和保存协议沿用现有路径。
