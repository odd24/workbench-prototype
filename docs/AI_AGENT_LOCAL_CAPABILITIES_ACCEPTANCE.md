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


## AG-132：记录与项目独立附件正式提案

2026-11-09完成。监督接受AG-131/b7ce3fe后派发，起始Git干净，唯一执行写入；本节不代表知识库附件AG-133或真实模型客户端矩阵AG-142完成。

### 实现与兼容事实

新增attachment_prepared领域准备、agent_attachments候选/来源保护、agent_attachment_execution静态执行和agent_attachment_http锁外传输；仍由唯一ProposalStore协调提案/确认/恢复，AttachmentRepository和原PreparedMarkdownWrite执行正式写入。旧网页和Agent共享metadata/链接助手，记录仍front matter、项目仍独立index，新增id/sha256是兼容额外字段；info有序字段、未知meta及原始body片段保留。知识库没有附件新格式，本项仅验证原外部图片/共享编辑器不退化。

一次明确本机预览共同批准具体owner的uploads.stage+attachments.write/create及最低确认方式，policy schema2/新attachment_policy管理家族以日志4私人快照/CAS持久恢复，root3/auth4/transport2不变。旧schema1只有stage，旧项转2显式null，dormant不激活。双方绑定同一批准后client_version；共同批准→新ready→正式提案，无旧ready迁移。旧read/propose/commit/目标范围继续必要，两确认取最严格。get_attachment_target是第20工具，仅当前许可owner元数据/revision/已有分类，不提供Agent二进制下载/替换/删除。

attachment/create严格六content字段，既有project/issue/todo/info、固定ASSET-<upload UUID hex>及唯一名称、outer target_id/base_revision；分类只已有或空，project不插正文。完整候选/base合计≤256KiB，超限拒绝不截断，最终名称/原生路径约束在准备时检查。完整预览显示来源、真实SHA/size/MIME、before/after元数据、正文/差异及未解析二进制警告，确认前零正式文件/新业务目录。updated/created明确占位，实际接受当前确认时生成真实时间/唯一历史ID并绑定具体after摘要/metadata_time，不使用草稿时间。

原proposal3/v3摘要与两确认状态机保留，新增attachment@1/execution_schema2五阶段。固定意图、确认/网页action、快照先落prepared/copy pending再锁外复制；part在.agent下，不在普通孤儿扫描根。session/operation OS锁持I/O，业务/凭据/空间只在短校验/发布/metadata阶段持有；接受意图后write_guard阻止普通写/孤儿清理，读取/授权撤销/换库可完成。copy真实bytes/SHA与part卷/文件身份持久后以同一READ+DELETE句柄、父链属性句柄、不覆盖FileRenameInfo发布，无跨卷fallback。相同SHA的外部同名对象也不收编。

来源引用以proposal为事实，session镜像缺口在各入口保护/重建，未知绑定继续保护；一源仅一有效提案，取消/修订/过期无执行日志时才能解绑。consumption保持64hex=sha256(proposalUUID-version)，与原操作、版本、owner revision、upload及回执交叉校验。metadata before需当前权限/目标/类别集合，after只核实际发布/历史证据补消费和原回执；receipt持久后不重放后来改删。已完整committed的proposal/manifest/receipt及消费证明允许维护立即退休源blob并释放预算，仍验证同一删除句柄，保留墓碑/原回执；未完成、未知、篡改或在途不释放。

### 已运行自动与原生验证

| 检查 | 实际结果 |
| --- | --- |
| python -m unittest -v | 337项256.901秒通过，1项原生符号链接创建权限不足跳过；是最后四个附件边界测试补入前的全量，不冒称当前全量一次通过 |
| 早期相关组 | 121项150.694秒，1失败/1错误/1跳过：131的19工具旧预期与合成未知绑定需保护，见失败段 |
| python -m unittest test_agent_attachments -q | 后续22项50.952秒及51.737秒通过；包含新增联合策略/同身份/类别与权限边界 |
| python -m unittest test_agent_attachments test_assets test_agent_uploads test_agent_web_approval test_agent_execution test_mcp_stdio -q | 最后93项144.534秒通过，1项符号链接权限跳过；源保护/旧Markdown/两确认/MCP/新旧格式均回归 |
| 100MiB正式复制 | 真实私人blob→正式file并流式重读SHA，最初峰值1870978B/0.734秒；后续93组样本1524717B/0.795秒，均<8MiB；只证明有界内存/字节持久，不冒称独立性能基线 |
| python codex_agent_acceptance.py | Codex0.163.0-alpha.10.2、MCP2025-11-25、20工具、原四类型三操作/两确认与重试取消重启撤销通过，0模型turn、user_config_changed=false；新附件原始stdio另外测试，不替代AG-142 |

真实os._exit覆盖15提交断点：快照无manifest、prepared而proposal仍previewed、committing、copy partial、完整fsync未记证据、copy证据前后、applying、binary发布前后、history、metadata、consumed、receipt、proposal。无manifest不自动发布；partial不足保留阻塞，完整已接受part可重验续原计划，重启后固定ID/一份历史/原回执。另有3处proposal→session镜像间隙（prepare/cancel/revise）真实退出，cancel/get/维护保护或修复绑定；7个共同policy快照/日志/门槛/ledger/registry/终结断点真实退出，旧stage schema1不隐含正式权，schema2恢复与幂等/快照回收通过；4个退休断点（证明、已验、真实删除、记账）真实退出，正式附件及回执不重建/丢失。

原生不覆盖rename探针、预览后同名相同/不同bytes占位409、已发布对象被同SHA/不同bytes替换后拒绝收编，真实子进程退出后按volume/index/created/written/SHA保护；普通孤儿清理仍503，外部内容不被覆盖。具体类别配置与推导集合变化拒绝，实际受理时间与模拟2000年草稿区分并稳定重放；body无链接逐字保留含CRLF/首尾空格和未知meta，有链接仅公共助手追加，任意改写重算摘要仍拒。info字段顺序/换行/引号/首尾空格、todo状态/截止日及旧Markdown/新附件混合日志通过。真实归档b7ce3fe拒绝新处理器/管理家族且前后JSON逐字不变，未知执行版本cleanup零写保留。

