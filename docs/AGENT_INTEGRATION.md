# 通用 Agent 接入

规划提示（2026-11-09）：文件读取、附件上传、概念图、删除、项目创建及分类/工作流变更见 [本机能力扩展执行方案](AI_AGENT_LOCAL_CAPABILITIES_PLAN.md)。AG-128～136已完成，AG-137～143待开始且已暂停后续；下文当前接入命令、能力与限制不因此改变。

本文说明设置界面和备用 CLI 接入方式。AG-107～110 提供启停、授权管理、配置向导与分层诊断。设计见 [接入管理 UI 方案](AGENT_SETTINGS_PLAN.md)，实际状态见 [实施台账](AI_AGENT_PROGRESS.md)。

## 通过工作台设置接入

1. 正常启动工作台，在“设置 → AI Agent 接入”查看当前工作空间，点击“开启接入”。仅查看不会生成凭据。
2. 需要普通启动时保持开启，则勾选“下次普通启动时开启”并保存启动偏好；它与本次运行开关分开保存，显式 CLI 参数可覆盖当次状态。
3. 点击“添加客户端”，填写名称，选择只读或整理入库权限，勾选项目和知识库范围。默认不授权全部；“全部”明确包括未来新增内容。
4. 保存后进入向导，核对环境、服务地址和 MCP 登记名称，点击“检查并接入本机 Codex”。页面展示服务当前用户的目标配置路径、同名登记摘要及完整新登记。点击“确认接入”，在确认框选择“接入并检查”，无需打开终端。
5. 同名登记不同则改名重新检查，或勾选“替换同名登记”并明确确认；相同登记不会重复写入。完成后页面分别显示配置登记结果、原配置备份位置和自动连接自检结果。重启 Codex 或开启新聊天，再实际调用工作台 capabilities/项目/分类验证当前聊天。

目标为工作台服务环境的 `CODEX_HOME/config.toml`，未设置 CODEX_HOME 时为当前用户目录下 `.codex/config.toml`；若工作台与 Codex 运行在不同用户/环境，须先核对页面路径。一键接入只支持检测到的原生 Codex 可执行程序，不能输入任意路径或命令，不安装软件或启动模型 turn。

需要手工接入时，展开“高级：手工接入”，在“执行终端”选择 CMD 或 PowerShell，生成并复制命令到同种终端执行。Windows 默认 CMD；`C:\Users\…>` 通常为 CMD，`PS C:\Users\…>` 为 PowerShell，不要复制提示符。通用客户端可展开程序与参数。仅生成/复制命令不会改配置。

登记超时或响应丢失时先点击“查询上次接入结果”，不要再次接入。当前标签页使用 sessionStorage 仅保存工作空间对应的请求/客户端 ID，刷新后仍可查询，令牌不写入浏览器存储。服务重启后回执仍可读取；关闭标签页会失去该查询提示，可用结果中的请求编号按维护说明核查私人回执。查询不会重放配置写入。

写入仍按完整预览与用户新消息确认流程。界面不显示令牌；失败或版本冲突保留表单输入，重新读取授权后核对修改。网络结果不确定时先点“查询上次操作”，不重复新建。撤销不自动移除 Codex 登记；服务端口变化时使用对应客户端的“更新服务地址”，它不改 Codex 配置。

向导优先使用检测到的 Codex 绝对路径，不要求修改系统 PATH。服务 PATH 没有 Codex 时，Windows 会检查当前用户 LOCALAPPDATA 下桌面安装的 OpenAI/Codex/bin 版本目录；升级移动后重新打开向导生成命令。确实未检测到则显示提示，不把裸 codex 命令宣称为可用。CMD 路径含百分号/感叹号/双引号时拒绝生成可误解释的命令，请改选 PowerShell。

需要恢复凭据管理操作时见 [维护说明](MAINTENANCE.md)，不要删除私人管理日志或把它与业务提案日志混用。

### 检查连接

在有效客户端点击“检查连接”。后台分别验证服务、授权、配置、Python/桥接、Codex 环境、MCP 初始化与工具目录、capabilities 只读请求；上游失败会跳过依赖项，页面显示检查时间与修复建议。自检不创建提案或业务条目、不启动模型 turn，也不修改 Codex 配置。

