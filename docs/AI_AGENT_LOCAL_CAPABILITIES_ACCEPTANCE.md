# AI Agent 本机能力扩展验收

## AG-128：休眠授权与能力协商

日期：2026-11-09。仅本项完成，不代表AG-129～143或六类业务能力已开放。用户在监督对话明确“现在开始执行方案”；执行前HEAD ba24e37、工作区干净。早先AG-127只文档/等待指令保留历史含义。

### 实际实现

- 严格版本化capability_grants、显式操作/资源/确认方式；新授权统一持久dormant，未来启用必须管理员重新授权；files.read当前拒绝配置。
- 管理UI/CLI复用CredentialManager；新schema允许无旧kinds/范围的独立休眠客户端，不补通配。edit省略保留、显式空清空；轮换保留、撤销生效、CAS和幂等持久化。
- capabilities的configured配置与implemented/effective分开，当前新增能力后两者为空；12个MCP工具与原四类型三操作不增加。初始化/工具规则同步，连接成功不能冒充业务权限。
- 新schema catalog标签来自有权条目，空项目仍可查工作流；无旧业务范围时无标签/分类/项目/正文泄露，legacy全局配置标签兼容保留。文档分类变更收窄休眠grant，重用名称不复活。
- root registry2、client authorization3、management log3、transport2；详细grants不复制桥接配置，16KiB保持。读取旧格式不重写。首次升级prepared3→root2格式门槛→config→registry→completed，未知/混合旧未决日志先预检，异常/abandon/清空不降格式，秘密快照完成后清除。
- 新日志恢复另严格核查授权快照，篡改激活或损坏快照停止恢复、不覆盖。当前持久dormant校验与effective空集合共同约束；后续处理器不可仅因implemented非空激活旧授权，AG-129与能力项须继续绑定授权版本和管理重新授权。

### 实际自动化结果

| 命令/范围 | 实际结果 |
| --- | --- |
| python -m unittest -v | 当时全部249项通过，122.476秒；随后增加快照恢复校验及匹配备份用例，按下列专项复验，不把旧总数当最终发现数 |
| python -m unittest test_agent_capabilities test_agent_management test_agent_runtime test_agent_extensions test_agent_web_approval -q | 最后恢复代码变更后72项通过，66.227秒，包含新增损坏快照用例 |
| python -m unittest test_agent_capabilities.LegacyFenceTests.test_matching_preupgrade_backup_restores_to_separate_directory -v | 新增匹配备份恢复用例1项通过，1.441秒 |
| python -m unittest test_agent_runtime.AgentManagementHTTPTests -q | 最终补查null/数组grants严格400后6项通过，5.643秒 |
| 全Python py_compile / 全JS node --check | 62个Python、46个JS通过；Python编译输出位于临时目录 |
| node test_agent_settings.js | 真实Edge管理UI通过，含新休眠独立客户端、空旧范围、取消、丢响应查询、重开、清空及旧设置回归 |
| 其余19个test*.js | 提案专项1项通过，其余组17项通过，Agent工作流独立1项通过；连同设置共20个Node契约分别通过 |

新的test_agent_capabilities覆盖：旧库只读不改写；严格非法字段/枚举/资源；休眠权限隔离；编辑省略/清空、轮换/撤销、陈旧CAS；分类名称重用；真实并发CLI；配置大小；未知/混合未决日志；第三方改动report/abandon；持久激活篡改/损坏快照拒绝；匹配备份恢复。

五阶段异常与真实os._exit均逐轮独立临时空间，每轮先断言root1，再于prepared/format_fence/config/registry/completed中断。归档基线ba24e37的真实旧代码分别验证鉴权、recover、启用接入、abandon、CLI拒绝，门槛建立后额外验证clients()拒绝；CLI等拒绝前后全部私人JSON指纹不变。新版重启恢复原client/令牌/授权/幂等结果，完成日志清秘密快照。归档探针需要Git基线对象；本机实际存在，未跳过。

