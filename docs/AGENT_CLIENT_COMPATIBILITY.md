# Agent 客户端兼容矩阵与隔离验收

新能力验收见文末 AG-142。以下 AG-121 历史结论只覆盖当时版本和范围。

核查日期：2026-11-07。工作项：AG-121。当前结论：**AG-121已完成；当前WorkBuddy5.9.3四类型三操作、两确认路径、查询/协议/故障/取消撤销均具备真实证据**。第14轮汇总一字符差异已由原始工具返回核实为汇总转写，原始空格正确。原装CLI连接与显式协议探针单列。临时连接器/服务/身份/目录收尾已完成；下文逐轮历史保留当时未完成状态和较早确认缺口，不改写为当前版本的成功证据。

## 1. 已有证据和缺口

| 客户端 | 精确版本/传输 | 状态 | 证据与限制 |
| --- | --- | --- | --- |
| Codex CLI | 0.163.0-alpha.10.2 / stdio MCP 2025-11-25 | 已实测 | python codex_agent_acceptance.py；12工具、四类型、两确认路径、重启/撤销；无模型turn，不计为非Codex验收 |
| WorkBuddy桌面 | 5.1.5 / stdio MCP2025-11-25 | 四类型三操作、两确认路径及查询/幂等/取消子集已实测 | 16份历史回执与正式文件重读一致；四类型update有完整展示/新消息确认，local_web有独立网页批准。较早轮次确认未独立核实；协议、认证、重启/丢响应等仍待完成 |
| WorkBuddy附带的原装CodeBuddy CLI | 2.103.3 / stdio MCP2025-11-25 | 连接与工具发现通过 | python workbuddy_agent_acceptance.py；真实initialize/initialized/tools/list、12工具、Connected；无模型turn，写入/故障矩阵未运行 |
| WorkBuddy桌面 | 5.9.3 (d4692421) / stdio MCP2025-11-25 | 当前本机矩阵已完成 | 用户关于页核实版本；第6～14轮真实任务与29份回执/正式文件一致；原始段1核实707字汇总中的一字符仅为转写，未沿用5.1.5结果作为新版通过 |
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

## 4. 当前本机必跑矩阵（5.9.3已完成）

| 组 | 真实操作 | 必须保留的脱敏证据 | 当前结果 |
| --- | --- | --- | --- |
| 协议 | initialize/initialized、tools/list、UTF-8、ping、未知消息/字段、断连/重连 | 客户端/OS/协议版本、12工具目录、错误码、stdout仅协议 | 原装CLI/桌面握手12工具及桌面重连真实请求通过；一次取消通知不等于取消语义通过，原装CLI与5.9.3桌面显式ping/未知方法均通过；曾提前tools/list获-32002后初始化重试成功，5.9.3在途capabilities收到关联取消，迟到isError后同一连接查询恢复；不承诺立即中断/回滚 |
| 查询 | kinds范围交集、catalog四类型、分页、分段正文、引用越权 | 允许/拒绝对照、完整分段拼接等于磁盘正文 | 四类型catalog、授权范围、两页无重复、6段707字符拼接逐字等于磁盘通过；越权读取not_found/引用invalid_reference通过，5.9.3旧授权缺kinds时仅issue/document，info/todo搜索空/读取not_found、issue允许对照通过，原四类型恢复；5.9.3第10轮info/todo读取恢复通过 |
| create | issue/document/todo/info各新建 | 完整预览/警告/版本、规范字段、保存后重读与新仓储重载 | 5.1.5历史四类型落盘、较早确认缺口保留；5.9.3四类型local_web新建独立网页批准/日志/正文和字段/回执哈希重读通过 |
| append | 四类型各追加 | 合成全文、todo/info只接受body，字段不隐式合并 | 5.9.3四份agent_attested完整展示后新消息确认提交，正文/字段/回执SHA256通过；5.1.5另有网页批准追加；info附加status被unknown_field拒绝 |
| update | 四类型各更新/重排info_fields | revision校验、保留未开放元数据、清空/省略差别 | 5.9.3四份完整展示后新消息确认提交；todo完成/due=null、info三字段逆序保值、文档改标题ID稳定及issue优先级通过；取消候选省略保留3项、显式空列表0项，取消后正式字段/revision未变 |
| agent_attested | 展示当前完整预览，修改后旧确认拒绝、取消 | 真实工具往返；程序测试声明不能称为人类确认或模型遵规证明 | 四类型update具备完整展示/指定新用户消息/提交证据；取消候选修订后旧版version_conflict、取消后invalid_state通过，较早轮次确认缺口保留 |
| local_web | Agent自报确认拒绝，本机网页重新预览批准，再由客户端查询 | confirmation_required、同一版本/摘要/回执，无可兑换票据到客户端 | 四类型自报拒绝→用户网页批准→真实客户端查询/重放原回执通过，批准日志/版本/摘要/正式文件一致 |
| 幂等 | 相同request_id重试、不同输入拒绝、提交丢响应先查询 | 只有一份正式条目/历史，原回执不变 | 四份提交重放原回执；prepare原样同提案、不同body为idempotency_conflict，旧版/取消拒绝通过；5.9.3唯一提交成功响应截断→先查原提案/正式问题→重启后重放原回执通过 |
| 故障 | 撤销/轮换、服务重启、错空间、isError、限流 | 令牌失效生效、持久恢复、无秘密输出 | 5.9.3实际服务重启后原回执重放不变，轮换旧令牌401/新令牌恢复、错空间头409、真实限流429/重启恢复通过；最终正常撤销后探针及capabilities/get_proposal/get_item均unauthenticated，注册表disabled；合成条件见下文 |
| UI | 结果链接打开，记录/知识库保存重开与冲突 | 浅深主题/桌面窄屏、草稿不丢失 | 四类型链接和两编辑器由独立真实Edge契约覆盖；5.9.3新建四类型的真实结果链接用户已逐份打开并刷新，标题/类型正确 |

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

### 5.9.3第9～10轮：在途取消与四类型网页批准

用户正常重连后发送单次capabilities，在其执行时点击停止。实际脱敏中继原文：

```json
{"direction":"client_to_server","method":"notifications/cancelled","cancelled_request_pending":true,"cancelled_tool":"workbench_capabilities"}
{"direction":"server_to_client","tool":"workbench_capabilities","tool_is_error":true}
```

HTTP夹具已从真实服务取得200只读结果，再延迟响应12秒；桥接既有同步HTTP上限10秒，取消后仍观察到迟到isError，不能声称立即中断或撤销业务。17回执/正式问题不变。第10轮同一连接（中间无新initialize）capabilities/get_proposal/INFO-0001/TODO-0001成功，用户报告原回执不变、info707/todo111字符完整可读；当前trace无unparsed行，未观察额外非JSON输出。

第10轮四类型catalog/检索已执行。document携project_id的catalog得到invalid_request，改为仅kind=document后成功；文档按分类、无项目归属，符合领域契约。四个独立wb593-create-* request_id生成local_web v1完整预览，用户核实展示，四次自报提交均confirmation_required/false无回执。用户随后在真实网页逐份重新预览批准，四份completed批准日志/提案approval/版本/摘要/持久回执一致，回执21。正式ISSUE-0003/DOC-0002/TODO-0002/INFO-0003的正文及全部开放字段重新解析匹配候选、SHA256匹配回执；todo due=2026-11-30，info3字段顺序、引号、LF及value/note首尾空格与请求逐字一致。未由夹具/Agent代替网页批准。

当前OS实测Windows11专业版10.0.22631；用户截图的模型UI标签为Hy4，未独立核实后端模型版本，不将单次客户端执行外推为任意模型遵规保证。第11轮网页回执查询/重放及四类型append待执行，新版update/旧版本拒绝/最终撤销与链接人工打开仍待收口。

用户已逐份打开并刷新本轮ISSUE-0003/DOC-0002/TODO-0002/INFO-0003正式结果链接，确认均对应正确标题/类型；此为手工结果打开证据，不外推为新的编辑器主题/草稿冲突验收。第11轮已由用户手动发送，读写后续仍待实际结果。

### 5.9.3第11～14轮：更新、负向与最终撤销

第11轮客户端四份原网页回执查询/重放不变，四份append完整预览展示经用户核实；用户新消息发送指定确认任务后，第12轮四份agent_attested append提交、回执25。随后四份update完整展示经用户核实，用户再发送新确认任务，第13轮四份提交及各自get_item成功，用户确认全部成功并停止。四份正式正文/开放字段等于候选、SHA256等于回执；todo完成且due=null、info三项字段完全逆序但内容/空格/LF保持、document改标题但DOC-0002稳定、issue优先级高。追加及更新段各一次，回执29，四个新条目各两份修改历史。

第14轮报告核实：未授权项目搜索空、catalog及ISSUE-0002读取not_found，越权引用invalid_reference、info追加非法status为unknown_field，均未生成提案。list_proposals(limit=3)五页共13项，cursor为3/6/9/12/null；search(limit=2)两页四个新ID，无重复。INFO-0001分段offset为0/128/256/384/512/640，末段next_offset=null、body_characters=707；汇总正文与磁盘逐字核查有一字符差异，原始工具结果核对待补，不能据707长度一致声称逐字一致。

取消专用提案479662ac-b9c9-4b6d-a7ca-acad8c48b4e5：省略info_fields的v1保留三项，原prepare重放同一提案、改body复用request_id为idempotency_conflict；revise显式空列表的v2预览为0项，旧v1提交version_conflict；取消v2后提交invalid_state。均retryable=false，无成功回执；最终cancelled/v2/previewed_version=2，正式INFO-0003仍三项、77字符、revision60b35224d6c14d7b25d805aa3753f60fe832fbe39c7103343f19c4457b14d34e，候选清空未落盘。

末尾固定哨兵查询触发正常CredentialManager撤销，真实服务关键HTTP原文：

```json
{"fixture_mode":"revoke_before","fixture_step":null,"http_status":401,"route":"/api/agent/v1/proposals/00000000-0000-0000-0000-000000000014","service_error_code":"unauthenticated"}
```

用户第14轮报告原文摘录（省略表格中的request_id与重复说明）：

```text
探针 get_proposal(00000000-0000-0000-0000-000000000014) 本身即返回 unauthenticated「Agent 凭据已失效或被撤销」
```

