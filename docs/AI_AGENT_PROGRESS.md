# 通用 AI Agent 接入进度台账

最后更新：2026-11-06。

方案：[AI_AGENT_PLAN.md](AI_AGENT_PLAN.md)。执行规范：[AGENTS.md](../AGENTS.md)。本台账只记录 AG-* 新功能；原重构台账继续保留历史事实。

接入管理 UI 的需求、契约及验收分解见 [AGENT_SETTINGS_PLAN.md](AGENT_SETTINGS_PLAN.md)。AG-106 为文档工作；AG-107～111 的实施事实和当前状态见下表及记录。

后续扩展详见 [AI_AGENT_EXTENSION_PLAN.md](AI_AGENT_EXTENSION_PLAN.md)。AG-115 仅文档；AG-116～120 已完成；用户已明确仅本机使用，AG-122～125已取消当前实施；AG-121已选WorkBuddy并恢复本机兼容验收，AG-126本机验收已验证、待该兼容范围收口，不影响已完成首期的历史状态。

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
| AG-121 | 非 Codex 真实客户端兼容验证 | 进行中 | 2026-11-06 | — | AG-120 |
| AG-122 | 远程 MCP 协议、认证及部署设计门槛 | 已取消 | 2026-11-06 | — | AG-120；需目标身份服务/客户端 |
| AG-123 | 远程身份授权、主体映射与网络入口 | 已取消 | — | — | AG-122门槛；用户已授权实施 |
| AG-124 | 远程 MCP 传输与会话适配 | 已取消 | — | — | AG-123 |
| AG-125 | 真实远程拓扑验收与停用维护 | 已取消 | — | — | AG-124、AG-121 |
| AG-126 | 本机兼容回归、文档与交付验收 | 受阻 | 2026-11-06 | — | AG-117～121；远程项已取消 |

状态只使用：待开始、进行中、受阻、已完成、已取消。每项开工记录精确范围、文件、检查和风险；完成记录实际结果、兼容影响和剩余问题。代码写完但未验证仍为进行中。

## 执行记录

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
