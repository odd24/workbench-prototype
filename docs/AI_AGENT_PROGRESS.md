# 通用 AI Agent 接入进度台账

最后更新：2026-11-03。

方案：[AI_AGENT_PLAN.md](AI_AGENT_PLAN.md)。执行规范：[AGENTS.md](../AGENTS.md)。本台账只记录 AG-* 新功能；原重构台账继续保留历史事实。

## 工作项

| ID | 范围 | 状态 | 开始 | 完成 | 依赖 |
| --- | --- | --- | --- | --- | --- |
| AG-000 | 需求、方案和执行规范 | 已完成 | 2026-11-03 | 2026-11-03 | 用户已确认 Codex 优先、每次预览、通用接口 |
| AG-101 | 写入协调、版本检查与文档历史 | 已完成 | 2026-11-03 | 2026-11-03 | AG-000 |
| AG-102 | 认证、访问边界与只读 API | 待开始 | — | — | AG-101 |
| AG-103 | 提案、确认提交、幂等与恢复 | 待开始 | — | — | AG-102 |
| AG-104 | MCP 适配与 Codex 联调 | 待开始 | — | — | AG-103 |
| AG-105 | 深链接、全流程验收与发布 | 待开始 | — | — | AG-104 |

状态只使用：待开始、进行中、受阻、已完成、已取消。每项开工记录精确范围、文件、检查和风险；完成记录实际结果、兼容影响和剩余问题。代码写完但未验证仍为进行中。

## 执行记录

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