匹配备份演练不删除升级现场：无服务运行时复制升级前业务+私人状态，升级原空间，向独立目录恢复匹配副本；旧版成功鉴权并读取项目，恢复副本root1，升级原空间JSON指纹保持不变。当前无自动授权格式降级转换工具；无匹配备份不得手改格式或删日志回退。

最终文档检查：修改Markdown的UTF-8/围栏/83个相对链接、AG-128完成及后续待开始、其他历史状态行不变、无数据/生成物路径检查通过；git diff --check通过。最终发现数随新增保护用例变化，上表保留每次实际运行范围。

### 真实浏览器与视觉

浅/深×1440/390真实Edge截图目视检查，新增表单纵向标签、focus、休眠提示、明确资源及长中文正常；空客户端/空授权、大量项目分类、disabled/error、取消、丢响应查询、编辑/轮换/撤销、换页与重载沿用并扩展设置测试。截图位于临时目录，不提交。发现标签横向挤压后复用既有表单CSS规则修正并复验，index缓存更新。新增管理表单确认完整展示休眠配置及旧版格式限制。

### 失败与复验记录

- 旧版探针首次按UTF-8解码Windows stderr失败；改为字节级错误断言后通过，不放宽旧版拒绝要求。
- 首次语法检查与测试并行写现有pycache出现WinError5；改为临时cfile输出后全文件通过。
- 设置新增截图在切宽后立即检查布局时失败；等待布局稳定、明确截图滚动位置。取消后立即再开确认出现close事件时序竞态；测试等待真实close事件后复验通过。应用确认语义未放宽。
- Node提案专项首次刷新恢复等待超时，独立复验通过；Agent工作流两次在不同深链接刷新等待超时，添加页面异常/状态失败诊断后独立复验通过，未修改超时、断言或应用导航实现。尚不能证明偶发超时根因；保留诊断，后续持续观察。

### 兼容及剩余范围

APP_VERSION=2026.11.09.1；settings JS/management CSS缓存20261109-1。无业务Markdown/JSON迁移、草稿/历史/编辑器格式变化。所有测试临时数据及隔离凭据/客户端配置，未接管真实客户端；未启动模型turn，未跑新增业务真实客户端验收（留AG-142）、性能或独立视觉基线脚本。

决策AG-LOCAL-DEC-009～012。下一项为监督审查后AG-129。概念图、文件、附件、删除、项目及配置业务能力仍未开放；未来资源身份与完整迁移/恢复由各自工作项承接，不能借本项休眠配置宣称可用。


## AG-129：新提案与多步骤持久恢复基础

日期：2026-11-09。开工基线f6463db，AG-128监督审查接受后派发，工作区干净；用户总体执行授权持续有效。本项只贯通现有四类型三操作，不开放文件/附件/概念图/删除/项目/配置能力。

### 实际实现与兼容

- agent_execution.py仅静态markdown@1/12种组合，逻辑计划包含两个受控步骤history_snapshot、markdown_write、归属/既有ID及候选摘要。具体目标路径/ID/历史版本由领域Prepared和服务端派生，不接受任意路径、方法或测试处理器。
- 新proposal3/sha256-json-v3绑定授权management_revision与完整client_version、相关依赖、计划摘要；manifest3使用独立execution_schema_version=1及具体计划摘要/实际字节/进度，原领域Prepared.apply仍是历史与正文唯一写入入口。旧1/2原读取/摘要及恢复分支保留。
- 依赖只绑定当前归属存在、模板ID/当前kind的name+completed完整状态集合、候选使用标签名称存在性、固定引用ID集合/revision。相关状态集合成员增删保守冲突；无关项目/说明/排序/分类和标签颜色不绑定，不包含私人settings/data_dir。此保守粒度及代价已在AG-LOCAL-DEC-015明确。
- history/target真实写后、步骤日志更新前均有退出接点；恢复以快照摘要和磁盘字节判断，正文仍before须重查授权/依赖，即使history已完成；正文after只补原回执。create applying后正文缺失仍歧义拒绝，不能新分ID重建。
- 文件内ID、workspace/proposal/version/client/kind/operation/目标归属、快照候选与receipt显式交叉校验；非秘密摘要不能替代语义校验。未知提案/manifest/步骤/算法/批准格式先零写预检，阻止其他已知日志恢复、清理或取消绕过；在途错误content_cleaned标记也拒绝。
- 新批准action3绑定逻辑计划/授权/依赖，已批准但无manifest只查询not_applied，不自动提交。批准完成回执/授权字段严格验证，执行manifest还核验实际agent_attested确认或独立网页批准证据，撤去确认标记也零写拒绝。旧批准2和取消1保留。策略收紧保持proposal3、递增版本/清预览/绑定新授权；旧四类凭据无需新增休眠grant。
- 匹配终结回执时仍逐一验证JSON格式/身份/摘要，不重复读取终结Markdown快照；在途完整读验。过期扫描仅在真正过期且允许过期时进行，expire=False预检不再每提案扫描operations。