随后严格仅capabilities/get_proposal/get_item三读，用户报告均unauthenticated/retryable=false、无正文或提案数据；中继三次isError及注册表enabled=false一致，无补权或换凭据。29回执加四份正式文件的33项字节哈希检查点不变，stdout trace无unparsed行。此为当前明确版本与临时范围的实测，不代表任意客户端/模型或远程互操作。

收尾：用户已移除仅本次workbench_probe。两个临时夹具STOP后退出0，业务/代理端口均关闭，按命令行匹配未见相关进程；本次身份及旧live身份disabled。旧恢复原始静态副本曾留enabled=true，使用其既有空间的正常CredentialManager撤销后清理，未运行旧服务或重建空间。历史三处和本轮三处递归删除均曾被自动审批拒绝（只有blocked by policy），未换方法绕过；用户分别手工删除，只读核实六处目录均不存在，未触及其他客户端或正式数据。

最终原始结果已收到：用户提供同一INFO-0001/offset0/length128的段1，解码换行为128字符，项目显示名是“WorkBuddy 隔离验收”（空格），项目id仍为“WorkBuddy-隔离验收”。该段逐字等于已校正汇总前128字符，结合清理前其余706字符逐字相同的比对，确认六段707字符完整拼接通过；差异仅在汇总转写，不是服务原文变化。提案分页5页13项、搜索2页4项均无重复/遗漏；无新增模型任务或重建环境。

## AG-142 新能力兼容验收（2026-11-10）

| 表面 | 本机版本 | 已证实或待测 |
| --- | --- | --- |
| Codex 安装包 | Windows `OpenAI.Codex` 26.1103.7773.0 | 磁盘安装元数据。桌面任务启动前需由用户核对运行版本 |
| Codex CLI 与 App Server | 0.167.0-alpha.3.2 | 临时 `CODEX_HOME` 下实际直连 MCP 2025-11-25、完整 22 项 Schema、重载配置和新会话重新发现。未启动模型 |
| WorkBuddy 安装包 | 5.9.3，ProductVersion 5.9.3.0 | 磁盘安装元数据。桌面任务启动前需由用户核对运行版本 |
| WorkBuddy 原装 CLI | 2.165.0，`lite-wb` | 两次新进程实际 initialize、initialized 和 tools/list，MCP 2025-11-25、完整 22 项工具名称。显式探针的 ping 和未知方法应答均通过。原装 `mcp --help` 只有登记、移除、列表与详情，公开直接业务调用入口未验证 |
| WorkBuddy 桌面 | V5.9.3 / Hy4 | 用户级临时单项发现 22 项，真实只读及概念图新建 `local_web` 单案通过。项目级发现、其余写入与确认矩阵待验 |
| Codex 桌面 | 中继记录 `codex-mcp-client 0.167.0-alpha.3.2` | 文件读取、概念图新建和更新 `local_web`、单文件附件 `agent_attested` 均通过。其余写入和确认待验 |

### 已观察的桌面试点

用户批准两客户端各一次只读试点，随后授权监督自行验证 WorkBuddy，并指定 Hy4。监督在 WorkBuddy V5.9.3 的新建任务中选择了本次临时 `desktop-project`，模型选择器显示 Hy4。夹具已生成项目级 `.workbuddy/mcp.json`。等待至少 60 秒后仍未出现 `protocol.jsonl`，因此没有 `initialize` 或 `tools/list` 证据。按约定在发送前停止，实际模型回合为 0，未切换模型或使用用户级配置。结论限于这次运行环境的项目级发现，WorkBuddy 原装 CLI 的 22 项工具证据继续单列。

监督通过本次夹具的 STOP 路径收尾。进程退出码为 0，输出记录 `stopped=true`、`port_closed=true`、`temporary_directory_removed=true`、`revoked_credential_denied=true`。随后只读核验临时项目不存在。

Codex 使用另一份夹具。用户手工报告「没发现 workbench_ag142」。监督只读核对临时目录存在，`protocol.jsonl` 不存在，无中继握手或工具目录证据。通过该夹具唯一 STOP 路径退出 0，输出记录服务和端口关闭、撤销后旧凭据被拒、临时目录移除，随后只读核验根目录不存在。该次试点没有启动模型或改用户级配置。实际 App Server 业务直调的通过证据仍单列。

2026-11-11，用户用长路径复验。截图中的 `/mcp` 列表显示现有的 `workbench`，未显示本次 `workbench_ag142`。本次临时中继恰有 5 条记录，按顺序为 `initialize`（`codex-mcp-client 0.167.0-alpha.3.2` 提出 `2025-06-18`）、服务端返回 `2025-11-25`、`notifications/initialized`、`tools/list`、22 项工具应答。该轨迹证实桌面已通过本次中继发现工具。界面未列出临时项的原因待查。实际 `tools/call` 为 0，模型回合为 0。

另用全新隔离 `CODEX_HOME` 验证了按名称调用。临时可信项目的 App Server 目录只有 `workbench_ag142`。显式指定 `server=workbench_ag142` 调用一次 `workbench_capabilities`，返回空间 ID 与本次夹具匹配，中继也只记录该次工具调用。夹具通过 STOP 撤销旧凭据并清理。实际桌面截图里只有既有 `workbench`，本次没有可核实的桌面调用入口能在发消息前把工具限定到 `workbench_ag142`。继续桌面验收需要先验证该项在真实任务里可独立选中并限定调用。

监督写入本次 STOP 并实测端口已关闭。夹具退出码为 1，清理 `desktop-project` 时遇到 Windows 文件占用或访问错误 `WinError 32/5`。复核时 STOP 和临时项目目录仍在。待用户关闭本次临时项目后复核清理，保留本次协议证据。此次未改用户级 MCP 配置。

用户随后确认已关闭本次 Codex 临时聊天和项目。当时只读复核显示系统临时目录中的 `workbench-ag142-pilot-codex-y2bf7efe` 仍存在，Codex、Python 和 Node 的进程命令行匹配数为 0。针对这一确切目录的 PowerShell `Remove-Item` 清理请求包含目录、父路径及子项的重解析点检查。自动审批以 `blocked by policy` 拒绝该请求，清理命令未执行。用户随后手工删除目录，按原路径只读执行 `Test-Path` 返回 `False`，独立清理待办关闭。

### 连接器发现与启动时机对照

| 表面 | 已复验结果 | 边界 |
| --- | --- | --- |
| WorkBuddy 原装 CLI 2.165.0 | 同一 stdio 配置放在 `<项目>/.workbuddy/mcp.json` 时，`mcp list` 报无服务。放在 CLI 自身的 `<项目>/.mcp.json` 时，默认 `list` 无握手。对照见过 `Needs approval`。对同一项目条目显式 `mcp get workbench_ag142` 显示 `Scope: project`，并实际完成 initialize、initialized 和 tools/list，发现 22 项 | CLI 项目作用域与桌面项目作用域分开。已安装版的 `mcp list` 子命令拒绝显式 `--mcp-config` 的组合，不能把会话启动选项套到子命令上 |
| WorkBuddy 5.9.3 安装包 | 静态核对显示桌面管理列表返回已登记项与缓存。展开某个已登记项的工具详情走 `describe`，可信且启用时会进入 `activate`。项目资源另在会话准备时解析。部分运行入口注入 `--mcp-config` 和 `--strict-mcp-config` | 已选工作目录、登记列表、连接启动是三个不同证据。若桌面已经列出本次**项目级**目标，可在发送前只展开该行，并以中继核实实际连接。当前没有证据表明此前项目文件会进入该列表，也未验证此动作在桌面会启动本次连接器 |
| Codex 安装版 App Server 0.167.0-alpha.3.2 | 同一无 `.git` 的临时目录和同一项目配置，默认、明确不可信、只信任另一目录时均无目标工具和中继。独立 `CODEX_HOME` 中仅将实际线程 CWD 的确切目录标记可信后，发现 22 项并产生中继轨迹。客户端提出 `2025-06-18`，服务返回 `2025-11-25`，随后收到 initialized 和工具目录请求 | 证明该二进制在隔离运行下可加载项目级配置。用户此前实际桌面未发现的原因未确定。应先核对本地线程工作目录和有效信任，避免原样重试 |

