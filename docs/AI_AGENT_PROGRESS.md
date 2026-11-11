# 通用 AI Agent 接入进度台账

最后更新：2026-11-10。

方案：[AI_AGENT_PLAN.md](AI_AGENT_PLAN.md)。执行规范：[AGENTS.md](../AGENTS.md)。本台账只记录 AG-* 新功能；原重构台账继续保留历史事实。

接入管理 UI 的需求、契约及验收分解见 [AGENT_SETTINGS_PLAN.md](AGENT_SETTINGS_PLAN.md)。AG-106 为文档工作；AG-107～111 的实施事实和当前状态见下表及记录。

后续扩展详见 [AI_AGENT_EXTENSION_PLAN.md](AI_AGENT_EXTENSION_PLAN.md)。AG-115仅文档；AG-116～121、AG-126已完成；用户已明确仅本机使用，AG-122～125已取消当前实施、远程未实现。当前WorkBuddy5.9.3与本机最终交付证据见末尾及扩展验收，不影响首期历史状态。

2026-11-09 用户在监督对话明确“现在开始执行方案”，解除此前暂停实施限制。AG-128～130及独立POST锁修复已通过监督审查，AG-131已通过监督审查，AG-132已通过监督审查，AG-133已通过监督审查，AG-134已提交9e43aa3并获监督接受，AG-135～136已完成。2026-11-10 用户明确“继续持续的推进方案”，AG-137～141 已完成，AG-142 进行中，AG-143 待开始。历史 AG-127 的仅文档授权和暂停事实保留。

## 工作项

| ID | 范围 | 状态 | 开始 | 完成 | 依赖 |
| --- | --- | --- | --- | --- | --- |
| AG-000 | 需求、方案和执行规范 | 已完成 | 2026-11-03 | 2026-11-03 | 用户已确认 Codex 优先、每次预览、通用接口 |
| AG-101 | 写入协调、版本检查与文档历史 | 已完成 | 2026-11-03 | 2026-11-03 | AG-000 |
| AG-102 | 认证、访问边界与只读 API | 已完成 | 2026-11-03 | 2026-11-04 | AG-101 |
| AG-103 | 提案、确认提交、幂等与恢复 | 已完成 | 2026-11-04 | 2026-11-04 | AG-102 |
| AG-104 | MCP 适配与 Codex 联调 | 已完成 | 2026-11-04 | 2026-11-04 | AG-103 |
| AG-105 | 深链接、全流程验收与发布 | 已完成 | 2026-11-04 | 2026-11-04 | AG-104 |
| AG-106 | 接入管理 UI 需求、契约与实施方案 | 已完成 | 2026-11-04 | 2026-11-04 | AG-105；本轮仅文档 |
| AG-107 | 启用偏好、运行时切换与管理接口保护 | 已完成 | 2026-11-04 | 2026-11-04 | AG-106 |
| AG-108 | 客户端管理、授权变更与凭据恢复 | 已完成 | 2026-11-04 | 2026-11-04 | AG-107 |
| AG-109 | 设置 UI 与 Codex 配置向导 | 已完成 | 2026-11-04 | 2026-11-04 | AG-108 |
| AG-110 | 分层诊断与真实客户端验收 | 已完成 | 2026-11-04 | 2026-11-04 | AG-109 |
| AG-111 | 兼容回归、维护文档与交付验收 | 已完成 | 2026-11-04 | 2026-11-04 | AG-110 |
| AG-112 | CMD/PowerShell 向导与 Codex 非 PATH 检测修复 | 已完成 | 2026-11-04 | 2026-11-04 | AG-111；用户实机反馈 |
| AG-113 | 网页预览确认、一键登记 Codex 与结果恢复 | 已完成 | 2026-11-04 | 2026-11-04 | AG-112；用户明确授权 |
| AG-114 | 入库关键日志摘录与来源引用规范 | 已完成 | 2026-11-04 | 2026-11-04 | 用户明确要求 |
| AG-115 | 后续扩展详细方案与工作项登记（仅文档） | 已完成 | 2026-11-06 | 2026-11-06 | 用户要求先完善方案，不修改代码 |
| AG-116 | 类型授权、能力协商与流程格式兼容 | 已完成 | 2026-11-06 | 2026-11-06 | AG-115；用户已授权实施 |
| AG-117 | 待办 todo 查询、提案与持久写入 | 已完成 | 2026-11-06 | 2026-11-06 | AG-116 |
| AG-118 | 结构化信息 info 与字段无损往返 | 已完成 | 2026-11-06 | 2026-11-06 | AG-117 |
| AG-119 | 本机提案管理、预览、取消与结果查询 | 已完成 | 2026-11-06 | 2026-11-06 | AG-118 |
| AG-120 | 网页独立批准与持久恢复 | 已完成 | 2026-11-06 | 2026-11-06 | AG-119 |
| AG-121 | 非 Codex 真实客户端兼容验证 | 已完成 | 2026-11-06 | 2026-11-07 | AG-120；WorkBuddy5.9.3真实本机矩阵 |
| AG-122 | 远程 MCP 协议、认证及部署设计门槛 | 已取消 | 2026-11-06 | — | AG-120；需目标身份服务/客户端 |
| AG-123 | 远程身份授权、主体映射与网络入口 | 已取消 | — | — | AG-122门槛；用户已授权实施 |
| AG-124 | 远程 MCP 传输与会话适配 | 已取消 | — | — | AG-123 |
| AG-125 | 真实远程拓扑验收与停用维护 | 已取消 | — | — | AG-124、AG-121 |
| AG-126 | 本机兼容回归、文档与交付验收 | 已完成 | 2026-11-06 | 2026-11-07 | AG-117～121；远程项已取消 |
| AG-127 | 本机能力扩展详细方案与执行登记（仅文档） | 已完成 | 2026-11-09 | 2026-11-09 | 用户要求写入方案，暂不执行功能开发 |
| AG-128 | 新能力授权、管理 UI/CLI 与能力协商 | 已完成 | 2026-11-09 | 2026-11-09 | AG-127；用户已授权执行 |
| AG-129 | 新提案格式与多步骤持久恢复基础 | 已完成 | 2026-11-09 | 2026-11-09 | AG-128；监督已接受f6463db并派发 |
| AG-130 | 本机文件授权与分段读取 | 已完成 | 2026-11-09 | 2026-11-09 | AG-128；具体文件独立批准，Windows固定NTFS |
| AG-131 | 流式暂存、上传会话、配额与清理 | 已完成 | 2026-11-09 | 2026-11-09 | AG-129；监督接受eeeaf86后派发；实际结果见末节 |
| AG-132 | 记录与项目附件提案入库 | 已完成 | 2026-11-09 | 2026-11-09 | AG-130、131；监督接受b7ce3fe后派发；实际结果见末节 |
| AG-133 | 知识库附件领域能力与网页接入 | 已完成 | 2026-11-09 | 2026-11-09 | AG-131、132；监督接受6c28f12后派发；实测见末节 |
| AG-134 | 概念图版本、历史与准备写入 | 已完成 | 2026-11-09 | 2026-11-10 | AG-129；监督接受e0a5a88后派发 |
| AG-135 | 概念图 Agent 提案与完整预览 | 已完成 | 2026-11-10 | 2026-11-10 | AG-128、134；新鲜授权/唯一提案/22工具/完整预览；433Python、23Node分批及隔离Codex通过；决策047/048 |
| AG-136 | 条目删除与回收站持久恢复 | 已完成 | 2026-11-10 | 2026-11-10 | AG-129、135；完整删除预览/强制网页批准/原回执及恢复保护验收完成；后续暂停 |
| AG-137 | 项目创建、排序与可选独立授权 | 已完成 | 2026-11-10 | 2026-11-10 | AG-129；同卷目录发布、排序和独立范围授权已验收 |
| AG-138 | 项目级联删除 | 已完成 | 2026-11-10 | 2026-11-10 | AG-136、137。独立授权、本机批准、固定目录移动及恢复，验收见分册 |
| AG-139 | 三类分类变更与授权迁移 | 已完成 | 2026-11-10 | 2026-11-10 | AG-129、133、135。三类分类命令、身份代次及授权迁移已验收 |
| AG-140 | 工作流变更、状态迁移与模板切换 | 已完成 | 2026-11-10 | 2026-11-10 | AG-129、137。工作流许可、状态映射及恢复已验收 |
| AG-141 | 提案管理、恢复入口与诊断整体验收 | 已完成 | 2026-11-10 | 2026-11-10 | AG-132～140 |
| AG-142 | 新能力真实 Codex、WorkBuddy 兼容验收 | 进行中 | 2026-11-10 | — | AG-141；真实客户端环境 |
| AG-143 | 新能力兼容、备份、运维与最终交付 | 待开始 | — | — | AG-142 |

状态只使用：待开始、进行中、受阻、已完成、已取消。每项开工记录精确范围、文件、检查和风险；完成记录实际结果、兼容影响和剩余问题。代码写完但未验证仍为进行中。

## 执行记录

### 2026-11-09 / AG-128 / 开始

- 授权：已直接读取监督对话中用户“现在开始执行方案”；HEAD ba24e37，git status --short 干净。普通 Agent 功能项，不改变 RF 历史。
- 范围：严格休眠 capability_grants、独立客户端、三层能力协商、管理 UI/CLI、目录元数据隔离、凭据格式门槛与恢复；不实现 AG-129～143 业务工具、不接管真实客户端。
- 预计文件：agent_security/management/service/tools、server、agent-settings、index、http_api 版本；新增授权测试及扩展管理/HTTP/MCP/浏览器测试；方案、架构、格式、接入使用维护、README/AGENTS 与本台账。
- 检查计划：专项及全量 unittest、全 Python/JS 语法、相关 Node（含设置真实浏览器浅深×桌面窄屏）、各持久阶段异常/进程退出及旧版本拒绝、git diff --check；全部使用临时库和隔离配置。
- 风险：旧日志盲恢复、注册表降级、部分落盘、名称复用及休眠授权意外激活、catalog 全局标签泄露。先记录 AG-LOCAL-DEC-009～012 与严格契约，再实施；测试实际完成前不标通过。

### 2026-11-09 / AG-127 / 开始

- 分类：Agent 功能规划文档治理，不是 RF 重构；用户要求将六类能力方案写入执行文档，明确暂不执行、等待执行指令。
- 范围：附件上传、本机文件读取、概念图、删除、创建项目、分类和工作流配置的契约、权限、恢复、分期及验收；登记 AG-128～143 待开始，不启动实现或真实客户端任务。
- 预计文件：新增 docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md；同步本台账、主方案、上一扩展分册、README、AGENTS、接入与使用指引、维护入口。
- 前置核查：git status --short 干净；已检查 agent_service/agent_tools/agent_http/agent_proposals/security/management、assets/concept_maps/projects/configuration/repository 和架构、格式、最终扩展验收；rg 未发现 AG-127～143 已占用。
- 已知文档冲突：README 的 AG-116～126 尚未开始描述与最终台账冲突，本次修正当前摘要；旧方案的首期排除项保留历史含义，以新分册说明未来范围。
- 影响：仅文档；不修改业务 Markdown/JSON、运行时代码、公共 API、凭据、草稿、历史、资源缓存或 APP_VERSION，不读取用户文件或创建测试授权。
- 计划检查：目标 diff、文档 UTF-8/围栏/本地链接、17 项状态与依赖一致性、git diff --check；本次不运行业务、浏览器和真实客户端验收，不沿用旧结果证明新功能。
- 风险：本机路径跳转、源文件替换、敏感内容披露、多文件部分落盘、授权迁移及网页保存冲突均须留至实施项实测；所有拟定接口和限额不得标成现状。

### 2026-11-09 / AG-127 / 完成

- 实际文件：新增 docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md；更新 AI_AGENT_PROGRESS、AI_AGENT_PLAN、AI_AGENT_EXTENSION_PLAN、AGENT_INTEGRATION、AGENT_USAGE、MAINTENANCE、README 和 AGENTS，共 9 个 Markdown 文件。
- 交付：六类能力的范围/排除项、独立授权/确认策略、旧凭据兼容、新提案和持久恢复、具体文件授权、流式暂存、三类附件、概念图版本/冲突、回收站、项目创建/级联、分类/工作流迁移、HTTP/MCP/前端、17 项工作分解及验收/回滚/等待入口。AG-128～143 保持待开始，不写入开始日期。
- 规划细化：AG-136 比初始对话方案补充 AG-135 依赖，以保证概念图删除接点就绪；实际路径输入与浏览器上传分开，原始字节流与普通 stdio 客户端能力分别验收；待验证技术项明确记录，未伪称实现。
- 验证：Python 内联文档检查实际验证 9 文件 UTF-8、围栏、81 个本地链接、17 项登记/依赖/范围/等待边界和 README 旧摘要修正，通过；人工审阅目标 diff 与新分册；git diff --check 通过。文档状态收口后再次检查全部新工作项与链接；纯文档不运行应用测试、浏览器或模型/真实客户端任务，不引用旧数量作为新验收。
- 兼容影响：无运行时代码、公共 API、业务 Markdown/JSON、私人凭据、草稿、历史、APP_VERSION 或资源缓存变化；未读取用户源文件、启动服务、生成授权或修改真实配置，无数据迁移。
- 决策/风险：登记 AG-LOCAL-DEC-001～008；未解除文件身份、暂存限额、知识库序列化、图保存冲突及多文件授权迁移等实施风险，分别由后续项验证。
- 后续：本次仅规划文档已完成；等待用户执行指令，通常从 AG-128 开始。AG-127 完成和文档本地提交均不构成 AG-128～143 开工授权，不修改 AG-000～126 历史状态。

### 2026-11-06 / AG-115 / 开始

- 分类：Agent 功能规划文档治理，不是 RF 重构；仅制定后续方案，不启动功能开发或接入真实服务。
- 范围：todo/info、网页独立批准、提案管理页、其他 Agent 兼容验收、远程 MCP 的分期契约、依赖、风险、兼容及验收；登记独立待开始工作项。
- 预计文件：新增 docs/AI_AGENT_EXTENSION_PLAN.md；更新 AI_AGENT_PLAN/AI_AGENT_PROGRESS、AGENT_SETTINGS_PLAN、README 和 AGENTS 文档入口与范围说明。
- 前置核查：git status --short 干净；已读取主方案、设置方案、台账、架构、数据格式与验收记录，搜索 records/agent_service/agent_proposals/agent_security/agent_http/navigation 的类型、权限、确认及落盘读写点。
- 影响：不改 Markdown/JSON 数据、HTTP/MCP 实现、前端缓存、草稿或历史；未来契约只能标为拟定，不回写当前实现事实。
- 计划检查：目标 diff、文档相对链接/围栏、工作项状态与依赖一致性、git diff --check；纯文档不运行业务或真实客户端写入验收。
- 已知风险：远程暴露需要独立认证/传输和运维决策；网页批准不能沿用 Agent 自报确认；新增类型不能自动扩展旧凭据的可见范围。历史记录保留，现状与未来设计分别说明。

### 2026-11-06 / AG-115 / 完成

- 实际文件：新增 docs/AI_AGENT_EXTENSION_PLAN.md；更新 docs/AI_AGENT_PLAN.md、docs/AGENT_SETTINGS_PLAN.md、docs/AI_AGENT_PROGRESS.md、README.md、AGENTS.md，共 6 个 Markdown 文件。
- 交付：五类后续范围拆为 AG-116～126 共 11 个待开始项；逐项记录字段/API 拟定契约、模块接点、依赖、验收门槛和独立提交要求；补齐类型权限、旧提案/摘要/schema 兼容、网页批准幂等与崩溃恢复、远程 OAuth/TLS/部署门槛和阶段交付。
- 文档冲突：主方案现状摘要原写“不自动修改 Codex 配置”，与已完成 AG-113 的明确确认登记不符；更新摘要与首期范围说明，保留历史完成记录及首期验收。
- 检查：Python 内联文档检查验证 6 个 Markdown、48 个本地链接、代码围栏/编码和 11 个实现项均为待开始，通过；人工核对目标 diff、五类覆盖、依赖顺序和当前事实/未来契约区分；git diff --check 通过。纯文档未运行应用测试、浏览器或真实客户端验收，未借用历史结果宣称新功能已实现。
- 兼容影响：仅文档，不变更业务 Markdown/JSON、HTTP/MCP 实现、草稿、历史、localStorage、资源缓存、APP_VERSION 或用户配置；无需数据迁移。
- 决策与风险：新增规划决策 AG-DEC-006～011；远程身份服务/客户端/协议版本与部署依赖待 AG-122 核查，新增类型/批准流程的实现风险留至对应工作项验证，无本次规划遗漏。
- 遗留和下一步：本次仅规划已完成；AG-116～126 保持待开始，未来获开发指令后从 AG-116 开工，远程另按设计门槛推进。未启动功能实现或外部接入。

### 2026-11-04 / AG-114 / 开始

- 范围：把关键日志摘录至正文、外部路径不能作为唯一证据、已存工作台文件可引用的规则同步至使用指引、MCP 初始化/工具说明及仓库维护规范。属于内容规范维护，不改变模块边界或 RF 顺序。
- 文件：docs/AGENT_USAGE.md、workbench/agent_tools.py、AGENTS.md、现有 MCP 契约测试及本台账。
- 检查：git status --short 干净；已搜索规则与初始化/工具描述读写点；计划运行 MCP 专项、Python 语法、文档及 diff 检查。
- 影响：不修改业务数据、API Schema、提案确认、草稿/历史或 UI；不读取或上传实际日志。规则不能补造未获得的原文，摘录需保留上下文并脱敏。

### 2026-11-04 / AG-114 / 完成

- 实际文件：docs/AGENT_USAGE.md 增加日志证据与来源引用细则；workbench/agent_tools.py 的 AGENT_RULES 同步精简规则；AGENTS.md 9.1 增加维护约束；test_mcp_stdio.py 在已有初始化与工具目录契约中验证规则实际输出；本台账记录状态。
- 验证：`python -m unittest -v test_mcp_stdio` 8 项通过，包含真实 stdio/HTTP 工作流；`python -m py_compile workbench/agent_tools.py test_mcp_stdio.py`、变更文档本地链接/围栏及 `git diff --check` 通过。
- 兼容：仅扩展 MCP 初始化说明及 capabilities/prepare_proposal 工具描述，不变更协议/工具 Schema、业务数据、确认流程或 UI；无需数据迁移或前端缓存变更。文档是主要规范，工具说明向其他客户端传达同一规则，不宣称服务端自动验证日志内容。
- 决策/遗留：按用户要求保留关键日志正文，已存工作台文件可引用；不新增日志上传或执行能力。重新连接 MCP 后可获取更新说明，本项无遗留实施内容。

### 2026-11-04 / AG-113 / 开始

- 范围：网页检测本机 Codex 用户配置与同名登记，展示变更后明确确认；固定参数在隔离配置中生成登记，验证只改变目标 MCP 项后备份/版本检查/原子安装；持久回执、结果查询和崩溃恢复；登记后自动只读自检，保留终端高级入口。
- 预计文件：新增 agent_registration.py 和专项测试；management_http、agent-settings/index/http_api、真实浏览器测试、方案/接入/维护/架构/格式/验收/README/AGENTS。
- 检查：工作树干净；已读取涉及读写点、测试与文档并核对官方 MCP 文档及真实 CLI help；计划全 Python、专项真实 Codex 隔离登记/冲突/各阶段失败/并发/重读、HTTP 安全边界、两主题两宽度浏览器、语法及 diff。
- 影响/风险：不改变业务格式、API、提案/编辑器/历史；仅页面明确确认会修改服务当前用户 CODEX_HOME/config.toml。外部程序不遵守工作台锁，保留写前重读和剩余文件系统竞态说明；私密备份不进入可移植导出。不操作真实 Codex 配置作验收。

### 2026-11-04 / AG-113 / 完成

- 文件：新增 workbench/agent_registration.py、test_agent_registration.py；修改 management_http/http_api、agent-settings/index、test_agent_runtime.py、test_agent_settings.js，以及 README/AGENTS/方案/进度/接入/架构/格式/维护/验收文档。
- 实现：网页环境/同名检查，脱敏原项与完整新项预览；明确确认后固定参数运行隔离 Codex mcp add/get，验证只改变目标项；原配置私密字节备份、配置/客户端版本复查、跨空间目标锁、单文件原子安装和持久请求回执。相同项不重复写文件，同名差异必须改名或显式替换。
- 恢复/UI：准备及写入阶段中断可重读判断 completed/not_applied/recovery_required，不重放或回滚目标。响应丢失后原标签页刷新可继续查询；sessionStorage 只存请求/客户端 ID。成功后自动运行既有只读自检，登记与自检/聊天加载分别说明；手工终端入口折叠保留。连续点击确认框的竞态在浏览器验收中发现并修复；窄屏替换勾选框布局目视修正。
- 自动验证：全量 `python -m unittest -q` 192 项通过；回执损坏/格式及后续外部修改边界补充后，`python -m unittest -q test_agent_registration test_agent_runtime` 23 项复验通过。全部 18 个 Node 契约通过；设置浏览器在最后布局修正后复验通过。53 个 Python、43 个 JavaScript 语法、变更文档链接/围栏和 git diff --check 通过。
- 专项：10 项登记测试含真实 CLI 新建/同名替换/原配置备份及其他项保留、重复/并发、跨空间目标冲突、旧授权版本、损坏/超大配置、超时/异常候选、各阶段故障与实际子进程 os._exit 后查询恢复；管理 HTTP 同源/会话/Agent 凭据拒绝及持久查询验证。真实 Edge 浅深主题 × 1440/390，确认/取消/改名失效/双击/响应丢失/刷新恢复/自动只读检查通过，代表截图目视检查，未提交截图。
- 真实 Codex：codex-cli 0.163.0-alpha.10.2 / MCP 2025-11-25，12 工具和既有入库/追加/更新/重试/取消/重启/撤销全链路验收通过，model_turns_started=0、user_config_changed=false。登记与所有浏览器验收均为临时 CODEX_HOME、数据和凭据；未接管真实用户配置。
- 兼容/决策：落实方案第 15 节；业务 Markdown/JSON、旧 API/手工命令、编辑器/提案/历史与旧导航存储保持兼容，无数据迁移；新增管理 API 和私人回执 schema=1，缓存版本与 APP_VERSION 同步。外部程序竞态、备份长期保留及非原生 CLI 需手工接入的限制已写维护文档。当前工作项无遗留实施内容。

### 2026-11-04 / AG-112 / 开始

- 范围：按用户反馈补充 CMD/PowerShell 终端选择、对应安全命令与执行提示；服务 PATH 无 Codex 时检测当前用户桌面安装目录，返回可执行文件绝对路径。无需改变系统 PATH，不自动登记真实 MCP。
- 文件：agent_setup/management_http、agent-settings/index、相关 Python/浏览器测试、接入/维护/验收文档。属功能修复，不改变领域边界或既有 RF 顺序。
- 检查：先 git status --short（干净）；搜索 setup 字段/API/UI/测试；官方 MCP 文档和本机路径核对；真实 CMD/PowerShell 隔离登记与特殊字符校验、空 PATH 安装发现、两主题/宽度浏览器、全量 Python/语法/diff。
- 数据/API：新增可选 terminal 参数与响应字段，旧 powershell_command/默认 Python 调用保持兼容；不读取令牌到网页，不改业务/草稿/历史/用户配置。风险：CMD 的百分号/延迟展开无法靠双引号消除，遇到这类路径明确引导 PowerShell，不生成可能被解释的命令。

### 2026-11-04 / AG-112 / 完成

- 文件：agent_setup/management_http/http_api、agent-settings/index/management.css、management/diagnostics/settings 测试；README、接入/维护/方案/架构/管理验收/台账。
- 实现：Windows 默认 CMD，可切 PowerShell，标签/命令/执行步骤同步；旧 API 不传 terminal 仍按 PowerShell。CMD 参数双引号，PowerShell 字面量单引号；CMD 的百分号/感叹号/双引号/控制字符不生成有歧义命令。命令生成请求有顺序校验，过期响应不覆盖新选择。
- 检测：先服务 PATH、后当前用户桌面版本目录，返回 Codex 绝对路径；实际清空本进程 PATH 后检测本机安装并运行 --version 成功，不修改系统环境。未找到时明确提示，诊断复用检测。
- 验证：全 Python 181 项通过；新增真实 CMD 临时 CODEX_HOME 登记且 PATH 为空，含空格/单引号/&/括号/^ 的参数重读一致；原真实 PowerShell 隔离登记和缺失客户端诊断通过。全 Python/JS 语法、Node 入口/API/管理/样式契约、文档链接/围栏及 diff 检查通过。
- 浏览器：真实 Edge 设置工作流通过，包含 CMD/PowerShell 切换、生成/复制、主题/桌面与390窄屏；新增长 Codex 路径换行/最小列宽保护，无溢出，已目视检查浅色窄屏 CMD 和深色桌面 PowerShell。刷新用例增加旧页面标识，避免把 reload 前 DOM 当成新页面；截图只留临时目录。
- 兼容：业务格式/权限/草稿/历史不变，不执行真实登记或修改用户配置；新增 API 字段为兼容扩展，资源缓存与 APP_VERSION 同步。剩余边界：其他安装分发若不在 PATH 或当前桌面目录，继续提示手工检查，不任意扫描磁盘。

### 2026-11-04 / AG-111 / 开始

- 范围：逐项审计方案要求、补齐空库/大量范围/迁移/备份/关闭验证、全部 Python/Node/语法与真实 Codex 最终门禁；同步当前能力、维护与验收文档。
- 文件：验收/方案/台账/README/AGENTS/架构/格式/维护/使用指引；必要的管理验收测试。若审计发现影响正确性的缺陷，修复并记录，不省略或收窄原方案。
- 检查：全量自动门禁、真实 Edge 矩阵和隔离真实 Codex；文档链接/围栏、最终 diff/工作区与生成物检查。
- 工作区：AG-110 已提交 ec7f833，状态干净。风险：旧设计措辞不能覆盖当前事实；只能用实际输出证明结果，不复制历史数量。

### 2026-11-04 / AG-111 / 完成

- 文件：新增 AGENT_SETTINGS_ACCEPTANCE.md；更新 README、AGENTS、接入/使用/原方案/本方案/台账/业务验收/架构/数据格式/维护文档；扩展 test_agent_runtime/management/settings/startup 与 codex_agent_acceptance 夹具，不修改正式业务数据。
- 交付审计：验收文档逐项映射方案 §1～15 的实现、测试和限制；本期启停/授权/向导/诊断均已落地，一键修改 Codex 配置仍为明确排除项。旧 RF 与 AG-000～105 历史保持不变。
- 兼容证据：新增真实 ZIP 导出排除接入身份/私人配置，解压恢复新身份、无源客户端，切换已有空间使用目标偏好；真实旧 schema-v1 注册表无 management_revision 时读取不重写、可鉴权并轮换。业务 Markdown/API/草稿/历史/编辑器不变，无真实库迁移或写入验收。
- UI 最终证据：全部 18 个 test*.js 通过；新增空范围引导与真实 60 项目/100 分类样本的两主题×1440/390限高滚动/无溢出；设置页概况/表单/诊断/大量范围 16 张临时截图，目视检查代表页。既有双编辑器/Agent/概念图/项目筛选真实浏览器均通过。
- Python：最终 `python -m unittest -q` 179 项通过，无跳过；此前 `python -m unittest -v` 177 项通过，新增旧注册表和 Windows 清理用例后全量再验。MCP/启动专项 12 项通过，原 MCP EOF 正常退出仍通过。
- Codex：最终 `python codex_agent_acceptance.py` 连续两次正常完成；codex-cli 0.163.0-alpha.10.2 / MCP 2025-11-25 / 12 工具、完整两类型/修改确认/追加更新/幂等取消重启撤销；model_turns_started=0、user_config_changed=false。
- 范围补充与修正：并行最终联调时 Codex 后台插件克隆导致 Windows 退出清理阻塞/临时目录占用；已停止该测试 Python、核对其客户端撤销。夹具禁用不相关插件/apps/remote_plugin，仅对测试 Codex 进程启用树回收；带真实继承管道子进程的 Windows 回归通过，保留普通桥接 EOF 流程。没有改用户 Codex 配置，失败临时目录不提交。
- 自动检查：51 个 Python/43 个 JavaScript 语法通过，17 份文档 UTF-8/围栏/本地链接通过，git diff --check 通过；提交前再次审阅目标 diff，不含业务库、机器配置、日志、截图或用户既有修改。
- 决策/风险：AG-DEC-006～010 落地；同用户程序沙箱、分类跨文件失败收窄、内存诊断不证明聊天身份、未知日志拒绝覆盖、其他平台/协议需实测等限制在验收与维护文档明确保留，不将未测平台标为通过。
- 后续：本方案首期无未完成工作项；自动登记或独立托管程序须新需求另行登记。

### 2026-11-04 / AG-110 / 开始

- 范围：有限时后台诊断、服务/授权/配置/环境/MCP 握手/只读能力分层结果、可信自检标记与实际请求观察、UI 查询及真实隔离 Codex 复验。
- 文件：新增 agent_diagnostics 及测试；runtime/management_http/agent_http/mcp_stdio、agent-settings 与浏览器测试、方案/使用/验收记录。
- 检查：真实临时服务的初始化/12 工具/只读往返；关闭/撤销/损坏/离线/超时/超限/协议污染；任务去重/清理/空间切换，真实 Codex 验收不启动模型或改用户配置；浏览器与全量回归。
- 工作区：AG-109 已提交 bd60acc，状态干净。风险：持业务锁等待诊断 HTTP 会死锁，因此仅在锁内登记任务，工作线程在锁外运行；自检 nonce 不接受调用方自报作为证明，不对外返回。

### 2026-11-04 / AG-110 / 完成

- 实际文件：新增 agent_diagnostics.py、test_agent_diagnostics.py；runtime/management_http/agent_http/management/mcp_stdio/http_api、agent-settings/management.css/index、浏览器测试、方案/接入/架构/README/台账。
- 实现：最多 50 份内存任务、每客户端并发去重；固定版本探测 3 秒、桥接 8 秒、各输出流 128 KiB 限制与子进程回收；7 层检查和跳过/失败/警告、时间与建议；后台不持业务锁等待 HTTP。
- 证据：nonce/client/有效期匹配才视为自检；普通请求与自检分别记录时间，伪造标记不证明来源；页面明确握手不等于当前聊天在线。任务/观察值在空间切换及服务重启后失效，不持久化敏感信息。
- 验证：全 Python `python -m unittest -q` 174 项通过；补充场景后诊断专项 7 项通过（真实握手/12 工具/capabilities、无业务或提案写入、离线、缺失 Codex、关闭/撤销/损坏/错地址、去重/参数拒绝、超时/超限/管道清理、污染脱敏、另一空间隔离）。51 个 Python/43 个 JS 语法、入口/样式与 diff 检查通过。
- 真实浏览器：`node test_agent_settings.js` 通过，增加真实诊断成功、仅自检时间、关闭失败；两主题×桌面/390 的诊断 4 张截图无溢出并目视检查代表页。此前完整设置流仍通过；临时截图不提交。
- 真实 Codex：`python codex_agent_acceptance.py` 通过；codex-cli 0.163.0-alpha.10.2、MCP 2025-11-25、12 工具、两类写入/修改预览确认/追加更新/取消/重试/重启撤销；model_turns_started=0、user_config_changed=false。
- 兼容/风险：不新增 MCP 管理权限，不变更业务格式/预览确认；仅桥接自检环境可添加专用头，正常客户端兼容。Codex 检测只运行固定 --version；Windows 实测，未宣称 Linux 实机验收。APP_VERSION 与资源缓存同步。
- 下一步：AG-111 最终审计、兼容矩阵和文档交付。

### 2026-11-04 / AG-109 / 开始

- 范围：设置内独立 Agent 页面、启停/偏好、客户端表单与操作、失败/冲突/未保存保护、Codex/通用 MCP 向导与正确 PowerShell 转义；不自动修改用户配置。
- 文件：新增 agent-settings feature、接入指引后端与专项测试/浏览器契约；app/index/navigation/api、管理/响应式样式、文档和台账。
- 检查：官方 MCP 文档及本机帮助（已核查）、后端设置参数/转义/无秘密、Node 入口/样式/管理契约、真实浏览器浅深主题×桌面/390、成功/失败/刷新/失效会话/未保存/复制、全量回归。
- 工作区：AG-108 已提交 add09b5，状态干净。风险：DOM 替换监听、过期响应、路径转义、旧客户端特殊 scope 组合；诊断握手与实际请求证据单列 AG-110。

### 2026-11-04 / AG-109 / 完成

- 文件：新增 js/features/agent-settings.js、workbench/agent_setup.py、test_agent_settings.js；修改 app/index/api/navigation/management.css、management_http/http_api、管理测试与 README/接入/架构/方案/台账。
- UI：设置入口、状态/偏好、授权表单/范围/旧组合、编辑/轮换/撤销/地址修复、未保存离开提示、服务端版本冲突与输入保留；结果不确定先查原操作，创建成功回执查询后清除新建表单，避免重复创建；过期响应不落新空间。
- 向导：只读派生程序/参数/服务地址/环境信息，GET/POST setup 与严格登记名校验，PowerShell 单引号转义，复制成功与回退选择；不执行登记、不修改用户配置，Codex 缺失只提示，不声称当前聊天已连接。
- 验证：全 Python `python -m unittest -q` 169 项通过；最终管理/运行专项 26 项通过，含真实 PowerShell 解析与真实 Codex 在隔离 CODEX_HOME 登记含空格/单引号/美元/反引号路径，配置参数重读完全匹配；全部 18 个 Node 契约通过，新增真实 Edge 流程再次专项通过。
- 浏览器：首次查看无凭据初始化、启用/偏好持久化、创建丢失响应查询不重复、编辑成功/会话失败/版本冲突保留、轮换/撤销/关闭/刷新、复制成功/失败；浅深主题×1440/390 的列表/表单 8 张截图，目视检查桌面概况与窄屏深色表单，焦点/disabled/error/长中文/空分类无溢出。截图仅临时目录。
- 检查/兼容：49 个 Python 文件语法、前端入口/样式/管理/API 契约和 diff 通过；index 缓存版本/APP_VERSION 同步，旧导航键不变，业务 Markdown/提案确认不变；前端不保存凭据或管理会话到 localStorage。
- 修正证据：首次浏览器用例在应用初始化尚未完成就导航，导致初始化恢复首页；测试改为等待已有启动 Promise 完成。窄屏矩阵等待现有布局过渡稳定后断言，未通过放宽溢出阈值掩盖问题。
- 风险/下一步：分层握手诊断与实际请求观察仍未实现，继续 AG-110；界面不以生成命令宣称连接成功。决策 AG-DEC-006/007/009。

### 2026-11-04 / AG-108 / 开始

- 范围：CLI/UI 共享持久管理操作、客户端脱敏列表与编辑/轮换/撤销、版本校验、凭据恢复与修复、授权范围生命周期；不修改 Codex 配置。
- 预计文件：agent_management/security/runtime/management_http、repository 与必要分类迁移钩子、CLI 管理修复入口、管理/恢复测试及方案/台账/数据与维护说明。
- 检查：临时凭据/数据的成功与失败重读、旧格式、并发/幂等、真实子进程中断恢复、第三方内容保护、分类重命名/删除/重建授权、HTTP 越权与脱敏；全量回归与语法/diff。
- 工作区：AG-107 已提交 73c18a9，开工状态干净。风险：多文件切换点、日志敏感快照、分类与授权跨存储一致性；先明确契约后编码。

### 2026-11-04 / AG-108 / 完成