### 实际检查

| 检查 | 实际结果 |
| --- | --- |
| python -m unittest -v | 267项通过，227.517秒 |
| python -m unittest test_agent_execution -q | 新执行16项通过，24.000秒；早期首轮14项20.721秒通过 |
| python -m unittest test_agent_execution test_agent_proposals test_agent_recovery test_agent_web_approval -q | 后续在途清理标记防御后48项通过，61.705秒 |
| python -m unittest test_agent_execution test_agent_web_approval -q | 批准记录嵌套字段/完成回执严格校验后29项通过，53.018秒；最后再补manifest确认完整性后29项58.889秒通过 |
| 全Python/JS语法 | 64个Python、46个JS通过，编译输出临时目录；收口再核对最终文件 |
| Node契约 | 共20个分别通过：首组19项中17通过，提案UI修正后独立通过，概念图/编辑器两项串行复验通过；不宣称一次整组全绿 |

执行专项证据：四类型×三操作真实路径/唯一回执；状态集合新增/删除冲突与无关改动不冲突；引用revision变化冲突；history已落但日志未记录时撤销阻止正文发布；target已落但进度未记录时撤销仍补原回执；篡改kind/目录且重算非秘密摘要拒绝、未知格式前后全部状态文件字节不变；schema1/2/3混合预览原文件字节和摘要不变、旧1/2未决创建恢复、旧2更新history后恢复保持一份历史。

十阶段独立临时空间真实os._exit涵盖snapshots、manifest、committing、applying、history、history_logged、target、target_logged、receipt、proposal，重启后同ID/回执，update历史一份。真实server --disable-agent两组：匹配私人授权正常恢复已接受更新，缺失配置保持applying/旧正文、不绕过权限。并发8次提交返回同回执；取消/过期/清理/abandon和第三方内容保护沿用并扩展既有专项。

预检I/O回归样本136提案、16份真实终结manifest，断言operations目录只扫描一次、终结Markdown快照读取零次；所有JSON格式仍预检。这只是临时I/O回归证据，不是完整性能基线或大文件性能验收。

### 浏览器及失败复验

真实Edge提案预览显示保存范围与完整执行依据，展开计划JSON并验证markdown@1；浅/深×1440/390四张新截图已目视检查，长中文、focus、disabled、滚动正文/固定头尾、完整预览、取消/批准、过期版本、丢响应查询、刷新与两个编辑器保存/草稿/历史/外部冲突均实际通过相应Node契约。截图只在临时目录，不提交。

首轮47项Python专项出现5失败/12错误；持久授权夹具修正后36项仍有2失败/12错误，继续修正reload挂载后的恢复后36项64.820秒通过。首错暴露Todo/Info旧夹具仅在内存扩权及reload未接入私人授权后恢复；已改为CredentialManager持久授权，并按真实server二阶段接入顺序复验，不放宽新恢复鉴权。新建提案算法预期改v3，另补真实旧1/2夹具证明兼容，不能只靠改断言。

新增浏览器测试最初在多次Runtime.evaluate中重复声明顶层const，已改为IIFE并增加原错误打印，复验通过。失败时finally清理EPERM可能掩盖首错，保留该事实；概念图清理也出现EPERM，编辑器初始化等待超时，两项串行复验通过，未修改应用行为/等待超时/业务断言，不将所有失败归因OS。关闭对应测试进程后只读按验收目录前缀核对Python/Edge进程为空，对应监听端口为空；不扫描或读取其他业务服务。

