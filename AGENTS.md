# AGENTS.md — 本地工作台开发与重构规范

本文件是修改本仓库时必须遵守的执行规范。它同时约束日常维护和重构工作。

重构相关文档：

- 执行方案：[docs/REFACTORING_PLAN.md](docs/REFACTORING_PLAN.md)
- 进度台账：[docs/REFACTORING_PROGRESS.md](docs/REFACTORING_PROGRESS.md)
- 当前架构：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 数据格式：[docs/DATA_FORMAT.md](docs/DATA_FORMAT.md)
- 维护发布：[docs/MAINTENANCE.md](docs/MAINTENANCE.md)

AI Agent 功能文档（实现事实以台账与验收记录为准）：

- 实施方案：[docs/AI_AGENT_PLAN.md](docs/AI_AGENT_PLAN.md)
- 后续扩展方案：[docs/AI_AGENT_EXTENSION_PLAN.md](docs/AI_AGENT_EXTENSION_PLAN.md)（AG-116 起逐项实施；状态以台账为准）
- 本机能力扩展方案：[docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md](docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md)（AG-127 仅文档；当前状态以台账为准）
- 接入管理 UI 方案：[docs/AGENT_SETTINGS_PLAN.md](docs/AGENT_SETTINGS_PLAN.md)（实现状态以台账为准）
- 实施台账：[docs/AI_AGENT_PROGRESS.md](docs/AI_AGENT_PROGRESS.md)
- 接入与使用：[docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md)、[docs/AGENT_USAGE.md](docs/AGENT_USAGE.md)
- 验收记录：[docs/AI_AGENT_ACCEPTANCE.md](docs/AI_AGENT_ACCEPTANCE.md)
- 接入管理 UI 验收：[docs/AGENT_SETTINGS_ACCEPTANCE.md](docs/AGENT_SETTINGS_ACCEPTANCE.md)

规则优先级：数据安全与兼容性 → 用户明确需求 → 本文件 → 重构计划 → 邻近代码惯例。若文档和代码事实冲突，先记录冲突，再以不损坏已有数据的方式处理并同步文档。

## 1. 开始工作前

每次修改前必须：

1. 运行 `git status --short`，识别并保留用户已有修改。
2. 阅读任务涉及的代码、测试和文档，使用 `rg` 找齐字段、API、选择器和函数的读写点。
3. 判断任务是日常功能维护，还是重构方案中的 `RF-*` 工作项。
4. 若属于重构：先阅读执行方案对应工作项，并在进度台账把状态更新为 `进行中`。
5. 明确数据格式、API、草稿、历史、外部修改和 UI 的影响面后再编辑。

禁止在没有工作项编号和台账记录的情况下进行计划内重构。普通缺陷和功能修改不强制创建 `RF-*` 编号，但若实际改变模块边界、公共契约或重构顺序，必须登记。

## 2. 项目技术基线

- 单用户、本地优先，默认监听 `127.0.0.1:4173`。
- Python 标准库后端，原生 HTML/CSS/JavaScript 前端。
- 没有包管理器、运行时第三方依赖或构建步骤。
- Markdown 是项目、记录和知识库文档的事实源。
- JSON 用于配置、排序、回收站索引和概念图。
- DOM、JavaScript 全局状态和 `localStorage` 只属于交互层，不得成为唯一业务数据源。
- 已有本地文件必须保持可读。不得为了简化代码擅自删除旧格式兼容逻辑。

启动方式：

```powershell
python server.py --seed-demo
python server.py
python server.py --data-dir <一次性目录> --port 4174
```

测试或手工验收不得对真实 `workbench-data/` 执行迁移、清理、删除或压力测试。

## 3. 当前代码边界

- `server.py`
  - 只负责 CLI、旧进程替换、服务生命周期和兼容导出。
  - `server.Repository` 是保留动态 patch 点的轻量装配子类，不是领域实现位置。