- 文件：新增 agent_management.py、test_agent_management.py；修改 security/runtime/management_http/agent_http/repository/configuration/http_api、server、test_agent_runtime 及方案/台账/架构/数据格式/维护说明。分类校验仍由配置领域仓储负责，门面仅注入授权迁移协作回调。
- 行为：CLI/UI 共享持久管理操作，脱敏列表、创建/编辑/轮换/撤销/地址修复、严格预期版本、操作查询；配置→注册表→精简回执，故障恢复/第三方内容停写，report/abandon CLI。凭据锁与已接受的 Agent 请求共享；未决客户端暂停鉴权，其他客户端保持可用。
- 授权迁移：分类改名前收窄旧名，业务成功后授予新名；删除或省略空分类移除授权，不扩大到未分类；中断保留收窄，可人工核对。项目仍按稳定 ID 授权，缺失范围在列表提示。
- 兼容：注册表 schema_version=1 不变，management_revision 可选缺省 0；旧 CLI/配置可读，新回执仅增加字段，不改业务 Markdown/提案确认规则。管理快照只在私人目录，完成/放弃即清除；精简幂等回执长期保留。APP_VERSION 更新。
- 验证：`python -m unittest -q` 167 项通过；最终严格版本检查后 `python -m unittest test_agent_management test_agent_runtime -q` 24 项通过；包含各写入阶段故障、真实 os._exit 中断/CLI 恢复、两个真实 CLI 并发、轮换/撤销持久化、重命名失败收窄、旧预览权限变更拒绝、HTTP 脱敏/边界。48 个 Python 文件语法、app/concept-map 语法、management/app-core Node 契约及 diff 检查通过。
- 风险：分类与私人配置不是跨文件事务；部分失败可能业务已完成但授权保持收窄，错误提示需重新核对；未知/损坏日志拒绝自动修复。管理会话不是同用户进程沙箱。UI、命令向导、诊断仍未交付。
- 决策：AG-DEC-008/010；下一步 AG-109 设置 UI 与配置向导。

### 2026-11-04 / AG-107 / 开始

- 用户已要求开始并完成方案；本项先实现运行时与管理边界，不提前登记真实客户端或修改 Codex 配置。
- 范围：只读发现、工作空间本机偏好、显式 CLI 覆盖、启停/部分失败、管理会话及 status/runtime/operations 路由、空间切换适配。
- 预计文件：新增 agent_runtime/agent_management_http 与专项测试；server/http_api/paths/agent_http；方案/架构/接入/台账。
- 检查：临时目录验证读取无副作用、重载、参数优先级、偏好异常、HTTP 同源/会话/版本/幂等、迁移；全 Python 测试及相关语法/diff。
- 工作区：开工 git status --short 无输出，保留 AG-106 提交。风险：锁序、CLI 覆盖与偏好独立、凭据自定义根目录、未决提交；AG-108 的凭据多文件日志后续单独实现。

### 2026-11-04 / AG-107 / 完成

- 实际文件：新增 `workbench/agent_runtime.py`、`workbench/agent_management_http.py`、`test_agent_runtime.py`；修改 server/http_api/paths/agent_http、方案/台账/README/架构/数据格式/接入说明。
- 行为：状态读取无初始化副作用；私人 runtime.json 偏好、CLI 启/禁用覆盖、当前服务启停、独立短期管理会话、同源/版本/运行设置幂等与部分失败；空间切换重新装配会话，Agent 业务在协调内重查授权；APP_VERSION 更新。
- 兼容：现有身份/注册表/业务 Markdown/API 不迁移；无偏好默认关闭；普通启动读取偏好，显式 CLI 只影响当次；关闭不撤销授权、不删除提案、不跳过业务恢复。
- 验证：`python -m unittest -q` 153 项通过；`python -m unittest test_agent_runtime -q` 10 项通过（含真实临时进程启动/重启、偏好与显式禁用、写锁期间关闭等待、迁移/会话失效、失败保留状态、版本冲突/幂等/跨站拒绝）。全部 46 个 Python 文件语法通过，app/concept-map 语法与 diff 检查通过；纯后端本项无 UI，不以仓储测试替代后续浏览器验收。
- 决策与风险：遵循 AG-DEC-008/009；管理会话不是同用户程序沙箱。运行设置去重仅限服务生命周期，重启后先查询再设置目标状态；凭据管理持久日志交 AG-108，不宣称已实现。
- 下一步：AG-108 客户端管理与凭据恢复；UI/向导/诊断继续待开始。

### 2026-11-04 / AG-106 / 开始

- 范围：将已讨论的工作台内接入管理方案形成执行文档，登记后续 AG-107～111，并补齐文档入口；不实现 UI、API 或运行配置，不授权真实客户端。
- 预计文件：新增 `docs/AGENT_SETTINGS_PLAN.md`；更新本台账、`docs/AI_AGENT_PLAN.md`、`docs/AGENT_INTEGRATION.md`、`README.md`、`AGENTS.md` 的文档入口。
- 分类与影响：Agent 功能规划文档治理，不属于 RF 重构；Markdown/JSON 业务格式、HTTP、草稿、历史、外部编辑及当前 UI 均不变。
- 工作区：`git status --short` 无输出，未发现用户已有修改。
- 计划检查：核对现有启动/授权/迁移/设置页实现；检查变更文档的 UTF-8、围栏与本地链接，审阅目标 diff，运行 `git diff --check`。纯文档变更不运行功能测试。
- 风险：启用持久化、管理接口边界、凭据多文件一致性与诊断证据均为待实施设计，不能写成已具备能力；原 AG-000～105 历史状态保持不变。

### 2026-11-04 / AG-106 / 完成

- 实际文件：新增 `docs/AGENT_SETTINGS_PLAN.md`；更新本台账、`docs/AI_AGENT_PLAN.md`、`docs/AGENT_INTEGRATION.md`、`README.md`、`AGENTS.md`。
- 交付：需求/排除范围、页面流程、启停偏好、模块与管理 API 草案、管理会话、授权生命周期、凭据多文件恢复、配置向导、诊断证据、迁移/修复/降级、AG-107～111 文件及验收分解、维护清单；决策 AG-DEC-006～010 记于新方案。
- 兼容影响：只改文档，不变更业务数据、API、UI、资源版本或用户配置；未授权真实客户端，未启动服务或模型。
- 自动检查：Python 内联检查 6 份变更文档的 UTF-8、围栏配对及本地链接；最终 41 个本地链接有效，`git diff --check` 通过。纯文档变更未运行功能/浏览器测试，不沿用历史验收结果宣称新功能通过。
- 人工审阅：对照启动参数、默认启动脚本、授权写入/鉴权、HTTP 访问边界、空间迁移与设置页实现核查；目标 diff 仅含方案、台账和入口，不含机器路径、秘密或生成物。
- 风险与遗留：凭据管理日志 schema/保留时间、切换点、修复入口及精确 API Schema 明确作为后续开工设计门槛；管理会话不构成同用户进程沙箱。未解除尚未实施的风险。
- 下一步：后续收到实施任务后从 AG-107 开始，先补充锁序/接口契约并记录开工；AG-107～111 保持待开始，不改写 AG-000～105 历史。

### 2026-11-03 / AG-000 / 开始

- 范围：只编写完整实现方案、接入约束及实施台账；不实现功能，不登记真实客户端，不操作业务数据。
- 预计文件：`docs/AI_AGENT_PLAN.md`、本文件、`AGENTS.md`、`README.md`、`docs/REFACTORING_PROGRESS.md`。
- 工作区：开始时 `git status --short` 无输出，未发现用户既有修改。
- 计划检查：方案与代码事实交叉核对、相对文档链接检查、目标 diff 审阅、`git diff --check`；文档变更不运行功能/浏览器测试。
- 风险：服务端无版本条件、文档无历史、文档 ID 并发、静态资源根边界、现有导航无条目深链接。均纳入方案，不在本轮顺带修改代码。

### 2026-11-03 / AG-000 / 完成

- 实际文件：`docs/AI_AGENT_PLAN.md`、`docs/AI_AGENT_PROGRESS.md`、`AGENTS.md`、`README.md`、`docs/REFACTORING_PROGRESS.md`。
- 交付：完整方案包含需求、代码差距、模块边界、HTTP/MCP 契约、提案状态、确认边界、历史、版本检查、持久幂等/故障恢复、权限、迁移/备份、阶段与验收矩阵。
- 数据/API 兼容：仅文档变更；未创建运行目录、未变更业务 API、数据格式、资源版本或客户端配置。文中新增契约均明确为待实施。
- 自动验证：通过 Python 内联检查验证 5 份文档的 UTF-8、代码围栏配对及 22 个本地链接；`git diff --check` 通过。未运行功能测试和浏览器验收，因为本轮没有运行时代码或 UI 变更。
- 人工审阅：对照 records/documents/http_api/repository/navigation 的实现核查关键事实，审阅目标 diff，未夹带业务数据、凭据和生成物。
- 关键决策：AG-DEC-001～005。风险已登记，未声称已解决实现层风险。
- 遗留与下一步：功能尚未实现；按 AG-101 开始共享保存保护，开工前记录精确范围和测试计划。

## 关键决策

| ID | 决策 |
| --- | --- |
| AG-DEC-001 | 通用业务 HTTP API + 本地 stdio MCP，Codex 为首个客户端；保留零第三方运行时依赖 |
| AG-DEC-002 | Codex 内完整预览后确认；服务端保证版本一致，不宣称独立验证人工确认 |
| AG-DEC-003 | 单服务共享写入、版本检查、持久操作日志与回执；不让桥接器直接写 Markdown |
| AG-DEC-004 | 第一版 issue/document，单提案单目标；todo/info、网页确认与远程接入后续单独登记 |
| AG-DEC-005 | 先补共享保存/历史保护，再开放 Agent 写入；不重开已完成 RF 工作项 |
| AG-DEC-006 | 新类型独立授权，旧凭据缺省仅 issue/document，不自动扩权 |
| AG-DEC-007 | info 使用有序字段；append 仅正文，不增加命令执行能力 |
| AG-DEC-008 | local_web 在本机管理通道批准并调用同一持久提交引擎 |
| AG-DEC-009 | 新流程格式显式版本化，保留旧摘要和旧日志兼容读取 |
| AG-DEC-010 | 远程采用独立最小入口，默认关闭并强制本机批准 |
| AG-DEC-011 | 远程 OAuth/传输版本和部署依赖须先通过 AG-122 设计与实测门槛 |

## 后续风险跟踪

- 外部编辑器无法被进程锁强制约束；实施时验证冲突和历史，并保留剩余竞态说明。
- MCP 候选版本必须与真实 Codex 握手验证；不把指定历史规范称为最新规范。
- Agent 自报用户确认是已接受的信任边界；后续网页独立确认可增强保证。
- 每个功能阶段都需记录实际测试数量和结果，不能复制历史测试基线。

### 2026-11-03 / AG-101 / 开始

- 范围：共享 Repository 写入锁、字节 revision 和条件更新、记录/文档历史、网页冲突与关闭保存适配、服务数据目录独占锁。
- 预计文件：workbench/write_coordinator.py、history.py、repository.py、records.py、documents.py、http_api.py、paths.py、server.py；app.js、js/core/api.js、index.html；测试和架构/数据文档。
- 检查：新增并发/历史/锁/409 测试，全 Python、Node 契约、全文件语法、浏览器编辑器矩阵与 diff 检查。
- 风险：外部编辑器不受进程锁控制；保留历史和明确剩余竞态。网页文档原先只有外部修改提示，需复用现有冲突对话框完成三种处理。

### 2026-11-03 / AG-101 / 完成

- 实际文件：workbench/write_coordinator.py、history.py、repository.py、records.py、documents.py、configuration.py、http_api.py、paths.py、server.py；app.js、js/core/api.js、index.html、css/components.css、css/knowledge-base.css；test_write_coordinator.py、test_http.py、test_startup.py、test_editor_workflows.js；README 和架构/数据/维护文档。
- 实现：共享可重入写锁覆盖门面写入与间接配置/附件操作；记录/文档的 SHA-256 条件保存和历史恢复；文档并发 ID；共用历史快照（兼容旧版本名）；服务目录 OS 锁、迁移接管与 replace 前置检查。分类迁移改走文档仓储，避免 revision 写入 Markdown 并保留历史。
- API/兼容：新增 revision 与可选 expected_revision，不改变旧调用；新增文档历史列表/读取/恢复和记录完整快照读取。正式 Markdown 不增加 revision，旧历史继续读取；无迁移真实数据。
- 网页：记录/文档/关闭保存使用版本条件，409 保留草稿；文档复用冲突对话框；历史查看和确认恢复。资源缓存版本与 APP_VERSION 已同步。截图发现窄屏按钮压缩，最小修正为保持按钮宽度并复用横向滚动。
- 自动验证：`python -m unittest -q` 最终 102 项通过；全部 16 个 Node 契约通过，随后对修改后的编辑器工作流、管理和样式专项复验通过；全项目 Python/JavaScript 语法检查和 `git diff --check` 通过。
- 浏览器：真实 Edge 验证两编辑器保存/失败/关闭/切换/草稿/重开、记录冲突、文档三种冲突选择、历史查看/恢复；四种主题/宽度截图在临时目录生成并目视检查，未提交截图。
- 平台：Windows 实际子进程排他/释放测试通过；POSIX flock 调用分支契约通过。本机 WSL 不提供可用 Linux 运行环境，未宣称 Linux 内核实机验收。
- 决策/风险：遵循 AG-DEC-003/005；外部程序写入竞态和无版本旧客户端限制保留；共享保存保护已具备，Agent 写入仍未开放。
- 下一步：AG-102（访问边界、认证和只读 API）。

### 2026-11-03 / AG-102 / 开始

- 范围：静态资源明确允许集、Host/Origin 校验、客户端本机凭据/作用域/撤销轮换、workspace 绑定及只读 Agent API；接入默认关闭。
- 文件：workbench/agent_security.py、agent_service.py、agent_http.py、http_api.py、server.py；test_agent_api.py 和接入/架构/维护文档。
- 检查：临时数据/配置目录 HTTP 成功、401/403/404、范围过滤、令牌轮换、跨源与静态泄露测试；全 Python/Node/语法门禁及正常资源浏览器回归。
- 风险：旧无认证 UI API 与本机文件并非恶意同用户进程沙箱；只声明 Agent API 授权边界。凭据只写用户配置目录，不输出秘密。

### 2026-11-04 / AG-102 / 完成

- 文件：新增 workbench/agent_security.py、agent_service.py、agent_http.py、test_agent_api.py、docs/AGENT_INTEGRATION.md；修改 server.py、http_api.py、paths.py、write_coordinator.py、test_startup.py 和 README/架构/数据/维护文档。
- 实现：默认关闭的 Agent API；独立用户配置目录的随机令牌/摘要/权限；客户端创建、撤销、轮换 CLI；工作空间绑定和迁移后重新装配；作用域过滤的 capabilities/projects/catalog/search/items 分段读取；分页和限流。
- 访问边界：Host/Origin/跨站校验，旧 UI API 拒绝 Agent Authorization；静态入口允许集及真实 Windows junction 逃逸测试；客户端输出不含机器路径字段和令牌。CLI 管理不启动第二个业务仓储。
- 兼容：不迁移现有业务数据；新增 .agent 身份文件按需创建，ZIP 排除；普通 UI 正常工作。--replace 比较 Agent 启用状态，APP_VERSION 更新。
- 验证：最终 `python -m unittest -q` 112 项通过（无跳过）；全部 16 个 Node 契约通过，包括真实浏览器编辑器、概念图、项目筛选与主题/宽度回归；全 Python 语法与 diff 检查通过。真实子进程 CLI 启动、查询、运行中创建客户端均验证。
- 风险：凭据仍属于本机用户权限下的秘密；未将旧接口或本机文件宣传为 MCP 沙箱。提案/写入和 MCP 仍未开放。
- 决策：AG-DEC-001/003；下一步 AG-103。

### 2026-11-04 / AG-103 / 开始

- 范围：领域仓储预备写入/应用复用、独立提案与完整预览、版本摘要确认、持久操作日志/回执、启动恢复和失败阻写、清理、导出/迁移规则；本期 issue/document 单目标。
- 文件：write_coordinator/history/records/documents/repository、agent_service/agent_http、新增 agent_proposals.py、提案/恢复/HTTP 测试；相关文档与 APP_VERSION。
- 检查：成功/失败/重新实例化，提案修改取消过期、权限/配置/版本冲突，重复与并发提交，manifest/快照/正文/回执/状态各阶段故障注入，旧格式回归、全量门禁。
- 风险：普通原子替换不是跨文件事务；不确定落盘保留日志并阻止自动覆盖；外部编辑器剩余竞态仍需明确。预览和提交使用同一归一化结果。

### 2026-11-04 / AG-103 / 完成

- 文件：新增 agent_proposals.py、test_agent_support.py、test_agent_proposals.py、test_agent_recovery.py；修改 agent_service/agent_http、领域 records/documents、repository/write_coordinator/history、http_api/paths/server、HTTP/写入测试和实施/架构/数据/维护/接入文档。
- 实现：issue/document 单目标新建/追加/更新提案；完整归一化预览、差异和字段变更；修改后版本递增、摘要重算、取消/过期和确认提交。HTTP 提交不接受临时正文，权限/目标/配置/字节版本在提交时重新检查。
- 可靠性：共享领域预备写入与应用，先持久前后快照/manifest 再写正文和回执；逐阶段中断后恢复；重复/并发提交只应用一次；回执和操作 ID 保留，删除后不重建或复用旧 Agent ID。恢复重复应用使用相同历史版本，不消耗多份历史保留数。
- 范围补充：审查发现读取期间外部写入可能使旧正文与新摘要配对，加入一致性重读、准备快照检查及两个真实竞态测试；保留动态 parser patch 点。历史/回收站/回执/操作记录参与分配，兼容转换后仍使用原 ID。
- 恢复边界：新建已尝试写入后文件不存在或出现第三方内容时不自动重建，标记 recovery_required 并阻止业务写入/目录迁移；本机 report/abandon CLI 支持核查和接受磁盘，不修改业务 Markdown。未知事务格式拒绝写入。恢复即使关闭 Agent 也执行。
- 清理与兼容：7 天提案有效期、终结内容 30 天清理、幂等映射和回执保留；在途状态不清理；业务 ZIP 排除 .agent，目录迁移保留其相对路径日志。旧 Markdown 与可选版本条件保持兼容，文档写入现在返回实际重新读取的规范正文。APP_VERSION 更新。
- 自动验证：最终 `python -m unittest -q` 135 项通过，无跳过；全部 16 个 Node 契约通过，随后对版本一致性改动再次运行真实浏览器编辑器工作流通过；全 Python 语法、文档围栏/本地链接和 diff 检查通过。
- 专项证据：两类型持久化；预览/修改/取消/过期/权限/配置冲突；并发幂等；snapshots/manifest/committing/applying/history/target/receipt/proposal 阶段故障；实际子进程 os._exit 在正文写后退出；重启回执恢复、第三方内容保护、快照损坏/路径逃逸/未知版本、真实 report/abandon CLI 均验证。
- 风险：外部编辑器不遵守锁、底层文件系统落盘边界及 Agent 确认声明边界保留，未宣称独立人工认证或跨程序 CAS。网页链接尚未实现，回执 web_path 暂为 null；交由 AG-105。
- 下一步：AG-104（MCP 标准协议适配、通用使用规则、真实 Codex 客户端联调）。

### 2026-11-04 / AG-104 / 开始

- 范围：零依赖 stdio MCP 桥接、工具 JSON Schema/通用规则、配置/连接错误与协议测试，使用独立临时 Codex 配置进行真实客户端握手和工具往返。
- 文件：agent_bridge.py、workbench/mcp_stdio.py（及工具定义模块）、test_mcp_stdio.py、独立 Codex 联调脚本和接入文档。
- 依据：已重新读取 OpenAI Docs 的 MCP 和 App Server 文档，以及 MCP 2025-11-25 生命周期/工具规范；本机 codex-cli 0.163.0-alpha.10.2。使用真实 App Server 工具调用接口，不依赖模拟客户端代替互操作验收。
- 检查：初始化/通知/ping/工具列表和调用、非法消息/参数/版本、EOF/取消/断连、标准输出纯协议、凭据不泄漏、loopback/重定向/大小限制及实际 Codex 工具读写往返。临时配置不修改用户现有 Codex 设置。

### 2026-11-04 / AG-104 / 完成

- 文件：新增 agent_bridge.py、workbench/agent_tools.py、mcp_stdio.py、test_mcp_stdio.py、codex_agent_acceptance.py、docs/AGENT_USAGE.md；修改接入/架构/README 与台账，补充 agent_security 的端口校验。
- 实现：标准 UTF-8 换行 JSON-RPC，MCP 2025-11-25 生命周期/协商、仅 tools 能力和 12 个通用工具；严格输入 Schema、业务 isError/结构化结果与兼容文本；未知参数/方法、非法 JSON/UTF-8/超限消息、通知/EOF/取消边界均处理。桥接只访问本机 Agent HTTP，不装配 Repository、调用模型或执行正文命令。
- 连接：凭据每次重读支持轮换、绑定 client/workspace 身份；仅 loopback，localhost 固定数值地址，无环境代理或重定向；超时/响应限制、标准错误脱敏及可选字段名诊断。新增通用使用指引和实测 Codex 注册/移除命令。
- 实际联调：本机 codex-cli 0.163.0-alpha.10.2，使用独立临时 CODEX_HOME/项目、App Server 的 mcpServerStatus/list 和 mcpServer/tool/call，无模型 turn、无用户配置修改。发现客户端 tools/list 携带 _meta，修正后互操作通过；工具目录 12 项、两类型新建/预览/修改确认、问题追加/文档更新、重试/取消/服务重启/撤销均通过。测试确认声明不是独立人工认证。
- 验证：全量 `python -m unittest -q` 143 项通过；后续端口边界调整的 8 项 MCP 专项复验通过；`python codex_agent_acceptance.py` 两次完整成功，报告 model_turns_started=0、user_config_changed=false；全 Python 语法、前端基础语法、文档链接/围栏和 diff 检查通过。既有 Node 契约在 AG-103 全量通过，本项无前端运行代码修改。
- API/兼容：服务端业务 API 和 Markdown 不变；新增独立 MCP 入口，未登记真实用户客户端或修改真实 Codex 配置。
- 风险：仅声明实测协议版本；其他 MCP 客户端仍需按同一协议自行验证。网页链接与最终发布验收交由 AG-105。
- 下一步：AG-105（深链接、完整浏览器矩阵、性能/最终门禁与发布文档）。

### 2026-11-04 / AG-105 / 开始

- 范围：正式条目稳定深链接、回执可用打开入口、网页刷新/脏编辑/缺失类型检查；最终真实 Codex + 浏览器主题/宽度/历史/冲突矩阵、性能和发布文档。
- 文件：js/core/navigation.js、app.js、index.html、agent_proposals/agent_http/http_api；导航、HTTP、真实浏览器和 Codex 验收脚本；README/AGENTS/架构/数据/维护/接入/进度文档。
- 检查：全部 Python/Node/语法/diff；真实 Codex 12 工具及入库更新/重启；两类型深链接直接打开/刷新/缺失/脏编辑；浅深主题与桌面窄屏截图；性能样本；备份/迁移/故障恢复与关闭接入验证。
- 风险：链接不能成为自动覆盖或新建入口；异步对象必须校验身份，跨功能打开先处理现有草稿/冲突。旧回执没有 web_path 时兼容生成显示链接。
- 范围补充：最终浏览器审查加入保存请求在途时继续输入的回归；修复旧保存回执清除新输入的 dirty/草稿问题，并校验记录保存响应所属会话。此项直接影响 Agent 与网页并发使用的数据安全，复用既有会话与请求注册器。

### 2026-11-04 / AG-105 / 完成

- 文件：app.js、index.html、js/core/navigation.js、三个 CSS 文件；agent_http/agent_proposals/http_api 的链接/版本；records/agent_service 复用搜索匹配；新增 test_agent_workflows.js 与验收记录，扩展导航/HTTP/编辑器/真实 Codex 验收脚本，更新 README/AGENTS/方案/架构/数据/维护/接入文档。
- 行为：正式回执返回稳定 ID 深链接和可信本机地址；旧回执兼容展示。参数与资源类型检查、直接打开/刷新、未保存取消和缺失条目不新建均验证。进入原有编辑器与轮询/冲突链路，无新增聊天或平行编辑器。
- 保存补充：真实浏览器先复现旧回执错误清理后续输入和草稿，再验证两个编辑器在保存期间继续输入后仍保持 dirty/草稿、二次保存并重开持久化。旧会话响应不会改变新会话；信息颜色在后续编辑存在时保留。历史预览使用共享只读 Markdown 渲染。
- 自动检查：最终 `python -m unittest -q` 143 项通过无跳过；全部 17 个 Node 契约通过；最后的保存细节修正后再次执行 `node test_editor_workflows.js`、`node test_agent_workflows.js` 通过。全项目 Python/JavaScript 语法、15 份 Markdown 本地链接/围栏和 `git diff --check` 通过。
- 真实 Codex：`python codex_agent_acceptance.py` 再次通过；codex-cli 0.163.0-alpha.10.2 / MCP 2025-11-25，12 工具、两类型新建/修改预览/确认、问题追加/文档更新、重复提交、取消、重启和撤销；model_turns_started=0、user_config_changed=false。修正 Windows 验收管道关闭阻塞和通知持续到来时总超时失效，不改应用协议。
- UI：真实 Edge 的两类型浅深主题/1440 与 390 视口；代码、表格、稳定引用、长中文、历史、focus/disabled/error。修正页脚按钮压缩、知识正文与长引用换行。固定样本 32 张和空库 4 张视觉矩阵通过断言，目视检查代表页面，截图留在临时目录未提交。
- 性能：`python performance_acceptance.py` 临时样本 12 项目/1200 记录/160 文档/120 附件/约 1 MiB 文档/500 节点；文件 SHA 和 ZIP 1620 成员 CRC 通过。正文打开 1250.2 ms、最大事件循环延迟 1194.3 ms 为现有长文档优化方向；实际各项数值见验收记录。
- 数据/API：原 Markdown、旧历史、localStorage 与无版本旧客户端兼容，无批量迁移；新增回执链接字段，不改提交摘要与候选内容。APP_VERSION 和受影响资源缓存版本同步。备份/迁移/恢复/关闭 Agent 的自动检查均保留通过，未操作真实业务库。
- 环境收尾：一次此前挂起验收遗留临时目录的删除被自动审批以 blocked by policy 拒绝，目录保留；对应服务已停止、客户端全部撤销。后续隔离验收正常退出清理，不绕过拒绝。
- 决策/风险：AG-DEC-001～005 的既定范围保持；Agent 确认声明、外部编辑器竞态、底层文件系统和旧无版本调用限制保留。Windows 进程锁已实测，POSIX 分支契约通过但 Linux 内核实机未验；其他 Agent/协议需另验。
- 下一步：本期 AG-000～105 无遗留实施项。用户可按接入说明显式启用、创建正式客户端并登记 MCP；未擅自修改用户 Codex 配置。todo/info、独立网页批准和远程接入仍属后续范围。

### 2026-11-06 / AG-116 / 开始

- 工作区：git status --short 干净，无用户既有修改；本项为 AG 功能实施，不重开 RF 或 AG-000～115 历史。
- 范围：显式 kinds 授权、旧凭据缺省 issue/document、范围交集与引用隔离、能力字段、schema=2 新提案/日志及 schema=1 旧摘要兼容；本项不提前开放 todo/info 写入和 local_web。
- 预计文件：agent_security/management/service/proposals/tools/http、mcp_stdio、server CLI、agent-settings/index；专项测试与架构/数据/接入/维护/验收文档。
- 验证计划：旧授权/轮换/分类迁移不扩权；严格字段/未知版本拒绝；新旧混合提案与故障恢复；Python 门禁、管理真实浏览器两主题两宽度、JS 语法、diff 检查。
- 影响与风险：业务 Markdown、草稿和编辑器不变；新增私人授权字段与流程版本；旧摘要不得重算。远程身份/TLS/非 Codex 实机依赖在对应项核查，不用模拟替代。

### 2026-11-06 / AG-116 / 完成

- 实际文件：agent_security/management/service/proposals/tools/http/setup、mcp_stdio、server/http_api；agent-settings/index；test_agent_extensions.py、test_agent_settings.js；README、扩展方案、设置方案、架构/数据/接入/使用/维护及本台账。
- 交付：kinds 显式白名单与旧 issue/document 缺省，UI/CLI 授权、轮换保权、引用/提案/项目范围交集；能力返回按类型操作/字段、有效授权、确认模式和流程版本。todo/info 仅可预授权，业务操作由后续项开放。
- 格式兼容：业务 Markdown、草稿、历史和旧 API 不变；新私人配置/管理日志/提案/事务 schema=2，旧 schema=1 读取与原摘要保留；未知版本拒绝清理/放弃/写入并保留证据。发现 setup 旧配置版本检查遗漏并同步修复。
- 自动检查：python -m unittest -q 全量 197 项通过；事务新增摘要关联后 test_agent_extensions/test_agent_recovery 13 项复验通过；全部 18 个 Node 契约通过；54 Python 和 43 JS 全文件语法、Markdown 本地链接/围栏、git diff --check 通过。
- 真实验收：node test_agent_settings.js 使用临时数据/凭据/CODEX_HOME 通过，含显式 todo 授权落盘、缺省两类型、丢响应恢复、编辑/轮换/撤销、会话失效及浅深主题×1440/390；代表桌面表单与深色窄屏大量范围截图目视检查无溢出，截图留临时目录未提交。原长列表断言限定为项目/分类，类型固定列表不要求滚动。
- 真实 Codex：python codex_agent_acceptance.py 通过，codex-cli 0.163.0-alpha.10.2 / MCP 2025-11-25，12 工具、旧两类型往返/修改/幂等/取消/重启/撤销；model_turns_started=0、user_config_changed=false。
- 决策/风险：AG-DEC-006/009；尚未开放新业务类型或 local_web，不宣称远程/非 Codex 已验收。APP_VERSION=2026.11.06.1 与缓存同步；提交使用标题 Add explicit Agent type authorization（哈希由 git log 查询）。下一入口 AG-117。

### 2026-11-06 / AG-117 / 开始

- 前置：AG-116 提交 0953a07；git status --short 干净。
- 范围：todo 读取/搜索/catalog/create/append/update；日期与工作流、派生 completed、既有元数据保留、事务恢复和稳定深链接。复用领域预备写与编辑器，不改变草稿/保存实现。
- 文件：agent_service/tools/proposals/http、repository、navigation/app/index/agent-settings；专项 Python、Node 浏览器与真实 Codex 脚本；版本及相关文档。
- 计划：三操作持久往返、旧授权拒绝、日期非法/清空/旧值保留、工作流变化/外部冲突、重复并发/各阶段恢复；导航和真实浏览器主题/宽度/刷新/保存重开；真实 Codex 三类型回归、语法/diff。
- 核查：网页 due 输入 YYYY-MM-DD 或 null，领域历史读取宽容字符串；新日期严格校验，未修改的旧值兼容保留，不迁移旧文件。已有 issue/todo 转换保留稳定原 ID，todo 新深链接严格 TODO 前缀；旧 issue 链接兼容逻辑不收窄。
- 风险：扩大恢复路径必须仍限定 projects/<id>/todos/TODO-*.md；外部编辑器不遵守锁的剩余竞态保持。

### 2026-11-06 / AG-117 / 完成

- 文件：agent_service/tools/proposals/http、repository/http_api；navigation/app/agent-settings/index；test_agent_extensions、test_frontend_entry、test_agent_workflows、codex_agent_acceptance；AGENTS/README/架构/数据/维护/接入/使用和本台账。
- 实现：受显式授权的 todo 查询/搜索/分段读取、项目工作流、新建/正文追加/更新；日期严格新值和清空、推导 completed、附件/links/旧日期保留；TODO 深链接进入已有抽屉，不新增编辑器。
- 兼容决策：发现历史转换保留 ISSUE 编号；保留此类 todo 更新/恢复，不改 ID，回执不生成会被严格新链接拒绝的地址，用户从项目页打开。旧 issue 链接不收窄；业务 Markdown 无迁移。新日期按 YYYY-MM-DD/null，原旧值未改时保留。
- 验证：python -m unittest -q test_agent_extensions test_agent_proposals test_agent_recovery test_agent_api test_mcp_stdio 49 项通过，随后新增更新六阶段恢复/四线程重复提交后 test_agent_extensions 11 项复验通过；node test_frontend_entry.js、test_agent_workflows.js、test_agent_settings.js 通过；全 Python/JS 语法及 git diff --check 通过。
- 真实浏览器：三类型深链接/刷新、浅深主题×1440/390、可视化→Markdown→保存→重开、未保存取消、Agent/UI 冲突、保存期间继续输入和缺失/非法链接通过；临时数据与凭据。未修改编辑器保存内核，既有草稿流程保持。
- 真实 Codex：隔离脚本通过，codex-cli 0.163.0-alpha.10.2 / MCP 2025-11-25，12 工具与 issue/document/todo 新建、预览修改/确认/读取/幂等/重启/撤销；model_turns_started=0、user_config_changed=false。
- APP_VERSION=2026.11.06.2，受影响缓存同步。风险：外部编辑器写入竞态保留；info/local_web 未开放。提交标题 Enable scoped Agent todo workflows；下一入口 AG-118。

### 2026-11-06 / AG-118 / 开始

- 前置：AG-117 提交 f9f9568；工作区干净。
- 范围：info 无状态的查询与三操作、有序字段严格请求校验/完整预览/差异/恢复、INFO 深链接；不开放颜色和命令执行，更新保留原元数据。
- 代码事实冲突：共享 normalize_info_fields 目前截 100 项/名称120字符并 strip value/note，app 的 infoFieldsFrom 同样 strip；与方案 200项/200字符及首尾空格无损冲突。依据数据安全优先，本项同步修正共享读取/写入/前端收集器，保留旧字典宽容读取；不另建 Agent 序列化器。
- 预计文件：markdown_io、agent_service/tools/proposals/http、repository、navigation/app/agent-settings/index，扩展 Python/浏览器/Codex 测试与相关文档。
- 校准与限制：使用现有基线多行样本和临时200字段边界样本验证；严格 name≤200字符、value/note≤64KiB、正文+字段≤256KiB、请求≤1MiB，不提高正文上限。
- 验证：字段顺序/空格/换行/引号、重排/清空、旧字典和附件/颜色保留、仅正文追加、未知字段/超限/空字符拒绝；全 Python，真实四类型 Codex，记录/知识库编辑器保存重开/草稿/冲突、主题宽度矩阵，语法/diff。

### 2026-11-06 / AG-118 / 完成

- 实际文件：共享 markdown_io、agent_service/tools/proposals/http、repository/http_api；app/navigation/agent-settings/index；test_agent_extensions/workflows/front-end-entry/editor-workflows、codex_agent_acceptance；README/架构/数据/接入/使用/维护/验收及本台账。
- 实现：info 无状态三操作和查询、完整字段/有序差异、INFO 深链接；仅正文追加，字段未知键/类型/空字符严格拒绝，不开放颜色/执行；保持现有附件/links/颜色。共享归一化和前端收集器保留 value/note 首尾空格，扩至200项/200字符；value/note各64KiB、合计256KiB实测边界通过。旧字典继续读取，读取超限旧文件不截断，不能通过更新静默丢字段。
- 自动：python -m unittest -q 全量207项通过；扩展专项15项覆盖四类型授权/兼容、todo/info操作、字段边界/顺序/旧格式和故障恢复；全部 Python/JS 语法、Markdown链接/围栏和git diff --check通过；node test_frontend_entry.js通过。
- 真实 Codex：隔离脚本四类型通过，codex-cli 0.163.0-alpha.10.2 / MCP 2025-11-25，12工具，info字段原文比较通过；无模型 turn、未改用户配置。
- 真实 Edge：node test_agent_workflows.js四类型深链接/刷新、浅深×1440/390、可视化→Markdown→保存重开、保存期间新增输入保留草稿、info字段重排/首尾空格/草稿刷新恢复通过；node test_agent_settings.js通过；info桌面浅色/窄屏深色截图目视检查，未提交截图。
- 编辑器回归：首次 node test_editor_workflows.js 行为完成但临时Edge目录清理EPERM，命令失败，未记作通过；脚本增加Browser.close正常关闭与临时绝对目录断言后重跑成功（保存/失败重试/关闭/切页/刷新/两编辑器草稿恢复/历史/外部冲突）。不改应用保存内核。
- 兼容：无业务格式迁移，旧授权不扩权；APP_VERSION=2026.11.06.3和缓存同步。决策AG-DEC-007/009。提交标题 Enable lossless Agent info workflows；下一入口AG-119。
- 外部依赖：用户回复暂无非Codex客户端/身份服务/TLS远程测试环境；AG-121/122对应实测门槛待处理，继续本机项，不用模拟代替。

