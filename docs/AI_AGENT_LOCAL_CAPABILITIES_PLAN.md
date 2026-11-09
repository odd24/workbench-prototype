# AI Agent 本机能力扩展执行方案

日期：2026-11-09。规划工作项：AG-127；实现与交付工作项：AG-128～143。

主方案：[AI_AGENT_PLAN.md](AI_AGENT_PLAN.md)。前期扩展：[AI_AGENT_EXTENSION_PLAN.md](AI_AGENT_EXTENSION_PLAN.md)。实施事实与状态：[AI_AGENT_PROGRESS.md](AI_AGENT_PROGRESS.md)。执行规范：[AGENTS.md](../AGENTS.md)。

**当前执行状态（2026-11-09）：用户最新明确“现在开始执行方案”，AG-128 已完成授权基础，尚未开放新增业务；AG-129执行基础已完成、AG-130～143待开始，状态以台账为准。此前 AG-127 仅文档和暂停实施是历史事实。方案不等于能力已实现或验收；不得提前开放后续业务工具或操作真实客户端。**

## 1. 目标与交付范围

继续采用单用户、单机本地、loopback 服务、Python 标准库后端、原生前端、无构建步骤和无运行时第三方依赖。远程 AG-122～125 保持已取消，不重新纳入交付前置。

| 能力 | 拟交付范围 | 主要用户流程 |
| --- | --- | --- |
| 上传附件 | 记录附件、项目独立附件、知识库附件 | 选择来源→暂存→提案→文件信息及正文/索引差异预览→确认→正式入库 |
| 读取本机文件 | 用户明确授权的具体文件，文本分段读取，二进制文件可作附件来源 | 本机授权→不透明 file_id→限范围读取或上传 |
| 生成概念图 | 查询、完整读取、新建、更新、图形预览、结果链接 | 外部 Agent 输出节点与边→严格校验→完整预览→确认保存 |
| 删除正式内容 | issue/todo/info/document/concept_map，另设项目级联删除 | 读取当前版本→删除影响预览→网页独立批准→回收站→结果查询 |
| 创建项目 | 名称、说明、状态、颜色、已有工作流模板 | 项目提案→网页批准→创建→查询回执，可另行明确授权 |
| 分类与工作流 | 三类分类增删改及排序；模板、状态变更与使用方迁移 | 生成完整影响计划→网页批准→持久迁移→重读验证 |

不包含模型调用、内置 AI 聊天、模型 API Key 管理、远程接入、自动抓取聊天、自动执行命令、任意文件写入、任意 HTTP 代理、永久删除、清空回收站、自动解压或内容解析引擎。文件授权首期不包括目录递归扫描。标签系统不在本次配置扩展范围。

正式业务写入继续先生成独立提案，不提前创建正式内容作为预览。新建跨资源批量业务事务不是首期接口；一个提案内部为完成同一操作而涉及多个文件，必须有执行计划和恢复日志。

## 2. 已核查事实与历史范围

2026-11-09 依据当前仓库核查；每项实施前必须用 rg 重查读写点，不能用此表替代最新代码事实。

| 当前实现接点 | 需要补齐的能力 |
| --- | --- |
| agent_tools.py/agent_service.py 支持 issue/document/todo/info 和 create/append/update | 显式能力授权、受控新增类型/操作、能力协商和错误契约 |
| agent_proposals.py 有 schema 1/2、Markdown 快照、幂等回执和恢复 | 版本化操作处理器，支持 JSON、附件、目录、移动及多资源配置迁移 |
| agent_http.py 在业务锁和凭据锁内分派请求 | 文件流传输需分离长 I/O 与短临界区，重查授权后才能发布正式结果 |
| assets.py 已有记录/项目流式上传，记录元数据与项目附件索引分离 | 私人暂存、文件摘要绑定、提案提交与部分落盘恢复；新增知识库附件领域能力 |
| concept_maps.py 归一化、持久化和 CRUD 已存在 | 内容版本、条件写入、历史、Agent 预览和网页自动保存冲突处理 |
| projects.py 创建目录、README 和排序 | 稳定身份保留、目录残留检查、可恢复创建与独立授权结果 |
| repository.py 回收站先移动再更新索引，已有自动保留期清理 | 持久移动计划、幂等删除、在途保护及各中断点恢复 |
| configuration.py 分类迁移会依次改文档/配置/排序，并协调授权 | 完整影响预演、版本检查和持久迁移；扩展概念图/项目附件分类 |
| 工作流配置已有归一化、校验和使用方处理 | Agent 严格输入、显式状态映射、迁移计划和恢复，不能简单开放整份配置覆盖 |
| 本机管理已有同源会话与凭据日志 | 新授权复用相同边界；Agent 不得管理授权或借业务配置提案扩权 |

README 原“AG-116～126 尚未开始”与最终验收冲突，本次修正当前摘要。主方案和上一扩展分册中附件/删除等排除项是各自历史阶段范围；本分册只定义未来工作，不回写旧实现或验收结论。

## 3. 权限、确认与隐私契约（AG-128）

### 3.1 新能力白名单

保留 read/propose/commit 基础 scopes，新增独立能力白名单。以下名称为拟定契约，在 AG-128 契约测试中定稿；不能复用 project_ids/categories 通配符隐式开启。