真实HTTP agent commit长Native读取期间可读取普通项目、拒普通孤儿清理、及时撤销；管理approve长读取期间关闭接入/切换可完成（并发操作整段<2秒），旧请求零正式发布；不是只测内部helper。真实--disable-agent服务启动可恢复既有已确认事务。synthetic binary发布后撤销且metadata仍before保持阻塞，metadata已after则完成原消费/回执，不重新发布。原始stdio真正调用get_attachment_target和既有prepare/preview/commit/get/cancel完成正式附件及重放，并拒path；合成user_confirmed不等于真实模型/人类身份验收。

### 浏览器与失败复验

新test_agent_attachment_workflows在真实Edge临时服务通过：共同许可完整预览/取消/明确批准、local_web完整附件预览、固定元数据/执行依据、项目附件结果深链/聚焦、下载真实PNG、源file_id导入、特殊文件名方/圆括号/%/#/中文空格。记录与知识库各完成可视化→Markdown→保存→重开，源URL/alt和info字段不变、真实图片仍可加载；知识库使用原外部图片目录，未新增附件格式。浅深×1440/390共同许可和正式预览八图已目视，长中文/空列表、固定头尾/滚动正文、焦点/disabled与无横向页面溢出，截图仅Temp评审。原test_editor_workflows也通过保存/重试/关闭/切换/草稿/历史/外部刷新/两编辑器冲突；普通URL粗斜体与b7ce3fe baseline对比相同，新行内code/转义符号及XSS/属性逃逸断言通过。

失败事实：最初领域9项的“目录不存在”断言误把项目预建images目录当预览副作用，改为前后全路径快照；另一夹具history_version不合法，改既有合法格式后9项通过。最初附件专项导入UploadTests导致重复发现旧项、编辑夹具漏完整name等字段，改模块引用和持久管理入参后通过，不放宽授权。HTTP测试未编码中文project ID导致urllib ASCII错误，按协议对称编码后通过；普通网页并发测试携Agent Authorization被正确403拒绝，移除该头后证明真实网页读取/503写保护。

121相关组中的未知binding缺失proposal改为继续保护，绝不因缺失释放源；旧MCP19预期同步20，两定向2项2.565秒通过。浏览器首轮尚未等application.start完成就切页，被初始化改回home，测试等待真实初始化结束；随后实际file_expiry与expires票据共存导致管理预览400，修兼容清理并补混合票据回归。新项目深链同时触发隐式/显式load，迟到回调互相取消致无限加载，改先加载再切页。之后第二次共同授权的测试等待条件匹配旧有效policy，提前用旧policy遭403，改等待新owner有效行、预览/待决消失并核能力返回owner；未放宽时间或业务断言。最后端到端通过；共享Markdown普通URL标签内格式潜在退化经baseline和专项关闭，文件名字面星号与普通强调语义分开。

本项没有自动审批拒绝或未清理测试目录遗留；测试服务/浏览器/子进程均按fixture关闭，截图仅评审不入Git。未读取真实用户源/认证材料、迁移真实库或更改真实客户端配置。部分未知/partial、外部磁盘竞争、同步OS等待、许可后迟到响应及保守client版本失效仍是明确边界；显式abandon不回滚文件，被保护残留需按现盘证据核查。决策030～036，APP_VERSION2026.11.09.6及修改JS缓存20261109-6；后续AG-133～143不在本项开工。


最终补充：所有21项Node分批通过，首3新附件/提案/设置通过，随后Agent刷新曾出现domCore undefined和等待超时，后17项中该项及其余通过；最后timestamp120条断言先false，独立复验通过并确认进程清理完成、exit=0。两者根因尚未证明，未调整应用导航、超时或断言来掩盖，保留观察。实际浏览器结果均为临时库，不把该批写成一次全绿。

收口又验证旧损坏附件metadata在创建proposal之前拒绝、记录字节不变/无非法提案（连assets10项1.448秒）；项目metadata原子写后重读与新23附件连assets32项74.179秒通过；正式get/commit在AgentService按handler分流且HTTP只作协议/空间guard，API+23附件36项92.497秒通过。旧转换todo ID附件写入保持稳定ID和原无深链限制，旧二进制/混合日志专项1项4.137秒通过。最后36组100MiB样本1290746B/2.73秒，仍仅有界内存证据。其他平台在正式policy使用前明确503拒绝，未宣称非Windows原生验证。

AG-132提交前最终检查：76个Python/47个JavaScript全文件语法、10份修改Markdown UTF-8/围栏/76个相对链接及git diff --check通过；AG-132已完成、AG-133～143待开始。目标测试进程检查无匹配残留，diff不含业务数据、凭据、日志或评审截图。


## AG-133：知识库附件领域与普通网页接入

2026-11-09完成实施与验收，起始6c28f12工作区干净，监督接受132后派发，唯一执行写入；本节不代表AG-134以后或AG-142模型矩阵完成。

### 数据与执行事实

文档仅有原type=document与分类，正式附件目录是原Markdown front matter有序attachments。写出JSON字符串项，读取兼容JSON字符串/既有对象项；轻量解析器会将部分JSON字串归一化为dict，故专门复验写盘仍为带引号JSON字串，普通保存/历史/Agent往返与带boolean/未知字段的旧对象均可读。字节位于全局assets/images或files，path相对原documents文件，稳定ASSET ID/真实size/SHA及文档原category。未知meta（包括非业务project_id）保留但不改变文档归属；原body/换行由共享准备助手保留或追加链接，不建新文档类型、附件分类索引或编辑器。

Agent仅通过新鲜共同policy的document owner生效，旧stage/schema1/schema2-null/休眠grant/attachment_source不扩权。复用attachment@1/schema2、同一ProposalStore和Prepared领域/历史、两确认/绑定/发布/消费/源退休/回执恢复；category/权限/版本变更在metadata前重查。当前仍20工具、无任意路径/二进制下载，capabilities如实列执行版本1/2。原始MCP对project及document实际完成取消旧提案、prepare/preview/commit/get/replay及拒绝path；合成确认不冒充真实模型新能力验收。

普通网页不依赖Agent开启/凭据：保存前失败不发流，等已有saving完成再条件保存；上传阶段暂停autosave、持续草稿、关闭/切文档等待。完成仅当前空间/doc/base一致才合并metadata/revision和一次链接，再独立保存当前输入，不用响应旧body覆盖；丢响应刷新后先查询原UUID，未接收404与损坏/空初始化503区分，409保留输入并进入原冲突选择。稳定UUID/过程证据位于私人.workbench-document-uploads，不是业务事实源；原生NTFS/目标路径在收源前验证，100MiB/64KiB、1GiB未释放预算、1000活跃、空闲5秒/总60秒、16MiB磁盘余量。长流/hash持单操作OS锁，不持业务/空间/凭据锁。

