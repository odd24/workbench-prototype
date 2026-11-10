# AI Agent 本机能力扩展执行方案

日期：2026-11-09。规划工作项：AG-127；实现与交付工作项：AG-128～143。

主方案：[AI_AGENT_PLAN.md](AI_AGENT_PLAN.md)。前期扩展：[AI_AGENT_EXTENSION_PLAN.md](AI_AGENT_EXTENSION_PLAN.md)。实施事实与状态：[AI_AGENT_PROGRESS.md](AI_AGENT_PROGRESS.md)。执行规范：[AGENTS.md](../AGENTS.md)。

**当前执行状态（2026-11-10）：用户已明确“继续持续的推进方案”，按依赖逐项交接。实际范围和验证以台账及验收为准，此前暂停与 AG-127 仅文档记录保留为历史。**

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

以下为各阶段的预计接点。实施前确定最小变更，复用现有 CRUD 和 Repository 进程。AG-127 为本文档治理，各实施项状态以台账为准。

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

## 18. AG-131 暂存具体契约（已实现）

- AG-LOCAL-DEC-024：新增独立uploads.stage，不使用休眠attachments.write或130的attachment_source意向。管理同源会话预览/明确批准一client一个有效policy：具体owner_kind/id、stream开关、file_id/source_revision清单、大小/期限；替代旧policy，read scope及现有目标业务访问范围同时满足。绑定批准事务后的完整client_version，任何授权或凭据修改都保守失效，需重新批准；policy不扩大正式业务读取/写入。
- AG-LOCAL-DEC-025：复用root3/auth4/transport2及管理日志4，新增严格operation_family=upload_policy、before/after_policies快照及私人upload-policies.json schema1。旧eeeaf86在管理全量预检因未知family拒绝，不盲升全部格式。旧已知家族兼容；未知格式全部先预检后恢复，终结后才清快照。独立上传session schema1在私人目录，UUID由workspace/client/request稳定派生，input_digest拒同request不同输入。
- AG-LOCAL-DEC-026：session绑定client/policy/client_version、具体owner与相关版本、原始安全basename、来源file_id/revision或stream、声明size/sha、24小时期限。created/receiving/ready/consumed/expired/failed与提案分开；binding/consumer受控保护字段预留，131无Agent绑定/消费入口。ready必须真实私有blob对应size/hash，不能自报；正式文件/索引/正文和消费留132/133。
- AG-LOCAL-DEC-027：created预留声明大小，单文件100MiB/client500MiB/workspace1GiB，并发2/client4/global，磁盘额外保留16MiB；失败/过期未真正删除占用不释放预算。跨进程元数据短锁与单session OS锁分离，64KiB有界I/O；socket idle5秒/total60秒逐块收紧，file源仍有OS同步等待边界。file源限额/期限与policy取严，同遍复制/hash并核前后身份，不重新开源路径复制。
- AG-LOCAL-DEC-028：固定PUT octet-stream、认证与空间header、固定upload_id，无URL抓取/任意路径/base64。重复/缺失/非法Content-Length、TE、超限、query等拒绝，剩余body或错误关闭连接。loopback/Host/Origin校验，全部socket长I/O与源复制不持空间/业务/凭据锁，ready发布前短锁重验policy/目标/服务/空间，响应锁外发送。
- AG-LOCAL-DEC-029：receiving→part写入fsync→sealed真实size/hash→固定blob rename→ready；各断点从磁盘证据恢复。partial终结failed，完整sealed/blob需重读验证和当前权限才ready；第三方/未知文件或版本保留核查，不能当可用ready。安全清理只固定未绑定且非在途对象，不能删除未知/引用中/消费中对象；先持久终结、真正删除后才释放配额，已ready历史状态不等于当前可消费权限。

开工另发现Agent POST外层serialized_write锁覆盖130批准hash，先独立缺陷提交及真实POST并发回归；普通网页写入/换库原协调不变。实际检查、失败复验及边界见本机能力验收AG-131和台账。


补充实施边界：1000限制只计未removed会话，墓碑仍供幂等查询；磁盘可用量扣除未物化预留而非重复扣已落字节。短目录锁保护元数据原子替换、目录扫描、part→blob、句柄实际删除及removed发布，hash/流在锁外。在途取消返回409，停止发送或撤销策略后查询原会话，不保证立即中断OS读取。ready历史回执不表示当前可绑定；当前授权、目标及磁盘验证同时通过才返回available_for_binding。

私人路径守卫同时使用原生属性检查失效junction；缺失UUID叶只解析既有祖先并在创建/打开后复验，不能将一次瞬时解析差异当已证明的OS内部根因。清理通过已验证的同一DELETE句柄标记并关闭后确认不存在才释放预算。官方API依据：[GetFileAttributesW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileattributesw)、[SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)、[FILE_DISPOSITION_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_disposition_info)。实际junction成功/失效分支已验证；符号链接因权限不足跳过，不能宣称已覆盖原生符号链接创建。


## 19. AG-132 正式附件契约（已实现，实际验收见分册）