| 能力 | 限定资源 |
| --- | --- |
| files.read | 当前客户端明确获授的 file_id 与用途 |
| attachments.read / attachments.write | 授权记录、文档或项目 |
| concept_maps.read / concept_maps.write | 授权项目、独立概念图分类或指定图 |
| items.delete | 授权类型和具体归属范围 |
| projects.create | 工作空间级显式创建许可 |
| projects.delete | 明确允许级联删除的项目 |
| categories.write | 文档/概念图/项目附件分类体系、范围和操作 |
| workflows.write | 指定模板、操作及允许迁移的项目 |

有效权限为基础 scope、能力、资源范围、操作、确认策略的共同约束。客户端数据和管理接口拟增加 capability_grants，使用版本化严格结构，不把任意字符串当成可执行权限；开工时定义 schema、默认值与管理 revision。缺失新字段等于没有新能力，旧 kinds 缺省继续原兼容规则。

- 旧客户端即使有全部项目/全部分类，也不会自动获得新类型、新操作或本机文件访问。
- 管理 UI/CLI 通过 CredentialManager 的同一日志、跨进程锁、预期版本及 report/abandon 管理；令牌轮换不扩权。
- read、propose、commit 分别检查；网页批准也不能突破原客户端有效范围。
- 概念图项目范围和独立图范围分别校验，project_id 为空不表示全部可见。
- 分类重命名/删除同步权限；失败保持收窄，不能把旧分类改成“未分类”授权。
- 查询、搜索、目录、引用、错误、文件名及预览差异均不得泄露不可访问资源。
- Agent 不得读凭据、修改授权、创建文件授权、启停接入或通过业务提案改写私人设置。

### 3.2 最低确认方式

| 操作 | 最低要求 |
| --- | --- |
| 已授权文件的分段读取 | 有效文件授权及用途匹配；不逐段重复批准 |
| 新建/扩大文件授权 | 同源本机管理会话明确授权，不由 Agent 自报 |
| 普通附件新建、概念图新建/更新 | agent_attested 或 local_web，服从客户端和操作最低策略 |
| 删除、创建项目、分类/工作流迁移 | 强制 local_web，不接受 user_confirmed 绕过 |

文件授权页明确说明内容将返回所选外部 Agent 客户端，后续可能进入该客户端的模型上下文。网页批准证明持有管理会话的操作者批准，不宣称现实人类身份认证。收紧策略使旧未提交预览失效，不能降级旧提案确认要求。

## 4. 统一提案、执行计划与恢复（AG-129）

### 4.1 拟定资源与操作

| kind | 操作 | 内容边界 |
| --- | --- | --- |
| issue/document/todo/info | 保留 create/append/update；新增 delete | 旧字段语义不变，删除不接受替换正文 |
| attachment | create | owner 类型/ID、upload_id、分类和是否插入正文；不接受目标磁盘路径 |
| concept_map | create/update/delete | 完整候选图；第一版无复杂局部补丁 |
| project | create/delete | 项目元数据或完整级联删除计划；不新增任意项目设置覆盖 |
| category_change | create/rename/delete/reorder | 分类体系、范围、名称/顺序和影响计划 |
| workflow_change | create/copy/rename/add_status/rename_status/delete_status/reorder/switch | 指定模板或项目、明确映射、完整影响计划 |

最终枚举与分派在各项定稿并通过契约测试；不允许将 kind 当模块名或任意方法执行。新增操作处理器必须有静态白名单，归一化与领域规则仍在现有领域仓储。若实际模块边界变化超过本分册已登记范围，另行登记 RF 项。

### 4.2 新持久格式

拟新增 proposal schema=3、独立执行日志版本与摘要算法标识，具体字段在 AG-129 定稿。保留 schema=1/2 原读取、摘要、历史和恢复，不能静默重算旧已预览摘要。

新格式至少绑定 workspace/client、kind/operation、目标稳定身份、提案版本、base_revision、授权 revision、配置和依赖版本、完整归一化候选、影响列表、确认策略、源文件/upload 摘要、预览摘要及处理器版本。依赖集合的成员增加/减少也须导致冲突，不能只检查原清单成员版本。

继续使用既有提案状态；执行日志记录 prepared/applying/completed/recovery_required 等阶段，状态命名与现有日志兼容后定稿，不另造平行提案状态机。

执行步骤：校验并预演→完整预览→当前版本批准→重查权限/目标/依赖→持久日志和快照→逐步应用→重读→回执。request_id 同输入返回原提案，不同输入返回 idempotency_conflict；提交以 proposal/version 幂等，回执长期保留。

### 4.3 崩溃恢复

- 每步骤记录受控目标身份、前后摘要、存在性、历史版本、稳定 ID 和实际完成情况；路径只由服务端派生并限于允许目录。
- 尚未应用时重新检查授权；已完整应用则补回原回执；部分应用按原计划恢复，不能分配新 ID 重建。
- 第三方内容、损坏日志、未知版本、无法区分的移动结果进入 recovery_required，保留现场，不自动覆盖或回滚第三方修改。
- 在途操作阻止冲突写入和相应暂存/回收站清理。初期可保持既有保守写入保护，未验证前不缩小阻塞范围。
- 分类/工作流权限变化与业务迁移分阶段记录，遵守空间切换锁→业务锁→私人配置锁顺序，不反向获取。
- 长流式 I/O 不持业务/凭据锁；开始和结束检查授权，正式发布在短临界区再次验证。撤销后不发布新结果；已向客户端发送的内容无法收回，需明确剩余边界。
- 单文件原子替换不代表多文件事务原子性。恢复能力必须由真实进程退出、重启和磁盘重读证明。

新状态仍与编辑器草稿、正式搜索、反向链接和普通导出隔离；恢复入口复用 report/abandon 语义，不通过删除 .agent 绕过。