### 收尾与剩余边界

自动审批曾拒绝清理3处本轮失败临时目录，仅返回blocked by policy；未换工具/命令绕过。对应后缀为workbench-proposals-browser-jmeItf、workbench-proposals-browser-bu1xhC、workbench-edge-concept-4nNPX9。已确认无按这些目录匹配的Python/Edge进程；用户随后手工删除，监督及执行只读核实三处均不存在。没有真实连接器/客户端配置变更；隔离测试凭据不输出，不把服务停止混称主动撤销。测试fixture停服/退出后清理，截图仅作临时评审。

APP_VERSION2026.11.09.2、agent-proposals.js缓存20261109-2；业务Markdown格式/领域仓储边界/草稿/历史格式不变，旧提案不强制迁移。决策AG-LOCAL-DEC-013～017。新增业务能力/真实模型客户端新功能验收/性能及独立视觉基线未运行，分别留后续项；AG-128休眠授权不激活。下一项须监督审查后派发AG-130，本项不串入文件授权。

AG-129提交前最终检查：64Python/46JS语法、修改Markdown编码/围栏/84相对链接、历史状态/后续待开始及生成物排除、git diff --check通过。

## AG-130：具体文件授权与只读分段

2026-11-09完成；起始HEAD9b6924d/工作区干净，用户整体执行授权及监督派发持续。仅本项，不代表AG-131～143或真实模型客户端新增矩阵完成。

### 实现与兼容

同源本机管理属性预览→明确批准→才读取/hash；票据绑定同管理会话、runtime/空间、client CAS、句柄身份/最终路径/显示名、编码/用途/期限/限额，长hash后再次检查。Agent只用file_id与source_revision，返回basename/无父路径信息；默认10MiB/1小时，最高100MiB/24小时，64KiB原始字节段。每段同遍捕获+完整hash与前后身份版本，严格编码边界，源变更拒绝。

Windows固定本机NTFS/普通文件句柄，逐层拒重解析/目录联接，拒全部多硬链接、SUBST、网络/设备/ADS/保留名及认证/私人配置范围；测试只使用合成材料，未读取真实用户来源或认证文件。私有根短名/大小写经最终句柄路径再检查，不能以改名绕过。其他平台fail closed，分支仅模拟覆盖，不宣称非Windows原生验收。

根3/授权4 active_file_ids与私人file-grants双向交集；其余grants仍dormant。日志4按credential/file分支外置私人快照，先终结再清理，失败可查询/retry；首写未prepared孤儿先abandoned后清理，恢复不重新打开源。旧根/授权/日志继续兼容，transport2不含具体文件表，旧9b6924d不识别新格式时拒绝，不能删日志降级。业务Markdown/草稿/历史/导出不变；APP_VERSION2026.11.09.3与设置JS20261109-3。

### 自动与浏览器实际结果

| 检查 | 实际结果 |
| --- | --- |
| python -m unittest -q | 首轮288项185.202秒：286通过、2处旧预期失败（files目录404、诊断12工具）；未宣称一次全绿 |
| python -m unittest test_agent_files test_agent_api test_agent_diagnostics test_agent_capabilities test_mcp_stdio -q | 修正旧预期并保持无授权拒读断言后63项60.784秒通过 |
| 有界内存/模拟未支持分支补测 | 2项0.513秒通过；11MiB原生文件每段校验，tracemalloc峰值<4MiB |
| 首写孤儿/abandoned终结前清理退出 | 1项0.517秒通过，恢复零源正文读取/零授权发布 |
| python -m unittest test_agent_files -q | 最终24项23.157秒通过 |
| Node全部20项 | 设置独立通过，其余19项串行整组通过；中文结构化预览后设置再次通过 |
| 全文件语法 | 67Python/46JS通过，编译输出临时目录 |
| python codex_agent_acceptance.py | Codex CLI0.163.0-alpha.10.2、MCP2025-11-25、15工具、原四类型/两确认路径及重试/取消/重启/撤销通过，0模型turn、用户配置未改 |