- `workbench/`
  - `repository.py` 是组合门面；项目、记录、文档、概念图、附件和配置规则分别位于对应领域仓储。
  - `http_api.py` 只处理协议、路由和错误映射；Markdown、原子写、安全、路径和外部编辑器有独立基础模块。
  - 新业务规则进入领域仓储，不回填到 `server.py` 或 HTTP Handler。
- `index.html`
  - 页面、抽屉、对话框和工具栏的静态骨架。
  - 它是 CSS/JavaScript 加载顺序和 `?v=` 缓存版本的唯一事实源；`concept-map.js` 先定义工厂，`app.js` 最后装配。
- `app.js`
  - 负责模块装配、页面 DOM 适配和剩余跨功能协调；不得新增已由 `js/` 模块提供的平行实现。
- `js/core/`、`js/editor/`、`js/features/`
  - 分别承载核心浏览器服务、共享编辑器内核和功能模型/控制器，公开接口位于 `window.Workbench`。
  - 记录与知识库必须继续共享 Markdown、文档模型、结构块、选区和编辑器宿主。
- `concept-map.js`
  - 概念图的图库、画布、撤销重做、自动保存和导出。
  - 通过 `Workbench.conceptMap.create(...)` 接收 DOM、API、对话框和状态依赖；不要恢复对未声明词法全局的读取。
- `css/`
  - 按令牌、基础、组件、布局、业务功能和响应式拆分；所有媒体查询只进入 `responsive.css`。
  - 加载和断点顺序由 `index.html` 与 `test_styles.js` 锁定。
- `test_*.py`、`test*.js`
  - Python 测试覆盖仓储、HTTP、持久化、安全、Agent 提案恢复和 MCP；Node 契约包含真实浏览器保存/冲突/Agent 工作流。数量以实际测试发现为准。
  - `codex_agent_acceptance.py` 显式运行真实 Codex MCP 联调，使用隔离配置和临时数据，不启动模型 turn 或修改用户配置。
  - `visual_baseline.js` 和 `performance_acceptance.py` 是显式运行的视觉/大数据验收，不进入快速测试发现。
- `docs/`
  - 架构、数据格式、维护、验收基线、重构计划和进度记录；更新必须反映真实状态，不写预计结果。

当前实现事实见 `docs/ARCHITECTURE.md`；数据契约见 `docs/DATA_FORMAT.md`；发布步骤见 `docs/MAINTENANCE.md`。重构方案定义历史范围，不能用旧目标文件名覆盖当前代码事实。

## 4. 重构执行与记录

### 4.1 工作项状态

只使用以下状态：

- `待开始`
- `进行中`
- `受阻`
- `已完成`
- `已取消`

状态变化必须写入 `docs/REFACTORING_PROGRESS.md`。通常同一时间只主动推进一个高风险工作项；可以并行的文档或独立测试任务也必须分别记录。

### 4.2 开始工作项

在写代码前更新台账：

- 工作项状态和开始日期；
- 本次实施的精确范围；
- 预计修改文件；
- 计划运行的自动检查和手工验收；
- 已知风险或依赖。

### 4.3 完成工作项

标记 `已完成` 前必须在台账记录：

- 完成日期；
- 实际修改文件；
- 数据和 API 兼容影响；
- 自动检查命令及实际结果；
- 必要的手工验证结果；
- 新增或解除的风险；
- 关键决策编号；
- 遗留问题和下一工作项。

代码已编写但验证未完成时，状态仍为 `进行中`。只有明确的外部条件阻止继续推进时才标记 `受阻`，并写明解除条件。

### 4.4 范围控制

- 一个工作项只完成方案定义的一个边界。
- 纯移动代码时不改变业务行为、文案或视觉。
- 发现旁支缺陷时，能安全隔离就登记后继续；会影响当前正确性时增加测试并在台账说明范围变化。
- 不把框架迁移、模块拆分、UI 重设计和数据格式升级塞进同一工作项。
- 每个工作项都必须能独立回滚，不依赖清空用户数据。

