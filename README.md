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

- 项目、条目及知识库文档只显示创建时间：项目概览与详情精确到秒，列表精确到分钟，卡片不显示时间。条目详情时间位于底部左侧，知识库详情位于底部右侧，按浏览器本地时区显示。旧数据缺失时间显示“未记录”，未保存文档显示“保存后生成”。Markdown 中的 `updated` 字段继续保留，供保存和最近更新排序使用。

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

前期 AI 接入扩展见 [详细执行方案](docs/AI_AGENT_EXTENSION_PLAN.md)：AG-116～121、AG-126 已完成，覆盖待办/结构化信息、提案管理、网页独立批准和本机客户端兼容；远程 AG-122～125 已取消且未实现。当前状态以 [实施台账](docs/AI_AGENT_PROGRESS.md) 和 [扩展验收](docs/AI_AGENT_EXTENSION_ACCEPTANCE.md) 为准。

附件上传、本机文件读取、概念图、删除、项目创建及分类/工作流变更见 [本机能力扩展执行方案](docs/AI_AGENT_LOCAL_CAPABILITIES_PLAN.md)。AG-127 仅为文档规划，用户已于 2026-11-09 授权执行。各能力的验收状态以 [实施台账](docs/AI_AGENT_PROGRESS.md) 为准。

项目没有包管理器或构建步骤。架构和模块职责见 [架构说明](docs/ARCHITECTURE.md)，日常修改、测试和发布步骤见 [维护说明](docs/MAINTENANCE.md)。重构执行事实记录在 [进度台账](docs/REFACTORING_PROGRESS.md)。

```powershell
python -m unittest -v
node test_editor_workflows.js
node test_timestamp_workflows.js
node test_agent_workflows.js
node test_agent_settings.js
node test_agent_attachment_workflows.js
python codex_agent_acceptance.py
python performance_acceptance.py
```

性能脚本只使用系统临时目录。默认规模与机器基线见 [大数据性能验收](docs/PERFORMANCE_ACCEPTANCE.md)。任何手工验收也应使用一次性目录，不要在真实 `workbench-data/` 上执行迁移、清理或压力测试。

AG-116 类型授权：管理页可显式选择 issue/document/todo/info，CLI 创建支持重复 `--agent-kind`。旧客户端及省略该字段仍仅 issue/document；AG-116 阶段仅开放 issue/document；AG-117 已开放 todo，info 已于 AG-118 开放，先查 capabilities。实施状态见 docs/AI_AGENT_PROGRESS.md。

AG-117 已开放受 kinds 授权的待办查询、新建、正文追加与更新，支持工作流、截止日期和 todo 深链接；info 已于 AG-118 开放。未授权 todo 的旧客户端权限不变。

AG-118 已开放 info 查询、新建、仅正文追加和字段更新。四类型均先生成完整提案预览并确认；info 字段保持顺序、换行、引号和首尾空格，只存储/复制命令文本。

AG-119：设置 → AI Agent 接入 → 提案管理，可按客户端/类型/状态/操作筛选当前空间提案，查看完整内容/差异、取消未提交版本并打开入库结果。网页批准已于AG-120开放，需local_web提案和当前完整预览。

提案管理的“查看恢复报告”可读取待核查与已放弃的事务状态。批准响应丢失时用“查询提案操作结果”找原回执。恢复和接受当前盘态仍使用停服维护命令。[维护说明](docs/MAINTENANCE.md)
完整预览在大弹窗内展示，支持本页上一条/下一条；关闭后保留筛选、页码与列表位置。窄屏使用全屏预览。

AG-120：客户端可设置最低确认方式为“本机网页独立批准”（CLI --agent-confirmation-mode local_web）。Agent 可请求同等或更严格策略，网页完整预览后点击批准入库；Agent自报确认不能绕过。批准响应丢失先查询原操作，不重复创建。

WorkBuddy桌面5.9.3(d4692421)已在临时库实测四类型新建/追加/更新、两确认路径、权限拒绝、分页/分段、幂等取消、丢响应查询、服务重启及轮换/撤销等故障。原装CLI2.165.0可运行python workbuddy_agent_acceptance.py核对连接与当前工具目录（旧12工具桌面证据不代表新能力矩阵），追加--protocol-faults显式测试固定服务端ping/未知方法响应（不调用模型、不写业务数据）；lite-only安装由原装入口自动选择固定lite开关。桌面和CLI证据分别记录，旧5.1.5历史不改写；结果和限制见[客户端兼容验收](docs/AGENT_CLIENT_COMPATIBILITY.md)。

