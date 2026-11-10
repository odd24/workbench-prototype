# 维护与发布

## 修改入口

AI Agent 下一阶段的文件、附件、概念图、删除、项目和分类/工作流实施依据见 [本机能力扩展执行方案](AI_AGENT_LOCAL_CAPABILITIES_PLAN.md)。AG-127 仅文档；用户已授权执行，AG-128授权基础已完成；后续依赖未满足不开放能力或启动真实客户端验收。当前业务备份、私人状态和降级规则不变；拟定新格式须随实际实现另行记录与验证。

- 领域或持久化规则：修改对应 `workbench/*.py` 仓储，HTTP Handler 只做协议转换。
- 新增 API：同步仓储、`workbench/http_api.py`、前端调用、错误提示和 HTTP 测试。
- Markdown/编辑器：同时覆盖记录与知识库的渲染、模型、序列化、保存重开和阅读模式。
- 前端状态或请求：复用 `Workbench.appState` 与请求注册表，不新增平行全局状态。
- CSS：进入对应 `css/*.css`；媒体查询只进入 `responsive.css`，并更新 `index.html` 缓存版本。

兼容导出、旧格式读取、`localStorage` 键和 `window.Workbench` 名称都是接口。没有迁移方案和测试时不要删除或重命名。

## 自动检查

```powershell
python -m unittest -v

$pyFiles = @(Get-ChildItem -Recurse -File -Filter *.py | ForEach-Object FullName)
python -m py_compile @pyFiles

$jsFiles = @(Get-ChildItem -Recurse -File -Filter *.js | ForEach-Object FullName)
foreach ($file in $jsFiles) { node --check $file; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }

git diff --check
```

全部 Node 契约（其中编辑器工作流会启动临时服务和真实浏览器）：

```powershell
$tests = Get-ChildItem -File test*.js | Sort-Object Name
foreach ($test in $tests) { node $test.FullName; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
```

概念图交互可单独运行 `node test_concept_map_workflows.js`。该测试自动使用临时数据目录与真实浏览器，覆盖缩放、概念/连接词连线、拖拽中断恢复、编辑后拖动、空白处扩展、撤销重做和保存重开，并检查浅色/深色与桌面/窄屏。设置 `WORKBENCH_CONCEPT_SCREENSHOTS=1` 可将截图写入系统临时目录。

视觉验收使用 `visual_baseline.js`，清单见 [BASELINE_CHECKLIST.md](BASELINE_CHECKLIST.md)。编辑器矩阵见 [EDITOR_ACCEPTANCE_MATRIX.md](EDITOR_ACCEPTANCE_MATRIX.md)。大数据验收运行 `python performance_acceptance.py`，基线见 [PERFORMANCE_ACCEPTANCE.md](PERFORMANCE_ACCEPTANCE.md)。

## 安全的手工环境

```powershell
$testData = Join-Path $env:TEMP ("workbench-agent-" + [guid]::NewGuid())
python server.py --data-dir $testData --seed-demo --port 4174
```

不要对真实 `workbench-data/` 执行迁移、清理、删除、压力测试或视觉样本替换。测试完成后停止服务，再删除一次性目录。

## 发布检查

1. 查看 `git status --short`，确认没有用户数据、`.workbench-*.json`、日志、缓存、截图或导出包。
2. 运行完整 Python、Node、语法和差异门禁。
3. 涉及 UI 时完成浅色/深色、桌面/窄屏、空/多数据与交互状态验收。
4. 涉及编辑器时完成记录和知识库的可视化 → Markdown → 保存 → 重开，以及失败、草稿、外部修改和冲突路径。
5. 涉及数据时用新仓储实例重新读取；涉及导出时验证 ZIP CRC 和成员路径。
6. 确认 `index.html` 资源版本、README、架构/数据文档和进度台账同步。
   后端功能变化还须更新 `workbench/http_api.py` 的 `APP_VERSION`；`--replace` 会复用版本号相同的进程，未更新会造成新前端调用旧后端接口。
7. 形成一笔可独立回滚、验证通过的本地提交。

## 已知后续方向

- `app.js` 仍包含页面 DOM 模板和跨功能适配；继续拆分应移动一个完整边界，不能复制渲染或编辑器实现。
- 是否切换 ES Modules、是否把根目录测试迁入 `tests/`，均是独立治理工作，不属于已完成重构的兼容性修补。
- 大数据基线中长 Markdown 打开是最明显的单次主线程阻塞点；若实际数据继续增长，可单独评估分块渲染或虚拟化。

## 保存与目录所有权

同一数据目录只允许一个服务写入，即使端口不同。启动时如提示目录被占用，请访问已有服务或先停止它；不要删除运行锁文件来绕过所有权。`--replace` 在装配仓储前检查已有服务。同一目录迁移时持有共享写锁，并先取得目标目录锁；失败保留当前服务和源数据。

记录和文档更新/历史恢复应使用读取结果中的 revision 作为 expected_revision。409 表示版本已变化，应保留输入并处理冲突，不进行无条件自动重试。省略版本仅为旧客户端兼容。外部编辑器不遵守服务锁，文件替换附近仍可能竞争，修改前历史与日常备份继续必要。

## Agent 客户端维护