### 2026-11-06 / AG-119 / 开始

- 前置：AG-118 提交 db77326；工作区干净。
- 范围：本机管理会话下跨客户端分页/过滤摘要、详情/完整只读预览、持久幂等取消和结果打开；独立feature装配，批准按钮禁用直至AG-120。
- 文件：新增 agent_proposal_management.py、js/features/agent-proposals.js及测试；management_http/runtime/app/navigation/index/management.css；相关文档。
- 验证：管理会话/Origin/Agent凭据拒绝、未初始化只读无副作用；20默认/100上限/客户端类型状态操作筛选、不泄密；取消重试/并发/故障/旧版本/清理正文；真实浏览器两主题两宽度、长中文/空库/大量分页/error/focus/disabled/切页不丢草稿、既有管理回归。
- 影响：业务Markdown/编辑器/历史不变；新增.agent/proposal-actions取消日志，独立于凭据日志；读取详情不重放业务提交，committing状态显示恢复中，已有事务仍按原恢复流程处理。
- 风险：管理预览含完整私人候选正文，必须仅管理会话可读且静态不可访问；分页不能一次返回全部正文；未知日志不自动删除。

### 2026-11-06 / AG-119 / 完成

- 文件：新增agent_proposal_management、agent-proposals feature、test_agent_proposal_management/test_agent_proposal_workflows；修改management_http、proposals、http_api、app/navigation/index/management.css及README/架构/数据/接入/使用/维护和台账。
- 实现：设置内提案管理入口；跨客户端20项分页/最大100，客户端/类型/状态/操作筛选；按需完整内容/字段/多行原文/差异/警告/来源预览；清理后仅回执明确提示；未提交当前版本可取消，稳定request_id持久日志可重试/刷新查询；结果深链接打开。批准保持禁用。
- 边界：管理session/Origin/loopback复用，Agent Bearer拒绝；空空间只读不初始化。列表无正文、令牌/路径不返回；详情不自动重放业务提交。预览构造复用ProposalStore同一函数，取消复用状态机；业务Markdown/保存/历史/旧工具不变。
- 自动：python -m unittest -q全量213项通过；取消日志校验补强后管理/既有提案专项17项复验通过；全部Python/JS语法、Markdown链接/围栏、styles/frontend-entry契约与git diff --check通过。
- 真实Edge：新增提案浏览器空库/25项分页/筛选/完整多行预览/禁用批准/旧版本取消拒绝/取消丢响应/刷新同请求查询/会话失效/浅深×1440/390通过，多次复验；代表截图目视检查无页面溢出。node test_agent_settings.js与test_agent_workflows.js通过，临时数据/凭据/CODEX_HOME，未提交截图。
- 验收脚本修正：等待applicationFeature.start完成后导航，避免初始化回首页干扰早期点击；未将早期失败记作通过。
- APP_VERSION=2026.11.06.4及缓存同步。提交标题 Add local Agent proposal management；下一入口AG-120。外部依赖仍为用户暂无非Codex/远程测试环境，当前不阻塞本机实施。

### 2026-11-06 / AG-120 / 开始

- 前置：AG-119提交42d5f48，工作区干净。
- 范围：客户端最低确认策略/Agent只可收紧，schema2 local_web，管理会话内10分钟预览凭据绑定workspace/version/digest/策略/授权版本；网页确认后同引擎提交，持久批准操作日志和原事务关联，结果查询/幂等/故障恢复。
- 文件：security/management/service/proposals/proposal_management/runtime/management_http/tools、CLI/设置/提案UI/缓存/版本；专项与真实浏览器/Codex脚本及架构/格式/使用/维护/验收文档。
- 验证：Agent自报绕过拒绝、旧提案策略收紧改版、票据会话/版本/权限/目标/超时失效；撤销/收窄、并发/重复/丢响应、批准前/快照/manifest/applying/正文/回执各阶段中断及真实进程退出；四类型两路径与旧流程回归，全部门禁。
- 风险：批准不是现实身份认证；会话秘密不持久化，批准记录在写前落盘；只有完整批准+事务准备可恢复，未尝试写入时撤销阻断，已应用按磁盘完成回执，绝不重建被删目标。

### 2026-11-06 / AG-120 / 完成

- 文件：security/management/service/proposals/proposal_management/runtime/management_http/tools、server；设置/提案feature/index/http_api；新增test_agent_web_approval，扩展管理/浏览器/Codex测试；AGENTS/README/设置方案/架构/格式/接入/使用/维护/验收与台账。
- 实现：客户端最低确认策略与提案有效策略，旧客户端默认agent_attested；策略收紧升级未终结旧提案版本/摘要重新预览，降低不降低原local_web。Agent请求可收紧不可放宽，MCP自报确认不能绕过网页。
- 网页：完整预览后生成仅内存10分钟票据，绑定空间/会话/提案版本摘要/策略/授权版本；批准确认只传版本/摘要/票据/request_id，不传正文；按钮防重，失效后重新预览，响应丢失/刷新查原操作，sessionStorage仅原请求编号，不存票据和管理秘密。
- 持久化：先批准记录再同一领域预备写/ProposalStore事务，回执关联批准。批准日志无manifest标not_applied，不自动补写；完整manifest和批准才恢复。prepared撤销/收窄停止，applying按原磁盘事实判定，删除不重建；报告/abandon保留证据。恢复全程业务锁+可重入私人跨进程锁；启动即使关闭Agent也装配已存在空间的恢复上下文，恢复CLI尊重显式私人目录。
- 自动最终门禁：python -m unittest -v全量226项通过；补强旧schema1策略升级后单项通过；路由收窄后提案管理6项通过；57Python/45JS语法、Markdown链接/围栏、git diff --check通过。此前一轮223项中Windows子进程清理1项失败，专项4项重跑与最终226项通过，未把失败轮次写作通过。
- 恢复专项：13项独立批准测试涵盖四类型三操作、失效/伪造/不同会话票据、旧schema1改版、撤销/收窄/目标变化/过期、并发幂等、批准记录/提案/快照/manifest/applying/正文/回执各阶段、缺失证据拒绝、真实os._exit正文后恢复和真实CLI prepared恢复。相关web/recovery/runtime/startup30项复验通过。
- 真实浏览器：提案管理批准、丢响应刷新查询原回执、无秘密存储；浅深×1440/390、禁用/旧版/会话失效及取消回归；设置表单local_web保存落盘通过。全部19个Node契约通过，含四类型保存重开、两编辑器草稿/冲突/关闭/切页；截图仅临时目录。
- 真实Codex：codex-cli0.163.0-alpha.10.2/MCP2025-11-25，12工具、四类型旧对话确认回归；实际创建local_web→自报被拒→本机管理HTTP独立批准→MCP查询同一回执通过。model_turns_started=0、user_config_changed=false；不声称模型遵循规则或现实身份认证。
- 兼容：业务Markdown不迁移，旧凭据/旧摘要兼容；新批准日志schema2和回执字段为增量。APP_VERSION=2026.11.06.5与缓存同步。AG-DEC-008/009；外部编辑器剩余竞态保留。
- 提交标题 Enforce independent local web proposal approval；下一入口AG-121及可独立设计的AG-122。用户暂无非Codex/IdP/TLS环境，后续真实验收门槛如实记录，不跳过。

### 2026-11-06 / AG-121 / 开始

- 前置：AG-120提交eed7c2a，工作区干净。
- 范围：兼容矩阵、隔离配置/真实客户端验收步骤与未验证项；不增加应用运行依赖、不启动付费模型。
- 核查：用户明确回复“暂时没有”非Codex/远程测试环境；Get-Command claude/gemini/cursor/goose/cline无匹配，只证明这些CLI不在当前PATH，不声称扫描全部客户端或系统不存在安装。
- 文件：新增docs/AGENT_CLIENT_COMPATIBILITY.md，更新接入/维护/README/台账；脚本只在实际选择客户端/工具调用设施后适配，不能以自制客户端替代真实客户端。
- 验证计划：文档编码/围栏/相对链接/diff；现有真实Codex仅作为已实测对照，不计入非Codex验收。缺少可用真实非Codex客户端、版本和隔离调用设施，真实互操作部分不能运行。

### 2026-11-06 / AG-121 / 外部条件受阻

- 已交付独立可审查材料：docs/AGENT_CLIENT_COMPATIBILITY.md真实版本矩阵、隔离登记契约、四类型三操作/两确认路径/协议/故障验收和解除入口；接入/维护/README链接同步。
- 受阻证据：用户回复暂无目标客户端；当前PATH中的五个常见非Codex CLI未找到。未选择真实客户端，未安装依赖/登录账号/启动模型，不把Codex或自制MCP测试作为非Codex结果。
- 未运行：全部非Codex协议、四类型、网页批准及故障互操作。解除条件：可隔离配置和真实工具调用的非Codex程序/版本；若需安装/真实账号/费用，先审查具体依赖与授权。
- 文档变更验证：UTF-8/围栏/相对链接、矩阵状态、git diff --check；不借用旧运行结果。该独立文档交付可提交，本工作项仍受阻，下一可推进入口AG-122设计准备。

### 2026-11-06 / AG-122 / 开始

- 前置：AG-120完成；AG-121环境受阻，独立准备材料提交3e348f8；工作区干净。
- 范围：固定版本官方传输/授权规范核查、候选私网拓扑/主体映射/introspection/路由边界、威胁模型、协议验收与缺少环境决策；仅文档与只读规范查询，不安装依赖或部署远程入口。
- 文件：新增docs/AGENT_REMOTE_DESIGN.md，更新扩展方案/维护/接入/README/台账。
- 官方依据：MCP2025-11-25 transports/authorization/security/cancellation、RFC7662/9728；已通过官方页面实际读取，固定候选版本不称“最新”。
- 已知外部缺口：用户暂无IdP/TLS/真实远程客户端，未确定私网或公网、固定origin/证书、代理/issuer/introspection/客户端注册与撤销能力；未满足门槛前AG-123/124不启动。
- 验证计划：逐项官方契约映射、威胁与失败关闭/停用审阅、文档链接/围栏/diff；没有目标身份服务不能伪造探测或标设计完成。

### 2026-11-06 / AG-122 / 设计准备与外部门槛受阻

- 交付：docs/AGENT_REMOTE_DESIGN.md包含官方固定版本核查、候选私网拓扑/最小路由/身份内省/主体授权映射/强制local_web、会话SSE/取消/重连/幂等矩阵、资源初值、威胁模型和精确解除清单。
- 核查事实：实际读取MCP2025-11-25传输/授权/安全/取消与RFC7662/9728官方页面；区分规范必需与本项目额外部署要求（例如aud/sub/exp可验证性）。未宣称候选是最新或已互操作。
- 外部受阻：用户暂无真实IdP/TLS/客户端，网络范围/固定origin/证书/代理/issuer/introspection/客户端版本均未确定。真实令牌发行/内省/撤销与拓扑探测全部未运行，不能标设计门槛完成；AG-123/124不启动，不伪造基础设施。
- 解除：提供可隔离测试的固定TLS/代理、IdP元数据/内省/受众/撤销与真实客户端；确认目标网络。新依赖/费用/真实账号另准备可审查实际配置后决定。优先现有私网环境只是建议，不是已批准部署。
- 验证：官方契约交叉审阅、文档UTF-8/围栏/相对链接及git diff --check通过；纯文档不重复运行应用测试或借用本机验收声称远程成功。独立设计准备提交不等于AG-122完成。

### 2026-11-06 / AG-123～125 / 前置门槛受阻（未开工）

- AG-122明确要求真实IdP/证书代理/客户端可行性，用户暂无环境；AG-123身份授权实现、AG-124远程传输不能越过门槛开工，AG-125真实拓扑/停用依赖同样缺失。表格受阻不代表已开始代码实现，开始日期保持“—”。
- 解除依赖链：补齐AG-122实际测试环境并验证门槛→AG-123→AG-124；AG-121真实非Codex完成后方可完成AG-125。用户远程开发授权有效，无需重新询问是否继续；新付费/账号/依赖仍须具体决定。

### 2026-11-06 / AG-126 / 可独立验收范围开始

- 前置：本机AG-116～120已完成；AG-121/122及远程依赖如实受阻，不把全扩展交付标完成。
- 文件：新增隔离extension_lifecycle_acceptance.py和docs/AI_AGENT_EXTENSION_ACCEPTANCE.md；同步台账/README/维护/架构与文档入口。
- 范围：最终本机门禁证据审计、四类型与两确认路径的停服完整备份/重载、便携ZIP排除接入状态/恢复新身份、关闭Agent后普通UI仍可用；逐项记录远程和非Codex未运行项、提交与恢复入口。
- 计划：运行隔离生命周期脚本、Python全文件语法、Node语法、文档链接/围栏和diff；运行时代码在eed7c2a后未改动，已有226Python/19Node完整门禁与真实Codex/浏览器证据复核，新增脚本若暴露问题才修复并重跑相关门禁。

### 2026-11-06 / AG-126 / 本机交付审计与剩余外部门槛

- 新增extension_lifecycle_acceptance.py与AI_AGENT_EXTENSION_ACCEPTANCE.md，核对AG-116～126逐项状态/实际功能兼容/运行证据/本地提交/外部解除入口；相关文档入口与维护命令同步。
- 隔离演练实际通过：四类型×agent_attested/local_web共8条；关闭Agent API得到404而普通records/documents HTTP仍可读；停服复制业务与私人状态后逐条内容/revision/信息字段与批准回执恢复；便携ZIP CRC/无.agent/私人状态且恢复业务完整、启用后新workspace且无旧授权。real_user_data_changed=false。初次脚本缺少临时文档分类前置失败，显式创建分类后通过，未误记失败。
- 完整运行门禁证据：eed7c2a运行代码最终python -m unittest -v226项、全部19个Node契约、真实Codex四类型两路径与两编辑器/管理真实浏览器已通过；之后仅外部准备文档和隔离演练脚本，不修改应用运行代码，未无理由重复整套门禁。新增脚本及所有Python/JS语法、全部文档链接/围栏、目标diff和git diff --check通过。
- 受阻：非Codex实机、IdP/TLS/代理/真实远程拓扑及远程停用未运行，不能完成AG-121～125，也不能标AG-126全扩展交付完成。性能/视觉全量基线本轮未重跑，未外推旧数字；远程资源校准待真实环境。
- 本地提交审计：0953a07/f9f9568/db77326/42d5f48/eed7c2a为AG-116～120；3e348f8/87f2d84为AG-121/122独立准备，不声称受阻项完成。AG-126本机审计提交标题Record local extension acceptance and external gates；状态仍受阻。
- 后续入口：有真实非Codex环境先恢复AG-121；目标网络/origin/证书代理/IdP与受众撤销/客户端齐备后恢复AG-122门槛，依次123→124→125，最后126补齐全扩展验收。用户原开发授权有效，不重复询问是否继续。

### 2026-11-06 / 用户范围澄清 / 开始

- 用户说明通常只在一台电脑接入，不使用远程接入；按此明确用途将AG-122～125移出当前交付范围，不再要求用户提供IdP/TLS/代理或公网环境。
- 本次为文档范围调整，不修改应用代码、数据/API/凭据/保存链路；工作区核查干净，保留全部已提交实现和历史验收事实。
- 预计文件：台账、扩展方案/验收、README、远程设计及架构/接入/维护/执行规范中的当前范围说明；计划文档链接/围栏/状态一致性和diff检查。
- AG-121的非Codex本机客户端需求单独澄清，不能从“单机”推断“只用Codex”；在答复前不取消该项，不把未运行兼容验收写成通过。

### 2026-11-06 / 用户范围澄清 / 远程项取消

- 当前范围改为单台电脑本地接入；AG-122～125按用户明确“不使用远程接入”标为已取消，取消日期2026-11-06。AG-122既有设计准备作为历史参考保留，AG-123～125未启动实现；没有伪称远程实现或验收完成。
- AG-126不再依赖远程身份服务、TLS/代理/网络部署和远程停用演练。已完成本机功能与验收记录不变；AG-121是否保留由本机客户端需求决定，单机用途本身不排除其他客户端。
- 未新增端口、依赖或运行时能力，不改变业务数据/授权/草稿/历史/缓存版本；旧远程授权不再作为当前自动推进依据，未来确需远程时重新明确范围后恢复设计门槛。

### 2026-11-06 / 用户范围澄清 / 文档验证与提交

- 实际文件：AGENTS/README、扩展方案/验收/台账、远程设计、架构/接入/维护共9份Markdown，更新当前范围并保留旧执行历史。
- 检查：全部文档UTF-8/代码围栏/相对链接、AG-122～125取消状态一致性、git diff --check通过；目标diff审阅未夹带运行数据或用户修改。纯文档不重跑功能/UI测试，不改APP_VERSION和缓存。
- 提交标题Limit Agent extension delivery to local use；AG-121客户端选择仍待用户答复，未自动取消；AG-126已移除远程前置，仅按本机范围收口。

### 2026-11-06 / AG-121 / WorkBuddy 本机验收恢复

- 用户提供已安装的WorkBuddy；只读核查桌面版本5.1.5（文件版本），安装内附CodeBuddy CLI包发布版本2.103.3，实际CLI版本待执行核实。非Codex需求明确保留，远程AG-122～125仍取消。
- 范围：核实原装客户端隔离配置和直接MCP设施，使用临时工作目录、用户目录、配置、数据和凭据完成可运行的真实客户端检查；不登录真实账号、不调用付费模型、不修改正式配置。
- 预计文件：客户端隔离验收脚本、兼容矩阵、接入/使用/验收及本台账；若发现协议差异先记录再决定最小修复，不预设运行时变更。
- 验证：原装CLI版本/help与官方文档、真实stdio握手/工具目录/四类型两确认路径及故障矩阵；自动回归、文档与diff检查。已知风险：原装CLI是否支持无模型直接调用尚未核实；桌面安装本身不能证明互操作通过。

### 2026-11-06 / AG-121 / 原装CLI连接验证

- WorkBuddy桌面安装包版本5.1.5；附带原装CodeBuddy CLI实际执行--version为2.103.3。新增workbuddy_agent_acceptance.py，使用环境白名单及独立HOME/USERPROFILE/APPDATA/LOCALAPPDATA/配置/缓存/工作目录、临时服务/凭据；无需安装依赖。
- 原装CLI执行mcp list，字节透明中继只记录方法/版本/工具名称元数据，不生成请求或替代客户端。实际观察initialize(2025-11-25)→notifications/initialized→tools/list，12工具，CLI Connected、退出0、无协议错误、无模型turn，临时令牌未进入stdout/stderr；客户端自报name来自登记名，不能作为厂商身份凭据。
- 初次脚本清理误用了不存在的撤销方法，随后Windows后代进程持有cwd/编译缓存导致清理失败；修正为change_client并用Windows kill-on-close Job绑定本次客户端后代、有限重试临时目录清理，修正后两次连接执行通过。失败轮次未算通过；未操作正式WorkBuddy配置。
- 已核对官方WorkBuddy MCP文档：桌面配置路径与随附CLI不同，不能把临时CLI连接外推为桌面任务或写入矩阵通过。未找到公开无模型直接调用入口，四类型三操作/两确认路径等仍未运行。
- 用户回复有测试账号/额度、可准备隔离会话；继续准备具体独立测试会话，不复制正式认证资料，不自动登录或发起付费模型调用。AG-121保持进行中，AG-126待完整本机兼容验收。

### 2026-11-06 / AG-121 / 隔离客户端进程回收修正范围

- 本轮全量226项中test_codex_fixture_reaps_windows_descendants_and_inherited_pipes再次出现Windows后代持有管道/cwd错误，其余225项通过。这与前轮记录的瞬态失败相同，不能以重跑掩盖。
- 扩展当前验收基础设施范围：提取仅供显式验收脚本使用的acceptance_process.py Job辅助，Codex/WorkBuddy共享kill-on-close后代回收；新增父进程先退出场景，避免taskkill只能依赖仍存活父进程的竞态。不修改应用模块边界、API或数据。预计文件：两客户端脚本、验收进程辅助、test_startup与本台账。
- 验证计划：启动专项、真实Codex/WorkBuddy连接和全量Python门禁；保持模型turn为0，脚本错误如实记录。

### 2026-11-06 / AG-121 / 桌面账号与隔离边界核实

- 原装CLI --serve临时Web UI健康检查通过；用户确认无登录/模型配置入口，只有WorkBuddy桌面账号额度。安装内iam.md要求独立API Key/OAuth token；此前将Web UI当作登录入口的判断不准确，未进行模型调用。该临时会话已停止、进程回收且目录清理，移除--session误导入口。
- 浏览器自动化返回Work设置禁用，未冒充UI验收；没有绕过到其他自动化技术。
- 新增--desktop-session仅准备临时工作台/候选项目MCP文件，不启动桌面或模型。用户已明确允许已有桌面的一次性项目测试（手动最多8轮），可能留下任务/最近项目历史；不读取认证、不改全局MCP、不自动付费。当前第一轮只读发现待用户操作，完整矩阵仍未通过。
- 全量门禁初次226项出现旧Windows后代清理错误，修复后最终227项通过；启动专项5项、真实Codex四类型/两方式、原装WorkBuddy CLI连接/12工具、生命周期脚本重跑通过；60Python/45JS语法和28Markdown编码/围栏/相对链接通过。应用运行时/数据/API/缓存版本未变化。
- 自动审批拒绝递归清理早期失败探测的三个临时目录（工具仅返回blocked by policy，无更具体原因）；正常会话清理已通过。遗留仅本任务临时目录basename：workbench-workbuddy-probe-2c2xum8z、workbench-workbuddy-probe-8yt3_klz、workbench-workbuddy-probe-___et8c4，位于系统TEMP；不能记录为已清理，不提交目录/凭据。

### 2026-11-06 / AG-121 / 可独立验证的连接子项提交

- 实际文件：workbuddy_agent_acceptance.py、acceptance_process.py、codex_agent_acceptance.py、test_startup.py；README、兼容矩阵、接入/维护、扩展方案/验收及首期验收的当前状态说明。完成新增桌面项目夹具HTTP/两份候选配置一致性/STOP撤销清理验证；最新原装CLI连接再次通过。透明中继无法解析的消息仍原样转发，只记unparsed，不替代服务协议处理。
- 目标diff和git diff --check通过，未夹带用户修改、运行库、配置、凭据、截图、日志或机器绝对路径；本地提交标题Probe WorkBuddy MCP in isolated test projects。该子项可独立验证，不标AG-121完成；当前下一入口为用户已授权的桌面临时项目只读工具发现，再完成完整矩阵，AG-126依赖保留。

### 2026-11-06 / AG-121 / 提交后检查纠正

- 连接子项提交5965316。首次暂存diff检查提示新增acceptance_process.py末尾多余空行；PowerShell命令串未按非零返回码停止，导致仍提交，前条“diff检查通过”不适用于该轮暂存检查。现去除该空行，以独立修正提交保留事实，不amend已有提交；未改变行为，复核git diff --check及暂存diff --check通过后提交。当前工作区无用户既有修改。

### 2026-11-06 / AG-121 / 桌面第一轮未通过与登记候选

- 用户提供WorkBuddy详细原文，覆盖此前“工具已调用”的简短答复：实际未进行验收工具调用；capabilities/list_projects/四类型get_catalog均未加载，会话工具名检索无workbench_probe，连接器无已启用条目。第一轮记未通过，不记为空数据查询成功；已消耗1轮手动任务，后续最多7轮，尚无自动模型调用授权。
- 必要原文摘录（来自用户转述的客户端报告，不作为服务端调用证据）：

```text
结论：无法执行，工具未加载
按要求仅做了工具可用性核查，未进行任何验收调用。
当前连接器状态中同样没有已启用的 workbench_probe 条目。
未读取任何本机文件、未执行任何命令、未创建或提交任何提案、未修改全局配置（含 MCP 配置）。
```

- 独立核查：本次临时工作台/api/projects仍返回唯一测试项目；protocol.jsonl不存在，未观察到桌面initialize或tools/list。资源列表count=0不是单独的失败依据，工作台本来只声明tools能力。项目候选文件未在本次桌面任务生效；不能外推为所有WorkBuddy版本不支持项目配置或MCP协议不兼容。
- 已只读核查安装内桌面主模块的CLI参数拼装：存在--mcp-config配合--strict-mcp-config的注入路径；这是配置注入差异线索，不等于已证明当前会话具体参数或根因。没有读取真实客户端配置、日志或登录资料。
- 下一可审查方案：生成仅含workbench_probe的WORKBUDDY_MCP_REVIEW.json于本任务TEMP根，不含令牌正文，只含已核实Python/中继程序/临时凭据文件位置；临时服务和凭据仍有效。由用户在桌面连接器界面仅新增并启用该临时条目，不替换既有配置；同名差异先停，结束撤销临时凭据并移除此条目。此方案尚未执行。
- 原授权仅桌面临时项目和任务/最近项目历史例外，不包含全局MCP登记；需用户明确是否允许这项新增临时条目。账号/模型仍沿用用户手动，最多剩余7轮；不重复申请已授权开发操作。AG-121保持进行中，AG-126继续等待完整兼容证据，远程项仍取消。
- 本次只改台账/兼容矩阵/扩展验收三份文档；计划UTF-8/围栏/相对链接、目标diff和git diff --check。无运行时代码/数据/API/资源缓存变更，无需重跑此前227项或声称新的UI通过。

- 文档实际验证：三文件UTF-8/围栏/相对链接通过，目标diff已审阅；git diff --check及暂存diff --check通过后本地提交，标题Record failed WorkBuddy desktop tool discovery。只更新真实失败证据与待决定入口，不宣称兼容通过。

### 2026-11-06 / AG-121 / 临时连接器例外已授权

- 用户明确回复“允许新增该临时连接器”，授权其在WorkBuddy连接器管理手工新增并启用已展示完整配置的workbench_probe；仅本任务临时库/凭据，验收后移除，不覆盖其他条目、不读取认证、不自动模型调用。原桌面手动最多8轮的边界不变（首轮失败，最多余7轮）。该授权仅解除登记前置，不能记为已登记或已连接。
- 开始前git status --short干净；重新核实临时服务HTTP返回唯一测试项目、审查文件仍存在；仍没有protocol.jsonl。已给出仅合并新条目、不整份覆盖和同名差异保留的步骤；等待实际连接状态，先观察握手/12工具，不消耗新的模型任务。
- 本次预计仅更新台账、兼容矩阵与扩展验收中的授权状态/实际证据；文档检查与diff验证后独立提交。不新增运行时代码、数据/API或版本变更，不将未运行验收标为通过。

### 2026-11-06 / AG-121 / 桌面真实调用与部分持久化证据

- 用户报告临时连接器连接成功、已开始发送任务。活跃夹具进程句柄重新轮询仍运行；中继实际记录MCP2025-11-25握手、initialized、12工具及ping，clientInfo为connector:custom-mcp:workbench_probe/1.0.0。此前未连接是历史失败轮，当前已解除连接前置，无需以重启替代核查。
- 快照53次真实tools/call（查询/提案/预览/提交/读取），其中prepare6、preview4、commit4；一次notifications/cancelled。临时磁盘4份提案均create/committed、agent_attested、version=previewed_version=1，4份回执与正式Markdown对应ISSUE-0001、TODO-0001、INFO-0001、INFO-0002；知识库尚无正式文件。不读取真实任务历史/认证，不将查询调用次数当作四类型目录覆盖或所有调用成功（中继不记录参数/工具isError）。
- 已集中请求用户反馈实际任务轮数、完整预览展示与后续新消息确认、其他已测试矩阵；持久回执本身不能证明人类确认。未自动发送模型任务，不擅自增加8轮额度。AG-121仍进行中，AG-126仍待完整兼容；本次仅同步三份文档，验证编码/围栏/链接及diff后提交。

- 实际检查：三份文档UTF-8/围栏/相对链接通过，目标diff已审阅、git diff --check通过；本次无运行时代码修改，不复跑或新增宣称全量/浏览器验收。本地提交标题Record real WorkBuddy desktop MCP calls；等待用户报告后继续剩余矩阵。

### 2026-11-06 / AG-121 / 八轮额度边界与剩余验收

- 用户报告“添加问题、待办、信息都成功”，附件因没有接口失败；随后明确累计8轮。此前授权的手动任务额度已用满，不安排第9轮，不自动调用模型。用户尚未回答完整预览后是否另发确认，保持待核实。附件写入在扩展方案明确排除，属于功能范围限制，不作为协议故障、不临时扩展上传工具。
- 本轮开始前工作区干净；只读重读4份正式Markdown，用现有解析器核对正文及title/status/priority/tags/completed/due/info_fields等候选开放字段，均一致；每份原始文件SHA256等于持久回执revision。未改临时业务数据，无知识库/追加/更新或local_web的新证据。
- 精确范围：仅更新使用说明的附件边界、兼容矩阵的实际用户反馈/补验安排、扩展验收及本台账；运行四份文档编码/围栏/链接、diff检查后独立提交。补验拟最多新增8轮手动任务，批量四类型三操作、两确认路径与故障；需用户决定新额度，未执行。现有服务寿命上限不延长；若退出先确认终态，不自动重建或复制正式配置。

- 文档实际检查：四文件UTF-8/围栏/相对链接通过、目标diff已审阅、git diff --check通过；仅文档，无运行时/API/资源版本改变。本地提交标题Record WorkBuddy trial limits and remaining checks。下一入口为用户对新增手动额度的决定；原8轮结果不升级为完整兼容通过。

### 2026-11-06 / AG-121 / 补验恢复

- 用户对新增最多8轮的具体补验请求回复“我有很多额度可以用来测试”，据此继续该批手动补验，不重复询问；仍不自动调用模型、不读取正式认证或改其他连接器。原确认过程尚待核实。
- 开始前工作区干净，原临时夹具进程仍运行、HTTP200；调用数仍53，正式条目仍4份create。下一实际任务为知识库create及issue/todo/info各append，完整预览4份后停止，不把本轮原始请求当作确认。
- 当前夹具仍按原2小时上限自然退出；开始时间已从本任务进程核实，截止前不宣称重启/恢复通过，若到期先核实终态并重新准备隔离环境，不重放不确定提交。本轮仅更新台账授权与入口，文档及diff检查后独立提交。

### 2026-11-06 / AG-121 / 补验第一轮真实预览

- 本轮开始前工作区干净；原夹具句柄仍活跃。实际新增客户端请求产生4份previewed提案：document/create v1、issue/append v2、todo/append v1、info/append v1；问题提案发生一次revise并重新预览。持久回执仍4份、commit调用仍4次，没有把本轮原始请求视为提交确认。
- 只读核对三份append的候选正文均保留base_content正文前缀并包含追加验收文本；base_content所有非正文开放字段均一致，包含due与info_fields。初次临时断言错误地要求候选的派生completed也存在于base_content，失败后查明base_content不含该字段，agent_service按状态派生False；按实际契约复核通过，未修改代码或把首次断言记通过。
- 精确范围仅同步本台账与兼容矩阵的实际预览证据；文档/目标diff检查后提交。已请求用户核实4份完整预览是否实际展示，特别是问题v2；尚未获得确认、不代替用户调用commit，不标agent_attested或append落盘通过。下一入口为用户查看最新预览后的新消息确认。

### 2026-11-06 / AG-121 / 预览展示确认与临时会话到期

- 用户明确反馈4份完整预览均已展示，仅证明已展示，不视为已批准提交。原夹具句柄随后返回退出码0，达到原2小时上限；尚无该批commit，不能记为计划内断线恢复通过。
- 到期前已在另一个本任务TEMP目录保存data与private的受限恢复副本：使用现有private_directory设置仅当前用户访问，排除进程锁文件，复制前后源文件清单/哈希不变、目标38文件哈希一致。只含本次隔离数据和一次性凭据，未读取正式客户端配置/认证，不进Git；副本basename为workbench-workbuddy-recovery-0q5zwp5r。尚未恢复、不记备份恢复验收通过。
- 下一范围：使用该副本准备同一测试身份的续验服务，服务开放前轮换旧测试凭据；仅生成新的临时连接器完整项供用户手工更新本次条目，不操作真实配置。先核对4份原回执/4份待确认提案和旧令牌拒绝，真实客户端复连后重新查询/预览，再由用户新消息确认。夹具代码仅放本任务TEMP，不加入应用运行时，不替代MCP客户端。计划本机HTTP/持久状态/轮换拒绝检查和文档diff检查，未知结果如实保留。

- 实际续验准备：在受限副本的live子目录恢复38文件，临时Python夹具复用真实Repository/AgentSecurity/AgentService/AgentRuntime/HTTP Server，无自制MCP客户端、无模型调用；服务开放前rotate原测试身份，并实际验证旧令牌unauthenticated。同一loopback端口HTTP200，8份提案与4份回执逐字节等于恢复源，4份待确认提案保持原版本。
- 实施调整：原夹具正常退出并清理后，重建仅该任务原TEMP目录中的私人配置别名，指向新续验服务（同一URL/身份、新令牌）；private_directory限制访问，别名与新配置逐字节一致。原桌面连接器的程序/参数/env不变，用户只需重新连接，无需额外修改桌面配置；不是读取或覆盖真实客户端配置。旧目录现在仅为本任务重新创建的别名/协议元数据，需收尾清理；恢复副本/live也需最终撤销并清理。新版临时夹具保留文件以供核证，不宣称自动清理已完成。
- 用户已核实4份完整预览展示；仍需在WorkBuddy后续新消息明确确认当前版本才能提交。恢复只属于开发侧夹具核对，真实客户端复连/查询/提交与独立网页批准尚待执行，AG-121不标完成。本轮两份文档编码/围栏/链接及diff检查后本地提交，运行时/数据契约/缓存版本未变化。

### 2026-11-06 / AG-121 / 工具结果元数据补强范围

- 开始前工作区干净。续验实际已观察桌面重新initialize/initialized/12工具，尚无该批提交请求；夹具句柄仍运行。真实复连证据与原自然到期区分记录，不外推为完整故障矩阵。
- 现有中继仅记录调用名与JSON-RPC错误，无法区分工具业务isError；补强验收元数据，仅按请求ID在内存关联工具名、记录响应的isError布尔，不落盘ID、参数、正文、结构化业务结果或凭据。请求关联有界，丢失关联也不改变字节转发。
- 预计文件：workbuddy_agent_acceptance.py、对应安全/关联专项测试、兼容矩阵和台账；应用运行时、协议Schema、数据和缓存版本不变。验证计划：元数据不泄密/成功与业务错误/交错响应/关联上限，原装CLI无模型连接、Python语法和diff；当前已运行桌面中继不热替换，下一次正常重连才会使用新记录，不伪称已有结果字段。

- 实际专项：python -m unittest -v test_workbuddy_acceptance共3项通过，验证交错响应关联、不记录业务/秘密/请求ID、输入不变、业务isError与JSON-RPC错误/畸形标志区分，以及256项有界关联。两脚本py_compile通过；原装CLI2.103.3无模型连接重跑通过（MCP2025-11-25、12工具、退出0、未修改正式配置）。已启动全量Python门禁，尚未出结果。该专项只验证验收中继，不替代真实客户端业务错误验收。