双向接受前屏障：Agent已受理长copy时，先前receiving网页不能再prepared；web已prepared/applying时，Agent Markdown和attachment必须在第二manifest之前拒绝。执行仅绕过当前web operation ID，不能绕过别的未决。真实HTTP确定性交错中普通GET和另一客户端撤销<2秒，后来者409/503、无第二计划/发布，原事务继续完成。最初FileExists型屏障被通用Agent路由映射500，改为明确document_upload_pending/503后通过。

全目录report/recover/cleanup/明确abandon可在设置页发现其他浏览器/丢失存储/重启留下的UUID；未知全量预检先于恢复写。receiving中断只失败封存，prepared/applying按固定before/after、源身份/SHA、历史和回执恢复。completed先固定精简墓碑再校验/同句柄DELETE快照；已知失败part按创建device/inode+原生版本+真实SHA删除，实际消失后removed才释放预算。历史终结墓碑不耗尽1000活跃名额，1001份合成终结日志后仍可新真实上传及查原回执（不称1001次端到端或性能基线）。终结源重新出现认未知503，不删、不继续新上传。空初始化真实退出可报告并明确转为不可重用墓碑，未知/含文件初始化不可借此删除。abandon不回滚已发布文件，仍有计划的残留保持保护、人工核查。迁移拒绝未决及未回收failed/abandoned源；回收后真实迁移保持原UUID回执和正式字节。

三层路径：metadata/计划是原始相对路径，不URL解码；文档Markdown URL恰好解码一次；HTTP路由入口一次unquote后名称下游不再解码。字面%3A/%253A/%2F/%25/#/中文的不同文件、错层404、下载/图片/ZIP/历史/孤儿保护已测；实际冒号、问号、斜线/绝对路径仍按Windows规则拒绝。文档附件仅按完整metadata路径匹配，另一目录同basename外部图不被遮蔽；外部图两个百分号相近文件实字节验证。下载按Doc ID+实际metadata受控解析并有界发送，不提供任意文件读取。HTML/SVG主动类型下载+CSP sandbox/nosniff；原被动图片/PDF及audio/video MIME/inline保留。合成PCM WAV与浏览器MediaRecorder产生的VP8 WebM经旧record和project四个端点，在真实Edge原生媒体页加载/播放请求、audio duration=1、videoWidth=16验证，未新增播放器或转码依赖。

孤儿候选仅受控全局/项目assets，库存覆盖正式文档/记录/项目meta/body、历史/回收站按原owner目录及在途/保留操作。操作库存复用各自严格preflight，不维护弱第二解析器；任一共享引用保留，未知/损坏/重解析/硬链接保守不删并脱敏警告。补了旧实现遗漏正文/历史/回收站及恶意索引仍判孤儿的问题，并验证真实无引用文件仍会清理。文档删除/恢复/历史恢复不删除共享文件。已有明确永久删除流程仍按其原契约，不借本项开放Agent删除。

知识ZIP平铺MD+assets/<规范路径摘要>-<原名>，选中文档实际metadata/body/既有附件token受控解析、共享去重与同名分离；只改副本路径和metadata，不写回原MD。临时解压逐引用核对真实字节，缺失/越界/重解析/硬链接/未支持本地HTML或定义式引用拒绝不完整包。裸.md仍单文件；完整ZIP含正式assets并排除私人web/Agent证据。未迁移、清理或压力测试真实workbench-data，未读真实来源/认证文件。

### 自动与浏览器实测批次

| 检查 | 实际结果与范围 |
| --- | --- |
| 冻结全量 python -m unittest -v | 366项544.997秒通过，1项原生符号链接因权限不足跳过；在最后补充边界之前，不冒称当前发现数全量一次通过 |
| 相关领域/HTTP/MCP批次 | 95项223.548秒通过；当时web100MiB峰值440287B、Agent复制1141018B，仅有界样本 |
| 尾审文档/资产/Agent HTTP/capabilities | 52项78.571秒通过；当时web100MiB峰值441179B |
| 百分号/旧资产/HTTP | 24项11.077秒通过；外部图与旧HTTP另14项8.434秒通过 |
| 真实退出/回收/未知/大流及web+Agent HTTP/MCP | 14项31.548秒通过，web100MiB峰值447944B；真实11个接收/提交退出点、3个终结回收退出点，Agent原15阶段对issue/document各验 |
| 双向屏障与迁移/源重现 | 两方向屏障定向1项3.719秒；最后迁移/真实回收/屏障3项6.437秒通过，晚到候选严格字段4项6.256秒通过 |
| 未知meta与序列化 | 文档/Agent保留非业务project_id的2项1.098秒；JSON字串磁盘/普通保存/历史/原始MCP的5项7.119秒；旧对象boolean及真实重启/Agent的3项7.737秒通过 |
| 媒体与HTTP收口 | 19项13.071秒通过；MIME扩展契约1项0.882秒，接收前平台/路径与web HTTP最后7项4.963秒通过 |
| 22项Node | 分批全部通过：首3、余17、Agent与Editor各独立复验；最终document专项还通过保存失败不发流、409/维护、百分号/同名外图及四个原生音视频预览。不是一次整组全绿 |
| 真实Codex隔离CLI | 0.163.0-alpha.10.2 / MCP2025-11-25 / 20工具，旧四类型/两确认/重试取消重启撤销通过；0模型turn，user_config_changed=false；不替代AG-142 |
| 语法与交付 | 82 Python/48 JavaScript全文件语法通过，编译输出临时目录；提交前再核对最终文档/资源版本/diff与工作区 |

真实Edge使用临时库/临时浏览器profile，既有两编辑器往返与Agent document共同授权/local_web、完整预览和下载已通过；普通文档浅深×1440/390的visual/read八图已逐张目视，长中文、窄屏首个上传按钮、无横向页面溢出，深色附件链接使用既有token提高可读性。截图只在Temp，不提交；不据此称独立visual_baseline或performance_acceptance已执行。

### 失败、复验与保留边界