## 5. 持久化与兼容契约

默认数据结构：

```text
workbench-data/
├─ config/
├─ projects/<project-id>/
│  ├─ README.md
│  ├─ issues/*.md
│  ├─ todos/*.md
│  ├─ ideas/*.md
│  ├─ infos/*.md
│  └─ assets/
├─ documents/*.md
├─ concept-maps/CMAP-*.json
├─ ideas/
├─ assets/
├─ history/
└─ .trash/
```

必须保持：

- 项目、记录、文档和概念图 ID 是稳定标识，不能随标题变化。
- `[[ID]]`、正文引用和附件引用依赖稳定 ID；调整语法需同时检查插入、渲染、反向链接、搜索和导入导出。
- front matter 使用项目自带的轻量解析器，不是完整 YAML。新类型必须经过读写往返测试。
- 写入保持 UTF-8、现有元数据语义和时间字段习惯。
- 数据格式升级采用兼容读取，不强制批量原地迁移。
- 记录缓存不能取代磁盘事实源；绕过现有写入方法时必须处理缓存失效。
- 删除默认进入 `.trash`；只有明确的永久删除流程可以不可恢复地删除。
- `settings.json` 和 `.workbench-*.json` 中的机器路径不得进入可移植数据或 Git。

## 6. 领域不变量

### 项目和记录

- `issue`、`todo`、`info` 必须属于项目。
- `idea` 仅为历史兼容，当前 UI 和普通新建流程不得重新暴露。
- 状态来自工作流模板；状态重命名需迁移使用方，使用中的状态和标签不得直接删除。
- 拖放排序必须写回持久配置，不能只改变 DOM。

### 结构化信息

- `info` 无状态，使用一个有序 `info_fields` 列表。
- 不创建 command 子类型或命令专用平行编辑器。
- `name` 是说明，`value` 可包含多行文本/命令，`note` 可选。
- 创建、编辑、草稿、历史、导入和重载都要保留字段顺序、换行、引号和空格。
- 应用只允许复制字段内容，永远不得执行记录中的命令。

### 知识库

- 文档只有分类，没有第二套文档类型。
- 空分类、分类顺序和分类内文档顺序必须独立持久化。
- 分类重命名需迁移文档和排序；删除分类只把文档移到“未分类”。

### 概念图

- 概念图持久化为 JSON，服务端归一化是可信边界。
- 保持版本、节点/边 ID、节点类型、箭头和视口语义。
- 不得无测试放宽节点数量、边数量、文本、坐标、尺寸、颜色和缩放限制。
- 自动保存、关闭前 flush、撤销重做和原子写入必须一起验证。