常用入口为“设置 → AI Agent 接入”。管理页面会话过期后刷新状态，不自动重放写入；保存超时先查询原操作再核对列表。轮换通常不改变配置路径，桥接每次请求重读；撤销不自动移除 Codex MCP 登记。若端口改变，点击对应客户端“更新服务地址”，再检查连接；若仓库或 Python 位置改变，通过向导重新检查并确认更新登记，也可使用高级手工命令。

### Codex 一键登记（AG-113）

先核对页面显示的目标 `CODEX_HOME/config.toml`（缺省当前用户 `.codex/config.toml`）；服务运行用户或环境变量与桌面不同会指向不同配置。一键接入不修改 PATH、不安装软件，不接受 HTTP 指定可执行路径。Windows PATH 仅有 npm 的 codex.cmd 而无原生 exe 时会提示使用高级手工接入，或从桌面安装环境重新启动工作台。官方登记格式见 [OpenAI Docs MCP](https://learn.chatgpt.com/docs/extend/mcp)，修改 CLI 适配后须在隔离环境重新实测。

预览摘要同时绑定整个文件和客户端版本；授权、同名项或无关配置变化都需要重新检查。生成阶段固定调用 mcp add（最多 8 秒）和 mcp get --json（最多 3 秒），每流限制 128 KiB，隐藏子进程窗口；只在私人临时 CODEX_HOME 写入候选，语义比较只允许目标 MCP 项变化。生成失败保留原文件；明确确认后才备份并安装。

响应丢失先点击“查询上次接入结果”。当前标签页刷新后从 sessionStorage 恢复请求编号；服务重启使用持久回执，查询不重放写入。completed 表示记录的候选曾确认写入，configuration_unchanged=false 提醒现值已变化，需重新检查；not_applied 表示准备后未写入，可重新预览以新请求接入；recovery_required 表示发现第三方内容，必须核查，不能直接重复覆盖。登记成功而自检失败时保留登记，按对应诊断层修复，不自动回滚。

私人 `<workspace_id>/codex-registrations/<sha256(request_id)>/` 长期保留 receipt.json、before.toml（原文件存在时）和 after.toml；快照可能含其他 Codex 凭据，不能上传日志或进入可移植备份。与 management-operations 的精简凭据回执不同，这里不自动清除原配置备份。关闭标签页丢失查询提示时，按请求编号 SHA-256 或客户端/登记名在本地 receipt.json 核查；只查看状态/摘要，不公开快照正文。未知格式保持原样。

手工回滚前停止相关工作台和 Codex，备份当前 config.toml 与整份私人操作目录，比较 before/after/现值，仅恢复确定属于该次登记的项。只有现值仍完全等于 after.toml 且用户确实希望回退整份配置时，才可使用 before.toml 恢复；原文件不存在时不盲目删除新配置，以免删除后续设置。不删除日志以重试，也不把单文件替换当作多文件事务。工作台锁不能约束外部编辑器，写前重读与替换间仍有竞态。业务库迁移后私人操作记录仍按 workspace_id 查找；迁移 CODEX_HOME 后旧回执目标不同会拒绝查询，须对原目标离线核查。

后续验收须为服务设置临时 CODEX_HOME，同时隔离数据/凭据；不能让新增一键按钮测试落到真实用户配置。登记、自检和当前聊天工具加载是三份不同证据，当前聊天仍可能需要重启或新建。

AG-112 的向导支持 CMD/PowerShell 选择，标签、命令和步骤同时变化。看到“此时不应有 &”应核对是否在 CMD 粘贴 PowerShell 命令；看到“codex 不是内部或外部命令”应重新打开向导，使用检测到的绝对路径。检测顺序为服务 PATH、当前用户 LOCALAPPDATA/OpenAI/Codex/bin 下实际存在的版本化 codex.exe；不扫描其他用户目录或修改 PATH。无匹配时保留明确提示。CMD 不支持安全复制的路径字符引导改用 PowerShell，不执行有歧义的命令。诊断和向导复用同一检测函数。

诊断任务、客户端请求观察仅保留于当前服务内存；重启后暂无记录。每客户端同时只运行一项，保留最近 50 份；版本检测/桥接总时限分别 3/8 秒，每流 128 KiB，超限或超时回收进程。nonce 仅环境/专用头流转，不记录或展示。检查通过不证明当前 Codex 聊天接入，仍要在新聊天做只读工具调用。修改诊断需运行 `python -m unittest test_agent_diagnostics -v` 和真实浏览器 `node test_agent_settings.js`。

本机灾难备份应停服并妥善保护私人凭据目录、未决日志及业务目录；便携 ZIP 不含这些接入状态。使用设置页的复制迁移保留同一 workspace_id；直接复制目录得到的副本共享身份和本机授权，不能当成独立库同时使用。要独立副本，优先通过可移植 ZIP 解压到新目录再开启接入，建立新身份/客户端，不手工删除未决 `.agent` 日志。自定义凭据根在启动/管理/恢复时必须一致。

runtime.json 损坏/未知版本时保留文件并默认关闭；先用 `--disable-agent` 启动，停服备份后按 [格式说明](DATA_FORMAT.md) 核对并修复本机配置，不自动覆盖。凭据损坏而无可靠备份时撤销旧客户端并新建；不要把完整配置或令牌贴入诊断/聊天。

AG-108 的凭据管理恢复使用同一数据目录和凭据根：`python server.py --data-dir <目录> --agent-config-dir <私人根> --agent-management-report`。它尝试可证明安全的恢复并报告未决操作，不输出令牌。第三方内容冲突时先停止服务并备份完整私人目录，核对后可用 `--agent-management-abandon <operation_id>` 放弃该操作；此操作保留当前配置文件、撤销相关客户端并清除日志凭据快照，不恢复旧令牌。未知/损坏日志拒绝放弃，不删除日志绕过。

正常启用、管理写入或操作查询会尝试恢复 prepared；recovery_required 只暂停相关客户端，其余客户端正常工作。已完成/已放弃日志保留精简幂等回执，不含令牌快照；未决快照不得自动清理。降级前先解决管理与业务未决操作并备份。分类同步失败可能已经完成业务重命名，应重新读取分类并核对授权；不要假定错误意味着业务完全未改动。

本机 Agent 接入与授权命令见 [AGENT_INTEGRATION.md](AGENT_INTEGRATION.md)。首次默认关闭，普通启动读取当前空间本机偏好；--enable-agent/--disable-agent 显式覆盖当次状态，--agent-config-dir 指定外部凭据根。--replace 同时比较 Agent 是否启用，避免复用功能状态不同的旧服务。更换凭据目录需要重新启动服务。

静态文件必须在 index.html 显式加载清单内才能访问。新增 UI 资源时同时验证正常加载与目录/源码/数据拒绝访问；不要恢复对仓库根的无限制静态服务。

Agent 提案/提交故障的恢复步骤、运行中清理和本机接受磁盘命令见 [接入说明](AGENT_INTEGRATION.md)。遇到 recovery_required 不要删除 .agent，先停止服务完整备份后核查。即使不带 --enable-agent 启动，也不能绕过已有事务恢复。未决事务阻止业务写入与目录切换。

发布 Agent 变更时运行 `node test_agent_workflows.js` 和 `python codex_agent_acceptance.py`；后者要求已安装 Codex CLI，只使用隔离配置/临时库，不调用模型。浏览器脚本覆盖深链接、两编辑器冲突和在途保存后继续输入的草稿保留。视觉基线另行使用临时样本库和空库运行；性能使用 `python performance_acceptance.py`。当前验收结果及剩余限制见 [AI_AGENT_ACCEPTANCE.md](AI_AGENT_ACCEPTANCE.md)。

### AG-116 升级与降级

升级兼容 schema=1 私人配置、凭据日志、提案和事务；新流程写 schema=2。旧凭据默认仅 issue/document，轮换和分类授权同步不扩权。新增专项 `python -m unittest -v test_agent_extensions`，管理修改运行 `node test_agent_settings.js`。

降级前关闭 Agent、停止服务，备份业务目录（含 .agent）与私人凭据目录，使用当前版本 report/abandon 解决未决事务。旧版本不能读取 schema=2 时应保留文件并改回匹配版本，不删除 .agent/管理日志绕过，不把便携 ZIP 当作接入状态备份。

### AG-117 验证入口

待办专项包含 test_agent_extensions.TodoAgentTests、node test_frontend_entry.js、node test_agent_workflows.js 与 python codex_agent_acceptance.py（增加 todo，仍仅隔离配置）。新建/更新事务恢复继续走原 before/after/第三方判定；删除项目后不恢复创建项目。旧转换编号兼容见数据格式。

### AG-118 字段兼容验收

共享信息字段归一化修正首尾空格并扩大200项/名称200字符，需同时运行 test_markdown、test_records、test_agent_extensions 与 node test_agent_workflows.js、node test_editor_workflows.js。真实 Codex 隔离验收已扩为四类型；字段原文、顺序和 note 必须重新读取比较。限额由 capabilities 返回，不用界面截断代替服务端拒绝。

### AG-119 管理验收

新增 python -m unittest -v test_agent_proposal_management 与 node test_agent_proposal_workflows.js，修改管理页仍运行 node test_agent_settings.js。取消日志位于.agent/proposal-actions，停服备份须保留；业务日志与取消日志职责分离。管理读取不初始化空空间，不自动发起业务提交；恢复中的提案提示本机核查。

### AG-120 批准恢复

新增python -m unittest -v test_agent_web_approval，涵盖四类型三操作、独立票据、撤销/收窄/策略变化、幂等/并发和真实进程正文写后退出。node test_agent_proposal_workflows.js覆盖网页批准及响应丢失刷新查询；真实Codex脚本涵盖local_web拒绝自报和本机批准后同回执查询。

停服备份同时保留.agent/proposal-actions批准证据和operations事务；不能删批准日志绕过。只有批准记录而无manifest不会自动补写。prepared未尝试应用时需要匹配私人授权才能恢复，恢复CLI通过--agent-config-dir装配该授权；缺失/不匹配时保留并报告，启动同空间/私人凭据环境核查；撤销后停止未应用写入，已进入应用按磁盘事实完成必要回执。仍可使用原report/abandon接受磁盘，不删除日志。

AG-121当前WorkBuddy桌面5.9.3(d4692421)已实际验证四类型三操作、两确认路径、权限拒绝、幂等取消、提交丢响应查询、服务重启、轮换/撤销、错空间及限流；旧5.1.5记录保留历史标签。原装CLI2.165.0的python workbuddy_agent_acceptance.py只验证隔离连接/12工具；--protocol-faults显式注入固定服务端ping/未知方法、验证真实回复，无模型/业务写入，不能外推桌面。--desktop-session仅准备一次性项目，桌面历史/临时连接器例外及手动测试额度以台账授权为准；结束须撤销临时凭据、停止进程、清理副本/别名并由用户仅移除临时连接器，不把配置文件存在当作接入成功。精确矩阵与收尾事实见[客户端兼容矩阵](AGENT_CLIENT_COMPATIBILITY.md)。

远程默认未提供实现；候选部署边界、威胁模型和恢复/停用验收见[AG-122设计准备](AGENT_REMOTE_DESIGN.md)。未经真实IdP/TLS/客户端验证不得标远程可用，不应直接公网化本机工作台。

显式隔离生命周期演练：python extension_lifecycle_acceptance.py，验证四类型两确认路径、关闭Agent普通读取、停服完整备份/批准回执恢复、便携ZIP CRC/接入排除/新身份。仅使用TemporaryDirectory，不启动模型或修改用户配置。脚本non_codex_and_remote标记仅说明自身未执行外部客户端，不覆盖另行取得的WorkBuddy实测；远程按用户范围取消。[扩展验收](AI_AGENT_EXTENSION_ACCEPTANCE.md)分别记录各项证据。

当前范围更新（2026-11-06）：AG-122～125按用户单机用途取消，原远程外部门槛不再阻塞本机交付；既有设计仅作历史参考。本机使用不需要TLS/IdP/代理，原loopback边界保持。

显式客户端验收的Windows后代进程由acceptance_process.ClientJob回收；该模块只被验收脚本引用，不进入应用运行时。修改它需运行test_startup和真实Codex/WorkBuddy连接检查，涵盖根进程先退出仍持有管道/cwd的场景。临时会话存在时不要把其健康检查当作模型或完整兼容通过。


WorkBuddy验收脚本兼容原装lite-only安装：完整CLI产物缺失且lite-wb.mjs存在时，通过厂商bin入口的固定环境开关选择lite-wb，输出cli_bundle；不提取SDK或修改安装文件。2026-11-07当前CLI2.165.0默认/显式探针通过，桌面运行版本由用户关于页核实为5.9.3，旧5.1.5结果保留独立版本标签。客户端升级后不能直接继承旧版完整矩阵，现状见[兼容矩阵](AGENT_CLIENT_COMPATIBILITY.md)。

## 创建时间展示

运行 `node test_timestamp_workflows.js`，使用临时数据目录和真实 Edge/Chrome，覆盖项目概览、三类条目底部左侧及知识库底部右侧的创建时间、卡片不显示时间、排序、保存失败/重试、重开/刷新、外部修改、历史恢复、缺失及异常时间、空数据/120 项、浅色/深色和桌面/窄屏。`WORKBENCH_TIMESTAMP_SCREENSHOTS=1` 将评审截图写入系统临时目录，不写入仓库。界面仅显示现有 `created`，不迁移数据；`updated` 继续用于保存和最近更新排序，但不显示修改时间；文件 mtime 仍只用于外部变更检测，不替代业务修改时间。


### AG-128 私人授权格式与降级

首次显式保存新grants升级根registry到2、授权到3、管理日志到3；transport仍2。只读旧库不迁移，根2即使清空grants或abandon也保持。正常report/recover/abandon复用持久日志，未知格式及新日志混合旧未决拒绝恢复，不删除证据。旧二进制应拒绝管理/鉴权新格式，不承诺能只读新授权；普通网页不属于这个授权格式保证。

降级必须停服，先用当前新版report并解决未决日志，再保留业务及私人状态的完整匹配备份。当前无授权格式导出/降级转换工具；可行回退仅恢复经核对的、升级前业务+私人状态匹配备份，再使用相应旧代码。没有匹配备份则继续新版，不手改schema、不丢grants或删日志绕过。回退会失去备份之后的状态，须由操作者明确选择；不能把已发给外部客户端的内容收回。测试仅使用临时空间，真实配置不参与。


### AG-129 执行恢复

proposal3/manifest3(execution_schema_version=1)/approval action3保留原独立目录，旧1/2事务与旧批准/取消格式继续读取。恢复、过期、取消和清理先验证全部已知格式，不在发现未知算法/步骤后继续修改其他日志。prepared/applying只是进度：实际正文仍before必须重查私人授权版本和依赖，即使历史已落；正文after且证据完整只补原回执。create进入applying后正文缺失不重建，使用report核查，接受磁盘只能通过已知格式abandon，不自动回滚。

正常关闭Agent入口的服务启动仍会在runtime挂载后恢复；匹配私人配置可恢复已接受操作，配置缺失则保持写保护、普通读取可用。CLI继续显式传同一agent-config-dir；不能猜测其他私人目录。已形成回执不因后来编辑/删除重放正文，清理只移除终结内容快照且保留幂等/计划/回执；在途记录即使被错误标为content_cleaned也拒绝恢复。

预检逐一验证JSON格式/身份/摘要绑定，但匹配终结回执时不重新读取Markdown快照；在途快照仍完整验证。临时历史样本只证明预检I/O回归，不是完整性能基线。回退旧代码前先解决新事务并停服备份，旧版不认识schema3时不能删日志绕过。未来处理器须按版本新增分支，不改变markdown@1或旧摘要语义。

### AG-130 文件授权与私人备份

新增python -m unittest -v test_agent_files及node test_agent_settings.js；所有源文件、链接/盘符别名和凭据都必须为临时合成夹具。原生安全证明限Windows固定本机NTFS，拒所有多硬链接、重解析/联接、SUBST、UNC/设备/ADS；其他平台文件入口fail closed，旧业务保留。逐段O(file-size)校验、块间5秒截止仍有OS同步等待、已获许可响应可迟到，不能宣传绝对超时或撤回。

停服匹配私人备份须包含clients根3、file-grants、management-operations日志4及management-snapshots，与原workspace身份保持一致；不能把私人目录复制到业务ZIP或Git。源文件不在业务备份里，恢复授权不会重新hash或读取源，后续读取仍按批准版本验证。批准或撤销结果不确定先查原operation；prepared/recovery_required保留现场，先report，再核对是否继续恢复或显式abandon。

快照首写后未prepared即退出，重启在完整预检后先持久abandoned再清理，不发布授权。completed/abandoned后清理失败可由operation查询snapshot_cleanup_pending，重启恢复会重试，不能手动删日志或先删未决快照。根3下凭据轮换/编辑/撤销也使用同一日志4，完成后才清除秘密快照；不确定先查询，不重放。旧9b6924d必须拒绝新根/日志，降级只能停服恢复匹配旧备份，不能删除格式门槛。三文件工具的原始MCP实测不是AG-142真实模型客户端矩阵。

### AG-131 暂存维护与回退

运行python -m unittest -v test_agent_uploads、node test_agent_settings.js及相应Agent/HTTP/MCP门禁；100MiB真实临时文件专项只证明有界流式，不是完整性能基线。新工具目录19项，既有真实CLI无模型回归与AG-142新模型客户端矩阵分开。Windows固定NTFS为当前实际支持边界；源文件拒重解析/多硬链接/SUBST/秘密位置，私有暂存验证与同句柄DELETE也遵守普通文件身份核查。

停服私人备份新增upload-policies.json和uploads（session.json、part.bin/blob.bin、锁文件）并保留workspace/clients/management-operations及未决snapshots的一致副本。业务ZIP不含这些私人数据，不能移入静态资源或Git。根/授权/transport保留3/4/2；日志4新增upload_policy家族，eeeaf86因未知家族拒绝，降级只用匹配备份，不删日志绕过。

设置页“查看当前空间暂存状态”只读元数据；“恢复已接受暂存”在重新打开服务后根据sealed/真实磁盘恢复原ID，不重新读取来源或重传。也可由同client get_upload/complete_upload恢复原会话，空间关闭或权限失效不发布新ready。created可继续首次传输，receiving无完整sealed则failed；已记录evidence的已知半成品可在过期安全清理，超出最后证据的未知尾部需人工核查，保留预算。

“清理当前空间过期暂存”先全量预检固定目录/格式，跳过OS锁持有的在途和binding/consumption保护项。只删通过同句柄大小/hash证明的已知对象，实际关闭DELETE句柄并持久removed后才释放预算。长hash在目录配额锁外，物理rename/delete和预算状态在同一短锁，避免统计重复/缺失；断言materialized在0到used之间，不用截零掩盖竞态。清理失败/第三方对象/未知版本保留现场，不递归删私人目录，不修改正式附件。终结墓碑保留request幂等而不占活跃1000会话限制。外部进程耗盘仍会导致写失败，不能把预检余量说成文件系统原子空间预留。


### AG-132 附件事务维护

共同policy为私人schema2，新管理attachment_policy家族；旧schema1/休眠配置不自动升级成正式权。业务提案仍3，新执行attachment@1/schema2；旧b7ce3fe遇新处理器/管理家族拒绝，匹配备份恢复前停服解决未决，不删除日志/快照/part降级。正式附件新增兼容id/sha256字段，记录front matter与项目独立index仍原事实源；知识库无新增附件格式。

已确认意图先保存manifest prepared/copy pending，再在.agent/operations固定part中有界复制。此期间普通写/孤儿清理被write_guard阻止，读取/撤销/切换仍可进行；不要手动删除被引用源或把part当正式附件。服务启动（包括--disable-agent）和停服--agent-recovery-report使用匹配私人配置恢复已接受事务；Agent查询及本机批准action查询走专用锁外hash路径。缺少授权、未知/篡改或partial不足证据时保留现场，report/显式abandon表示接受现盘，不回滚或接管其他文件；被保护的残留需按证据人工核查，不能直接释放源预算。

同名相同字节也不代表本操作发布，须卷/文件身份和摘要证据一致；恢复不会覆盖外部占位。metadata仍before需重查权限/目标/类别；已经after才只补消费与原回执，历史证据仍必须存在。receipt持久后只查询原结果，不重放后来改删。正式时间在接受确认时固定，携时区/唯一history ID跨重启校验；不回填草稿日期。

维护按钮现在可立即退休正式提交已完整完成的源blob：先证明proposal、manifest、receipt及binding/消费映射/SHA大小匹配，再同一DELETE句柄校验删除并记removed，保留墓碑。删除后未记账的崩溃可在磁盘确实不存在且原回执匹配时完成记账；未知/第三方内容不删。在途或未完成消费不能以consumed标签跳过证据。业务ZIP包含正式附件与原索引/Markdown，排除私人授权/上传及.agent快照/part；灾难恢复仍须复制匹配私人状态，不能把旧源权限带入新空间。

本项浏览器专项node test_agent_attachment_workflows.js使用临时库，覆盖共同授权、两主题两宽度、完整批准、项目结果/下载和两个编辑器特殊文件名往返；普通URL标签格式/代码/引用随共享编辑器回归。100MiB专项在test_agent_attachments中验证有界内存和磁盘事实，不替代独立性能/视觉基线。

## AG-133文档附件维护

正式文件仍为documents/*.md及全局assets/images、assets/files；无attachments旧文档可直接读取，不批量迁移。普通上传仅在已验证Windows固定本机NTFS开启；接收前验证平台和目标路径，模拟不支持分支不代表非Windows原生验收。既有文档/编辑器读取不依赖新上传。单文件100MiB/64KiB块、1GiB未释放暂存、1000活跃、5秒空闲/60秒流截止、16MiB磁盘保留；同步OS调用和外部磁盘竞争仍有边界，不能声称多文件原子事务。

设置→附件清理中“查看文档上传操作”读取全部日志，含来自其他浏览器或localStorage丢失的操作及错误ID。恢复/回收先全目录格式、primitive、路径及快照/回执预检，未知停止全部恢复写并报告document_upload_recovery_required/503。receiving中断只失败封存，prepared/applying按固定计划恢复；第三方正文/名称/身份冲突保留现场。当前浏览器有待查询时先查询原UUID，doc/空间/base匹配才合并当前输入；不要重传生成第二份附件。

“回收终结上传暂存”对completed先保留稳定回执/UUID的精简墓碑，再校验SHA/同句柄删除before/after；已完成文件后的编辑/删除不重放。failed/无领域view的abandoned按创建设备/文件身份、原生版本、真实partial SHA验证后DELETE，实际删除完成才removed释放预算；删除后会计前崩溃可补完。历史墓碑不占1000活跃名额，但仍有O(历史操作数)的元数据预检/报告和日志增长成本。未知/替换/硬链接/重解析不删、不提前释放预算。

“放弃此操作”仅明确标记，不回滚已发布附件；仍含领域计划的放弃残留保持孤儿保护，需人工按现盘证据核查。folder已建而operation.json未写的空初始化可在报告中“放弃空初始化”，生成不可重用的DOC-0000占位墓碑；不是正式文档。若含binary.part/未知文件或损坏日志，不能用这个入口删文件或覆盖原证据；保留原目录，按报告UUID停服核查/恢复匹配证据后重启。禁止删除旧ID日志来重放请求。私人目录不得作为数据源或附件索引。

完整ZIP保留正式Markdown/全局assets，排除整个.workbench-document-uploads及原Agent证据子树，单个.md保持无二进制；选择文档ZIP用平铺MD+assets/<规范路径摘要>-<原名>，副本重写body/metadata引用、共享规范路径去重，不改源。解压到临时目录验证每份MD的实际资源字节；缺失/路径越界/硬链接/重解析/未支持本地HTML或定义式引用拒绝不完整包。目录迁移拒绝receiving/prepared/applying及尚未释放的failed/abandoned来源，先回收或人工核查，避免复制改变源身份而失去回收证明；已完成或已回收的终结日志可随本机目录相对搬迁维持原UUID回执。已终结源字节重新出现按未知503处理，不删、不继续接受新上传。

孤儿扫描只查受控assets roots，已覆盖文档、正文相对图片/附件、记录/项目、历史及回收站按原owner目录、在途Agent/web操作；任一共享有效引用保留。GET orphan-assets?report=1及清理结果显示脱敏警告；损坏/未知引用或链接对象保守不删全部候选。Markdown代码示例/未知本地语法可能保守阻止清理，先核查再处理，不以扫全盘或强制忽略未知来删。外部写入与扫描/删除之间的文件系统竞态不能用服务内锁宣称消除。

专项：python -m unittest test_document_attachments test_assets test_agent_attachments；node test_document_attachment_workflows.js及test_agent_attachment_workflows.js，另跑共享编辑器/设置/样式/HTTP/MCP门禁。前者验证无Agent普通上传、持续输入、关闭切换、刷新草稿/响应丢失/原ID查询、409及维护；后者含document共同授权/local_web正式提案。100MiB样本仅证明有界内存和真实字节，不替代独立性能/视觉基线或AG-142真实模型矩阵。

## AG-134 概念图保存冲突和历史维护

升级后请刷新旧页面：已有图PATCH和历史恢复要求expected_revision，旧缓存无签名请求409而不覆盖磁盘；Python旧调用仅保留服务内无版本兼容。概念图“处理版本冲突”保留当前画布和撤销栈：可先从更多操作导出原始JSON，再选择读取磁盘、继续编辑，或明确确认覆盖最新磁盘。读取磁盘后撤销可恢复本地内容且沿用新base，确认期间磁盘再次变化仍拒写。保存/冲突未解决时关闭/切页被阻止；刷新提示和草稿只是尽力保障，出现草稿写失败须先导出。

更多操作“查看历史”选择受控快照，恢复仍检查当前版本并保留恢复前图。`history/CMAP-ID/*.json`是原始字节快照，全部保留且无自动清理；需监测长期自动保存的磁盘增长，Markdown原最近30份策略不变。未知/损坏历史保留并标不可恢复，不通过手工删未知文件来强制恢复。未知未来图version禁止写回，先备份/使用支持该版本的软件核查，不能把version手工改2绕过。

历史保存后异常可能已留下快照；目标replace后响应丢失可能已完成，请GET当前图/历史比较revision后明确重试，不把错误解释为零落盘。本项无新持久日志/后台自动重放，读操作不会创建历史。分类批量改名/删除的逐图写入有历史，但配置与多图不是原子事务；中途报错后重读分类/各图，按实际剩余范围继续，勿宣称全量成功。回收图/恢复不删除历史，完整ZIP保留概念图及JSON历史；PNG和当前图JSON导出不包含传输revision。

验收使用临时数据：`python -m unittest test_concept_maps test_server test_http -q`，`node test_concept_map_workflows.js`（真实画布/冲突/草稿刷新/历史/迟到/导出及浅深桌面窄屏），另运行相关入口/样式/保存/Agent深链回归。全量运行期间冻结代码；大文件截止保持原5秒，资源竞争或其他失败必须按实测保留，不通过放宽超时掩盖。

## AG-135图授权/分配/恢复维护（已完成）

完整备份与迁移请保留config/concept-map-ids.json；不要为了恢复旧程序删除游标、图proposal、manifest、receipt或私人管理日志/快照。游标损坏、未来schema或任一占用来源未知会停止新分配（503），不能归零重试。缺文件只能从现有证据派生，无法鉴别首次升级与人为删除历史；部分恢复或删除元数据不保证无证据旧编号不复用。完整ZIP含游标而不含私人提案/批准/凭据，解压新空间不恢复旧Agent身份或继续旧批准；需重新接入授权。单项目/文档ZIP不承诺复制全库分配状态。旧并行程序忽略新游标的分配仍不受保证。

新图许可需管理员在“概念图授权”完整预览后明确批准，升root4/auth5/log5；旧dormant不生效。其它客户端编辑/轮换/文件或暂存策略操作必须保留最高格式下界与图字段；图授权变动会更新client_version，使暂存/正式附件共同policy需重新批准。管理批准丢响应先查operations原request，既有report/abandon负责未决私人快照，不能删除日志或手动回填权限。分类更名前先收窄，若后续图/配置写失败，保持已收窄状态，管理员重新核对再批准，不自动转移到未分类。

图执行继续用原提案恢复report/abandon入口：before/after.json、manifest execution_schema3、原始history及两个计划摘要交叉核查。prepared尚未发布必须匹配当前权限/资源；历史已落也不能绕过撤销继续写图。after和必要history已证明时只补原回执；缺失history、第三方字节或未知步骤/算法/版本保留原状人工核查。create applying但目标缺失不自动重建；明确接受磁盘状态后才能abandon，后续新建会用新编号。已完成回执查询不重放后来删改的图。禁止将跨文件步骤描述为原子事务，服务外文件系统最终检查/发布间竞态与非秘密摘要无法证明作者的边界保留。

管理只读画布不保存，失败或旧版本/会话不得批准。普通主画布与Agent竞争仍按134的409/草稿/撤销/明确选择再CAS；必要时先导出当前JSON。v2关系文字不会再在仅打开时自动拆边；v1/缺version保留原迁移，未知未来版本不能当旧版处理。图回收恢复遇稳定ID占用现在409保留两端，不自动改文件名；普通记录/文档/项目原冲突恢复策略不变。AG-135专项不代替142真实模型矩阵或独立性能基线。

## AG-136 删除维护（已完成）

管理员在客户端“删除授权”选择具体资源，完整预览全部当前成员/版本再批准。此许可不扩大读取、kind或图授权；旧上传/附件策略绑定旧client_version后失效，需重新批准。新格式registry5/auth6/log6不可通过删除日志或清空grants回退。当前只支持已验证Windows固定NTFS普通文件；硬链接、重解析、SUBST/特殊路径及无法完整读的对象不能执行。移入回收站与索引/回执不是多文件事务。

响应丢失先查询原request/proposal；设置与提案管理保留待查询标识，刷新后继续查询。未知格式/异物/移动中但原trash缺失时使用原report/abandon入口核查，不另建请求重删源，不从before快照复制重建。abandon不是撤销：已移动文件不会回滚，残留token仍保护，需人工按原证据核查。读回收站列表不会触发恢复/清理；保护项有文字提示且不能网页恢复、永久删除或批量操作。全局未决时普通写/分类/历史恢复/cleanup/孤儿清理均受保护；关闭Agent启动仍先恢复后清理。

附件、共享资源及历史保留，活动引用清单不包含历史/回收站的旧引用；孤儿报告遇未决/放弃残留保守保留。默认回收30天，但本机可提前永久删除。排序保留原ID/位置而不修改配置。完整活动集合和原索引均为保守依赖，无关成员变化也可能要求重新预览。每文件1MiB、活动集合4096文件/32MiB、完整JSON预览2MiB，超限需在本机核查而非截断。

迁移已完成删除需停止服务并完整复制数据目录及匹配私人凭据/日志，再以匹配版本启动；新Agent回收条目按受控相对源恢复，旧机器绝对路径仅保留原证据。实际完成态copytree恢复已验；复制未决操作会改变物理身份，不能声称可自动恢复。可移植ZIP排除.agent及.trash，不是删除事务/私人凭据备份。私人提案内容30天清理保留原回执与身份墓碑；旧提交不会删除已恢复对象。普通记录/文档原文件名冲突规则保留，图同ID仍409。

## AG-137 项目创建与范围恢复（已完成）

项目和可选范围授权分别以原提案/批准请求和管理操作编号查询。查看项目恢复报告时，project_state 与 sorting_state 分开：可信正式目录但外部排序变化时保留项目及第三方字节，不用新列表重算。发布前可恢复已验证的私人暂存；暂存中证据不明、发布中未证明正式原对象，不自动再发布。放弃接受当前盘态，不移除残留、不回滚正式项目或重建旧身份。人工核查前保留快照、原日志、配置和私人凭据，禁止删除日志以强行重试。

项目访问成功须来自同一原目录和当时版本的客户端。独立范围授权 prepared 且原项目/客户端证据一致时可恢复；发现冲突后进入既有 recovery_required，后续应按 report/abandon 维护，不自动补授权；放弃未决凭据操作沿用停用客户端的保守策略，项目创建原回执与文件仍保留。丢响应先查原操作。已覆盖范围不会产生新写入。完整目录复制后旧物理身份可能变化，已完成创建仍可查询原回执，但不能用副本直接证明新访问授权。目录与排序不构成多文件事务，外部编辑竞争窗口仍存在。

## AG-138 项目级联回收与恢复

发现未决操作时先查原提案、固定回收 token 和恢复报告。已记录 applying 而缺少原回收目录时，保留现状，禁止再移动仍在源路径或后来恢复的目录。回收目录原物理身份和完整树均匹配后，服务可续办原索引、缓存与回执，即使客户端授权已变化或同 ID 源路径重新出现。索引第三方变化或原树证据失配会停止。放弃表示接受盘态，残留证据继续受保护。

Windows 固定 NTFS 同卷目录句柄可验证原对象并执行不覆盖移动，外部进程仍可修改子文件。最终校验后、移动发生前的竞争可能留下已移动但无法证明的树。移动、索引和回执分阶段持久化。保留匹配的完整数据和私有配置、日志，再做停机迁移。已提交项在新卷可按完整相对名与文件内容核验并恢复原 ID。未决项仍要求原物理身份。使用可理解 registry7、授权8、日志8 和回收 schema2 的版本维护该工作空间。

### 分类恢复（AG-139）

已初始化空间的分类命令使用同一提案日志。原操作开始后先收窄，再发布分类、成员和原历史。重新核验成员集合、原历史、业务最终字节与客户端版本后，才补发等价的改名许可。发生响应丢失时查询原提案动作或在同一数据目录重试原本机票据。恢复检测到第三方状态时保留盘态与证据，放弃表示接受当前盘态。

停机完整迁移保留分类身份配对文件、`.agent` 和匹配的私人配置。可移植业务备份依旧排除私人计划与执行日志。普通全量兼容入口先收窄并更新身份，兼容入口或未初始化工作空间在多个文件之间中断时，可能需要按盘态人工核查。外部进程仍可在文件检查和原子替换之间写入。外部往返修改、旧程序绕过身份记录或同时移除两份身份文件时，服务无法识别所有代次变化。发布回归加跑 `node test_agent_category_workflows.js` 和 `python codex_agent_acceptance.py`。

### 工作流恢复（AG-140）

先查询原提案或重试同一张本机批准票据。服务核验匹配的私人授权、历史与当前业务文件，沿原计划处理可证明的中断；第三方内容、缺历史或未知版本时保留盘态。旧兼容 API 改变有效状态、记录或项目排序时需要当前完整计划和批准。旧工作流目录 PUT 接受原网页使用的 JSON 数组，其它对象路由保留原类型限制。

停机迁移保留配对身份文件、历史、`.agent` 与匹配的私人配置。未初始化空间的原字节计划无持久提案日志，多文件中断需要按实际盘态核查。历史和回收站不迁移，恢复过期历史状态须选有效状态或明确仅恢复其它内容。维护测试增加 `node test_agent_workflow_workflows.js` 与 `python codex_agent_acceptance.py`。

### 提案恢复报告（AG-141）

在本机同源管理会话进入“提案管理 → 查看恢复报告”。关闭 Agent 接入后，仍可读取已初始化空间的报告。网页只返回可验证的事务和提案 ID 及状态。遇到未知格式或损坏证据时，显示需核查，保留现场。报告读取不执行恢复、过期处理或清理。已放弃的状态表示本机操作员接受当前磁盘状态，可能仍有待核查的残留。

批准响应丢失时，用“查询提案操作结果”查询原批准。该入口沿用原事务的条件恢复及回执补写规则。确需进一步核查时，停服后使用 `--agent-recovery-report`，沿用该命令先尝试恢复再报告的行为。仅在确认接受当前磁盘状态后，使用 `--agent-recovery-abandon OPERATION_ID`。放弃不会回滚已完成的步骤。报告、原批准查询与停服维护各有独立入口。