## 5. 本机文件授权与读取（AG-130）

### 5.1 授权模型与管理入口

在私人配置目录按空间保存版本化文件授权；实际路径、file_id、client_id、用途、有效期、大小限制、文件身份、摘要和撤销状态不得进入 Git、普通业务数据或可移植 ZIP。

管理页面允许用户输入具体文件路径并验证；浏览器文件选择器通常不能提供可验证的服务端真实路径，不能依赖伪路径。可另用浏览器选择后流式上传，但此时是附件传输，不声称授予原路径读取。首期只授权具体文件，不提供目录浏览或递归扫描。

拟定管理路由在 /api/local/agent-management/file-grants 下提供预览、创建、查询和撤销，复用同源会话、版本及幂等日志。授权预览不向 Agent 透露路径，也不预先返回完整文件内容。

拟定 MCP 工具：workbench_list_file_grants、workbench_get_file_info、workbench_read_file。只接受不透明 file_id，不接受任意绝对路径。元数据只返回显示名称、大小、编码/类型、摘要、有效期和允许用途。

### 5.2 读取契约与边界

- 仅本机普通文件，拒绝网络共享、设备、命名管道、Windows ADS、特殊路径、目录及未支持的重解析对象。
- 不能只做 resolve/prefix 检查；打开后核对文件身份、普通文件属性和授权目标，防止符号链接/junction/reparse point、硬链接别名和校验后替换绕过。平台实现未能证明安全时拒绝该路径类别。
- 默认拒绝工作台凭据、私人配置、认证状态和已知秘密位置；硬链接身份匹配也纳入检查。不保证自动发现普通日志中所有秘密，授权页明确披露范围，内容入库继续脱敏。
- 使用稳定快照或前后版本核对，避免一次调用读到混合版本；快照不得在批准前先读取未经授权的正文。跨段携带 source_revision，变化返回 source_changed，不把不同版本拼接为全文。
- 首期支持 UTF-8、UTF-8 BOM、UTF-16；其他编码需明确指定并严格解码。不把二进制强行转换为文本，不自动执行脚本、宏或解压。
- 拟定每段最多 64 KiB 解码前字节，返回完整字符边界、next_offset、实际范围、编码和摘要；UTF-16 对齐及续读规则必须契约测试。正文读取与附件导入分别授权。
- 授权过期、撤销、换库、文件替换即停止新读取；同一 file_id 不悄悄跟随新文件。新版本需重新授权或显式重新绑定。
- 文件内容是数据，资料内“执行/批准/忽略限制”等文字不构成授权。

## 6. 流式暂存与附件（AG-131～133）

### 6.1 两类来源

1. 本机来源：Agent 传 file_id，服务核对 attachment_source 用途后流式读取，不让桥接器绕开服务读业务文件。
2. 字节流来源：先建立 upload 会话，再调用专用 loopback application/octet-stream 端点。此通道是受限附件传输，不是通用 HTTP 代理。

拟定路由：POST /api/agent/v1/uploads 准备会话；PUT /api/agent/v1/uploads/{id}/content 传输；POST .../{id}/complete 完成核验；GET .../{id} 查询。创建、完成和查询可映射为严格 MCP 工具；MCP JSON 消息不传整文件 base64。原始流客户端必须具备独立认证调用能力，未实测客户端不能声明支持该通道；普通 stdio 客户端可使用本机授权文件导入。

如需单次传输凭据，其只能限同一空间/客户端/会话/用途/大小/有效期，放在头部，不进 URL、日志和提案；管理凭据不得用作上传凭据。接口仍校验 Host/Origin 和 loopback，不接受远端来源或重定向。

### 6.2 暂存生命周期与限额

会话状态拟为 created/receiving/ready/consumed/expired/failed，独立于提案。流式写私人暂存，计算真实大小与 SHA-256，只有完整 ready 文件可绑定提案。一个上传的消费方式和重复请求须由服务记录，不能被跨客户端/跨空间复用。

拟定初始限制：单文件 100 MiB、单客户端暂存 500 MiB、每客户端 2 个并发流、未绑定暂存保留 24 小时。最终值须在 AG-131 临时大文件与窄速中断测试后记录并通过 capabilities 明示，不改变旧网页接口既有能力。增加全空间总配额及磁盘不足检查，避免多个客户端绕过单客户端配额。

限定长度、空闲超时、总时限及读取块大小；不依赖 Content-Type 判断安全性。只存储，不执行、不自动解压；浏览器预览沿用受控内容类型与下载策略。流中断清理可判定半成品，在途事务绑定文件不自动删除。

### 6.3 附件提案与正式写入

提案 content 拟包含 owner_kind/owner_id、upload_id、display_name、category、insert_link；服务返回归一化后的完整附件元数据及正文/索引差异。预览包含来源显示名、大小、摘要、类型、归属、最终名称/相对链接、分类和版本，不向 MCP 暴露实际路径。

- 记录附件继续用记录 front matter，项目独立附件继续用项目索引，严禁混用。
- 同名采用服务端唯一分配，分配结果纳入预览/日志；如果最终名称或正文变化，必须生成新版本重新预览。
- 文件与正文/索引分步应用，记录每一步前后摘要。提交后重读二进制、元数据和正文；响应丢失查询原回执，不能重新上传生成重复附件。
- 不对现有附件直接覆盖；替换或删除附件不是此阶段 create 的隐式行为。
- 知识库新增 DocumentRepository/AttachmentRepository 领域协作、受控引用和网页上传入口，明确采用兼容的正文相对链接及服务生成元数据；最终序列化方案在 AG-133 先写入 DATA_FORMAT 并完成往返测试，不另建业务事实源。
- 知识库同时覆盖显示、历史、删除/恢复、反向引用、孤儿识别、导出备份；不能在未检查其他引用前清理文件。