“MCP 握手通过”只能证明本机桥接可用，仍需在新 Codex 聊天中实际调用验证。客户端列表分别显示最近普通请求与最近自检时间；普通请求来源未经独立验证，不能当成当前聊天在线标志。观察值和最近 50 份诊断仅保留于服务内存，重启后暂无记录。

诊断命令均由服务固定，Codex 版本检测最多 3 秒，桥接最多 8 秒，每个输出流最多 128 KiB；超时/超限会清理子进程。离开页面只停止查询，不取消已发出的只读检查；同一客户端同时只运行一个检查。找不到 Codex 时可继续检查通用 MCP 桥接并按向导手工配置。

提供本机认证、范围内查询、提案预览和确认提交 HTTP 接口，以及已通过真实 Codex 客户端验证的 stdio MCP 桥接。正式提交返回可直接打开和刷新的网页链接。阶段状态见 [AI_AGENT_PROGRESS.md](AI_AGENT_PROGRESS.md)，完整契约见 [AI_AGENT_PLAN.md](AI_AGENT_PLAN.md)，验证证据见 [AI_AGENT_ACCEPTANCE.md](AI_AGENT_ACCEPTANCE.md)。

## 运行和客户端授权

首次接入默认关闭。显式启用：

已有本机启动偏好时，普通启动读取该偏好；`--enable-agent` 显式开启，`--disable-agent` 显式关闭，均不改写保存的偏好。偏好损坏时默认关闭并保留证据。尚无偏好的旧安装继续默认关闭。

```powershell
python server.py --data-dir <数据目录> --enable-agent
```

使用独立临时库进行接入验收，不对真实库测试写入：

```powershell
$agentTestData = Join-Path $env:TEMP ("workbench-agent-" + [guid]::NewGuid())
$agentTestConfig = Join-Path $env:TEMP ("workbench-agent-config-" + [guid]::NewGuid())
python server.py --data-dir $agentTestData --agent-config-dir $agentTestConfig --agent-client-add "接入验收" --agent-scope read --agent-project "*" --agent-category "*" --port 4174
python server.py --data-dir $agentTestData --agent-config-dir $agentTestConfig --seed-demo --enable-agent --port 4174
```

第一个命令返回 client_id、workspace_id 和 config_file；令牌只写入 config_file，不打印到终端。默认权限仅 read，默认项目/分类范围均为空；`--agent-project <项目ID>`、`--agent-category <分类>` 可重复，`*` 表示该类全部内容。propose、commit 为写入流程的权限，授权这些范围本身不跳过预览确认。

凭据默认存放在操作系统用户配置目录下的 `Workbench/agent/<workspace_id>/`，Windows 使用 LOCALAPPDATA；POSIX 使用 XDG_CONFIG_HOME 或 ~/.config。可用 `--agent-config-dir` 显式指定外部目录，同一库的服务和管理命令必须一致。目录不能位于仓库或业务数据内。Windows 移除目录继承并授权当前用户，POSIX 使用目录 0700/文件 0600。clients.json 只保存摘要和权限；客户端配置保存明文令牌，按本机秘密保管。

管理可在服务运行时执行，不装配第二个业务仓储：

```powershell
python server.py --data-dir <同一目录> --agent-client-rotate <client_id>
python server.py --data-dir <同一目录> --agent-client-revoke <client_id>
```

轮换后旧令牌立即失效，客户端应重新读取配置；已撤销客户端不能靠轮换恢复，需要另建客户端。自定义凭据目录时附加同一个 --agent-config-dir。不要把令牌放到 URL、提示词、命令行参数或 Git 中。

## HTTP 读取契约

所有 `/api/agent/v1/*` 请求包含：

- `Authorization: Bearer <配置文件中的令牌>`。
- `X-Workbench-Workspace: <workspace_id>`。

支持 capabilities、projects、catalog、search 和 items，精确字段见实施方案。catalog 返回现有文档分类和标签；传 project_id 才返回对应工作流状态。search 按凭据 kinds 返回授权范围内的问题、知识文档、待办和结构化信息摘要，旧凭据缺省仅 issue/document；获取完整正文用 items，offset/length 按字符分段（默认最多 65536 字符），以 next_offset 判断是否完整。响应不返回磁盘绝对路径或本机配置。

分页默认 20，最大 100；limit/cursor 必须有效。未知参数和重复参数返回 400。每客户端每分钟最多 120 次已认证请求，超限返回可重试 429。