首轮362项524.413秒3失败/1错误：运行期间仍修改持久字段，父进程旧partial与子进程新字段不匹配，另1处fixture重复mkdir；该轮不能当最终门禁。冻结后366全量通过，后续新增边界各按上表定向复验。初期body误进front matter候选被严格回读暴露并修正，补原始换行/未知meta/历史；特殊转义括号的孤儿误报、测试HTTP预期201/200及错误长度、负向URL未编码和GBK批次输出异常均如实纠正，不以放宽断言规避。磁盘JSON字串/对象归一化最后统一写JSON字串，旧boolean字典兼容并补恢复验证。

浏览器曾出现已有Agent刷新模块缺失/Editor初始化超时及新文档刷新apiAvailable未定义，根因未证明；独立复验通过，保留有限网络/异常诊断、未改超时或业务断言掩盖。文档列表惰性加载、刷新旧上下文标记及旧报告DOM早于维护完成的等待条件只按真实状态修正。原模型未透传renderLink导致附件显示原Markdown、普通URL编码遗漏括号、全局helper媒体MIME回归风险均已本项修复并实际复验。

边界仍为Windows固定本机NTFS；不支持分支仅模拟验证收源前503/零读取/零operation，不宣称非Windows原生验收。保留O(历史日志数)元数据预检成本、墓碑增长、未知/已放弃残留人工核查、同步OS等待与外部文件系统竞态；不承诺多文件原子事务、任意客户端/视频编解码矩阵或独立性能基线。本项无自动审批拒绝或清理遗留；最终进程/生成物检查见提交前记录。AG-134～143仍待开始。

AG-133提交前最终检查：82个Python/48个JavaScript全文件语法通过（编译输出临时目录），10份修改Markdown UTF-8/围栏/78个相对链接通过；git diff --check通过，39个目标文件无业务数据、凭据、日志、截图或用户既有修改。按本轮测试前缀筛查Python/Node/Edge进程无匹配残留；AG-133已完成、AG-134～143待开始。用户报告删除的历史合成目录已只读确认不存在。


## AG-134：概念图条件写入、历史与网页冲突（2026-11-10，已完成）

起始e0a5a88工作区干净，监督接受133后仅派发134，唯一仓库写入者。源码/测试已最终冻结验收，清理与结项决定见本节末尾；不代表135以后或Agent concept_map工具完成。

实现：同次原始JSON读取得到SHA-256 revision，版本只在API；保留version=2及支持的旧版宽容归一化，合法节点/边ID、type、箭头、视口和500/1000等既有上限不变。未来未知version拒写/恢复而保留原文件。HTTP已有图PATCH/历史恢复缺expected_revision有意409提示刷新，阻止旧缓存覆盖；Python省略兼容只在Repository写协调锁内基于当前字节，不宣称无版本客户端/外部FS原子CAS。非法签名400、缺失资源404、旧签名409，陈旧更新不产生历史。

ConceptMapRepository生成PreparedConceptMapWrite并复验before；history/CMAP-ID/时间UUID.json先保存原字节，再复验before、原子目标并重读after。无第二CRUD、索引、新日志或自动重放。常规读取不初始化图历史；历史保留全部，Markdown原30份策略不变。历史API只接受本图及受控版本名；未来/损坏快照标不可恢复并保留。历史恢复仍当前CAS并记录恢复前图。分类改名/删除逐图同Prepared，批量中途失败报错并可按实际剩余范围继续，不宣称配置/多图事务；回收/恢复留历史，完整ZIP包含JSON历史。

原字节格式（额外空格/换行/未知meta）和摘要重读、Python旧调用、两线程一赢家、Prepared期间外部改写/历史I/O期间改写、history写失败、target写失败、replace后异常及history/target两真实os._exit均验证；重启不自动重放，失败不等于零落盘。版本/ID路径限制、未知/损坏原证据不写不删；旧节点/引用/颜色/尺寸/缩放归一化与数量拒绝回归。分类部分失败及回收ZIP也验证真实重读。

网页继续唯一画布控制器/公共API/对话框。保存成功推进base，不用响应覆盖期间输入；冲突暂停autosave且保留画布/撤销栈。继续编辑不自动覆盖；读取磁盘后撤销恢复本地内容但沿用新base；明确覆盖须读最新图再确认CAS，确认期间再变仍拒绝。clean画布历史恢复409也标dirty并保留草稿，flush不得误判为成功。关闭/切页/图库/新建/切图检查flush结果；接受离开才使同一open世代失效，等待GET期间新输入/冲突或空间变化也拒绝落地。A迟到不能替换B；失败导航保留当前图/草稿/入口。恢复期间输入保留，autosave暂停到结果明确。刷新/标签关闭只是beforeunload与本地草稿尽力保障，配额失败提示导出，不宣称已保留。

自动检查事实：

- 概念图13项1.877秒通过；相关concept/server/http最终65项15.912秒通过。
- 第一冻结全量384项599.704秒：1错误、1权限skip，既有100MiB暂存complete触发source_timeout；同代码原限制单独1项2.232秒通过（5996265B峰值、样本1.83秒），不写成全量通过，不推断唯一根因。
- 最终源码/测试冻结后顺序全量384项598.002秒OK（1原生符号链接权限skip），exit=0。100MiB暂存5379728B/4.342秒，正式copy1851480B/1.468秒，web445873B；只称已有有界字节样本，不称AG-134性能基线。
- 22Node原批次21通过，concept项3.186秒fixture清理EPERM遮蔽前序结果，业务是否跑完未知，不用旧通过替代。之后最终完整concept两次exit=0且cleanup正常；四个入口/模块/样式Node再次通过。全量后追加导航相关Agent附件/双编辑器回归的实际结果见后续收口记录，不预写通过。
- 原画布20%～300%缩放、节点/连词/直接关系、捕获丢失、编辑拖动、undo/redo、保存重开；新完整流程包括CAS三选择/确认中再次冲突/撤销新base/历史恢复/clean历史409/刷新草稿/关闭flush/草稿配额失败/实际hidden显示/迟到导航和JSON/PNG导出。八张最终截图逐张目视，正常/冲突×浅深×1440/390无页面横溢；新冲突入口清楚、窄屏独立一行，原空工具按钮恢复文字，原长标题/焦点输入单行裁切。截图仅Temp评审。

失败与修正：初期回收测试误用业务ID而非token，改真实字段；弹窗测试等待自身open Promise导致卡住，快速重开/确认close continuation和保存busy竞态，改等真实close任务/disabled状态；草稿提示在后续autosave成功前读取，改同一input事件取状态而不放宽断言；reload只等started存在初始化竞态，补等待已有start Promise，原page断言失败不作唯一根因归因。保存中冲突入口明确disabled并在成功/409/异常finally恢复；尾审发现正常hidden被通用display覆盖，补本按钮[hidden]规则及computed display断言。所有失败与冻结批次分开保留，未改业务截止/断言或产品初始化掩盖。