- 全量实际结果：python -m unittest -v共230项通过（124.638秒）；61个Python文件py_compile通过。应用运行时未改，无新增UI验收声明；原来的227项历史不改写，新增3项为验收元数据安全专项。后续客户端结果仍须来自真实桌面，当前旧中继不会产生新的tool_is_error字段。

- 补充检查：45个JavaScript文件node --check通过；两份文档UTF-8/围栏/相对链接及目标diff、git diff --check复核通过后提交，标题Trace WorkBuddy tool outcomes without business content。只提交中继、3项专项测试和两份文档，不包含临时恢复副本、配置、日志或凭据；AG-121仍进行中。

### 2026-11-06 / AG-121 / 补验第二轮提交与四类型更新预览

- 开始前工作区干净；用户答复尚未发送、将手动发送，随后真实桌面请求到达。新中继已在正常重连后实际记录工具响应：get_proposal4、commit4、get_item4、prepare4、preview4均tool_is_error=false。不能仅凭时间关系推断人类确认，已请求用户核实是否在手动发送此前给出的新消息确认之后提交。
- 实际落盘：原document/create v1及issue/append v2、todo/append v1、info/append v1均committed，回执从4增至8。DOC-0001新建、ISSUE-0001/TODO-0001/INFO-0001追加后，逐文件重读正文及开放元数据并核对SHA256等于最新回执revision，全部通过；INFO-0002原记录仍匹配其原回执。
- 四份update均已预览v1、未提交，包含更新验收正文；info_fields候选等于原有字段逆序，值/备注未变，其他字段保留。已集中请求用户核对4份完整更新预览展示，不代替后续明确确认。
- 本次仅同步台账、兼容矩阵与扩展验收的上述真实证据；计划三文件UTF-8/围栏/链接、目标diff与diff检查后提交。AG-121仍进行中，剩余知识库append、四类型update落盘、local_web和故障矩阵不外推通过；下一入口为用户确认更新预览展示及上一轮新消息确认。

- 用户明确确认4份update完整预览均已展示；关于上一轮新消息确认选择“不是或需要说明”，进一步提供的是WorkBuddy执行报告而非其原始确认消息。必要原文：“已按确认执行。全程仅使用 MCP 工具。”“以上为 4 份 update 提案的完整服务端预览。这 4 份均未提交”。报告的回执、版本/摘要及info_fields逆序与临时服务事实相符，但客户端自报不能独立证明人工确认，旧轮次确认过程保留未核实，不推断为已通过或确定绕过。
- 报告沿用prepare返回的draft描述；当前磁盘与实际preview调用证明四份均previewed，不将客户端该静态描述当作当前服务状态。下一轮安排用户在完整更新预览之后手动发送新的明确确认，提交4份update；随后准备四类型local_web append，既补齐知识库append，又验证独立网页批准（不额外创建一批无关正式条目）。客户端自报提交仅作为预期拒绝的负向测试，正式落盘须网页操作者批准；具体仍由真实客户端/网页执行，不由开发夹具代替。

- 本次实际检查：三份文档UTF-8/围栏/相对链接与目标diff复核、git diff --check后提交，标题Record WorkBuddy writes and pending confirmation evidence；仅文档，不新增声称全量或UI结果，不夹带临时状态/凭据。

### 2026-11-06 / AG-121 / 四类型更新落盘与网页批准前置

- 本轮开始前工作区干净。用户对“确认4份update，再准备4份local_web追加”的指定任务明确回复已发送、正在执行；此前已核实4份update完整展示。真实桌面随后查询4份原update并提交，四类型v1均committed，工具响应均非错误，回执从8增至12。本轮具备用户所述的新消息确认与实际往返证据，不补推此前未核实的历史确认。
- 逐份重读四类型update正式Markdown，SHA256匹配回执revision，正文及开放元数据与候选一致，末尾更新验收文本保留；INFO-0001的6项info_fields等于原字段完全逆序、值/备注保留，全部通过。
- 随后真实客户端生成四类型local_web/append v1，均previewed；四次客户端自报确认commit均tool_is_error=true。四份提案approval/receipt均空，持久回执仍12，尚无网页批准。错误码和客户端完整展示已请求用户报告，不能仅从isError推断confirmation_required。
- 精确范围仅同步台账/兼容矩阵/扩展验收，文档与diff检查后提交。下一入口为用户核实拒绝错误码，并在临时网页“设置→AI Agent接入→提案管理”逐份重新读取完整预览后独立批准；开发夹具不发管理批准请求。知识库append尚未落盘，local_web正向和其余故障矩阵仍未通过。

- 用户确认4份local_web完整预览均已展示、4次均confirmation_required，并提供客户端错误表：message为“此提案需要在本机提案管理中独立批准”，retryable=false，无成功item_id/revision；客户端报告未重试、未重建。该报告与4次工具isError、4份空批准/回执和仍12份正式回执一致，四类型自报绕过拒绝通过。
- 已给出临时网页独立操作步骤并请求实际结果；原夹具句柄仍运行，页面HTTP200，当前proposal-actions为0，4份local_web仍previewed。未通过管理API代替用户批准。本次三文件文档编码/围栏/链接与目标diff检查后提交，标题Verify WorkBuddy updates and independent approval rejection；网页正向仍待真实操作，不标本项完成。

### 2026-11-06 / AG-121 / 查询权限对照准备

- 开始前工作区干净。精确范围：通过当前一次性工作台的普通HTTP领域API创建一个未授权对照项目/issue，验证其不在临时客户端project_ids中；只读回检并在任务TEMP保存对照ID。用于后续真实客户端分页/分段、越权读取与引用负向验收，不替代客户端请求、不改变客户端授权、不写真实workbench-data。
- 不改应用代码或真实配置，不修改已有四份待网页批准提案的目标；计划普通API创建/磁盘重读/授权不含对照项目检查，实际结果再记录。后续具体查询矩阵可在网页批准后的手动轮次执行；网页批准仍等待用户真实操作。

- 对照准备实际通过：普通临时HTTP API返回201，建立WorkBuddy-未授权对照/ISSUE-0002，正文为固定验收canary；磁盘重读存在，临时客户端project_ids不含该项目，授权未修改。ID仅保存在本任务TEMP的query_fixture.json；这不是MCP越权验收通过，仍待真实客户端读取/引用拒绝。

### 2026-11-06 / AG-121 / 四类型独立网页批准落盘

- 用户明确报告4份均已在网页批准并入库；临时磁盘证据对应4份local_web/append v1均committed、approval.mode=local_web，proposal-actions恰好4份completed，回执由12增至16。开发夹具未请求批准路由，没有替代操作者。
- 逐份核对批准日志、提案与回执版本相同，批准preview_digest等于当前提案摘要，action.approval与proposal.approval一致；四份正式文件SHA256匹配回执，正文/开放字段匹配候选且末尾为网页批准验收文本。知识库append也已落盘；四类型三操作均有真实客户端/网页落盘证据。网页操作仅此人工批准流程，未外推为新的主题/宽度/编辑器冲突验收。
- 当前剩余：由WorkBuddy查询网页回执/幂等、分页分段/范围与引用拒绝、未知字段、修改后旧版本拒绝/取消、重启与撤销/轮换/错空间等矩阵。三份文档同步实际结果，计划编码/围栏/链接/目标diff及diff检查后提交；AG-121仍进行中、AG-126未收口，不缩减剩余要求。

### 2026-11-06 / AG-121 / 显式协议故障探针准备

- 开始前工作区干净；当前真实桌面已查询网页4份提案并重复提交4次，回执仍16，分页/权限任务继续执行。该业务轮次不受协议探针开发影响，当前中继不热替换。
- 精确范围：为显式验收脚本增加可选protocol-faults模式，仅在initialized之后注入固定服务端ping与不存在方法，观察真实客户端空结果及-32601响应；不构造客户端消息、不执行业务写入，不改变默认逐字节转发。合成服务端请求和消费对应回复必须单独标注，不能混作真实服务主动请求或业务成功。超时有界，其他字节原样转发。
- 已核对MCP2025-11-25 ping与JSON-RPC官方规范；预计workbuddy_agent_acceptance.py、安全/协议专项测试、兼容矩阵和台账。计划原装CLI无模型实测默认/故障模式、专项/语法与全量门禁；桌面模式须用户手工更新仅此临时连接器的已展示完整新项并重连，未执行前不把CLI结果外推桌面。

- 实际专项5项通过：原3项元数据安全检查、新2项探针自身回复隔离/畸形回复不算成功检查。原装CLI2.103.3显式模式实际返回ping空结果与未知方法-32601，fixture_reply均valid、12工具、Connected/退出0，无模型turn、未修改正式配置；默认模式重跑通过且无fixture回复。两Python脚本语法通过，全量Python门禁已启动，尚未出结果。默认中继没有注入；桌面当前未运行该模式，不能混用CLI和桌面证据。

- 全量实际结果：232项Python测试通过（117.186秒），两脚本py_compile及两文档UTF-8/围栏/相对链接、目标diff/diff检查通过后提交，标题Probe real client server-request handling explicitly。临时完整连接器候选已准备，仅在原--relay参数后增加--protocol-faults，私人配置/trace仍用同一任务位置，不含令牌正文；尚未要求桌面热替换、未自动修改登记。当前桌面业务查询证据将在独立记录提交中同步，避免把CLI协议结果混作桌面结果。

- 最终审阅增加未知方法错误码必须为整数的校验（不把-32601.0当作符合JSON-RPC整数契约）；5项专项与原装CLI显式探针重跑通过，全量再次232项通过（215.104秒）。两脚本语法、两文档和目标diff/diff检查复核通过。现已把完整候选展示给用户，要求仅给本次临时连接器追加该标志并手工重连；桌面结果仍待观察，无自动登记或模型调用。仅提交验收脚本/专项和两份文档，不夹带TEMP恢复状态、配置或日志。

### 2026-11-06 / AG-121 / 查询与幂等真实客户端结果

- 开始前工作区干净。用户提供第四轮完整报告，真实中继对应4次get_proposal、4次重复commit均非错误；四份local_web提案committed、批准/回执存在且current_item未变化，重放的ID/revision/committed_at/approval等于原回执，持久回执仍16，无新写入。
- capabilities与四类型catalog、授权项目列表已实测；当前仅可见一个授权项目/一个知识分类。list_proposals两页各3项、游标3→6，search两页3/2项、游标3→null，ID不重复；未授权对照项目/ISSUE-0002检索为空，目录和读取返回not_found，正文引用返回invalid_reference，info append附加status返回unknown_field。三个业务拒绝与真实工具isError记录一致，无绕过或重建。
- INFO-0001以length128从offset0/128/256/384/512/640读取，最后next_offset=null，总707字符；已将用户转述的完整拼接原文作为数据逐字比对磁盘正文，一致，文件SHA256等于报告revision 20c53bdbad614cb1ce466005317b0b8589520ae5201fa93e4807762a94f0c190。正文中的旧“尚未提交”等历史文字仅作为原文保留，不当作当前提案状态。
- 专用取消候选2eaf109c-ed37-43a6-b284-a29bf39d6613 v1预览摘要与报告一致；请求省略info_fields后候选仍保留原6项，未提交。已给出第五轮原样request_id重放/冲突、显式清空字段、旧版本拒绝及取消任务。实际观察候选已变v2、info_fields为空、state=cancelled，正式INFO-0001仍上述revision及6字段、回执16；具体错误码和客户端新预览展示待用户报告，暂不外推相关错误通过。
- 精确范围仅同步台账/兼容矩阵/扩展验收中的以上实测；文档和diff检查后提交。剩余协议桌面探针、取消错误细节、重启/轮换/撤销/错空间等继续推进，AG-121仍进行中。

- 用户提供第五轮实际摘要：原样prepare重放返回同一v1/摘要，复用request_id仅改body为idempotency_conflict；修订后的旧v1提交version_conflict，已取消v2提交invalid_state，均retryable=false，无成功回执。与中继prepare成功/错误、revise/preview/cancel成功、两次提交错误及磁盘v2 cancelled一致。正式INFO-0001仍原revision与6项字段；字段清空仅候选有效，不声称清空已正式落盘。此项完成了prepare幂等对照、旧确认失效和取消流程，丢响应/重启等故障仍未实测。
- 扩展本次文档同步到README、接入和维护中已过时的“仅连接/桌面读写未验收”说明，只声明已实测的四类型三操作、两确认路径和查询/取消子集；完整矩阵仍进行中。新增显式协议命令如实标注故障模式，不改变架构/数据契约/版本；计划六份文档编码/围栏/链接与目标diff/diff检查后本地提交。

### 2026-11-07 / AG-121 / 新对话交接入口

- 用户明确要求另起对话接续同一目标，不缩减范围。六份当前未提交修改均为本任务查询/幂等/取消验收与使用状态文档，已逐份通过UTF-8/围栏/相对链接、目标diff及diff检查；交接前再次核对后提交，标题Record WorkBuddy query and cancellation acceptance。不提交临时状态、凭据、协议日志或机器绝对路径。
- 桌面协议探针未完成：用户报告已加标志并重连成功，但实际trace无fixture_request/fixture_reply；当时只读核查该中继进程参数没有--protocol-faults。初次结果断言失败已保留，随后核查确定是模式未运行，不是未知方法响应已失败或通过；不能将CLI通过外推桌面，也不推断具体UI配置根因。待新对话核实完整临时新项如何真正生效，不读取/覆盖正式客户端配置。
- 交接时原统一执行句柄已缺失；独立核查原续验夹具进程不存在、旧loopback端口连接失败，私人注册表测试客户端enabled=false，证明服务已停止且旧凭据撤销。受限TEMP恢复副本仍有16份回执、已取消v2候选及业务文件；不把状态文件存在当活跃进程，不在本对话自动重启。原临时别名和副本均需最终清理，早期清理审批拒绝的三个目录仍按前文保留事实。
- 下一入口：新对话先读最新AGENTS/方案/台账并git status，复核剩余协议/认证/故障矩阵；恢复新隔离服务时不得静默复活已撤销凭据，准备必要的临时新项供手工连接。继续真实WorkBuddy验收、最终完整门禁与AG-126交付审计。已验证子集不重做，未运行项不标通过；AG-121保持进行中、AG-126待收口、远程AG-122～125仍取消。

### 2026-11-07 / AG-121 / 新隔离身份续验开始

- 开始前git status --short干净，HEAD为30af32e。已核对当前方案、设置方案、架构/数据/维护、兼容矩阵和验收记录；这是AG-121续验，不是RF重构。文档顶部部分摘要仍停留首轮，和末尾实际记录不符，后续同步现状，历史记录保留。
- 精确范围：审阅旧夹具后另建受限TEMP续验环境，从最新live复制测试数据/私人状态并核对哈希；旧客户端保持撤销，另发仅本次测试的新身份（同等范围、无扩权）。旧16份回执保留核证，不修改归属或冒称新身份可查旧提案。新完整连接器项显式带--protocol-faults，供用户仅替换此次临时连接器；不读/自动修改真实配置、不调用模型。
- 预计仓库文件：台账、兼容矩阵、扩展验收；必要故障验收设施另登记精确范围。临时夹具不进Git。计划先核对旧服务停止/旧身份禁用、新副本哈希及HTTP，再观察真实桌面实际argv和fixture回复；等待人工重连时推进最终自动门禁。剩余取消/断连、重启/丢响应、认证/legacy交集/限流及结果链接逐项如实记录，不由开发侧探针替代客户端或网页批准。
- 影响面：应用运行时、业务Markdown/HTTP/MCP契约、草稿/历史、UI与缓存版本不变。风险是桌面仍沿用旧条目、旧凭据失效与服务到期；不能把连接提示或文件存在当有效协议证据。新夹具有界到期撤销，最终仍须移除临时连接器并清理任务TEMP（既有清理审批拒绝不绕过）。

- 实际恢复：新受限TEMP副本复制114个最新live文件，复制后逐份哈希核对且源未变化；16份历史回执保留。旧测试客户端仍enabled=false，并实际验证其旧令牌unauthenticated；新建同范围身份，未绕过“撤销后不得启用”规则，未改旧提案归属。新服务HTTP200，有2小时上限、STOP和最终撤销；临时basename为workbench-workbuddy-continuation-j86v1htb，旧恢复副本和别名未删除，最终均需收尾。
- 用户报告新完整项已替换并保存重连，但随后OS实际中继仍仅--relay，新trace尚未生成。仍不能认定模式运行；已请求仅核对程序/参数两个字段（不要求认证或秘密），不通过读取真实配置代替。
- 本轮实际自动检查：232项Python通过（148.840秒），61Python/45JS语法通过；真实Codex0.163.0-alpha.10.2/MCP2025-11-25、12工具、四类型/两确认/重启撤销通过，无模型turn/真实配置修改；extension_lifecycle_acceptance.py四类型×两模式8条、关闭Agent普通读取、停服备份回执恢复、ZIP CRC/排除秘密与新空间身份通过。
- Node首次test_agent_proposal_workflows.js在初始化apiAvailable/projects等待超时，未取得原因证据，不归因于应用或负载；随后该专项独立重跑通过（完整预览/批准/丢响应刷新查询/两主题两宽度）。未改代码或放宽断言；其余18项正在依序执行，未完成前不写全量通过。

- 用户再次手工添加参数并重连后，新trace实际出现initialize/initialized、12工具及两条fixture_request/reply；ping valid=true，未知方法valid=true、整数-32601。clientInfo.name=workbuddy-mcp-probe:custom-mcp:workbench_probe/version1.0.0；这是WorkBuddy连接探测端实际回复，不把短连接探测视为当前聊天持续在线，也不混作业务调用。此前未运行记录保留。已给出补验第6轮（新身份读取ISSUE-0001、准备单份追加完整预览后停止），尚未确认提交。
- 下一精确范围：仅在本任务TEMP准备loopback故障夹具，固定转发至新临时服务的Agent API，普通模式转发实际HTTP；显式一次性控制支持成功commit响应落盘后断开、延迟只读响应、轮换/撤销测试身份、错空间头及真实120/min限流预置。合成故障单独记录，不制造MCP客户端请求/人类确认，不操作管理批准或正式库，不向日志写凭据/业务内容。提交丢响应必须等当前预览后用户新确认，夹具只截断响应，后续查询来自真实客户端。测试配置仍保持同一临时文件/身份，切换至代理使用正常CredentialManager origin操作和持久日志；结束撤销停止清理。

- Node实际全部19个契约通过：提案专项独立重跑通过，其余18项顺序通过，包括设置、四类型深链接、两编辑器保存/草稿/外部冲突、概念图、主题与宽度。本轮没有改应用代码或缓存。固定目标HTTP夹具默认透传的开发侧capabilities核对通过（真实服务HTTP200、类型不变）；不把该HTTP自检计作WorkBuddy调用。用户已发送第6轮、正在执行，预览与后续确认仍待核实。

- 第6轮实际capabilities/get_item/prepare/preview四次均tool_is_error=false；新issue/append提案e736dfa2-35a9-40ec-8926-a683cebaa6bf v1、agent_attested、previewed，无回执，持久回执仍16。已请求用户核实完整展示，不把previewed当展示/批准。实际中继argv现已含--relay --protocol-faults；业务连接也回复两项显式探针。另有一次tools/list提前于initialized，服务-32002，客户端随后初始化并重试发现12工具；保留真实错误与成功重试，不宣称无协议错误。
- 本次三文档UTF-8/代码围栏/相对链接、目标diff与git diff --check通过后形成独立记录提交；运行时、数据格式/API、缓存与正式配置无变化。AG-121仍进行中，未施加的提交丢响应等不标通过，AG-126仍待剩余兼容矩阵。

### 2026-11-07 / AG-121 / 取消关联证据补强开始

- 开始前工作区干净，HEAD df59628。用户已核实第6轮完整预览；已为指定v1提案设置一次成功HTTP提交响应截断，尚待用户第7轮新消息确认和真实执行。当前夹具不代发commit。
- 精确范围：workbuddy_agent_acceptance.py的脱敏protocol_metadata增加取消通知与内存pending请求的关联（工具名/是否仍待响应），保留原逐字节转发、不记录请求ID/参数/reason/业务正文；已有pending上限256不变。对应test_workbuddy_acceptance.py覆盖真实关联、迟到结果/未知取消及不泄密。仅验收设施，不改应用取消语义、业务契约、UI或版本。
- 目的：一次notifications/cancelled不足以证明取消的是哪个在途请求；下一次正常重连后新中继可提供关联证据，当前运行中继不热替换、不回填历史。计划专项/语法/默认和显式原装CLI连接、必要全量Python、文档diff；真实桌面取消仍需用户实际停止及重连后查询，不以专项替代。

- 实际7项中继专项及两Python文件语法通过。原装CLI显式探针复查两次连接断言失败，已安全核查隔离子进程stderr：Cannot find module '../dist/codebuddy'/MODULE_NOT_FOUND；不是协议回复断言失败。磁盘安装元数据现为WorkBuddy5.9.3、CLI2.165.0，仅有lite-wb产物。原装启动器提供固定环境CODEBUDDY_FORCE_LITE_WB_BUNDLE=1；在隔离调用临时补该开关后真实CLI2.165.0显式探针/12工具/退出0通过，无模型turn/真实配置修改，未提取SDK或改厂商文件。旧5.1.5/2.103.3历史不重写，新桌面运行版本待用户核实；仓库CLI启动默认命令仍需另行修复，不把临时覆盖说成默认已通过。
- 第7轮观察到实际commit工具isError，HTTP故障日志对应真实200提交响应后截断；随后真实客户端get_proposal/get_item非错误，无新prepare。磁盘committed、回执17；正式问题SHA256等于239540b8d7d3497cdaeca1337063a2736d4debd80a1c8de49596bea34ca9ef07，正文及全部开放字段逐项等于候选，提案receipt等于持久回执。已保存17份回执/正式问题哈希基线供重启核查。尚待用户报告首次错误码和实际确认/查询结果，不以tool_is_error推断错误码。

- 取消关联补强本轮全量234项Python通过（102.959秒）；7项专项、两脚本py_compile通过。仅验收中继/保护性测试和两文档，实际桌面取消仍待后续正常重连后执行；本次不借用默认CLI失败轮次作通过。两文档UTF-8/围栏/相对链接及目标diff、git diff --check复核后独立提交。下一入口：修复当前安装lite-wb的验收启动选择，再继续用户第7轮结果与重启/认证/取消。

### 2026-11-07 / AG-121 / 新安装CLI入口兼容修复开始

- HEAD 7f27c00、工作区干净。用户截图已确认实际运行桌面WorkBuddy5.9.3(d4692421)、Electron37.10.0、Chrome138.0.7204.251、Node22.16.0；安装CLI2.165.0。不能沿用旧5.1.5完整兼容标签，后续按版本标注已测/缺口。
- 精确范围：验收脚本在完整CJS产物缺失且原装lite-wb.mjs存在时，使用原装bin支持的固定CODEBUDDY_FORCE_LITE_WB_BUNDLE=1；不改厂商文件、不抽取SDK、不自动模型、不改变应用运行时。旧完整安装继续默认入口，输出实际选择的bundle以便复核。预计workbuddy_agent_acceptance.py、已有专项及兼容/维护/台账；计划旧/新布局选择专项、语法、真实CLI默认/显式模式和必要全量Python。
- 第7轮用户报告首次service_unavailable/retryable=true且无回执，随后get_proposal committed恢复同一v1回执、get_item revision一致、追加只出现一次；用户在指定确认步骤后提供该执行报告，与实际唯一commit→两次读取/截断200/持久17回执一致。此报告不外推现实身份认证，也不补早期未核实确认。后续重启/认证/取消仍需执行。

- 当前8项专项及两脚本语法通过；修复后python workbuddy_agent_acceptance.py和追加--protocol-faults均真实CLI2.165.0/lite-wb、MCP2025-11-25、12工具、退出0通过，默认无注入、显式ping/未知方法均valid。无模型turn或正式配置修改。全量Python已启动，结果待记录；不把新CLI通过外推为5.9.3桌面全部矩阵。

- 本次完整Python门禁235项通过（98.060秒），8项专项、两脚本py_compile、真实CLI默认/显式入口通过；没有JS/CSS改动，19Node本轮此前已通过，无新增UI实现需要重复。三文档UTF-8/围栏/链接与目标diff/diff检查复核后，与入口修复及专项独立提交。
- 用户明确授权第8轮之后最多再6轮手动任务，用于当前5.9.3故障/取消及升级对应四类型/两确认契约，不自动发模型。用户截图确认的版本信息作为来源；历史5.1.5结果保留独立标签。
- 第8轮准备：用户第7轮已停止后，只替换本任务临时HTTP代理进程以加入固定顺序的显式故障控制，保持同一临时origin/配置文件/身份；未更改正式配置或应用运行时。代理更换不冒充业务服务重启。随后通过原夹具CONTROL实际重启业务服务，17份回执及正式问题SHA256基线全部不变。
- 新HTTP夹具仅按八次capabilities序列注入：正常、错误空间头、请求发出后轮换（本次旧token）、正常新token、真实120/min窗口预置、实际服务重启、服务端临时旧授权缺kinds且read-only、恢复原显式授权。旧授权模拟仅修改本任务TEMP注册表，范围收窄；恢复通过正常CredentialManager且仅恢复预置前的原范围，不自动扩权。错误空间头与限流预置/注册表条件是合成故障，不能冒充客户端真实配置损坏或自然流量；真实请求和响应由客户端/服务完成。已给出第8轮顺序任务，尚待执行，不先标通过。

### 2026-11-07 / AG-121 / 第8轮重启与认证矩阵实际执行

- 工作区干净、HEAD38d2839。第8轮由用户明确反馈已发送，真实客户端按顺序完成八次capabilities，固定HTTP阶段0～7全部消费；业务服务正常恢复，原17份回执/正式问题哈希基线全部不变。最初实际业务服务重启与限流后的再次重启都由原夹具重新装配真实Repository/AgentService/Runtime，不以代理进程替换冒充。
- 关键HTTP原文（合成条件由夹具施加，错误响应由真实服务返回）：

```json
{"fixture_mode":"wrong_workspace","fixture_step":1,"http_status":409,"route":"/api/agent/v1/capabilities","service_error_code":"workspace_mismatch"}
{"fixture_mode":"rotate_before","fixture_step":2,"http_status":401,"route":"/api/agent/v1/capabilities","service_error_code":"unauthenticated"}
{"fixture_mode":"rate_fill","fixture_step":4,"http_status":429,"route":"/api/agent/v1/capabilities","service_error_code":"rate_limited"}
{"fixture_mode":"restore_explicit","fixture_step":7,"http_status":200,"route":"/api/agent/v1/capabilities"}
```

- 相邻阶段实际正常200：轮换后下一次客户端请求重新读取新令牌；限流后真实重启清空服务内窗口再通过。旧授权阶段去除服务端kinds/authorization_schema_version并仅read，info/todo读取两次isError、issue读取成功、两次search成功和三次prepare isError；尚待用户报告具体结果/错误码，不从isError猜测。最后通过正常CredentialManager恢复原显式issue/todo/info/document与commit/propose/read，enabled保持有效。
- 新版完整矩阵尚未收口：用户已获最多6轮追加额度；下一入口是第8轮最终报告、同临时连接器正常重连加载取消关联元数据、实际停止一次只读请求并核查状态，再进行5.9.3四类型/两确认路径对应回归。未移除/撤销该临时连接器，最终清理尚待；不标AG-121/126完成。

- 用户第8轮最终报告已核实：八次capabilities严格按序、未补调/重试；get_proposal/get_item及原v1提交重放返回同回执（ID/revision/committed_at不变）；错空间workspace_mismatch与旧令牌unauthenticated均retryable=false，限流rate_limited为true。旧授权capabilities仅issue/document及read；info/todo search为空、读取not_found，issue读取成功；三次create均forbidden（缺propose scope），无新提案。恢复capabilities原四类型/scopes，业务回执17不变。
- 开发侧另核INFO-0001/TODO-0001文件SHA256等于续验源manifest，INFO仍6字段；客户端关于“空结果可能是授权收窄”的推测不拿来代替服务端文件事实。恢复后客户端info/todo再读取仍留下一轮验证，不由本次磁盘核查冒充。下一入口正常重连加载新版取消关联；不要求改程序/参数/env，不自动发模型任务。

- 本次三文档UTF-8/围栏/相对链接与目标diff、git diff --check通过，独立提交第8轮已执行证据；未改代码，不重跑已通过的235Python/19Node充当新实现。

### 2026-11-07 / AG-121 / 第9轮真实取消与新版回归开始

- HEADbc64cb9、工作区干净。用户在第8轮完成后手工重连同一临时连接器，再发送第9轮单次capabilities只读任务并明确反馈在执行期间点击停止。固定HTTP夹具收到真实capabilities且业务服务已200读完后，只延迟其响应12秒，没有业务写入。
- 新中继实际关键原文：

```json
{"direction":"client_to_server","method":"tools/call","tool":"workbench_capabilities"}
{"direction":"client_to_server","method":"notifications/cancelled","cancelled_request_pending":true,"cancelled_tool":"workbench_capabilities"}
{"direction":"server_to_client","tool":"workbench_capabilities","tool_is_error":true}
```

- 相比此前只有孤立通知，本轮关联确认为在途capabilities；通知不证明服务端立即中断，桥接既有同步HTTP有10秒上限，实际仍观察到迟到isError。17回执与正式问题哈希全部不变，未撤销已接受事务、不回滚正文。停止后复用/复连查询留给第10轮真实客户端核对，不由开发侧读取冒充。
- 第10轮范围：当前5.9.3读取原回执及恢复后的info/todo、四类型catalog/搜索；四类型local_web新建候选与有序多行info_fields、完整展示，四次自报绕过负向，网页批准另由用户操作。已给出明确四个独立request_id（wb593-create-issue/document/todo/info分别展开），不自动模型/不代替批准；预计仅三验收文档更新，无应用代码/缓存/数据格式变化。后续append/update逐轮完整展示后等新确认，所有写入仍只临时库。

- 第10轮用户提供完整报告：停止后原提案committed/revision未变，INFO-0001(707字符)/TODO-0001(111字符)读取恢复；四类型catalog已读，document错误携project_id时invalid_request，移除项目参数后成功，符合文档仅分类契约，不改应用。四份local_web create v1完整预览已展示，四次自报提交均confirmation_required/retryable=false、无回执。info三项有序字段按指定模板逐字核对，含引号、换行和首尾空格。
- 用户随后明确报告四份已在临时网页逐份完整预览并独立批准。实际四份committed、local_web批准日志各1份completed、approval/版本/摘要与提案及回执相同；正式文件重新解析的正文/全部开放字段等于候选、SHA256等于回执。ID为ISSUE-0003、DOC-0002、TODO-0002、INFO-0003，回执21。开发夹具未调用管理批准。
- 第11轮已安排真实客户端查询/重放上述四份网页回执，再完整读取、准备四份新的agent_attested append完整预览后停止；尚待执行/展示核实，不把安排记结果。已请用户打开/刷新四种正式结果链接，手工结果待回报。下一轮仍须新的明确确认后提交，不自行批准。

- 用户确认四种正式结果链接均打开正确且刷新正常；第11轮已发送、正在执行。三文档UTF-8/围栏/相对链接及目标diff、git diff --check通过后独立提交第9～10轮证据；不借用旧版读写标签完成新版append/update。


### 2026-11-07 / AG-121 / 第11～12轮新版追加与更新预览

- HEAD009475f、开始前工作区干净。用户核实四份append完整预览均展示、四份原网页回执重放不变；候选agent_attested v1正文保留完整前缀，原开放字段、todo due与info_fields均不变，正式回执仍21。
- 用户随后明确回复已发送第12轮指定新确认任务，实际四份append均committed，正式文件正文/全部开放字段重新解析等于候选、SHA256等于回执，回执25。ID仍ISSUE-0003/DOC-0002/TODO-0002/INFO-0003，无重复新建。
- 四份update v1均已previewed、未提交：正文在完整现文后添加更新回归段；issue priority=高，document title=WB593-新建-知识-已更新但target DOC-0002不变；todo due=null且completed=true为服务端推导；info3项完全逆序、value/note未变。逐项比对候选与base_content通过，等待用户核实实际完整展示，不能把previewed当人工已确认。下一入口确认当前update后真实提交，再执行最后负向/查询/撤销；不提前收口AG-121。
- 收尾预查仅只读：历史审批拒绝的三个TEMP basename均仍存在，按命令行匹配未见相关python/node/WorkBuddy进程。其中2c2xum8z仅留私人注册表等残余（enabled位仍true，原data/.agent/workspace.json已不存在），不能声称已撤销或仍有活跃工作空间；未重建旧业务空间、未调用删除/绕过原拒绝，最终需用户手工清理。另两个未见私人注册表。当前续验身份/服务不在这三个目录内，继续正常验收。


### 2026-11-07 / AG-126 / 最终本机收口继续

- AG-121剩余第13～14轮尚未完成，保持进行中；AG-126恢复进行中，仅并行推进独立文档与最终门禁准备，不把兼容未测项标完成。AG-122～125继续取消，首期/RF历史不变。
- 精确范围：最终Python/全部Node/全文件语法、真实Codex与生命周期恢复复核；README/接入/使用/维护/架构/数据格式/兼容与扩展验收同步真实本机范围，关闭/撤销/清理任务TEMP并复核Git提交。预计只改文档；验收设施代码已由7f27c00/38d2839独立验证提交。
- 已发现文档冲突：当前架构导航/数据格式通用链接仍只写issue/document，接入HTTP摘要亦遗漏todo/info；AG-116段“local_web尚未开放”未明确历史阶段。代码与后续AG-117/118/120说明已支持四类型/网页批准，本次纠正现状说明、保留历史验收和旧格式，不改公共契约、应用版本、资源缓存或数据。
- 完成门槛：当前5.9.3矩阵全部实际证据、最终检查和收尾结果齐备后才标AG-121/126完成；历史审批拒绝目录不绕过删除，必要时请用户手工清理，不假称已撤销/已删除。

- 最终门禁实际通过：全量Python235项（107.463秒）、61个Python/45个JavaScript文件语法；19项Node契约最终整组重跑全部通过。此前首次提案专项初始化等待超时、独立重跑及其余18项通过的记录保留，不放宽断言。Node包含真实Edge两编辑器保存/重开、草稿/冲突、接入设置/提案管理、四类型链接、概念图及浅深主题/桌面窄屏。
- 真实Codex0.163.0-alpha.10.2/MCP2025-11-25联调通过：12工具、四类型、两确认路径、重启/撤销，无模型turn或真实用户配置修改。extension_lifecycle_acceptance.py通过四类型×两模式8组、停用后网页读取、停止后的完整备份/回执恢复、ZIP CRC/凭据排除/新空间身份。该脚本自己的non_codex_and_remote未运行标记仅指脚本范围；WorkBuddy另有真实手动验收，不混用。性能脚本及视觉基线本轮未重跑。

### 2026-11-07 / AG-121 / 第13轮更新落盘与第14轮最终负向

- 用户核实四份update完整展示后，再反馈已发送指定确认任务；真实四份提交和随后四次get_item成功，用户最终确认四份成功并停止。正式Markdown正文/全部开放字段等于候选，SHA256等于持久回执，回执29。todo完成且due=null、info三字段完全逆序且原值/备注保留、文档标题改变但DOC-0002不变、issue优先级高；追加及更新段各一次。
- 第14轮已由用户发送，专用取消候选479662ac-b9c9-4b6d-a7ca-acad8c48b4e5现为v2/cancelled、previewed_version=2、无回执，候选info_fields为空。最终33文件检查点（29回执加四份正式文件）字节哈希全部未变。末尾指定哨兵查询触发正常CredentialManager撤销，等待客户端完整错误码/分页/拼接报告；不从tool_is_error猜业务码，未提前标通过或清理正在使用的连接器。