## 7. 概念图（AG-134、135）

由外部 Agent 输出结构化数据，服务不调用模型；首期 create/update 使用完整候选图，不做复杂局部 patch。图文关联按已有引用能力评估，不新增未经登记的引用语法。

沿用 JSON version=2、节点/边稳定 ID、concept/linking_phrase、箭头及视口语义；保持最多 500 节点/1000 边、现有文字/坐标/尺寸/颜色/缩放限制。Agent 请求先严格校验重复 ID、无效引用、类型和未知字段，再复用归一化器；已有宽容读取不被移除。有意义的纠正/截断不能静默丢内容，必须拒绝或在完整预览显式警告。

新增磁盘字节 SHA-256 revision、expected_revision 条件更新、历史快照和 Prepared 写入能力；旧调用兼容边界须说明。网页读取、自动保存、关闭 flush、冲突提示和 Agent 写入同步接入，避免旧页面覆盖新图。

完整预览包含画布、节点/边全量明细、文字和元数据差异、布局变化及警告。大图可分页/分段检查，但批准绑定完整内容摘要；不能只看缩略图或部分页即视为完整预览。更新保留未变节点/边 ID，不以重新编号伪装同一图。

结果深链接需校验图 ID，打开既有画布；验证保存重开、撤销重做、自动保存、关闭 flush、网页并发、浅深主题/桌面窄屏及导出。

## 8. 删除与回收站（AG-136、138）

delete 提案只接受目标 ID、base_revision 和必要来源说明，服务生成完整删除影响；不接受删除路径或替换正文。强制 local_web。

预览包含身份/标题/类型/归属、完整正文和结构化字段、版本、附件列表、引用影响和回收站保留规则。项目级联另列全部子条目、独立附件、目录及相关概念图的处理；项目外关联概念图不隐式删除，须在计划中说明保留及失去归属的处理并经校验。

- 删除默认移动到 .trash，不开放 purge、清空回收站或孤儿清理。
- 文件/目录移动、索引写入、缓存失效、排序维护与回执均登记阶段。恢复目标只使用服务端白名单，不接受日志中任意机器路径。
- 稳定删除 operation_id/trash token；重复提交返回原回执，不生成第二项。
- 预览后修改、依赖新增/删除或源位置异常，提交返回冲突。
- 目标后来恢复，重放旧删除提案仍返回旧完成结果，不再次删除；正式条目后续状态与原回执分开表达。
- 回收站自动保留期清理和网页恢复须识别在途操作；删除恢复与 ID 分配、历史和缓存一起验证。
- 删除条目不立即删除可能共享的附件，不自动清除正文引用；预览明确断链影响。
- 项目级联要求 projects.delete 及完整子资源读取/删除范围，不以部分条目权限触发。未能完整授权的影响计划不得提交。
- 回执提供受控回收站身份和网页结果，不返回原始机器路径。首期恢复仍由网页入口完成。

## 9. 创建项目（AG-137）

字段拟为 name/description/status/color/workflow_template；服务校验名称、状态、安全颜色和已存在模板，不提供任意项目配置覆盖。ID 仍由领域仓储分配、标题变化不改 ID。

预览展示完整元数据、说明、拟定身份和目录内容。身份保留记录属于提案流程，不提前建立正式 README 或业务目录；提交前如身份竞争导致变化，需新版本预览，不能静默改名。

创建计划覆盖 README、子目录和排序；检查磁盘残留目录、回收站及在途身份，不覆盖或接管已有目录。并发/响应丢失/重启保持同一项目，不重新分配 ID。

创建许可不等于访问新项目许可。网页可另设“同时授权此客户端访问新项目”的明确选项，使用独立 CredentialManager 操作、幂等键和回执；Agent 不能在业务 content 中请求扩权。项目成功但授权失败时分开返回事实并可恢复，不重建项目，不扩大到全部项目。

## 10. 分类与工作流（AG-139、140）

### 10.1 三类分类

分别处理知识库、概念图和项目独立附件分类；记录附件类别继续沿用原索引语义，不混用为项目独立附件。支持 create/rename/delete/reorder，不能用整份配置覆盖规避影响检查。

知识库同步文档分类、空分类、分类顺序、分类内模式/排序及授权；概念图同步图分类/分类列表/授权；项目附件同步类别和项目附件索引。删除只迁移到“未分类”，不删除内容；系统默认分类不可删除。

预演需给出全部受影响 ID/版本、 before/after 配置、排序及授权变更。迁移前收窄旧授权，迁移成功后只恢复到等价新名称；删除不授予未分类。多文件中断恢复保持收窄，不能扩大权限补救。分类名称复用与通配授权在测试中单独覆盖。

### 10.2 工作流

支持模板新建/复制/重命名，状态新增/重命名/排序，删除未用状态，使用中状态显式映射后删除，以及项目切换模板。info 保持无状态，旧 idea 只兼容读取，不重新开放创建。

计划绑定模板/全局配置/项目 README/受影响记录及排序的版本和集合，展示所有 before/after、状态映射、待办完成语义、历史计划和无法映射项。删除使用中状态无映射则拒绝，不能静默选第一个状态。模板切换不改记录稳定 ID；completed 由目标工作流语义推导，不能由 Agent 直接写。

