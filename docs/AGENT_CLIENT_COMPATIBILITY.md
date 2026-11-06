# Agent 客户端兼容矩阵与隔离验收

核查日期：2026-11-06。工作项：AG-121。当前结论：**AG-121进行中；WorkBuddy附带CLI真实连接/12工具发现通过，完整读写互操作未验收**。用户已提供WorkBuddy安装并表示有测试账号/额度，可准备隔离会话。不能把连接通过写成完整兼容通过。

## 1. 已有证据和缺口

| 客户端 | 精确版本/传输 | 状态 | 证据与限制 |
| --- | --- | --- | --- |
| Codex CLI | 0.163.0-alpha.10.2 / stdio MCP 2025-11-25 | 已实测 | python codex_agent_acceptance.py；12工具、四类型、两确认路径、重启/撤销；无模型turn，不计为非Codex验收 |
| WorkBuddy桌面 | 5.1.5 / 拟接本机stdio | 第一轮未通过：工具未加载 | 用户详细报告未执行capabilities/list_projects/catalog；桥接未观察到initialize，写入/故障矩阵未运行 |
| WorkBuddy附带的原装CodeBuddy CLI | 2.103.3 / stdio MCP2025-11-25 | 连接与工具发现通过 | python workbuddy_agent_acceptance.py；真实initialize/initialized/tools/list、12工具、Connected；无模型turn，写入/故障矩阵未运行 |
| 远程 OAuth/Streamable HTTP 客户端 | 当前范围取消 | 未验证 | 用户仅单机使用；本机stdio结果不能外推 |

## 2. 真实连接证据与剩余条件

```powershell
python workbuddy_agent_acceptance.py
```

脚本默认从当前用户安装目录定位WorkBuddy附带CLI；自定义安装用--install-dir传目录。使用已有Node运行原装bin/codebuddy，不提取/改写客户端实现、不安装SDK。CLI先执行--version，再执行mcp list。临时透明中继逐字节转发工作台桥接协议，仅记录方法、协议/客户端版本、工具名称与错误码，不构造客户端请求。输出固定ag121_complete=false，避免被当作完整矩阵验收脚本。

2026-11-06实际结果：CLI2.103.3、退出0、Connected、MCP2025-11-25、initialize→notifications/initialized→tools/list、12工具、无协议错误、model_turns_started=0、real_user_config_changed=false。CLI initialize中的clientInfo.name=workbench_probe来自登记名称，不作为客户端厂商或身份认证依据。临时凭据在清理前撤销；Windows Job关闭回收本次客户端后代，临时目录清理失败会报错。

尚未核实公开无模型直接工具调用入口。原装CLI公开mcp子命令仅登记/移除/列表/详情；不能因其内部打包了MCP SDK就抽出SDK冒充真实客户端。用户已表示有可用于隔离测试的账号/额度；下一步准备独立会话并由用户完成认证，账号/令牌不能贴入聊天或复制正式配置。若需要模型行为测试，单独记录实际模型/消费边界和用户新确认，不能把程序夹具声明当成人类确认。

[官方WorkBuddy MCP指南](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/MCP-Guide)描述桌面用户级~/.workbuddy/mcp.json、项目级.workbuddy/mcp.json；本次附带CLI的安装文档则描述CODEBUDDY_CONFIG_DIR下.mcp.json。两者须区分，不能把CLI临时目录写入桌面正式配置。桌面入口会登记系统协议，登录回调的隔离仍需核实，尚未启动第二个桌面实例。

### 桌面一次性项目测试（需明确例外授权）

```powershell
python workbuddy_agent_acceptance.py --desktop-session
```

脚本只启动临时工作台、生成临时凭据和一次性项目，不启动桌面、不读取认证、不修改全局MCP配置、不调用模型。项目包含官方桌面路径.workbuddy/mcp.json和附带CLI项目路径.mcp.json的相同候选配置；是否实际发现需真实任务核实，不能将候选文件视为登记成功。输出temporary_workspace、workbench_url和stop_file，不输出令牌。

用户2026-11-06明确允许此次例外：在已有WorkBuddy桌面打开该临时项目，由用户手动最多8轮；桌面可能保留任务/最近项目记录，其他正式配置和登录资料不得读取或修改。不将该例外扩大到自动模型调用、正式数据或全局MCP登记。账号额度不等于独立CLI API Key。

第一轮只读capabilities/list_projects/四类型catalog，报告空间与授权，工具未加载直接报告，不修改全局配置。随后依下表逐项执行四类型三操作、两确认路径和故障；agent_attested需展示完整预览后等用户在客户端新消息确认，local_web需临时网页独立批准。每轮保留真实工具/持久化证据；8轮不足则如实记录，不超出用户允许的手动范围。