按单机本地用途，远程接入已移出当前实施范围；不需要准备TLS/IdP/代理。[远程设计](docs/AGENT_REMOTE_DESIGN.md)仅保留历史参考，远程未实现。

AG-142 隔离验收可用 `python codex_pilot_anchor.py --init <新绝对目录>` 初始化专用空项目。图和附件试点的 `--anchor` 选项可复用该目录，各轮数据及凭据仍独立。仅用于合成验收，步骤与真实桌面限制见[客户端兼容验收](docs/AGENT_CLIENT_COMPATIBILITY.md)。

单条 issue 和项目级联删除分别使用 `python issue_delete_pilot.py --check` 和 `python project_delete_pilot.py --check`。两者均在新临时空间以零模型验证独立本机批准、原字节回收、回执和收尾。

当前本机扩展已交付：AG-116～121、AG-126已完成；AG-122～125按用户用途取消，远程未实现。最终235项Python、19项Node、全文件语法、真实客户端及备份恢复验收通过，临时接入已清理。详见[扩展验收与本地提交](docs/AI_AGENT_EXTENSION_ACCEPTANCE.md)。

AG-128已支持后续能力的休眠授权管理和能力协商；休眠配置尚不可使用，未来启用必须重新授权。实际测试和兼容边界见[本机能力验收](docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)。

AG-129已增加新提案保存计划与逐步持久恢复，旧提案摘要兼容保留；该阶段未开放新增业务能力。执行依据、故障复验和边界见[本机能力验收](docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)。

AG-130增加具体本机文件授权：设置→AI Agent接入→具体文件授权，先完整预览属性、再明确批准。可创建无旧业务范围的文件专用客户端。仅Windows固定NTFS普通文件，默认10MiB/1小时；Agent凭file_id分段只读，父路径不外传，文件不会自动入库。客户端可能把内容发往外部模型服务；附件来源本身只是意向。用法和限制见[接入使用](docs/AGENT_USAGE.md)。AG-130阶段固定工具15项；历史客户端12工具验收记录不代表新文件能力已由该客户端验收。

AG-131增加独立“上传暂存授权”：按客户端、具体目标、来源文件或原始流完整预览批准，旧意向不自动生效。普通MCP可用批准file_id让服务流式暂存，具备HTTP认证能力的客户端可用专用原始字节通道；不传整文件base64。单文件100MiB/client500MiB/空间1GiB，24h保留与安全恢复/清理。AG-131阶段固定19工具且不正式写入；正式附件于AG-132按独立共同许可开放。见[接入使用](docs/AGENT_USAGE.md)及[本机验收](docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)。


AG-132支持既有问题/待办/信息及项目独立附件创建：在暂存面板明确共同批准具体目标的暂存+附件创建及最低确认方式，再新建ready暂存、生成正式附件提案并完整预览确认；旧授权不自动扩权。该阶段20工具，get_attachment_target仅元数据，不下载字节；知识库附件由AG-133补齐，替换/删除仍未开放。支持有界复制、逐阶段恢复、正式回执后安全退休源暂存及原回执幂等查询。详见[使用步骤](docs/AGENT_USAGE.md)、[本机能力验收](docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)。

AG-133新增知识库附件：文档内“上传附件”先保存当前内容，再流式上传并插入受控相对链接；上传期间可继续输入，当前输入保留草稿，结果待定时先“查询附件结果”，不要重复上传。设置页“查看文档上传操作 / 恢复文档上传 / 回收终结上传暂存”可发现其他浏览器或重启留下的操作。Agent需为具体document重新共同批准，category使用文档原分类；该阶段仍为20工具，无任意二进制下载。文档导出单个.md不带附件；选择文档ZIP包含受控资源且只改副本路径，完整数据ZIP包含正式全局assets，操作证据不进入可移植ZIP。详见[数据格式](docs/DATA_FORMAT.md)与[维护](docs/MAINTENANCE.md)。

