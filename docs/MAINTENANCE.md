# 维护与发布

## 修改入口

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

AG-121尚缺真实非Codex客户端，恢复入口与未运行矩阵见[客户端兼容矩阵](AGENT_CLIENT_COMPATIBILITY.md)。文档准备不等于互操作通过。

远程默认未提供实现；候选部署边界、威胁模型和恢复/停用验收见[AG-122设计准备](AGENT_REMOTE_DESIGN.md)。未经真实IdP/TLS/客户端验证不得标远程可用，不应直接公网化本机工作台。

显式隔离生命周期演练：python extension_lifecycle_acceptance.py，验证四类型两确认路径、关闭Agent普通读取、停服完整备份/批准回执恢复、便携ZIP CRC/接入排除/新身份。仅使用TemporaryDirectory，不启动模型或修改用户配置。[扩展验收](AI_AGENT_EXTENSION_ACCEPTANCE.md)区分本机通过与非Codex/远程未验证。

当前范围更新（2026-11-06）：AG-122～125按用户单机用途取消，原远程外部门槛不再阻塞本机交付；既有设计仅作历史参考。本机使用不需要TLS/IdP/代理，原loopback边界保持。
