# 本地工作台

本地工作台是一个零运行时依赖、单用户、本地优先的项目与知识管理应用。Python 标准库提供 HTTP 服务，浏览器端使用原生 HTML、CSS 和 JavaScript；项目、记录和知识库正文以 Markdown 为事实源。

## 快速开始

需要 Python 3.11 或更高版本，以及现代 Edge、Chrome 或其他兼容浏览器。在仓库目录运行：

```powershell
python server.py --seed-demo --open
```

默认地址为 `http://127.0.0.1:4173`。`--seed-demo` 只在没有项目时创建演示数据，后续可直接运行 `python server.py`。Windows 也可以双击 `start-workbench.cmd`。

```text
--host <地址>       默认 127.0.0.1
--port <端口>       默认 4173
--data-dir <目录>   本次使用指定数据目录
--seed-demo         空目录时创建演示数据
--open              启动后打开浏览器
--replace           安全替换使用相同数据目录的旧服务
--enable-agent      本次启动开启 Agent 接口
--disable-agent     本次启动关闭 Agent，覆盖已保存的启动偏好
```

## 数据与备份

默认数据位于仓库下的 `workbench-data/`，可在设置中迁移，也可临时指定：

```powershell
$env:WORKBENCH_DATA_DIR = 'D:\MyWorkbenchData'
python server.py
```

主要数据包括项目 README、问题、待办、结构化信息、知识库文档、概念图、附件、历史和回收站。删除默认移入 `.trash`；永久删除不可恢复。完整目录和兼容契约见 [数据格式](docs/DATA_FORMAT.md)。

工作台支持项目或完整 ZIP 备份。完整备份不会携带本机绝对路径设置；恢复时应解压到新目录，再通过 `--data-dir` 或设置页打开。当前应用不提供 ZIP 一键导入。

## 主要能力

- 项目、条目及知识库文档可查看创建时间和上次修改时间：项目概览与详情精确到秒，列表精确到分钟，卡片不显示这两项时间。条目详情时间位于底部左侧，知识库详情位于底部右侧，按浏览器本地时区显示。旧数据缺失时间显示“未记录”，未保存文档显示“保存后生成”。修改时间沿用 Markdown 的 `updated`；项目包含自身资料及排序设置的保存，不汇总子条目活动；外部编辑器未同步时间字段时可能仍显示旧值。

- 项目记录支持状态、标签和优先级组合筛选及一键清除；切换项目或记录页签时自动清空筛选。
- 项目、问题、待办及无状态结构化信息；旧 `idea` 文件兼容读取，但不再从 UI 新建。
- 自定义工作流、状态、标签、排序、归档、回收站、历史版本和全局搜索。
- 记录与知识库共享的可视化/Markdown 编辑器，支持草稿恢复、内容版本检查、外部修改检测、三种冲突处理和历史查看/恢复。
- 记录和知识库可显示外部编辑器保存的相对路径图片，保存重开后保留原始图片路径。
- 稳定 `[[ID]]` 引用、反向链接、附件拖放/粘贴、流式大附件上传与孤儿清理；项目附件总览汇总项目及条目附件，图片、音视频和 PDF 可在浏览器预览，其余附件交给 Markdown 编辑器或系统默认应用打开。
- 独立知识库分类、分类内排序、批量 Markdown 导入和选择性 ZIP 导出。
- JSON 概念图，支持 500 个节点、撤销重做、自动保存、视口和导出。
- 浅色/深色主题与桌面/窄屏响应式布局。

## 开发与维护

在“设置 → AI Agent 接入”可开启/关闭接入、保存启动偏好、管理客户端授权，并通过“接入向导 → 检查并接入本机 Codex”预览、确认登记和自动检查连接，无需打开终端。同名冲突可改名或明确选择替换；写入前保留原配置备份。首次默认关闭；检查通过不代表当前聊天已加载工具。设计与阶段状态见 [实施与维护方案](docs/AGENT_SETTINGS_PLAN.md) 和 [台账](docs/AI_AGENT_PROGRESS.md)。

高级手工接入仍可选择 CMD 或 PowerShell；检测到 Codex 后使用绝对路径生成命令，避免终端 PATH 差异。Windows 默认 CMD；通用 MCP 可复制程序与参数。

