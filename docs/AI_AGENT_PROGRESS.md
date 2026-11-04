# 通用 AI Agent 接入进度台账

最后更新：2026-11-04。

方案：[AI_AGENT_PLAN.md](AI_AGENT_PLAN.md)。执行规范：[AGENTS.md](../AGENTS.md)。本台账只记录 AG-* 新功能；原重构台账继续保留历史事实。

接入管理 UI 的需求、契约及验收分解见 [AGENT_SETTINGS_PLAN.md](AGENT_SETTINGS_PLAN.md)。AG-106 为文档工作；AG-107～111 的实施事实和当前状态见下表及记录。

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
| AG-111 | 兼容回归、维护文档与交付验收 | 待开始 | — | — | AG-110 |

状态只使用：待开始、进行中、受阻、已完成、已取消。每项开工记录精确范围、文件、检查和风险；完成记录实际结果、兼容影响和剩余问题。代码写完但未验证仍为进行中。

## 执行记录

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