文件六阶段真实os._exit、根3普通create/edit/rotate/revoke×七阶段真实退出、首快照孤儿/终结日志后清理前退出、删除失败待清理查询/重试、真实旧二进制拒绝/JSON零变化、旧3未决混新4/未知版本零写均有断言。UTF8、BOM、UTF16两端序/代理对、GB18030四字节、ASCII/CP1252非法与合法、EOF/非法起点/截断、配额/超限/过期/版本/哈希改变覆盖。原始stdio真正调用三文件工具并拒path字段/撤销后拒读，不只核对工具数量。

真实HTTP长hash期间撤销/换库/关闭可完成，未获许可正文不发布；慢socket在许可后延迟，撤销可完成且原已获许可响应仍可能到达。管理session/票据到期在hash完成后拒绝发布，换session预览不能使用；不能在confirm替换path。Agent凭据/跨源管理拒绝，元信息/回执/日志无父路径/正文/token。

真实Edge：文件专用客户端无旧类型/范围，属性预览不含源正文、取消不授权、明确批准、丢响应后刷新查询原request且仅一项、逐文件撤销。中文预览将用途/大小/编码/期限/外部模型披露直接展示，身份与版本可展开；浅深×1440/390四张最终截图均目视检查，无横向溢出，图片仅临时评审不提交。既有Node同时覆盖focus/disabled/error、长中文/空数据/大量范围及原编辑器保存/冲突流程。

### 失败与剩余边界

最初22项出现4个旧implemented为空/12工具预期失败；修正后41项29.890秒通过。初轮HTTP测试桥接入口文件名错误及Windows原始换行比较错误，改真实agent_bridge入口及原始字节断言后通过。设置浏览器先暴露旧诊断12工具预期，再暴露新panel位于agent-settings样式容器外的溢出；移入既有容器、复用样式并复验通过，无放宽断言或超时。初步原生探针只因GBK控制台输出emoji失败，最终原生专项不打印敏感正文且通过。无本项临时目录清理遗留或自动审批拒绝。

决策018～023。每段O(file-size)全扫描，5秒只在本机同步读块之间检查，OS等待可能更长；已获发布许可的数据不能撤回且可迟到。文件名与内容可能发往外部模型服务，管理员预览明确披露。attachment_source仅未来意向，不能文本读取或上传。本次原始MCP和既有真实Codex无模型回归不替代AG-142新增业务客户端矩阵；无真实新能力模型turn、性能基线或独立视觉基线验收。下一项AG-131须监督派发，本次到此停止。

最终67Python/46JS语法、10份修改Markdown/72相对链接/围栏编码、后续待开始状态和git diff --check通过；diff无业务数据、私人凭据、日志或评审截图。

### AG-131开工发现的POST外锁缺陷与独立修复

监督审查AG-131长流接点时发现：130专用dispatcher虽然将hash放在自身短锁外，do_POST/PUT等的serialized_write装饰器仍在分派前持空间/业务锁。130此前真实GET长读测试不能证明管理POST批准也释放外层锁；原验收证据保留其实际范围，不重写为已验证该POST边界。

独立修复将Agent与同源Agent管理的分派从外层锁中豁免，继续使用各dispatcher自己的短锁；普通网页变更仍由原装饰器与guard协调。新增真实HTTP POST文件确认长hash测试，期间客户端撤销HTTP、关闭接入HTTP及换库锁均在2秒内完成，hash结束后拒绝发布、私人file-grants仍空。APP_VERSION2026.11.09.4，不改前端、数据/API格式或旧网页锁。

python -m unittest test_agent_files test_agent_api test_agent_runtime test_agent_execution test_server -q：107项83.793秒通过；node test_agent_settings.js原设置及130文件全流程通过；四个涉及Python入口/测试编译及git diff --check通过。此为独立缺陷修复，不包含未验证上传代码；AG-131仍进行中。


## AG-131：私人流式暂存、配额与恢复

2026-11-09完成。起始eeeaf86工作区干净，整体执行授权和监督派发持续；期间独立POST外锁修复5abd6f2另提交，见前节。本节只验收131，AG-132～143未开始。