业务错误返回 code、message、retryable、details 和 request_id。401 检查令牌/撤销/轮换；403 检查权限；404 表示未启用、资源不存在或不可见；409 检查工作空间身份。不要在出错时回退调用无认证旧接口。

## 访问和备份边界

Agent 功能只允许本机 loopback。HTTP 会验证 Host 和 Origin，拒绝跨来源浏览器访问；Agent 令牌只能用于 Agent API。静态路由只提供 index.html 显式加载的资源，不提供源码、目录列表、业务文件、凭据或符号链接目标。

旧 UI API 为原有本地网页保留，不构成隔离同用户恶意进程的沙箱；拥有本机文件权限的程序仍有文件访问能力。接入权限保证只针对受控 Agent API，不能将 MCP 的工具清单宣传为操作系统权限隔离。

数据目录 `.agent/workspace.json` 保存工作空间身份，不保存令牌。迁移整个库保留身份并重新装配服务；切换到另一个库会更换身份，旧客户端需重新授权。可移植 ZIP 排除 `.agent` 与机器配置；恢复 ZIP 后建立新身份/客户端。

安装和验收不会自动修改用户的 Codex 配置；正式接入按下面步骤登记。

## Codex 和通用 MCP 客户端

先在网页建立所需项目和知识库分类（空库可能没有分类），再创建拥有 read/propose/commit 的客户端，并选择明确的项目和知识库分类范围：

```powershell
python server.py --data-dir <数据目录> --agent-client-add "Codex" --agent-scope read --agent-scope propose --agent-scope commit --agent-project <项目ID> --agent-category <分类>
```

保留返回的 config_file 路径；若服务指定了 --agent-config-dir，创建客户端时也指定同一目录。启动带 --enable-agent 的工作台后，在 Codex CLI 登记：

```powershell
codex mcp add workbench -- python "<仓库绝对路径>/agent_bridge.py" --config "<config_file 绝对路径>"
codex mcp list
```

路径含空格必须加引号；python 必须指向 Python 3.11+，必要时使用解释器绝对路径。桥接与仓库脚本位置相关，但启动工作目录可以不同。登记后在新 Codex 会话中检查 workbench 工具；已运行会话不保证自动加载新配置。更换项目范围通过客户端授权管理，不能在提示词里覆盖权限。

其他 MCP 客户端使用相同程序和参数数组：command 为 Python 解释器，args 为 agent_bridge.py 的绝对路径、--config 和配置文件绝对路径，不需要 Codex SDK、模型 API Key 或第二个 Repository。当前只声明并实现 MCP `2025-11-25` 握手协议的 tools 能力；不同版本客户端需接受版本协商，不宣称支持未实现的新协议。

提供 12 个工具：capabilities、list_projects、get_catalog、search、get_item、list_proposals、prepare_proposal、revise_proposal、preview_proposal、commit_proposal、get_proposal、cancel_proposal（均带 workbench_ 前缀）。完整规则见 [AGENT_USAGE.md](AGENT_USAGE.md)，可复制到其他客户端的项目指令。

桥接进程不启动工作台服务、不扫描聊天、不执行命令、不调用模型。标准输出只有 UTF-8 JSON-RPC，诊断写标准错误；配置每次请求重读，令牌轮换生效。HTTP 仅使用配置的 loopback origin（localhost 固定连接 127.0.0.1），不使用环境代理、不跟随重定向，默认超时 10 秒，响应上限 8 MiB。输入单消息最多 1 MiB。EOF、取消通知和断线都不撤销已经接受的提交，需要查询原提案状态。

停用时执行 `codex mcp remove workbench`，并撤销对应工作台客户端；移除配置不等于撤销令牌。工作台默认 Codex 权限设置与入库预览是不同层次，接入指引不会替用户关闭客户端审批设置。

开发验收命令：

```powershell
python -m unittest test_mcp_stdio -v
python codex_agent_acceptance.py
```

第二个命令使用真实 Codex App Server、独立临时配置目录、临时工作台和临时会话，通过其 MCP 工具调用接口执行完整流程，不启动模型 turn，不读取用户 Codex 登录资料或修改现有配置。它验证工具发现、两类新建、预览修改后确认、问题追加、文档更新、重试、取消、重启和撤销；确认声明使用测试夹具，不能当成独立人类认证。当前实测客户端为 codex-cli 0.163.0-alpha.10.2。