边界：快照/目标非多文件事务，检查与replace间仍有外部FS竞态；Python旧无版本调用不保护调用方早先读到的版本。历史全部保留有磁盘增长成本，未知历史不自动清理。分类多文件部分进度不等于AG-139；Agent概念图/新工具/休眠许可未开放，135以后未开工，未运行模型turn或操作真实工作台/客户端配置。APP_VERSION2026.11.10.1，app/concept及相关CSS缓存20261110-1。决策043～046，实际文件/最终语法和提交检查见台账收口。

清理尚待用户：原批次EPERM留下本轮合成目录Temp/workbench-edge-concept-PQSsuE、Temp/workbench-concept-HsEGyp，无对应浏览器/服务进程。限定Temp路径/名称与无reparse检查后的工具清理仍被自动审批blocked by policy拒绝，未换命令/工具绕过；已异步请用户手工删除，尚待回复及只读确认，不宣称无遗留或已完成134。后续随机fixture正常清理，不触碰上述被拒目标。

AG-134独立验收收口（2026-11-10）：最终全量后仅追加两项导航依赖浏览器，test_agent_attachment_workflows.js exit=0/20.774秒、test_editor_workflows.js exit=0/71.935秒，原始日志仅Temp；没有继续改源码或测试。22Node按批次最终均有通过证据，不冒称首轮整组通过。代码、缓存和领域/API/UI证据已就绪，仍待两个被拒目录手工清理确认后方可结项和提交。

AG-134提交前独立材料检查（2026-11-10）：82Python/48JavaScript语法、8份修改Markdown UTF-8/围栏/67相对链接、四个资源缓存20261110-1及135～143待开始、git diff --check通过；最终status仅20个目标M，无新增生成物/业务数据/凭据/日志/截图或用户既有修改。按本轮concept/attachment/editor fixture前缀查Python/Node/Edge无匹配残留。两个已拒目录最后只读仍True，未再次删除/提问；代码/测试不再修改，提交说明已拟定为Add conditional concept map writes and history，等待清理确认后完成状态和本地提交。


### 2026-11-10 / AG-134 / 完成与清理记录闭合

- 监督更新管理决定：用户最新明确持续执行方案；此前“两个Temp残留清理前不得结项”是监督的管理安排，不是AGENTS或用户强制条件。代码/验收/20文件diff已经只读审查通过，独立合成测试残留不影响应用正确性或AG-135依赖，故应作为独立清理待办而不阻断已验证逻辑修改。保留上文等待、EPERM及blocked by policy原始事实，不抹历史，不再次工具删除/换工具绕过/重复提问。
- 本次只读复核结果：workbench-edge-concept-PQSsuE及workbench-concept-HsEGyp两个精确Temp路径Test-Path均False，对应Python/Node/Edge进程无匹配。未收到新的手工删除回复，故只陈述当前目录已经不存在，不补写是谁或何时删除。两处实际残留已不存在，此独立待办按只读现状闭合；自动审批拒绝作为历史保留。
- 功能与验证完成：原字节revision/条件Prepared JSON及历史、网页冲突/草稿/flush/迟到保护、分类/回收/导出接点均完成；数据/API兼容、原生/外部FS/历史增长/非多文件事务边界见本节与DATA_FORMAT。最终冻结全量384项598.002秒OK/1权限skip；22Node分批通过，最终导航附件20.774秒/双编辑器71.935秒通过；八图逐张目视、82Python/48JS及8Markdown/67链接通过。首轮384失败及后续复验不互相覆盖，无源码/测试尾改。
- 实际文件为上列20个；决策043～046、APP_VERSION2026.11.10.1与四资源缓存20261110-1。最终仅状态/文档记录变更及diff核对后按13.1独立本地提交；下一项仅AG-135获监督派发先设计，136～143不开始。没有真实数据/客户端配置修改或模型turn操作，无新的功能阻断遗留。

## AG-135：图授权、提案、完整预览（已完成）

当前已贯通新鲜图许可（registry4/auth5/log5）、独立concept_map_grants、完整候选/稳定ID/字节预算、共享单调游标与唯一proposal身份、concept_map@1/执行schema3/原始JSON历史、两确认、22工具、root隔离readonly完整画布/全量字段/差异/警告与批准门槛、结果深链及主画布CAS。没有136删除、项目创建或配置写能力、任意路径/shell/通用代理、模型turn或新依赖。最终门禁与实际结果见本节收口；实现及验收已完成。

阶段实际证据（均临时目录/隔离配置，不触及真实库）：