示例：把“处理中”改为“进行中”，须一起预览模板、所有迁移记录、看板/状态排序、待办完成语义。局部失败日志能说明哪些文件已改，恢复前重查第三方内容。

配置能力不隐含业务内容读取权；涉及未授权项目/条目而无法展示完整计划时，Agent 路径拒绝，由本机操作者另行处理，不能隐藏影响后继续批准。普通网页相关变更共用校验、协调和日志入口，避免网页绕过正在进行的迁移。

## 11. HTTP、MCP 与前端契约

保持 /api/agent/v1 和现有工具，按能力增量扩展；未知参数严格拒绝。新 kind/operation 逐项通过旧客户端目录解析测试。若发现必须改变旧语义，先登记版本设计，不能静默破坏旧请求。

拟新增 files、attachments、uploads 受控端点及对应必要工具，业务写入复用 prepare/revise/preview/commit/get/cancel。管理 API 仍只在 /api/local/agent-management，不加入 MCP，不接受 Agent 凭据。URL 参数前后端对称编码，文件/分类/项目 ID 不拼成未校验路径。

capabilities 明示 authorized capabilities、kind_operations、kind_fields、最低确认策略、提案/日志版本、读取编码、文件和暂存限额、可用传输方式。旧 confirmation_mode 等兼容字段不移除。工具提示和初始化 AGENT_RULES 同步新边界；不能仅在 AGENTS.md 约束其他客户端。

| 条件 | 拟定响应 |
| --- | --- |
| 非法字段/映射/编码 | 400，结构化不可自动重试错误 |
| 缺少操作权限 | 403 forbidden |
| 不存在或不可见的资源 | 404 not_found，避免存在性泄露 |
| 源变化/目标变化/依赖变化 | 409 source_changed/version_conflict/dependency_changed |
| 超限 | 413；429 rate_limited 含明确重试建议 |
| 未网页批准/提案状态无效 | 沿用现有对应状态码及 confirmation_required/invalid_state 语义 |
| 不完整上传/恢复不确定 | 明确 upload_incomplete/recovery_required，先查同一操作 |
| 未处理异常 | 500 脱敏错误，不输出文件正文、凭据或私有路径 |

前端复用 agent-settings/agent-proposals、统一 API、对话框、只读 Markdown 和现有概念图工厂。每个实现项同步自己的最小可用 UI 和专项验收，不能等 AG-141 才补必需预览。AG-141 做跨能力整体验收和恢复/诊断补齐。

上传进度、取消及响应丢失明确区分“停止传输/停止等待”和“业务已提交”；取消不能声称回滚已提交内容。render 后监听和过期异步结果遵守原规范。修改 JS/CSS 更新 index.html 缓存版本，媒体查询只放 responsive.css。

## 12. 工作项、文件与独立验收

以下是预计接点，不是要求创建所有候选文件。实施前确定最小变更，不复制现有 CRUD 或另建 Repository 进程。AG-127 为本文档治理；AG-128/129已完成、AG-130～143待开始，实际状态以台账为准。

| ID | 范围/依赖 | 预计文件或模块 | 独立完成证据 |
| --- | --- | --- | --- |
| AG-127 | 详细方案及登记；无依赖 | 本文、台账、主方案、旧扩展入口、README/AGENTS/接入使用维护 | 文档链接/围栏/状态/依赖及 diff 检查；无功能启动 |
| AG-128 | 授权、管理 UI/CLI、能力协商；127 | agent_security/management/management_http/service/tools、CLI、agent-settings/index、管理与 MCP 测试 | 旧权限无扩张，新字段严格校验，轮换/撤销/并发/持久恢复，设置真实浏览器 |
| AG-129 | 提案格式和恢复基础；128 | agent_proposals、write_coordinator、领域 Prepared 接口、proposal_management、持久故障测试 | 新旧混合日志、未知版本、每落盘阶段异常/进程退出、磁盘重读、第三方修改拒绝 |
| AG-130 | 文件授权和分段读取；128 | 候选 agent_files、management/http/service/tools、设置 UI、路径/编码测试 | 具体文件授权、过期撤销、替换/链接/特殊文件拒绝、多编码分段不混版、无路径泄露 |
| AG-131 | 流式暂存与配额；129 | 候选 agent_uploads、agent_http、HTTP 流处理、配置和流式测试 | 大文件内存有界、中断/限额/超时/磁盘满/取消、并发配额、在途不清理、重启查询 |
| AG-132 | 记录/项目附件；130、131 | assets/records/repository、Agent 提案处理器、附件前端、领域/HTTP/浏览器测试 | 二进制与元数据/正文摘要一致、重放不重复、各阶段恢复、导出和重新加载 |
| AG-133 | 知识库附件；131、132 | assets/documents、markdown_image/路径处理、知识库 UI、导出/孤儿识别、DATA_FORMAT | 可视化→Markdown→保存重开、引用保留、删除恢复、共享引用不误清理、备份包含附件 |
| AG-134 | 图版本/历史/准备写入；129 | concept_maps/repository/history、http_api、concept-map.js、图契约/浏览器测试 | 稳定 ID、条件写入、外部修改/网页冲突、历史、自动保存/flush/撤销/重开 |
| AG-135 | 图 Agent 能力和预览；128、134 | agent_service/tools/http/提案处理器、agent-proposals/navigation/index | 严格字段与图限制、全图/明细预览、两确认模式、结果链接、真实画布保存与导出 |
| AG-136 | 条目删除/回收站；129、135 | repository 回收站、records/documents/concept_maps、提案处理器、trash/提案 UI | 四 Markdown 类型及图删除、移动/索引中断恢复、旧提交不再删恢复项、清理在途保护 |
| AG-137 | 项目创建/排序/独立授权；129 | projects/repository、提案处理器、CredentialManager、提案 UI | 并发身份、残留目录、README/排序恢复、项目成功授权失败分别查询、无自动扩权 |
| AG-138 | 项目级联删除；136、137 | projects/repository/回收站、Agent 影响计划、项目/提案 UI | 子资源全集授权和版本、项目外关联图不误删、目录/索引恢复、恢复后旧操作不再删除 |
| AG-139 | 分类变更及授权迁移；129、133、135 | configuration/concept_maps/assets、agent_management、提案处理器、分类/提案 UI | 三体系空分类/顺序保留，重命名/删除权限不扩大，多文件失败/重启、URL 编解码 |
| AG-140 | 工作流及状态迁移；129、137 | configuration/projects/records、提案处理器、管理/提案 UI | 映射必填、状态使用检查、集合变化冲突、todo 完成语义、排序/历史、各阶段恢复 |
| AG-141 | UI/恢复/诊断整体验收；132～140 | agent-settings/proposals/diagnostics、管理路由、相关 Node 测试 | 每类型完整预览、禁用/错误/焦点、浅深×桌面窄屏、长中文/空库/大量数据及报告入口 |
| AG-142 | 真实客户端；141 | codex_agent_acceptance、workbuddy_agent_acceptance、隔离夹具、兼容矩阵和新验收记录 | 按真实版本工具发现、读取/提案/确认、负向权限、重放/响应丢失/重启/撤销；清理证据 |
| AG-143 | 运维/兼容/最终交付；142 | lifecycle 验收、README/AGENTS/架构/格式/维护/使用/台账、新验收记录 | 全量门禁、备份恢复、停用/降级/未知日志、无秘密泄露、临时身份进程目录清理 |