协议错误 -32002 表示尚未初始化，-32602 表示参数/顺序错误；工具业务失败通过 isError 和结构化错误体返回。服务离线返回可重试 service_unavailable，身份/响应无效返回 invalid_connection，均不回显令牌或原始异常。需要协议诊断时可在桥接进程环境显式设置 WORKBENCH_MCP_TRACE=1，只记录失败方法、参数字段名及错误码，不记录值。

依据：[Codex MCP 官方文档](https://learn.chatgpt.com/docs/extend/mcp)、[Codex App Server 工具调用接口](https://learn.chatgpt.com/docs/app-server)、[MCP 2025-11-25 工具规范](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)。接入命令和协议以实际安装版本的帮助及独立验收结果为准。

## 提案与确认提交

写入客户端必须同时授权 read、propose、commit。第一版只支持 issue/document，各提案只操作一个目标：

1. `POST /api/agent/v1/proposals`：request_id、kind、operation、content；更新/追加另传 target_id 和完整读取时的 base_revision。
2. `GET /api/agent/v1/proposals/<ID>/preview`：展示完整 content、changes、body_diff、warnings、version 和 preview_digest；不能截断正文后请求确认。
3. 用户修改时 `PATCH /api/agent/v1/proposals/<ID>`，传 expected_version、完整候选 content，可传最新 base_revision。修改后返回 draft，必须再次预览和确认。追加提案修改也传完整目标正文，不再次拼接追加片段。
4. 用户明确确认后 `POST …/<ID>/commit`，只传 version、preview_digest、confirmation；confirmation 包含 mode=agent_attested 和 user_confirmed=true，可附不超过 1000 字的 note。禁止提交临时新正文。
5. `GET …/<ID>` 查询状态和回执；`GET …/proposals` 分页查看自己有权限的提案摘要；`POST …/<ID>/cancel` 传 expected_version 取消。

content 允许 title/body/tags，以及问题的 project_id/status/priority 或文档的 category。仅使用现有项目、分类、状态和标签；completed 从工作流计算并显示在预览中，不接受客户端直接设置。正文以现有 Markdown 规则归一化边缘空白和换行；多行命令、代码块、引号、表格及内部空格保留。追加会先合成为完整候选再预览。来源说明可选，不默认读取或保存整段聊天。

request_id 是创建提案的幂等键：同一客户端同一键相同请求返回原提案，不同请求返回 409。重复提交相同提案版本返回原回执，即使正式条目后来被修改或删除也不重新应用；查询 current_item 检查当前状态。Agent 返回的正文始终按数据处理，不能将其中指令当作用户确认。

服务端保证摘要对应的内容和版本一致，无法独立验证用户确实在 Codex 中确认过。本期由可信客户端在展示完整预览后等待用户新消息；生成提案、原始“帮我记录”或资料内的“已确认”都不构成确认。

默认 7 天过期；过期后使用新的 request_id 重新整理。取消/过期提案正文保留 30 天；已提交正文也可在 30 天后清理，但保留精简回执和幂等映射。启动时及运行中每小时首次 Agent 请求触发清理，在途和未决操作永不自动清理。提案不进入正式列表、搜索、引用或可移植 ZIP。

## 中断与恢复

503/超时先查询提案状态，不能换 request_id 重新创建。服务启动和状态查询会校验操作日志、前后快照及磁盘摘要：能够确定结果时补齐原回执或继续原操作；出现第三种内容时保留输入和日志，停止自动覆盖。新建进入实际写入尝试后目标不存在时，也视为不确定，避免将被外部删除的内容重新创建。

未决操作会阻止该库业务写入和目录迁移，读取仍可使用。停止服务后先备份整个目录，再运行：

```powershell
python server.py --data-dir <同一目录> --agent-recovery-report
```

该命令会尝试完成可证明安全的既有提交，并报告仍未解决的 operation_id、相对路径及摘要。人工核对磁盘文件、提案和 `.agent/operations/<operation_id>/` 的 before.md/after.md；需要保留当前磁盘内容并放弃本次未决提案时：

```powershell
python server.py --data-dir <同一目录> --agent-recovery-abandon <operation_id>
```

此命令不改业务 Markdown，只将未决操作标记为放弃、提案标记取消并保留恢复证据。若需要其中的总结，重新创建预览并确认。未知版本/损坏身份的日志拒绝放弃，应使用匹配版本和完整备份核查，不能直接删除日志强行启用写入。恢复命令未暴露给 Agent 工具。

所有覆盖继续使用原子文件替换和写前历史；事务恢复经过进程中断测试，底层文件系统落盘保证与日常备份仍是恢复边界。外部编辑器不服从服务锁，校验与替换间的跨程序竞态仍然存在。

### 类型授权（AG-116）

创建客户端可重复指定 `--agent-kind issue --agent-kind document`；省略时只授权 issue/document，项目通配不包含新类型权限。网页创建/编辑可明确选择四类；AG-117 起 todo 已可用，info 已于 AG-118 开放。先读取 capabilities 的 kinds、authorized_kinds、kind_operations、kind_fields，不能把已授权推断为已实现。旧凭据无需迁移；轮换保留类型。

### AG-117 待办

授权需显式包含 todo（管理页选择或创建 CLI --agent-kind todo），旧凭据不自动获得。capabilities 已列出 todo 三操作；catalog 传 kind=todo 和 project_id 取得工作流。到期日可省略或设 null；新增/变更必须有效 YYYY-MM-DD。待办追加仅传非空 body。

### AG-118 结构化信息

显式 kinds 包含 info 才可访问；旧凭据不扩权。info 无工作流状态，catalog(kind=info,project_id=...) 不返回 statuses/priorities。通过 capabilities 查看字段和字节限额。完整读取含 info_fields，按服务器返回的有序列表预览；新增/重排/删除字段必须重新确认。INFO 深链接进入原信息抽屉。

### AG-119 本机审查入口

AI Agent 接入页的“提案管理”可查看当前空间所有客户端提案，Agent 工具仍只能访问自己的授权提案。每页20项、最多100项服务端限制；支持客户端/类型/状态/操作筛选。详情含字段、正文、差异、警告、版本、来源；正文清理后明确提示，不能用回执代替完整预览。网页批准已于AG-120开放，需local_web提案和当前完整预览。

### AG-120 网页独立批准

管理客户端最低确认方式可选本机网页；旧配置不变。CLI新建可用 --agent-confirmation-mode local_web。Agent prepare_proposal 可请求confirmation_mode=local_web，不能降低客户端最低策略。此类提案的MCP commit返回confirmation_required，需要本机提案管理完整预览后批准。网页操作者仅代表持有本机会话，不宣称现实身份认证。

WorkBuddy桌面5.9.3(d4692421)已在临时库实测四类型三操作、两确认路径、权限拒绝、幂等取消、提交丢响应查询、服务重启、轮换/撤销、错空间及限流。附带原装CLI2.165.0的连接/显式协议探针结果单列；旧5.1.5/2.103.3证据保留历史标签。精确范围及限制见[客户端兼容矩阵](AGENT_CLIENT_COMPATIBILITY.md)，不将Codex或CLI结果代替桌面证据。

远程接入仍未实现，不能代理原4173端口作为远程MCP。[远程设计与外部门槛](AGENT_REMOTE_DESIGN.md)记录候选方案和待提供的真实环境。

当前用途更新（2026-11-06）：用户只需单机本地接入，远程AG-122～125已取消当前实施；无需为本机使用准备IdP、TLS或代理。本机Codex和独立网页批准已实测，其他本机客户端仍须另行真实验证。

### WorkBuddy本机兼容验收（AG-121已完成）

当前核实桌面5.9.3(d4692421)、随附原装CLI2.165.0、stdio MCP2025-11-25。python workbuddy_agent_acceptance.py使用临时环境执行真实mcp list，只证明连接与12工具发现；追加--protocol-faults显式注入固定服务端ping/未知方法，仅观察真实客户端回复，不替代客户端或发起模型。lite-only安装由原装bin的固定CODEBUDDY_FORCE_LITE_WB_BUNDLE=1选择lite-wb，完整安装保持默认入口，无SDK提取或厂商文件修改。桌面矩阵另由用户手动真实任务验证；单次结果不保证任意模型遵规，也不构成现实身份认证。

python workbuddy_agent_acceptance.py --desktop-session只准备临时项目与工作台，不启动桌面或模型；使用已有桌面的任务历史与仅本次临时连接器例外已获用户明确许可，手动额度及实际轮次以台账为准，不读取正式认证、不自动调用模型。桌面与随附CLI配置路径不同，项目候选文件不等于桌面登记成功；本次实际通过用户手工登记临时连接器完成连接。完整步骤、清理责任与剩余矩阵见[客户端兼容验收](AGENT_CLIENT_COMPATIBILITY.md)。


### AG-128 休眠能力配置

接入管理可添加后续能力、明确操作及资源，加入休眠配置后完整确认再保存。页面标为“已配置、尚未实现、不可使用”，未来首次启用必须重新授权。没有旧业务权限时仅capabilities/必要诊断可用，不会因连接成功具备文件或业务访问权。具体文件授权待AG-130，当前不能配置files.read。

备用CLI创建独立客户端：`--agent-no-legacy-kinds --agent-grants-json '<严格JSON>'`；此参数接收JSON正文，不接收文件路径。示例JSON：

```json
{"schema_version":1,"grants":[{"capability":"projects.create","operations":["create"],"resources":[{"type":"workspace"}],"minimum_confirmation_mode":"local_web"}]}
```

仍需原`--agent-client-add`、隔离或目标空间的data-dir和一致agent-config-dir；旧kinds/project/category默认不被补为通配。此配置只保存休眠意向，不创建项目。管理API沿用clients POST/PATCH，可选capability_grants；edit省略保留、显式空清空。首次新格式保存会建立root2/log3门槛，旧版本拒绝管理；降级前见维护步骤。

capabilities新增capability_authorization.configured/implemented/effective/activation。configured不能当可用权限；AG-128阶段新增能力implemented/effective均空。新授权schema3/4的catalog标签只来自可见条目，有权空项目可查工作流但标签为空；legacy catalog兼容行为不变。该阶段未增加工具，AG-130文件工具见下文。


### AG-129 新提案保存计划

新建提案使用schema3；旧schema1/2继续按原算法读取和确认，不自动重算已预览摘要。capabilities新增execution_schema_versions=[1]、proposal_schema_versions包含3，AG-129阶段保持12工具及四类型三操作。完整预览包含authorization_revision、dependencies、execution_plan、plan_digest；客户端须展示全部依据，授权或相关依赖变化后修订并重新预览确认。

现有四类业务的旧凭据可直接生成新3提案，不要求配置休眠grants。新计划当前仅历史快照与Markdown保存，新增文件/附件/图/删除/项目及配置操作仍未开放。引用只绑定固定ID及revision，状态集合成员增删也会冲突；项目说明/排序、无关资源和标签颜色不引起冲突。提交仍只接受版本和预览摘要，不接受替换正文或执行计划。

网页完整预览增加保存范围与执行版本依据，批准action3绑定逻辑计划及授权/依赖；已批准但未形成manifest时查询not_applied，不自动发起新提交。遇commit_interrupted先查询原proposal；未知格式或recovery_required按维护入口核查，不能删除日志或换request_id重建。

### AG-130 文件工具与管理

固定工具目录增至15项，新增workbench_list_file_grants、workbench_get_file_info、workbench_read_file，对应GET /api/agent/v1/files、files/{file_id}、files/{file_id}/content。只接受UUID file_id，read必须有source_revision，可带原始字节offset/length（8～65536）；未知/重复query为400，缺失授权404，源变化409，不返回父路径。HTTP/MCP共享服务，不直接读取业务库外路径。

文件批准只能在同源本机管理会话clients/{client_id}/files/{preview|confirm}执行，Agent凭据不能调用；confirm不接受path，仅当前票据/摘要、expected_version、稳定request_id、approved=true。管理GET files与DELETE files/{file_id}用于查看/撤销，具体完整契约见DATA_FORMAT。文件专用创建使用file_access_only=true及空旧类型/范围；已有客户端的文件ID由服务端批准流程维护，不允许通用编辑自报active_file_ids。

capabilities区分Windows实现、当前具体授权与用途操作；configured休眠列表仍不生效。file_access明示大小/期限/分段上限、每段全文件校验、5秒块间截止及撤销许可边界。传输配置仍schema2，新授权4/根3/日志4建立旧版拒绝门槛；支持范围和管理员操作见AGENT_USAGE。原12工具和四类型三操作保留，此次原始MCP实测不代替AG-142真实模型客户端新增业务矩阵。

### AG-131 暂存控制与原始流

固定MCP19项，新增create_upload/get_upload/complete_upload/cancel_upload，仍保留原15项；只控制私人暂存，不正式入库。create_upload接受稳定request_id、policy_id、source、owner_kind/id、filename、bytes、sha256；source为{mode:stream}或{mode:file,file_id,source_revision}，无路径/URL/base64。get允许查询同client原收据，ready不等于当前可消费，须看available_for_binding。file模式由complete在服务内同遍复制/hash，普通stdio无需也不得自行读文件或提供原始流。

具备独立HTTP认证能力的客户端可POST /api/agent/v1/uploads建会话，PUT uploads/{id}/content传application/octet-stream，再POST complete（空JSON），GET同ID查询，POST cancel（空JSON）终结。PUT必须Bearer与X-Workbench-Workspace，不仅凭ID；正确单一Content-Length、无TE/重复header/query，仅loopback与正确Host/Origin。缺失/重复/非法长度400/411，超限413，短读/摘要409，idle/total超时408。每块64KiB、idle5s/total60s逐读收紧；错误或PUT完成均关闭连接。已缓冲超额拒绝，之后迟到多余字节由强制关闭丢弃，不作下一请求。

传输在途cancel返回upload_busy，未即时停止；客户端停止连接后查询/取消，或管理员撤销policy阻止发布ready。已接受取消不复活，不重传原会话；失败先查原upload_id。MCP不要求所有客户端具备HTTP字节能力，未实测客户端不宣称支持原始流；原始HTTP和stdio文件来源分别验收，仍不替代AG-142真实模型客户端矩阵。

同源管理clients/{client_id}/upload-policy GET/DELETE、preview/confirm POST；确认仅票据/摘要/CAS和approved，不接替换policy。uploads/maintenance GET只读报告，POST {workspace_id,cleanup:false|true}恢复/安全过期清理，管理凭据不可作上传凭据，Agent不可调用管理路由。新capability uploads.stage及upload_staging明示有效policy/来源/配额，formal_attachment_write=false。


### AG-132 正式附件工具与提案

固定MCP目录20项，新增workbench_get_attachment_target（GET attachment-targets/{owner_kind}/{owner_id}），只对当前共同附件许可的具体既有project/issue/todo/info返回revision、附件元数据及已有分类，不提供Agent二进制下载、路径、替换或删除。原prepare/revise/preview/commit/get/cancel_proposal增量支持attachment/create；旧四类型三操作不变。

先由本机管理在上传暂存面板勾选共同attachments.write/create并完整批准，再以同policy建立新ready暂存；随后get_attachment_target取最新revision。prepare外层target_id=owner_id、base_revision必填，content严格{owner_kind,owner_id,upload_id,display_name,category,insert_link}；project的insert_link=false，分类仅已有或空。MCP schema可列两类content字段，服务端按kind拒绝混合/未知字段；正文/路径/元数据不能由Agent自报替换。返回固定最终名称、ID、真实size/SHA/MIME、来源、完整before/after与正文差异；二进制未解析，不能声称看过内容。

完整预览后按最严格的client/共同policy/request确认策略提交。local_web不能自报，需本机完整预览票据和持久action；Agent提交只引用version/digest/确认，不接受临时内容。一次upload仅一有效提案；修订/取消/过期在无执行日志时同步解绑。失败查询原proposal/原网页action，不能换ID重建。copy意图是已接受事务，部分写入可能需恢复或人工核查，不是多文件原子事务。

receipt含owner_kind/id、固定asset ID、upload_id、64hex消费映射、真实受理时间、metadata revision与计划摘要；原响应丢失或后来正式改删仍返回原回执，current_item单列当前状态。记录结果用原条目链接；项目结果为/?item=project&itemId=<encoded ID>&assetId=ASSET-<32hex>，打开附件页并聚焦，不自动下载或执行。21项Node与原始MCP证据见验收，真实模型新功能矩阵仍留AG-142。

旧转换为todo但仍保留ISSUE ID的记录沿用既有receipt.web_path=null契约；可在项目/记录UI查看附件，不重编ID或扩大旧深链语法。

### AG-133 document附件契约

AG-133阶段工具数仍20，附件owner_kind白名单新增document；没有新增原始二进制下载、任意路径或HTTP代理工具。只对重新共同批准具体document且仍有原分类业务范围的客户端生效；旧schema2的其它owner和旧null许可不变，休眠grant不激活。content保持六字段，category为文档当前原分类，target_id/base_revision绑定原MD，project_id=null，access_target={type:document,category:原分类}。返回附件元数据/正文差异必须完整展示，不能根据路径推断已发布或已检查二进制。

Agent仍复用attachment@1/执行schema2及原uploads绑定/消费/回执恢复，分类变更和客户端revision在最终metadata前重验。普通网页上传和维护API属于浏览器业务操作，不加入MCP；Agent Authorization访问这些普通路由403。普通浏览器使用稳定UUID和独立日志，不声明Agent确认，也不绕过Agent提案批准。

### AG-135图契约（已完成，验收见台账）

工具目录从20增至22：workbench_list_concept_maps（query/project_id/category/分页）与workbench_get_concept_map（map_id=CMAP-数字）只读；现有prepare/revise/preview/commit/get/cancel扩展concept_map的完整create/update，不另建写入工具。HTTP GET /api/agent/v1/concept-maps及/<ID>对应只读；图写入仅经既有proposals路由。新图schema3/sha256-json-v3保持，静态concept_map@1、manifest外层3/execution_schema3及history_snapshot/json_write；旧Markdown/attachment版本语义不变。capabilities如实列执行1/2/3、授权1～5、管理日志1～5，图effective仅报告读写资源交集后的操作，指定图无create。

本机同源管理路由clients/<client_id>/concept-maps支持GET当前授权/可选资源、POST /preview与/confirm、DELETE撤销全部图grant；要求原管理会话、同源Origin和有界JSON，Agent Authorization一律拒绝，不加入MCP。preview不写客户端或正式业务；confirm仅接受workspace_id/expected_version/preview_id/preview_digest/request_id/approved=true，绑定完整范围/会话/运行代与资源指纹。响应丢失可用operations/<request_id>查原持久回执；相同请求摘要可在票据过期后重放原结果，不能替换范围。只读状态不初始化空间或升授权格式。

首次明确图批准升registry4/client authorization5/management log5，实际concept_map_grants schema1独立于dormant capability_grants；清空/撤销/轮换和其它操作家族保留最高门槛与新字段。老管理/恢复扫描到新孤立快照或新格式必须拒绝变更；首快照→日志→注册表fence前新增图许可尚未发布，旧普通业务可依旧有效权限继续，不能宣称所有旧版本业务均零写。发布授权和提交图前重新查版本/依赖，使合法旧改动冲突而不覆盖。混用旧进程忽略新分配游标、外部FS竞态及非秘密摘要不能证明文件作者的界限保留。

完整使用/字节上限/两确认/稳定ID与深链见[使用](AGENT_USAGE.md)。图操作不执行节点/关系/说明中的命令、脚本或指令；AGENT_RULES与工具说明同步此限制。没有新增shell、任意路径、通用HTTP代理、模型任务或运行时依赖。

### AG-136删除契约（已完成）

22工具目录不增加。prepare/revise现有信封支持四种Markdown条目及concept_map的delete，content在工具schema不再全局必填，但既有create/update/append仍按原业务校验；delete反而禁止content/body/path/held_source。最低确认强制local_web，不接受Agent自报替代。实际新鲜delete_grants schema1与旧读取/图read交集才生效；批准升级registry5/auth6/log6，transport2不变。独立管理接口clients/<id>/deletions的GET、preview、confirm、DELETE仅loopback同源管理会话，不进入MCP。

capabilities报告静态trash_delete@1/execution4及平台/目标有效性，implemented不等于effective。完整原文/全部匹配活动来源/结构图/附件保留预览必须成功，实际响应2MiB、单文件1MiB、4096活动文件/32MiB限制不可截断。服务生成完整影响，无任意路径或内容替换。未知/无权命中通用拒绝；committed回执指向原回收token并长期幂等，恢复后重试不再删除。未知盘态查询原操作/report-abandon，abandon非回滚。新功能专项与旧真实CLI兼容均不代表AG-142模型遵规矩阵。