### 实现、数据与授权

新agent_upload_policy、agent_uploads和agent_upload_http分别承载明确策略、私人会话与专用传输；既有管理日志/领域权限/原子写复用。uploads.stage必须同源本机管理会话完整预览并明确批准，绑定批准后的完整client_version、owner及相关版本、stream开关或具体file_id/source_revision、大小与期限；客户端改动保守失效，重批准替代旧policy。既有read/propose、attachment_source意向、text_read与休眠attachments.write均不自动生效；file来源同时要求有效attachment_source及新策略逐文件批准。目标范围仍用旧业务读取访问规则，不因此得到正式写入。

root3/auth4/log4/transport2保持，新增严格upload_policy操作家族和外置私人before/after_policies；policy/session各schema1，全部未知格式先预检，旧eeeaf86真实归档二进制拒绝且相关私人JSON逐字不变，不能删除日志降级。私人上传UUID由workspace/client/request确定，完整输入digest拒同请求换内容；原始basename无任意path/URL/base64。正式附件、资产索引、正文、导出格式、草稿和历史不变；consumer_contract固定拒绝，binding/consumption只预留并保护，不提供Agent消费入口。

单文件100MiB、client500MiB、空间1GiB、I/O并发2/client与4/空间、1000未removed会话、24小时、16MiB磁盘余量。预留按声明，真实长度/SHA独立校验；可用磁盘只扣未物化预留，已占用内容不重复扣减。墓碑保留幂等但不计活跃上限，未来墓碑增长仍需治理，131不自动删除幂等证据。跨进程短目录锁协调配额、原子元数据/扫描、rename、同一已核验DELETE句柄关闭及removed发布；长hash/流不持空间/业务/凭据/目录锁。每session OS锁保护传输与维护，在途取消409，停止发送或撤销策略后查询原会话，不承诺立即中断OS调用。

固定loopback PUT octet-stream，Bearer/空间及Host/Origin校验；拒TE、重复身份/Host/Origin/CL、缺失/非法长度、超限、query。64KiB块、idle5秒/total60秒逐块收紧；已缓存多余body拒绝，迟到余字节由必关连接丢弃，不作为下一请求。fsync证据→sealed→blob rename→磁盘重读→当前服务/空间/权限/owner复验→ready。未sealed中断保守failed；完整证据可重启恢复，无需重读源；未知尾部/对象/版本及篡改保留，不能当可用ready。清理只处理已过期、非在途、未绑定/消费且字节证据匹配对象，真正消失才释放预算。

### 实际检查

| 检查 | 实际结果 |
| --- | --- |
| python -m unittest -q | 较早全量311项231.587秒通过；发生在最后边界补测前，不声称当前全量一次通过 |
| python -m unittest test_agent_uploads -q | 修复并发路径与元数据扫描后23项28.218秒通过；随后失效junction新增分支曾失败，见下文 |
| python -m unittest test_agent_uploads test_agent_files test_agent_capabilities test_mcp_stdio -q | 前轮70项71.210秒通过；最终原生属性修复后71项85.775秒通过，1项原生符号链接因WinError1314权限不足跳过 |
| 100MiB临时来源/真实blob | 最终样本Python峰值3199815字节，2.767秒，断言低于8MiB；此前多个样本亦通过，仅有界内存证据，不是性能基线 |
| 20个Node契约 | 其余19串行通过、设置独立通过；设置最终包含真实ready状态行及token不进入DOM的断言再次通过，不称一次整组全绿 |
| python codex_agent_acceptance.py | Codex0.163.0-alpha.10.2/MCP2025-11-25/19工具、原四类型三操作与两确认路径及重试/取消/重启/撤销通过；0模型turn、user_config_changed=false，不替代AG-142新能力模型矩阵 |