- 基础严格图+旧管理/休眠/原图62项40.383秒，扩展管理22项12.564秒、同源HTTP1项1.127秒通过。7管理真实os._exit点及实际9e43aa3旧管理拒变更；旧普通业务合法修改后发布依赖冲突阻断，限定首快照/日志/root窗口，不概称所有旧业务零写。file/upload/attachment及edit/rotate/withdraw保留auth5和新字段，收窄先于分类业务写，后续失败不扩权。
- 原生真实设置node test_agent_settings.js完整exit0，覆盖完整图授权范围/资源版本、预览零写、取消、明确批准、丢响应刷新查询/撤销及原设置/文件/暂存流程；四张浅深×1440/390图授权截图已逐张目视。JSON完整换行、按钮/focus可见，无页面横向溢出。最早新夹具201状态/取消选择器及窄屏复验失败保留，复用既有agent-scope及等待响应式布局后严格通过。
- 编号/图/授权45项23.290秒通过；游标首轮null被当缺失1失败，修复exists分支后复验。后来新增恢复/create并发、图恢复409、普通record/document/project原冲突策略、未知Agent占用及领取身份前后两真实退出，10项3.682秒通过。旧正式/历史/回收/索引前孤立图占用取max，12并发、所有无历史图永久清除后重实例、失败跳号、完整ZIP真实解压及copytree迁移后继续分配。游标没有依赖空历史目录；缺失/人为删除/部分恢复的承诺限制见决策047。
- 图提案create/update×10真实退出加往返/修订/取消墓碑/网页避让/外改冲突4项14.079秒通过；加跨字段/未知manifest全量预检、prepared撤销/after证明补回执、已完成删除重放/固定目标占用409后7项21.061秒通过。实际旧9e43aa3静态proposal/manifest验证器拒新契约且业务/私人JSON摘要不变，追加篡改单项2.309秒通过；不以此宣称所有旧普通入口不写。历史已落后撤销不发布及必要历史被移除不补回执1项0.752秒通过。各阶段前后SHA/历史/身份/时间/步骤/计划/批准/回执交叉验证，非秘密摘要无法证明文件作者的边界保留。
- 原execution/proposals/提案管理33项43.446秒通过；22工具MCP/旧休眠与图52项64.531秒通过。原始stdio新图完整read/prepare/preview/attested commit/replay、路径拒绝、500节点/1000边完整结构化+文字响应1项2.837秒通过；首轮把schema错误当业务isError的夹具错误已按原-32602协议修正。真实模型遵规不在这些合成确认结论内。
- node test_agent_concept_map_workflows.js多次完整exit0：全图及所有节点边字段/原图/完整稳定ID差异、转义、pan/zoom、后台dirty/draft/全局Delete/CtrlZ/V/paste无副作用、反复dispose、renderer失败禁批、关闭后迟到结果不能复活ticket、不同proposal切换、500节点1000关系所有DOM明细/画布、真实本机批准/落盘。结果锚点实际走原openItemLink/leave/flush/open；v2带label深链打开等待autosave窗口原字节不变，标签显式编辑保存重开保留节点/边ID、箭头和虚线；v1/缺version兼容迁移，未来99仅打开不改原文件。Agent更新当前脏画布的409/草稿/磁盘选择/撤销原输入再CAS保存也贯通。此批初次后台图v2 label旧迁移使授权依赖失效为真实冲突，先调整夹具后按决策048修复产品并补上述完整链；一次草稿键夹具误用旧形式已改原冒号/空间/ID键，未重命名产品键。
- 图候选5项1.414秒通过：纯prepare/实际时间/历史原字节、named-only不可reparent、伪造ID时间拒绝、旧顶层保留/节点额外字段明确警告、500/1000漂亮JSON超过256KiB但紧凑数据合规可完整读取、原始1MiB/紧凑256KiB分别拒超限、graph-only无项目/记录正文权限、effective/operation真实资源交集。插入新测试误带原函数尾4行致NameError，移动回原函数后复验通过，不改实现掩盖失败。

四张完整图预览浅深×1440/390截图已逐张目视；早期截图处于用户缩放/平移后的视口而部分图超出屏，后续验收已每次resize后适应全图并断言所有节点框在shell内，完整画布另可滚动至可视区。所有字段明细和差异保留在同一滚动弹窗，不能只凭首屏截图宣称已阅读；票据不证明DOM或现实人类身份。原主画布全流程Node也完整通过，新主标签Enter传播保护等最终改动仍由后续冻结门禁覆盖。暂无本项自动审批拒绝或新增清理遗留；历史tmp0u2oav7r用户补充回复已删除并只读不存在，仅补现状，不重开历史待办。

阶段剩余项在下文最终收口完成；此处保留当时验收过程。AG-136～143不开始。

AG-135最终冻结全量Python（2026-11-10）：python -m unittest -v，433项419.257秒OK，1项原生symlink权限skip；非Windows仅模拟分支覆盖。未再修改源码或测试。相比首轮只更新文件模拟分支的精确implemented及空effective/grants/operations断言，无实现变化。23Node正在顺序执行，真实隔离Codex仍待运行，状态保持进行中。最新四张浅深1440/390完整图预览已逐张目视：适应全图后节点和关系可见，焦点/按钮清楚，长中文正常换行，无页面横向溢出；全部明细仍需滚动查看，票据不证明人眼阅读。

AG-135冻结Node首批：attachment18.879秒、新图19.595秒、proposal18.681秒均exit0；settings18.961秒在原登记reload第111行超时，诊断仅page unavailable/无页面横向溢出，现有证据不能确定根因。原样单独复验25.606秒越过该处，但第338行旧提示文案断言失败：135提示已改为无旧业务条目权限并说明图独立授权，测试仍查无旧业务数据权限。仅同步该条精确完整提示断言，保留前置空kinds/project_ids/categories/dormant断言，不改实现/超时。两失败日志与stderr留Temp，fixture终于清理无异常，当前对应临时目录无残留；不将已通过3项写成首轮23全绿。重新冻结151文件，唯一变化test_agent_settings.js；Python源码/测试摘要全部未变，其433项419.257秒通过仍有效。重新顺序运行23Node，首次超时根因未知保留。

AG-135设置复验第三次38.428秒失败在新增图撤销尾部第548行：磁盘仍旧read grant而catch busy=true。代码顺序证明确认helper仅click，dialog close续体尚未设busy时旧panel存在/不忙条件即可满足，磁盘断言早于DELETE完成；首次登记reload超时原因仍未知。仅加强测试：捕获真实DELETE完成响应状态，等200、dialog关闭、无pending/busy及重载panel空范围后再读盘，原空grant/kinds断言不变，无实现/超时改动。重新冻结151，唯一变化仍该JS测试，Python433/419.257秒及首批3Node证据有效；先完整settings再余下19Node，不称首轮整组通过。

### 2026-11-10 / AG-135 / 完成

