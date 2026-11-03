# 通用 Agent 接入

当前进度：AG-102 提供本机认证和只读 HTTP 接口。提案提交与 MCP 桥接仍在实施，不能用下文只读接口直接创建正式内容。阶段状态见 [AI_AGENT_PROGRESS.md](AI_AGENT_PROGRESS.md)，完整契约见 [AI_AGENT_PLAN.md](AI_AGENT_PLAN.md)。

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