- AG-134新增原JSON字节revision、Prepared条件写入及history/CMAP-ID/*.json原字节历史；HTTP已有图PATCH/历史恢复必须expected_revision，缺失409提示刷新以阻止旧缓存覆盖。Python省略版本仅服务锁内兼容。未知未来version拒写/恢复；历史全部保留、无自动重放/清理，失败后查询实际版本，不称多文件事务。画布冲突保留输入/撤销及草稿，明确选择后再CAS；成功flush才接受离开并失效同一open世代，迟到请求不能覆盖新图。详见数据格式/维护及134验收；该阶段未开放Agent概念图，135接点见下条。
- AG-135已完成：新鲜concept_map_grants独立批准，registry4/auth5/log5；旧休眠/通配不扩权，其它管理家族和撤销/轮换保留新字段/格式下界。22工具含图list/get，写入仅完整create/update和既有提案两确认；原图/全部节点关系/元数据/布局/差异/警告与执行依据完整展示，禁止以缩略图或片段替代。唯一ProposalStore、concept_map@1与manifest3/execution_schema3复用同域Prepared/JSON历史，历史已落但图未发布仍重查权限；after及必要history证明后只补原回执，未知/缺历史/第三方状态保留，create applying目标缺失不重建。config/concept-map-ids.json为共享单调分配游标，真正领取才写；Agent身份仍由唯一原子proposal绑定并在取消/过期/清理后保留墓碑。坏占用/游标停止分配，完整ZIP/迁移保留；人为删除/部分恢复及旧进程忽略游标不保证无证据ID不复用。readonly通过同一工厂及共享渲染、root隔离与dispose，不写主画布/草稿/撤销；全量画布/明细载入失败或版本切换禁止批准，票据不证明人眼阅读。v2 label保留原ID/结构，自动迁移仅v1/历史缺version，未来版不迁移；图同ID恢复409，其它类型原策略不变。最终状态/范围以135台账验收为准；136状态见独立台账。

### 附件与导入导出

- 大附件继续使用流式上传，不能退回整文件 JSON/base64。
- 拼接后的路径必须位于预期数据目录内。
- 不信任 ZIP 内路径、上传文件名、分类名或导出名。
- 记录附件和项目独立附件索引不同，不得混用。
- 孤儿清理只能删除确认无引用的文件。
- 外部编辑器使用参数数组启动，不拼接 shell 命令。

## 7. 编辑器与 Markdown 契约

记录编辑器和知识库编辑器必须共享同一套渲染、归一化、文档模型和序列化能力。

```text
Markdown
→ markdownToHtml
→ hydrateEditorBlocks
→ 编辑器 DOM
→ editorToDocumentModel
→ documentModelToMarkdown
→ 保存并重新加载
```

规则：

- 段落、标题、列表、任务列表、引用、代码块、分隔线和表格都是结构块。
- 结构块应是编辑器直接子节点。
- 禁止用 `execCommand('insertHTML')` 插入列表、任务项、表格、引用或代码块。
- 标准 Markdown 能无损表达时优先使用标准 Markdown。
- 行内扩展只能使用受控 HTML 白名单。
- 代码高亮 DOM 不能污染保存内容，语言和原始代码必须保留。
- 新增块类型必须同时覆盖渲染、识别、模型、序列化、光标、两个编辑器、阅读模式和保存重开。
- 阅读模式不得出现编辑控件，默认可视化模式不得暴露 Markdown 标记。

## 8. 保存、草稿、历史和外部修改

- 记录和文档分别维护 dirty、saving、timer 和草稿状态。
- 保存成功后才能清理草稿并更新签名/mtime；失败时保留用户输入。
- 外部文件冲突必须允许选择磁盘版、工作台版或合并结果，禁止静默覆盖。
- 15 秒轮询异常时保留当前内容，等待下次重试。
- `beforeunload` keepalive 只是最后保障，不是主保存机制。
- 修改保存链路时必须验证关闭、切页、刷新、草稿恢复、外部编辑和冲突。

## 9. 后端与 HTTP 规范

- 业务规则进入仓储或领域模块，HTTP 层只负责协议转换和错误映射。
- API 至少正确区分 `400`、`404`、适用时的 `409` 和未处理的 `500`。
- 路径参数必须在前后端对称编码/解码。
- JSON 调用复用统一 API 客户端；上传和下载使用明确的字节流处理。
- 新端点同时修改仓储、路由、前端调用、错误提示和测试。
- 配置变更必须提供默认值和旧格式兼容读取。
- 服务端是最终校验边界，前端限制不能替代服务端校验。

### 9.1 通用 AI Agent 接入约束

- 接入设置按 `docs/AGENT_SETTINGS_PLAN.md` 的 AG-107～111 及台账维护。管理路由仅 loopback 同源管理会话，不加入 MCP 工具；Agent 凭据不能扩权、启停或读取私人配置。状态读取不得初始化空间。
- CLI/UI 凭据管理复用同一持久日志与跨进程锁；完成后清除凭据快照，未决操作按 report/abandon 恢复，不删除日志绕过。分类重命名/删除需同步授权，失败保持收窄，禁止扩大到未分类。
- 固定诊断在业务锁外等待子进程/HTTP，必须限制时间/输出并回收进程；自检 nonce 不能出现在页面/日志。握手、自检与普通客户端请求分层表达，不能宣称证明当前聊天在线。管理 UI 回归运行 `node test_agent_settings.js`。

- 后续类型、网页批准、提案管理、客户端兼容和远程接入按 `docs/AI_AGENT_EXTENSION_PLAN.md` 逐项实施；规划不等于开工授权。旧凭据不得自动获得新增类型；网页批准不接受 Agent 自报替代；远程入口不得暴露本机管理 API。
- 2026-11-09 本机能力扩展按 `docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md` 登记 AG-127～143。用户已于2026-11-09明确“现在开始执行方案”；AG-128授权基础已完成，后续按依赖交接，历史暂停记录保留。文件读取、附件、概念图、删除、项目创建和分类/工作流配置的拟定契约不是现有能力；下文及旧方案的历史接口限制继续生效，只有相应工作项获后续指令并实现、验收和同步工具规则后才可按新增范围开放。
- AG-128仅提供严格休眠授权配置；configured不能视为implemented/effective。新增能力首次启用必须管理员重新授权，不能随处理器上线自动激活。历史根registry2/授权3/管理日志3/transport2及AG-130新门槛见DATA_FORMAT；失败、abandon及清空grants不能降版，不以删日志回退。文件采用AG-130独立逐文件批准，其余后续业务操作仍未开放。
- AG-129新proposal3绑定授权/相关依赖及保存计划，manifest3内execution_schema1为markdown@1，AG-132新增execution_schema2/attachment@1；旧1/2按原摘要恢复。未知步骤/算法/批准格式先零写预检，正文未发布即使历史已落也重查权限；已发布只补原回执。新增处理器须版本化，不改变旧语义或提前激活休眠授权。
- AG-130仅具体文件授权：管理会话完整属性预览后明确批准才可hash，source path不接受Agent提供；授权4 active_file_ids与私人file-grants交集，其他grants继续休眠。支持Windows固定NTFS普通文件，拒重解析/所有多硬链接/SUBST/特殊路径/私人配置；长I/O及socket发送不持业务/凭据/换库锁，发布前短锁重验。每段同遍完整hash与片段捕获，按source_revision/原始字节续读；附件来源仅意向，不开放上传。root3/log4/transport2、快照终结后清理、剩余等待及迟到许可语义见DATA_FORMAT与维护文档。
- AG-131暂存独立uploads.stage策略需管理完整预览/批准，read及既有目标范围不变，旧附件来源/休眠grants不生效；policy绑定批准后client_version，变更即失效。19工具中的新4项只控制私人暂存，正式附件/绑定消费留132/133。声明长度预留与真实bytes/SHA、sealed/磁盘证据、目标/权限结束复验必须共存；原始流仅固定loopback octet-stream，拒TE/重复CL，余body关闭。长流/hash锁外，短目录锁共同保护配额统计、rename/DELETE句柄实际删除/removed发布；未知对象、在途、已绑定/消费保护不清理，失败预算不提前释放，墓碑保留幂等但不占活跃数。具体版本/恢复/限制见DATA_FORMAT。
- AG-132正式附件仅既有project/issue/todo/info的attachment/create，共同policy2须完整本机预览批准，旧stage/schema1/dormant不扩权；双方绑定同一批准后client_version。先共同批准再建新ready，不迁移旧ready。唯一ProposalStore及领域Prepared接口，确认/固定名与计划先落manifest再锁外copy/hash；session引用镜像缺口各入口保护，消费ID严格映射原操作。最终同句柄不覆盖rename，metadata仍before重查权限，after只补原回执。完整committed回执证明后才可退休源并释放预算，未知/在途不清理；AG-133扩展知识库附件，范围与证据见对应台账。正文只保留原body或公共助手追加链接，服务端时间明确占位后在受理确认时定稿；共享Markdown文件名转义/URL及两个编辑器往返必须验证。
- AG-133文档附件事实源仅文档front matter的有序attachments列表，path相对原documents文件指向全局assets/images或assets/files，category为原文档分类。普通网页上传独立于Agent授权，长流锁外、稳定UUID先存后查、Prepared领域计划及操作证据恢复；不能用上传响应正文覆盖当前输入。私人.workbench-document-uploads不是业务索引，不进入静态或可移植ZIP；终结保留幂等墓碑，先证明真实删除才释放预算。孤儿识别覆盖正文、历史原owner目录、回收站与在途，未知保守保留并报告。ZIP只改导出副本路径和附件元数据，不写回正式Markdown。文档仍只有分类，134以后不在133范围。
- AG-136删除接点：独立新鲜delete_grants/schema1，仅items.delete/delete/local_web；registry5/auth6/log6，旧休眠不激活，其他家族保留全部字段/格式下界。只开放issue/todo/info/document/concept_map单条移入回收站，无Agent恢复/purge/项目级联。完整目标/匹配活动来源/附件元数据/原图全字段预览，单文件1MiB、实际UTF8 JSON预览2MiB、活动集合4096文件/32MiB；有权读取且有删除许可才可执行，无权命中通用拒绝不泄露详情。唯一ProposalStore/trash_delete@1/execution4，manifest及原索引快照先落；同一NTFS句柄最后重验后不覆盖rename，原trash身份/字节证明后只补原索引/cache/receipt。移动中但trash缺失不重删恢复源，不从快照重建；committed重放只回原回执。索引/排序为保守依赖，排序ID/位置、历史、共享附件保留。全局在途保护涵盖普通恢复/purge/cleanup/孤儿清理；abandon接受盘态而非回滚，残留仍保护。已完成完整目录迁移须匹配私人配置/日志，ZIP不含删除事务。实现和验收状态以136台账为准，137以后不开始。
- AG-137项目创建接点：独立新鲜project_create_grant/schema1，registry6/auth7/log7，transport2及旧家族语义保留。仅project/create五字段/已存在模板/固定ID/强制local_web；普通创建和Agent共享残留/回收/预留/显式范围占用，不能接管。完整项目及排序规则对Agent可见，本机完整前后排序，未授权他项不泄露。唯一ProposalStore/project_create@1/execution5，先批准和原字节快照/manifest，再同卷私有暂存，以同NTFS目录句柄无覆盖发布；只有原目录与完整树证明才续办固定排序/回执，不重发不覆盖异物。访问授权由本机再次完整预览批准，独立CredentialManager CAS及原回执/目录/README证据，只追加一个精确项目范围，既有通配照旧，不由Agent内容启用。项目成功与授权失败分别查询。状态以137台账为准。
- Agent 功能按 `docs/AI_AGENT_PLAN.md` 的 `AG-*` 工作项实施；开工和完成必须更新独立台账，不改写已完成 RF 工作项的历史状态。超出已登记边界的重构另行登记。
- AG-138 项目级联删除使用独立 `project_delete_grants` schema1、registry7/auth8/log8。旧授权家族与格式下界保留，休眠授权不激活。必须有原项目读取、各实际子记录独立读删及逐个独立附件批准。本机完整预览项目及子目录、附件、影响和保留归属的关联图。外部活动附件引用、历史 idea 或未知树成员使整案拒绝。唯一 ProposalStore 的 `project_trash@1`/execution6 在同 NTFS 目录句柄无覆盖移动前后核验原树。未知盘态保留，已应用证据只补原索引、缓存和回执。回收 schema2 原 ID 固定，恢复碰撞 409，子 ID 永久占用。备份、在途保护和验收见数据格式、维护和台账。
- 业务接口不得绑定 Codex、特定模型或聊天 ID。MCP 是协议适配层，必须调用工作台服务，不直接写业务文件或另建 Repository 进程。
- 整理入库的日志证据按 docs/AGENT_USAGE.md：关键原文摘录至正文代码块，保留必要时间/错误码/上下文并脱敏，省略明确标注，区分事实与推测。外部日志路径仅作来源补充；确认文件已存工作台时才可引用已有文件/附件，关键片段仍优先入正文。未取得原文须标注待补充，不补造摘录或附件链接；维护时同步 MCP 的 AGENT_RULES，不能只依赖本文件约束其他客户端。
- 正式新建、追加、更新均须先生成服务端提案和完整预览，用户明确确认当前版本后提交。提交只接受提案版本和摘要，不接受临时替换正文；修改内容必须重新预览、确认。
- agent_attested 采用对话内确认，由 Agent 声明确认结果；local_web 必须在本机管理会话完整预览后独立批准，不能被自报确认绕过。两者均不得描述为现实人类身份认证。仓库规则不能替代对其他 Agent 的工具说明和接入指引。
- Agent 提案与网页编辑器草稿、正式 Markdown 分离；不得提前创建正式条目作为预览，不把提案加入业务搜索、反向链接或普通导出。
- 复用领域校验、Markdown 序列化、历史和原子写。预览与提交复用同一归一化逻辑，不在桥接器建立平行 CRUD。
- Agent 更新强制检查内容版本，当前网页保存同步接入版本检查和冲突处理。服务内写入使用共享协调；文档历史、ID 并发和文件系统剩余竞态必须有测试及明确说明。
- 提交必须有持久幂等回执和崩溃恢复设计；禁止用内存去重或单个文件原子替换宣称多文件事务安全。发生不确定落盘先查询/恢复，不重新创建。
- 第一版只暴露方案允许的类型与操作，不暴露删除、任意文件路径、shell、命令执行、通用 HTTP 代理或跳过预览的写入工具。
- 凭据、权限、工作空间身份和访问范围由服务端校验；不能信任调用方自报 client_id。本机凭据不能进入静态目录、工具返回、日志、Git 或可移植备份。
- 启用接入前完成静态资源访问边界核查。MCP stdout 只能输出协议消息；只声明实测支持的协议版本和能力，不擅自增加运行时依赖。
- 网页修改本机 Codex 登记必须先展示目标配置/完整新项并明确确认；同名差异需改名或显式替换。只调用服务确定的固定可执行文件和参数，不接受路径/shell。候选在隔离 CODEX_HOME 生成并校验、原配置私人备份、版本复查及持久回执缺一不可；不确定先查询，不重放或静默回滚。验收只用临时 CODEX_HOME，不能修改真实用户配置。
- 测试必须覆盖完整预览、取消、旧版本确认、越权、并发、重复提交和落盘各阶段失败恢复。真实 Codex 验收使用一次性数据目录，未经验证不得标记接入完成。

## 10. 前端规范

- 保持 2 空格缩进、单引号、`camelCase` 和原生浏览器 API。
- 重构第一轮使用显式 `window.Workbench` 命名空间，不擅自引入框架或构建链。
- 来自 API、文件或用户的数据进入 HTML 前必须 `escapeHtml`，颜色必须经过 `safeColor` 或等价白名单。
- 异步结果落地前确认请求对象仍是当前记录、文档或项目。
- render 会替换 DOM 时，事件绑定到稳定祖先或明确清理旧监听器。
- `localStorage` 键是兼容接口，重命名需要迁移旧键。
- 修改 JS/CSS 后更新 `index.html` 对应资源的 `?v=` 缓存版本。
- 用户文案保持现有简体中文术语、语气和按钮层级。

## 11. CSS 与视觉规范

- 优先使用既有 CSS 变量和组件类，不新增等价的一次性变体。
- 修改选择器前搜索所有定义、动态模板和 `classList` 使用。
- CSS 拆分保持原加载和级联顺序，先验证再删除旧规则。
- UI 修改至少验证浅色/深色、桌面/窄屏、hover/focus/disabled/error、长中文、空数据和大量数据。
- 不能只用颜色传递状态；控件需有文字、图标或无障碍标签。
- 视觉截图用于评审，不提交 `preview*.png`。

## 12. 测试与验收

基础门禁：

```powershell
python -m unittest -v
python -m py_compile server.py test_server.py
node --check app.js
node --check concept-map.js
git diff --check
```

新增文件后扩展命令覆盖所有 Python 和 JavaScript 文件。

测试要求：

- 文件系统测试使用 `tempfile.TemporaryDirectory()`。
- 同时覆盖成功、校验失败、缺失资源和旧格式。
- 写入测试必须重新读取或重新实例化仓储，证明真正持久化。
- 缓存、并发、外部修改、路径和流式上传不能只验证内存返回值。
- UI 变更必须运行服务完成浏览器验收；当前仓储测试不能替代 UI 验收。
- 编辑器变更必须在记录和知识库各完成一次可视化 → Markdown → 保存 → 重开。

安全的手工环境：

```powershell
$testData = Join-Path $env:TEMP ("workbench-agent-" + [guid]::NewGuid())
python server.py --data-dir $testData --seed-demo --port 4174
```

## 13. 文档与 Git

- 重构计划定义范围，进度台账记录事实，二者不得互相替代。
- 功能、命令或用户可见目录变化时更新 `README.md`。
- 架构、契约或执行规则变化时更新本文件和必要的重构文档。
- 不提交 `workbench-data/`、`.workbench-*.json`、`preview*.png`、缓存、日志、个人附件、导出包或绝对机器路径。

### 13.1 本地提交规则

- 一次完整、可独立验证的逻辑修改在完成并通过相应检查后，必须形成一笔本地 Git 提交；用户明确要求暂不提交时除外。
- “一次完整修改”是一个缺陷修复、一个小型功能、一个文档治理变更，或一个可独立验收的 `RF-*` 工作项/子项，不是每次文件编辑。
- 较小的 `RF-*` 工作项原则上对应一笔提交。较大的工作项可以拆成多笔提交，但每笔都必须保持应用可运行、已有数据可读且相关测试通过。
- 纯重构、保护性测试、用户可见功能和无关格式整理应分开提交；测试若直接证明同一修复或重构行为，可以与实现放在同一提交。
- 重构代码与该工作项的进度台账更新应放在同一笔提交中，确保提交本身包含真实状态和验证证据。
- 不使用无法运行、未完成验证的 WIP 提交作为工作项终点。需要跨提交推进时，在台账中保持 `进行中`，直到最终验收提交完成。
- 提交前必须检查 `git status --short`、目标 diff 和 `git diff --check`，确认没有夹带用户既有修改、运行数据、缓存、日志、预览图或机器配置。
- 不修改、合并、重写、rebase 或 amend 用户已有提交，除非用户明确要求。
- 提交标题使用简短的祈使式英文，例如 `Extract Markdown persistence helpers`。
- 重构提交正文建议记录工作项、主要变化和验证命令，例如：

```text
Work item: RF-101

- Extract Markdown parsing and serialization helpers
- Preserve existing Repository behavior

Verification:
- python -m unittest -v
- python -m py_compile server.py test_server.py
```

## 14. 完成标准

任何修改交付前必须确认：

- 数据和 API 兼容影响已经说明；
- 成功、失败和重新加载路径已经验证；
- 相关自动检查通过；
- UI 影响完成必要的主题和宽度验证；
- 没有形成第二套编辑器、仓储、API 或组件实现；
- 缓存版本和相关文档已同步；
- 若属于重构，进度台账已记录真实状态和验证证据；
- 最终 diff 不包含本地数据、生成物、无关格式化或用户既有修改。

后续扩展的本机成果、外部阻塞与最终恢复入口见[扩展验收](docs/AI_AGENT_EXTENSION_ACCEPTANCE.md)；仅本机阶段通过不能声明AG-116～126全部完成。

2026-11-06用户范围更新：当前仅单机本地接入，AG-122～125已取消实施；远程设计保留为历史参考，不再作为当前授权或交付前置。AG-121本机非Codex兼容范围须单独按用户需求确认。
