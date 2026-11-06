# 通用 AI Agent 接入进度台账

最后更新：2026-11-06。

方案：[AI_AGENT_PLAN.md](AI_AGENT_PLAN.md)。执行规范：[AGENTS.md](../AGENTS.md)。本台账只记录 AG-* 新功能；原重构台账继续保留历史事实。

接入管理 UI 的需求、契约及验收分解见 [AGENT_SETTINGS_PLAN.md](AGENT_SETTINGS_PLAN.md)。AG-106 为文档工作；AG-107～111 的实施事实和当前状态见下表及记录。

后续扩展详见 [AI_AGENT_EXTENSION_PLAN.md](AI_AGENT_EXTENSION_PLAN.md)。AG-115 仅文档；AG-116～126 均未启动，不影响已完成首期的历史状态。

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
| AG-116 | 类型授权、能力协商与流程格式兼容 | 待开始 | — | — | AG-115；实现另行授权 |
| AG-117 | 待办 todo 查询、提案与持久写入 | 待开始 | — | — | AG-116 |
| AG-118 | 结构化信息 info 与字段无损往返 | 待开始 | — | — | AG-117 |
| AG-119 | 本机提案管理、预览、取消与结果查询 | 待开始 | — | — | AG-118 |
| AG-120 | 网页独立批准与持久恢复 | 待开始 | — | — | AG-119 |
| AG-121 | 非 Codex 真实客户端兼容验证 | 待开始 | — | — | AG-120 |
| AG-122 | 远程 MCP 协议、认证及部署设计门槛 | 待开始 | — | — | AG-120；需目标身份服务/客户端 |
| AG-123 | 远程身份授权、主体映射与网络入口 | 待开始 | — | — | AG-122；远程实现另行授权 |
| AG-124 | 远程 MCP 传输与会话适配 | 待开始 | — | — | AG-123 |
| AG-125 | 真实远程拓扑验收与停用维护 | 待开始 | — | — | AG-124、AG-121 |
| AG-126 | 扩展全量回归、文档与交付验收 | 待开始 | — | — | AG-117～125 |

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