建议顺序：127→128→129→130→131→132→133→134→135→136→137→138→139→140→141→142→143。AG-136 比初始对话表补充 AG-135 依赖，确保概念图删除接点已具备；这只细化规划，不改变旧项。可以按未来用户授权调整独立项顺序，但高风险项一次只主动推进一个，依赖未完成不得越过。

每项开工：git status、重查 AGENTS 和接点、台账进行中、范围/文件/检查/风险；每项完成：实际结果、兼容、失败重跑、遗留、下一项及独立本地提交。禁止未测 WIP 作为终点。发现超出已登记范围的模块重构另记 RF 项。

## 13. 验收矩阵与交付门禁

### 13.1 全部操作的共同矩阵

成功、非法输入、资源缺失、旧格式、完整预览、取消、旧版确认、修改后重预览、未授权/撤销/收窄/换库、并发、重复 request_id、响应丢失先查询、各阶段异常/进程退出、目标第三方改动、未知格式、重启恢复。写入必须重读磁盘或重新实例化，不能只检查内存响应。

源文件替换/编码边界、流中断/磁盘满/配额、删除后恢复再重放、依赖集合新增、状态映射缺失、授权迁移中断分别做专项。运行自动化使用 TemporaryDirectory；路径跳转和 Windows 文件身份按目标平台实测，不以字符串测试代替。

### 13.2 自动化与浏览器

实施各项运行相关专项；交付执行 python -m unittest -v、全 Python py_compile、全 JS node --check、全部 test*.js 契约和 git diff --check。不能预写测试数量和通过结果。新增回归须证明实际风险，不为低影响文档修改添加镜像测试。

管理变更至少 node test_agent_settings.js；提案及图新增专项。UI 必须启临时服务真实浏览器验证浅/深、桌面/窄屏、hover/focus/disabled/error、长中文、空数据和大量数据。知识库/记录编辑器变更各做可视化→Markdown→保存→重开。图验证自动保存、关闭 flush、撤销重做和并发冲突。新流式规模、图上限及配置大迁移必须运行对应性能场景；是否扩展 performance_acceptance.py/visual_baseline.js 在开工记录明确，不借旧验收宣称新的性能/视觉通过。

### 13.3 真实客户端

Codex、WorkBuddy 分别记录客户端/CLI/协议版本、工具目录刷新、完整文件读取、附件来源、图新建更新、删除、项目、分类/工作流和最低确认方式。local_web 自报绕过必须拒绝；每个支持 agent_attested 的新操作验证后续用户新消息确认。

验证幂等、取消、旧版提交、权限拒绝、限流、错空间、响应丢失查询、重启、轮换及撤销。原始流通道与本机 file_id 通道分开标支持范围。自动化或 CLI 握手不能替代真实桌面任务；不宣称任意模型遵规。需人工模型任务/额度/配置改变时，在当时明确具体安排，旧验收授权不自动沿用到新任务。

### 13.4 备份、停用与降级

- 正式附件/图/配置按业务备份规则导出；私人文件授权、实际路径、暂存、票据、凭据及提案流程不进可移植 ZIP。
- 新私人文件授权默认不因复制业务库自动生效；迁移到不同空间身份必须失效。完整灾难恢复停服复制业务与相应私人状态，并重新核查授权源。
- 关闭新能力后网页业务数据仍可读；恢复新 ZIP 建立新空间身份和新授权，不保留源文件访问权。
- 新能力默认关闭、逐项开放；回滚代码前解决在途日志。遇未知日志版本保留证据并拒绝不安全写入，不删除 .agent 实现降级。
- 回退不保证撤销已对外披露的文件内容，也不自动撤销已完成业务迁移；恢复业务需通过明确恢复计划。
- 最终撤销临时身份、移除本次临时连接器、停止进程、关闭端口、清理任务目录，保留失败或审批拒绝事实，不碰真实库或其他连接器。