- 完成范围：新鲜图授权、完整只读发现/读取、完整create/update提案及两确认、唯一ProposalStore静态concept_map@1/执行schema3、稳定身份/共享单调游标、原字节历史与恢复、readonly全图/全部字段/差异/警告、严格结果深链。无delete/配置创建/项目创建或模型调用；136～143未开始。
- 最终自动门禁：python -m unittest -v，433项419.257秒OK/1原生symlink权限skip。23个Node按批次全部exit0：首批附件18.879秒/新图19.595秒/提案18.681秒；settings最终完整通过并真实观测同客户端DELETE开始/200响应、operation/version与随后GET重载版本相等、空grant面板/无busy/pending及磁盘[]；其余19项全部通过，其中主图54.491秒、文档附件17.118秒、双编辑器71.858秒、项目筛选8.227秒、时间戳9.746秒。不是首轮整组全绿，前述超时/文案/夹具早读失败及复验保留；登记reload首次超时原因未知，后续完整流程通过，无断言/超时弱化。
- 真实兼容：python codex_agent_acceptance.py，exit0；codex-cli 0.163.0-alpha.10.2、协议2025-11-25、22工具，旧issue/document/todo/info、两确认、追加/更新、重试/取消/重启/撤销通过。隔离数据与CODEX_HOME，model_turns_started=0、user_config_changed=false。这是既有CLI/MCP兼容门禁，不是AG-142真实模型矩阵或对话遵规证明；新图stdio/浏览器/两确认由前述专项证明。
- 冻结/静态验证：151源码/测试/HTML/CSS最终SHA一致，89Python/49JS全文件语法、10修改Markdown UTF-8/围栏/85相对链接、git diff --check通过。Python完成后仅settings测试断言/同步加强，产品/Python摘要不变，监督接受保留433项证据；不将首次冻结失败和中断冒充通过。APP_VERSION2026.11.10.2、六资源缓存20261110-2。
- 必要人工验证：图授权与完整图预览均浅深×1440/390四图逐张目视；长中文/全量JSON换行、focus/disabled/error/空资源和500节点1000关系覆盖，适应全图后节点关系可见，无页面横向溢出。主图保存/冲突/草稿/撤销/JSON-PNG、记录与知识库可视化/Markdown/保存重开由真实浏览器通过；截图仅Temp不入Git。
- 数据/API兼容：旧业务Markdown/附件与旧execution1/2语义保持；旧图宽容读取和网页默认根节点保留，Agent严格完整候选。图新鲜批准才升级registry4/auth5/log5，旧dormant不激活；所有family保留格式下界。图恢复冲突现在409，其他类型恢复原策略不变；v2 label不再自动改ID/结构，v1/缺version仍兼容迁移。新增可移植config/concept-map-ids.json单调游标，原完整ZIP自然包含；完整解压/copytree迁移已实际验证。Graph工具22目录和服务端权限为事实源。
- 风险/边界：不是多文件事务；未知/缺历史/第三方状态保守阻断，已发布仅补原回执；游标/墓碑/历史保留增长，损坏占用停止分配。缺失游标无法区分初次升级与人为删除，升级前永久消失ID无法追溯；部分恢复/旧进程忽略游标/混用版本/外部文件系统竞态不承诺消除。资源派生全集依赖保守，无关成员变化可能需重预览。非秘密摘要不证明作者，票据不证明人眼阅读/现实身份，PNG保留既有节点摘要而非无损备份。首次登记reload超时根因未定，后续原样及最终完整流程均越过且通过，保留证据而不归因OS或新图无关。
- 决策：AG-LOCAL-DEC-047（单调分配）、048（v2稳定label/只迁移旧版）。本次无真实业务数据/私人配置变更、无新增清理拒绝或fixture残留；历史清理回复仅补充闭合。最终目标diff不含数据/凭据/日志/截图/缓存或用户既有修改。下一工作项AG-136仅为交接候选，尚未开始，等待监督派发。

## AG-136 验收记录（2026-11-10，进行中）

范围为四Markdown类型/概念图单条delete，新鲜独立local_web批准及唯一ProposalStore执行4；137以后未开始。领域纯准备、同句柄NTFS无覆盖移动、原字节/身份、完整引用/附件预览、保守集合/索引/排序CAS、真实退出与原回执、普通清理保护均已接入。最终全量门禁尚未执行，不以135的433项/23Node代替。

补充原索引快照/摘要后29项128.360秒OK，含五类型×12真实os._exit共60场景。新增实际HTTP/原始stdio两项2.522秒OK，检查同源/管理令牌/Agent凭据隔离、无初始化读、完整零写预览、明确批准、22工具、禁止held_source、网页独立批准、回收恢复及旧回执。首次HTTP夹具遗漏管理标记403已纠正；随后真实发现旧HTTP装饰把删除链接改成业务链接，产品已修为稳定token校验/原回收站链接，返回增加当前服务web_url而不改持久原回执。

补充7项17.474秒中唯一失败是迁移夹具Temp短路径/长路径未规范化，实际原字节恢复已成立；改resolve目录包含断言并新增旧源仍缺失断言，迁移专项1项1.400秒OK。终结30天内容清理仍保留manifest/receipt/恢复依据；实际UTF8 JSON2MiB及超1字节拒绝、原索引未知/重复及移动前变化均已验证，完整全量仍待。

浏览器最新完整exit0，真实200响应接收后注入授权/业务丢响应，再reload或查询原操作，旧待查询身份一致；新页面ready/app初始化及接入页恢复有CDP诊断。完整info/附件/匹配文档、两readonly图/全部节点边、取消/重开/结果导航flush/普通恢复/旧commit不重删均通过。8张浅深×1440/390授权与图预览已逐张目视，完整JSON换行、全图与明细/按钮清楚，无页面横向溢出；截图仅Temp。布局截图改为等待.main实际到0/244位置而非捕捉过渡，不增超时。此前首次reload home/超时原因未定，保留；取消异步续体及批准响应前早读的夹具等待已加强真实完成状态，不归因全部相同根因。


AG-136最终结论（2026-11-10）：已完成。469项Python569.157秒OK/1原生symlink权限skip，24Node最终全部exit0；首轮旧入库提示兼容失败已按operation恢复原提示，不改断言/超时，仅JS两文案变化，Python/测试摘要保持。163源码/测试/HTML/CSS最终摘要一致、100Python/50JS语法、10修改Markdown链接/围栏及diff检查通过。隔离真实Codex0.163.0-alpha.10.2/2025-11-25/22工具，旧四类型/两确认/恢复重试撤销通过，0模型turn/不改用户配置，不代替142。新删除真实HTTP/stdio、五类型60退出、目录完成态迁移、终结清理、权限/预算/原索引与身份冲突、旧提交不重删及完整浏览器证据见本节与台账；非Windows仅模拟覆盖。默认30天可本机提前purge，附件/历史/排序保留；不是多文件事务，未知/abandon残留继续保守保护。完成136提交交审后已按用户最新指令暂停后续，137未开始。

## AG-137 项目创建验收（已完成）

原生目录发布探针验证同句柄、同身份、已占用目标无覆盖；领域与既有服务器持久化专项分别 4 项和 46 项通过。13 个真实退出覆盖快照/意图/暂存中与完成/发布中与完成/排序/回执/提案；发布中无可信目标不重发，已发布原对象只补固定排序与回执。项目已发布但排序异物的专项证明分开报告且不覆盖；实际 986d6fe 对新私人意图及新项目提案零 JSON 写拒绝。七阶段新 grant 真实退出保留格式下界及原范围；auth7 与文件/暂存/正式附件/图/删除/edit/rotate/revoke 兼容专项通过。新 HTTP/原始 stdio 两项验证真实工具目录、五字段、拒绝越权字段/自报批准、隐藏本机顺序和原回执重放。独立授权测试覆盖未授权、已有覆盖、同字节替代目录拒绝、版本改变/撤销、故障与恢复/放弃后项目保留。