- AG-LOCAL-DEC-030：具体owner的一次本机完整预览，共同批准uploads.stage和attachments.write/create及最低确认方式。私人policy schema2新增attachment_write（能力、create列表、minimum_confirmation_mode）；旧schema1仍仅stage，转2时旧项显式null，不激活任何dormant。新管理attachment_policy家族与before/after_policies快照复用日志4/CAS，双方绑定同一个批准后的client_version。按共同批准→新暂存→正式提案操作；任何客户端变化或stage-only重批使旧许可失效，不迁移旧ready，无循环授权。旧read/propose/commit和实际目标访问范围仍必须满足，两确认策略取最严格。
- AG-LOCAL-DEC-031：attachment/create只处理既有project/issue/todo/info；外层target_id为owner，base_revision必填，content严格六字段owner_kind/owner_id/upload_id/display_name/category/insert_link。项目无正文，insert_link=true拒绝；分类仅已有值或空。AttachmentRepository领域准备/应用与旧网页共享metadata/链接助手，记录保留未知meta与info_fields，项目只改独立index。预览固定ASSET-<upload UUID hex>和唯一最终名/相对链接，同名占位409或修订新版本，提交时不静默换后缀；不建正式文件或业务目录作预览。完整候选与base合计最多256KiB，拒绝超限而非截断；原生最终路径最多240字符及敏感名称限制在准备时拒绝。
- AG-LOCAL-DEC-032：提案source_bindings为事实，session.binding为保护镜像；所有get/complete/cancel/维护/新prepare先预检引用。修改持非阻塞session OS锁，先持久proposal再镜像；缺口重建唯一匹配绑定，多引用/未知版本不释放。修订、取消、过期仅在没有执行manifest时解绑；copy意图也是执行日志。consumption.operation_id保持64hex，唯一映射sha256(proposalUUID-version)，与原operation_id、proposal/version/owner revision、upload_id、receipt交叉校验。
- AG-LOCAL-DEC-033：保留proposal3/sha256-json-v3和唯一ProposalStore状态机，新增静态attachment@1、execution_schema2及五阶段binary_copy/binary_publish/history_snapshot/metadata_write/upload_consume。确认和固定计划、元数据前后快照、实际接受时刻/唯一history ID先落manifest prepared，再放锁复制，绝不靠临时文件推定确认。预览中updated/created明确为提交时间占位，只有这两个服务端字段在接受确认时定稿，实际after摘要/metadata_time/receipt时间写具体计划；不回填草稿时间。旧Markdown处理器/摘要/日志仍走原分支，新旧混合先全格式预检，旧b7ce3fe拒绝新家族/处理器，不删日志降级。
- AG-LOCAL-DEC-034：64KiB复制至同卷.agent/operations/<proposal-version>/binary.part，长copy/hash/恢复hash不持空间、业务、凭据或目录配额锁。持session和operation OS锁；write_guard在接受意图后阻止普通写/孤儿清理，但读取、撤销和换库仍可进行。真实SHA/大小/part卷与文件身份持久证据后，以同一READ+DELETE句柄、目标父链属性句柄及FileRenameInfo不覆盖发布，无跨卷copy fallback。同名相同字节但不同身份仍拒绝。最终短锁重验空间/服务、权限/最低确认、owner/index、分类配置及推导集合、来源/固定名称；发布后记录历史与metadata，消费、回执逐步持久。metadata仍before需当前权限，已经after只核既有发布证据后补原消费/回执；receipt存在不重放后来改删。关闭Agent启动可恢复既有已确认事务，不能新建未确认事务。
- AG-LOCAL-DEC-035：执行中、未知或未完成消费继续保护；只有committed proposal、manifest、receipt、源binding/消费ID/大小/SHA全匹配才允许显式维护退休已消费源blob（不必等24h）。同一已核验DELETE句柄实际关闭删除后持久removed才释放预算；消失但未记账的退出可按回执证明与磁盘不存在完成记账。消费墓碑/原请求/正式回执保留，不能重建源或正式附件；外部篡改字节、未知绑定和未决记录保持保护，不能把所有consumed一概放开。
- AG-LOCAL-DEC-036：附件正文只允许逐字保留before快照的原始body片段（含CRLF/首尾空格），或公共助手保留原文后追加链接；base_content、base_revision、before快照与候选语义交叉验证。标签转义与相对URL编码共用；共享渲染支持转义文件名、受控相对附件链接并保留原Markdown URL标签的强调/行内code语义，序列化保留data-markdown-src。外部图片先兼容字面百分号路径，再在边界内单次URL解码。知识库仅回归原图片/编辑器能力，不建立133附件格式。

本项100MiB专项为有界内存与真实持久字节场景，不扩展独立performance_acceptance.py/visual_baseline.js，不冒称完整性能/视觉基线或AG-142真实模型矩阵。官方平台依据：[FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)、[SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)。不覆盖行为与同身份恢复以原生测试为准；外部文件系统剩余竞态、内核等待和确认许可后迟到响应边界继续保留。

## 20. AG-133实施决定（2026-11-09，已完成）