概念图版本与历史（AG-134已完成）：新页面按磁盘版本条件自动保存，旧缓存页面收到409时先刷新重读；冲突处理保留当前画布和撤销，可先导出JSON，再明确选择磁盘版或确认覆盖。更多操作可查看并恢复历史，恢复仍检查并发修改。关闭/切页前等待保存成功，刷新草稿为尽力恢复；草稿保存失败请先导出。概念图JSON历史全部保留，长期使用需留意磁盘增长；AG-135图接点见下文，已完成独立验收。详见[格式](docs/DATA_FORMAT.md)及[维护](docs/MAINTENANCE.md)。

概念图 Agent 接点（AG-135已完成）：设置→AI Agent 接入→客户端“概念图授权”，选择具体项目图、独立图分类或已有图，完整预览范围与资源版本后明确批准；旧通配范围和休眠配置不会生效。当前22工具，新增list_concept_maps/get_concept_map；图只接受完整create/update候选，提交前展示完整画布、全部节点/关系字段、原图、差异与警告，并依最严格策略对话确认或本机独立批准。新图预览已固定ID，取消不复用；时间由服务在接受确认时固定。保存失败先查询原提案；入库结果链接使用现有画布的保存/离开与冲突保护。

Agent 删除接点（AG-136已完成）：客户端“删除授权”需独立完整预览并批准具体范围，原读取权限也必须满足。四种Markdown条目和概念图只可生成单条删除提案，完整查看原文、全部潜在活动引用、附件保留及图结构后，在本机提案管理批准移入回收站；对话自报确认不能替代。默认回收站保留30天，本机可提前永久删除，Agent无恢复或永久删除能力。附件、历史和排序原样保留；操作不确定先查询原提案，旧提交不会再次删除已恢复条目。首期仅支持Windows固定NTFS普通文件，大小和扫描限制见[使用说明](docs/AGENT_USAGE.md)。

图编号单调游标config/concept-map-ids.json随完整备份/迁移保留，请勿手工删除或部分恢复。坏格式或未知占用停止分配，不归零；升级前已永久删除无证据ID无法追溯。v2带关系文字的图打开后保留节点/边ID，不再自动拆边；仅旧v1/缺version保留兼容迁移。图恢复遇同一固定ID占用返回409，不自动改文件名。边界见[数据格式](docs/DATA_FORMAT.md)、[使用](docs/AGENT_USAGE.md)、[维护](docs/MAINTENANCE.md)及[本机验收](docs/AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)。

项目创建 Agent 接点（AG-137 已完成）：设置→AI Agent 接入→客户端“项目创建授权”，独立批准后才可生成单个新项目提案。完整预览固定编号、说明、模板、目录及排序；正式目录只在本机批准后发布。创建不会新增项目访问范围；已有通配仍按旧规则。可从创建回执另行预览、批准原客户端的精确项目范围，两个结果分别查询。仅支持 Windows 固定 NTFS，详见[使用说明](docs/AGENT_USAGE.md)。

项目级联删除（AG-138）使用客户端的“项目级联删除授权”，选择具体项目并逐个批准独立附件。每条实际子记录都需既有读取和删除权限。每次移入回收站前，本机提案管理页完整展示原项目、全部子记录与目录、外部引用和保留原归属的关联图。项目外存在指向将移动附件的活动引用时拒绝整案。本机可从原回执打开回收站并以原 ID 恢复。详见[使用说明](docs/AGENT_USAGE.md)。

知识库、概念图和项目独立附件支持新建、重命名、删除和重排分类。确认前可查看成员、配置和排序变化。删除分类将成员迁入对应默认分类并保留内容和文件。Agent 需要在设置中取得具体分类、具体操作的授权，每次变更仍须本机独立批准。详见[使用说明](docs/AGENT_USAGE.md)。

工作流模板支持新建、复制、重命名及维护状态。删除使用中的状态或切换项目模板时，网页会列出需要映射的状态，并在批准前显示记录、完成语义和看板排序的变化。待办完成值由目标状态推导。Agent 每次变更需要精确工作流许可和独立本机批准。[使用说明](docs/AGENT_USAGE.md)