- 第14轮用户完整报告核实not_found×2、invalid_reference、unknown_field、idempotency_conflict、version_conflict、invalid_state及撤销后unauthenticated×4，均retryable=false。分页提案5页13项、搜索2页4个ID，无重复；取消候选省略保留三字段、修订显式空列表只影响候选，正式INFO-0003 revision仍60b35224d6c14d7b25d805aa3753f60fe832fbe39c7103343f19c4457b14d34e。四个新条目各两份历史，29回执及四文件哈希仍全部不变。
- 分段offset=0/128/256/384/512/640→null、707字符；逐字比较用户转述汇总与磁盘，恰有offset93一字符差异（汇总U+002D、磁盘U+0020，目标项目显示名），其余706字符一致。已请用户查看该轮既有原始工具结果，不新增模型任务，不把汇总误差直接称原始协议损坏或完整逐字通过。此前5.1.5的完整拼接核对历史保留独立版本。
- 用户报告临时workbench_probe已移除，历史三处审批拒绝目录已手工删除；只读核实三处均不存在。STOP后两个夹具正常退出0、端口53702/57866无监听、按命令行匹配未见相关进程；续验两个身份及live旧身份均disabled。另发现旧恢复目录原始静态副本保留enabled=true（未运行服务），在其既有空间通过正常CredentialManager撤销，未重建空间或读取正式配置。
- 原先允许正常清理的续验/旧恢复/别名三个目录，在绝对Temp父目录/无reparse/进程退出/端口关闭核实后，递归删除又被自动审批拒绝（仅blocked by policy）。未尝试其他工具或方法绕过；已明确请用户手工删除这三处，结果待核实。AG-121/126继续进行中，不把已撤销等同已删除。

- 用户随后报告上述三处也已手工删除；只读复核包括历史三处在内的六目录均不存在。临时连接器移除、身份撤销、进程/端口停止和目录清理收尾全部完成。用户询问“原始工具”位置，已解释为第14轮既有INFO-0001/offset0/length128调用卡片的结果，无需新增模型任务或重连；唯一剩余证据核实是汇总中的项目名空格差异，仍不提前标完成。

### 2026-11-07 / AG-126 / 当前摘要一致性复核

- 28c8766后工作区干净、临时接入清理已核实。复核发现扩展验收顶部仍停留5.1.5/CLI连接与AG-126受阻，首期验收末尾亦仍称完整读写待验收，和第8节/台账的新证据不一致。同步README、首期/扩展验收、扩展方案的当前摘要，保留逐日历史及AG-121/126进行中，不重写已完成工作项。
- 本次纯文档，不改运行时/API/数据/版本/缓存；仅执行28份Markdown编码/围栏/相对链接和git diff --check，既有235Python/19Node等结果仍标为实际先前运行。原始工具结果核实问题仍待用户答复，无可替代该证据的自动测试，不新增模型任务、重建已清理环境或读取正式客户端历史。

### 2026-11-07 / AG-121 / 原始返回核实与完成

- 0012163后Git干净；用户先提供调用parameters，继而提供同一调用段1原始body。按转义换行解码为128字符，逐字等于此前磁盘比对中仅校正offset93为空格后的前128字符；其余706字符已在清理前逐字核对。确认差异仅在最终汇总转写，原始返回保留空格，707字符六段拼接核实通过，未新增模型任务或重建已清理环境。
- 原始关键摘录（第14轮get_item，offset=0、length=128；省略用途段，仅保留差异及分段边界）：

```text
- 目标项目：WorkBuddy 隔离验收（id: WorkBuddy-隔离验收；status: ac
```

- AG-121于2026-11-07完成：WorkBuddy5.9.3(d4692421)/Windows11 22631/stdio MCP2025-11-25，四类型三操作、两确认路径、分页分段、范围/字段/引用拒绝、幂等/取消/丢响应查询、真实重启、轮换/撤销/错空间/限流及真实结果链接齐备；29回执/正式文件及历史计数核实。CLI2.165.0/lite-wb默认/显式协议探针另列，旧5.1.5确认缺口不改写。
- 实际修改包含workbuddy_agent_acceptance.py、test_workbuddy_acceptance.py及客户端矩阵/台账/扩展验收/接入/维护说明，设施变更见7f27c00、38d2839；不改业务API、Markdown、旧授权语义、应用版本/资源缓存或真实用户配置。沿用AG-DEC-006～009，不引入运行时SDK/厂商文件修改。235Python、8项专项、真实CLI默认/显式探针及最终19Node/语法结果见前文；本次收口仅文档检查。
- 风险已明确：提前tools/list获-32002后初始化重试；取消不保证同步HTTP立即中断/业务回滚；Hy4仅UI标签，不证明后端精确模型或任意模型遵规；合成故障条件不冒充自然故障，远程未实现。临时连接器/凭据/进程/端口/六目录收尾已核实，无AG-121遗留项。下一项AG-126最终文档/交付审计及提交。

### 2026-11-07 / AG-126 / 本机扩展交付完成

- AG-121完成提交3f412f8后Git干净，按扩展方案第7/9/10节逐项审计：当前四类型三操作/两确认、查询与协议/故障矩阵、两编辑器浏览器回归、真实Codex、停用/备份恢复/ZIP排除、临时接入收尾均有实际证据，详见扩展验收第9节。保留最初失败、升级重跑、早期确认缺口和合成故障边界，不以脚本或旧版本代替当前客户端。
- 实际收尾文件为README、AI_AGENT_ACCEPTANCE、AI_AGENT_EXTENSION_PLAN、AI_AGENT_EXTENSION_ACCEPTANCE、AI_AGENT_PROGRESS及ARCHITECTURE；先前接入/使用/维护/数据格式已同步。无应用运行时/API/Markdown格式/旧授权变化，APP_VERSION和资源缓存不变，无真实数据迁移。
- 最终检查结果：235Python（107.463秒）、19Node整组、61Python/45JS语法、真实Codex与生命周期通过，命令及范围见前文；本次仅文档状态变化，28Markdown编码/围栏/相对链接、目标diff和git diff --check通过后提交，不重复运行已通过门禁充当新实现。最终提交标题Complete local Agent extension delivery。
- AG-126于2026-11-07完成，沿用AG-DEC-006～009；无当前本机范围遗留项。远程AG-122～125保持已取消，不实施/不标通过；不同客户端版本与模型限制、取消迟到语义及本轮未跑性能/视觉基线均保留。后续客户端升级须重跑对应契约，不自动创建新工作项或发模型任务。


### 2026-11-07 / 提案预览交互优化 / 已完成

- 用户授权按预览优化方案实施；普通功能维护，不改变模块边界或公共契约，不新增RF或改写已完成AG状态。开始前Git干净。
- 范围：大弹窗、固定头尾和正文滚动、本页连续切换、关闭恢复列表位置与焦点、可读字段与完整原始信息、弹窗内反馈；保留批准/取消二次确认及未决操作恢复。
- 预计文件：agent-proposals.js、management.css、responsive.css、index.html、提案浏览器测试、README/使用/验收与本台账。API、Markdown、草稿、历史、外部修改和凭据持久化不变。
- 计划检查：Python全量与语法、JS语法、提案/设置/样式Node契约、真实Edge浅深×桌面窄屏截图检查及diff检查。重点风险为嵌套确认焦点、关闭时迟到请求、未决写入不得重放。

- 2026-11-07完成：实际修改README、AGENT_USAGE、AGENT_SETTINGS_ACCEPTANCE、本台账、js/features/agent-proposals.js、css/management.css、css/responsive.css、index.html和test_agent_proposal_workflows.js。完整预览改大弹窗，固定头尾/窄屏全屏、连续查看、位置/焦点恢复和可读字段均完成；原始字段/正文/差异/警告/来源完整保留。
- 实际检查：Python235项通过（97.261秒）；提案/设置浏览器与样式Node契约通过；主入口/修改JS语法、Python编译和diff检查通过。浅深×1440/390顶部/底部截图已目视检查；关闭慢请求、嵌套确认、过期版本、取消丢响应、批准在途关闭/刷新原操作查询与成功结果已验证。详情见AGENT_SETTINGS_ACCEPTANCE末节。
- 兼容与风险：不改后端/API/正式数据格式/草稿/历史/外部修改或凭据契约；关闭清理预览并使迟到响应失效，未决请求继续保留；无新增决策编号或遗留项。此次不重跑真实Codex/WorkBuddy模型联调或性能基线，不改变既有实测边界。下一步按用户新需求维护。


### 2026-11-09 / AG-128 / 完成

- 实现：严格休眠grants与独立客户端、UI/CLI、三层能力协商、catalog范围隔离、文档分类grant收窄；root2/client3/log3/transport2格式门槛及恢复，具体字段与新日志授权快照校验见DATA_FORMAT。
- 实际文件：agent_security/management/service/tools、http_api版本、server CLI、agent-settings、management.css、index；新增test_agent_capabilities，扩展API/runtime/MCP/settings/Agent工作流失败诊断；README/AGENTS/接入使用维护/架构/格式/本方案/台账及新验收分册。
- 自动：全量Python249项122.476秒通过；后续恢复快照校验变更后相关72项66.227秒通过，新增匹配备份1项1.441秒通过。62Python/46JS语法通过；20Node分别通过（设置+提案+其余17+Agent工作流独立），最后null/数组grant严格400的管理HTTP6项5.643秒通过；修改Markdown编码/围栏/83相对链接、历史状态及生成物排除、git diff --check通过。五阶段首次root1独立空间、真实进程退出、新版重启、归档旧版各入口拒绝/私人JSON不变、并发CLI、unknown/mixed日志、abandon及匹配备份均实际验证。
- 浏览器：真实Edge浅深×1440/390、focus/disabled/error、长中文、空数据及大量范围、取消/丢响应查询/清空/重开通过，四张新表单截图目视检查；修正标签挤压并复验，截图不提交。
- 失败保留：stderr解码改字节断言；pycache并行权限改临时编译输出；设置测试等待布局/close事件；提案/Agent导航偶发刷新等待超时独立复验通过，保留失败诊断、不改超时或断言，根因仍待观察。详见AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE。
- 兼容：旧读取不自动迁移，旧授权不扩权；新格式旧版拒管理/鉴权，abandon不降版，无自动格式降级器，只能停服解决未决并恢复匹配备份。业务Markdown/JSON/草稿/历史不变，无真实库/私人配置修改。APP_VERSION2026.11.09.1和资源缓存已更新。
- 决策：AG-LOCAL-DEC-009～012；持久dormant+当前effective为空，未来首次激活须管理员重新授权，AG-129与各能力继续承接。新文件授权和全部后续业务工具未开放，不将旧客户端/旧联调结果冒充新能力验收。
- 遗留/下一项：偶发浏览器刷新等待风险保留诊断；无阻止本项交付的未决问题。AG-129仍待开始，先交监督审查，不顺带开工。


### 2026-11-09 / AG-129 / 开始

- 授权：用户“现在开始执行方案”持续有效，监督已接受AG-128提交f6463db并派发本项；git status --short干净。执行者唯一写入，监督只读审查。
- 精确范围：proposal3/独立执行日志版本及摘要、静态操作处理器、受控多步骤计划、依赖集合/授权revision/批准绑定、幂等/重启恢复/在途清理保护；用现有四类型create/append/update贯通。不开放文件/附件/图/删除/项目/配置能力，不新增任意路径/方法或测试处理器。
- 预计文件：agent_proposals、agent_service、agent_proposal_management、write_coordinator及领域Prepared接点（按实际最小需要）；相关恢复/提案/网页批准/API/MCP测试；格式/架构/计划/使用维护/验收和本台账，公共契约/UI有变再同步资源及浏览器测试。
- 计划检查：旧schema1/2摘要/恢复、新旧混合、未知日志预检、各步骤异常及真实进程退出、授权/配置/集合变化、第三方改动/部分应用、幂等/并发/关闭接入恢复/取消/过期/清理/abandon；专项及必要全量Python/Node/语法、真实浏览器适用项、文档与diff检查。全部临时库/隔离凭据。
- 风险：现有单Markdown恢复的applying缺失目标歧义必须保留；新处理器不得另造CRUD、提前开放业务或激活休眠授权；授权撤销与已应用回执恢复需按阶段区分。开工先具体定稿分流/步骤/批准/依赖/锁契约并发监督。


### 2026-11-09 / AG-129 / 完成

- 实际：新增agent_execution.py静态markdown@1与test_agent_execution.py；修改agent_proposals/service/proposal_management/tools、http_api、proposal UI/index及相关测试夹具/浏览器；同步方案/格式/架构/接入使用维护/README/AGENTS/验收/台账。领域Prepared仍唯一写入，不引入平行CRUD或后续能力。
- 兼容：新proposal3与独立execution_schema1、批准action3绑定；旧1/2摘要/字节/恢复保留，真实混合与旧2更新历史实测。具体计划/授权/依赖/批准/回执交叉校验、零写未知格式预检、磁盘阶段恢复、在途清理保护；APP_VERSION2026.11.09.2、proposal JS缓存20261109-2。无真实业务数据迁移或配置操作。
- 检查：全量Python267项227.517秒通过；新增执行16项24.000秒通过；后续在途标记保护48项61.705秒、批准字段29项53.018秒、最终manifest确认完整性29项58.889秒通过；64Python/46JS语法；20Node分批通过（首组17、提案UI独立1、概念图/编辑器复验2），不写一次全绿。十阶段真实退出、四类型三操作、两确认路径、混合格式、真实关闭Agent启动/授权缺失、依赖/并发/清理/未知格式/第三方修改均有证据，详见本机验收AG-129。
- UI：保存范围/展开执行依据，浅深×1440/390四图目视检查；焦点、disabled、长中文、固定头尾/正文滚动和原保存冲突工作流通过。I/O临时样本136提案/16终结日志仅证明一次目录扫描/终结快照零读取，不冒充性能基线。
- 失败：持久授权与reload夹具修正；新增浏览器重复顶层const改IIFE，清理EPERM曾掩盖首错，增加原错诊断；概念图清理EPERM/编辑器初始化等待超时串行复验通过，未放宽等待或断言。3处Temp清理命令被自动审批拒绝，仅blocked by policy，未绕过；用户手工删除，监督及执行只读核实不存在，无对应测试进程，清理遗留关闭。
- 决策/风险：AG-LOCAL-DEC-013～017；状态集合保守绑定会要求相关集合改变后重预览；外部文件系统竞态仍不能称多文件原子事务；create applying缺失需人工核查，不自动重建。新能力dormant仍不生效，无模型turn/真实新能力客户端/性能基线运行。
- 下一项：交监督审查，AG-130～143仍待开始，不在本项内执行文件授权。

AG-129提交前最终检查：64Python/46JS语法、修改Markdown编码/围栏/84相对链接、历史状态/后续待开始及生成物排除、git diff --check通过。


### 2026-11-09 / AG-130 / 开始

- 授权：用户总体执行授权持续，监督接受AG-129/9b6924d后派发。起始git status --short干净；唯一写入，监督只读。
- 精确范围：具体文件同源管理预览/批准/撤销、私人file-grants/日志/恢复、句柄身份与敏感范围防护、file_id目录/元信息/64KiB原始字节分段文本、三工具与HTTP、管理UI/文档。既有休眠grants不激活；不做目录授权、上传暂存、附件或任意文件写入。
- 预计文件：新增agent_files及平台句柄模块、security/management/http/service/tools、agent-settings/index/http_api；文件/日志/路径/编码/HTTP/MCP/浏览器专项及受影响门禁；方案/格式/架构/使用维护/验收/台账。
- 验证计划：Windows真实临时普通文件/硬链接/重解析/特殊路径/替换拒绝，敏感位置仅合成夹具；批准前零正文读取；每管理落盘阶段恢复/幂等/并发/CAS/撤销/轮换；多编码分段/源变化/过期/边界/超限/有界内存；HTTP/MCP与浅深桌面窄屏真实管理UI；全部隔离配置/临时文件，禁止真实用户源文件或认证材料。
- 风险：批准前哈希即越界读取；Windows路径别名/句柄身份/硬链接与共享模式；长I/O持锁及撤销窗口；私人授权/客户端版本多文件恢复；未知日志降级；未支持平台必须拒绝而非降级路径检查。具体安全方案先发监督并核查官方API。

### 2026-11-09 / AG-130 / 完成

- 实际文件：新增agent_files、agent_file_handles、test_agent_files；security/management/management_http/http/service/tools、http_api/index、agent-settings、API/diagnostics/capabilities/MCP/settings测试、Codex/WorkBuddy固定工具目录验收预期；同步AGENTS/README/本机方案/台账/验收/架构/格式/接入使用维护。
- 数据/API：根3/授权4/active_file_ids与私人file-grants交集，日志4外置私人快照及终结后清理；transport2及旧根/授权/日志兼容读取，其他休眠grants不激活。三个只读工具合计15；Agent无任意path/目录/上传，管理预览无正文，批准后hash，session/票据/CAS/runtime结束复验。业务Markdown/草稿/历史/导出不变。APP_VERSION2026.11.09.3、设置JS缓存20261109-3。
- 自动：全量Python首轮288项185.202秒，286通过/2处旧契约预期失败；修正files空目录与诊断15工具后，相关63项60.784秒通过；补有界内存/模拟未支持分支2项0.513秒、孤儿首写与终结退出1项0.517秒；最终文件专项24项23.157秒通过。67Python/46JS语法通过；20Node分别通过（19项串行整组+设置独立，结构化预览后设置再通过）；真实Codex0.163.0-alpha.10.2隔离验收15工具、四类/两确认路径及故障通过，0模型turn/未修改用户配置。未将首轮全量写成一次全绿。
- 原生/恢复：真实Windows句柄、所有多硬链接/目录junction/SUBST拒绝、合成秘密根短名/大小写防护；多编码边界与来源变更/期限/配额，11MiB分段tracemalloc峰值<4MiB；6阶段file和4凭据操作×7阶段真实退出、首写孤儿/abandoned终结退出、旧9b6924d拒绝与零JSON变化、混合/未知预检、清理失败查询重试。原始HTTP/MCP无路径、schema拒path、CAS/幂等/撤销、长hash换库/关闭/撤销及慢socket许可边界通过。
- UI：文件专用创建、无隐含旧业务范围、中文完整预览/技术依据展开、取消/明确批准、响应丢失刷新查原操作、撤销；浅深×1440/390四张最终截图已目视，无横向溢出。复用既有样式，未新增CSS。
- 失败与复验：旧12工具/未开放files契约更新并保留无授权拒读断言；初版文件panel放在agent-settings外导致溢出，移回既有容器后通过；测试桥接入口名错误/Windows换行比较修为真实agent_bridge及原始字节比较；初步原生探针仅控制台GBK打印emoji失败，后续真实断言通过。无本项自动审批拒绝/清理遗留，无真实用户源文件或认证文件读取。
- 决策/边界：AG-LOCAL-DEC-018～023；仅Windows报告固定本机NTFS普通文件，拒SUBST/硬链接/重解析/特殊对象，其他平台仅模拟分支回归、未宣称原生实测。每段O(file-size)，5秒是块间截止仍有OS等待；许可先于撤销的响应可迟到。原始MCP及既有真实Codex回归不代替AG-142新增模型客户端矩阵；附件来源仅意向。无阻塞本项遗留；提交后停AG-130，AG-131等待监督派发。

AG-130提交前最终检查：67Python/46JS语法、10份修改Markdown编码/围栏/72相对链接、AG-130完成及AG-131～143待开始、git diff --check通过；起始工作区干净，无用户已有修改夹带，无数据/凭据/日志/截图进入diff。

### 2026-11-09 / AG-131 / 开始

- 起始HEAD eeeaf86、git status --short干净；用户整体执行授权持续，监督已接受130并派发，执行者唯一写入。
- 精确范围：独立明确暂存授权、私人上传会话/配额/状态、file_id来源与loopback原始字节流、真实长度/SHA/幂等、进程中断/重启/安全清理、控制MCP/HTTP/最小管理UI与文档。正式附件、索引/正文写入和消费执行留132/133，不激活旧attachment_source意向或休眠attachments.write。
- 预计文件：agent_uploads及授权/管理/HTTP/service/tools/runtime挂载；设置UI/index；新增上传域/HTTP/原生文件/进程故障/大文件/真实MCP/浏览器测试；方案/格式/维护/使用/架构/验收及本台账。
- 计划验证：无新授权旧凭据拒绝；用途/owner/source_revision/CAS/过期/撤销；同request不同输入、完成响应丢失/重复；真实长度与SHA、零字节/超限/截断/慢流/TE与剩余body关闭；配额预留、多线程/跨进程、磁盘不足；receiving/rename/ready落盘各阶段真实退出、未知格式零写/篡改保留/安全清理、长I/O期间换库/撤销；有界内存100MiB临时源、相关Python/必要门禁及真实管理UI。
- 风险：旧意向无意激活、目录/文件身份替换、慢socket持锁、跨进程配额超卖、ready不对应真实磁盘、未知对象误清理、旧版本恢复覆盖新授权。先具体定稿协议与格式门槛再实现，132以后保持待开始。

AG-131开工发现130验证缺口：虽然专用文件管理dispatcher在hash外释放短锁，do_POST/PUT等外层serialized_write仍持空间/业务锁；此前GET长读并发测试未覆盖该外层POST。监督要求先独立修复提交，历史130结果保留原范围。修复只使Agent与本机Agent管理分派在外层锁外执行，由各dispatcher既有短锁协调；普通网页写入和换库仍保留装饰器锁与guard。上传策略草稿不夹入本修复提交；131保持进行中。

独立锁缺陷修复验证：python -m unittest test_agent_files test_agent_api test_agent_runtime test_agent_execution test_server -q，107项83.793秒通过；新增真实POST文件确认hash在途HTTP撤销/关闭及换库锁均<2秒完成，最终零文件授权发布。node test_agent_settings.js通过原设置与130全流程；http_api/test_agent_files/server/test_server编译及git diff --check通过。APP_VERSION2026.11.09.4，前端资源未变；源数据/API格式/普通网页锁未变。独立修复与130补充验收一起提交，131未完成、上传新代码不入本提交。


### 2026-11-09 / AG-131 / 完成

- 实际文件：新增agent_upload_policy/agent_uploads/agent_upload_http与test_agent_uploads；修改agent_file_handles/files/management/management_http/service/tools/http_api、agent-settings/index及相关capabilities/diagnostics/files/MCP/settings测试和两个客户端固定目录预期；同步AGENTS/README、本机方案/台账/验收、架构/格式/接入使用维护。
- 契约：独立uploads.stage完整预览批准，具体owner、stream或显式file_id/source_revision、批准后client_version；旧read/propose、attachment_source意向和休眠grants均不自动授权暂存。root3/auth4/log4/transport2保留，严格新upload_policy家族及私人快照、policy/session各schema1，真实旧eeeaf86拒绝且JSON零变化。新增4控制工具合计19，正式附件/索引/正文/绑定消费仍未开放，业务Markdown、草稿、历史无格式变化。APP_VERSION2026.11.09.5、设置JS缓存20261109-5。
- 持久化与边界：100MiB/文件、500MiB/client、1GiB/空间、2/4并发、1000活跃会话、24小时、16MiB磁盘余量；跨进程预留、实际物化预算、短目录锁协调原子元数据/rename/DELETE关闭/removed，长流/hash在锁外。真实长度/SHA、fsync/sealed/blob恢复、未知对象保留、在途/绑定/消费保护，墓碑供幂等不占活跃数。取消在途409而非承诺立即中断；ready旧回执不等于当前可消费许可。
- 自动：全量Python311项231.587秒通过发生在最终边界补测前，不冒充当前全量；后续上传23项28.218秒通过，相关70项71.210秒通过；失效junction补测暴露缺口后原生属性修复，最终python -m unittest test_agent_uploads test_agent_files test_agent_capabilities test_mcp_stdio -q，71项85.775秒通过（1项符号链接创建因WinError1314权限不足跳过）。最终100MiB样本Python峰值3199815字节、2.767秒，低于测试8MiB上限，只是有界内存样本、不冒充性能基线。20Node分批通过（19串行、设置独立且最终再通过）；真实Codex0.163.0-alpha.10.2/MCP2025-11-25/19工具既有四类型两确认路径回归通过，0模型turn、用户配置未修改，不替代AG-142。
- UI：真实Edge显式暂存策略预览/取消/批准/撤销、丢响应刷新查原操作、状态/恢复/清理及真实ready行通过；长中文/120项目、空数据、focus/disabled/error与浅深×1440/390四张最终截图已目视，无新增CSS/横向页面溢出。原设置/编辑器保存冲突随既有Node通过。
- 失败保留：跨进程配额首轮69项1失败，5成功加1次路径别名拒绝，未出现超卖；只解析既有祖先/创建后复验并将元数据原子写与扫描共用短锁后18轮独立并发及相关复验通过，不宣称已证明OS内部原因。失效junction专项24项出现2错误/1跳过，补GetFileAttributesW与fixture恢复自身空目标后最终71通过；权限不足符号链接保持跳过。UI先后修正旧panel迟到/版本竞态、响应丢失测试等待早于实际提交、刷新仍匹配旧DOM，未放宽断言/超时。详情及其他真实中断证据见验收分册。
- 清理：失效junction失败fixture遗留一处本轮合成Temp目录；自动审批以blocked by policy拒绝清理，未换工具或命令绕过。用户回复“已删除”，执行和监督只读Test-Path均False，相关原测试进程已结束、子进程回收/线程join；该清理遗留关闭。没有读取真实用户源文件、修改真实工作台数据或凭据配置，没有提高系统权限。
- 决策AG-LOCAL-DEC-024～029。保留本机同步OS等待、许可后响应可迟到、未知磁盘证据需人工核查、墓碑增长及保守client版本失效边界；无阻塞本项遗留。下一项AG-132等待监督审查派发，本项不顺带开始132～143。

AG-131提交前最终检查：71Python/46JavaScript全文件语法通过（编译输出临时目录），10份修改Markdown UTF-8/围栏/74相对链接通过；最终目标diff、后续AG-132～143待开始及git diff --check通过，无业务数据、私人凭据、日志或截图夹带。


### 2026-11-09 / AG-132 / 开始

- 授权：用户总体执行授权持续，监督接受AG-131/b7ce3fe后派发；git status --short干净，唯一执行写入，监督只读。
- 精确范围：新的明确attachments.write资源授权；既有issue/todo/info及项目独立附件的attachment/create提案、完整预览/两确认路径、领域准备/应用、binary/历史/正文或索引/暂存绑定消费/回执的分阶段恢复；最小只读附件元数据及既有网页显示下载/导出验证。只处理既有目标，知识库、新建归属、替换/删除附件留后续，不激活旧休眠grant。
- 预计文件：assets/repository领域准备应用；agent_attachment相关静态处理器、execution/proposals/service/security/management/HTTP/tool契约，uploads绑定保护与协调；agent-settings/proposals UI/index；附件领域、授权、恢复、HTTP/MCP/浏览器专项及既有回归；方案/台账/验收/架构/格式/接入使用维护/README/AGENTS。
- 计划检查：旧授权不扩权、CAS/撤销与stage授权顺序、owner/index/category/source/filename依赖、确认前零正式写入、同名409、同upload单有效绑定、修订取消过期解绑、未知日志保护、逐阶段真实os._exit及磁盘重读、第三方修改/权限变化、长流期间换库/关闭/普通网页写入/孤儿清理、100MiB有界复制、原始MCP、必要全量Python/Node/全文件语法、真实Edge浅深桌面窄屏/显示下载备份导出；全部临时数据/隔离配置。
- 主要风险：client_version批准循环、暂存与正式提案跨日志恢复、文件发布和metadata不同步、未索引binary被孤儿清理、长I/O持锁、旧客户端或旧格式误恢复新处理器。先定稿持久授权/具体计划/锁序，不以长全局锁或新状态机绕过；133～143保持待开始。

AG-132开工补充：100MiB专项采用test_agent_attachments临时文件验证有界复制/真实磁盘，独立performance_acceptance.py和visual_baseline.js本项不扩展、不据此宣称完整性能/视觉基线。记录/知识库共享Markdown适配是本项特殊文件名正确性所需，两个编辑器均验证保存重开；文件票据与提案票据期限混合及新项目深链双重load互相取消在端到端暴露，登记为本项贯通缺陷修复，保留失败与复验事实。


### 2026-11-09 / AG-132 / 完成

- 实际文件：新增attachment_prepared、agent_attachments、agent_attachment_execution、agent_attachment_http及Python/Node附件专项；修改assets/repository、execution/proposals/service/proposal_management/management、upload_policy/uploads/upload_http/management_http/http_api/file_handles、server生命周期；agent-settings/proposals、共享Markdown/document-model/navigation/app及index缓存；相关assets/Agent/capabilities/diagnostics/MCP/settings/Markdown/入口测试及两个客户端目录预期；同步AGENTS/README、本机方案/台账/验收、架构/格式/接入使用维护。
- 数据/API：具体owner共同policy2/新attachment_policy日志家族，root3/auth4/log4/transport2及dormant不变；一次明确批准后新暂存，client_version同绑定无循环，不迁移旧ready。attachment/create/静态attachment@1与execution_schema2仍用唯一ProposalStore/领域Prepared；20工具新增get_attachment_target仅元数据。记录/项目附件事实源不变，兼容额外id/sha256；无文档附件格式。正式名称/ID固定，时间明确占位后在受理确认时定稿。APP_VERSION2026.11.09.6，所有涉及JS缓存20261109-6。
- 恢复/安全：确认与固定计划先manifest，锁外64KiB复制/校验与同句柄不覆盖发布；15提交、3镜像缺口、7共同许可、4退休阶段真实退出。source引用事实与保护镜像、严格消费映射、权限前后/类别集合/原生身份/历史/元数据重读及回执恢复；未知/partial/外部同名保留，消费完整回执后才允许安全退休源，预算实际删除后释放。原始body（含CRLF/首尾空格）只保留或公共助手追加，info字段/未知meta保留；旧转换todo ID仍可写附件，沿用既有无深链限制、不改ID。
- 自动实际：全量python -m unittest -v 337项256.901秒通过（1原生符号链接权限skip），发生在最后四个附件边界补测前；后续22附件专项50.952/51.737秒、相关93项144.534秒（1skip）通过；旧损坏metadata补测+assets10项1.448秒、最后assets+23附件32项74.179秒、API+23附件36项92.497秒及转换todo/旧二进制1项4.137秒通过。100MiB复制各样本<8MiB（最新36组1290746B/2.73秒）；只称有界字节场景，不称性能基线。原始stdio20工具正式附件流程/重放/拒path通过；真实Codex0.163.0-alpha.10.2/MCP2025-11-25/20工具原四类型两确认与故障回归通过，0模型turn、用户配置未改，不替代142。
- 浏览器/Node：21项分批全部通过，首3附件/提案/设置，后17项（含Agent/编辑器/概念图等），最后timestamp独立复验exit=0并清理完成；不写一次整组全绿。新端到端共同授权/取消/完整预览/网页批准、项目结果聚焦/下载、特殊[]()%#中文空格文件名，以及记录与知识库各视觉→Markdown→保存→重开通过，八张浅深×1440/390截图已目视。普通URL粗斜体对比b7ce3fe baseline相同，代码/引用/原外部图片/XSS及原编辑器保存冲突回归通过，无新增CSS。
- 失败保留：121相关首轮1失败/1错误（旧19工具预期与未知绑定应保护）定向复验关闭；夹具目录/历史ID/不完整edit/中文HTTP编码/网页误带Agent头已修正。端到端暴露文件/提案票据期限共存400、项目深链双load互相取消，已按当前正确性修复；初始化及第二次共同批准测试等待命中旧状态，改等真实初始化/新owner行，不放宽断言或超时。全Node首轮Agent刷新domCore未加载、后批timestamp120条断言false，分别独立复验通过且exit=0，根因未证明，保留观察，不归责OS。详情见本机验收132。
- 决策AG-LOCAL-DEC-030～036；当前原生能力仅已验证Windows本机NTFS，其他平台拒绝；保守授权失效/同步内核等待/外部文件系统与磁盘竞争/许可后迟到/未知partial人工核查边界保留。普通CLI/UI/MCP复用现有权限和状态机，正式字节/metadata后重读，不宣称多文件原子事务。没有真实数据、私人配置或模型任务操作，无本项清理遗留/审批拒绝。
- 完成后交监督审查，不自动推进AG-133～143。

AG-132提交前最终检查：76个Python/47个JavaScript全文件语法、10份修改Markdown UTF-8/围栏/76个相对链接及git diff --check通过；AG-132已完成、AG-133～143待开始。目标测试进程检查无匹配残留，diff不含业务数据、凭据、日志或评审截图。

### 2026-11-09 / AG-133 / 开始