真实浏览器已跑通授权完整预览/取消、项目完整预览/取消不建正式目录、勾选只引导第二独立预览、取消授权后刷新从原项目回执重新进入、真实200后模拟响应丢失并查询独立回执、最终打开新项目。浅深1440/390截图仅留临时评审；初轮发现项目长文块内部横向滚动，已将新预览块改用既有折行样式，当时最终复验和全量门禁尚未执行。


AG-137最终验收：首轮485 Python 628.476秒，唯一旧HTTP状态码断言失败、1原生symlink权限skip；仅强化该测试，test_agent_api 13项12.224秒通过，保留其他不变测试证据，不称全量一次通过。25 Node最终全过；首轮新增项目刷新测试误读旧上下文，仅加强等待真实新窗口后复验，产品/超时不变。最终浅深1440/390共12图逐张目视，授权、项目和独立访问预览均折行，无页面横向溢出。隔离Codex0.167.0-alpha.3.2/2025-11-25/22工具旧流程通过，0模型turn/未改用户配置，不代替142。174源码/测试/HTML/CSS最终SHA及110Python/51JS全语法、10Markdown/88链接、差异检查通过。AG-137已完成；138未开始。

## AG-138 项目级联删除验收（2026-11-10）

- 原生 NTFS 专项覆盖完整目录原身份、原字节、目录和文件身份、带命名数据流的文件、多硬链接、未知成员、固定回收身份长度和移动前后竞争。最终扫描前变化阻止移动，最终扫描后变化可能已移动且证据失败，测试证明保留现场。
- 实际进程退出覆盖持久 manifest、移动 applying、已移动、索引已落和原回执已落五个阶段。应用中缺原回收对象时保护源和业务写入。原回收证据足够时补齐同一操作，保留外部重新出现的源。完整副本可按可移植证据恢复，同 ID 碰撞和被改写回收字节阻止恢复或清理。
- 实际旧版本 `6f9722c` 在首个私人快照、prepared 日志、registry 门槛及 registry 已发布四个阶段均拒绝恢复且零 JSON 改写。新版本将孤立快照终结为放弃并保留 registry7 下界，其余三个阶段恢复至 auth8。授权轮换、撤销与相同确认重试通过。
- 实际 HTTP 与原始 stdio 覆盖新授权管理边界、`list_projects` 原始版本、原始预览及本机批准、对话自报拒绝、受控回执、恢复后的原回执重放。隔离真实 Codex CLI 0.167.0-alpha.3.2 协议 2025-11-25 和 22 工具通过旧类型、两确认、恢复与撤销，未启动模型 turn 或修改用户配置。
- 实际浏览器通过逐个附件选择、完整授权、本机项目级联批准、两张及以上保留关联图画布和全部节点边字段、回收深链、原 ID 恢复及关联图原字节保留。验收捕获授权及级联预览的浅色/深色、1440/390 布局。窄屏首轮摘要需要区块内横向滚动，复用全文样式后换行，无页面或目录清单横向溢出。
- 首轮全量 Python 为 492 项，607.473 秒。唯一失败为休眠客户端的已实现目录仍预期旧范围，已同步断言并加强未生效检查。另有一项原生 symlink 权限跳过。首轮 25 项 Node 中仅时间戳浏览器用例失败，保持用例与产品不变单独复验通过。一次并行期间的删除浏览器复验超时于启动，顺序复验通过。最终完整门禁结果以台账收口为准。
- 最终冻结版 Node 批次 24 项直接通过，通用编辑器在等待真实新页面时超时，随后同一版本、同一用例独立执行 69.698 秒通过。两批中的时间戳与通用编辑器失败均保留记录。新增项目级联浏览器用例在最终批次 20.449 秒通过。
- 最终全量 Python 为 493 项，655.573 秒，492 通过、1 项原生 symlink 权限跳过。AG-138 验收完成，实施边界和实际文件见[台账](AI_AGENT_PROGRESS.md)。

## AG-139 分类变更与授权迁移（2026-11-10）

- 三体系纯计划覆盖四种操作、空分类、默认分类和名称代次。仓储重开核对文档原正文和历史、分类内模式与排序、附属项目图归属、独立附件字节和关联标签。新独立附件删除只移动独立条目的分类，记录附件的同名分类保留。
- 具体许可与已有成员读取分别检查。默认分类原许可若扩大现有成员范围，拒绝整案。隐式建类消费原空缺名称许可，旧名称后续重用不恢复许可。实际专项还验证了独立附件缺少原索引授权时的通用拒绝、项目关联图按既有项目授权预览，以及两个并发批准只返回同一回执。
- 实际进程退出覆盖 manifest、客户端已收窄、历史已落、业务已写、客户端已补发、回执已落六处。重启后查询原票据返回同一回执，终结后清除已提交的私人计划。业务已经写入而原历史缺失时继续保持收窄，原证据恢复后可核验续办。
- 使用实际旧版 `9ed9006` 在首个私人快照、prepared 日志、registry 门槛与 registry 已发布四个阶段核验。旧版均拒绝且业务和私有 JSON 保持原字节。新版放弃孤立快照，恢复其余三个阶段，并保留 registry8 下界。
- 浏览器覆盖设置授权、取消、完整影响与脱敏授权、本机批准、长中文及 HTML 转义、三类普通网页入口、分类名中的空格与符号、中文项目路径及批准响应丢失后同票据重放。授权与提案预览截图覆盖浅色/深色、1440/390，检查了布局与横向溢出。项目附件实测发现旧请求会在完成后重发读取并抢占新请求，加入已加载项目检查后实测通过。
- 隔离真实 Codex CLI 0.167.0-alpha.3.2、MCP 协议 2025-11-25、22 工具通过。Codex 准备新分类，拒绝自报批准，本机批准后可查询同一回执并在重启后读取分类。0 个模型 turn，用户配置未改。
- 普通旧全量保存保留兼容数据语义。未初始化空间和旧全量兼容入口的多文件中断可能需要人工核查。完整最终门禁和状态见[台账](AI_AGENT_PROGRESS.md)。
