# Agent 客户端兼容矩阵与隔离验收

核查日期：2026-11-07。工作项：AG-121。当前结论：**AG-121进行中；WorkBuddy桌面四类型三操作、两确认路径及查询/幂等/取消子集已有真实证据，完整协议和故障矩阵尚未收口**。原装CLI连接与显式协议探针通过，不能外推桌面。逐轮历史和确认缺口保留在下文。

## 1. 已有证据和缺口

| 客户端 | 精确版本/传输 | 状态 | 证据与限制 |
| --- | --- | --- | --- |
| Codex CLI | 0.163.0-alpha.10.2 / stdio MCP 2025-11-25 | 已实测 | python codex_agent_acceptance.py；12工具、四类型、两确认路径、重启/撤销；无模型turn，不计为非Codex验收 |
| WorkBuddy桌面 | 5.1.5 / stdio MCP2025-11-25 | 四类型三操作、两确认路径及查询/幂等/取消子集已实测 | 16份历史回执与正式文件重读一致；四类型update有完整展示/新消息确认，local_web有独立网页批准。较早轮次确认未独立核实；协议、认证、重启/丢响应等仍待完成 |
| WorkBuddy附带的原装CodeBuddy CLI | 2.103.3 / stdio MCP2025-11-25 | 连接与工具发现通过 | python workbuddy_agent_acceptance.py；真实initialize/initialized/tools/list、12工具、Connected；无模型turn，写入/故障矩阵未运行 |
| WorkBuddy桌面 | 5.9.3 (d4692421) / stdio MCP2025-11-25 | 显式协议探针及issue追加丢响应查询通过，矩阵进行中 | 用户关于页核实版本；第6～7轮真实预览/提交/查询与17份回执一致，未沿用5.1.5全部结果为新版通过 |
| 当前附带原装CLI | 2.165.0 / lite-wb / stdio MCP2025-11-25 | 默认连接及显式探针通过 | 原装启动器固定lite开关，12工具、退出0、无模型turn；旧默认入口缺少产物失败已保留 |
| 远程 OAuth/Streamable HTTP 客户端 | 当前范围取消 | 未验证 | 用户仅单机使用；本机stdio结果不能外推 |

## 2. 真实连接证据与剩余条件

```powershell
python workbuddy_agent_acceptance.py
```

脚本默认从当前用户安装目录定位WorkBuddy附带CLI；自定义安装用--install-dir传目录。使用已有Node运行原装bin/codebuddy，不提取/改写客户端实现、不安装SDK。CLI先执行--version，再执行mcp list。临时透明中继逐字节转发工作台桥接协议，仅记录方法、协议/客户端版本、工具名称、JSON-RPC错误码与工具结果的tool_is_error布尔，不构造客户端请求。请求ID仅在内存关联响应（最多256项），不落盘ID、参数、正文或结构化业务结果；取消通知新增cancelled_request_pending及匹配时的cancelled_tool，不记录reason，仍保留关联以观察迟到响应，不把通知当业务撤销；异常isError类型单独记tool_result_malformed，不当作成功。旧记录没有tool_is_error时不补推结果；当前已启动的旧中继需正常重连才会加载补强代码。输出固定ag121_complete=false，避免被当作完整矩阵验收脚本。

2026-11-06实际结果：CLI2.103.3、退出0、Connected、MCP2025-11-25、initialize→notifications/initialized→tools/list、12工具、无协议错误、model_turns_started=0、real_user_config_changed=false。CLI initialize中的clientInfo.name=workbench_probe来自登记名称，不作为客户端厂商或身份认证依据。临时凭据在清理前撤销；Windows Job关闭回收本次客户端后代，临时目录清理失败会报错。

### 显式协议故障模式

```powershell
python workbuddy_agent_acceptance.py --protocol-faults
```