## 14. 文档、决策与等待执行入口

本次 AG-127 只写方案、台账和入口，不把未来字段写成当前 DATA_FORMAT/ARCHITECTURE 实现事实，不生成伪造验收结果。各实现项随代码同步架构、数据格式、AGENT_INTEGRATION、AGENT_USAGE、README、AGENTS 与维护。新增最终验收分册可命名 AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md，首次创建时只记录已发生事实。

本分册决策编号使用 AG-LOCAL-DEC，避免与旧分册历史编号冲突：

| 编号 | 决策 |
| --- | --- |
| AG-LOCAL-DEC-001 | 单机本地，旧凭据无新增能力，用户后续执行指令才启动实现 |
| AG-LOCAL-DEC-002 | 私人具体文件授权和不透明句柄，不开放任意路径或递归扫描 |
| AG-LOCAL-DEC-003 | 附件流式暂存；提案绑定摘要；三类业务索引分开 |
| AG-LOCAL-DEC-004 | 复用提案与领域规则，新增受控恢复处理器，保留旧摘要与日志 |
| AG-LOCAL-DEC-005 | 删除/项目创建/分类工作流强制 local_web，授权始终独立管理 |
| AG-LOCAL-DEC-006 | 多步骤日志按磁盘事实恢复，不声称多文件原子事务 |
| AG-LOCAL-DEC-007 | 配置迁移完整影响预演、授权失败收窄、未授权影响不隐藏提交 |
| AG-LOCAL-DEC-008 | 新能力每项独立验收提交，真实客户端与最终运维单独收口 |

待实施验证：Windows 文件身份与链接策略、源快照和文本续读边界、暂存最终配额、知识库附件兼容序列化、目录创建身份保留、图历史与自动保存冲突、分类/工作流迁移及授权恢复、客户端原始流支持。这些有对应工作项，不是已获得的结论。

**继续入口：AG-128完成后交监督审查；后续按依赖推进，不把 AG-127 文档完成当作历史开工授权。**


## 15. AG-128 定稿契约（已实现，验收见新分册）

- AG-LOCAL-DEC-009：configured 是已保存配置；implemented 只来自服务端静态处理器；effective 为实现、授权、scope、范围、策略及激活状态的交集。本项所有新增能力 implemented/effective 为空，旧四类型三操作保持。新增 grant 一律 dormant，首次启用必须管理员重新授权；未来代码上线不自动激活。
- AG-LOCAL-DEC-010：capability_grants={schema_version:1, grants:[{capability, operations, resources, minimum_confirmation_mode}]}，所有层严格字段/类型/枚举，最多64条 grant，每条最多64资源；重复项拒绝。资源仅 workspace、project(id)、item(kind,id)、document_category(name)、concept_map(id)、concept_map_category(name)、project_attachment_category(project_id,name)、workflow_template(id)。具体能力的允许资源与操作见 agent_security 静态表；无任意路径、通配和空资源。files.read 仅列为规划能力，本项拒绝配置（具体 file_id 留 AG-130）。分类/模板仅保存休眠意向，不永久预授；文档分类消失即从 grant 收窄，名称重用不复活，其他资源启用前重新授权。
- AG-LOCAL-DEC-011：根注册表2、client authorization3、management log3、transport2 分责。缺失 grants=无新增权限；edit省略保留、显式空清空。旧授权缺省 issue/document、不自动改写；新授权显式 kinds=[] 可保存结构合法休眠grant，旧范围可空。桥接不镜像 grants，16KiB不变。management_revision缺省0、管理变更递增，CAS仍用完整client_version摘要。
- AG-LOCAL-DEC-012：首次新格式操作先恢复全部旧未决；任何受阻日志禁止格式升级。写log3 prepared→原子根2格式门槛（保留旧clients）→transport配置→根2目标授权→completed清快照。根2保持，不随清空/失败/abandon降版；log3也保持。旧版根读取/日志恢复必须拒绝，逐阶段用旧版实际入口验证。遇外部修改保留现场；停服解决未决后才能由新版受控回退或恢复匹配备份，禁止直接用旧版读取/管理新授权或删日志降级。

新schema catalog标签仅来自旧授权范围内可见条目，分类仍按授权过滤；空项目仍可查其工作流，空可见数据标签为空。仅休眠客户端projects/search/catalog无元数据，正文/引用不泄露；capabilities与必要固定诊断可用。legacy catalog保留现有全局标签兼容行为。以上格式及恢复顺序须由实际测试验证，不是本节文字自行证明安全。

AG-128实际结果见[本机能力验收](AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)，其余规划不因授权基础完成自动成为已实现能力。


## 16. AG-129 执行契约（已实现，实际验收见分册）