桌面第一轮实际未通过：用户详细报告工具未加载，连接器无已启用workbench_probe；临时服务仍可读，但桥接没有initialize。此前简短“已调用”答复由该详细报告纠正。本次资源count=0本身不能判断失败，因为工作台仅提供tools。候选项目文件存在不等于桌面已登记。已用1轮手动任务，最多剩余7轮。

下一候选是由用户在桌面连接器中仅新增并启用临时workbench_probe，完整新项在本任务TEMP下WORKBUDDY_MCP_REVIEW.json审查；只指向临时库和凭据，不含令牌正文、不替换其他条目，同名差异先停。**尚未获全局登记例外授权，未执行该操作**；不得把原项目测试授权扩大为全局配置修改。结束需撤销临时凭据并仅移除本次条目，保留任务历史例外的原边界。

曾尝试原装CLI --serve本机Web UI：HTTP健康检查通过，但用户确认没有登录/模型配置入口，安装内iam.md要求API Key或OAuth token。不能用桌面账号额度直接登录该空白UI；已停止并清理该临时会话，删除误导性的--session入口，不要求用户另办API Key。浏览器自动化被本次Work设置禁用，没有把HTTP检查记作UI通过。

停止：在输出stop_file位置创建空文件，或启动终端Ctrl+C；最多保留2小时。退出撤销测试凭据、关闭临时工作台并清理本次目录；若桌面仍持有项目目录，先由用户关闭该任务。认证/日志/配置不进Git，未完成会话不生成通过回执。

## 3. 隔离配置契约

工作台启动使用全新临时数据和私人凭据根，监听127.0.0.1及动态端口。客户端使用临时配置/缓存/工作目录；登记仅使用程序和args数组，不复制真实用户配置。显式授权四类型及测试项目/分类，并保留另一个不授权todo/info的旧凭据作为拒绝对照。

通用MCP登记对象（占位符必须换成临时实际路径，不能直接执行）：

```json
{
  "command": "<已核实的Python可执行文件>",
  "args": ["<仓库中的agent_bridge.py>", "--config", "<临时私人客户端配置.json>"]
}
```

配置是客户端配置数据，不是shell命令。不把令牌内联到args、页面、日志或提交。工具目录仍为12项，确认新客户端能刷新Schema；如需额外协议版本，先登记规范差异和测试再扩展。

## 4. 必跑矩阵（只完成连接与工具发现）

| 组 | 真实操作 | 必须保留的脱敏证据 | 当前结果 |
| --- | --- | --- | --- |
| 协议 | initialize/initialized、tools/list、UTF-8、ping、未知消息/字段、断连/重连 | 客户端/OS/协议版本、12工具目录、错误码、stdout仅协议 | 原装CLI握手/12工具通过；取消/重连/未知消息未运行 |
| 查询 | kinds范围交集、catalog四类型、分页、分段正文、引用越权 | 允许/拒绝对照、完整分段拼接等于磁盘正文 | 未运行 |
| create | issue/document/todo/info各新建 | 完整预览/警告/版本、规范字段、保存后重读与新仓储重载 | 未运行 |
| append | 四类型各追加 | 合成全文、todo/info只接受body，字段不隐式合并 | 未运行 |
| update | 四类型各更新/重排info_fields | revision校验、保留未开放元数据、清空/省略差别 | 未运行 |
| agent_attested | 展示当前完整预览，修改后旧确认拒绝、取消 | 真实工具往返；程序测试声明不能称为人类确认或模型遵规证明 | 未运行 |
| local_web | Agent自报确认拒绝，本机网页重新预览批准，再由客户端查询 | confirmation_required、同一版本/摘要/回执，无可兑换票据到客户端 | 未运行 |
| 幂等 | 相同request_id重试、不同输入拒绝、提交丢响应先查询 | 只有一份正式条目/历史，原回执不变 | 未运行 |
| 故障 | 撤销/轮换、服务重启、错空间、isError、限流 | 令牌失效生效、持久恢复、无秘密输出 | 未运行 |
| UI | 结果链接打开，记录/知识库保存重开与冲突 | 浅深主题/桌面窄屏、草稿不丢失 | 未运行 |

取消MCP请求不等于撤销已经持久提交的业务事务；需分别查询提案状态。已删除条目不能因重试重新创建。客户端升级后重新验收，不能沿用旧版本通过标签。

## 5. 证据记录和收尾

每组记录实际命令、精确版本、测试时间、退出码、关键返回字段和异常；原文仅取必要脱敏片段。秘密/完整配置不进Git，截图只留临时目录。测试完成撤销临时客户端，停止服务/客户端，核验隔离进程退出后清理本任务临时目录；保留失败/未运行事实。

完成门槛为矩阵全部要求具备真实证据，并更新[台账](AI_AGENT_PROGRESS.md)、[接入](AGENT_INTEGRATION.md)、[验收](AI_AGENT_ACCEPTANCE.md)。本文件已准备不代表AG-121完成。
