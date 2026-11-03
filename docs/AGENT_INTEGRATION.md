# 通用 Agent 接入

当前进度：提供本机认证、范围内查询、提案预览和确认提交 HTTP 接口。MCP 桥接与 Codex 联调仍在实施。阶段状态见 [AI_AGENT_PROGRESS.md](AI_AGENT_PROGRESS.md)，完整契约见 [AI_AGENT_PLAN.md](AI_AGENT_PLAN.md)。

## 运行和客户端授权

接入默认关闭，普通启动方式保持不变。显式启用：

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

第一个命令返回 client_id、workspace_id 和 config_file；令牌只写入 config_file，不打印到终端。默认权限仅 read，默认项目/分类范围均为空；`--agent-project <项目ID>`、`--agent-category <分类>` 可重复，`*` 表示该类全部内容。propose、commit 为后续写入流程的权限，授权这些范围本身不跳过预览确认。

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

本阶段不注册或修改用户 Codex 配置。MCP 适配及真实 Codex 测试在 AG-104 完成后补充具体命令。

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