WorkBuddy 文档区分用户级和项目级文件，也说明可在管理界面查看连接状态。CLI 文档另外说明项目级审批、严格注入和首条消息的预热时机。这些资料与上述静态及隔离对照相符，但无法确定实际桌面的首次等待会在哪一层停止。全局自定义 MCP 开关若禁用，只记录，避免为试点修改影响其他连接器的设置。[WorkBuddy MCP 指南](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/MCP-Guide) [WorkBuddy 工具管控](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Permission-Modes) [CodeBuddy CLI MCP](https://www.codebuddy.cn/docs/cli/mcp) [CLI 首轮状态](https://www.codebuddy.cn/docs/cli/mcp-first-run-status)

Codex 官方配置说明要求项目可信，桌面文档提供 `/mcp` 查看连接。旧试点的长路径和脚本当时输出的 8.3 拼写，在默认候选文件的 `projects` 中均未匹配。该检查未确定旧任务实际选取的路径或桌面生效信任。新夹具会输出解析后的长路径，中继摘要分别记客户端提出的版本和服务返回的版本。[OpenAI Docs 配置层](https://learn.chatgpt.com/docs/config-file/config-advanced) [OpenAI Docs MCP 界面](https://learn.chatgpt.com/docs/extend/mcp?surface=app)

若用户此前未能核实旧任务的实际目录与信任，可审查一次新的零模型检查。用户准备好后启动 `python workbuddy_agent_acceptance.py --readonly-pilot codex`，在 Codex 桌面创建新本地任务并精确选择该次输出的 `desktop_project` 长路径。若客户端明确询问，只在用户同意时信任该目录。信任记录可能写入项目配置映射，本次步骤不增删用户级 MCP 项。核对实际目录与信任后，从输入框的命令菜单选择 `/mcp` 查看连接。若无此本地命令、目录或信任无法核对，停止。若菜单可用但 60 秒仍无目标项或中继握手，也停止，不发送 `PROMPT.txt`。随后按本次 STOP 收尾。已有证据显示前一任务确切信任时，不原样重复这次检查。

### 待审查的单条用户级备选

仅在用户接受用户级可见性并明确批准完整候选时采用。一次只启动一个新的只读夹具，工作目录、连接器参数、令牌文件和 TTL 均取自该次输出。与既有的项目级条目不能同时生效。授权最多是该客户端一次合成只读回合，WorkBuddy 指定 Hy4，Codex 模型由用户另定。消费额度未知。

| 客户端 | 用户级配置目标 | 可审查的完整候选来源 |
| --- | --- | --- |
| WorkBuddy | 默认 `~/.workbuddy/mcp.json`，仅增加 `mcpServers.workbench_ag142`。安装包支持 `WORKBUDDY_CONFIG_DIR`、`CODEBUDDY_CONFIG_DIR` 覆盖，须先核对实际客户端目标 | `python workbuddy_agent_acceptance.py --readonly-pilot workbuddy` 输出的 `config_text`。从其中取唯一的 `workbench_ag142` 对象合并，不用它替换整个文件 |
| Codex | 默认 `~/.codex/config.toml`，仅增加 `[mcp_servers.workbench_ag142]` 及其 `.env` 子表。以实际桌面设置打开的用户配置为准 | `python workbuddy_agent_acceptance.py --readonly-pilot codex` 输出的 `config_text`，完整两张表，包含程序、参数和环境路径 |

WorkBuddy 完整候选的结构如下。实际值须由本次夹具解析后重新审查，不能复制已关闭预演的路径。

```json
{
  "mcpServers": {
    "workbench_ag142": {
      "command": "<本次输出的 Python 绝对路径>",
      "args": ["<本次输出的 workbuddy_agent_acceptance.py 绝对路径>", "--relay"],
      "env": {
        "WORKBENCH_PROBE_TRACE": "<本次临时 protocol.jsonl>",
        "WORKBENCH_PROBE_CONFIG": "<本次临时私人客户端 JSON 路径>"
      }
    }
  }
}
```

Codex 候选同样只登记固定中继和本次两个路径。

```toml
[mcp_servers.workbench_ag142]
command = "<本次输出的 Python 绝对路径>"
args = ["<本次输出的 workbuddy_agent_acceptance.py 绝对路径>", "--relay"]

[mcp_servers.workbench_ag142.env]
WORKBENCH_PROBE_TRACE = "<本次临时 protocol.jsonl>"
WORKBENCH_PROBE_CONFIG = "<本次临时私人客户端 JSON 路径>"
```

本次只读审计，当前 shell 无上述覆盖。两处默认文件均为普通文件且可解析，WorkBuddy 有 0 个其他项，Codex 有 2 个其他项。均未发现完全同名或按大小写及分隔符保守归一化后的冲突。未输出其他条目、配置值或凭据。当前 shell 结果不能确认运行中桌面的配置根。

获准后，先在实际目标处复核同名、同义名称、已登记项、配置可解析且未在审查后变化。遇到冲突、权限限制、重解析路径、无法核对实际配置或无关设置变化时停止。只新增本次唯一条目，保留其余条目和顶层字段。若客户端已显示本次条目，可只查看或连接该项，以中继的 initialize 与 tools/list 判定。60 秒仍无握手或目录，停止，不发模型提示。用户级条目可能暂时对其他项目可见，但本次凭据只能读取单一合成工作空间、项目和文本文件。

生成与比对顺序。可先在两个启动命令后追加 `--pilot-check` 审查结构，预演退出后其路径即失效。用户准备审查本次确切配置时，才以不带 `--pilot-check` 的对应命令启动一份夹具。从输出复制 `config_path`，用 `Get-Content -LiteralPath '<本次 config_path>' -Raw` 只读查看完整项，与 `config_text` 核对。添加前，从客户端确认实际生效配置文件，并解析该文件记录所有非目标条目和顶层字段的本机私有快照。添加后重读文件，核对目标程序、参数、环境和连接范围与本次候选完全相同，再比较除目标外的整个解析结构。删除后，比较整个解析结构与基线，确认目标不存在。无关内容不出本机，不通过整个文件覆盖回滚。使用用户级候选时，从该夹具根下另建无项目配置的空工作目录，打开这个目录而非含同名项目配置的 `desktop_project`。实际读取仍用同一 `PROMPT.txt`，并核对其中的空间 ID。

退出时先关闭临时项目和连接，再创建本次 `stop_file`。夹具先撤销身份并检查旧令牌返回 401，然后停止服务并清理临时目录。核对终端退出、端口关闭和目录消失后，从实际配置中仅移除与审查候选匹配的 `workbench_ag142`，并复核其他条目和顶层字段。发现条目或文件被其他操作改写，停止覆盖并保留现场，不恢复整个旧文件。文件授权最长 20 分钟，WorkBuddy 发现阶段另有 20 分钟上限。超时不会移除真实用户级条目。若实际账号隔离、项目入口或这项用户级例外无法确认，只保留已证实的隔离 CLI/App Server 结果和桌面缺口。

已证实的零模型隔离路径是 Codex App Server 的可信项目和 WorkBuddy 原装 CLI 的显式项目条目详情。没有证据表明能够给现有 WorkBuddy 或 Codex 桌面账号启动一份独立认证会话，同时保证完全隔离用户级配置和任务历史。上述两条隔离路径可保留为协议证据，实际桌面任务继续按可核对的用户许可处理。

### Codex 可信项目内限制连接器

在已安装的 App Server `0.167.0-alpha.3.2` 和临时 `CODEX_HOME` 中，用两个不同的合成空间测试。用户级 `workbench` 指向对照空间。可信项目配置设置 `[mcp_servers.workbench] enabled = false`，并用 `enabled_tools` 将 `workbench_ag142` 限定为 `workbench_capabilities`、`workbench_list_file_grants`、`workbench_get_file_info` 和 `workbench_read_file`。可信项目的目录仍列出 `workbench` 名称，工具数为 0，调用该服务返回 `-32603`。临时服务恰有四项，空间 ID 匹配，额外的 `list_projects` 和 `prepare_proposal` 被 App Server 拒绝。相同项目配置在不可信目录无效，对照 `workbench` 仍有 22 项，临时服务不可调用。交错重查无项目配置的旧目录和可信目录，各自配置保持生效。[OpenAI Docs MCP 设置](https://learn.chatgpt.com/docs/extend/mcp?surface=app) [OpenAI Docs 配置层](https://learn.chatgpt.com/docs/config-file/config-basic)

生成一份新的临时项目及完整 `config_text`：

```powershell
python workbuddy_agent_acceptance.py --readonly-pilot codex --codex-project-guard
```

首轮限制版桌面复验中，`/mcp` 截图显示既有 `workbench` 已禁用，临时 `workbench_ag142` 未列出。随后用户的「插件 → MCP」截图显示 `workbench_ag142` 已开启，既有 `workbench` 已关闭。中继恰有 5 条记录，完成一次 `2025-06-18` → `2025-11-25` 握手及一次 `tools/list`，原始应答含 22 项工具。工具调用和模型回合均为 0。

用户关闭旧临时聊天和项目后，监督写入 STOP 并实测端口已关闭。夹具进程退出码为 1，清理 `desktop-project` 遇到 `WinError 32/5`。只读复核确认旧临时目录 `workbench-ag142-pilot-codex-db19kz_k` 仍在，列为独立清理待办。新的四项过滤夹具已启动，等待用户在该夹具的确切项目内核对插件页和中继目录。通过核对后才发送已授权的一次只读提示。

当前 `--codex-project-guard` 还会给临时中继启用独立四项过滤。中继向客户端返回 `expected_tools` 对应的四项。目录缺项或重复时返回错误，额外 `tools/call` 在转发前拒绝，轨迹记录拒绝结果。`--pilot-check` 实测返回四项，拒绝项目列表和提案创建，六段读回与合成文本的 SHA-256 一致。停止后旧令牌返回 401，端口关闭，临时目录移除。

准备就绪后才启动新夹具。实际桌面新建本地任务并选择输出的 `desktop_project` 长路径，核对精确目录与信任。发送一次只读提示前，核实当前任务的既有 `workbench` 已禁用，且没有其他可访问真实工作台数据的连接器。核对本次独立只读凭据及中继真实握手后转发的 `tools`，须与四项 `expected_tools` 完全一致。即使桌面列表仍不显示临时项，也要满足这些可核验条件。仅有握手或无法确认禁用状态时停止。通过后使用该次 `PROMPT.txt`，核对 `workspace_id`、六段合成文本和 `source_sha256`。

2026-11-11 真实 Codex 桌面已完成一次用户发送的只读回合：两次转发目录均恰四项；capabilities、授权列表、文件信息及前两段读取成功，第三段 offset 23 返回 `not_found`、`retryable=false`，模型停止。62 字节 UTF-8 文件前两段为 `[0,11)`、`[11,23)`，同版本和 SHA-256。真实桌面调用已证实，完整读回尚未通过。源写入 `02:44:59 UTC`、最后错误轨迹写入 `03:04:59.129687 UTC`，与固定 1200 秒文件授权高度相关；真实回合为 `03:02:17–03:05:21 UTC`。原 `expires_at` 及逐调用时刻未保留，故到期原因是强时序推断。夹具自行到时退出 1、目录清理报 `WinError 32/5`，残留单列。下次用户就绪后才启动新夹具，发送前核对剩余 TTL；若需延后，重新完整批准后再发送。不得沿用过期授权或擅自增加模型回合，生产授权上限保持不变。

同日真实 Codex 桌面只读复验通过。用户另行同意并发送一轮，发送前四项工具目录已核对，文件授权有效且剩余 1077 秒。聊天 `01a1caac-282c-7130-b02c-6d57806b915b` 对应新的隔离项目，回合用时 174.567 秒。9 次调用均由 `workbench_ag142` 完成，与中继 9 次调用、0 次 `isError` 匹配。工作空间匹配，前三次为 capabilities、授权列表和文件信息，随后使用同一 `source_revision` 按 12 原始字节请求读取六段，区间为 `[0,11)`、`[11,23)`、`[23,33)`、`[33,43)`、`[43,54)`、`[54,62)`，末段 `next_offset` 为 `null`。六段均报告 SHA-256 `023887f7b2aff5b9ec2c79756c98f36676d8817c2b743f5a35cf3eddf9c04d70`。监督程序逐字比较最终代码块与合成源，确认 62 字节原文一致，首尾空格均保留。该回合仅使用临时连接器读取。监督待用户关闭项目后执行 STOP 并核对收尾。该结果覆盖真实桌面只读，桌面写入矩阵仍待验。

收尾更新：用户已关闭临时项目，监督写入 STOP，实测端口关闭。脚本清理 `desktop-project` 时报告 `WinError 32/5` 并退出 1，项目目录仍存在。最终审计未输出，旧令牌 401 未独立实测。目录残留单列。

### WorkBuddy 5.9.3 / Hy4 单项审查步骤

先从当前 WorkBuddy 的连接器管理打开配置入口，只读确认客户端指向的文件路径及当前范围。默认候选为 `~/.workbuddy/mcp.json`。若界面无法证实它是当前实际生效的用户级目标，则停在审查。若项目级列表已经有本次临时项，先只展开该行工具详情，核对中继握手，不改全局安全设置。项目级行缺失时，按前面的单条用户级方案另行审查。

2026-11-11 运行中 V5.9.3 的模型选择器显示 Hy4。「专家·技能·连接器 → 连接器 → 自定义连接器」的 MCP 服务管理未列出 `workbench_ag142`，显示一个已启用的插件项。「添加 MCP」的编辑器明确显示当前目标为 `~/.workbuddy/mcp.json`，未见项目作用域选项，检查后取消。只读解析该目标，文件与直接父目录均未见重解析点，`mcpServers` 有 0 项，无完全同名或保守归一化冲突。管理列表和该文件分别核对，因为插件项也会列入管理界面。当前项目入口未提供可展开的临时项；若新隔离项目能显示该行，仍优先核对该行握手。否则用户级备选只审查和登记一个临时对象，保留插件及其他设置。现场生成完整 JSON 后，在保存前复核目标和基线；结束时仅移除与该对象完全匹配的键，再比对其余结构与基线。

用户级候选在准备执行时用 `python workbuddy_agent_acceptance.py --readonly-pilot workbuddy` 生成，查看 `config_text` 中唯一的 `mcpServers.workbench_ag142` 和两个临时环境路径。添加前，以实际目标文件解析结果为基线，核对精确或归一化同名冲突，并仅在本机保留非目标字段。添加后再次解析，核对目标项与审查值及非目标结构。使用同一夹具根下无项目配置的新目录，在发送前核实本次目标项完成握手并指向合成空间。如还有可调用的真实工作台连接器，停在发送前。用户审批范围内最多一次 Hy4 只读回合，额度未知。结束时关闭临时任务和连接、创建 STOP、核实旧凭据返回 401、端口关闭和目录移除。随后只移除与候选匹配的条目，重读实际文件并核对整个解析结构等于基线。发现与文件授权分别计时，用户级项仍需单独移除。

2026-11-11 用户批准单条用户级登记。监督仅加入 `workbench_ag142`，实际编辑器显示预期配置路径。编辑器追加 JSON 尾空白并保存后，管理列表才出现新项和首次信任提示。用户完成信任时，原夹具已到期，0 次 initialize，0 个模型回合。夹具退出 0，旧凭据返回 401，端口关闭，临时目录移除。监督只移除精确匹配的新项，用户配置恢复为原字节。

WorkBuddy 当前使用两阶段夹具。运行 `python workbuddy_agent_acceptance.py --readonly-pilot workbuddy` 后先读取 `mode=pending_activation` 的完整候选。此阶段等待最长 1200 秒，临时客户端只有 `read` scope 和单项目范围，文件授权为空。用户级登记仍按上述单项审查，若需刷新，使用客户端编辑器保留现有结构。完成信任后只展开临时项，核对该次 `trace_path` 依次记录 initialize、协议响应、initialized、tools/list 和完整 22 项目录。监督确认合成空间和连接范围后，在终端创建该次输出的唯一 `activation_file`：

```powershell
New-Item -Path '<本次 activation_file>' -ItemType File
```

夹具消费该信号。提前触发而没有发现证据会结束试点，STOP 或等待到期也会撤销并关闭。信号有效时才经现有本机管理预览和确认授予单文件 `text_read`，输出 `mode=ready`、`file_id`、`file_expires_at` 和已生成的 `PROMPT.txt`。`file_expires_at` 为 Unix 秒，发送前用它核对剩余时间。读取窗口最多 1200 秒，第二次信号不会续期。用户同意的一轮使用本次提示，以同一临时连接器、六段至 EOF、原文及 SHA-256 匹配验收。退出时按上文核对撤销、端口、临时目录和仅移除本次用户级项。

`--readonly-pilot workbuddy --pilot-check` 用隔离 stdio 验证激活前授权为空且读取返回 `not_found`，收到完整目录后激活，六段原文匹配，提案创建返回 `forbidden`，最后撤销和清理。真实桌面的独立结果见下文。

2026-11-11 真实 WorkBuddy V5.9.3 / Hy4 只读复验通过。监督在空工作区使用隔离合成资料，按用户批准登记并信任临时用户级单项。无文件授权的等待阶段，界面显示 22/22，探测 `clientInfo.name` 为 `workbuddy-mcp-probe:custom-mcp:workbench_ag142`。监督随后触发 `ACTIVATE`，发送一条只读提示。真实回合 `clientInfo.name` 为 `workbench_ag142`，协商 MCP `2025-11-25`。capabilities、list_projects、list_file_grants、get_file_info 各成功一次，read_file 成功六次，共十次。中继未观察到该连接器上的写入请求。

Hy4 界面报告六段区间 `[0,11)`、`[11,23)`、`[23,33)`、`[33,43)`、`[43,54)`、`[54,62)`，末段 `next_offset=null`。报告 SHA-256 `023887f7b2aff5b9ec2c79756c98f36676d8817c2b743f5a35cf3eddf9c04d70` 与合成源一致，界面显示原文。UI Automation 会折叠代码块空格，本轮未独立按字节比较界面回显。STOP 后退出码 0，审计 `port_closed`、`temporary_directory_removed`、`revoked_credential_denied` 均为 `true`。监督只移除匹配的临时项，并核对用户配置恢复为添加前的原始字节。

### 新能力的零模型证据

| 能力 | Codex 实际 App Server | 原始 stdio、HTTP 和持久化回归 |
| --- | --- | --- |
| 文件和附件 | 六段完整 UTF-8 文件、逐字节和摘要核对，file_id 暂存并正式附件下载，stream 用实际 Codex 工具建会话及完成并提交，原始 bytes 由固定 loopback HTTP 助手发送 | 文件越权、逐文件批准、错版本、BOM 和多字节边界、原始流上限、暂存取消/恢复、项目与记录及文档正式附件和磁盘重读 |
| 概念图 | 精确授权，完整 v2 图 create/update，更新提交响应被夹具关闭后查询同一提案和回执，读回完整图 | 原始 MCP 图范围、完整候选、大预览、条件写和持久历史 |
| 删除 | 单条 issue 和项目删除，检查独立授权、自报被拒及原回收证据 | 五类单条、级联树和引用权限、恢复、同一回执重放及原树保护 |
| 项目 | 创建后先验证客户端看不到新项目，再独立批准访问并读取 | 同源管理、固定排序、授权持久回执及失败恢复 |
| 分类和工作流 | 知识库、概念图及项目独立附件分类创建，工作流创建，全部拒绝自报且用当前本机票据批准 | 分类三域影响和不扩权，工作流状态映射、跨项目影响及中断恢复 |
| 故障与确认 | `agent_attested` 使用程序确认夹具，`local_web` 走本机管理批准。验证旧版本拒绝、取消、原响应丢失查询、重放、错误工作空间、实际 429、重启、轮换和撤销 | raw MCP、HTTP 鉴权、限流和持久状态分别核证 |

Codex 实测使用 `mcpServer/tool/call` 和临时配置中的 `config/mcpServer/reload`，重开临时线程后验证工具 Schema 和配置身份。旧 bridge 在运行中阻止身份改变，重连后才能使用另一份临时身份。同一身份的令牌轮换可保留连接。工作台限流在首次扩大矩阵中实际触发，改用独立授权的第二份临时身份运行新能力，在主身份重启读回后单独测 429。项目附件分类授权会使旧上传许可版本失效，矩阵显式刷新同目标许可后通过。真实模型对完整预览的展示、用户后续消息和桌面行为仍需单独验收。[OpenAI Docs App Server](https://learn.chatgpt.com/docs/app-server)

WorkBuddy 探针旧断言硬编码 20 项。此次首轮已经连通但断言失败，修正为核对服务定义的完整名称集后，默认及显式探针均发现 22 项。CLI 观察结果仅覆盖连接与工具目录。上表的业务往返不能归入 WorkBuddy CLI 或桌面。

### 桌面执行前的审查项

- 每客户端各用一份一次性项目与工作台，业务库、私人凭据、源文件和任务目录彼此独立。工作台只监听 `127.0.0.1` 的动态端口。夹具固定数据为项目 `AG142 隔离项目`、一条 `AG142 单条删除`、仅含一条合成待办的 `AG142 级联删除`、三个空分类域、独立测试工作流和 `AG142-fixture.txt`。文本使用 `  UTF-8 中文与引号 "原文"`、`第二段 🧪`、`尾部空格  ` 三行，并保留末尾两个空格。仅明确批准这些合成文件及资源。准备操作记录实际 ID、初始 revision、授权和待检查的磁盘证据，令牌只保存在私人夹具文件。
- Codex 优先在新临时项目的可信项目级 `.codex/config.toml` 登记唯一 `workbench_ag142`，用已核实的 Python 程序、验收中继程序和 `--relay` 参数，私人配置通过 `WORKBENCH_PROBE_CONFIG` 指向当前夹具。官方文档支持可信项目级 MCP，安装版桌面实际发现、项目可信记录及任务历史仍须实测。试点时若该层未加载，停下核查，任何用户级登记另行展示完整项和影响后决定。[OpenAI Docs MCP 配置](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- WorkBuddy 使用本次 `--readonly-pilot workbuddy` 生成的 `.workbuddy/mcp.json`。旧验收的候选项目配置曾未加载。若这次没有实际握手，报告失败并停止。任何用户级登记另行审查，超出试点范围。[WorkBuddy MCP 配置说明](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/MCP-Guide)
- 第一批授权各一次只读试点，合计最多 2 个模型回合。Codex 由用户手工执行，WorkBuddy 由监督按用户另行授权执行，观察结果见上文。后续表格是单独审查的完整候选，每客户端最多再 25 个用户消息回合。估计试点各 10–15 次 MCP 工具调用，完整后续各 75–130 次，触发限流时按原 ID 查询并停止本轮。实际额度、费用和内部重试次数未知，后续授权时须按所用客户端确认。

### 拟运行提示与批准点

只读试点的启动命令，分别在本仓库目录的两个终端按需运行。`--pilot-check` 是自动预演，打印本次配置与完整提示后撤销并退出。真实桌面试点批准后省略 `--pilot-check`。Codex 直接开始 20 分钟窗口。WorkBuddy 先等待最多 20 分钟完成发现，再按前述信号激活最多 20 分钟的文件读取窗口。

```powershell
$env:PYTHONIOENCODING = 'utf-8'
python workbuddy_agent_acceptance.py --readonly-pilot codex --pilot-check
python workbuddy_agent_acceptance.py --readonly-pilot workbuddy --pilot-check
```

正式启动的两条命令。

```powershell
python workbuddy_agent_acceptance.py --readonly-pilot codex
python workbuddy_agent_acceptance.py --readonly-pilot workbuddy
```

终端输出中的 `config_text` 是本次唯一连接器的完整项，`config_path` 指向临时项目文件。获得文件授权后才生成 `PROMPT.txt`，实际路径取终端的 `prompt_path`。`source_sha256` 用于核对原始工具返回。检查桌面关于页的实际版本，再打开输出的 `desktop_project`。使用 WorkBuddy 用户级方案时改用前述无项目配置目录。两者各使用一个新任务。工具界面出现 `workbench_ag142` 后确认中继的 initialize、initialized 与 tools/list 证据。信任完成后若展开仍无握手或目录，停止夹具并记录缺口。真实用户级配置变更按单条候选审查。

试点逐字提示的模板。运行时由脚本填入全部实际 ID。

```text
只使用 workbench_ag142 对应的 MCP 工具。先查询 capabilities，核对空间 <空间 ID>，再查项目 <项目 ID>。列出本次可见的工具名和协议证据。查找已批准的 AG142-fixture.txt（file_id <文件 ID>），用 get_file_info 的 source_revision 和每段 next_offset，按每段 12 原始字节读到结束。把合成文本原样放入代码块，另列各段字节区间和服务返回的 SHA-256。仅做上述读取。工具缺失、空间不符或任一分段失败时报告原错误并停止。不要使用终端、读取路径、改配置或提交。
```

本次试点只有 `read` scope、一个项目及一个仅 `text_read` 的文件授权。收尾时先关闭本次任务和临时项目，待桌面关闭本次中继连接后，在另一终端创建启动输出中的唯一 `stop_file`（`New-Item -Path '<stop_file>' -ItemType File`）。脚本撤销身份、检查原令牌返回 401、停止服务并清理夹具。保留最终 `audit` 脱敏摘要和用户展示的合成原文。此次约束对两份夹具分别生效，预演中的 ID 已失效。

早期本机预演实测两份普通夹具均成功发现 22 项工具，读取同一个合成原文的六段且校验完整 SHA-256，创建提案返回 `forbidden`，无提案文件。两份 ready/STOP 路径也已实测，旧令牌拒绝、进程退出、端口关闭和临时目录不存在。预演的 stdio 请求来自验收夹具，真实桌面记录见上文。

两客户端真实桌面只读已通过，WorkBuddy 概念图新建 `local_web` 单案也已通过。其余写入、确认与故障对照仍待按客户端验收。下一步先复用固定图和最小授权做 Codex 同类单案。后续每次只执行已批准的范围。固定提示为「仅使用本次临时 MCP 和下列固定 ID。执行本行操作，展示当前完整候选、全部变更、警告、版本和摘要，然后停止。任何权限或版本错误先报告并停止，禁止自行换范围或新建替代请求。」每行操作文字与夹具的实际固定 ID 一起附在提示末尾。各行需要的本机授权先单独预览与批准，避免变更授权后沿用旧票据。以原结果读取为准。

| 操作文字 | 后续用户消息或本机操作 | 回合上限 |
| --- | --- | --- |
| 新建标题 `AG142 关系图` 的完整 v2 图，两个节点 `甲`、`乙`，一条 `联系` 边。之后读取同一图，保留结构，仅把标题改为 `AG142 关系图更新` 并生成更新预览 | 新建及更新分别在之后的新消息发送「我已核对并确认此提案 `<ID>` 的版本 `<版本>`、摘要 `<摘要>`。只提交该版本一次并查询原回执。」 | 4 |
| 分别用指定 `file_id` 和已通过独立 HTTP 助手写入的合成原始流创建正式附件。固定项目、文件名、长度、摘要与链接选择。file 路径采用 `agent_attested`，stream 路径采用 `local_web` | file 采用上述新消息。stream 由本机独立批准后，发送「查询 `<ID>` 原回执和固定附件；不要提交或重传。」原始流由本机助手固定 PUT 写入，MCP 客户端仅建立会话、查询、完成及准备正式提案 | 4 |
| 依次为 `AG142 单条删除`、`AG142 级联删除`、`AG142 新项目`，知识库、概念图、项目独立附件三个 `AG142 新分类`，以及 `AG142 新工作流`，生成 7 份独立提案。每次先展示完整范围。使用对应的 `local_web` 授权 | 每项先核对一次自报提交拒绝，再由用户在本机网页阅读完整当前版本后批准。项目创建后，先核查客户端仍不可见，再单独审批项目访问。每项后续消息只查询原回执和该项状态 | 14 |
| 依夹具清单执行一次取消与旧版本拒绝，一次固定响应丢失后的原提案查询与同 ID 重放，一次重启后的错空间、限流、轮换和撤销只读查询 | 仅使用当前夹具预先列出的对照 ID。错空间及限流由隔离协议助手注入，不在真实桌面复制凭据或连续发起大量模型工具调用。响应丢失后先查原提案，终止态不得产生第二条正式结果 | 3 |

完成或中止后，先撤销该夹具的所有身份与文件/暂存授权，确认原客户端只读调用拒绝。仅移除本次临时连接器，关闭本次临时任务并确认任务历史是否保留。关闭服务和中继，核对进程退出和端口关闭，再清理本次任务根目录。中继只留工具名、版本、布尔结果和错误码，不留令牌、参数和正文。桌面结果由用户展示和原始工具证据配合磁盘重读确认。若实际桌面隔离、费用或配置例外未获同意，可提交已完成的直接调用与协议证据并保留缺口。

### 首个真实桌面写入试点：概念图新建（2026-11-12）

先验一个 WorkBuddy V5.9.3 / Hy4 的 `local_web` 单案。固定合成输入为 `AG142 图隔离项目` 中的 v2 图 `AG142 关系图`，分类 `未分类`，焦点问题 `甲与乙有什么联系？`，节点 `a`（甲，坐标 100、120）、`b`（乙，坐标 420、220），关系 `edge` 从 `a` 指向 `b`、标签 `联系`。脚本按现有领域归一化生成固定提示，包含实际项目 ID 和所有样式、视口、节点、关系字段。固定请求 ID 为 `ag142-graph-pilot-create`，图 ID 与时间由服务分配。普通网页图授权表单将新建和更新合并选择，本试点经现有管理接口仅批准同一空项目的图读和 `create`，最低确认 `local_web`。基础权限为 `read`、`propose`、`commit`，没有旧业务项目或知识库范围。启动时的休眠图读取配置须另行批准才生效。

```powershell
$env:PYTHONIOENCODING = 'utf-8'
python concept_map_pilot.py --check
python concept_map_pilot.py
```

第一条 Python 命令只用一次性数据、原有中继和程序化本机批准做预演。第二条才启动待接入夹具。它输出完整 `grant_preview`，最多等待 540 秒。以下步骤使用该次输出，切勿沿用预演 ID。

1. **用户亲自批准范围。** 核对完整 `grant_preview` 的空间、身份、空项目、图读取和仅 `create`、`local_web`。用户确认后，由本人或监督在本机执行 `New-Item -Path '<本次 approval_file>' -ItemType File`，受理该次固定授权；这一步只授予权限。夹具输出 `mode=ready`、本机地址、完整配置、提示和唯一 STOP 路径，等待最多 1200 秒。
2. **用户亲自同意本次连接器及信任。** 核对 `config` 唯一项 `workbench_ag142_graph`、Python 程序、固定中继参数、两个临时环境路径和用户级可见范围。按此前 WorkBuddy 单项方案复核实际配置与基线，只加此项，打开输出的空 `desktop_project`。首次信任由用户完成。只展开该项并查看 `trace_path`，核对 initialize、协商 `2025-11-25`、initialized、tools/list 与 `expected_catalog` 的 22 项。发送前核对没有可调用的真实工作台连接器。目录是通用工具目录，权限以 `capabilities` 的 `kind_operations={"concept_map":["create"]}`、生效图读写家族及资源为准。
3. **用户确认使用 Hy4 发送本次预览提示。** 预览阶段只调用 `workbench_capabilities`、`workbench_list_concept_maps`、`workbench_prepare_proposal`、`workbench_preview_proposal`。展示完整图、原图、差异、警告、版本、摘要和执行依据后停止。监督从该次临时工作台 `GET /api/concept-maps` 或夹具 `data/concept-maps` 只读核对正式图仍为空。记录本次提案 ID、预留图 ID、版本和摘要；错误时查原提案。
4. **用户亲自在隔离网页批准正式写入。** 打开 `workbench_url` 的「提案管理」，在本次 ID 上点击「查看完整预览」。等待完整只读画布和全部明细载入，核对图信息和视口、两个节点、一条关系、完整原图和差异、警告、版本、摘要与完整保存依据。与桌面预览一致后，用户点击「批准并入库」并在独立确认框再次确认。此单案采用本机网页批准。若预览有变化或加载失败，停止批准并核查原提案。
5. 记录网页原回执及正式图 ID。监督从临时盘读取 `data/concept-maps/<图 ID>.json`，确认只有一张图，内容、节点及边 ID 与预览一致，原始字节 revision 与回执一致；确认只有一份原回执。如用户同意追加查询回合，可让 Hy4 只调用 `workbench_get_proposal` 和 `workbench_get_concept_map`，核对同一回执和图。预演已覆盖同批准请求重放，实际结果不明确时先查询原操作，保留原 ID。
6. 关闭本次临时任务和连接，创建该次 `stop_file`。核对脚本退出、旧凭据被拒、端口关闭和目录移除；脚本的收尾摘要列出图与回执数量。只移除与该候选完全匹配的用户级项，复核配置基线。若目录仍被占用，记录残留与实际退出状态。

隔离预演已通过：22 项目录、有效图操作只有 `create`、批准前 0 图和 0 回执、自报确认 `confirmation_required`、本机预览与 Agent 候选摘要及完整拟保存图一致、批准后 1 图及 1 原回执、同批准请求重放返回原结果且图原字节不变、原图重读及 revision 核对、更新拒绝、401 撤销、端口关闭和目录移除。既有浏览器专项另验证完整画布、明细、差异、加载失败禁批、真实网页批准和重开。以上为隔离预演。真实桌面模型、信任和用户批准的独立证据见下节。

### WorkBuddy 真实桌面概念图新建结果（2026-11-12）

- 用户同意 WorkBuddy V5.9.3 / Hy4 限定单案，亲自信任 `workbench_ag142_graph`，随后在隔离网页亲自批准当前版本 1。桌面协商 MCP `2025-11-25` 并发现 22 项。真实模型端在 `notifications/initialized` 前发 `tools/list`，收到 `-32002`，随后自动按顺序完成。中继记录成功 `capabilities` 一次、`list_concept_maps` 两次、`prepare_proposal` 一次、`preview_proposal` 一次，未见 `commit_proposal`。模型报告工具框架曾把参数当字符串并沿用原 `request_id` 重试。中继证实一次成功的真实 prepare，该报告不足以定位字符串问题的来源。
- 桌面完整展示候选、原图、差异、警告和执行依据。批准前服务端提案 `fca2a40d-5070-4359-beb8-cf64d25a28fe` 为 `previewed`，版本 `1`，摘要 `9ff74896e827a69c6ce95a05978580a4d799d99a9bd6e029f6c3217986e73188`，预留 `CMAP-0001`。固定候选匹配，正式图和回执均为零。用户批准后为 `committed`，正式图和回执各一份。磁盘完整候选字段相等，原始文件 SHA-256 `0cb010f52cc069fce4f7c4041b148b4b470f6287eaf528b8be811dcec93d4991` 与原回执吻合，提案内回执与独立回执一致。真实桌面没有追加模型查询回合，重放证据仍来自隔离预演。
- STOP 先撤销临时凭据并校验旧凭据 401，再关闭服务。脚本在临时目录清理遇 `WinError 32/5` 后退出 1，最终 audit JSON 未输出，监督实测端口已关闭。用户配置恢复原始字节，刷新后桌面缓存仅保留原 `miora`。锁释放后空 `desktop-project` 已移除。根目录余项的工具删除被自动审批以 `blocked by policy` 拒绝，用户随后手工删除，监督独立运行 `Test-Path` 得到 `False`，残留清理闭合。

### Codex 可信项目同类单案（隔离预演通过）

复用 `concept_map_pilot.py` 的固定 v2 输入、单空项目读与仅 `create` 授权和 `local_web` 确认。Codex 启动命令如下。使用 `--check` 在一次性 `CODEX_HOME` 和临时项目预演，省略 `--check` 才等待用户确认后生成当次真实桌面候选。

```powershell
$env:PYTHONIOENCODING = 'utf-8'
python concept_map_pilot.py --client codex --check
python concept_map_pilot.py --client codex
```

脚本只在临时项目生成 `.codex/config.toml`。六项中继过滤与项目 `enabled_tools` 使用同一名单，后两项供已同意的结果查询回合。正式试点把发现和执行分开，完整授权审查在两者之间：

1. `mode=pending_discovery` 给出 `desktop_project`、`config_path`、`config_text`、`trace_path`、`expected_catalog` 和 `discovery_file`，最多等待 1200 秒。此时身份仅有休眠配置，尚无生效图授权，也未输出模型提示。用户先核对当次候选，打开精确临时项目并确认信任。监督核对继承的 `workbench` 已禁用、无可调用的真实工作台连接器，并从中继确认该次 initialize、服务协议响应、initialized、tools/list 及恰六项目录，再执行 `New-Item -Path '<本次 discovery_file>' -ItemType File`。提前信号缺少握手证据时退出，撤销身份并清理。
2. `mode=grant_review` 只在发现核对后输出当次完整图授权，最多等待 540 秒。用户检查空间、身份、单空项目、图读取、仅 `create` 和 `local_web`，明确同意后创建当次 `approval_file`。这个信号只授予上述图能力。它不批准任何提案。任一等待阶段到期或收到 STOP 都走撤销及清理。
3. `mode=ready` 确认图授权已生效，输出固定 `prompt` 和 Unix 秒 `execution_expires_at`，此时才开始 1200 秒的预览与批准窗口。用户确认所选模型和这次预览回合后使用当次提示。随后由用户在隔离网页独立批准当前完整提案版本。执行窗口是夹具的运行期限，到期时关闭服务并撤销临时客户端。

```toml
[mcp_servers.workbench]
enabled = false

[mcp_servers.workbench_ag142_graph]
enabled = true
command = "<本次夹具的 Python 路径>"
args = ["<本次夹具的中继程序路径>", "--relay", "--relay-graph-pilot"]
enabled_tools = ["workbench_capabilities", "workbench_list_concept_maps", "workbench_prepare_proposal", "workbench_preview_proposal", "workbench_get_proposal", "workbench_get_concept_map"]

[mcp_servers.workbench_ag142_graph.env]
WORKBENCH_PROBE_TRACE = "<本次夹具轨迹路径>"
WORKBENCH_PROBE_CONFIG = "<本次夹具私人客户端配置路径>"
```

已在 Codex App Server `0.167.0-alpha.3.2` 的临时环境中做零模型对照。相同项目 TOML 放入不可信目录时，模拟继承的 `workbench` 仍有 22 项，新项不可见；可信目录内旧项无法调用，临时项恰六项，轨迹完成 initialize、initialized 和目录应答。直接探测确认中继转发前拒绝 `commit_proposal`，App Server 业务调用确认图更新及 issue 新建被服务拒绝。可信项目的同一固定新建完成预览、零正式图和回执、本机程序化批准、唯一图和回执、原审批重放及字节 revision 核对。

真实桌面发送前确认实际工作目录、项目受信任、旧项禁用、临时项目目录与轨迹六项工具，以及合成空间匹配。用户核对并同意精确图授权、项目级候选与信任、所选模型的一次预览回合。模型按固定提示完整展示并停止，监督核对零正式图和回执后，用户在隔离网页独立批准当前版本。随后核对原回执及正式图原始字节。结果查询回合按用户同意执行。真实用户级 Codex 配置无需登记新项。

收尾先关闭桌面任务与临时项目，等待本次中继退出，再写 STOP。夹具撤销凭据、实测旧凭据 401、关闭服务并核对端口，随即输出 `mode=service_stopped`。目录移除后输出 `mode=stopped`。若根目录仍被占用，保留前一阶段审计，输出 `mode=cleanup_failed`、错误码和目录未移除状态，退出 1。用一次性目录的 Windows 文件锁实测 `WinError 32`，确认服务审计先出现，端口独立检查已关闭。释放锁后由测试外层临时目录收尾。正常 STOP 验证退出 0 和目录移除。真实 Codex 桌面模型与用户批准仍待验收。

2026-11-12 真实 Codex 桌面首轮证实项目级发现。用户同意精确授权和项目级候选，临时本地项目已建立，用户确认看到了临时 MCP。中继 `codex-mcp-client 0.167.0-alpha.3.2` 提出 `2025-06-18` 并协商 `2025-11-25`，完成 initialized 和 tools/list。目录恰为 capabilities、list_concept_maps、get_concept_map、prepare_proposal、preview_proposal、get_proposal。20 分钟窗口结束前只有上述五条协议记录，零工具调用、零正式图、零回执。没有模型回合证据，无法区分提示未发送和客户端未调用，概念图新建仍待验。

用户移除临时项目。夹具退出 0，`service_stopped` 和 `stopped` 证实 `revoked_credential_denied=true`、`port_closed=true`、`temporary_directory_removed=true`。独立复核临时项目已从 Codex 项目列表消失，夹具根目录不存在。此次没有用户级 MCP 登记。

分阶段复验在零模型 App Server 中实测：同一临时连接器在发现及授权审查时均没有生效图权限，完整固定图 prepare 在授予前由领域授权拒绝。缩时对照让发现等待超过执行窗口长度，批准后仍获得独立的新执行窗口。隔离另测无发现超时、缺少握手的提前发现信号和预放的授权信号，均未授予权限，随后撤销并清理。两端 `--check` 的完整预演仍通过。此次分阶段核查使用缩短窗口，未等待真实 20 分钟，也未启动桌面模型。

### Codex 真实桌面概念图新建结果（2026-11-12）

- 分阶段夹具先在可信临时项目发现。用户确认插件页临时项开启、旧 `workbench` 禁用，随后报告 `/mcp` 菜单未列临时项。监督核对实际路径及信任映射。五条中继记录确认 `2025-06-18` 至 `2025-11-25` 协商及恰六项工具，随后才审查和批准本次项目的图读取与仅 `create`，启动独立 1200 秒窗口。
- 用户发送一次，聊天 `01a1cbbd-ebbe-7bf0-928b-c696c8f40687` 的工作目录匹配临时项目，回合用时 191.735 秒。聊天和中继均记录 `workbench_ag142_graph` 的 capabilities、list_concept_maps、prepare_proposal、preview_proposal 各一次成功，无 commit。最终消息约 5278 字符，包含完整候选、原图、差异、警告、版本摘要和执行依据。
- 用户批准前，提案 `a5985a37-1e69-49ed-b29e-89c05bfdbe85` 为 `previewed`，版本 `1`，摘要 `48021c74c829f88d4aae83af5a74ad5e877d14d472d4d6a638606c892bdb2b9c`，候选与固定合成图匹配，正式图和回执均为零。用户在隔离网页独立批准后，提案为 `committed`，一张 `CMAP-0001` 和一份回执，完整字段一致。图文件原始字节 SHA-256 `aab1996f38c0a3599f47935c8313e16b08e41d9e8422e8969605e34f14ce0f5c` 与回执吻合，提案内原回执等于独立回执文件。没有追加桌面查询或真实桌面重放。
- 两端真实桌面同类 `concept_map/create` 与 `local_web` 单案均通过。其余写入与确认矩阵仍待验。
- 用户退出并移除临时项目，监督独立复核项目列表已无该目录。STOP 先输出 `service_stopped`，其中 `discovery=verified`、`graph_granted=true`、`graph_count=1`、`receipt_count=1`、`revoked_credential_denied=true`、`port_closed=true`。之后输出 `cleanup_failed`，`errno=13`、`winerror=32`，进程退出 1。自动审批以 `blocked by policy` 拒绝工具重试删除剩余夹具目录。后续独立 `Test-Path` 确认为 `False`，目录清理闭合，移除方式未确认。

### 下一单案：更新同一张隔离概念图（2026-11-12）

更新试点使用新的临时空间，由夹具通过领域仓储预置同一份合成 v2 图。它仅将标题从 `AG142 关系图` 改为 `AG142 关系图更新`。图 ID、项目、分类、焦点、主题、视口、节点与关系的全部字段保持原值。授权为指定一个图 ID 的 `read` 和仅 `update`，要求 `local_web`，没有创建图的授权，也不使用上一轮的图或凭据。

```powershell
python concept_map_pilot.py --client codex --operation update --check
python concept_map_pilot.py --client workbuddy --operation update --check
```

两条均为隔离预演。Codex 使用实际 App Server 和六项限制，WorkBuddy 使用隔离 stdio 和 22 项通用目录。预演覆盖完整图读取与原始 revision、预览与批准前的原文件字节保持、一次原回执和唯一历史、历史字节与原图完全一致、正式图 ID 与非标题字段不变、同批准请求幂等重放、旧 revision 返回 `revision_conflict` 以及创建拒绝。两个临时服务均核对撤销、端口关闭和目录清理。

真实桌面安排确定后，先选一个客户端，去掉对应命令的 `--check`。Codex 沿用 `pending_discovery`、`grant_review` 和 `ready`，WorkBuddy 沿用单项用户级登记、信任和握手核对。用户分别确认当次固定图的授权和连接器配置、信任、模型及预览回合。`ready` 输出目标 ID、原始 revision 和完整固定提示。模型先调用 capabilities、list_concept_maps、get_concept_map，核对同一空间、唯一目标、原 revision 和完整原图，随后 prepare、preview 并展示完整候选、原图、全部差异和执行依据，等待本机批准。若原 revision 或任何非标题字段不同，停止并核查。

独立批准前监督核对仍只有一张原图，SHA-256 等于 `base_revision`，尚无更新历史或回执。用户在隔离网页核对同一提案的当前版本、摘要、完整画布与明细、标题差异、警告和保存依据，亲自批准。随后核对原 ID 文件的当前哈希和唯一回执、历史原始字节和 `base_revision`、全部非标题字段。真实桌面额外查询回合和负向操作另行安排。关闭本次项目和连接后写 STOP，并按之前的步骤核对撤销、端口、目录及配置恢复。

WorkBuddy V5.9.3 / Hy4 真实更新单案通过。用户同意单案，沿用已信任的 `workbench_ag142_graph`。实际协商 `2025-11-25`、目录 22 项，初始化前一次 tools/list 返回 `-32002` 后自动恢复。capabilities、list_concept_maps、get_concept_map、prepare_proposal、preview_proposal 各成功一次，无 commit。界面核对了完整原图、候选、差异、警告、执行依据及提案标识，模型停止等待。

提案 `98f06e0f-25f3-4b61-bfa4-e9ca1d6efc1a` 版本 `1`，摘要 `55007f61df7a2eff32ced2f07040d6cf4f357dc3cfdde91a84c884c98ee8f6f6`。批准前仅 `CMAP-0001`，原 SHA-256 `f06c9530ddbf7189c4433c38e40fc658265ad212f4f460d1f81b101da098f563`，零历史、零回执。用户在隔离网页亲自批准后，同一图只有 `title` 和 `updated` 改变，完整候选匹配，历史逐字节等于原图且与 `base_revision` 匹配。当前 SHA-256 `619c59e9ad6aaf72b7419e79d398eb4268ab6442c30f5c6a83399e15cc83737f` 与原回执相同，提案内与独立回执一致。无追加桌面回合，负向和重放证据来自隔离预演。

退出任务后恢复用户配置并刷新桌面缓存，仅原 `miora` 保留。STOP 退出 0，旧凭据被拒、端口关闭、临时目录移除并独立复核。

Codex 真实更新同样通过。用户同意并确认可信临时项目及临时 MCP 启用、旧 `workbench` 禁用。打开 `/mcp` 后中继记录五条握手，协商 `2025-06-18` 至 `2025-11-25` 并返回恰六项，之后才批准 `CMAP-0001` 的读取和仅更新，采用 `local_web`。真实聊天 `01a1cdbd-4836-7e23-bca9-e21dc04fb36c` 工作目录匹配，回合用时 221.904 秒，聊天与中继的 capabilities、list_concept_maps、get_concept_map、prepare_proposal、preview_proposal 五次均成功，无 commit。完整答复 5518 字符，包含图、原图、差异、警告、版本摘要和执行依据。

提案 `c48e2768-64bf-4b56-9efa-362ef99b862c` 版本 `1`，摘要 `a50977f7bd23ca4acf4456de5a0eb5d9c44eaf0a30e584d62fb94ba7b73a3401`。批准前一张图，原 SHA-256 `7be365a298b116000df55eb8d33cb30a1261ebb0745ea64b378bb523760364dd`，零历史零回执，固定候选相等。用户在隔离网页亲自批准后同一图 ID，只有 `title`、`updated` 变化，一张图、一份历史、一份回执。历史原字节一致，新 SHA-256 `1841dd7571fc86fbf6e6fea7692aabc96b5c34ef209c81ba732704108e3f0bac` 与回执匹配，提案内回执与独立回执一致。

用户退出并移除项目，监督核对列表已无该项目。`service_stopped` 证实 401、端口关闭及一图一回执，随后 `cleanup_failed` 报 `errno=13`、`winerror=32`，退出 1。自动审批以 `blocked by policy` 拒绝工具重试删除该次新残留，待用户手工处理。该残留与已经核实不存在的 Codex 新建目录独立。两端真实概念图新建、更新均通过，其余矩阵待验。

### 正式附件两来源隔离预演与桌面交接（2026-11-12）

原 Codex App Server 矩阵已证明两种来源可完成正式附件。原预演使用一个同时允许两种来源的策略，两条路径都走 `agent_attested`。当前 `python codex_agent_acceptance.py` 在同一隔离矩阵依次使用两个互斥策略，每次建立新的暂存会话。固定数据为 62 字节合成 UTF-8 文本，SHA-256 `023887f7b2aff5b9ec2c79756c98f36676d8817c2b743f5a35cf3eddf9c04d70`。两条均使用空分类、`insert_link=false` 和同一个隔离项目的独立附件位置。

| 来源 | 本机前置授权与传输 | 正式提案确认 |
| --- | --- | --- |
| 指定 `file_id` | 先单独批准一个合成文件的 `attachment_source`。策略只接受当前 `file_id` 与 `source_revision`，原始流关闭，批准暂存和正式附件。Agent 从授权元信息读取摘要，用固定文件来源创建暂存，不读取路径或正文 | `agent_attested`。先完整展示候选，等用户之后的新消息明确确认当前提案版本和摘要，再提交一次 |
| 独立原始流 | 独立策略仅允许 stream，文件列表为空。Agent 建会话，本机独立认证助手只向该会话固定 loopback `PUT` 端点发送声明的 `application/octet-stream` 字节。Agent 核对暂存结果并完成 | `local_web`。Agent 展示完整当前预览，用户在隔离网页独立批准；自报提交应被拒绝 |

两条都先让 `complete_upload` 得到 `ready`，再由 `get_attachment_target` 取当前目标 revision。`prepare_proposal` 绑定 `attachment/create`、目标 ID、目标 revision 和本次 `upload_id`；`preview_proposal` 展示完整目标、来源元数据、文件名、字节数、摘要、附件元数据差异、版本、警告与保存依据。`ready` 和预览阶段均应没有新增正式附件或回执。确认后对照原回执、暂存 `consumed`、重开仓储的正式文件和下载字节。

Codex App Server `0.167.0-alpha.3.2` 零模型预演通过。file 来源只授 `attachment_source`，读取正文被拒；`user_confirmed=false` 返回 `-32602`，没有正式写入，程序化对话声明提交后，同一请求返回原回执。stream 只接收独立助手发送的原始字节，自报提交返回 `confirmation_required`，随后以本机管理票据程序化批准，客户端查询原回执。两条分别仅增加一份附件和回执，暂存均为 `consumed`，重开仓储读回及 HTTP 下载均与固定合成源一致。附件浏览器专项通过，覆盖共同授权、完整预览、网页批准、项目结果和下载。上述是协议及隔离证据，真实桌面的完整展示和后续用户消息仍待验证。

下一次桌面先安排单个 file 来源。为该次临时工作台固定项目、合成源、临时客户端及策略窗口。用户先审查并批准文件用途和该项目的共同暂存及正式附件策略，再确认临时连接器与首个预览回合。预览回合只暂存并展示完整提案，停止等待。用户核对该次实际提案 ID、版本和摘要后，在新的消息明确写「我确认此提案 `<ID>` 的版本 `<版本>`、摘要 `<摘要>`。只提交这个版本一次，查询原回执。」原始试点请求、界面文字或程序化预演均不作为桌面确认。提交结果不明确时先 `get_proposal` 查询原提案。独立原始流留在后续单案，实际桌面运行仍需安排本机助手和独立网页批准。

#### Codex 可信项目的 file 来源单案

```powershell
$env:PYTHONIOENCODING = 'utf-8'
python attachment_pilot.py --check
python attachment_pilot.py
```

`--check` 使用安装版 App Server、临时可信与不可信目录及程序化声明，零模型复核完整链路。省略该选项启动待用户操作的隔离服务。固定项目 `AG142 附件隔离项目`、文件 `AG142-attachment.txt`、62 字节、仅 `attachment_source`、精确文件 ID 和 revision。基础权限仅一个隔离项目、既有项目访问所需的 `issue` 类型及 `read/propose/commit`。验收中继对 `prepare_proposal` 另行限定为 `attachment/create`，其余类型和操作在转发前拒绝。项目 TOML 禁用旧 `workbench`，仅启用 `workbench_ag142_attachment` 的九项工具：capabilities、get_file_info、create_upload、complete_upload、get_attachment_target、prepare_proposal、preview_proposal、commit_proposal、get_proposal。正文读取工具未开放，提交仅接受本次已解锁的提案 ID、版本与摘要。

1. `pending_discovery` 提供当次 TOML、临时项目、目录及信号路径，等待 1200 秒。用户核对配置并信任临时项目。监督核对旧项禁用、实际临时工作目录和中继完整九项目录后，以 `New-Item -Path '<本次 discovery_file>' -ItemType File` 继续。此阶段无文件授权或暂存策略。
2. `review_file` 和 `review_policy` 依次输出完整本机预览，每项等待 540 秒。用户分别同意文件用途及共同暂存和正式附件策略后，才各自创建当次 `approval_file`。策略绑定单项目和该文件，关闭原始流，最低确认方式为 `agent_attested`。批准这两项仅开启能力。
3. `ready_preview` 开始 1200 秒执行窗口并输出首条固定提示。用户同意所选模型后发送一次。模型只准备并完整展示。夹具观察到精确候选处于 `previewed`、暂存为 `ready`、零附件零回执，才输出 `await_user_confirmation` 的提案标识及信号。等待真实回合结束，人工核对完整预览和同一标识。
4. 用户在监督对话明确同意实际提案 ID、版本和摘要后，监督才创建 `ENABLE_COMMIT` 对应的 `approval_file`。夹具重核当前版本并输出 `ready_commit`。用户把这条固定确认作为之后的新消息发送到原桌面聊天。信号只让中继转发匹配的提交，正式确认由用户的新消息表达，服务仍按原 `agent_attested` 契约处理。两条提示共享 `execution_expires_at`，解锁不续期。结果不明先查询原提案。
5. `committed` 记录原回执、磁盘摘要及消费状态。监督核对一份独立附件和回执。关闭临时聊天及项目、等待中继退出，再创建 STOP。保留先输出的 `service_stopped`，另核对目录清理。使用项目级配置，不登记用户级 Codex MCP。

安装版 App Server 的 `--check` 和真实启动参数下的隔离程序驱动均通过。可信目录九项与继承项禁用、不可信目录的对照、确认前提交拒绝和零附件零回执、错误摘要拒绝、精确提交和原回执重放、暂存消费、重开磁盘字节、旧凭据 401 及端口和目录收尾均已核对。隔离程序驱动实际经过两个授权提示与两个模型提示的输出，未发送桌面消息。

#### Codex 真实桌面单文件附件结果（2026-11-12）

- 用户确认可信项目和旧连接器禁用。中继两次完成从 `2025-06-18` 至 `2025-11-25` 的握手，目录均恰九项。授权仅覆盖同一空隔离项目的单文件 `attachment_source` 和 file-only 正式附件新建策略，固定合成源 62 字节。
- 真实聊天 `01a1cdde-2b26-7540-9173-49da7d6e5716` 第一回合用时 216.475 秒。capabilities、get_file_info、create_upload、complete_upload、get_attachment_target、prepare_proposal、preview_proposal 各成功一次。未调用 commit 或读取文件正文。完整预览核对版本和摘要，暂存 `ready`，正式附件与回执均为零。
- 用户在监督聊天明确批准提案 `452ef21b-445d-4d2b-9179-a8e4a64ab0ec` 版本 `1`、摘要 `02cb485e48d7340137b252f90d3bdd800e85b840430920ac1b88666eadcc6e3c`。监督解锁后，用户亲自在原桌面聊天发送绑定同版本和摘要的新消息。第二回合用时 26.983 秒，`commit_proposal`（`agent_attested`、`user_confirmed=true`）和 `get_proposal` 各成功一次。两轮共九次成功调用，均使用临时连接器。
- 重开仓储核对唯一附件 `ASSET-412cf7bab20756538a519e81f46c5b3e` 和唯一原回执。磁盘 62 字节与合成源逐字节相同，SHA-256 `023887f7b2aff5b9ec2c79756c98f36676d8817c2b743f5a35cf3eddf9c04d70`。暂存为 `consumed`，原提案与回执一致。真实桌面未重放。
- 夹具自然到期，`service_stopped` 保留一份附件、一份回执、相同 SHA-256 与 `consumed`，并确认 `revoked_credential_denied=true`、`port_closed=true`。随后 `cleanup_failed` 报 `errno=13`、`winerror=32`，进程退出 1。项目仍在 Codex 列表，临时根仍在，等待用户退出并移除。该次残留未尝试自动删除，与较早的图更新残留分开跟踪。

#### Codex 可信项目的独立原始流单案

```powershell
python attachment_pilot.py --source stream --check
python attachment_pilot.py --source stream
```

复用同一夹具、固定项目和 62 字节合成数据。临时项目仍禁用继承的 `workbench`。本次仅提供七项工具：capabilities、create_upload、complete_upload、get_attachment_target、prepare_proposal、preview_proposal、get_proposal。中继只转发 `attachment/create` 类型的准备请求，始终拒绝 `commit_proposal`。无文件授权、无 `file_id`、无上传字节的模型工具。`review_policy` 要求明确批准 `stream=true`、`files=[]`、单项目共同暂存与正式附件策略，最低确认方式 `local_web`。

1. 按该次 `pending_discovery` 核对项目级配置、信任、旧项禁用及实际中继七项目录，再创建 `discovery_file`。用户核对并同意当次完整策略后创建 `approval_file`。`ready_stream_session` 才开始 1200 秒窗口，用户同意所选模型后发送首条固定提示，仅创建会话并停止。
2. `await_stream_put` 只在仓储恰有一个符合当次固定请求的会话时输出。核对原模型返回和监督看到的 `upload_id`、长度、摘要，按本次安排创建 `send_file`。本机助手在发送前重新核对工作空间、客户端、目标、策略、请求、状态、文件名及长度摘要，随后使用自身持有的隔离凭据，向固定 `127.0.0.1` 端口的原会话 PUT 62 字节。信号不接受 URL、路径、ID 或字节输入。遇错误先查原会话，夹具不会自动重传。
3. 服务器封存证据匹配后才输出 `ready_stream_preview`。用户发送第二条固定提示，模型完成原会话、读取当前目标、生成并完整展示 `local_web` 提案后停止。`await_web_approval` 标明当前 ID、版本、摘要和零正式附件零回执。监督等待实际完整展示后核对，同一当前版本由用户在隔离网页独立批准。两个提示与批准共享同一执行窗口。
4. `committed` 输出原回执、磁盘摘要和消费状态。监督核对唯一附件和回执，关闭临时聊天、项目与中继后 STOP，分别核对服务审计和目录结果。若需让模型查询原回执，另安排只查询回合。

安装版 App Server 的流 `--check` 和普通启动参数的隔离程序驱动均通过。预演验证固定助手拒绝其他会话、固定原始字节封存、客户端批准前后均无法提交、完整本机预览及原批准重放、批准前零附件和回执、批准后唯一原回执和正式文件、磁盘字节匹配及暂存消费。旧凭据 401、端口关闭和目录移除通过。file 路径回归及 19 项中继专项通过。网页批准在隔离预演中通过管理 API 执行，真实桌面和真实用户批准仍待安排。

#### Codex 验收专用项目目录复用

真实新建和更新均在项目列表移除、旧凭据 401 和端口关闭后出现 `WinError 32`。隔离文件锁对照也复现了清理失败，现有证据未定位真实桌面具体句柄。建议先将临时桌面项目目录与每轮业务数据、私人凭据和轨迹目录分开，保持每轮独立空间。即使项目目录仍被占用，也可独立回收已停服的数据和凭据，并单独报告项目目录状态。

夹具现在支持显式 `--anchor`。仅为隔离验收创建一个新空目录，绝对路径末段须以 `workbench-ag142-anchor-` 开头。初始化不采用既有目录，不登记或信任真实 Codex 项目。下列命令仅用隔离环境预演：

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$anchor = Join-Path $env:TEMP ('workbench-ag142-anchor-' + [guid]::NewGuid().ToString('N'))
python codex_pilot_anchor.py --init $anchor
python concept_map_pilot.py --client codex --operation update --anchor $anchor --check
python attachment_pilot.py --source stream --anchor $anchor --check
python -m unittest -v test_codex_pilot_anchor
```

初始化写入夹具标记和空闲 TOML。每轮租约排斥同一锚点并行使用，仅接受标记及受管配置，遇意外目录成员、重解析或外部改写会拒绝。先写当次 TOML 摘要与监听端口，再原子替换项目配置。正常 STOP 先撤销并实测 401、停服，再恢复不含临时连接器的空闲 TOML。真实用户级配置和继承连接器状态仍由用户设置决定，空闲项目不用于试点模型。若受管 TOML 仍被锁，脚本单独报告 `anchor_cleanup_failed` 和每轮临时数据实际移除状态。下次获得租约时，只有当配置与该轮摘要或已知空闲字节一致、旧端口已关闭，才可恢复。遇未知改动或旧端口仍在监听，保留现场，不覆盖。

实际桌面仅在用户同意后保留这个验收项目并首次信任。每轮结束旧回合并关闭旧聊天，保留项目登记。监督 STOP、核对 401、端口和空闲状态后，再启动所选夹具的新一轮。用户从同一项目新开聊天，复核实际目录、继承旧项禁用、本轮中继名单与实际 workspace 后才发送。新旧聊天都不以目录名单代替身份核验，显式 reload 可能将旧聊天接到新空间。现场是否无需手动刷新或打开 `/mcp`，以及是否复用首次信任，仍待真实桌面核验。项目禁用继承项的配置沿用前述已知继承 `workbench` 的方案；若客户端缺少该继承 transport 并拒绝加载，停止发送并审查本次候选。

已在隔离工作树实测同一个安装版 App Server 先后加载同一受管项目上的 file 和 stream 夹具。未在轮间 reload，两次新聊天分别看到九项和七项并实际读取对应的不同工作空间；旧聊天显式调用返回 `Transport closed`。锚点文件持锁时两个独立数据和凭据根均移除，两轮 401 和端口关闭通过。空闲后执行 reload，新旧聊天均无当次临时项工具。另持有受管 TOML 文件锁，实测 STOP 保留 401 和端口审计、移除每轮数据根、单独报告锚点恢复失败并退出 1；释放锁后下一次租约恢复空闲配置。真实桌面复用仍待验证。

首次真实 stream 锚点试点经用户同意后，先用 `codex_pilot_anchor.py --init` 创建一个新的受管空目录，再运行 `python attachment_pilot.py --source stream --anchor $anchor`。从实际输出确认 `managed_anchor=true`，用户登记并信任该目录，打开该目录的新聊天。随后按前节依次核对七项工具、批准 stream-only 策略、发送建会话提示、触发固定会话的本机 PUT、发送完整预览提示并在隔离网页独立批准。保留锚点项目登记，结束时只关闭当次聊天，等待中继结束后 STOP，核对 `anchor_idle=true`、本轮数据根移除、401 和端口关闭。该轮验证首次使用受管项目，后续独立空间再验证真实桌面复用。