- AG-LOCAL-DEC-013：新建proposal3/sha256-json-v3，旧1/2原分支和原摘要保留，修订旧提案不自动改摘要版本，旧策略收紧仍走原已登记升级。新3策略收紧保持3、递增版本、清预览并绑定新授权；其余授权变化须修订后新预览。
- AG-LOCAL-DEC-014：唯一静态处理器markdown@1，12种四类型×create/append/update；逻辑计划含目标归属/既有ID或提交时分配、候选摘要、history_snapshot/markdown_write、空source_bindings。具体manifest外层3、独立execution_schema_version=1，绑定实际ID/服务端目标路径、前后字节摘要、history_version、授权/依赖/预览/逻辑计划和具体计划摘要。两步复用原领域Prepared.apply边界，不提供动态方法、任意路径或测试处理器。
- AG-LOCAL-DEC-015：依赖仅归属存在和工作流模板ID、当前kind状态完整name/completed集合、候选已用标签名称存在性、固定引用ID集合及revision。状态集合是保守绑定：同一被使用状态集合成员增删即冲突，即使已选状态仍存在；换来明确检测模板集合变化，代价是这类变更需重预览。无关项目/说明/排序/分类、其他类型状态、标签颜色不绑定。无settings/data_dir/不可见资源清单。
- AG-LOCAL-DEC-016：prepared/applying标记不替代磁盘事实；history写后、日志记录前及target写后、记录前均可真实退出。正文仍before时重查授权完整版本、依赖及快照，history已完成不能跳过；正文after时核对历史/批准/回执绑定后只完成原回执。create applying目标缺失仍歧义拒绝，不创建新ID补写。receipt存在后不重放后来的修改/删除。
- AG-LOCAL-DEC-017：所有proposal/manifest/action版本、步骤、算法和跨字段身份先零写预检，再恢复/过期/修订/取消/清理；schema3必须交叉校验文件ID/proposal/client/kind/operation/归属、候选快照和回执，非秘密摘要不是语义认证。已完成回执匹配时仍验证JSON格式及绑定，不反复读取正文快照；在途快照逐字验证。过期保护只在确实过期且允许过期时扫描相关操作，不在expire=False全量预检中重复扫描目录。未知/损坏保留现场并拒写；abandon只接受识别且身份一致的计划，表示接受当前磁盘，不回滚或新建内容。

新3网页批准action3独立于execution manifest，绑定逻辑计划摘要、授权revision和依赖摘要；批准已记但manifest未存在时查询返回not_applied，不自动发起提交。旧批准action2/取消action1保留。未应用恢复需要对应私人授权，server现有runtime接入后第二阶段recover在关闭Agent时也运行；私人授权缺失保持阻塞，不猜测配置位置。AG-128的dormant继续拒激活，旧authorization1/2亦可使用现有Markdown新3提案，无需创建休眠grant。


## 17. AG-130 文件授权契约（已实现）

- AG-LOCAL-DEC-018：文件授权独立于休眠capability_grants，client authorization4保存active_file_ids，与私人file-grants双向交集并受read scope/用途/期限约束；其余dormant不激活。文件专用客户端显式空旧类型/范围，不补假授权。root registry3/log4拒旧9b6924d，transport2无文件列表；新平台只在已验证Windows固定NTFS宣称files.read implemented。
- AG-LOCAL-DEC-019：预览仅属性，不读取正文或hash，票据绑定管理session/workspace/client CAS、路径/句柄身份/大小/版本、用途/编码/期限/限额；confirm只接受票据与摘要、不得替换path。明确批准后才流式读取/hash。log4只存不透明快照ID/摘要，路径及必要秘密仅私人file-grants/management-snapshots；终结日志先持久化再删快照，删除失败可查询并重启回收，不删日志绕过。
- AG-LOCAL-DEC-020：CreateFileW逐层OPEN_REPARSE_POINT属性句柄、拒share write/delete，叶GetFileType/DOS最终路径/卷FS/卷序列+file index/BasicInfo ChangeTime核对；QueryDosDevice拒SUBST等映射，只接受Windows报告的固定本机NTFS卷，不声称证明物理硬件。拒UNC/ADS/设备/保留名/目录/重解析及全部多硬链接，敏感目录/名称默认拒绝，不扫描真实认证材料。不可证明的平台/FS fail closed，旧业务不受影响。
- AG-LOCAL-DEC-021：默认10MiB/1小时、显式至100MiB/24小时；同句柄64KiB流式hash时捕获目标片段，整digest/身份/大小/ChangeTime验证后返回，每段O(file size)而非全文入内存。每client2/全局4、块间5秒截止；同步本地OS读取仍有内核等待边界，不能宣称绝对5秒终止。attachment_source仅未来意向，binary仅信息，不获得文本或上传权。
- AG-LOCAL-DEC-022：UTF8/BOM、UTF16 BOM/显式LE/BE及显式ascii/gb18030/cp1252严格解码；offset/length为原始字节，默认/max65536、min8，offset0消费BOM但body不含BOM，完整字符尾部边界/UTF16对齐，携source_revision避免混版。拒非法起点、源变化、过期和撤销。
- AG-LOCAL-DEC-023：开始/结束短锁核验身份/空间epoch/授权，hash在所有业务/凭据/切换锁外。结束线性化发布许可后锁外限时网络发送；撤销先于许可阻止新响应，已获许可字节可迟到、无法收回。禁止锁内wfile.write，也不在换库后将旧请求重跑至新空间。

平台规范依据（仅官方，行为须实测）：[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)、[GetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle)、[GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)、[GetDriveTypeW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getdrivetypew)、[GetFileType](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfiletype)、[FILE_BASIC_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info)。

[QueryDosDeviceW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-querydosdevicew)用于检查当前DOS设备映射。快照首写未prepared的孤儿只持久abandoned再回收，不代替用户hash或发布；管理session、runtime版本与票据期限在长I/O后再次核查。批准预览披露受控display_name，Agent元信息只返回该名称，不返回父路径。实际测试见[本机能力验收](AI_AGENT_LOCAL_CAPABILITIES_ACCEPTANCE.md)。