- 起始HEAD 6c28f12，git status --short干净；监督接受132并派发133，总体执行授权持续，唯一写入。本项为AG功能实施，不改已完成RF历史；134～143待开始。
- 精确范围：文档front matter有序attachments JSON字符串列表，复用记录元数据语义；全局assets/images、assets/files，路径相对documents原文件。旧无attachments、未知meta、正文与唯一document类型保持兼容；category使用原文档分类，不建立附件分类事实源。先在DATA_FORMAT登记并往返验证。
- 网页链路：已有文档选择文件/流式上传并插入链接，共享editor/session/API；先保存草稿，再按expected_revision完成附件元数据及链接写入，上传期间输入持续写草稿，完成只合并附件/版本/链接到当前输入，不用返回body覆盖编辑器；切文档/刷新/中断/外部修改/409保留输入，具体并发保护随实现记录。
- Agent：复用共同policy、ProposalStore、attachment@1、PreparedMarkdownWrite、历史与五阶段恢复；只新增明确document归属，新鲜共同批准，旧category权限及休眠grant不扩权；分类/权限变动在正式写入前重查。
- 引用与清理：按document ID+实际metadata受控下载/图片，保持外部编辑器相对图片；接入现有[[ID#attachment:...]]和反链。补孤儿识别对正式文档/正文相对资源、历史原owner目录、回收站及在途提案保护；共享任一引用保留，未知或损坏保守报告，不扫描受控roots外文件。既有清理仅识别record metadata/project index，缺少正文/历史/回收站证据，本项按必要正确性补齐并回归。
- ZIP：保留平铺Markdown文件，包含所选文档受控实际引用附件，去重映射assets/...；只改导出副本body及metadata的相对路径，不写回源；成员校验、同名冲突与解压真实读取测试。裸.md仍为不带二进制的单文件。
- 预计文件：workbench/assets/documents/repository/attachment_prepared/agent_attachments/agent_attachment_execution/agent_upload_policy/http_api及引用、安全、历史必要接点；共享Markdown/文档保存宿主与app/index；test_document_attachments及现有资产/Agent/HTTP/浏览器回归；DATA_FORMAT/ARCHITECTURE/README/使用/维护/计划/台账/验收。
- 计划验证：临时目录格式往返、真实重载、路径/MIME/大小/流中断/冲突与有界内存；共同授权和两确认/取消/并发/分类迁移/各写阶段故障及os._exit恢复；共享引用/历史/回收站/孤儿旧行为；ZIP临时解压字节；真实Edge两编辑器往返和上传持续输入/切换/草稿/外部修改，两主题×桌面窄屏；相应Node、必要全量Python、全文件语法及diff/文档检查。未执行不写通过。
- 风险：旧清理缺失引用会误删，先补保护再开放文档上传；长流不能持业务/凭据锁，正式写入需版本复查；二进制与Markdown非单文件事务，Agent沿用持久恢复，普通网页中断可能留下保守保护/可报告孤儿，不发布伪链接；外部文件竞态及未知格式需fail closed，不迁移真实库或更改真实客户端。

### 2026-11-09 / AG-133 / 完成

- 完成范围：知识库front matter有序attachments，写盘JSON字符串/兼容既有对象读取，单一文档分类及稳定ID；全局受控字节与相对链接；普通网页流式上传/保存草稿保护/完整操作发现恢复回收，Agent document共同授权及attachment@1；引用/反链/历史/回收站/共享孤儿保护；带附件的知识ZIP副本。没有第二索引/文档类型/编辑器、任意文件路径或Agent二进制下载。
- 数据/API兼容：旧无attachments文档及未知meta可读，非业务project_id不参与文档归属；普通保存/历史同时保持附件项、顺序、原字段/换行/引用。旧record/project附件格式与policy2其它owner不变，旧null/stage/休眠grant不扩权。新普通路由不依赖Agent，Agent Authorization仍被拒；私有过程目录不是事实源，不进静态/ZIP，终结墓碑保留幂等。迁移要求未决或未释放来源先恢复/回收；未知/放弃残留保守人工核查，不回滚文件。
- 自动实际：冻结全量366项544.997秒通过（1原生符号链接权限skip），发生在最后补充边界前；相关95项223.548秒、尾审52项78.571秒、旧HTTP/资产及百分号24项11.077秒、真实退出/回收/100MiB与web+Agent HTTP/MCP14项31.548秒通过。后续迁移/源重现/真实回收/屏障3项6.437秒、未知meta2项1.098秒、JSON字串/保存/历史/MCP5项7.119秒、旧boolean对象/真实退出/Agent3项7.737秒、媒体与HTTP19项13.071秒、平台/路径与web HTTP7项4.963秒、媒体扩展契约1项0.882秒通过。当前新增发现数不冒称整组一次全绿，完整批次见本机验收。
- 22Node分批全部通过，最新普通文档浏览器还验证保存失败不发流、持续输入/暂停及恢复autosave、切doc/关闭、丢响应/刷新/草稿/原ID查询、409保留输入/冲突选择、维护UI实际compacted、%3A等合法字面名/同名不同目录图片、两编辑器往返、浅深/1440/390；原record/project的WAV及VP8 WebM四个原生媒体页真实加载/播放请求、duration/尺寸通过，无新增播放器/转码依赖。原Agent文档共同批准/local_web与下载也通过。八张文档visual/read主题宽度截图已逐张目视，仅Temp评审不提交。
- 真实Codex0.163.0-alpha.10.2/MCP2025-11-25/20工具，旧四类型/两确认/重试取消重启撤销通过，0模型turn、真实用户配置未改；原始MCP正式附件project/document实际prepare/preview/commit/get/replay/拒path通过，不替代142。capabilities执行版本如实列1/2。
- 100MiB真实字节各样本Python峰值<8MiB（最后关闭组447944B），仅有界流/字节场景，不称性能基线；1001合成终结日志后仍可真实新上传/查询原回执，不称1001端到端。真实web11退出点、终结3退出点及Agent15阶段×issue/document、同字节换身份不删、1GiB精确声明预算与回收已覆盖。
- 失败保留：初轮362项524.413秒3失败1错误，父/子进程在运行期间加载了不同partial字段，另fixture重复mkdir；不能用作最终门禁，冻结后366通过。初期body误入metadata、旧对象JSON读写类型、renderLink未透传、URL括号/百分号歧义、孤儿转义括号误报、屏障异常映射500及媒体全局helper影响均修复复验。浏览器既有Agent刷新/Editor启动及一次新文档刷新失败根因仍未证明，独立复验通过；GBK批次输出中断、测试长度/HTTP状态和负向URL编码错误均记录，不改超时/业务断言掩盖。
- 关键决定AG-LOCAL-DEC-037～042。APP_VERSION2026.11.09.7，修改JS/CSS缓存20261109-7。82Python/48JS全文件语法、文档UTF-8/围栏/相对链接及最终diff收口核对；详细证据见本机能力验收AG-133。
- 保留边界：仅Windows固定NTFS（不支持分支仅模拟），O(历史操作数)元数据预检/墓碑成本，未知/放弃残留人工核查、同步OS等待及外部FS竞态；不是多文件原子事务，不宣称独立性能/视觉基线或142真实模型矩阵。本项无自动审批拒绝或清理遗留，不读取真实来源/认证材料、迁移真实库或修改真实客户端配置。完成后交监督审查，134～143不自动开工。
- 实际修改文件：`AGENTS.md`、`README.md`、`app.js`、`css/knowledge-base.css`、`docs/AGENT_INTEGRATION.md`、`docs/AGENT_USAGE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md`、`docs/AI_AGENT_PROGRESS.md`、`docs/ARCHITECTURE.md`、`docs/DATA_FORMAT.md`、`docs/MAINTENANCE.md`、`index.html`、`js/editor/document-model.js`、`js/features/agent-settings.js`、`test_agent_attachment_workflows.js`、`test_agent_attachments.py`、`test_agent_workflows.js`、`test_assets.py`、`test_document_attachment_workflows.js`、`test_document_attachments.py`、`workbench/agent_attachment_execution.py`、`workbench/agent_attachments.py`、`workbench/agent_proposals.py`、`workbench/agent_service.py`、`workbench/agent_tools.py`、`workbench/agent_upload_policy.py`、`workbench/asset_references.py`、`workbench/assets.py`、`workbench/attachment_prepared.py`、`workbench/document_attachment_http.py`、`workbench/document_attachments.py`、`workbench/document_export.py`、`workbench/document_uploads.py`、`workbench/documents.py`、`workbench/http_api.py`、`workbench/paths.py`、`workbench/repository.py`、`workbench/write_coordinator.py`。

AG-133提交前最终检查：82个Python/48个JavaScript全文件语法通过（编译输出临时目录），10份修改Markdown UTF-8/围栏/78个相对链接通过；git diff --check通过，39个目标文件无业务数据、凭据、日志、截图或用户既有修改。按本轮测试前缀筛查Python/Node/Edge进程无匹配残留；AG-133已完成、AG-134～143待开始。用户报告删除的历史合成目录已只读确认不存在。

### 2026-11-09 / AG-134 / 开始

- 起始e0a5a88、工作区干净；监督已接受133并派发134，总体执行授权持续，唯一执行写入。135～143待开始，不开放Agent concept_map工具/类型或休眠许可。
- 精确范围：磁盘原始字节SHA-256 revision、领域Prepared JSON条件写入与原字节历史；HTTP条件更新/历史读取恢复；画布自动保存/关闭flush/网页并发冲突、保留当前输入与撤销栈、保存重开。保持version=2与原宽容归一化、节点边ID/类型/箭头/视口/各限制。
- 盘点：create/update、兼容_write_concept_map、分类rename/delete逐图写入、图库单图分类PATCH、画布autosave/flush、回收站移动/恢复、完整ZIP和浏览器JSON/PNG导出。无图历史现状；普通画布关闭忽略flush失败，本项修正；页面导航和卸载保护需接入。
- 方案：HTTP修改已有图必须非空expected_revision（缺失409要求刷新，阻止旧缓存页静默覆盖）；Python旧调用缺字段在共享锁内读取当前字节并生成条件Prepared，保留兼容但不宣称客户端CAS。快照history/CMAP-ID/时间UUID.json为原字节，无独立索引/新日志；先快照再目标，阶段失败保留证据、不自动重放，重试必须重新读取版本。历史恢复走同一归一化/Prepared和当前CAS，未知未来version快照拒恢复、原样保留。
- 预计文件：concept_maps/history/write_coordinator/repository/http_api、concept-map/app/index及必要既有生命周期接点；概念图领域/HTTP/真实Edge/前端测试；数据格式/架构/维护/README/AGENTS/本机方案/验收/台账。
- 验证：临时目录重读/原字节hash/旧调用格式/限制/非法字段/并发409/分类/回收/导出，历史阶段异常及真实退出、不重放未知证据；真实画布自动保存/关闭flush/失败保留/撤销重做/冲突明确选择/重开/JSON/PNG，浅深1440/390及长中文空/大量图；冻结代码后全量及必要Node/全文件语法/diff。风险：旧HTTP写调用有意拒绝，Python兼容仍不保护无版本客户端；快照与目标非多文件事务、外部FS最终检查/replace间竞态、历史保留成本/异常残留均需如实记录。

AG-134阶段验证（2026-11-10，尚未完成）：13项概念图专项1.877秒通过；相关server/http63项16.049秒通过。冻结源码/测试后全量384项599.704秒，1错误/1权限skip：既有100MiB暂存complete阶段触发5秒source_timeout，单独原限制复验1项2.232秒通过（5996265B峰值、1.83秒）。不将该全量记为通过。22Node批次21通过，concept项3.186秒在fixture清理EPERM遮蔽早期结果，业务是否跑完未知；此前独立新增概念图全流程通过是另批事实，不能替代该失败。测试夹具弹窗等待、快速close事件已修正后独立通过；失败记录保留。

阶段尾审：全量结束后补同一open世代的成功离开失效/迟到响应等待期间输入保护、本按钮hidden选择器、历史恢复409在原clean状态仍保留草稿并阻止离开。不会将后续边界补测冒称冻结全量覆盖。APP_VERSION2026.11.10.1及对应app/concept/CSS资源缓存20261110-1；该尾审仍待最终浏览器回归。

本轮清理待办：冻结Node失败留下精确目录Temp/workbench-edge-concept-PQSsuE及Temp/workbench-concept-HsEGyp；只读无对应浏览器进程。限定路径/名称/无reparse的PowerShell删除仍被自动审批blocked by policy拒绝，未绕过，已异步请用户手工删除，尚待回复和只读确认。不得写无遗留或提前完成134；历史另一个非本轮目录未操作。

AG-134最终冻结全量（2026-11-10）：最终源码/测试固定后顺序python -m unittest -v，384项598.002秒OK（1原生符号链接权限skip），exit=0；全程未并行浏览器批次、未修改源码/测试。既有100MiB暂存本组5379728B峰值/4.342秒在原5秒界限内通过，正式copy1851480B/1.468秒、web445873B。首轮失败与单独复验保留，不推断唯一资源/OS原因，不替代独立性能基线。

最终concept Node完整exit=0两次，最后一次等既有applicationFeature.start() Promise完成后复验通过；不是仅等started（其语义为初始化开始，home不会设置navigation-restoring）。新增返回值诊断保留，一次page仍为home失败不作唯一根因归因。源码未扩改产品初始化。覆盖原zoom/gesture/undo/redo/保存重开及新CAS选择、覆盖确认再次变化、clean历史409的dirty草稿/flush保护、真reload恢复、草稿失败提示在同一input事件读取、JSON剥离传输字段/PNG有效字节头、成功离开/失败保留/A迟到B正确与实际computed display。保存期间入口disabled，所有结束分支恢复；正常状态hidden被通用display覆盖的尾审已用专属选择器修正。四入口/模块/样式依赖Node通过；其余21Node已有冻结批次通过，导航相关附件/编辑器回归另在最终全量后运行。

最终八图目视（原画布/冲突×浅深×1440/390）：无页面横向溢出，正常状态无冲突按钮，错误状态入口文字清楚；窄屏独立一行，旧空白工具按钮显示文字，标题/焦点字段在原单行空间内裁切而不覆盖控件。截图仅Temp评审不入Git。当前尚待两个被拒目录手工清理确认、最终文档检查/依赖结果和提交，134保持进行中，135不开始。

AG-134独立验收收口（2026-11-10）：最终全量后仅追加两项导航依赖浏览器，test_agent_attachment_workflows.js exit=0/20.774秒、test_editor_workflows.js exit=0/71.935秒，原始日志仅Temp；没有继续改源码或测试。22Node按批次最终均有通过证据，不冒称首轮整组通过。代码、缓存和领域/API/UI证据已就绪，仍待两个被拒目录手工清理确认后方可结项和提交。

AG-134实际目标文件（20）：`AGENTS.md`、`README.md`、`app.js`、`concept-map.js`、`css/concept-map.css`、`css/responsive.css`、`docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md`、`docs/AI_AGENT_PROGRESS.md`、`docs/ARCHITECTURE.md`、`docs/DATA_FORMAT.md`、`docs/MAINTENANCE.md`、`index.html`、`test_concept_map_frontend.js`、`test_concept_map_workflows.js`、`test_concept_maps.py`、`workbench/concept_maps.py`、`workbench/history.py`、`workbench/http_api.py`、`workbench/repository.py`。

AG-134提交前独立材料检查（2026-11-10）：82Python/48JavaScript语法、8份修改Markdown UTF-8/围栏/67相对链接、四个资源缓存20261110-1及135～143待开始、git diff --check通过；最终status仅20个目标M，无新增生成物/业务数据/凭据/日志/截图或用户既有修改。按本轮concept/attachment/editor fixture前缀查Python/Node/Edge无匹配残留。两个已拒目录最后只读仍True，未再次删除/提问；代码/测试不再修改，提交说明已拟定为Add conditional concept map writes and history，等待清理确认后完成状态和本地提交。


### 2026-11-10 / AG-134 / 完成与清理记录闭合

- 监督更新管理决定：用户最新明确持续执行方案；此前“两个Temp残留清理前不得结项”是监督的管理安排，不是AGENTS或用户强制条件。代码/验收/20文件diff已经只读审查通过，独立合成测试残留不影响应用正确性或AG-135依赖，故应作为独立清理待办而不阻断已验证逻辑修改。保留上文等待、EPERM及blocked by policy原始事实，不抹历史，不再次工具删除/换工具绕过/重复提问。
- 本次只读复核结果：workbench-edge-concept-PQSsuE及workbench-concept-HsEGyp两个精确Temp路径Test-Path均False，对应Python/Node/Edge进程无匹配。未收到新的手工删除回复，故只陈述当前目录已经不存在，不补写是谁或何时删除。两处实际残留已不存在，此独立待办按只读现状闭合；自动审批拒绝作为历史保留。
- 功能与验证完成：原字节revision/条件Prepared JSON及历史、网页冲突/草稿/flush/迟到保护、分类/回收/导出接点均完成；数据/API兼容、原生/外部FS/历史增长/非多文件事务边界见本节与DATA_FORMAT。最终冻结全量384项598.002秒OK/1权限skip；22Node分批通过，最终导航附件20.774秒/双编辑器71.935秒通过；八图逐张目视、82Python/48JS及8Markdown/67链接通过。首轮384失败及后续复验不互相覆盖，无源码/测试尾改。
- 实际文件为上列20个；决策043～046、APP_VERSION2026.11.10.1与四资源缓存20261110-1。最终仅状态/文档记录变更及diff核对后按13.1独立本地提交；下一项仅AG-135获监督派发先设计，136～143不开始。没有真实数据/客户端配置修改或模型turn操作，无新的功能阻断遗留。


### 2026-11-10 / AG-135 / 开始（设计）

- 起始9e43aa3，git status --short干净；监督已接受134并继续派发135，用户持续执行授权有效，唯一仓库写入者。仅登记、读码/测试盘点和设计讨论，当前未改业务代码；136～143待开始。
- 精确范围：concept_map只读发现/完整读取、create/update完整候选、明确新鲜授权与两确认策略、唯一ProposalStore/静态concept_map@1、持久预留身份、AG-134同域Prepared JSON/历史及崩溃恢复、完整画布+全量明细/差异/警告预览与结果深链。无delete/局部patch/配置创建/模型调用/运行时依赖。
- 已盘点：agent_security的授权版本/休眠grants/allows，CredentialManager原私有快照日志和分类收窄hook；service normalize/prepare/submission/dependencies、ProposalStore schema3/全量预检/批准/恢复/终结清理及reserved_resource_ids；AG-134图create尚max(formal)分配且内部添加默认根节点，需同域prepare_create与统一占用；管理预览通用正文模板需图分支，既有画布全局事件/查询需readonly实例范围隔离；navigation显式图深链、工具schema与MCP1MiB输入/8MiB响应上限。
- 拟定范围/文件：concept_maps/repository/id预留；agent_concept_maps及必要静态execution adapter、agent_security/management/runtime/HTTP/service/tools/proposals/proposal_management/CLI；concept-map readonly工厂、agent-proposals/settings/navigation/app/index及必要CSS；新图Agent领域/授权/真实退出/MCP/管理/浏览器测试及既有门禁；AGENTS/README/计划/台账/验收/格式/架构/接入使用维护。以最小接点为准，不建立平行CRUD或提案状态机。
- 计划验证：旧configured/全项目/全分类不扩权、read/propose/commit与资源/操作/最低确认交集、分类/项目/授权变化；严格字段/类型/非有限数/重复ID/关系/限制/保留ID/完整字节预算；create预览零正式图/目录/历史，预留与网页创建/回收/在途并发、终结后不重用；前后字节/历史/固定时间/批准/回执各阶段真实退出及未知零写、第三方修改/删除/响应丢失/幂等；真实两确认完整明细/画布/差异和旧版本批准拒绝，浅深1440/390/大图/焦点/错误/无后台画布副作用，结果深链保存/冲突/undo/redo/导出。最终源码冻结后全量及必要Node/MCP/真实CLI回归只用隔离数据/配置，0模型turn。
- 主要风险：新图授权格式须兼容且旧程序拒绝新证据；不能复用旧休眠配置为active；身份预留与普通网页ID分配必须同锁同占用源，取消/过期不释放已展示ID；preview/commit同一归一化不静默截断；readonly预览不能触发主画布全局监听器或保存；分类权限先收窄失败不得扩大到未分类；图操作日志不得走旧Markdown路径/清理假证据。设计提案见方案22节，重大格式选择先报监督，不宣称实现完成。

AG-135设计获监督接受（2026-11-10）：先同步方案22节七项收口再实施。图授权新registry4/auth5/log5及旧快照窗口/所有family保留门槛；proposal持久预留和全占用未知fail closed；稳定ID只查唯一完整结构匹配、不作语义猜测；256KiB图数据/1MiB原始base与请求/2MiB完整preview的字节层分开；execution_schema3同Prepared与纯prepare零副作用；readonly实例root/lifecycle契约纳入135，票据不宣称人眼阅读证明；新增两只读工具和深链按真实测试目录验收。代码稳定后冻结全量，不与源码修改混跑。接下来先实现领域严格验证/纯prepare及兼容保护，再接管理与唯一提案引擎，136不开始。


2026-11-10监督兼容边界修订：首private snapshot→operation log→registry fence顺序保持，不增加全局阻塞标记。旧管理/恢复/客户端变更入口扫描到孤儿新快照时必须零JSON写拒绝；root4/log5或图proposal/manifest存在后，只对实际经过相应格式门槛的旧Agent授权/提案恢复写入口声明拒绝。首快照但root/log未升的窗口尚无新增图权限生效，旧dormant不激活；已经运行的旧HTTP业务可按旧有效授权继续，普通无凭据网页也不必经过registry，不能概称所有旧业务零写。真正授权发布/图提交前重查client_version和目标/依赖版本，窗口内合法旧修改造成CAS/依赖冲突而不静默覆盖。测试按每个真实退出点和入口分组，证明旧管理不覆盖新快照/授权且active grant发布前root fence已持久；保留混用版本/外部FS与非秘密摘要不能证明文件作者的边界。此前更宽的“旧代码零写”目标以本修订限定，不抹原讨论。

AG-135授权基础阶段（2026-11-10，仍进行中）：严格完整图候选、纯领域prepare_create、唯一结构证明的ID保护已实现；原网页宽容规则/default root保留。实际registry4/auth5/log5与concept_map_grants独立新鲜批准，不激活dormant；文件/暂存/正式附件/通用edit/rotate/revoke/withdraw保留auth5及图字段。管理完整资源预览零正式写入，批准票据绑定会话/运行代/客户端版本/资源集合；持久签名绑定原批准摘要，响应丢失在票据过期后仍可查询/重放原回执。分类rename/delete/移除空分类先持久收窄图grant，业务后续失败不恢复/扩大；复用原CredentialManager日志和领域回调，不另建事务。

阶段实际验证：此前18项图专项10.349秒、相关46项26.951秒通过（UTF-8夹具修正后）；新增管理分支后图/旧管理/休眠能力/原概念图62项40.383秒通过。加入完整预览/会话与资源过期/幂等/分类失败及受控路径后22项12.564秒通过；新增同源HTTP授权边界1项1.127秒通过。包含7个真实os._exit点与9e43aa3旧管理零JSON写拒绝；旧普通业务可合法写、后续依赖冲突拒发布的兼容限定保留。新路径读取复用现有safe_local_path，拒重解析/硬链接和越界，原始图1MiB有界读，不把损坏/未来图静默略过。设置页源码/Node语法与diff检查通过；首轮真实浏览器因新夹具预期创建返回200但实际201中止，已纠正并复验中，未声称UI通过。尚未开放图只读工具、提案执行或标记135完成；本次无全量冻结门禁。

历史清理补充：用户本轮明确回复已删除Temp/tmp0u2oav7r，随后只读Test-Path False。该路径属于此前已经闭合的历史合成清理，本次仅补充用户回复与当前不存在的事实，不列为135新增残留、不再次工具删除或重复询问。

AG-135管理阶段复验：真实node test_agent_settings.js完整exit=0，新增新鲜图范围/完整资源与版本/取消/批准/丢响应刷新查询/撤销/dormant保留及原设置/文件/暂存流程通过。四张图授权浅深×1440/390截图已逐张目视，JSON完整换行，按钮/focus可见，无页面横向溢出；仅Temp评审。首轮新夹具201/取消按钮错误及后续窄屏布局复验失败保留；改用既有agent-scope字段组避免窄屏控件撑开，并与原宽度验收相同等待100ms完成响应式布局后严格复验通过，未更改宽度断言。领域候选专项首轮因夹具未先建所要求既有分类而失败，明确建分类后3项0.691秒通过：纯prepare零写/固定时间与原历史往返、named-only不能reparent/拒伪造身份时间/append、未知顶层保留与旧节点额外字段显式警告。图+原概念图36项17.844秒通过，不称完整冻结全量。

AG-135范围补充已获监督接受：此前无更新历史的网页图永久清除后缺占用证据，登记决策047，以最小单调config/concept-map-ids.json游标补齐统一分配契约，不改RF历史。预计修改领域分配/占用源、repository及首proposal领取接点，补并发/各发布前真实退出/失败跳号/取消及永久删除/完整ZIP解压重实例/实际迁移/坏格式零写；完整ZIP和迁移复用原实现，无新增导入格式或Agent删除能力。兼容缺失游标、历史不可追溯、人为部分恢复及旧并行进程边界按决策记载；当前开始实施，不提前写验收结果。

AG-135单调分配阶段：新增concept_map_ids及6项专项；真正create先归一化校验再领取身份，counter与全部占用取max，purge先保留上界，图恢复同ID占用409不改名。最新图/管理候选/HTTP/原图/编号45项23.290秒通过，包含12线程并发、失败跳号、无历史图全部永久清除后重实例、两真实os._exit（游标已写/正式发布前）、完整ZIP解压后重实例和实际copytree迁移、旧formal/history/trash/孤立trash派生及坏格式零写拒绝。第一组45项22.317秒1失败暴露JSON null被当作缺文件，已按exists单独校验修复复验；之前新旧39项20.133秒1错误因新图专用占用提供器夹具仍返回DOC身份，改为明确图ID集合并保留未知提供器拒绝用例。Agent首proposal领取、取消墓碑和新图manifest仍待贯通，不声称该接点已验收或135已完成。

AG-135图提案执行接点阶段：已接同一ProposalStore的concept_map@1、outer manifest3/execution_schema3、固定身份schema1、完整base/candidate/diff/warnings绑定的sha256-json-v3预览、before/after.json及AG-134 Prepared/原字节history。首create先领取共享游标再原子存proposal，仅后者绑定request/client/workspace；重试先查原提案，revision沿用身份，取消/过期/清理保留身份与游标。3项完整create/提交重放/磁盘重开、revision/cancel/墓碑/网页避让、update原历史与外改拒绝通过；加入create/update各10个真实os._exit后4项14.079秒全过。prepared未发布可重查权限依赖后续办；create applying但目标缺失阻断并需明确abandon，不重建；after/history证明后仅补回执。尚待完整只读画布、只读工具、结果深链及更多边界/两确认浏览器和最终冻结门禁，135仍进行中。回收站图原冲突行为是自动改文件名但内部ID不变，本项仅图分支改409，避免产生不可按稳定ID发现的副本，不改记录/文档/项目分支；相关回归仍待补。

AG-135最终冻结起点（2026-11-10）：最后49项图/编号专项37.621秒通过；PNG真实Node完整exit0，长中文、多行、特殊字符各关系行完整绘制，颜色一致，测得变换后的文字范围均在导出画布内且保持原5000px界限；JSON导出节点/边/说明/样式原样且无传输revision。PNG仍沿用既有节点栅格摘要，不替代全量JSON/提案明细，不扩为重设计。新源数据缺省归属/无version往返0.374秒，graph-only无项目正文和effective交集等6项1.745秒，收窄保留inactive kind及重算摘要仍不能扩大资源/scope0.647秒通过；原图管理10项14.013秒通过。新图实际首存/修订前亦校验静态契约，CMAP身份新接点统一ASCII以对齐HTTP/MCP/深链，拒非法身份不污染持久提案。

冻结内容为151个源码/测试/HTML/CSS文件SHA（快照仅Temp），89Python/49JS全文件语法、10修改Markdown UTF-8/围栏/85相对链接通过；APP_VERSION2026.11.10.2，app/concept-map/navigation/agent-settings/agent-proposals及concept-map.css六资源20261110-2。现顺序python -m unittest -v，再23Node及隔离真实Codex旧流程，期间不改实现/测试；文档仅补实际结果，AG-135保持进行中，136不开始。尚未执行的最终门禁不写通过。

AG-135首次冻结全量实际失败（2026-11-10）：433项403.403秒，1 failure/1 skip。唯一失败为原生文件不支持分支的旧implemented==[]断言；135的独立图实现不依赖Windows文件句柄，该断言遗漏新增concept_maps.read/write。撤销首次测试冻结，仅修改test_agent_files对应断言为精确两项图能力并新增effective==[]；原三项文件操作unsupported_platform逐一断言和旧业务可读断言均保留，无实现变更、未放宽安全条件或超时。该专项1项0.206秒通过。重新冻结151源码/测试后重跑完整门禁，首轮失败保留。

监督补充同模拟分支显式证明未批准图grants/operations为空；为加入两条更严格断言，主动中断刚开始的第二次全量，不将中断记为通过。未修改实现。最终该项+capabilities 14项13.475秒OK；再次冻结151文件后重新顺序全量。此为模拟平台分支，非真实非Windows验收。

AG-135最终冻结全量Python（2026-11-10）：python -m unittest -v，433项419.257秒OK，1项原生symlink权限skip；非Windows仅模拟分支覆盖。未再修改源码或测试。相比首轮只更新文件模拟分支的精确implemented及空effective/grants/operations断言，无实现变化。23Node正在顺序执行，真实隔离Codex仍待运行，状态保持进行中。最新四张浅深1440/390完整图预览已逐张目视：适应全图后节点和关系可见，焦点/按钮清楚，长中文正常换行，无页面横向溢出；全部明细仍需滚动查看，票据不证明人眼阅读。

AG-135冻结Node首批：attachment18.879秒、新图19.595秒、proposal18.681秒均exit0；settings18.961秒在原登记reload第111行超时，诊断仅page unavailable/无页面横向溢出，现有证据不能确定根因。原样单独复验25.606秒越过该处，但第338行旧提示文案断言失败：135提示已改为无旧业务条目权限并说明图独立授权，测试仍查无旧业务数据权限。仅同步该条精确完整提示断言，保留前置空kinds/project_ids/categories/dormant断言，不改实现/超时。两失败日志与stderr留Temp，fixture终于清理无异常，当前对应临时目录无残留；不将已通过3项写成首轮23全绿。重新冻结151文件，唯一变化test_agent_settings.js；Python源码/测试摘要全部未变，其433项419.257秒通过仍有效。重新顺序运行23Node，首次超时根因未知保留。

AG-135设置复验第三次38.428秒失败在新增图撤销尾部第548行：磁盘仍旧read grant而catch busy=true。代码顺序证明确认helper仅click，dialog close续体尚未设busy时旧panel存在/不忙条件即可满足，磁盘断言早于DELETE完成；首次登记reload超时原因仍未知。仅加强测试：捕获真实DELETE完成响应状态，等200、dialog关闭、无pending/busy及重载panel空范围后再读盘，原空grant/kinds断言不变，无实现/超时改动。重新冻结151，唯一变化仍该JS测试，Python433/419.257秒及首批3Node证据有效；先完整settings再余下19Node，不称首轮整组通过。

加强DELETE完成/空panel同步后完整settings exit0；监督要求观测精确同客户端endpoint、返回操作/版本与GET重载版本一致并finally还原fetch，继续最小加强该JS测试，未改产品/Python或超时，再冻结后完整settings复验。上一通过仅阶段同步证据，不冒充最终测试版本。

### 2026-11-10 / AG-135 / 完成

- 完成范围：新鲜图授权、完整只读发现/读取、完整create/update提案及两确认、唯一ProposalStore静态concept_map@1/执行schema3、稳定身份/共享单调游标、原字节历史与恢复、readonly全图/全部字段/差异/警告、严格结果深链。无delete/配置创建/项目创建或模型调用；136～143未开始。
- 最终自动门禁：python -m unittest -v，433项419.257秒OK/1原生symlink权限skip。23个Node按批次全部exit0：首批附件18.879秒/新图19.595秒/提案18.681秒；settings最终完整通过并真实观测同客户端DELETE开始/200响应、operation/version与随后GET重载版本相等、空grant面板/无busy/pending及磁盘[]；其余19项全部通过，其中主图54.491秒、文档附件17.118秒、双编辑器71.858秒、项目筛选8.227秒、时间戳9.746秒。不是首轮整组全绿，前述超时/文案/夹具早读失败及复验保留；登记reload首次超时原因未知，后续完整流程通过，无断言/超时弱化。
- 真实兼容：python codex_agent_acceptance.py，exit0；codex-cli 0.163.0-alpha.10.2、协议2025-11-25、22工具，旧issue/document/todo/info、两确认、追加/更新、重试/取消/重启/撤销通过。隔离数据与CODEX_HOME，model_turns_started=0、user_config_changed=false。这是既有CLI/MCP兼容门禁，不是AG-142真实模型矩阵或对话遵规证明；新图stdio/浏览器/两确认由前述专项证明。
- 冻结/静态验证：151源码/测试/HTML/CSS最终SHA一致，89Python/49JS全文件语法、10修改Markdown UTF-8/围栏/85相对链接、git diff --check通过。Python完成后仅settings测试断言/同步加强，产品/Python摘要不变，监督接受保留433项证据；不将首次冻结失败和中断冒充通过。APP_VERSION2026.11.10.2、六资源缓存20261110-2。
- 必要人工验证：图授权与完整图预览均浅深×1440/390四图逐张目视；长中文/全量JSON换行、focus/disabled/error/空资源和500节点1000关系覆盖，适应全图后节点关系可见，无页面横向溢出。主图保存/冲突/草稿/撤销/JSON-PNG、记录与知识库可视化/Markdown/保存重开由真实浏览器通过；截图仅Temp不入Git。
- 数据/API兼容：旧业务Markdown/附件与旧execution1/2语义保持；旧图宽容读取和网页默认根节点保留，Agent严格完整候选。图新鲜批准才升级registry4/auth5/log5，旧dormant不激活；所有family保留格式下界。图恢复冲突现在409，其他类型恢复原策略不变；v2 label不再自动改ID/结构，v1/缺version仍兼容迁移。新增可移植config/concept-map-ids.json单调游标，原完整ZIP自然包含；完整解压/copytree迁移已实际验证。Graph工具22目录和服务端权限为事实源。
- 风险/边界：不是多文件事务；未知/缺历史/第三方状态保守阻断，已发布仅补原回执；游标/墓碑/历史保留增长，损坏占用停止分配。缺失游标无法区分初次升级与人为删除，升级前永久消失ID无法追溯；部分恢复/旧进程忽略游标/混用版本/外部文件系统竞态不承诺消除。资源派生全集依赖保守，无关成员变化可能需重预览。非秘密摘要不证明作者，票据不证明人眼阅读/现实身份，PNG保留既有节点摘要而非无损备份。首次登记reload超时根因未定，后续原样及最终完整流程均越过且通过，保留证据而不归因OS或新图无关。
- 决策：AG-LOCAL-DEC-047（单调分配）、048（v2稳定label/只迁移旧版）。本次无真实业务数据/私人配置变更、无新增清理拒绝或fixture残留；历史清理回复仅补充闭合。最终目标diff不含数据/凭据/日志/截图/缓存或用户既有修改。下一工作项AG-136仅为交接候选，尚未开始，等待监督派发。

AG-135实际修改文件（46）：`AGENTS.md`、`README.md`、`app.js`、`codex_agent_acceptance.py`、`concept-map.js`、`css/concept-map.css`、`docs/AGENT_INTEGRATION.md`、`docs/AGENT_USAGE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md`、`docs/AI_AGENT_PROGRESS.md`、`docs/ARCHITECTURE.md`、`docs/DATA_FORMAT.md`、`docs/MAINTENANCE.md`、`index.html`、`js/core/navigation.js`、`js/features/agent-proposals.js`、`js/features/agent-settings.js`、`test_agent_attachments.py`、`test_agent_capabilities.py`、`test_agent_concept_map_workflows.js`、`test_agent_concept_maps.py`、`test_agent_files.py`、`test_agent_settings.js`、`test_agent_uploads.py`、`test_concept_map_ids.py`、`test_frontend_entry.js`、`test_mcp_stdio.py`、`workbench/agent_concept_authorization.py`、`workbench/agent_concept_execution.py`、`workbench/agent_concept_maps.py`、`workbench/agent_concept_service.py`、`workbench/agent_execution.py`、`workbench/agent_http.py`、`workbench/agent_management.py`、`workbench/agent_management_http.py`、`workbench/agent_proposal_management.py`、`workbench/agent_proposals.py`、`workbench/agent_security.py`、`workbench/agent_service.py`、`workbench/agent_tools.py`、`workbench/agent_upload_policy.py`、`workbench/concept_map_ids.py`、`workbench/concept_maps.py`、`workbench/http_api.py`、`workbench/repository.py`。

### 2026-11-10 / AG-136 / 开始（读码与设计）

- 起始fe32140，git status --short干净；监督已接受135并派发仅136，继续唯一仓库写入者；137～143不开始。
- 精确范围：issue/todo/info/document/concept_map删除，新鲜独立许可、强制local_web、完整内容/结构/附件/引用影响预览；唯一ProposalStore静态版本处理器与领域PreparedDelete、稳定trash token/原操作、移动/索引/排序/缓存/回执证据及在途保护。无idea新增暴露、项目级联、Agent恢复/purge/空回收站/孤儿清理工具。
- 预计接点：repository及records/documents/concept_maps、统一删除Prepared基础、Agent授权/管理/服务/静态执行/ProposalStore/工具/HTTP、现有提案预览/设置/回收站必要UI、测试与AGENTS/README/计划/台账/格式/架构/维护/验收文档。精确文件在设计审查后按最小范围确定，不另建CRUD或恢复进程。
- 计划验证：完整授权/预览/取消、CAS/依赖集合变化、强制网页批准、未知版本零写；逐阶段异常与真实退出、移动后索引前恢复、并发外部移动/恢复/删除/异物、重复/丢响应/关闭Agent重启恢复；网页恢复后旧提交不再删、清理/purge/普通写在途保护、稳定ID及历史/游标/备份迁移、缓存排序真实重读。真实浏览器浅深1440/390与旧流程；稳定后冻结全量Python/必要Node/隔离真实Codex0模型turn，只用临时数据/配置。
- 已知风险：现有回收站移动后写索引不是事务，源/目标同时存在或丢失、索引异物和用户恢复会形成不确定状态；必须保持未知保守不写、不扩大授权，已移动仅凭原证据补原状态，不能重删恢复条目。附件与历史需保留，引用影响完整读取不能靠摘要替代。先报告设计、监督定稿后实现。

AG-136独立读码/测试盘点补充（2026-11-10，尚未实现）：原有test_records覆盖仓储共用回收边界/索引路径篡改；test_server覆盖单项/批量恢复永久删除、文档/图及排序；test_agent_recovery已具snapshots/manifest/committing/applying/history/target/receipt/proposal中断模式；test_agent_concept_maps与test_concept_map_ids覆盖真实退出、未来格式零写、图游标/同ID恢复409与其他类型原恢复冲突策略。136应新增五类型删除阶段矩阵，不把旧写入测试冒充新删除证据；保留旧四类create/update/append和graph/attachment执行语义。现有普通record/document冲突恢复会改文件名但不改内部ID，136不借机改此旧规则；Agent旧回执必须无论恢复位置只回原结果。现有全量433基线是135交付，不是136门禁。方案23节等待监督定稿，继续未动产品/测试。

AG-136设计已获监督定稿（2026-11-10）：23节及补充边界接受，开始实现，无需再等启动。先同域PreparedDelete（新workbench/deletion_prepared.py，records/documents/concept_maps/repository轻量接点）与test_deletions.py验证纯准备/唯一对象/原字节/同句柄NTFS无覆盖move、排序保留及缓存阶段；再新鲜delete授权（agent_delete_authorization及security/management/http/settings）、唯一提案静态执行（agent_delete_execution/service及现有Store接点）、共享引用识别器/完整预览/回执/在途保护与专项/浏览器，文件按实际最小接点增加并在完成清单列出。新首期平台限制如实capabilities，不影响普通网页旧删除规则。已接受引用宇宙和无权命中通用拒绝、每文件1MiB/实际preview2MiB、默认30天但本机可提前purge、abandon非回滚；137以后不开始。

AG-136领域基础阶段：新增deletion_prepared纯计划/受控来源/1MiB读/NTFS同句柄identity+原字节绑定/不覆盖rename，四仓储门面新增prepare_delete接点，未改普通删除/未开放Agent handler。test_deletions新增7项加旧records/concept_maps共24项3.654秒OK，覆盖五类型准备零磁盘写、目标同原对象和原字节、错误类型/缺失/idea/过期版本、相同字节替换身份拒绝、最后检查后新建异物目标仍不覆盖、权限失败/硬链接/超限、trash同字节换对象拒绝、模拟不支持平台和恶意token。索引/缓存/恢复仍留唯一执行引擎后续接入，不把领域move当完整删除事务通过。

AG-136活动引用/授权阶段（未接工具）：共享references识别既有[[ID]]/body/attachment与受控item深链及links字段，遍历info/其它用户文本；document backlinks复用同一识别器补info而不建立反链持久索引。严格active_inventory扫描正式四MD/legacy idea/项目README/图，历史和trash非活动源；拒未知未来/重复/超单文件，绑定完整清单摘要。另设内部扫描预算4096文件/32MiB总原始字节，超过即拒完整影响计划，不截断；每原文件1MiB/preview2MiB仍独立。初次41项20.776秒2错误为Temp短路径根未规范化，已按可信Repository根规范化；12项1.764秒（新增inventory/deletion及旧文档反链）复验OK。原生删除准备仍只表示领域阶段。

新鲜delete_grants/auth6/root5/log6基础和同CredentialManager快照/日志/恢复/终结保留接点已加入；尚无新Agent handler/工具/UI路由，不声称能力已开放。旧capabilities/管理/图授权42项38.005秒OK。新增5项新授权专项首轮1.943秒3错误暴露Path对象也有root属性导致CLI资源重查误取盘根，已改为识别Repository领域门面；同5项2.432秒复验全过，证明完整范围零写预览/原回执重放、空或无scope/kind/read不生效、显式attested拒绝、版本/会话/资源变化拒绝、图/删除字段及格式下界在edit/rotate/revoke保留。真实退出/旧版本拒绝/其它授权家族与分类收窄仍待验证，不提前标该阶段完成。

AG-136新管理真实退出及扫描边界：新增新授权6项7.994秒OK，含7个os._exit点及实际fe32140旧管理零JSON变化拒绝；新版按原证据恢复，首snapshot孤儿不激活，保持root5，终结私人快照清理。增量inventory已改逐文件读取/解析，不保留32MiB全量raw；只保存内部摘要/显示元数据，target调用仅留目标和命中全文，原量先拒超2MiB，最终实际UTF8 JSON响应独立计量。真4096/4097文件、32MiB/超1字节、单file1MiB/超1字节及新授权共12项21.027秒OK；未知结构/超限拒绝，不截断。

AG-136唯一提案引擎阶段：新增server-derived DeleteCandidateService、static trash_delete@1/outer3/execution4与同ProposalStore删除分支，固定token/source identity/raw SHA/完整影响/排序保留/本机批准。五类型完整prepare/preview/local approve/trash原字节/原index操作/restore/旧commit不再次删除的1项五子例4.927秒OK。首轮1项5错误，第一例原生DELETE句柄持有时permit复开源native read被SHARE_READ规则拒绝，随后全局保护正确阻止其余例创建；定向诊断确认无移动。修复为最终同句柄核验后保持源锁，permit基于该句柄已核验before字节重扫其它活动来源并重验权限/依赖，不再次打开被持有的同一源，不放宽句柄share模式或释放句柄后rename；正常路由不接受held_source参数。该阶段无真实浏览器/完整退出矩阵结论，guard/read状态/普通恢复保护/工具/UI仍在接入，136保持进行中。

AG-136恢复/保护阶段实际验证：test_agent_delete_recovery共4项85.006秒OK，包含五类型×12真实os._exit共60场景（snapshots/manifest/committing/move applying/实际move/移动log/index/index log/cache/cache log/receipt/proposal），关闭Agent式启动先恢复再清理、manifest前批准只查询not_applied、applying但无trash拒重删并明确abandon、全局guard阻止普通restore/purge/batch/cleanup/项目删除/创建/孤儿清理。移动后源重建及撤销只补原index/receipt，不碰新源；token异物index保留、abandon后残留仍保护且孤儿报告保守；未知执行版本/handler/跨字段/路径/token/时间/回执零JSON写预检，不能以abandon绕过。后续加强held-source为只在真实DELETE句柄生存期有效的内部能力，普通HTTP/Agent参数拒held_source，伪造PreparedDelete/失效能力拒绝；不开放重新构造快照写源。

新增授权/来源/领域19项20.334秒OK，含文件/暂存/附件family保持auth6/delete字段、分类后续失败已收窄且不扩大未分类、无权活动命中通用拒绝且不漏未匹配ID/标题/路径、README命中不隐式授全文读、集合变化/CAS和禁止替换content/path/body/held_source/attested；另旧capabilities/原生文件模拟及相关28项35.695秒OK。新图只读删除显示不产生图候选，独立1MiB读取/2MiB响应预算；原create/update的256KiB默认验证接口不放宽。

浏览器接点正在验收：删除新鲜范围完整预览/取消/批准丢响应后reload查询、删除影响全部source/双readonly图、回执/原回收站链接、保护按钮及原流程。首轮400来自夹具授权未先建立既有未分类；后续夹具误假设记录文件名仅ID，改为既有file_path；Windows短路径/大小写边界用native realpath规范化保持同目录断言。一次授权reload后显示home并超时，原因尚未确定，后续加实际startup路径/状态诊断原样越过，不据此归因；取消后续点确认超时为等待只看dialog关闭，已补现有isBusy/confirming结束的状态同步，未增超时或删产品断言。完整浏览器尚未通过，不先宣称UI完成。


AG-136收口补充：原索引必须在移动前完整验证并绑定原字节SHA，before.md/json与index-before.json先落manifest。移动前索引任何变化（含无关变化）保守要求重预览；移动后的恢复仅并入原token，不覆盖其他成员，快照不授权重建索引/源。补充后29项128.360秒OK，含60真实退出。实际HTTP+原始stdio两项首轮夹具缺管理标记403；补齐后发现HTTP通用回执装饰错误改写删除链接，产品严格核对服务端稳定token/受控trash path并保留，2项2.522秒复验OK，普通四类/附件/图旧链接随后全量回归。工具不能输入任意path影响该分支。

新必要负例：未知/重复回收索引预览零JSON写、移动前index变化、相同字节替换源物理身份拒绝、实际UTF8 JSON2MiB及超1字节、终结30天原文/索引快照清理后仍恢复/返回旧回执、已完成完整目录+匹配私人配置copy迁移及游标保留。初次7项17.474秒1失败仅Temp长短目录未规范化，改resolve保持受控目录断言并增加旧源仍不存在，迁移专项1项1.400秒OK。增量活动JSON解析拒重复字段，防止正文引用被后字段覆盖。无数据格式迁移或真实配置变更。

最新node test_agent_delete_workflows.js完整exit0，新增撤销真DELETE200/operation version与GET重载expected_version一致、空delete grant及原图read仍保留；不是在响应前读磁盘。8张布局稳定后的浅深×1440/390授权/完整双图预览逐张目视，JSON正常换行、按钮/focus可见、无页面横向溢出。第一次reload未知原因继续保留，后续完整reload初始化诊断及最终流程通过。APP_VERSION2026.11.10.3，实际修改app/navigation/agent-settings/agent-proposals/trash五资源20261110-3，图工厂/CSS版本不变。

2026-11-10用户监督对话新指令：“完成当前任务后，先暂停下任务执行，等待我的指令”。当前任务边界为AG-136收口、必要门禁、独立本地提交及交监督审查；完成后暂停后续，不登记开工/设计/实施AG-137或其他后续任务。此前持续执行授权保留为历史，不再作为自动衔接后续工作的授权。

AG-136最终冻结Python：python -m unittest -v，469项569.157秒OK/1原生symlink权限skip。163源码/测试摘要仍冻结，无实现或测试修改。24Node正按文件顺序执行，隔离真实Codex尚待；仍保持进行中。100MiB附件copy/staging/文档网页流实测有界Python内存，非独立性能基线。

AG-136冻结Node首轮：附件17.984秒/图16.826秒/新删除15.058秒exit0；旧提案25.563秒因精确回执提示断言超时，实页为“已查到原操作回执。”而旧契约为“已查到原入库回执。”。定位为136把通用提示改名影响旧入库流程，恢复产品按operation分支：旧入库提示原样，delete明确删除回执/移入回收站。不改测试断言或超时。撤销首轮JS冻结，仅agent-proposals.js两处文案变更，163重新冻结；全部100 Python/测试摘要未变，其469项569.157秒证据保留。完整24Node重新顺序运行，首轮失败/日志保留，不称首轮全绿。

AG-136最终冻结Node复验：24个文件顺序全部exit0；附件21.544秒、图16.837秒、删除15.150秒、旧提案14.926秒、设置38.193秒、旧Agent23.090秒、主图49.857秒、知识库附件12.499秒、双编辑器72.039秒、项目筛选8.194秒、时间戳12.152秒，其余模型/核心/选择器/CSS契约通过。首轮提示失败继续保留，最终只有agent-proposals.js两文案分支变化。额外在Temp载入冻结删除浏览器测试并加入两处精确UI等待，实际完整运行exit0，确认“已查到原删除回执。”及“已批准并移入回收站。”；旧提案冻结测试已验证原入库回执提示。未修改仓库测试或超时。额外驱动初次只加载module未调用main，不计验收；随后显式调用完整main并输出实际通过记录。隔离Codex正运行，尚不标完成。


### 2026-11-10 / AG-136 / 完成，后续暂停

- 完成范围：issue/todo/info/document/concept_map单条delete，新鲜独立delete_grants、强制local_web、完整原文/匹配来源/结构图/附件元数据预览；唯一ProposalStore/trash_delete@1/execution4、领域PreparedDelete、NTFS同句柄不覆盖移动、原索引快照/CAS/仅本token合并、排序保留与cache、原回执及在途保护。无Agent恢复/purge/项目级联/新建配置，137～143未开始。
- 最终自动检查：python -m unittest -v，469项569.157秒OK，1项Windows原生symlink权限skip；100 Python/50 JS全文件语法、163文件最终SHA一致、10修改Markdown UTF8/围栏/相对链接及git diff --check通过。24Node最终逐项全过，包含设置/新删除/旧入库、图、附件、双编辑器/保存重开、核心和CSS契约；首轮旧提示失败及仅JS两文案恢复过程已保留，不称首轮全绿。Python源码/测试摘要未变，其完整证据保持有效。
- 真实兼容：python codex_agent_acceptance.py exit0，codex-cli 0.163.0-alpha.10.2、协议2025-11-25、22工具，旧四类型与两确认/追加更新/重试取消重启撤销通过；临时数据/隔离CODEX_HOME，model_turns_started=0、user_config_changed=false。不是AG-142真实模型/对话遵规矩阵；新增删除的实际stdio/HTTP与强制网页批准由专项证明。
- 必要手工/浏览器验证：授权完整预览/取消/真实200后丢响应reload原操作查询、完整info与共享附件保留、全部匹配文档、双readonly图及全部字段、取消/关闭重开、原回执/回收恢复/旧重放不再删、后台输入草稿不变及结果导航flush、撤销DELETE200/当前版本与空grant和旧图read保留通过。浅深1440/390八图逐张目视，长中文/完整JSON换行、focus/disabled/错误和空范围、全图/明细清楚，无页面横向溢出；截图只留Temp。两删除精确提示另做完整浏览器实际验证。首次授权reload超时原因未知保留，后续完整初始化诊断和流程通过，不归因全部为同一问题。
- 数据/API兼容：旧Markdown、图原字节/JSON历史、附件二进制/共享资源及排序ID位置保留；新鲜批准才registry5/auth6/log6，transport2/旧执行1～3语义保持，其他授权家族与终结/abandon保留下界。工具仍22个，delete禁止替换内容/路径，旧写入仍须content。完整集合/排序/原索引依赖保守，变化需重预览。完成态完整目录迁移+匹配私人配置/日志实际恢复、游标保留；私人终结内容30天清理后原回执/恢复依据仍可用。ZIP排除.agent/.trash，不是删除事务备份。
- 风险和边界：不是多文件事务；移动证据不明、异物/未来格式保守阻断，不能从快照重建source/trash或重删恢复源。abandon接受盘态非回滚，残留仍保护且孤儿报告保守。历史/回执/身份墓碑保留增长；外部文件系统剩余竞态、原生等待/平台限制不承诺消除，非Windows只有模拟分支。全部活动扫描上限4096文件/32MiB、单文件1MiB、实际响应2MiB，超限拒绝无截断；潜在文本引用不证明任意自然语言关联。票据不证明现实身份或人眼阅读。普通记录/文档冲突恢复原文件名规则保留，图同ID仍409。
- 决策AG-LOCAL-DEC-049；无真实业务数据/私人配置变更。无新增工具清理拒绝或fixture残留；Temp日志/截图用于本机评审不提交。历史tmp清理仅当前不存在事实已闭合，不重问。最终diff只含本工作项代码/测试/文档/缓存版本，无用户既有修改、运行数据或生成物。
- 后续：遵守用户“完成当前任务后，先暂停下任务执行，等待我的指令”，136独立本地提交交审后暂停全部后续；137不登记开工/设计/实施，不自行衔接。

AG-136实际修改文件（48）：`AGENTS.md`、`README.md`、`app.js`、`docs/AGENT_INTEGRATION.md`、`docs/AGENT_USAGE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md`、`docs/AI_AGENT_PROGRESS.md`、`docs/ARCHITECTURE.md`、`docs/DATA_FORMAT.md`、`docs/MAINTENANCE.md`、`index.html`、`js/core/navigation.js`、`js/features/agent-proposals.js`、`js/features/agent-settings.js`、`js/features/trash.js`、`test_agent_attachments.py`、`test_agent_capabilities.py`、`test_agent_delete_http.py`、`test_agent_delete_recovery.py`、`test_agent_delete_workflows.js`、`test_agent_deletions.py`、`test_deletion_inventory.py`、`test_deletions.py`、`test_frontend_entry.js`、`workbench/agent_concept_authorization.py`、`workbench/agent_concept_maps.py`、`workbench/agent_delete_authorization.py`、`workbench/agent_delete_execution.py`、`workbench/agent_delete_service.py`、`workbench/agent_execution.py`、`workbench/agent_http.py`、`workbench/agent_management.py`、`workbench/agent_management_http.py`、`workbench/agent_proposal_management.py`、`workbench/agent_proposals.py`、`workbench/agent_security.py`、`workbench/agent_service.py`、`workbench/agent_tools.py`、`workbench/asset_references.py`、`workbench/concept_maps.py`、`workbench/deletion_inventory.py`、`workbench/deletion_prepared.py`、`workbench/documents.py`、`workbench/http_api.py`、`workbench/records.py`、`workbench/references.py`、`workbench/repository.py`。


### 2026-11-10 / AG-137 / 开始

- 用户在监督对话明确“继续持续的推进方案”，解除136后暂停；监督派发仅137，唯一仓库写入者。起点986d6fe，git status --short干净。历史暂停记录保留；138以后尚未开始。
- 范围：仅项目create，五字段、既有模板、完整固定身份/目录/排序影响、强制独立本机批准；创建与可选客户端访问授权分开确认、执行和查询。无其他项目/工作流配置写入。拟接点为projects/repository/configuration、唯一ProposalStore及静态处理器、Agent授权/管理/HTTP/MCP、现有提案和设置UI、专项测试与文档。
- 盘点：普通create当前仅看可列出的README项目，可能复用残留目录或回收身份；普通custom创建在写README后重算排序。项目访问已有project_ids可影响多种既有操作，不可把追加项目ID称为纯只读。项目排序配置宽容读回退不适合用作严格事务证据。137不改变记录/文档编辑器草稿或历史格式，依赖和碰撞必须按磁盘核验。
- 验证计划：临时数据/凭据；五字段/模板/格式及授权边界、普通网页与提案同名和大小写/残留/回收/在途竞争、排序模式与版本、阶段真实退出/恢复/未知零写/回执重放、项目成功而授权失败、丢响应/重启与无隐式扩权；浏览器完整预览与批准/撤销、兼容全量Python/Node/隔离Codex。风险：目录发布与排序不是事务，残留/第三方文件需保留；已创建后独立授权可能失败；旧读取/管理版本不得激活新许可。持久格式、目录发布及恢复设计先交监督定稿。

AG-137阶段验证：监督已定稿，领域与真实 NTFS 目录句柄原语/普通46/领域4项通过；管理兼容29项通过。13个项目真实退出全部过，七个创建授权真实退出阶段保留旧范围与格式下界。旧版986d6fe实际拒新私人快照/项目提案零JSON变化；保留格式围栏前旧普通业务可合法写的限定。独立项目访问持久意图发生外部README变化后，首次测试误期望原字节恢复即可自动继续；既有CredentialManager把已经确认为冲突的操作保持recovery_required直至人工处理。修正为验证不扩权、放弃保留原项目/回执，另增无冲突prepared恢复成功，2项2.536秒通过；未放宽冲突行为。新增凭据家族测试首次因测试方法插入位置错误把旧版测试尾部归到撤销之后，归位后2项2.779秒通过，无产品更改。

项目发布后排序异物保留并分开报告、HTTP/stdio 2项2.952秒通过；浏览器首轮和增加刷新/独立授权取消后完整通过，真实200后丢响应查询独立回执。初次截图中长说明在预览块内部横向滚动，复用已有折行规则并更新缓存；冻结后最终Node将重新验证。APP_VERSION2026.11.10.4，app/navigation/agent-settings/agent-proposals/management.css资源20261110-4。137仍进行中，138未开始。

AG-137首次冻结全量Python：485项628.476秒，唯一失败为test_agent_api旧断言（休眠projects.create已识别但不可用，实际403而旧预期400）；1项Windows原生symlink权限skip。仅修改该测试：合法name输入、精确403/forbidden、effective false/kind_operations无project、磁盘无正式目录，原其余断言不减。整个test_agent_api 13项12.224秒复验OK，174重新冻结仅此测试SHA变化，产品及其余测试SHA一致；监督认可保留首轮其余通过证据，不重跑无关全量，不称485一次全绿。25Node和隔离Codex待顺序跑，仍进行中。

AG-137冻结Node首轮：附件16.032秒/图13.740秒/删除12.661秒过；新项目9.467秒失败在Page.reload后第一次review点击，旧页面可在上下文销毁前满足原ready/selector条件，随后的点击查询null，catch上下文已不可用。只加强测试：刷新前给旧window加标记，等待不含标记的新上下文仍满足原ready/接入提案页/原回执行；未改产品或超时。174重新冻结仅该JS测试变，Python证据不变；完整25Node重新顺序跑。


### 2026-11-10 / AG-137 / 完成

- 交付单条 project/create：固定 slug ID、完整五字段/模板/README/目录，原 custom 可见相对顺序保留、新项目置末，非 custom 零排序写。Agent 完整项目预览和不泄露他项的排序摘要，本机独立网页批准展示完整排序前后。新鲜创建许可不授予读取；原通配保持。可选精确项目范围从原创建回执另行预览/批准，单独 CAS、查询和回执；不重跑项目。
- 兼容/执行：registry6/auth7/管理日志7，transport2、既有授权家族/语义和 22 个工具保留；旧休眠不激活。唯一 ProposalStore project_create@1/execution5，批准受理固定实际时间和前后快照；同一 NTFS 目录句柄发布完整私有暂存，无覆盖/复制回退。普通创建仍用既有领域/排序但独占目录，既有正式数据格式无迁移。复用现有项目、排序与管理仓储；不改变记录/知识库草稿、历史或编辑器保存。
- 最终 Python 证据：首轮 python -m unittest -v 485 项 628.476 秒，唯一失败为旧 HTTP 400 断言，另 1 项原生 symlink 权限 skip；其余通过。仅加强该测试为合法候选 + 精确403/forbidden、能力未生效、操作列表无项目和零正式目录；test_agent_api 13 项 12.224 秒通过。监督认可首轮其余证据，产品/其余 Python 测试 SHA 未变；不称最终485一次全绿。
- 最终 Node 25 个文件顺序均 exit0；项目11.000秒、旧提案16.927秒、设置38.390秒、旧 Agent21.267秒、附件16.969秒、图14.250秒、删除12.905秒、主图49.549秒、知识库附件10.426秒、双编辑器68.266秒、项目筛选9.122秒、时间戳11.692秒，其他契约通过。首轮新增项目 reload 旧上下文竞态仅增强测试观察新上下文，保留原检查和超时，产品不变；首轮失败记录保留。最终174源码/测试/HTML/CSS SHA一致，110 Python/51 JS 全语法、10 修改 Markdown UTF-8/围栏/88 相对链接及 diff 检查通过。版本2026.11.10.4，app/navigation/agent-settings/agent-proposals/management.css缓存20261110-4。
- 实际隔离 Codex：python codex_agent_acceptance.py exit0；codex-cli 0.167.0-alpha.3.2、协议2025-11-25、22工具，旧四类型与两确认/追加更新/重试取消重启撤销通过。0模型turn、不改用户配置；新项目实际HTTP/stdio由专项证明，不等于AG-142真实模型矩阵。
- 手工/专项：真实目录移动/竞争/13个项目与7个许可中断、真实旧986d6fe拒新格式零JSON变化、同字节异物、发布后外部排序保护、版本/撤销/无隐式访问、项目与授权独立恢复和查询。真实浏览器含新鲜授权预览取消、创建取消零正式目录、勾选仅引导、第二批准取消、实际刷新后从原回执重开、真200后模拟丢响应、独立回执和结果导航。三种预览浅深1440/390共12图目视，长文本折行、focus/disabled状态和操作可见；无页面横向溢出。截图/日志仅留Temp。
- 风险：目录/排序/回执不是多文件事务；不明阶段和第三方版本保留，abandon接受盘态非回滚。授权已确定冲突后需人工核查，不在字节复原时自动续发；匹配的 prepared 意图可恢复。Windows同卷固定NTFS、目录身份限制，非Windows只做适用旧回归；外部文件系统竞争和完整复制后的物理身份变化不承诺消除。完整私人证据和原回执长期保留身份；可移植ZIP不是提案/凭据备份。无真实业务数据、私人配置或新增清理残留。
- 决策AG-LOCAL-DEC-050。AG-138～143未开始，本轮仅提交137并交监督审查，下一项按依赖交接。

AG-137实际修改文件（48）：`AGENTS.md`、`README.md`、`app.js`、`css/management.css`、`docs/AGENT_INTEGRATION.md`、`docs/AGENT_USAGE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md`、`docs/AI_AGENT_PROGRESS.md`、`docs/ARCHITECTURE.md`、`docs/DATA_FORMAT.md`、`docs/MAINTENANCE.md`、`index.html`、`js/core/navigation.js`、`js/features/agent-proposals.js`、`js/features/agent-settings.js`、`test_agent_api.py`、`test_agent_attachments.py`、`test_agent_capabilities.py`、`test_agent_project_creation.py`、`test_agent_project_creation_workflows.js`、`test_agent_project_http.py`、`test_frontend_entry.js`、`test_project_prepared.py`、`workbench/agent_concept_authorization.py`、`workbench/agent_delete_authorization.py`、`workbench/agent_execution.py`、`workbench/agent_file_handles.py`、`workbench/agent_http.py`、`workbench/agent_management.py`、`workbench/agent_management_http.py`、`workbench/agent_project_access.py`、`workbench/agent_project_authorization.py`、`workbench/agent_project_execution.py`、`workbench/agent_project_service.py`、`workbench/agent_proposal_management.py`、`workbench/agent_proposals.py`、`workbench/agent_security.py`、`workbench/agent_service.py`、`workbench/agent_tools.py`、`workbench/configuration.py`、`workbench/http_api.py`、`workbench/project_directory.py`、`workbench/project_identity.py`、`workbench/project_prepared.py`、`workbench/projects.py`、`workbench/references.py`、`workbench/repository.py`。


### 2026-11-10 / AG-138 / 开始

- 起点 6f9722c，git status --short 干净；监督验收 AG-137 并派发仅 AG-138。沿用用户持续推进授权，仍为唯一仓库写入者，139～143 不开始。
- 精确范围：项目目录级联移入回收站；新鲜明确 projects.delete、完整子资源读/删权及独立本机批准；完整 README、子记录、附件/目录、外部引用和关联图影响；固定身份、目录树、索引/排序、原回执、在途保护与普通恢复。无项目永久删除工具、无配置事务。
- 当前事实：普通删除只移动 projects/<id>，不清除排序、历史或旧授权，也不修改 concept-maps/ 内项目关联图。图权限按原 project_id 匹配；改空归属会触发独立分类范围，不可隐式做。现有项目独立附件只提供网页操作和受策略约束的 Agent 写入元数据路径，不能把其当作普遍读取或删除许可。历史 idea 无 Agent 全文读/删授权。现有记录编号占用读取回收索引 ID，但项目索引只有项目 ID，需额外保护级联子 ID。现有普通项目回收恢复遇目标冲突会改目录名；新固定证据项须拒绝冲突以防换身份/覆盖。
- 拟接点：projects/repository 与原生目录原语、项目树/外部引用盘点、CredentialManager 和新鲜级联管理、唯一 ProposalStore 静态执行、MCP/HTTP、既有设置/提案/回收 UI、测试及契约文档。先提交权限、格式、发布、恢复和图处理设计定稿，不提前实现协议。
- 验证计划：临时数据/凭据、完整权限和隐藏来源/附件/异常目录/扫描上限、外部版本变化、真实阶段退出及关闭 Agent 恢复、普通回收冲突/批量/永久清理/ID占用/迁移、旧授权拒绝、实际 HTTP/MCP/浏览器、冻结全量门禁。风险：目录对象一致不等于递归命名空间不变；索引和回执不是事务；共享项目内附件、旧精确授权、可移植备份和外部写入需明确限制。
- 监督定稿 AG-LOCAL-DEC-051，见本机能力方案 §25。目标格式 registry7/auth8/管理日志8、`project_trash@1`/execution6 和级联回收 schema2，仍待实施与验收。原生探针验证目录句柄持有期间外部仍可向子目录新增文件，执行设计采用移动前后全树核对与未知状态保护。

### 2026-11-10 / AG-138 / 完成

- AG-LOCAL-DEC-051 实施。独立项目和逐附件授权，既有子记录读删权，与本机每案完整独立批准共同约束操作。项目外关联图和外部正文、共享字节、排序与历史原样保留。外部活动来源引用将移动的附件或未授权影响时拒绝。固定项目和子记录身份可恢复并永久保留占用。
- 兼容与执行：registry7/auth8/管理日志8、transport2、proposal3/manifest3、`project_trash@1`/execution6、回收 schema2。旧能力、旧回收格式、22 工具和本地数据格式继续读取。项目列表仅为原有范围附可核验 README `revision`。工作台版本 2026.11.10.5，app、navigation、agent-settings、agent-proposals 资源版本 20261110-5。
- 最终 `python -m unittest -v` 493 项，655.573 秒，492 通过、1 个 Windows 原生 symlink 权限跳过。首轮 492 项有一项旧能力目录断言失败，同步断言并验证休眠许可仍无有效操作。最终 Node 24 项同批通过，通用编辑器重载等待超时后同一冻结版独立复验 69.698 秒通过，25 个测试文件均有通过结果。首轮时间戳独立复验 9.673 秒通过。181 源码、测试、HTML、CSS 摘要一致，117 Python 和 51 JS 语法、10 Markdown UTF-8/围栏/95 相对链接及 `git diff --check` 通过。
- 10 项最终专项覆盖 NTFS 原树、恢复和可移植副本、原始 HTTP/stdio、固定回执。实际退出 5 个目录提交阶段，旧 `6f9722c` 管理器在 4 个持久化阶段拒绝且零 JSON 改写。真实浏览器级联用例最终批次 20.449 秒通过。浅深 1440/390 授权和目录预览截图已目视。隔离 `python codex_agent_acceptance.py` 通过，0.167.0-alpha.3.2 / 2025-11-25 / 22 工具，0 模型 turn，用户配置未改。详细记录见[本机能力验收](AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)。
- 剩余边界：NTFS 目录句柄无法冻结外部子目录写入，最终校验之后的竞争可能移动到不匹配状态，保留现场且不补成功回执。未决迁移仍需原物理身份，停机完整副本的已提交树可用便携摘要核验。下一项 AG-139 按依赖另行交接。

AG-138 实际修改文件（49）：`AGENTS.md`、`README.md`、`app.js`、`docs/AGENT_INTEGRATION.md`、`docs/AGENT_USAGE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md`、`docs/AI_AGENT_PROGRESS.md`、`docs/ARCHITECTURE.md`、`docs/DATA_FORMAT.md`、`docs/MAINTENANCE.md`、`index.html`、`js/core/navigation.js`、`js/features/agent-proposals.js`、`js/features/agent-settings.js`、`test_agent_attachments.py`、`test_agent_capabilities.py`、`test_agent_delete_http.py`、`test_agent_delete_workflows.js`、`test_agent_project_delete.py`、`test_project_delete_tree.py`、`workbench/agent_concept_authorization.py`、`workbench/agent_delete_authorization.py`、`workbench/agent_delete_execution.py`、`workbench/agent_delete_service.py`、`workbench/agent_execution.py`、`workbench/agent_http.py`、`workbench/agent_management.py`、`workbench/agent_management_http.py`、`workbench/agent_project_access.py`、`workbench/agent_project_authorization.py`、`workbench/agent_project_delete_authorization.py`、`workbench/agent_project_delete_execution.py`、`workbench/agent_project_delete_service.py`、`workbench/agent_project_execution.py`、`workbench/agent_proposal_management.py`、`workbench/agent_proposals.py`、`workbench/agent_security.py`、`workbench/agent_service.py`、`workbench/agent_tools.py`、`workbench/asset_references.py`、`workbench/deletion_inventory.py`、`workbench/deletion_prepared.py`、`workbench/http_api.py`、`workbench/project_delete_impact.py`、`workbench/project_delete_tree.py`、`workbench/project_identity.py`、`workbench/references.py`、`workbench/repository.py`。

### 2026-11-10 / AG-139 / 开始

- 起点 `9ed9006`，`git status --short` 干净。监督验收 AG-138 并派发仅 AG-139。先盘点与评审协议，AG-140～143 待依赖交接。
- 范围：知识库、概念图和项目独立附件的 create/rename/delete/reorder。保留空分类与排序语义。删除只迁默认分类。源内容及附件字节保留。复用同一领域准备、网页和 Agent 写入协调、唯一 ProposalStore 与现有授权日志。
- 首轮盘点：知识库保留分类列表和独立 `document-sort.json`，普通 create 当前为两次 PUT，现有改名钩子只尝试恢复普通文档读取名。图分类普通改名/删除会迁移同名的项目关联图，现有钩子移除命名图读写和单删范围。项目附件 `PUT` 以全量列表保存，并会清除记录附件的同名分类。这是新独立附件分类事务必须隔离的兼容点。项目独立附件级联授权虽以 ID 选择，证据摘要实际含分类元数据，改名可能使该证据失效。上传/正式附件策略按 owner ID 与 client_version 绑定，提交候选另有分类版本依赖。
- 拟接点：`configuration.py`、`documents.py`、`concept_maps.py`、`assets.py`、仓储和网页路由、已有管理日志、唯一提案引擎、设置和完整预览、集成测试和契约文档。验证计划覆盖三类四操作、空分类和排序重读、精确/通配/未来成员及名称复用、权限差异和默认分类、多文件真实中断与恢复、实际 HTTP/stdio/浏览器及全量门禁。
- 风险：当前普通全量列表和隐式 `ensure` 可增删分类，须共同约束授权生效点。现有精确授权按名称匹配，改名/复用有悬空权限风险。私有客户端授权和日志不得进入 Agent 可见预览。记录附件旧路径、项目图的既有归属、附件策略版本及多文件中断需先定稿。
- 监督接受 AG-LOCAL-DEC-052，范围及格式见本机能力方案 §26。确认新独立附件命令与旧混合 PUT 分开，项目默认空字符串与旧字面「未分类」分别保留。确认默认授权导致可见/可写成员扩张时保守拒绝，以及已初始化/未初始化普通路径的不同日志边界。开始纯领域计划与身份核验，协议及验收尚待实施。
- 首个纯领域专项 `python -m unittest -v test_category_changes` 3 项通过。覆盖三类四操作的目录计划、项目空默认与历史字面值、改名保留身份、名称复用换代、只读不写和单边身份文件缺失拒绝。现有网页与 Agent 路径尚未接入此计划。

### 2026-11-10 / AG-139 / 完成

- 决策 AG-LOCAL-DEC-052。三类目录支持 create/rename/delete/reorder，保留原 ID、正文、历史、图项目归属及附件字节。删除迁入对应默认分类，独立附件命令保留记录附件分类，旧混合全量 PUT 保留原语义。正常网页和 Agent 分类命令共用领域准备与原字节核验。新管理接口仅本机同源，现有 22 个 MCP 工具复用提案契约。
- 格式与兼容。registry8、authorization9、管理日志9、transport2、proposal3/manifest3、`category_mutation@1`/execution7。分类身份配对文件保留名称代次与墓碑，旧业务配置继续是事实源。先收窄精确授权，业务与历史完整且客户端版本匹配后才补发等价权限。服务版本 2026.11.10.6，更新相关静态资源缓存版本。
- Python 全量 `python -m unittest -v` 506 项，700.716 秒，505 通过，1 项 Windows 原生符号链接权限跳过，同域原生 junction 另有测试。全量启动后补了同一 UUID 但过期代次不得等价补发的限制，该限制的直接反例与最终 13 项分类专项均通过。初轮旧断言与故障注入点按新契约更新，另一次修改中启动的试跑因混合模块导入失效，均不作为最终通过证据。
- 最终 26 项 Node 用例均有通过结果，其中 24 项同批通过。设置重载等待及概念图加载分别超时、遇页面脚本尚未定义，两个用例和产品保持原样后逐项复验通过。分类浏览器通过浅深色、1440/390，含精确授权、完整预览、取消、三类普通入口、中文项目路径、带符号分类名及批准响应丢失后的重放。127 Python、52 JS 语法检查、10 Markdown UTF-8/围栏和 97 个相对链接均通过。
- 实际进程在六处退出后核对原操作、历史、权限与回执。实际旧版在四个授权日志阶段拒绝且零 JSON 改写。独立附件授权和关联图专项验证了两次并发批准返回同一回执。隔离真实 Codex CLI 0.167.0-alpha.3.2、协议 2025-11-25、22 工具验证分类提案、本机批准和重启，0 模型 turn，用户配置未改。详见[本机能力验收](AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)。
- 剩余边界。旧全量兼容入口或未初始化空间的多文件中断可能需要人工核查。Agent 独立附件分类沿用现有附件索引读取平台和策略门槛。外部未观察到的往返修改、旧程序绕过或双侧身份记录被移除时，无法识别所有代次变化。AG-140 按依赖另行交接。

AG-139 实际修改文件（54）：`AGENTS.md`、`app.js`、`codex_agent_acceptance.py`、`concept-map.js`、`css/components.css`、`docs/AGENT_INTEGRATION.md`、`docs/AGENT_USAGE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md`、`docs/AI_AGENT_PROGRESS.md`、`docs/ARCHITECTURE.md`、`docs/DATA_FORMAT.md`、`docs/MAINTENANCE.md`、`index.html`、`js/features/agent-proposals.js`、`js/features/agent-settings.js`、`README.md`、`test_agent_attachments.py`、`test_agent_capabilities.py`、`test_agent_category_changes.py`、`test_agent_category_workflows.js`、`test_agent_concept_maps.py`、`test_agent_deletions.py`、`test_agent_files.py`、`test_agent_management.py`、`test_category_changes.py`、`workbench/agent_category_authorization.py`、`workbench/agent_category_execution.py`、`workbench/agent_category_management.py`、`workbench/agent_category_service.py`、`workbench/agent_concept_authorization.py`、`workbench/agent_delete_authorization.py`、`workbench/agent_execution.py`、`workbench/agent_management_http.py`、`workbench/agent_management.py`、`workbench/agent_project_access.py`、`workbench/agent_project_authorization.py`、`workbench/agent_project_delete_authorization.py`、`workbench/agent_project_execution.py`、`workbench/agent_proposal_management.py`、`workbench/agent_proposals.py`、`workbench/agent_security.py`、`workbench/agent_service.py`、`workbench/agent_tools.py`、`workbench/assets.py`、`workbench/category_changes.py`、`workbench/category_identity.py`、`workbench/category_local.py`、`workbench/category_prepared.py`、`workbench/concept_maps.py`、`workbench/configuration.py`、`workbench/http_api.py`、`workbench/project_identity.py`、`workbench/repository.py`。

### 2026-11-10 / AG-140 / 开始

- 起点 76b250c，git status --short 干净。监督接受 AG-139，派发仅 AG-140。先按 §10.2 核对旧数据和操作入口，再评审持久协议。
- 范围：模板新建、复制、重命名，状态新增、重命名、重排、删除，项目切换模板。模板、全局状态、项目绑定、记录、顺序和历史的影响统一准备。使用中状态需显式映射；待办完成从目标工作流推导；info 保持无状态，旧 idea 仅作兼容迁移。
- 拟接点：configuration/projects/records 和 Repository 协调、现有工作流 HTTP 与网页、Agent 凭据管理、唯一 ProposalStore、Agent 提案/设置页面、契约和测试。计划用临时库验证多模板、实际成员与未授权影响、排序和看板、并发及真实进程退出、历史与旧入口、浏览器和隔离 stdio。
- 首轮核对：旧全量工作流 PUT 先落配置再重命名记录，只处理分类型的 README 状态键；没有更新混合看板，也不重新计算已迁移待办的完成值。旧项目 PATCH 可以直接切换模板。旧状态模板 PUT 独立写 fallback 文件。前端与 Agent 对悬空绑定的 fallback 不一致。记录状态保存为名称，项目和全局 ideas 仍被仓储读取。历史恢复从快照直接带回旧状态，需明确迁移后的兼容办法。
- 隔离基线：仓储工作流新增/切换、使用中拒删/改名、Agent 待办工作流冲突三个现有用例通过。另用临时库实证：旧模板保存可将非终态改名为终态，记录完成值仍为 false，两个 mixed 状态键仍为旧名，原历史可读。已将拟定 DEC-053（本机能力方案 §27）发送监督评审，持久格式与代码尚未改动。
- 监督接受 DEC-053，并定稿系统模板历史显示名、模板与类型级状态授权、切换许可一次消费、旧 HTTP 实质变更须使用同一批准票据、原历史恢复选择和终态契约。开始共用领域计划。

### 2026-11-10 / AG-140 / 完成

- 决策 AG-LOCAL-DEC-053。八项受控工作流操作，使用中状态必须显式映射，项目切换保留同类同名自然对应，待办完成由目标定义推导。迁移保留记录 ID、原正文、附件、手动 ID 排序和原历史。分类型及 mixed 状态顺序、排序冲突和终态差异均进入完整预览。历史恢复过期状态须本机明确选择。
- registry9、授权10、日志10、transport2、proposal3/manifest3、`workflow_mutation@1`/execution8。仅新鲜精确工作流授权和本机独立批准生效。新建、复制和项目切换许可一次消费。配对身份记录保留模板代次和退役 ID。Agent 只看到既有范围内实际影响；本机可核对完整 README、配置和脱敏授权。服务 2026.11.10.7，三个更新后的 JS 缓存版本 20261110-7。
- 旧网页目录 PUT 在实际 76b250c 服务上发送合法数组得到 400。此次只在该精确路由恢复有界数组解码。冻结浏览器用例验证无实质影响写入兼容返回，非法元素、形状、超限、其它对象路由的数组、缺映射及实质影响旧请求拒绝。普通实质变更共享当前预览批准和业务日志。
- 冻结 `python -X utf8 -m unittest -v` 共 522 项，740.542 秒，521 通过、1 项 Windows 原生符号链接权限跳过。首轮 522 项也通过，最后的小幅 README 保真与浏览器配置刷新修正后重新全量。新增 16 项工作流专项进入冻结全量。203 个源码、测试和网页资源指纹一致，137 Python 与 53 JS 语法、10 Markdown UTF-8/围栏和 100 相对链接通过。
- 最终 27 个 Node 文件均有通过证据。24 项同批通过，旧设置页面重载、通用 Agent 页面脚本连接、文档附件临时目录清理三项原样逐项复验通过。工作流实测含权限、旧接口、缺映射、修订、取消、历史、普通项目切换和映射删除，浅深 1440/390 的授权、提案和普通预览已检查。
- 真实进程在工作流 manifest、授权收窄、历史、业务发布、最终核验和回执中断点获得同一回执；第三方原文件变化保留现场。实际旧版在四个授权日志和两个业务执行阶段拒绝，采样 JSON 字节保持一致。隔离 Codex CLI 0.167.0-alpha.3.2 / MCP 2025-11-25 / 22 工具通过工作流、本机批准与重启读取，0 模型 turn，用户配置未改。详见[本机能力验收](AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)。
- 剩余边界。未初始化空间使用同域 CAS 和历史而无 Agent 持久日志，多文件中断需人工核对。历史和回收原字节继续保留，模板外状态可读，悬空工作流绑定需本机明确修复。对外部无法观察的往返写入、缺失或损坏的配置不承诺自动修复。AG-141 按依赖交接。

AG-140 实际修改文件（52）：`AGENTS.md`、`app.js`、`codex_agent_acceptance.py`、`docs/AGENT_INTEGRATION.md`、`docs/AGENT_USAGE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md`、`docs/AI_AGENT_PROGRESS.md`、`docs/ARCHITECTURE.md`、`docs/DATA_FORMAT.md`、`docs/MAINTENANCE.md`、`index.html`、`js/features/agent-proposals.js`、`js/features/agent-settings.js`、`README.md`、`test_agent_attachments.py`、`test_agent_capabilities.py`、`test_agent_files.py`、`test_agent_workflow_changes.py`、`test_agent_workflow_workflows.js`、`test_workflow_changes.py`、`workbench/agent_category_authorization.py`、`workbench/agent_category_management.py`、`workbench/agent_concept_authorization.py`、`workbench/agent_delete_authorization.py`、`workbench/agent_execution.py`、`workbench/agent_management_http.py`、`workbench/agent_management.py`、`workbench/agent_project_access.py`、`workbench/agent_project_authorization.py`、`workbench/agent_project_delete_authorization.py`、`workbench/agent_project_execution.py`、`workbench/agent_proposal_management.py`、`workbench/agent_proposals.py`、`workbench/agent_security.py`、`workbench/agent_service.py`、`workbench/agent_tools.py`、`workbench/agent_workflow_authorization.py`、`workbench/agent_workflow_execution.py`、`workbench/agent_workflow_management.py`、`workbench/agent_workflow_service.py`、`workbench/category_local.py`、`workbench/configuration.py`、`workbench/http_api.py`、`workbench/project_identity.py`、`workbench/projects.py`、`workbench/records.py`、`workbench/repository.py`、`workbench/workflow_changes.py`、`workbench/workflow_identity.py`、`workbench/workflow_local.py`、`workbench/workflow_prepared.py`。

### AG-141 提案管理、恢复入口与诊断整体验收（2026-11-10 开始）

- 范围。盘点 AG-132～140 的提案管理、审批、原回执、恢复入口和本机诊断，按实际证据补齐缺口。预计涉及提案管理服务、管理路由、提案管理界面及其回归测试，必要时同步诊断测试和维护文档。复用现有提案、执行与恢复逻辑。
- 验收矩阵。项目、记录、知识库三类附件，概念图，单条删除和项目级联删除，项目创建与独立授权，三个分类域及工作流均检查完整预览和授权边界。跨类型检查状态、失效票据、迟到响应、取消和失败后禁用，区分原回执查询、恢复和接受当前盘态。管理入口检查同源与禁用，诊断检查超时、输出、子进程回收及隐私。浏览器检查浅深色、桌面窄屏、长中文、空列表、大量数据及焦点、错误与禁用反馈。
- 验证计划。隔离数据的专项 Python、真实浏览器工作流、全量 Python 和 Node 回归、语法检查及 `git diff --check`。恢复操作涉及中断后的不确定盘态，沿用既有证据要求；真实客户端矩阵留待 AG-142。
- 范围决定。监督接受只读脱敏的网页报告，停服 CLI 仍负责恢复和接受盘态。网页新增 GET `/api/local/agent-management/proposal-recovery`，无需启用 Agent。报告与原批准查询是两条独立调用链，沿用持久证据，不新增写权限或日志格式。
- 独立清理待办。AG-140 的合成临时目录 `workbench-document-browser-mKOTbr` 仍存在。该目录的递归删除已被自动审批以 `blocked by policy` 拒绝，未再尝试或换工具。AG-141 开始时只读进程查询无命令行匹配，未检查所有系统句柄。该待办由监督确认与 AG-141 验收独立。

### AG-141 完成（2026-11-10）

- 决定记录。按本项开始记录中的监督审定范围交付网页只读报告。报告复用持久执行预检，返回工作空间、原事务和提案 ID 及状态。已初始化空间停用后可查，空空间零初始化，未知或损坏仅提示核查。报告不触发恢复、过期、清理、回执或业务写入。原批准查询显示三种处理器的已放弃状态，无原完成回执，重复原批准不重新发布。停服 CLI 继续负责恢复核查和显式接受盘态。
- 兼容。复用原持久格式、授权和 Agent 工具。管理预览返回本次票据绑定的摘要，浏览器校验当前身份、版本、摘要和时限。附件缺执行计划禁用批准，分类和工作流详情可查看原回执。诊断结束立即清除 nonce。服务版本 2026.11.10.8，提案脚本缓存版本 20261110-8。
- Python。首轮 `python -m unittest -v` 525 项，699.041 秒，524 通过，1 项 Windows 原生符号链接权限跳过。该轮启动后补强报告版本身份校验与诊断私有路径断言。最终相关 16 项专项通过。最终 Python 全量 525 项，659.554 秒，523 通过，1 跳过，1 项既有附件并发耗时断言失败。`first='agent'` 先通过功能断言后测得 4.3603718 秒，门槛 2 秒。该测试未调用本轮新增报告、原批准查询、浏览器或诊断。保持原门槛，两次单独复跑通过，其中全量退出后整项 4.212 秒。保留原失败证据，原因未进一步归因。
- Node。27 个文件均有通过证据。初批 26 个通过，设置页一次刷新竞态后改用实际页面代次等待并通过。第二批删除页面初始化超时，原样单独复跑通过。附件缺执行计划、分类和工作流原回执、提案报告浅深色 1440/390 布局最终通过。窄屏标题遮挡在目视检查中发现并修正，加了顶栏可见性断言。
- 语法及实机。137 个 Python 与 53 个 JS 通过语法检查，6 个 Markdown 文件与 83 个相对链接、`git diff --check` 通过。隔离 Codex CLI 0.167.0-alpha.3.2、MCP 2025-11-25 和 22 工具的既有兼容验证通过，0 个模型 turn，用户配置未改。详情与限制见[本机能力验收](AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)。
- 实际文件（22）。`AGENTS.md`、`README.md`、`docs/AGENT_USAGE.md`、`docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md`、`docs/AI_AGENT_PROGRESS.md`、`docs/MAINTENANCE.md`、`index.html`、`js/features/agent-proposals.js`、`test_agent_attachment_workflows.js`、`test_agent_attachments.py`、`test_agent_category_workflows.js`、`test_agent_concept_maps.py`、`test_agent_diagnostics.py`、`test_agent_proposal_management.py`、`test_agent_proposal_workflows.js`、`test_agent_settings.js`、`test_agent_workflow_workflows.js`、`workbench/agent_diagnostics.py`、`workbench/agent_management_http.py`、`workbench/agent_proposal_management.py`、`workbench/agent_proposals.py`、`workbench/http_api.py`。
- 交接。AG-140 独立临时目录清理待办仍在，收口时只读结果一致。AG-142 待开始，待监督派发。

### AG-142 真实客户端兼容验收（2026-11-10 开始）

- 起点 `00fe468`，工作区干净。监督接受 AG-141，派发仅 AG-142。先盘点版本与可运行入口，以合成临时库、私人配置和固定 loopback 执行零模型回合协议验收。真实客户端、原始 stdio、HTTP、浏览器和真实桌面任务分列证据。
- 范围。工具目录与刷新、完整文件读取及两类附件来源、图新建和更新、删除、项目创建和独立授权、三个分类域和工作流、两种确认和自报拒绝。覆盖重放、取消、版本、空间、授权、限流、响应丢失和重启。优先复用现有 Codex、WorkBuddy 验收脚本与领域专项，按实际证据补齐。预计涉及兼容矩阵、验收台账、隔离脚本及必要验收测试。
- 人工任务、费用、登录和真实客户端配置变更需审查具体安排。先准备每次操作和批准点、调用预算、退出和清理措施。历史 AG-121/126 的授权和通过结论仅作参考。AG-140 递归清理被拒的临时目录继续单列，已只读核实存在。

### AG-142 零模型回归及只读试点准备（2026-11-10）

- 实际 Codex App Server `0.167.0-alpha.3.2`，MCP `2025-11-25`，22 项 Schema。独立子进程配置、用户目录和合成库完成文件六段完整读取、两个附件通道、图 create/update、单条和项目删除、项目创建后另行批准访问、三个分类域和工作流。实际丢弃图更新 HTTP 成功响应后原提案查询和同回执重放通过。另核证旧版、取消、错空间、429、重启、轮换、撤销及重载目录。流式 bytes 由独立 loopback HTTP 助手发送。程序确认仅是协议证据。
- WorkBuddy 安装 `5.9.3.0`，原装 CLI `2.165.0` 的默认和显式探针各实际发现完整 22 项名称，MCP `2025-11-25`，ping 和 `-32601` 符合预期。旧 20 项固定断言失败及修复保留。原装 CLI `mcp --help` 无直接工具调用选项。真实桌面业务仍待验收。
- 原始 stdio、HTTP、领域持久化与管理回归 207 项，288.623 秒，206 通过、1 项 Windows 符号链接权限跳过。两份只读试点分别预演完整读回、写入拒绝、撤销后 401、ready/STOP、端口关闭和目录删除。无活动试点服务，无真实配置改动、桌面启动或模型回合。实际步骤、完整候选和预算见[兼容矩阵](AGENT_CLIENT_COMPATIBILITY.md)。
- 阶段门禁 `python -m unittest -v` 共 525 项，931.041 秒，524 通过，1 项同样因 Windows 原生符号链接权限跳过。新脚本最终版本分别执行 Codex 直调、WorkBuddy 默认/故障和两份试点预演通过。Python/JS 语法、两份 Markdown UTF-8/围栏及 12 个相对链接、`git diff --check` 通过。范围仅验收脚本和文档，实际文件为 `codex_agent_acceptance.py`、`workbuddy_agent_acceptance.py`、`docs/AGENT_CLIENT_COMPATIBILITY.md` 与 `docs/AI_AGENT_PROGRESS.md`。继续使用既有业务、协议、数据格式和应用版本。
- 等待本次桌面安排。监督接收每客户端最多一轮只读试点的审查稿，两个试点合计最多两轮，后续写入、额外额度和用户级配置另行决定。AG-142 保持进行中，AG-143 未开始。

### AG-142 桌面只读试点观察（2026-11-10）

- 用户批准两客户端只读试点，另授权监督自行验证 WorkBuddy 并指定 Hy4。实际桌面显示 WorkBuddy V5.9.3，新建任务选择本次临时 `desktop-project`，模型选择器显示 Hy4。项目级配置由夹具生成。至少 60 秒内未见 `protocol.jsonl`，无 initialize 或 tools/list 证据。按约定在发送前停止，0 个模型回合，未切用户级配置或使用其他模型。结论仅为本次项目级发现未证实，原装 CLI 结果继续单列。
- WorkBuddy 夹具按 STOP 退出 0，记录端口关闭、撤销凭据拒绝和临时目录已移除。随后只读 `Test-Path` 复核该试点目录不存在。Codex 的独立夹具已交用户手工执行，截至本条记录尚无中继轨迹，待用户结果。AG-142 保持进行中，AG-143 待开始。详见[兼容矩阵](AGENT_CLIENT_COMPATIBILITY.md)。

### AG-142 项目级发现对照与备选配置（2026-11-10）

- 用户报告 Codex 桌面未发现 `workbench_ag142`。监督核查无中继轨迹，原夹具通过唯一 STOP 退出 0，端口关闭、旧令牌拒绝、临时目录不存在。0 个模型回合，无真实用户级配置写入。实际 App Server 业务验证保持独立。
- WorkBuddy 5.9.3 安装包静态核查区分已登记管理列表、详情激活和会话项目资源注入。原装 CLI 2.165.0 用 CLI 自身项目 `.mcp.json` 执行 `mcp get workbench_ag142`，真实项目作用域握手及 22 项工具通过。仅放桌面 `.workbuddy/mcp.json` 的 CLI 列表未发现，CLI 项目默认列表未握手。当前无桌面项目级发现通过证据。
- Codex App Server 对照。临时 `CODEX_HOME` 中只有信任实际线程目录才读取该项目的 `.codex/config.toml`，同一无 `.git` 夹具其余三种信任条件无目标工具。可信条件发现 22 项。实际客户端提出 MCP `2025-06-18`，服务返回 `2025-11-25`。中继摘要已区分提出与返回的版本。旧项目长路径及 8.3 拼写在默认配置中均无确切信任匹配，实际桌面生效信任仍无法确定。试点启动输出改为已解析长路径。
- 已准备两客户端的单条用户级候选，默认文件只读核查无同名，真实生效目标仍须现场确认。实际命令、逐项核对、20 分钟 TTL、撤销和保留其他条目的方案见兼容矩阵。未启动新的待用夹具或模型，未修改真实客户端配置。仅在可以核实确切目录与信任时考虑 Codex 零模型 `/mcp` 检查。用户级例外和模型回合另行决定，AG-142 保持进行中，AG-143 待开始。
- 本次改动限两份文档和验收脚本。WorkBuddy 元数据与原始 stdio 17 项通过，两个只读夹具 `--pilot-check` 通过，真实隔离 Codex 可信项目复验验证双端协议版本与 22 工具并按 STOP 清理。Python/JS 语法、文档 UTF-8/围栏/相对链接、`git diff --check` 通过。实际桌面未重跑。

### AG-142 Codex 桌面长路径复验（2026-11-11）

- 用户截图中的 `/mcp` 列表显示现有 `workbench`，未显示临时 `workbench_ag142`。本次临时中继恰有 5 条记录。`codex-mcp-client 0.167.0-alpha.3.2` 提出 `2025-06-18`，服务返回 `2025-11-25`，随后完成 `notifications/initialized` 和 `tools/list`，收到 22 项工具。桌面协议发现已有证据，界面未列出临时项的原因待查。0 次 `tools/call`，0 个模型回合。
- STOP 已写入，监督实测端口关闭。夹具退出 1，临时项目清理遇到 `WinError 32/5`。只读复核确认 STOP 和临时项目仍存在。待用户关闭本次临时项目后复核清理，AG-142 保持进行中。此次未改用户级配置。详见[兼容矩阵](AGENT_CLIENT_COMPATIBILITY.md)。
- 独立清理待办已关闭。用户关闭临时聊天和项目后，临时目录 `workbench-ag142-pilot-codex-y2bf7efe` 一度仍存在，关联 Codex、Python 和 Node 命令行匹配数为 0。仅针对该目录的 PowerShell `Remove-Item` 请求被自动审批以 `blocked by policy` 拒绝，命令未执行。用户随后手工删除目录，原路径的只读 `Test-Path` 返回 `False`。桌面界面显示和模型验收仍待核查。

### AG-143 运维验收准备（2026-11-11，工作项待开始）

对照[方案 §13.4](AI_AGENT_LOCAL_CAPABILITIES_PLAN.md#134-备份停用与降级)核对已有隔离证据。以下准备供后续执行，AG-142 的桌面缺口仍在。

| 核对范围 | 已有证据 | 后续需要补齐 |
| --- | --- | --- |
| 可移植 ZIP | `python extension_lifecycle_acceptance.py` 本次复跑通过，四类型八条业务条目、两确认方式、ZIP CRC、新身份和空客户端。附件下载及导出、图游标和文档 ZIP 引用改写有独立测试 | 在同一新能力夹具中核对项目、记录及知识库正式附件、图、分类与工作流配置和业务历史的字节、引用与重读。检查 `.agent`、`.trash`、私人授权和上传暂存、机器路径配置排除，以及旧文件授权无法在新身份使用 |
| 停服完整恢复 | 生命周期脚本复制业务与匹配私人根，重读四类型与原批准回执。已完成删除的完整目录复制和相对源恢复另有专项 | 在同一混合副本核对新能力原回执、排序、配置身份和历史。分别测试匹配、缺失与错配私人根。文件授权还需重核源文件身份。对复制后物理身份变化的未决事务保留现场 |
| 停用、降级与未知日志 | 生命周期脚本确认 Agent 关闭时 API 返回 404，普通记录和文档 API 可读。实际停用启动恢复、旧程序拒绝新格式、匹配升级前备份恢复及未知格式零写均有专项 | 同一新能力夹具中测普通网页读写和停用期间在途保护。分别对当前混合日志与匹配旧备份运行对应新旧版本，核对未知执行、批准或凭据日志被拒绝时业务文件和日志哈希一致 |
| 脱敏 | 已覆盖静态路径拒绝、管理错误、诊断及只读恢复报告的脱敏专项 | 将合成令牌和路径标记贯穿同一夹具，检查 API、MCP stdout/stderr、诊断、管理报告及 ZIP。私人目录内预期存储的凭据单独核对 |
| 临时资源 | 两客户端隔离探针已验证撤销、STOP、端口关闭和目录移除。最近桌面夹具的审批拒绝与手工清理已闭合 | 为后续新夹具逐项记旧凭据拒绝、实际退出、端口和目录。AG-140 的独立清理记录继续单列 |

本次另选 8 个已有用例复跑，8.077 秒全部通过。覆盖 `test_agent_runtime` 的可移植恢复与管理脱敏、`test_agent_delete_recovery` 的完成态复制、`test_agent_execution` 的停用恢复与未知格式、`test_agent_capabilities` 的匹配升级前备份、`test_agent_api` 的静态路径边界和 `test_agent_diagnostics` 的诊断脱敏。

开工后按以下顺序执行。所有分支使用新建一次性业务目录和匹配的私人根。

1. 运行 `python extension_lifecycle_acceptance.py` 建立四类型回归基线，再用当前接口构建含三类正式附件、图、分类和工作流、回收及在途操作的合成库，记录业务文件和回执哈希。
2. 导出可移植 ZIP，核对成员和合成秘密标记，解包至独立目录。接入前核对业务可读，接入后检查新身份和旧授权拒绝。
3. 停服复制完整业务和私人根。用不同副本核对匹配、缺失和错配状态。执行停用、未知日志拒绝、旧版拒绝及匹配升级前备份的恢复对照。
4. 核对响应和日志脱敏，撤销并关闭全部本次夹具。最后执行全量 Python、仓库 Node 门禁、语法和文档检查，将证据写入交付台账。

AG-142 的独立检查已验证 App Server 只配置 `workbench_ag142` 时可以按服务器名定向调用，结果匹配临时空间并完成清理。桌面尚无已验证的同等入口。当前可审查的范围决定是保留桌面待验并允许先做 AG-143 运维收口，或先审查可将桌面调用限定到临时连接器的具体步骤。

### AG-142 可信项目隔离对照（2026-11-11）

- 用户选择先完成真实桌面验收。本阶段复验 Codex 项目配置对模拟用户级连接器的覆盖，准备仅写入临时项目的启动选项，并核对 WorkBuddy 单项候选。以隔离 App Server 对照、两夹具预演和实际目录证据验证。真实客户端配置、模型回合和 AG-143 状态仍按原授权范围处理。
- 安装版 App Server 对照通过。可信目录中模拟用户级 `workbench` 有 0 项工具，显式调用返回 `-32603`，`workbench_ag142` 只允许四项并命中独立合成空间。不可信目录仍使用模拟 `workbench`，临时项不可调用。交错核查旧目录和可信目录，各自生效。实际生成的 `--codex-project-guard` 项目也通过 App Server 复验，模拟旧项及额外工具拒绝、六段合成读回的 SHA-256 一致，两个夹具均收尾。桌面仍须在本任务中核实同等作用域，才可发送一次只读提示。
- WorkBuddy 5.9.3 / Hy4 已整理实际目标确认、完整候选、非目标基线、仅新增和仅移除、20 分钟 TTL 与 STOP 验收步骤。项目级预激活仅在实际列表已有该行时可尝试。用户级写入仍待另行审查，真实桌面缺口待验。
- 本次 `test_workbuddy_acceptance` 和 `test_mcp_stdio` 共 17 项通过。两客户端 `--pilot-check`、Python 和 JavaScript 语法、文档检查及 `git diff --check` 通过。变更限验收脚本与两份记录。

### AG-142 可信项目桌面复验与中继工具限制（2026-11-11）

- 当前桌面 `/mcp` 截图显示既有 `workbench` 已禁用，仍未显示 `workbench_ag142`。临时中继有 5 条记录，依次为 `initialize` 提出 `2025-06-18`、服务返回 `2025-11-25`、`notifications/initialized`、`tools/list` 和 22 项原始工具响应。工具调用和模型回合均为 0。夹具收尾由监督在用户关闭项目后执行，结果待核对。
- 用户随后提供「插件 → MCP」截图，临时 `workbench_ag142` 开启，既有 `workbench` 关闭。当前在线夹具仍只有一次初始化和一次原始 22 项工具应答。用户可只读查看目标工具详情，待核实该会话实际启用四项预期工具后才发送已授权的一轮。若详情无法核实，则等待四项中继过滤复验。
- 本阶段在验收中继增加独立四项工具限制，预演工具目录、允许读回、额外工具拒绝和夹具清理。生产 MCP、数据与 API 兼容不涉及本次变更。
- `--readonly-pilot codex --codex-project-guard --pilot-check` 通过。转发目录恰四项，两次额外工具调用被中继拒绝，六段合成文件及 SHA-256 核对通过，撤销后旧凭据返回 401，端口关闭和目录清理通过。WorkBuddy 普通只读预演仍发现 22 项。真实桌面下一次发送前须同时确认当前任务旧项禁用、无其他真实工作台连接器、本次独立只读身份及中继转发四项工具的证据。
- `test_workbuddy_acceptance` 和 `test_mcp_stdio` 共 18 项通过，覆盖目录过滤及缺项和重复拒绝。Python/JavaScript 语法、文档检查及 `git diff --check` 通过。本阶段仅改验收脚本、专项和两份记录。
- 旧限制版夹具收尾。用户已关闭临时聊天和项目，监督写入 STOP 并实测端口关闭。进程退出 1，目录清理报 `WinError 32/5`。只读确认 `workbench-ag142-pilot-codex-db19kz_k` 的 STOP 和项目目录仍在，列为独立清理待办。该轮 0 次工具调用和 0 个模型回合。新四项过滤夹具已启动，等待用户核对确切项目、既有项关闭、临时项开启及中继确切四项目录。

### AG-142 真实桌面首轮读取及到期时序（2026-11-11）

- 真实 Codex 桌面用户发送 1 个只读模型回合，临时聊天 `01a1c88e-4829-7e40-8fe6-a5b917707baa` 的工作目录属于 `workbench-ag142-pilot-codex-stvb2y37`。两次真实握手均提出 `2025-06-18`、协商 `2025-11-25`，转发目录均恰为四项。6 次真实工具调用中 capabilities、授权列表、文件信息和前两段读取成功，第三段读取失败。模型按要求停止，无终端、配置修改或业务提交。
- 文件 62 字节、UTF-8、`text_read`。capabilities 空间与提示指定空间匹配。请求每段 12 原始字节，前两段返回 `[0,11)`、`[11,23)`，同一 source_revision，SHA-256 均为 `023887f7b2aff5b9ec2c79756c98f36676d8817c2b743f5a35cf3eddf9c04d70`，与合成源匹配；第三段 offset 23 失败，模型停止且未重试。真实桌面发现、限定工具及调用已经证实，完整六段读回仍未通过，AG-142 保持进行中，AG-143 不开工。真实聊天保留的服务原错误如下：

```json
{"code":"not_found","message":"文件不存在或不可访问","retryable":false,"details":{},"request_id":"e243956b-12a2-48af-aa19-023e0940e895"}
```
- 只读时序核对：源文件最后写入为 `02:44:59 UTC`；回合为 `03:02:17–03:05:21 UTC`；最后一条轨迹是第三段错误，文件最后写入 `03:04:59.129687 UTC`。夹具代码在写源后批准 `duration_seconds=1200`，随后才开始桌面准备和同为 1200 秒的服务等待；生产 `authorized_files` 将到期授权过滤为 `not_found`。这些是授权到期的强时序关联，不能替代原授权到期字段或每次调用时间：轨迹无逐条时间，私人授权文件已随收尾清除，原 `expires_at` 未取得。没有证据将其判为生产读取缺陷。
- 监督确认无 STOP，夹具自行到时退出 1，项目目录清理报 `WinError 32/5`；根目录仍有残留，单列待办。不得以此宣称正常清理通过。后续复验应在用户已就绪时启动新夹具并核对剩余 TTL 后立即发送，或修改验收夹具在发送前重新完整批准；不延长生产授权上限、不复用过期授权。额外模型回合须用户另行同意，本阶段未启动。
- 用户另行报告合成失效联接测试目录 `tmp0u2oav7r` 已手工删除，本轮 `Test-Path -LiteralPath` 返回 `False`。该项闭合，原自动审批 `blocked by policy` 拒绝工具清理的事实保留，不与两个桌面残留目录混同。
- 本阶段仅更新两份证据文档；核对真实聊天和脱敏轨迹、UTF-8、Markdown 围栏及 `git diff --check`，不涉及生产数据、API 或客户端配置变化。

### AG-142 真实 Codex 桌面只读复验通过（2026-11-11）

- 用户明确同意追加一轮并发送。真实聊天 `01a1caac-282c-7130-b02c-6d57806b915b` 的工作目录属于 `workbench-ag142-pilot-codex-oubzpt3a`，回合用时 174.567 秒。监督发送前核对目录恰四项、文件授权有效且剩余 1077 秒。聊天记录和中继均为 9 次 `workbench_ag142` 调用，全部成功。没有其他连接器调用、命令或写入。
- 空间匹配。capabilities、授权列表、文件信息和读取偏移 `0, 11, 23, 33, 43, 54` 通过，读至 62 字节 EOF。六段完整源 SHA-256 一致且与夹具匹配，监督程序比较回复代码块与合成源完全相等，首尾空格均保留。真实 Codex 桌面只读通过，写入矩阵和 WorkBuddy 桌面只读仍待验。AG-142 保持进行中，AG-143 待开始。
- 用户关闭临时聊天和项目后，监督写入 STOP，端口实测关闭。脚本退出 1，清理项目目录报 `WinError 32/5`，目录仍在，单列待办。最终审计未输出，旧凭据 401 未独立实测。
- WorkBuddy 5.9.3 / Hy4 实际 MCP 管理的添加页已证实用户级目标为 `~/.workbuddy/mcp.json`，只读解析 `mcpServers` 为空且无同名。管理列表有一个已启用的插件项，未见临时目标可预激活。添加页已取消。后续优先核对新隔离项目能否显示临时项，否则在用户就绪后生成完整单项候选，按兼容矩阵审查添加和移除。当前仅更新证据文档，真实客户端配置未写入，未发送 WorkBuddy 模型提示。

### AG-142 WorkBuddy 信任等待和读取窗口（2026-11-11）

- 用户批准单项用户级登记。监督使用 `ltijav5d` 夹具，复核基线后仅加入精确对象。实际编辑器追加 JSON 尾空白保存后列表出现目标。用户亲自完成首次信任，但原夹具已到时，0 次 initialize、0 个模型回合。脚本退出 0、旧凭据 401、端口关闭、目录移除。监督移除精确匹配对象并验证用户级配置与原字节完全一致。
- WorkBuddy 验收夹具先输出 `pending_activation`，单项目只读身份最多等待 1200 秒且没有文件授权。监督看到该次完整握手与 22 项目录后创建唯一 `ACTIVATE` 信号，夹具才使用既有本机管理预览和确认发放单文件 `text_read`，打印实际 `file_id`、Unix `file_expires_at` 和提示。读取窗口仍为 1200 秒，重复信号不续期。STOP、提前信号或等待超时执行既有撤销及清理。无需改生产授权或业务接口。
- 隔离 WorkBuddy 预演验证同一 MCP 连接激活前文件授权为空、读取返回 `not_found`，激活后六段原文和 SHA-256 匹配，提案被拒绝，旧凭据 401。Codex 四工具预演仍通过。缩短隔离夹具时钟实测未激活超时、提前信号无授权、重复信号不续期、读取到期收尾，端口关闭且目录移除。正常预演核对服务返回 1200 秒授权窗口，缩时对照未等待实际 20 分钟。文件授权过期拒绝随 `test_agent_files` 回归。`test_workbuddy_acceptance`、`test_mcp_stdio`、`test_agent_files` 共 43 项通过，脚本语法及 `git diff --check` 通过。
- 本次代码仅在验收脚本，未写真实 WorkBuddy 配置、未启动真实模型。真实桌面握手和只读仍待复验，AG-142 进行中，AG-143 待开始。