上传测试实际覆盖明确授权/持久重载/越权/隐藏与不存在同404、来源用途/版本、owner/client/policy变动、重复请求与不同输入、完成重放与丢响应查询；零字节/边界/截断/超长/错SHA/取消后不复活；500MiB与1GiB精确边界、多线程/真实跨进程竞争、磁盘不足/已物化预算、1000活跃与墓碑幂等；未知/混合元数据零写、第三方改动、已绑定/消费/在途保护；目录锁确定性交错验证rename/删除与预算统计一致、长hash不阻塞统计，元数据原子写时目录扫描不会误报未知临时文件。

独立临时进程在receiving、partial_evidence、part_fsynced、sealed、blob_renamed、ready真实退出并重启查询；policy私人快照/日志/格式门槛/策略/registry/终结阶段真实退出、孤儿及清理失败恢复均有断言。原始HTTP真实流、慢速/idle/total/header异常、撤销/关闭/换库期间旧请求不能发布ready；原始stdio真正调用新4工具及file来源复制，拒path字段，旧工具继续可用。这里HTTP客户端和stdio测试分列，不声称MCP JSON能携带原始流或已有真实模型新能力矩阵。

真实Windows普通文件与多硬链接、有效及失效目录junction守卫覆盖；失效junction由GetFileAttributesW在Python缺失路径分支前拒绝，避免将链接当可创建叶。符号链接创建权限不足的分支明确跳过，未开启开发者模式或提高权限。安全清理使用同一已验证句柄的SetFileInformationByHandle/FileDispositionInfo标记及关闭，不重新按路径删除已验证内容；来源读取默认不申请DELETE。官方依据见方案第18节，行为以本节实际断言为准。

真实Edge设置浏览器覆盖完整中文预览、取消/明确批准、丢响应刷新查询原request、撤销、当前空间报告/恢复/清理及真实ready行。旧文件panel迟到结果不覆盖当前client；待决批准禁止无关写入。浅深×1440/390最终四图已目视，长中文与120项目、空数据、focus/disabled/error、无页面横向溢出，图片只在Temp用于评审，不提交；无新增CSS。原编辑器/Agent保存冲突工作流随既有Node通过。

### 失败、清理与交付边界

首轮相关69项出现1个并发失败：5次成功和1次非预期路径别名拒绝，未超卖；即时再次解析与先前不一致只是观测，不能宣称证明Python/OS内部原因。改为只解析既有祖先、服务派生UUID创建/打开后复验，并将元数据原子写与扫描纳入同一短锁；18轮独立跨进程竞争复验及后续70/71项通过，未放宽配额断言。

扩展真实失效junction测试后24项出现2错误、1跳过：守卫未拒绝失效对象，fixture随后rmdir清理也失败。补原生GetFileAttributesW与fixture仅恢复自身空target再移除链接；两个定向分支1通过/1权限跳过，最终71项通过。浏览器失败先暴露旧panel/版本竞态，后暴露响应丢失测试仅等待pending早于实际提交及刷新仍匹配旧DOM；分别清空旧panel并校验请求序号、等待实际丢响应反馈、用窗口标记确认新执行上下文后通过，不放宽业务断言/超时。

原失效junction失败fixture留一处本轮合成Temp目录（后缀tmp0u2oav7r），清理命令遭自动审批blocked by policy拒绝；未换工具/命令重试绕过。用户随后回复“已删除”，执行与监督均只读Test-Path=False；原fixture无HTTP服务，测试进程已退出、相关子进程等待回收和线程join已完成，该清理遗留关闭。后续夹具自身清理通过；无真实用户来源/认证文件读取、真实工作台数据迁移或系统权限修改。

APP_VERSION2026.11.09.5、agent-settings缓存20261109-5，决策024～029。同步OS读取仍可能超过块间截止，已获许可响应可迟到；未知磁盘证据需人工核查，ready历史回执不等于当前可绑定权限，任何客户端变动保守失效需重批。不开放正式附件/绑定消费，无真实新增模型turn、跨客户端新能力矩阵、独立性能或视觉基线。131完成后交监督审查，132～143继续待开始。

AG-131提交前最终检查：71Python/46JavaScript全文件语法通过（编译输出临时目录），10份修改Markdown UTF-8/围栏/74相对链接通过；最终目标diff、后续AG-132～143待开始及git diff --check通过，无业务数据、私人凭据、日志或截图夹带。