通用 AI Agent 接入支持通过 MCP 在 Codex 中整理问题和知识文档，新建、追加和修改均先生成完整预览，用户确认当前版本后再正式入库，并返回网页打开链接。启用、授权与登记步骤见 [接入说明](docs/AGENT_INTEGRATION.md)，Agent 操作规则见 [使用指引](docs/AGENT_USAGE.md)，验证证据见 [业务验收](docs/AI_AGENT_ACCEPTANCE.md) 和 [管理 UI 验收](docs/AGENT_SETTINGS_ACCEPTANCE.md)。Codex 配置仅在页面明确确认接入后写入。

后续 AI 接入扩展已形成 [详细执行方案](docs/AI_AGENT_EXTENSION_PLAN.md)：待办/结构化信息、提案管理、网页独立批准、其他客户端兼容验证和远程 MCP。当前仅完成方案，AG-116～126 尚未开始，不属于现有功能。

项目没有包管理器或构建步骤。架构和模块职责见 [架构说明](docs/ARCHITECTURE.md)，日常修改、测试和发布步骤见 [维护说明](docs/MAINTENANCE.md)。重构执行事实记录在 [进度台账](docs/REFACTORING_PROGRESS.md)。

```powershell
python -m unittest -v
node test_editor_workflows.js
node test_timestamp_workflows.js
node test_agent_workflows.js
node test_agent_settings.js
python codex_agent_acceptance.py
python performance_acceptance.py
```

性能脚本只使用系统临时目录。默认规模与机器基线见 [大数据性能验收](docs/PERFORMANCE_ACCEPTANCE.md)。任何手工验收也应使用一次性目录，不要在真实 `workbench-data/` 上执行迁移、清理或压力测试。

AG-116 类型授权：管理页可显式选择 issue/document/todo/info，CLI 创建支持重复 `--agent-kind`。旧客户端及省略该字段仍仅 issue/document；AG-116 阶段仅开放 issue/document；AG-117 已开放 todo，info 已于 AG-118 开放，先查 capabilities。实施状态见 docs/AI_AGENT_PROGRESS.md。

AG-117 已开放受 kinds 授权的待办查询、新建、正文追加与更新，支持工作流、截止日期和 todo 深链接；info 已于 AG-118 开放。未授权 todo 的旧客户端权限不变。

AG-118 已开放 info 查询、新建、仅正文追加和字段更新。四类型均先生成完整提案预览并确认；info 字段保持顺序、换行、引号和首尾空格，只存储/复制命令文本。

AG-119：设置 → AI Agent 接入 → 提案管理，可按客户端/类型/状态/操作筛选当前空间提案，查看完整内容/差异、取消未提交版本并打开入库结果。网页批准已于AG-120开放，需local_web提案和当前完整预览。
完整预览在大弹窗内展示，支持本页上一条/下一条；关闭后保留筛选、页码与列表位置。窄屏使用全屏预览。

AG-120：客户端可设置最低确认方式为“本机网页独立批准”（CLI --agent-confirmation-mode local_web）。Agent 可请求同等或更严格策略，网页完整预览后点击批准入库；Agent自报确认不能绕过。批准响应丢失先查询原操作，不重复创建。

WorkBuddy桌面5.9.3(d4692421)已在临时库实测四类型新建/追加/更新、两确认路径、权限拒绝、分页/分段、幂等取消、丢响应查询、服务重启及轮换/撤销等故障。原装CLI2.165.0可运行python workbuddy_agent_acceptance.py验证连接/12工具，追加--protocol-faults显式测试固定服务端ping/未知方法响应（不调用模型、不写业务数据）；lite-only安装由原装入口自动选择固定lite开关。桌面和CLI证据分别记录，旧5.1.5历史不改写；结果和限制见[客户端兼容验收](docs/AGENT_CLIENT_COMPATIBILITY.md)。

按单机本地用途，远程接入已移出当前实施范围；不需要准备TLS/IdP/代理。[远程设计](docs/AGENT_REMOTE_DESIGN.md)仅保留历史参考，远程未实现。

当前本机扩展已交付：AG-116～121、AG-126已完成；AG-122～125按用户用途取消，远程未实现。最终235项Python、19项Node、全文件语法、真实客户端及备份恢复验收通过，临时接入已清理。详见[扩展验收与本地提交](docs/AI_AGENT_EXTENSION_ACCEPTANCE.md)。
