# 通用 Agent 接入

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

支持 capabilities、projects、catalog、search 和 items，精确字段见实施方案。catalog 返回现有文档分类和标签；传 project_id 才返回对应工作流状态。search 只返回授权范围内的问题与知识文档摘要；获取完整正文用 items，offset/length 按字符分段（默认最多 65536 字符），以 next_offset 判断是否完整。响应不返回磁盘绝对路径或本机配置。

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