默认中继不注入消息；仅显式模式在initialized之后发送固定服务端ping及workbench/probe_unknown_method请求，并单独标注fixture_request/fixture_reply。只消费这两条合成服务端请求的客户端回复，其余消息仍逐字节转发；不构造客户端调用或业务响应。工具目录响应最多等待2秒供客户端回复，进程整体超时和回收规则不变。探针期待ping空结果、未知方法-32601，依据[MCP2025-11-25 ping规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping)及[JSON-RPC错误定义](https://www.jsonrpc.org/specification)。合成消息不能描述为工作台业务服务实际发起的请求。

2026-11-06原装CLI2.103.3显式模式实际通过：两项fixture_reply均valid=true，未知方法-32601、ping空结果、连接/12工具及退出0，无模型turn或正式配置修改。默认模式重跑通过且fixture_replies为空。新增2项专项验证仅消费探针自身回复、异常回复不算成功、不记录业务内容；此前3项元数据安全检查保留。CLI结果不外推桌面；桌面须在仅此临时连接器的已展示完整项中给--relay追加--protocol-faults并手工重连，再读取实际回复，不自动修改用户配置。

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

下一候选是由用户在桌面连接器中仅新增并启用临时workbench_probe，完整新项在本任务TEMP下WORKBUDDY_MCP_REVIEW.json审查；只指向临时库和凭据，不含令牌正文、不替换其他条目，同名差异先停。用户随后明确允许新增该临时连接器，已给出仅合并新条目和同名差异保留的操作步骤；授权当时登记/连接仍待实际证据，后续实际结果见下文。该授权仅限所展示的临时项，不扩展为读取认证、覆盖其他配置或自动模型调用。结束需撤销临时凭据并仅移除本次条目，保留任务历史例外的原边界。

曾尝试原装CLI --serve本机Web UI：HTTP健康检查通过，但用户确认没有登录/模型配置入口，安装内iam.md要求API Key或OAuth token。不能用桌面账号额度直接登录该空白UI；已停止并清理该临时会话，删除误导性的--session入口，不要求用户另办API Key。浏览器自动化被本次Work设置禁用，没有把HTTP检查记作UI通过。

停止：在输出stop_file位置创建空文件，或启动终端Ctrl+C；最多保留2小时。退出撤销测试凭据、关闭临时工作台并清理本次目录；若桌面仍持有项目目录，先由用户关闭该任务。认证/日志/配置不进Git，未完成会话不生成通过回执。

## 3. 隔离配置契约

桌面后续实际证据：用户报告连接成功并已开始发送任务；透明中继观察到clientInfo.name=connector:custom-mcp:workbench_probe、version=1.0.0、initialize/initialized、12工具目录及ping响应。一次快照共53次tools/call：capabilities×5、list_projects×5、get_catalog×12、search×13、prepare×6、preview×4、commit×4、get_item×2、list_proposals×1、get_proposal×1；另有一次notifications/cancelled。工具名元数据不含参数/业务响应，不能独立证明四类型目录、错误处理或取消语义通过。

临时磁盘复核4份提案均为create、version=previewed_version=1、agent_attested、committed，有对应持久回执及正式Markdown：ISSUE-0001、TODO-0001、INFO-0001、INFO-0002；无知识库文件。未记录到JSON-RPC error_code，但中继没有记录工具isError，不能据此宣称所有调用成功。没有读取真实客户端任务历史或认证；完整预览是否向用户展示、提交前是否有后续新消息确认、实际任务轮数待用户反馈。agent_attested回执本身不证明人类确认。尚未安排额外模型任务。

工作台启动使用全新临时数据和私人凭据根，监听127.0.0.1及动态端口。客户端使用临时配置/缓存/工作目录；登记仅使用程序和args数组，不复制真实用户配置。显式授权四类型及测试项目/分类，并保留另一个不授权todo/info的旧凭据作为拒绝对照。

通用MCP登记对象（占位符必须换成临时实际路径，不能直接执行）：

```json
{
  "command": "<已核实的Python可执行文件>",
  "args": ["<仓库中的agent_bridge.py>", "--config", "<临时私人客户端配置.json>"]
}
```

配置是客户端配置数据，不是shell命令。不把令牌内联到args、页面、日志或提交。工具目录仍为12项，确认新客户端能刷新Schema；如需额外协议版本，先登记规范差异和测试再扩展。

## 4. 必跑矩阵（已完成部分真实读写）

| 组 | 真实操作 | 必须保留的脱敏证据 | 当前结果 |
| --- | --- | --- | --- |
| 协议 | initialize/initialized、tools/list、UTF-8、ping、未知消息/字段、断连/重连 | 客户端/OS/协议版本、12工具目录、错误码、stdout仅协议 | 原装CLI/桌面握手12工具及桌面重连真实请求通过；一次取消通知不等于取消语义通过，原装CLI与5.9.3桌面显式ping/未知方法均通过；曾提前tools/list获-32002后初始化重试成功，实际请求取消仍待验 |
| 查询 | kinds范围交集、catalog四类型、分页、分段正文、引用越权 | 允许/拒绝对照、完整分段拼接等于磁盘正文 | 四类型catalog、授权范围、两页无重复、6段707字符拼接逐字等于磁盘通过；越权读取not_found/引用invalid_reference通过，5.9.3旧授权缺kinds时仅issue/document，info/todo搜索空/读取not_found、issue允许对照通过，原四类型恢复；恢复后info/todo读取待复核 |
| create | issue/document/todo/info各新建 | 完整预览/警告/版本、规范字段、保存后重读与新仓储重载 | 四类型真实新建落盘/正文字段及回执哈希重读通过；完整确认过程仍待补证 |
| append | 四类型各追加 | 合成全文、todo/info只接受body，字段不隐式合并 | 四类型追加/正文/字段/回执SHA256通过，document由网页批准落盘；info附加status被unknown_field拒绝 |
| update | 四类型各更新/重排info_fields | revision校验、保留未开放元数据、清空/省略差别 | 四类型update及info字段反转落盘通过；取消候选省略字段保留6项、显式空列表变0项已核对，空字段候选未正式提交 |
| agent_attested | 展示当前完整预览，修改后旧确认拒绝、取消 | 真实工具往返；程序测试声明不能称为人类确认或模型遵规证明 | 四类型update具备完整展示/指定新用户消息/提交证据；取消候选修订后旧版version_conflict、取消后invalid_state通过，较早轮次确认缺口保留 |
| local_web | Agent自报确认拒绝，本机网页重新预览批准，再由客户端查询 | confirmation_required、同一版本/摘要/回执，无可兑换票据到客户端 | 四类型自报拒绝→用户网页批准→真实客户端查询/重放原回执通过，批准日志/版本/摘要/正式文件一致 |
| 幂等 | 相同request_id重试、不同输入拒绝、提交丢响应先查询 | 只有一份正式条目/历史，原回执不变 | 四份提交重放原回执；prepare原样同提案、不同body为idempotency_conflict，旧版/取消拒绝通过；5.9.3唯一提交成功响应截断→先查原提案/正式问题→重启后重放原回执通过 |
| 故障 | 撤销/轮换、服务重启、错空间、isError、限流 | 令牌失效生效、持久恢复、无秘密输出 | 真实业务拒绝已记录isError；5.9.3实际服务重启后原回执重放不变，轮换旧令牌401/新令牌恢复、错空间头409、真实限流429/重启恢复均通过；撤销仍待运行，合成条件见下文 |
| UI | 结果链接打开，记录/知识库保存重开与冲突 | 浅深主题/桌面窄屏、草稿不丢失 | 四类型链接和两编辑器由独立真实Edge契约覆盖；本次WorkBuddy回执链接的人工打开仍未核实 |

取消MCP请求不等于撤销已经持久提交的业务事务；需分别查询提案状态。已删除条目不能因重试重新创建。客户端升级后重新验收，不能沿用旧版本通过标签。

## 5. 证据记录和收尾

### 首批八轮结果与后续补验安排

用户确认问题/待办/信息新建成功，附件请求因无接口失败；附件写入为明确排除范围。累计8轮已用满，不能继续沿用原额度。正式文件重读与4份回执SHA256、候选正文和开放元数据逐项一致；人工确认过程尚待核实，不能据此完成agent_attested验收。

后续用户表示“我有很多额度可以用来测试”，据此恢复已提出的最多8轮手动补验，不自动发起模型调用。第一轮实际产生4份已预览、未提交提案：document/create v1、issue/append v2（一次revise后重新预览）、todo/append v1、info/append v1。三份追加均保留原正文前缀及base_content开放字段（含due/info_fields），回执仍4份、commit调用未增加。完整预览展示待用户核实，不能把服务端previewed状态当作已看过或已确认；问题须使用最新v2。

用户随后明确确认4份完整预览均已展示；这仍不是提交批准。原2小时夹具随后正常退出，未将自然到期记作重启验收通过。到期前保存的本任务受限副本38文件经过复制前后及目标哈希核对；续验服务复用真实应用组件，开放前轮换临时令牌并验证旧令牌拒绝，8份提案/4份回执逐字节保持。同URL恢复了原TEMP配置别名，仅需用户重连原workbench_probe，桌面登记无需修改；临时副本和别名在验收后均须撤销/清理，不涉及正式认证或配置。开发侧恢复核对不能替代真实客户端复连和查询证据；下一轮先查当前提案，版本/摘要变化则重新预览确认。

续验第二轮真实结果：桌面重连后get_proposal4→commit4→get_item4→prepare4→preview4均记录tool_is_error=false，四份原预览提交成功，回执总数8。DOC-0001新建与issue/todo/info追加后正文、开放字段及文件SHA256均匹配最新候选/回执。随后四类型update v1均previewed、未提交，信息字段候选为原字段逆序且值/备注不变。用户已确认上一批完整预览展示，本轮提交前是否手动发送所给确认消息、4份update是否完整展示仍待用户回报；服务端回执不替代确认过程证据。知识库append、update落盘、网页批准及其他故障仍未验收。

用户随后确认4份update完整预览展示，并提供客户端的完整执行/预览报告，回执/候选内容与服务一致。关于此前确认消息仍未提供独立说明，客户端“已按确认执行”不能替代用户确认事实，不把该缺口写成通过或认定确定绕过。下一轮以新的明确用户消息测试update提交，再准备四类型local_web append，补齐document append及四类型独立批准；替代原安排中额外4份local_web create，减少重复临时条目，不减少类型/确认路径覆盖。网页批准仍必须由用户独立完成。

第三轮用户明确回复已发送指定确认/网页批准测试任务；四类型update均提交、逐份正式文件重读通过（正文/字段/回执SHA256），info字段6项逆序保持。本轮记录用户确认事实，不推断其他轮次。随后四类型local_web append均v1已预览，4次自报确认均tool_is_error=true，无approval/receipt，正式回执仍12份；具体错误码与完整展示待用户反馈。网页尚未批准，document append尚未正式保存，不能标完整两路径通过。

随后用户核实4份完整展示、4次confirmation_required，提供客户端错误表（retryable=false、需要本机提案管理独立批准，无item_id/revision，无重试/重建）；与工具错误及空批准/回执状态一致。四类型自报绕过负向验证通过，网页正向仍待用户逐份重新读取完整预览后批准；夹具不代发批准HTTP请求。当前页面HTTP200、proposal-actions为0。

用户随后在真实网页逐份独立批准4份local_web追加，四份completed批准日志与提案approval、版本/摘要及回执相符，正式回执16份；逐份重读正式文件的正文、开放字段及SHA256匹配，document append已保存。未通过夹具或Agent执行管理批准。下一轮由客户端查询回执/幂等并补查询负向；普通临时HTTP已准备未授权项目WorkBuddy-未授权对照及ISSUE-0002，磁盘存在且未授予当前客户端，用作真实范围/引用拒绝对照，尚不记拒绝通过。

第四轮真实客户端报告与工具/磁盘核对：4份网页回执查询及重复提交返回原回执，回执16不变；四类型catalog已读取，分页两页ID无重复，search游标终止。INFO-0001分6段、707字符，完整拼接原文已逐字比对磁盘且revision匹配。未授权项目/ISSUE-0002搜索为空、catalog/get_item为not_found，引用为invalid_reference，非法info append附加status为unknown_field，均未生成越权提案。取消候选省略info_fields保留6项；下一轮已观察其v2空字段且cancelled，正式revision/6字段未变，具体旧版本/取消拒绝码待客户端回报。

第五轮用户摘要与工具/磁盘一致：原样prepare同一提案v1，改body复用request_id为idempotency_conflict；修订显式info_fields=[]后v2完整预览，旧v1提交version_conflict；取消v2后提交invalid_state，无回执，均retryable=false。正式INFO-0001保持原6字段/revision，回执16不变。清空/省略区别在候选中验证，清空候选未正式提交。丢响应、服务重启与认证故障仍待真实客户端测试。

后续最多8轮按下表批量补验；每轮由用户手动发送，所有提交仍等待当前完整预览后的新消息或网页独立批准。表格是待执行安排，不代表通过；额度不足时保留未完成项，不自动追加。

| 轮次 | 手动客户端任务 | 前置与证据 |
| --- | --- | --- |
| 1 | 补充原确认过程；准备知识库create及现有issue/todo/info的append，展示4份完整预览后停止 | 完整读取目标与revision；不把本轮请求当确认 |
| 2 | 用户确认上轮后提交；读取4类型现值，准备4份update并完整预览 | 检查实际落盘/回执；info字段重排、多行/空格保持 |
| 3 | 用户确认update后提交；准备4类型local_web append并完整预览，验证自报确认被拒绝 | 同时补齐document append；正式写入等待用户另在临时网页批准 |
| 4 | 查询4份网页批准回执，重复提交查询幂等；准备一个供修改/取消的提案 | 网页批准必须独立人工进行，完整UI证据单列 |
| 5 | 修改提案、重新预览，验证旧版本提交被拒绝并取消；分页/分段/范围/未知字段错误 | 使用专用可取消测试提案，禁止制造正式内容的错误覆盖 |
| 6 | 受控临时服务重启后查询既有回执，验证断连重连与持久性 | 开发侧只对临时服务协调故障，不替代真实客户端请求 |
| 7 | 临时凭据轮换/撤销、错空间及业务错误对照 | 开发侧准备可审查临时配置；不读账号或覆盖其他连接器 |
| 8 | 复连只读复核、缺口复测、汇总精确模型/客户端版本和实际结果 | 未通过项仍保留；结束撤销临时凭据并由用户移除连接器 |

重启/凭据实验前需落实临时夹具生命周期控制及完整新项审查；不得把首次2小时会话超时误记为计划内恢复通过。记录/知识库保存重开、草稿及冲突的真实网页验收独立记录；当前Work浏览器自动化禁用，不冒充已操作。补验已获额度答复并开始第一轮，剩余项仍待实际执行，AG-121保持进行中。

每组记录实际命令、精确版本、测试时间、退出码、关键返回字段和异常；原文仅取必要脱敏片段。秘密/完整配置不进Git，截图只留临时目录。测试完成撤销临时客户端，停止服务/客户端，核验隔离进程退出后清理本任务临时目录；保留失败/未运行事实。

完成门槛为矩阵全部要求具备真实证据，并更新[台账](AI_AGENT_PROGRESS.md)、[接入](AGENT_INTEGRATION.md)、[验收](AI_AGENT_ACCEPTANCE.md)。本文件已准备不代表AG-121完成。

### 2026-11-07 续验环境与桌面探针核查

旧恢复服务已停止且旧测试身份撤销；新续验夹具从最新live复制114个文件，逐文件核对复制及源未变化的SHA256，保留16份历史回执。旧身份保持撤销，另发同范围的新测试身份；不改写历史提案归属，新身份不能查询旧身份的私人提案。新loopback服务HTTP200只证明开发侧环境可用。临时配置、私人状态与trace不进Git。

新完整连接器项显式含--relay和--protocol-faults，已展示给用户并获得“已替换完整项并保存重连”的反馈；随后只读核查仍仅见旧--relay进程、新trace不存在。因此模式尚未运行，不能记桌面成功或协议失败。已请求核对界面程序/参数两个非秘密字段，未读取正式客户端配置/认证，也未替用户发模型请求。

用户再次添加参数重连后，实际中继argv已含--relay --protocol-faults。连接探针和后续业务客户端分别出现真实回复，关键脱敏原文：

```json
{"direction":"client_to_server","fixture_reply":"ping","valid":true}
{"direction":"client_to_server","fixture_reply":"unknown_method","valid":true,"error_code":-32601}
{"direction":"server_to_client","error_code":-32002}
```

第三行来自后续业务连接提前于notifications/initialized发出的tools/list；服务拒绝后，客户端完成initialized并重试，实际获得12工具。不能将该错误从成功记录中抹去，也不能把成功重试说成没有协议错误。业务连接clientInfo.name=workbench_probe/version1.0.0，仅为配置名称，不作为厂商身份认证。

第6轮真实客户端依序capabilities/get_item/prepare/preview均tool_is_error=false；新append提案e736dfa2-35a9-40ec-8926-a683cebaa6bf v1、agent_attested、previewed、无回执，旧16回执不变。完整预览是否实际向用户展示仍待答复，开发侧不提交；后续丢响应尚未施加。

### 取消证据补强与本机安装版本变化

新增2项专项验证取消关联在途工具但不泄露requestId/reason/参数、迟到响应仍可单独记录，以及未知/畸形取消不消耗pending；7项专项通过。此为验收中继，默认仍逐字节转发；旧中继不热更新，尚无新版字段的真实取消通知，不能标桌面取消语义通过。

本轮原装CLI复查两次失败，实际错误为：

```text
Error: Cannot find module '../dist/codebuddy'
code: 'MODULE_NOT_FOUND'
```

只读安装元数据核查：磁盘WorkBuddy.exe为5.9.3，CLI package版本2.165.0；旧5.1.5/2.103.3历史保留，不把旧版完整矩阵直接升级。当前安装仅有codebuddy-lite-wb.mjs；原装bin/codebuddy提供CODEBUDDY_FORCE_LITE_WB_BUNDLE=1入口，使用该固定环境开关后真实CLI显式探针通过（2.165.0、12工具、ping空结果、未知方法-32601、退出0、无模型turn/真实配置修改）。本次通过临时Python调用覆盖隔离环境开关，仓库命令尚未修复；后续应独立修复验收启动设施。未提取SDK/修改厂商安装文件。桌面运行中版本已请求用户核实，磁盘安装版本不冒充运行中版本。

用户“关于”截图确认当前运行桌面5.9.3(d4692421)，Electron37.10.0/Chromium138.0.7204.251/Node22.16.0。第6～7轮及本轮桌面探针按该版本记录；旧5.1.5四类型三操作历史不改写为新版全量通过。第7轮首次唯一commit为service_unavailable、retryable=true、无回执；随后原提案查询committed/同v1摘要及持久回执，正式ISSUE-0001完整正文286字符、revision239540b8d7d3497cdaeca1337063a2736d4debd80a1c8de49596bea34ca9ef07，追加只一次。与HTTP故障日志真实200后截断、工具commit isError→get_proposal/get_item成功、磁盘正文/开放字段/17回执核对一致，无重建。客户端报告“待验证无”只指本轮，不代表完整兼容矩阵收口。

CLI验收入口已修复：只有完整codebuddy.js缺失且lite-wb.mjs存在才选择原装固定lite开关；完整安装保持默认路径，不改厂商安装。8项专项通过，当前默认/--protocol-faults两命令均真实CLI2.165.0、cli_bundle=lite-wb、12工具、退出0通过，默认无注入、显式两回复valid，无模型turn/正式配置修改。两次旧启动失败保留；该修复不改变应用运行时/协议/数据/资源版本。

### 5.9.3第8轮：重启、幂等与授权故障

用户确认按八次capabilities严格顺序执行。真实服务重启后get_proposal/get_item与原v1 commit重放均返回原回执，revision/committed_at不变，回执仍17。错空间头得到409 workspace_mismatch/retryable=false；桥接已发请求时轮换，旧令牌得到401 unauthenticated/false，下一请求自动重读配置后200。夹具以真实HTTP预置120/min窗口，实际429 rate_limited/true；真实业务服务重启后200。服务端旧授权模拟去除kinds且仅read，capabilities仅issue/document；两次search为空，INFO/TODO读取not_found，ISSUE允许读取，三次create均forbidden（缺propose），无提案生成。随后正常管理写恢复原显式四类型/scopes，capabilities200。

代表性HTTP夹具原文（其条件是显式合成，响应来自真实服务）：

```json
{"fixture_mode":"wrong_workspace","fixture_step":1,"http_status":409,"route":"/api/agent/v1/capabilities","service_error_code":"workspace_mismatch"}
{"fixture_mode":"rotate_before","fixture_step":2,"http_status":401,"route":"/api/agent/v1/capabilities","service_error_code":"unauthenticated"}
{"fixture_mode":"rate_fill","fixture_step":4,"http_status":429,"route":"/api/agent/v1/capabilities","service_error_code":"rate_limited"}
```

以上和真实工具isError/恢复成功、持久注册表及17份回执/正式问题哈希一致；INFO-0001/TODO-0001文件仍等于复制源哈希、INFO6字段，无删除。客户端尚未在恢复后重读info/todo，留下一轮验证。错空间头只证明注入错误被服务拒绝/客户端收到错误，不冒称已测试客户端配置文件真实损坏。限流为真实服务限额加人工流量预置，不声称自然高负载性能。撤销/实际取消及新版四类型两确认仍待运行。