- AG-LOCAL-DEC-037：文档仅新增可选有序attachments，磁盘条目复用记录JSON字符串序列化和宽容字典读取；path相对原documents/*.md指向全局assets/images或assets/files，id/sha256由服务生成，category为原文档分类。无第二文档类型、附件分类索引或编辑器；旧无字段按空读取，未知meta与原始body保留，历史恢复含附件列表。
- AG-LOCAL-DEC-038：document共同许可由管理页面重新完整预览批准；旧stage/schema1或schema2的null许可、休眠grant与attachment_source意向均不扩权。继续attachment@1及现有五阶段/Prepared领域/消费回执，document access_target绑定原分类，分类改名/删除/迁移与授权变化在发布前拒绝旧提案，after只补原结果。
- AG-LOCAL-DEC-039：普通网页流不走Agent批准。浏览器稳定UUID先持久化，等待已有saving并先条件保存；上传时autosave暂停，继续输入持续进草稿，关闭/切文档等待上传结束。完成仅当前doc/空间/base匹配才合并附件/新revision/一次链接并条件保存，旧响应body从不覆盖当前输入；丢响应先查询原UUID，未接收的404与损坏/空初始化503区分，外部变化进入原冲突流程。使用既有共享renderer/host/session，补document-model透传renderLink。
- AG-LOCAL-DEC-040：普通网页日志.workbench-document-uploads只存操作证据，不是附件事实源；先NTFS/路径验证再收流，64KiB、100MiB、1GiB未释放预算、1000活跃操作、5秒空闲/60秒总截止及16MiB磁盘余量。prepared后短锁保护、锁外hash与同句柄无覆盖rename、历史/元数据重读；已接受的合法操作有全量发现/恢复/明确放弃入口，未知全量预检停止写入。completed先固定回执再精简快照，失败partial按创建身份/真实SHA证据同句柄删除后removed；终结墓碑不占活跃名额、不删除UUID绕过幂等。abandon不回滚已发布文件，含未知文件的初始化需人工核查，只有空初始化可明确放弃为墓碑。
- AG-LOCAL-DEC-041：孤儿候选只来自全局assets及项目assets，引用库存覆盖正式文档/记录/项目正文与meta、历史及回收站按原owner目录、在途Agent/web操作，任一共享引用保留；未知/损坏/链接对象使候选保守清空并返回脱敏警告。已证实旧实现漏正文/历史/回收站并在恶意索引下仍判孤儿，属于133必要正确性修复；不扫描全盘、执行文件或以索引取代MD。
- AG-LOCAL-DEC-042：知识ZIP保留平铺MD，受控真实引用文件按规范相对路径摘要+原名映射assets/...并去重，只改导出副本body及metadata。内部附件token转换为导出副本相对链接，裸.md仍单文件不附二进制；缺资源/越界/重解析/硬链接/尚不支持的本地HTML或定义式引用拒绝不完整ZIP。完整工作台ZIP含正式全局assets，排除私人web/Agent操作证据；迁移未决拒绝，终结日志按原相对布局保留幂等。

## 21. AG-134实施决定（2026-11-10，已完成）

- AG-LOCAL-DEC-043：revision只取同次原始字节SHA-256，传输字段不入JSON。HTTP已有图PATCH/历史恢复缺expected_revision有意409阻断旧缓存，提示刷新；Python省略兼容只在共享服务锁内线性化，不承诺无版本调用的外部CAS。未知未来version拒写/恢复，已支持旧版保持宽容，节点边上限与归一化语义不放宽。
- AG-LOCAL-DEC-044：领域Prepared固定before/after与唯一历史名，原字节历史→再查before→原子目标→重读；history/CMAP-ID/时间UUID.json无索引/新操作日志、不自动重放，所有历史保留。失败可能已有历史或目标，查询实际revision后处理；未知历史保留标警告、不自动删除。真实history/target退出及失败重读证明，保留外部FS竞态，不称多文件事务。
- AG-LOCAL-DEC-045：唯一画布控制器持base/dirty序号/保存Promise/冲突和原open世代。409暂停保存并保留输入/撤销；明确继续编辑、读取磁盘或确认覆盖最新磁盘，再CAS。撤销不恢复旧base。成功flush才接受离开并失效未决open，失败/取消保留当前图；迟到请求还复核等待期间输入和空间。刷新草稿尽力保存，失败可见；JSON/PNG仅导出画布。恢复期间暂停autosave但继续输入，不用恢复响应覆盖新的输入。
- AG-LOCAL-DEC-046：分类逐图、兼容_write、普通update/create和历史恢复复用同域Prepared；单图图库移动有列表CAS。分类配置与多图迁移中断仍属原有非事务边界，报错不宣称全部成功，不扩展AG-139。回收/ZIP接点保持，未开放Agent concept_map类型、工具或休眠许可，AG-135以后另行派发。


## 22. AG-135实施设计（2026-11-10，监督接受，已实施；以下设计过程保留）

1. **新鲜授权与兼容门槛**：拟root registry4 / client authorization5 / management log5，保留旧1～3/1～4/1～4读取，首次明确图授权管理批准才升新门槛，清空/撤销不降版。复用CredentialManager、锁、expected_version、私人前后快照/幂等及report/abandon；新concept_map授权操作家族。独立`concept_map_grants` schema1为实际批准内容，原capability_grants继续严格dormant，绝不复制configured为active。scope read/propose/commit、明确concept_map类型、read/write能力、具体资源与create/update操作及最低确认共同满足；旧客户端即使全项目/分类也无图能力。最低确认取请求/客户端/所有匹配写grant最严格。新版本保持其它文件/暂存/附件字段和旧行为，旧代码未知root/log/proposal/handler全量预检拒绝；真实9e43aa3验证零JSON变更。此格式提升是待讨论的明确选择，不伪称现有格式。

2. **范围和依赖**：具体project资源只覆盖关联该项目的图，独立category资源仅覆盖project_id=null的图，named map资源只针对现有稳定ID；空project不表示所有图。read/write分开；create只可项目或独立分类授权，named map不授予尚未存在的任意ID。update同时校验原图和完整候选，改变归属还需明确目的项目/独立分类写范围，不凭named map迁移到任意归属。只用现有project/category，不创建配置。授权变更绑定client_version，执行依赖绑定图base_revision、相关project存在/版本和分类原始配置及完整归一化集合，成员增减均冲突。分类改名/删除复用既有“先收窄授权再迁移业务”的CredentialManager hook，拟对图分类grant移除旧资源且不自动恢复/改成未分类；需重新明确授权，失败保持收窄。静态读取/错误/列表/引用不泄漏未授权图或项目正文。外部文件系统及字节版本ABA边界不伪称已消除。

3. **稳定身份，无额外ID状态机**：create提案原子落盘本身持久预留`target_id=CMAP-ID`（显式identity schema1，含proposal/workspace/client绑定），不另建预留目录/第二索引。共享Repository写锁+既有ID锁分配，取正式图、图历史、回收站、所有graph提案（含取消/过期/已清理）、执行manifest和回执的占用并集；网页create也使用同一占用提供器。首次proposal落盘前退出无已展示身份，落盘后按request_id/hash找回原proposal和ID；revision版本保持同ID，终结墓碑保留身份永不重用。读/取消/过期不创建正式JSON或目录/历史。标题同名沿用现有允许规则，ID区分；固定正式路径被占用一律409，不换名换ID或接管外部文件。现有ProposalStore终结清理保留target_id/identity；不靠内存预留。AG-134同域新增prepare_create并由普通create调用；Agent create要求完整至少一个节点，避免网页空输入默认根节点被当成隐式候选修改。

4. **完整候选与严格校验**：content拟仅`graph`对象，完整version2/title/project_id/category/focus_question/theme/viewport/nodes/edges；顶层id/created/updated/revision与任意路径均拒绝，ID由预留或target给定。在既有宽容normalize前逐层拒绝未知字段、错误类型/bool充数/NaN或Infinity、重复/非法节点边ID、自环/缺失引用、非法类型/箭头组合及所有现有数值/字符/颜色/数量上限。输入不得被静默修正/截断；颜色等纯等价规范化完整预览显示。稳定ID检查仅识别唯一、完整相同的非ID字段结构匹配所证明的纯重新编号；边先按已证明节点映射归一端点，不做NLP/模糊语义推断。重复相同节点或身份无法证明时不武断拒绝，明确服务不能证明任意语义身份。旧文件宽容读取/网页路径不移除；无法严格表达的旧图需先本机处理，不自动重编号。已有未知meta若领域保留必须完整列出，任何可能丢失的旧字段/归一化变化须显式警告和完整前后差异或拒绝。候选与base各拟最多256KiB、完整preview拟最多2MiB，超限413而不截断/声称完整；不放宽旧1MiB请求/8MiB响应或旧正文限制，capabilities分别明示。

5. **唯一引擎与恢复**：保留proposal3/sha256-json-v3，新增静态concept_map@1、外层manifest3内独立execution_schema3与history_snapshot/json_write两步。preview与commit同域prepare（不apply），候选固定ID及时间占位；受理确认时才生成实际created/updated并持久固定，只允许这些托管字段变化。计划/批准/依赖/managed_time/固定history版本、before.json/after.json摘要与原receipt绑定；server派生concept-maps/CMAP-ID.json及history受控路径，不接受执行指令或任意path。同一ProposalStore预检全部新旧证据后才任何过期/恢复/清理写，复用guard、report/abandon、两确认、幂等回执，无平行恢复进程。before需当前授权与依赖，after已发布且历史证据匹配只补原回执；第三方其它字节/缺历史/未知版本保留503，不分配新ID、不重放已完成后来的编辑/删除。create applying后目标消失不擅自重建；无manifest的初始化/快照残留不推定已确认。真实退出覆盖提案预留首次保存、批准、快照/manifest、历史、target replace、receipt/proposal终结与清理；不称两文件事务或文件作者身份认证。

6. **完整预览与画布复用**：拟扩展既有conceptMap工厂的只读模式及明确root范围/销毁监听器；同一几何/节点/边渲染能力，不再实现第二套图画布或另用PNG缩略图替代。只读实例独立交互状态、不注册编辑/保存/全局快捷键，不修改后台current/dirty/undo；平移缩放仅查看。既有编辑factory的全局选择器/监听器需限定自有root，避免预览节点误触编辑。管理modal提供可缩放全图、完整元数据/保留字段、全部节点文字/note/ID/布局/样式、全部边端点/文字/箭头/样式，及按稳定ID的增删改、全部文字和坐标/尺寸/视口差异与警告；当前规模不分页，不折叠或截断明细作为默认“完整”。MCP完整结果含同样候选/base/明细/差异/警告，全部纳入graph分支preview_payload摘要，普通Markdown摘要语义不变。local_web只有完整API/画布/明细同版本加载成功后才能申请批准，沿既有会话ticket/完整摘要/依赖/authorization绑定；改候选须新版本重预览。Agent自报不能替代local_web，两确认均不宣称现实身份认证。

7. **接口/深链与验收接点**：拟新增范围只读list/get graph工具（目录20→22，最终以实测目录为准），复用prepare/revise/preview/commit工具的concept_map create/update分支，不开放delete。明确graph只读结果与可编辑候选、保留metadata及revision，过大完整内容拒绝而非返回伪全文。web_path `/?item=concept_map&itemId=CMAP-ID`经严格ID和当前请求检查，先AG-134 flush/leave，再打开原画布；不绕过dirty冲突保护。真实浏览器两确认/完整大图明细/旧版本拒批/取消/丢响应/刷新查原回执/结果深链/后台画布无副作用/保存重开/undo-redo/JSON-PNG/浅深1440-390；新旧格式、管理私有快照与旧二进制拒绝、并发预留/网页创建、各写阶段真实退出、授权/分类/项目变化及MCP原始stdio均进入临时数据验收。此为设计，尚无新增已实现能力；不提前开展136。


2026-11-10监督设计收口：上述总体方案已接受，可实施135；136不开始。registry4/auth5/log5必要性是旧程序无法理解实际图授权及撤销恢复，普通旧客户端只读/状态不升级；须覆盖首个私有快照已落但root未升的窗口、所有其它管理family及withdraw/rotate/revoke/report-abandon/terminal cleanup不降版不丢字段。预留全部未知/损坏占用来源fail closed，所有显示过ID的墓碑永久保留且记录扫描/增长成本。project/category完整派生集合依赖是保守选择，无关成员增减也可能要求重预览，须在警告中明确。

字节预算明确为新增Agent路径：候选与base各256KiB按紧凑、ensure_ascii=False JSON数据的UTF-8计数（含全部图字段/保留元数据，排除传输revision）；原始base文件另设1MiB接收上限以拒绝异常格式膨胀，正式快照仍保存上限内原字节及原SHA，不能用重序列化代替revision。JSON请求envelope仍服从现有1MiB；完整preview实际JSON上限2MiB，并验证MCP双structured/text结果仍在8MiB预算内。超任何界限413，不影响网页原有图限制。只读量化盘点：标准500节点/1000边样本紧凑UTF-8为220400B，缩进JSON为347464B；两种字节层必须区分，不把缩进使合法常见图误判为256KiB数据上限。

readonly工厂/root/lifecycle公开契约调整登记在135内，不回写RF历史；优先共享最小几何/渲染原语，不能复制整套编辑器。避免DOM id重复，选择器/监听器/快捷键/blur/paste/unload/pagehide/rAF/save timer有明确实例归属和dispose；旧预览迟到不装配新提案，readonly不调用写API或污染草稿/undo/current。local_web可批准状态绑定同一proposal/version/digest的完整明细与画布载入，失败/取消/更版清空；ticket仅证明服务端完整预览数据和管理会话绑定，不证明DOM可信或人眼读过每条。未实现的能力仍不在capabilities中宣称。


2026-11-10监督兼容边界修订：首private snapshot→operation log→registry fence顺序保持，不增加全局阻塞标记。旧管理/恢复/客户端变更入口扫描到孤儿新快照时必须零JSON写拒绝；root4/log5或图proposal/manifest存在后，只对实际经过相应格式门槛的旧Agent授权/提案恢复写入口声明拒绝。首快照但root/log未升的窗口尚无新增图权限生效，旧dormant不激活；已经运行的旧HTTP业务可按旧有效授权继续，普通无凭据网页也不必经过registry，不能概称所有旧业务零写。真正授权发布/图提交前重查client_version和目标/依赖版本，窗口内合法旧修改造成CAS/依赖冲突而不静默覆盖。测试按每个真实退出点和入口分组，证明旧管理不覆盖新快照/授权且active grant发布前root fence已持久；保留混用版本/外部FS与非秘密摘要不能证明文件作者的边界。此前更宽的“旧代码零写”目标以本修订限定，不抹原讨论。

AG-LOCAL-DEC-047（2026-11-10，监督接受，135分配契约补充）：统一图分配器使用config/concept-map-ids.json的schema_version=1/high_water非负整数单调游标，仅作分配元数据，不是第二套提案预留或事务日志。真正领取身份在repository.write_lock→既有ID锁下，严格读取游标与formal/history/trash/全部proposal/manifest/receipt占用取max，先原子持久化新上界，再发布网页图或首个proposal。Agent身份/客户端/工作空间仍只由唯一proposal原子JSON绑定，重试先查原request不重新领取；纯prepare与只读list/get不初始化游标。失败/取消/过期/清空回收站不降上界，允许安全跳号。缺文件时只能从现存证据派生，无法区分首次升级与人为删除旧游标；升级前已永久移除且无证据ID不能追溯，人为删除或部分恢复分配元数据后不再保证无证据旧ID不复用。未知/损坏任一占用源或游标停止分配，不归零/跳过。完整ZIP自然包含此可移植配置文件，完整解压及copytree迁移保留；单项目/文档ZIP不承诺全库图编号。旧并行进程不理解游标，延续混用版本不能保证其分配的边界。不采用空history目录，不扩展136的Agent删除能力。

AG-LOCAL-DEC-048（2026-11-10，监督接受，135主画布贯通修复）：原主画布不只迁移旧v1，v2只要edge.label非空也自动拆边/新增linking_phrase并autosave；与135完整图候选及稳定ID冲突。自动迁移限定已支持version1及历史缺version约定，version2保留label和节点/边身份，不再因打开而改结构；未知未来版不得当旧版迁移或写回。复用同一共享几何/边/节点渲染，主图标签沿用已有标签编辑宿主，不另建画布。补完整Agent提交→深链打开→等待保存窗口字节不变→显式标签编辑保存重开身份和关系样式/箭头保留、旧v1迁移和原画布/readonly回归。此为有意修正旧v2自动迁移行为，不宣称该旧行为保留。

AG-135实施收口（2026-11-10）：22节及决策047/048范围已完成，最终433项Python/23项Node分批与隔离真实Codex旧流兼容验收通过，实际结果、首次失败/复验、兼容及风险见独立台账与验收。上文拟定/尚未实现等表述保留为当时设计事实，不代表当前能力状态。136～143未开始。

## 23. AG-136实施设计（2026-11-10，监督已定稿，已完成）

以下为已定稿设计，实际实现/验收见台账；拟定措辞保留设计阶段原意。只覆盖四Markdown类型及concept_map单条删除；137以后不开始。

1. **新鲜删除许可与格式门槛**：拟新增独立delete_grants（schema1、仅items.delete/delete/local_web），不读取休眠capability_grants为有效授权；资源沿用明确project/item(kind+id)/document_category/concept_map/concept_map_category，无通配。实际执行必须read/propose/commit、原类型/读取范围及新删除范围交集，图仍另需fresh graph read，删除批准不授予读取或增加kind。拟registry5/auth6/log6，transport2不变；auth6保留全部图/文件/休眠字段，并要求明确空或有效delete_grants。图/文件等所有家族和rotate/revoke/edit/withdraw/report-abandon保持新下界，首私人快照→日志→root顺序及旧入口拒新孤儿快照窗口按135限定，不概称旧普通业务全部零写。管理同源会话完整范围/资源版本预览、独立明确批准/撤销/收窄，复用CredentialManager/锁/持久幂等回执；不进入MCP。
2. **输入与完整影响计划**：复用prepare/revise/preview/commit，新增operation=delete；只接kind/target_id/base_revision/source_note等提案信封，不接content/path/body替换；明确传agent_attested拒绝，默认local_web。服务精确读取原文件UTF-8/原SHA/身份归属，保留未知业务元数据、不归一化后替换。展示目标完整正文/front matter/有序info_fields，图沿用原图+readonly全图/全部节点边字段；附件为完整元数据与受控资源存在/保留说明，不读取或删除二进制。缺失资源明确列出；非法/未知结构或无法完整呈现拒绝。固定保留30天与历史/共享附件保留/断链说明，不改其他正文。
3. **依赖/引用盘点**：不能直接把现有document backlinks当完整证据（只扫issue/todo/document，未覆盖info字段/图等）。拟严格扫描受控正式Markdown/图清单，绑定全部来源的ID/类型/原字节revision及集合，识别既有[[ID]]/body/attachment与可识别内部深链、info字段及图文字；匹配的影响来源完整读权与全文/结构预览均必需，否则拒绝，不泄露隐藏对象详情或给不完整影响。项目README/legacy idea/历史/回收站是否出现潜在引用、哪些仅保留规则而非活动断链，须在实现前与监督确定：无法证明完整的来源不可静默略过。全预览建议沿用2MiB实际响应上限，单原文件1MiB有界读，超限拒绝不截断；禁止用小摘要冒充完整影响。此保守全清单依赖可能因无关修改要求重新预览，需明确警告。
4. **领域PreparedDelete与原回收站**：拟新增同域纯PreparedDelete，records/documents/concept_maps各自定位/校验身份和归属后产生唯一受控相对源路径、before原字节和trash_kind。token从proposal UUID+version与既有record/document/concept-map前缀确定（绑定operation_id），预览即固定，无正式目录/移动/索引写。deleted_at在接受当前确认时定稿，计划/批准/manifest交叉绑定。manifest3/execution_schema4、静态trash_delete@1；before.md/json与source/trash/索引成员/排序证据固定在唯一ProposalStore操作目录，不另建执行或恢复引擎。
5. **移动/索引/缓存/排序阶段**：manifest先落，再持久move applying，再重验授权/完整依赖/源SHA/路径无重解析/目标不存在后同卷不覆盖rename；不得使用可退回copy+delete的shutil.move处理Agent计划。随后验证trash原字节/身份，按当前索引仅添加本token（不覆盖异物），处理cache，完成原回执。拟排序采用兼容原行为的显式保留：现有三类删除不删除项目README的*_record_order或document-sort.json中的ID；不改排序文件，预览说明保留旧位置以便恢复，记录相关配置/序列的前后不变证据，不凭Agent删除额外改项目元数据或清空分类。记录cache改为移动证实后失效，恢复始终再失效；不把内存cache当持久证据。此排序选择须监督确认。
6. **恢复判定**：prepared且move尚未applying、source=before/trash缺失/索引token缺失，重查当前授权依赖后才可继续；move applying后source仍在而trash缺失，无法区分尚未move与外部恢复，不自动再次删除，保留现场走report/abandon。trash存在且完整before/身份匹配，即使source后来重新出现，也只补原索引/cache/原回执，不再接触source；token索引成员缺失可仅补本项，已有必须与计划完全相同，异物拒绝。trash缺失/不符、source与trash未知组合、计划/历史/索引损坏先零写阻断；不从快照重建被删源或trash。完整committed证据与回执后，无论目标后续恢复/修改/再删/purge，旧提交只返回原结果。具体每个可允许状态及abandon收口必须测试，不称多文件事务。
7. **普通入口保护/ID/历史/附件**：沿用已有在途全局write_guard保守保护，不缩小为未经验证的局部锁；覆盖普通删除/项目删除/分类迁移/历史恢复、网页trash restore/purge/batch、保留期cleanup及孤儿清理，已确认且持久在途计划不能被绕过；读列表显式在途/受保护状态（最小UI变化）。Repository启动先ProposalStore全预检/恢复再cleanup，关闭Agent同样恢复；未知新格式旧程序不清理。全局阻断期间禁止孤儿清理，必要只读报告把删除before快照按原owner目录计引用；现有asset_references对record/concept-map回收kind仅保守保留，若调整只补正确识别，不借机放宽未知清理。历史不移动不删；Markdown receipt/manifest和既有trash保留ID占用，图继续共享单调游标/全占用源。完整ZIP当前明确排除.trash及.agent，不把它说成删除事务备份，不改变导出格式；停服完整目录迁移与匹配私有配置/日志保留边界另验。
8. **预览/回执/UI**：同一提案预览新增删除影响分支，危险操作明确文字；所有源全文、结构/图、附件、全部匹配影响与保留规则/稳定token/版本/步骤依据载入成功后才允许网页批准，关闭/切换/迟到/失败禁批沿用现有epoch/dispose。回执只受控token/身份/删除时间/原操作及回收站结果链接，无机器路径，当前是否已恢复单列查询事实，不改原回执。Agent无恢复/purge/清空/孤儿清理新工具；工具目录预计仍22，实际以验收为准。

待定稿重点：新许可版本与原家族保留；引用宇宙/读权和完整预览预算；排序保留不写；move applying后无trash不重删的保守恢复与abandon；普通入口全局保护与迁移/备份边界。定稿前不修改产品实现。

2026-11-10监督定稿：23节整体接受，可实施。补充作为本节准绳：四MD明确issue/todo/info/document；显式agent_attested拒绝，省略默认local_web。活动引用宇宙为全部受控正式records（含legacy idea目录）、documents、project README、concept_maps，用户文本既有字段及图title/focus/node text/note/edge label复用单一共享识别器，代码块命中可标潜在文本引用，不证明任意自然语言。README/idea命中无既有全文读取契约则通用拒绝；未匹配者仅内部集合/revision，不泄露ID/标题/数量/正文。历史/.trash不计活动断链，明确仍含旧引用且原样保留，不扫描无限历史；未知/超预算集合拒绝。每原文件1MiB/完整实际UTF8 JSON preview2MiB，默认30天保留可由本机提前purge，Agent不开放。保留排序序列、不写相关配置；引用全集变化代价警告。复用LocalFileHandle同句柄无覆盖rename，首期Agent删除仅Windows固定NTFS，implemented/effective及错误明确平台限制，不假设POSIX os.rename不覆盖。abandon接受盘态解除保护，不回滚/撤销删除。普通全局保护、关闭Agent先恢复后cleanup、旧恢复规则及备份迁移边界保持。

- AG-LOCAL-DEC-049：136复用唯一ProposalStore静态trash_delete@1/execution4与领域NTFS同句柄不覆盖移动；原索引快照/摘要先落且保守CAS，活动全集/排序绑定，不改变排序序列。移动证据不明不重删恢复源，原trash身份/字节证明后仅补本索引和旧回执；abandon接受盘态、残留仍保护。只授权单条local_web删除，不提前开放137以后。

历史停止边界（2026-11-10，AG-136交付阶段）：仅继续AG-136必要验证、文档和独立提交收口；完成交审后暂停所有后续任务，等待用户新指令，不自动开始AG-137。此前持续执行授权保留为历史。


## 24. AG-137 实施设计（2026-11-10，已定稿）

监督已批准以下设计及本节末尾的收口条件；能力开放及验收事实以台账为准。

- 许可：项目创建使用独立新鲜 `project_create_grant`，只允许 `projects.create/create/local_web`；与既有 read/propose/commit 交集，不追加业务 kind、项目访问范围或其他能力。旧休眠字段不激活。候选格式为 registry6/auth7/管理日志7，transport2 保持；管理操作沿用快照、意图、格式围栏和持久回执，不降级旧家族。项目提案读权与项目业务读权分别判定。
- 候选：复用项目仓储和 Markdown 轻量格式；只接收 name/description/status/color/workflow_template，严格验证字段类型、单行名称、状态、安全颜色、已存在模板与 UTF-8。展示实际归一化结果及服务时间占位；最终 README 仅在批准受理时固定服务时间。服务端分配 slug 身份；普通网页和 Agent 共享占用约束，检查实际目录、回收站及私人提案/执行/回执保留身份，大小写冲突按磁盘处理，未知证据停止分配。既有悬空显式项目授权也须纳入防复用设计；已有通配本身的语义保持。更改名称或重试不静默领取新身份。
- 排序：绑定实际排序字节、相关项目集合与选定模板依赖。自定义模式按原排序规则追加新项目，既有项目相对顺序不变；本机完整显示排序变更，Agent 侧不泄露不在读取范围的项目身份。非自定义模式不修改排序文件，预览展示原规则下新项目影响。排序最终语义和非授权范围展示边界待审查。
- 发布：候选为同一 ProposalStore、proposal3/manifest3、静态 project_create@1/execution5。先有持久批准、已核准 README/排序快照和 manifest，才在私人同卷目录组装；以真实物理身份和完整树证据绑定独占暂存，使用经验证的 Windows 固定 NTFS 同目录句柄无覆盖发布，无复制回退。目录不能由预览创建，不接管陌生残留或占用项；路径、子目录及类型固定。发布前复查权限、模板、占用及排序版本。目录证据成立后只完成既定排序与原回执；不重新分配项目、不用新当前状态重算排序。证据不明停止，放弃不回滚或清理第三方；进入发布阶段但目录尚未证明的恢复策略待定稿。
- 独立授权：创建时网页明确勾选后，在项目成功后另行打开固定客户端/新项目的本机权限预览，另行批准后通过 CredentialManager 执行一个 CAS 幂等操作，核原项目仍在及身份匹配。只追加一个项目 ID，既有 scopes/kinds 不变；必须完整说明已具备的读取/提案/提交会怎样扩展到这个项目。已含 ID 或通配无需再次授权。授权结果、失败、重试和恢复与项目创建回执分开；业务候选拒绝任何授权字段。
- 验收重点：检查预览、关闭和取消零正式目录；既有配置/未知格式、残留及过期身份、同名并发、同字节异物、文件与目录重解析、排序 CAS、真实退出阶段及重启查询；独立授权 CAS、撤销和丢响应、项目成功授权失败不重建、读取未隐式扩大；旧编辑器/项目列表/排序、完整真实浏览器和隔离接入回归。阶段测试应核磁盘原字节和重实例结果。

定稿收口：同一提案保持已显示 ID，身份冲突另建提案和完整预览，原身份继续保留。custom 使用现有 canonicalizer：先依原规则补齐旧未列项并清掉重复/失效 ID，再把新项目置末；本机展示完整前后清单，Agent 只展示不披露他项的模式、规则、位置与计划摘要。进入 publish applying 后仅当正式目标原目录身份和完整树匹配才续办排序和回执；否则不重发。项目回执始终可重新进入独立授权预览，之前的网页勾选仅是引导。隔离 NTFS 探针已验证目录句柄无覆盖 rename：已占用目录不替换，成功移动保持物理身份和子树；这只验证原语，不是完整持久化验收。

- AG-LOCAL-DEC-050：固定项目身份由私人提案保留，普通创建共用占用识别；原目录身份、完整树与原排序证据约束阶段发布。项目创建与精确范围授权分为两个批准及回执，权限以当前版本 CAS，恢复不领养陌生目录、不重新创建。AG-137 实测已完成，下一项须监督交接。

## 25. AG-138 实施设计（2026-11-10，监督已定稿）

- AG-LOCAL-DEC-051。仅固定项目整目录移入回收站。沿用现有项目读取，同时每个实际 issue/todo/info 必须有独立读、删权。历史 idea 和无法完整识别或授权的来源使候选失败。新鲜 `project_delete_grants` schema1 只覆盖具体项目的 `projects.delete/delete/local_web`，逐一绑定本机管理员选择的独立附件 ID 与证据。registry7/auth8/管理日志8，transport2。旧授权家族和操作阶段的格式下界须保留，旧休眠项不得生效。
- `list_projects` 只为现有可见项目补充原 README `revision`。删除输入为 `kind=project`、`operation=delete`、`target_id`、`base_revision` 和可选来源说明。完整预览同时绑定目标目录、每个子记录、项目内附件、实际外部关联与排序/回收索引。项目外的关联图保留原 project_id、文件和历史，有全文读权才展示完整只读图。其他活动来源只在匹配后展示并检查全文读权。若外部活动来源仍引用会被移动的附件，整案拒绝。全局共享字节、历史和原排序不改写。
- 固定 NTFS 上全量树证据覆盖根与每个成员的物理身份、相对名、类型和每个原始文件的字节数与 SHA-256。未知成员、孤儿二进制、多硬链接、重解析、额外数据流、目录别名拒绝。二进制流式哈希，不入预览。完整树最多 4096 成员和 64MiB，单文本最多 1MiB，活动来源沿用 4096/32MiB，完整实际 UTF-8 JSON 预览最多 2MiB。数据流枚举参照 [FindFirstStreamW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-findfirststreamw) 与 [FindNextStreamW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-findnextstreamw)。
- 唯一 ProposalStore 新增 `project_trash@1`/execution6。正式执行先保存原 README、树、原索引、排序及操作证据，持久记录 applying 后以同一 NTFS 目录句柄执行不覆盖 rename。隔离探针确认目录句柄不能冻结子目录命名空间。移动前和移动后均核对完整树，最终检查后出现外部变化时可能已移动，证据不足则保留现场供核查。没有自动重移、复制回退或自动回滚。已在原 trash 路径证明原物理身份及完整树，才可补原索引、缓存和回执。已提交重放只返回原回执。
- 新项目级联回收项使用 `delete_schema_version=2`，保留项目与全部子记录 ID 占用。普通本机恢复验证完整可移植树和已提交证据，仍用原项目 ID，碰撞返回 409。同一完整停机副本的已提交树可按便携内容证据核验，未决副本不能代替原物理身份恢复。普通恢复、永久删除、自动清理、孤儿清理均受在途保护。ZIP 不含私人事务与回收站。本机管理预览、独立批准、回执和受控回收深链沿用现有界面与工具入口。
