# 数据格式

## Agent 本机启动偏好（AG-107）

私人凭据根目录下的 `<workspace_id>/runtime.json` 保存 `schema_version: 1`、`workspace_id` 与布尔 `startup_enabled`。它不是业务数据，不进入可移植 ZIP 或 Git。缺失默认关闭；损坏或未知版本保留原文件，禁止自动启用并在管理状态返回提示。读取未初始化空间不创建身份。`--enable-agent`/`--disable-agent` 只覆盖本次运行，不写偏好；自定义 `--agent-config-dir` 对偏好和凭据使用同一根目录。

## Agent 凭据管理操作（AG-108）

同一私人目录下 `management-operations/<sha256(request_id)>.json` 保存 schema_version=1、workspace_id、operation_id、request_id、input_digest、client_id、state 和脱敏 result。prepared/recovery_required 阶段另有 before/after 的客户端与配置快照，包含敏感凭据，仅保存在私人目录。完成或放弃后原子替换为不含快照的精简回执，长期保留幂等映射；未决快照不自动删除。这与业务 `.agent/operations` 是两套不同职责的日志。

配置先写、注册表后写；未决客户端暂停鉴权，日志 completed 后使用新凭据。恢复只接受 before/after 状态，不覆盖第三方内容。注册表保持 schema_version=1，客户端新增可选 management_revision，旧客户端缺省为 0；API 版本摘要包含客户端全部持久字段，不返回 token_hash。私人日志和配置不进入业务 ZIP。

管理会话（1 小时）、运行设置请求结果（本次服务最多 1000 条）、诊断任务（最近 50 条）、普通请求/自检观察时间仅在服务内存中，不写入业务数据或 localStorage。诊断 operation_id 是本次服务 UUID；它与管理凭据日志的 SHA-256 operation_id、业务提案 ID 分属不同查询入口。重启后诊断需重新运行；不得把暂无内存观察解释成没有历史提交。

## Codex 登记与恢复（AG-113）

私人工作空间目录 `codex-registrations/<sha256(request_id)>/` 与凭据管理日志分开：`receipt.json` 为 schema_version=1，包含 workspace/client/request、目标、输入摘要、前后文件摘要、before_exists、登记名和 state；`before.toml` 为原配置原始字节（原文件不存在则无此文件），`after.toml` 为候选配置。快照可能包含其他 Codex 设置和秘密，长期保留用于回滚核查，不进入 Git、静态资源或业务 ZIP。prepared 查询转为 completed / not_applied / recovery_required，查询不写目标 Codex 配置；未知 schema/目标不符拒绝查询，保留证据。

目标 CODEX_HOME 只来自服务环境，缺省当前用户 `.codex`；登记只替换其中 `config.toml`，其他配置语义保留，不迁移业务格式。目标目录额外 `.workbench-service.lock` 仅协调本功能跨进程写入，存在不代表仍被占用。新目录按当前用户私有权限创建；现有目录不更改 ACL。sessionStorage 的 `workbench.agentRegistration.pending.<workspace_id>` 仅保存未决 request_id/client_id，结果查询后移除。

## 目录

```text
workbench-data/
├─ config/
│  ├─ settings.json
│  ├─ status-templates.json
│  ├─ workflow-templates.json
│  ├─ labels.json
│  ├─ project-sort.json
│  ├─ document-sort.json
│  ├─ document-categories.json
│  └─ concept-map-categories.json
├─ projects/<project-id>/
│  ├─ README.md
│  ├─ issues/*.md
│  ├─ todos/*.md
│  ├─ ideas/*.md
│  ├─ infos/*.md
│  └─ assets/{images,files,library}/
├─ documents/*.md
├─ concept-maps/CMAP-*.json
├─ ideas/*.md
├─ assets/{images,files}/
├─ history/<record-id>/*.md
├─ history/CMAP-ID/*.json
└─ .trash/index.json
```

项目附件目录还可包含 `index.json` 和 `categories.json`。`ideas/` 和项目内 `ideas/` 只为旧数据兼容；当前 UI 和普通创建 API 不再产生新想法。

## Markdown

项目、记录和知识库文档使用 UTF-8 Markdown 与轻量 front matter。解析器只支持项目已有的标量、列表和历史字典兼容语义，不是完整 YAML。

稳定 ID 是引用与文件身份，标题变化不得改变 ID。常见前置字段包括 `id`、`type`、`title`、`created`、`updated`、`tags`；项目记录还可能包含 `project_id`、`status`、`priority`、`due`、`completed`、`attachments` 和 `info_fields`，知识库文档包含 `category`。字段应由仓储序列化器生成，不建议手工批量改写。

附件元数据保存在记录 front matter 或项目附件 `index.json` 中，路径相对于所属记录/项目。应用会在读取和删除时重新验证路径必须留在对应附件根目录。

外部编辑器写入正文的相对图片路径（如 `./${img}/图片.png`）也可直接显示，无需登记附件。`GET /api/markdown-images/<记录或文档ID>?path=<相对路径>` 按 Markdown 文件所在目录解析，只读取图片；记录限定在所属项目目录（历史全局记录限定在 `ideas/` 和 `assets/`），知识库限定在 `documents/` 和全局 `assets/`。缺失图片返回 404，越界、绝对路径和非图片返回 400。保存时保留正文中的原始相对路径，不迁移文件或改写附件索引。

## JSON

- `config/*.json`：工作流、标签、分类和排序。状态/标签删除与重命名必须经过仓储迁移使用方。
- `concept-maps/CMAP-*.json`：版本、稳定节点/边 ID、节点类型、样式、箭头和视口；最多 500 个节点和 1000 条边。
- `.trash/index.json`：回收站令牌、原路径、回收路径和删除时间；恢复和永久删除都会重新验证路径。
- 项目附件索引与记录附件元数据是两套索引，不能混用。

所有覆盖式 Markdown/JSON 写入使用原子替换。流式附件只写新的唯一文件；上传中断会删除半成品。

## 历史、删除和兼容

记录和知识库文档更新前的版本写入 `history/<record-id>/`。项目、记录、文档和概念图删除默认移动到 `.trash`，只有明确永久删除才不可恢复。

旧文件采用兼容读取，不要求批量原地迁移。读取异常旧项时应跳过或降级，而不是清空整个配置。任何格式变更都必须增加旧格式与写入后重读测试。

## 本机设置与可移植备份

`config/settings.json` 保存当前绝对数据目录，只供本机运行使用；仓库根目录的 `.workbench-location.json`、`.workbench-export.json` 和 `.workbench-editor.json` 也属于本机配置。这些文件不得提交，也不进入可移植 ZIP。

完整 ZIP 包含业务 Markdown、概念图、可移植配置、附件和历史，但排除 `.trash`、符号链接及本机路径设置。项目 ZIP 只包含该项目目录。当前没有 ZIP 一键导入；恢复完整备份时解压到新目录并以 `--data-dir` 打开。

## 内容版本与历史 API

读取记录/文档返回 `revision`（磁盘字节 SHA-256），保存和历史恢复可传 `expected_revision`；旧 `file_mtime` 保留。版本字段只存在于 API，不写入 front matter。条件失败返回 409，不写正文和历史。

记录 `/api/records/<ID>/history` 与文档 `/api/documents/<ID>/history` 提供历史列表；后接 `/<version>` 可读取完整快照，`POST /api/{records|documents}/<ID>/restore` 接受 version 和 expected_revision。恢复本身会保存当前内容的历史。历史保留最近 30 份，新版本名为时间戳加唯一后缀，旧时间戳版本继续可读。

数据目录根的 `.workbench-service.lock` 是操作系统持有的运行锁，不属于业务数据、导出或迁移内容；文件存在不代表服务仍运行，锁随进程结束释放。

## Agent 工作空间身份（AG-102）

启用 Agent 或创建客户端时按需生成 .agent/workspace.json，包含 schema_version=1 与随机 workspace_id；旧库无该目录仍可正常使用。未知版本拒绝启用。凭据在本机外部用户配置目录，业务目录只存身份；.agent 不进入可移植 ZIP。迁移整个目录保留身份，切换已有目录重新校验身份。

## Agent 提案和提交日志（AG-103）

.agent/proposals/<UUID>.json 保存 schema_version=1、workspace/client 身份、版本、候选内容、基础版本、预览摘要和状态；与编辑器 localStorage 草稿完全分离。正常状态为 draft/previewed/committing/committed，另有 conflicted/cancelled/expired/recovery_required。

.agent/operations/<proposal-id>-<version>/ 保存 manifest.json 和前后 Markdown 快照。日志只使用库内相对目标路径，状态为 prepared/applying/committed/abandoned；.agent/receipts/<proposal-id>.json 保留正式 ID、版本、提交摘要和位置。历史快照版本写入日志，使更新恢复不会重复消耗历史保留数。精简回执/已记录操作参与新 ID 分配，防止旧操作重试引用已复用的 ID。

所有新增 JSON 使用原子替换；进程中断后依次比较回执和磁盘摘要恢复，不能简单把多文件原子写称为单一事务。第三方内容和不确定删除不自动覆盖。提案清理只删除已终结内容及对应安全快照，幂等映射仍保留；在途数据不清理。完整 ZIP 不包含这些流程状态，文件级灾难恢复需停止服务后完整复制，降级前须处理在途日志。

正式条目链接当前使用 `/?item=issue|document|todo|info&itemId=<稳定ID>`，不包含正文、令牌或磁盘路径。回执保存相对 web_path；web_url 在 HTTP 返回时根据当前可信本机地址生成。旧回执缺少该字段时兼容展示链接，不重写其提交内容。

### AG-116 私人类型授权与流程格式

clients.json 外层 schema_version=1 保持；新授权条目增加 authorization_schema_version=2 和显式 kinds（issue/document/todo/info 非空白名单）。缺失 kinds 按 issue/document 读取。客户端私人配置与新凭据管理日志 schema_version=2，兼容读取 1；配置内 kinds 只是镜像，权限以服务端授权为准。轮换不扩权，旧编辑请求省略 kinds 时保留原值。

AG-116阶段的新提案/业务事务 schema_version=2；提案含 digest_algorithm=sha256-json-v2、confirmation_mode=agent_attested、approval=null，摘要覆盖规范内容、类型、来源、警告和确认策略；事务关联相同摘要与策略。schema=1 按旧预览载荷和摘要计算，旧提案不自动升级。未知版本拒绝写入、清理和 abandon，保留原证据。业务 Markdown/历史无迁移。AG-116 阶段仅开放 agent_attested，当前 local_web 按下文 AG-120 契约开放。

### AG-117 todo 字段与兼容

Agent todo create 接受 title/project_id/body/tags/status/priority/due；update 不迁移项目；append 仅 body。due 新值必须是有效 YYYY-MM-DD 或 null，不做时区转换；省略保留原值，更新时不改变的旧日期字符串继续保留。completed/时间/ID 由服务端产生。业务 Markdown 格式不变，未开放元数据、附件和 links 由原仓储保留。

历史 issue↔todo 转换保留原 ID；新建 todo 必须 TODO 编号，已有 ISSUE 编号的 todo 更新日志可恢复。新 todo 链接强制 TODO 前缀；旧转换记录回执 web_path/web_url 为 null，应从项目页打开，不伪造不匹配链接。旧 issue 链接兼容范围不收窄。

### AG-118 info 字段限额与无损边界

Agent info create 接受 title/project_id/body/tags/info_fields；update 不迁移项目；append 仅 body。拒绝 status/priority/due/completed/info_color。字段只接受必需 name/value 和可选 note 文本，不含空字符，名称非空且不含控制字符。最多200项，名称200字符，value/note各64KiB UTF-8，正文与全部字段值合计256KiB UTF-8，请求1MiB。新请求严格校验，不依赖宽容解析丢弃未知键。

共享字段归一化上限从100项/名称120字符扩至200/200，value/note不再 strip，前端收集器同步保留首尾空格；不改轻量 front matter 格式，不批量改写旧文件。完整 Agent 读取旧字段不截断；超限旧文件的更新须缩小到可完整预览范围，不能悄悄丢尾部字段。未修改的颜色、links、附件及原仓储元数据保持。字段顺序变化通过完整列表 before/after 表达。

### AG-119 本机提案取消日志

.agent/proposal-actions/<sha256(request_id)>.json schema=1，记录 workspace/request/proposal/version、operation=cancel、input_digest、created_at、prepared/completed 与精简 result。先日志再取消，响应丢失或中断重试相同输入得到同一结果；同 request_id 不同输入409，未知版本保留证据并拒绝覆盖。日志不进入业务 ZIP、搜索或静态资源，不能删除绕过。

### AG-120 确认策略和批准日志

私人授权/配置增加 minimum_confirmation_mode=agent_attested|local_web，旧记录缺省前者；编辑省略保留原策略，轮换/分类同步不改变。提案schema2记录有效策略；旧schema1升级策略时递增版本并使用新摘要，不静默改旧已预览摘要。

proposal-actions批准日志schema2含operation=approve、workspace/proposal/version/request、输入摘要、approved/completed/not_applied、business_operation_id和approval记录。approval含mode/version/preview_digest/approved_at/operation_id/input_digest，不包含票据或会话秘密；正式回执关联相同approval。票据只在进程与页面内存，10分钟、重启/会话/授权变更失效。

批准日志存在但无事务manifest时查询标not_applied，不自动提交；manifest完整且有匹配批准才恢复。prepared阶段原授权撤销或收窄则停止，applying/已落盘按before/after/第三方判定核查，删除后不重建。恢复保留未知/损坏证据。sessionStorage仅保存原request/proposal编号供结果查询，不存票据。


### AG-128 休眠能力授权（历史阶段，兼容读取）

AG-116 的根1/授权2/管理日志2是历史格式，仍兼容读取，不因读取或列出旧客户端而改写。首次显式保存 capability_grants 才采用新授权：clients.json 根 schema_version=2；客户端 authorization_schema_version=3、capability_grants={schema_version:1,grants:[{capability,operations,resources,minimum_confirmation_mode}]}、capability_grant_state=dormant。详细结构、64项/64资源上限与类型白名单位于 agent_security；files.read 暂不接受配置。拒绝未知字段/版本、通配、任意路径和空资源。服务端状态不接受管理请求自报激活。

缺失 grants 等于无新能力；编辑省略保留、显式空清空。旧授权 kinds 缺省 issue/document且显式列表非空；授权3允许显式kinds=[]，新建独立客户端至少一条结构合法的休眠grant；既有授权3可清空成为拒绝全部业务的客户端。管理revision旧缺省0、每次操作递增，完整client_version摘要仍作CAS。transport配置保持schema2，不复制grants，16KiB上限不变。

新管理日志schema3含registry_schema=2，复用before/after客户端与配置快照。首次升级先恢复旧prepared，旧recovery_required阻止升级；恢复先预检全部日志格式，新日志与旧未决混合拒绝。持久顺序prepared3→原子根2格式门槛（原clients不变）→config→根2目标授权→completed。日志在根升级前阻止旧版鉴权/管理恢复；根2阻止旧clients读取。各单文件原子写不代表多文件事务；故障/abandon/清空grants不回退根2或日志3。completed/abandoned删除秘密快照，保留精简幂等回执。旧日志/旧摘要继续按原版本读取恢复，不静默重算。

capability_grant_state=dormant持久保存；当前实现验证该状态，篡改成active拒绝鉴权。所有新增能力implemented/effective为空，capabilities.capability_authorization.activation=requires_reauthorization说明未来开启要求；后续处理器必须保留此门槛，仅实现上线不能激活旧授权。分类/模板名称只有休眠意向；文档分类变更移除对应grant资源且重命名不恢复grant，名称复用不复活；其他对象首次启用必须重新绑定可验证身份并由管理员授权，属于后续能力工作项。


### AG-129 proposal3与执行日志

当前新建提案schema_version=3、digest_algorithm=sha256-json-v3；旧1/2读取/预览摘要/历史恢复保持，不静默迁移已预览值。新字段authorization_revision={management_revision,client_version}、dependencies={schema_version:1,owner,statuses,tags,references}、execution_plan与plan_digest进入完整预览摘要。逻辑计划包含markdown@1、kind/operation、归属/既有target_id、候选摘要及两个静态步骤，source_bindings当前固定空；新ID/时间仍提交时服务端分配。grants休眠规则独立，现有业务不要求authorization_schema3。

具体operations/<proposal>-<version>/manifest.json外层schema3，execution_schema_version=1；含operation/access_target/client、授权/依赖、具体execution_plan及execution_plan_digest、step_states。具体计划将逻辑摘要绑定item_id/relative_path/before_digest/after_digest/history_version，receipt增加逻辑及具体计划摘要。before.md/after.md仍为受控快照，history_snapshot与markdown_write仍复用领域Prepared方法，进度日志不能代替实际字节证明。合法进度pending/pending→completed/applying→completed/completed；历史步骤对新建无旧快照副作用。

批准action3含proposal_schema_version=3及plan_digest，approval还绑定authorization_revision/dependencies_digest；批准记录先于manifest，响应丢失查同请求，未形成manifest则not_applied。旧action2批准/action1取消不改。

恢复/清理先预检全部版本和身份再执行，未知格式不修改其他已知日志。未发布正文时重查授权/依赖，即使历史已落；正文after只补原回执，后续权限变化不阻止完成已应用事实。create applying目标不存在不能猜测从未写过，进入核查。正常关闭接入仍可用正确私人授权恢复；缺失授权不绕过。已完成回执持续保留，30天内容清理不清在途快照，也不移除幂等证据。

### AG-130 具体文件授权

显式文件授权采用clients.json根3、authorization_schema_version=4与active_file_ids（最多100个UUID）；原kinds/范围不扩权，休眠capability_grants保持dormant。文件专用客户端显式kinds=[]、project_ids=[]、categories=[]及read scope。transport仍为2，不复制文件列表或源路径。旧根1/2和授权1/2/3兼容读取，首次批准或文件专用创建才设新门槛，撤销/abandon不降版。

私人file-grants.json为schema1/workspace_id/files映射。每项含file_id/client_id、最终path、受控basename display_name、句柄identity（volume/index/size/created/written/changed）、sha256、source_revision、encoding/bom_bytes、purposes、expires_at、max_bytes、status/version。source_revision绑定identity和内容哈希。只有客户端active_file_ids与此表的active、同client、未过期项交集生效；text_read允许文本，attachment_source仅意向，不提供上传或文本权限。Agent只见display_name及无路径元信息；路径只在本机预览、私人表和必要私人快照。

管理日志4包含registry_schema=3、operation_family=credential|file、固定私人快照ID/摘要及精简回执；不含源路径、正文、token或token_hash。management-snapshots/<operation sha256>.json为schema1，含workspace/operation/client、intent与before_/after_ values；credential为client/config，file为client/files。目录继承已收窄的私人ACL，固定ID派生且拒链接，恢复验证摘要/格式。持久顺序私人快照→prepared4→根3门槛→file ledger或transport config→client registry→completed→删除私人快照。prepared阻断该client；恢复只使用批准后的快照，不打开源文件。所有日志/私人快照/混合旧未决先预检，未知或损坏保留现场拒写。

快照先写、prepared尚未写即退出时，没有发布任何授权；重启预检后为该intent持久化abandoned（orphaned_before_prepare），再回收快照。completed/abandoned落盘后清理失败标记snapshot_cleanup_pending，可查询原operation并在恢复时重试。终结记录始终先于删除，不删日志绕过。根3下普通凭据操作也使用日志4外置私人快照。

批准预览仅元数据，10分钟、同管理会话/进程/空间/客户端CAS绑定；confirm只收票据/摘要及approved=true，不接替换path。批准后有界流式hash，不缓存全文；长hash后再次校验会话/票据期限/CAS才发布授权。响应丢失查原request，不能换ID重新授权。读取需source_revision，offset/length为原始字节，8～65536；返回end_offset/next_offset保证编码边界，BOM仅首段移除。每段同遍捕获并重算完整文件hash与前后句柄版本，源变更拒绝，不返回混版。

### AG-131 私人暂存策略与会话

root3/authorization4/transport2保留，管理日志4新增严格operation_family=upload_policy和before/after_policies私人快照；旧eeeaf86遇未知家族先拒绝管理/鉴权，不写其他已知日志。私人upload-policies.json为schema1/workspace_id/policies映射，项含policy_id/client_id、批准事务后的client_version、owner_kind/id、stream、files（file_id/source_revision）、max_bytes/expires_at/enabled。每client新批准禁用旧policy；read scope、当前业务目标访问范围及有效policy交集，不能扩权正式业务。任何client编辑/轮换均使旧policy失效。旧attachments.write休眠及attachment_source意向不激活；file模式还需新policy逐文件再批准，且旧具体grant仍有效。

私人uploads/<UUID>/session.json为schema1，UUID=uuid5(workspace, client_id+":"+request_id)，input_digest绑定完整创建输入，相同request不同输入409。固定part.bin/blob.bin，不接受路径。字段含workspace/client/client_version/policy、owner（kind/id/title/revision）、filename、source（stream或file_id/source_revision）、declared_bytes/sha256、created_at/expires_at、state、evidence、sealed、binding/consumption、removed/error。filename仅安全basename；file来源名称/长度/SHA来自具体批准记录，stream名称/长度/SHA为发送方声明，实际字节另验。项目版本仅id/name，不因排序/颜色冲突；记录/文档按内容revision绑定。隐藏、缺失、跨类型目标统一404，不返回当前不可见标题或版本。

状态created/receiving/ready/consumed/expired/failed与提案分开。创建预留声明字节；receiving先落盘，part逐块写，首块/每MiB/终结fsync后写evidence累计真实bytes/hash；完整声明匹配才sealed，固定重命名blob，重读真实字节与当前权限后ready。未知尾部/格式/第三方对象保留核查，未sealed完整part保守failed不自动重传。binding保留schema1/proposal_id/version/owner_revision、consumption保留schema1/operation_id，仅未来受控内部消费使用；131不开放绑定/消费入口。可绑定须ready且未removed/error/binding/consumption，并重验当前授权/目标/字节。策略失效后可查询原持久历史收据，available_for_binding=false，不返回当前目标新元信息。

单文件100MiB/client500MiB/workspace1GiB，1000个仍占资源的会话，24h保留；removed终结墓碑不占活跃会话数，仍保留幂等不让旧request重建。目录跨进程短锁保护预留、物理重命名/删除和removed预算发布；每session OS锁防重复I/O，2/client、4/workspace并发。磁盘free仅再扣未落盘预留（声明总量-真实part/blob占用）和新会话，留16MiB，不将已落盘字节重复扣算。所有内容切换同配额锁，断言0≤materialized≤used；流/hash不持该全局锁。外部进程耗盘仍可能失败，失败或删除未完成不释放预算。

清理仅已知、过期、未绑定且非在途对象，先终结后同一已验证DELETE+READ句柄hash/标删除，短配额锁内关闭句柄实际删除并持久removed；源读取句柄无DELETE权。未知/篡改对象不删，不能仅按路径先验后unlink。处于保护/在途的维护返回protected/busy，不声称已清理。凭据/策略/暂存备份均私人；正文不进普通ZIP、Git、搜索、历史或正式附件索引。


### AG-132 正式附件与执行格式

私人upload-policies schema2在每项增加attachment_write:null或{capability:attachments.write,operations:[create],minimum_confirmation_mode:agent_attested|local_web}，且每client最多一个enabled策略；owner沿用同项具体owner_kind/id。共同授权使用管理日志4新attachment_policy家族，快照before/after_policies可为旧1和新2；原root3/auth4/transport2不变，写后不自动降级。省略或旧schema1没有正式写权限，既有休眠grants仍不生效；schema2下stage-only预览显式显示null并撤销旧共同许可。CAS绑定批准后完整client_version，旧ready不迁移。

提案仍schema3，新kind=attachment/operation=create，target_id为既有owner，base_revision为记录原始Markdown SHA或项目assets/index.json原始字节SHA（缺失取空字节SHA，损坏索引拒绝）。content仅六项owner_kind/id、upload_id、display_name、category、insert_link。项目/issue/todo/info之外拒绝，项目不插正文，分类不自动创建。normalization由附件领域产生固定ASSET-<upload UUID hex>、最终name/path/size/mime/category/id/sha256（项目另有created）、binary_relative/metadata_relative、完整metadata_before/after、body、source与policy等依据；不给Agent机器绝对路径。记录仍使用原attachments列表，项目仍原index列表，新id/sha256是兼容的额外元数据，旧读写保留；没有知识库附件新格式。

依赖schema2包含owner快照、owner_revision、category_revision、upload_id、policy_id、source_sha256。category_revision绑定类别配置原始摘要和从项目索引/当前记录推导的现有名称集合；目标内容/索引及相关集合最终重验。执行计划attachment@1包含固定五步骤及source_bindings（upload/owner revision/bytes/SHA）。source与binding保护先持久proposal再镜像，不以session.binding为空证明无引用。binding仍schema1/proposal_id/version/owner_revision，consumption仍schema1/operation_id=sha256(proposalUUID-version)，不放宽为任意字符串。

新manifest保持外层schema3、独立execution_schema_version=2，位于原operations/<proposalUUID-version>/manifest.json；静态handler attachment@1，字段绑定metadata相对路径及前后摘要、binary_relative、固定asset ID、upload ID/消费ID、authorization_revision、依赖、预览/批准、history_version、metadata_time、copy_evidence、五步骤状态及原receipt。before.md/after.md仅保存元数据快照（项目为JSON字节）；binary.part只在.agent流程目录。确认及固定计划先落prepared/copy pending，再复制；copy_evidence含真实bytes/SHA及volume/index/size/created/written/changed，最终同身份不覆盖rename。没有manifest的残留不是已接受确认，不自动发布。已接受partial证据不足保留；完整part可重验补证据；同名相同SHA但不同身份不接管。

预览的record.updated/project-asset.created显示“提交确认时由服务端生成”，只在受理当前确认时定稿；实际after摘要与metadata_time、真实committed_at、原有格式的唯一history ID记入manifest，重试沿用，不使用草稿时间。时间校验按明确时区的同一时刻进行，不因恢复机器时区不同改写原时间。正文无插链接时原body片段逐字保留，插入时经公共助手只追加，不允许把任意正文改写伪装附件创建；未知meta/info_fields保持。

完成源消费不立即等同可清理。维护仅在committed proposal/manifest/receipt及binding/消费映射/源SHA大小全匹配后退休已消费blob；不需等待24h，但仍须同一已验证句柄安全删除并记removed，失败保留预算。墓碑与receipt供幂等、留原结果，不重建后来删改的附件。未知/在途/未完成消费仍protected。所有私人策略、暂存和.agent意图/快照/part不进可移植ZIP；正式附件及原Markdown/index按原导出规则进入。

## AG-133文档附件序列化与普通网页操作证据

文档仍只有type: document与原category。新增可选attachments，采用与记录一致的有序列表，每项为JSON字符串，字段name/path/size/mime/category及服务生成id/sha256；path相对documents中的原Markdown文件，指向全局assets/images或assets/files。category记录所属文档分类，不建立附件分类索引。没有attachments的旧文档按空列表读取，不批量改写；未知元数据及原正文保留。历史和回收站引用按原owner路径解释。当前实施与实测状态见AI_AGENT_PROGRESS及本机能力验收，不据方案推断验收完成。

服务落盘示例（轻量解析器兼容既有字典读取，写出仍为列表JSON字符串）：

```text
attachments:
  - "{\"name\":\"说明.txt\",\"path\":\"../assets/files/说明.txt\",\"size\":4,\"mime\":\"text/plain\",\"category\":\"原文档分类\",\"id\":\"ASSET-<32位十六进制>\",\"sha256\":\"<64位十六进制>\"}"
```

document正式Agent提案仍schema3/attachment@1，category必须等于文档当前原分类，project_id为null，access_target为type=document及原category，目标revision是原MD字节SHA。使用相同binary_copy/publish、history_snapshot、metadata_write、upload_consume。正文只保留原raw body或公共助手追加链接；旧其它owner的policy2语义不变。

普通网页使用POST /api/documents/<DOC-ID>/attachments/uploads/<UUID>?name=<编码文件名>&expected_revision=<SHA>的原始流及同路径GET查询。UUID不可重用，重放只返回原操作结果，绝不宣称接受另一份请求字节；POST无论是否重放均关闭连接，重复CL/TE拒绝。单文件100MiB、64KiB块、空闲5秒/总60秒、16MiB磁盘余量；先证明目标Windows固定NTFS再接收。documents/Markdown及正式assets仍可移植，原文档读取不依赖Agent或新上传开关。

私人.workbench-document-uploads/<UUID>/operation.json schema_version=1（严格整数），状态receiving/failed/prepared/applying/completed/abandoned。字段包含文档ID、文件名、声明size/base_revision、实际SHA、stream_identity(device/inode)、partial(size/SHA/原生身份)、固定领域view、after_revision、history_version、receipt、removed/compacted及原生发布identity。before.md/after.md为完整快照，binary.part是唯一过程字节。receiving中断只封存失败，不自动发布；prepared/applying使用实际before/after判定恢复，第三方版本停止；completed回执绑定attachment/revision/base_revision/document_id，后续编辑/删除不重放写入。

completed先持久化保留回执的compacted墓碑，再验证摘要/同句柄DELETE精简快照；失败字节先核对创建时设备/文件身份和真实partial SHA/版本，实际消失后removed才释放预算。只有未释放的非完成操作计1GiB预算，receiving/prepared/applying计1000活跃名额，历史墓碑不耗尽名额。abandoned保留证据，不回滚正式文件；未开始写日志的纯空UUID目录可明确放弃为DOC-0000占位墓碑（不是业务文档），未知或含文件目录不可借此清除。全目录格式/路径预检先于维护写；终结证据不进入静态、业务搜索、引用或ZIP。操作日志的相对路径不含机器绝对路径。

GET /api/document-uploads返回全部可发现操作和脱敏错误/操作ID；POST /recover、/cleanup对应恢复及证据回收，POST /abandon要求operation_id/document_id/approved=true。无Agent前置；这些普通网页业务入口不会加入MCP工具，带Agent Authorization访问仍403。原操作尚未接收返回404/document_upload_not_found；损坏或空初始化返回503/document_upload_recovery_required，不能当作无操作重传。

知识ZIP成员为原文件名.md及assets/<规范相对路径摘要前24位>-<原文件名>，不同路径同名不会覆盖，同一规范路径共享一份。副本metadata.path与正文链接同步为ZIP相对路径；内部附件引用在副本中转为普通附件链接，不改正式body或稳定ID。受控来源以原文件目录解释，逐文件原生句柄流式归档；缺失/越界/未知本地HTML或定义式资源明确拒包，不从任意机器路径补齐。裸MD保持原相对路径与metadata，不声称完整备份。

三层路径解释：持久metadata.path及私有计划路径都是原始文件系统相对路径，不进行URL解码；文档Markdown source是URL，恰好解码一次；HTTP route由协议入口unquote一次，附件名称下游不再解码。字面%3A、%253A、%2F、%25、#及中文可作为合法文件名的一部分，正文/HTTP分别编码后解析；真实冒号、问号、斜线等仍按Windows可移植规则拒绝。文档元数据只按完整路径匹配正文附件，不用basename遮蔽另一目录的同名外部图片。原文档中的非业务project_id等未知meta保留，但不参与文档附件归属，正式字节始终在全局assets。

原record/project音视频继续保留audio/*、video/*的正确Content-Type与inline语义，光栅图片/PDF同样按既有可预览类型内联，nosniff保留；HTML、SVG等主动内容采用octet-stream+attachment及CSP sandbox。被动媒体不施加改变其文档origin的sandbox，避免破坏原生浏览器媒体预览；实际兼容范围以HTTP契约和临时合成WAV/WebM真实浏览器验收为准，不引入转码或播放器。

## 概念图磁盘版本与历史（AG-134）

`concept-maps/CMAP-<数字>.json`继续version=2，ID/节点/边/类型/箭头/视口及归一化上限不变。缺version或version=1的旧图继续宽容读取/归一化；未知未来版本可读取原数据但禁止更新和历史恢复，不能降级写回。未知当前元数据保留。GET单图与列表、create/update/restore返回的revision为同一次read_bytes所得原始磁盘字节SHA-256，不根据mtime或重序列化计算；revision/expected_revision是传输字段，不写入JSON或导出副本。

HTTP `PATCH /api/concept-maps/<ID>`及`POST /api/concept-maps/<ID>/history/<version>/restore`必须携带非空expected_revision；缺失返回409及刷新/重读提示，非法签名400，字节变化409、资源缺失404。此处有意阻断旧缓存页面不带版本的覆盖请求；刷新加载新资源后重新读取，再处理原画布或浏览器草稿。Python旧update调用未提供字段时兼容：仅在同一Repository共享写锁内基于当前字节准备和应用，不能宣称保护无版本调用方的外部编辑CAS。显式null不是兼容省略。

更新经过ConceptMapRepository.prepare_update生成PreparedConceptMapWrite（受控目标、ID、before/after字节和固定时间UUID历史名），共享写协调应用。先复验before，保存`history/CMAP-ID/<YYYYMMDD-HHMMSS-ffffff-8hex>.json`原始字节，再复验before、原子替换目标并重读after。历史无索引/新日志，不自动重放；读取不会创建历史目录。历史后失败可能已有旧快照；目标替换后失败/响应丢失可能已经提交，查询当前revision及历史判断，不将异常等同零写入，不宣称多文件原子事务。保留检查与replace之间的外部文件系统竞态。

GET `/api/concept-maps/<ID>/history`列出版本，后接`/<version>`读取完整图与原快照revision。恢复只接受本图ID和受控版本名，不接受路径；复用当前CAS/归一化/Prepared，恢复前的当前图也进入历史。未知/损坏历史在列表标available=false及警告，原文件保留、拒绝恢复。概念图历史本项保留全部，不套用Markdown最近30份策略、不自动清理，长期自动保存会增加磁盘占用；完整ZIP包含这些JSON历史，回收站移图/恢复不删除图历史。

分类改名/删除对每图调用相同Prepared更新；图库单图分类PATCH携带列表revision，旧画布随后保存会冲突。分类配置和多图迁移仍非多文件事务，中途失败明确报错，可按现盘分类重读后继续；不以AG-134宣称AG-139配置事务完成。删除/回收本项不新增Agent操作。

浏览器`workbench-concept-map-draft:<data_dir>:<CMAP-ID>`是schema1、base revision、完整画布的尽力恢复草稿，不能作为业务事实源，不含授权。草稿写失败必须提示导出JSON，不承诺已保存。冲突暂停autosave、保存当前输入/撤销栈，明确选择继续编辑、读取磁盘或确认以当前图覆盖最新磁盘；读取磁盘后的撤销只恢复内容，不恢复旧revision。覆盖确认期间再变仍409。成功flush才允许关闭、切页、切图/图库和新建；已接受的离开使同一open世代失效，迟到响应不能落入新图，等待GET期间新增未保存输入也不覆盖。刷新/关闭标签以beforeunload提示和本地草稿为尽力保障，没有异步保存成功承诺。JSON/PNG导出仅当前画布，不附revision/冲突字段。

## 概念图单调分配元数据（AG-135实施接点）

真正领取图身份时创建/更新config/concept-map-ids.json：严格对象{"schema_version":1,"high_water":非负整数}，布尔/浮点/负数、null、未知字段/版本或损坏拒绝分配，普通HTTP返回503并保留原文件。共享Repository写锁及既有ID锁下，全部正式图、JSON历史、回收站（含移动后索引前孤立图）、提案/manifest/回执占用与游标取max后原子写入新上界，再发布图。失败可以跳号；纯prepare/只读列表和读取不创建游标。永久清除图前亦先记现存最大占用；冲突恢复图拒绝改名/覆盖稳定ID。Agent首提案沿同一分配器领取并以唯一proposal绑定，整体状态以台账为准。

此文件是可移植的ID分配配置，不是提案预留/事务日志，不含机器路径、凭据或批准。完整工作台ZIP及完整解压/迁移保留它；单项目/文档ZIP不含全库分配承诺。缺失时从全部现存证据派生，无法区分首次升级与外部删除游标；升级前永久移除无证据ID不可追溯，人为删除或仅部分恢复分配元数据后不保证无证据旧ID不重用。旧并行进程不了解新游标，分配不受此保证。扫描随全部历史与提案墓碑增长，不自动清理以换取编号复用。

## 图授权与唯一提案执行（AG-135实施接点）

首次明确图管理批准采用registry schema4、client authorization_schema_version5、management log schema5。客户端必有concept_map_grants={schema_version:1,grants:[...]}；每项为concept_maps.read/write、明确operations、project(id)/concept_map_category(name)/concept_map(id)资源及最低确认方式。read为read/agent_attested；write仅create/update，指定图不得create。实际图授权与旧capability_grants分离，后者继续dormant，缺省为空；旧通配project_ids/categories和旧configured不自动激活。范围重命名/删除先持久收窄图分类grants，失败不恢复或扩大到未分类；相关知识库分类授权仍用原流程。

新concept_map日志家族保存graph_action=approve/revoke/narrow、graph_grants_digest和graph_dependencies（仅approve有完整资源依赖，其余为null）。依赖含schema1、分类配置与完整分类集合摘要、每个资源的原始版本、完整派生图ID/revision集合摘要/数量；项目依赖取README原字节，仅用于身份与变化检测，不授予项目正文读取。首私人快照intent5→操作日志→registry4 fence→传输配置→客户端授权发布→终结回执与私人快照清理，仍是原CredentialManager持久恢复，不是新事务。其它操作家族在root4下写log5并保留auth5/图字段、既有文件/暂存/附件字段与版本下界，不降级清空。

孤立新私人快照在日志/root尚未升版时不代表图许可已经生效。旧管理/恢复/修改入口扫描它必须拒绝更改；已运行旧业务和普通网页未必检查这些格式，可按旧有效权限继续。授权真正发布与图提交前重查客户端和资源，旧合法变更导致冲突；不能将所有旧业务称为零写。非秘密摘要不证明文件作者；外部文件系统和混用版本剩余竞态保留。

图proposal仍schema3/digest_algorithm=sha256-json-v3，kind=concept_map、operation=create/update，normalized_content仅{graph}，base_content为完整原始JSON对象（不含传输revision）。target_id在首次create原子proposal保存前经共享游标领取；identity为{schema_version:1,kind:concept_map,id,proposal_id,client_id,workspace_id}，修订不变，取消/过期/内容清理保留。source_target在update绑定原归属，access_target绑定完整候选；两者都要读取授权，写入还要求源、候选及变更归属的具体目标写权限。CLI/MCP均不接收任意磁盘路径作为图来源。

静态logical plan的handler=concept_map@1、steps=[history_snapshot,json_write]，绑定identity/source/target/candidate_digest、authorization_revision和图资源依赖。完整预览含content、base_graph、prepared_graph（仅服务端时间为明确占位）、graph_diff（全部元数据、节点/边稳定ID前后字段及顺序）、graph_warnings、依赖、计划与版本；这些全部进入图预览摘要，旧Markdown预览摘要含义不变。各原图/候选canonical紧凑JSON UTF-8至多256KiB；原始文件独立上限1MiB；实际完整预览响应至多2MiB；MCP结构化+文字完整返回不超过既有8MiB。普通图原500节点/1000边上限保持，超限拒绝413不省略。节点14字段、关系7字段和视口字段须完整、严格类型/有限值、唯一ID/有效端点/箭头兼容；拒静默裁剪、钳制和重新编号，仅颜色字母规范化明确给警告。

图执行manifest外层schema3/execution_schema_version3、固定relative_path=concept-maps/<target_id>.json，before/after.json保存原始字节，managed_time在受理确认时定稿，history_version为固定时间UUID名。静态concrete plan绑定上述字段、身份、前后SHA及proposal plan；回执继续绑定原proposal/version/两个plan digest/after revision与批准。新建没有before/history旧字节；更新history/CMAP-ID/<history_version>.json必须等于原before。履行与恢复共用同一PreparedConceptMapWrite和唯一ProposalStore，不另开进程或状态机。历史落盘及进度记录后仍重查权限/依赖，目标发布前失效就停止；目标after与必要history证明后只补回执。create applying且目标缺失不重建；未知/第三方/缺历史保留503核查。receipt已证明完成后，后来正常编辑或删除仅返回原回执，不重放目标。终结30天后按原清理流程删除before/after.json与内容，identity/target/摘要/回执墓碑及单调游标仍保留。

设置页sessionStorage新增workbench.agentGraphGrants.pending.<workspace_id>，仅存client_id/request_id供结果查询，不存令牌或正文。只读预览实例通过同一conceptMap.create({readOnly:true,...})工厂，共享几何、节点和关系渲染，root隔离、唯一marker ID、AbortController监听器及取消rAF的dispose；无写API、脏标记、草稿或撤销栈。管理票据绑定同一完整预览，前端完整画布和全部明细加载后才允许批准，不将票据视为DOM/人眼/现实身份认证。

## AG-136 单条删除格式与证据（已完成）

新鲜授权为`delete_grants={schema_version:1,grants:[...]}`；仅items.delete/delete/local_web，资源为具体project、item(kind+id)、document_category、concept_map或独立concept_map_category。无通配/idea/project cascade。读取范围、原kind/read/propose/commit与delete许可取交集，图另须新鲜图read。新批准后registry5/auth6/管理log6，transport2不变；auth6必须明确包含图和删除字段。其他管理家族保留全部字段及格式下界，清理/abandon不降版。旧休眠不激活，旧版遇新私人快照/日志拒绝恢复；首快照到格式围栏间旧普通业务仍可能写入，后续依赖CAS拒发布，不承诺整个窗口全业务零写。

仍使用22工具及同prepare/revise/preview/commit。delete仅信封kind/target_id/base_revision/source_note等，无content/body/path/held_source。省略确认方式取local_web，显式agent_attested拒绝。服务生成完整原始UTF-8文件、SHA、元数据/正文/有序info_fields、图只读完整结构、附件元数据及存在/保留状态；不读取二进制。活动正式记录（含legacy idea）、文档、项目README、图全量清单按ID/类型/路径/revision绑定，仅保存目标/命中的全文。无权命中、README/idea无既有全文读契约、坏路径/未知数据或超限通用拒绝，不返回隐藏ID/数量。历史和回收站不计活动断链，明确保留旧引用；既有语法命中也可能只是代码示例。每文件1MiB、4096文件/32MiB实际原始字节、完整实际UTF-8 JSON响应2MiB，全部超限拒绝而非截断。图删除只读显示可处理1MiB原图，原图create/update的256KiB契约不变。

proposal3/sha256-json-v3新增静态trash_delete@1，manifest3/execution_schema4；旧1/2/3处理器语义不改。token固定为record/document/concept-map-agent-<proposal UUID>-<version>，operation_id仍UUID-version。private delete_binding绑定受控相对源、卷/文件index/creation身份、原SHA、排序保留依据、trash_index_digest；dependencies绑定完整活动清单/排序/原索引摘要。实际接受批准时固定deleted_at及原回执；before.md或before.json和index-before.json先落，manifest交叉绑定计划、批准和全部摘要后才移动。原索引快照不提供重建权限。旧排序ID和位置原样保留，相关配置字节为依赖，不更新项目README/document-sort。

执行步骤固定trash_move/trash_index/preserve_sort_and_cache/receipt。先persist move applying，使用同一Windows固定NTFS READ+DELETE句柄核身份/原字节，保持源句柄及祖先保护，基于内部仅句柄生存期有效的HeldDeleteSource核当前授权/全集/索引，再不覆盖rename；无copy fallback。该内部能力不能由HTTP/MCP提供。trash物理身份和原字节均匹配后仅添加本token索引成员，保留无关成员；缓存失效后落原回执。新索引成员delete_schema_version1、original_relative_path和agent_operation_id扩展原7字段；未知格式拒绝，不静默去字段。

prepared且未进入移动时可按当前权限/依赖继续；applying但trash缺失无法区分未移动与已恢复，阻断而不重删source。原trash证据成立，即使源重建或权限撤销，也只补原索引/缓存/回执。异物/不完整证据先全预检拒写。committed重放永远只回原回执，后来恢复/修改/purge不重演。abandon接受当前盘态而非回滚，残留仍受保护。原历史/附件/图游标保留；30天私人内容清理可去before/index快照，但身份/manifest/receipt墓碑保留。默认trash30天，本机可提前purge；Agent无restore/purge/清空入口。

## AG-137 项目创建与独立项目范围（已完成）

新鲜 project_create_grant schema1 为固定 capability=projects.create、operations=[create]、minimum_confirmation_mode=local_web 和 enabled；registry6/auth7/管理日志7，transport2 保持，旧图/删除/文件/暂存/附件字段保留。日志独立 project_create 和 project_access 家族，兼容旧家族；先私人快照、意图和格式围栏，未知旧入口零恢复写拒绝。首次私人快照后旧普通业务仍可能在格式围栏前合法写，项目依赖必须复查。撤销、轮换、收窄、终结和放弃不降版，不因删除证据降级。

项目复用 projects/<id>/README.md 的 Markdown 及既有 issues/todos/ideas/infos、assets/images/files 空目录。候选只接受五字段。固定 slug 在私人提案原子保留，重试/修订/取消/到期/清理不复用已展示 ID；普通和 Agent 共同查物理残留、现存/回收身份与提案/回执。匹配私人授权可用时查显式项目范围和项目暂存策略；原通配语义不变。非自定义排序保持原字节；custom 按有效旧显示顺序补齐项目，清理重复/失效项，新项目置末。完整原排序/前后计划仅留私人 project_sort_details 和本机管理响应；Agent 只见模式、位置、规则和摘要。模板原字节、相关 README 版本集合和排序原字节绑定；完整预览 2MiB，说明 64KiB。

proposal3/manifest3 新增 project_create@1/execution5，依次 project_stage/project_publish/project_sort/receipt。批准受理时固定实际时间和 README 字节；持久批准、after.md、sort-before.json/sort-after.json 与 manifest 后才建立私人同卷暂存。记录目录物理身份（volume/index/created）及完整树；同 NTFS 目录句柄核验后无覆盖 rename，无复制替代。发布前重查授权、占用、模板、集合及原排序；进入发布中后仅可信正式目标可补固定排序和原回执。排序只接受批准的原前后字节；异物不覆盖，已发布项目不重建。回执证明完成后重放不依赖后续项目或排序。终结内容按既有清理，原身份/摘要/回执保留。

独立范围授权绑定原项目创建回执、固定客户端、目录物理身份、当前 README 摘要和完整客户端 CAS。已发布 registry 只补原管理回执；待发布重查真实目录/README 持有句柄，第三方同 ID 同字节目录不视为原项目。批准后只追加一个精确 project_ids，既有授权类型、scope 和通配语义不变。独立授权不是项目写入事务，不会重跑项目。

## AG-138 项目级联回收证据

私有 registry7、客户端授权8 和管理日志8 新增 `project_delete_grants` schema1。每项是 `projects.delete/delete/local_web`，含精确项目 ID 和选中独立附件的 ID 及元数据与内容证据摘要。旧家族按原字段、版本与撤销语义读取。管理日志采用原有私有快照、日志、格式门槛和发布阶段。

proposal3 与 manifest3 的执行分支为 `project_trash@1`、execution6。`before.md` 保存 README 原字节，`index-before.json` 保存原回收索引，`tree-before.json` 保存原树物理身份与全部相对成员证据，若项目排序文件存在，`sort-before.json` 保存其原字节。固定 token 为 `project-agent-<UUID>-<正整数版本>`。回收项 `delete_schema_version=2` 用当前根相对路径，保留原操作 ID，便于完整停机副本核验。项目和子记录 ID 在终结提案证据中长期保留。schema1 仍用于单条删除。可移植 ZIP 保持排除 `.agent` 和 `.trash`。

树最多 4096 个目录和文件成员、64 MiB 原始字节，单文本 1 MiB。完整活动集合最多 4096 文件、32 MiB，完整 UTF-8 JSON 预览最多 2 MiB。二进制仅记录元数据、大小及 SHA-256；保留原字节的完整目录直接移动。额外 NTFS 数据流、硬链接、重解析和未知成员均拒绝。[FindFirstStreamW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-findfirststreamw)、[FindNextStreamW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-findnextstreamw)

## 分类变更和授权（AG-139）

原文档分类、文档排序、图分类及项目独立附件分类继续使用原 JSON 路径。独立附件索引只迁移成员的 `category`。知识库及图默认名称为「未分类」，独立附件默认值为空字符串。旧独立附件目录中的字面「未分类」仍可作为现有普通分类迁移。文档改名保留分类内模式和文件顺序，概念图保留项目归属，独立附件改名保留分类关联标签。

`config/category-identities.json` 和 `config/category-identities-fence.json` 为配对的 schema1 身份记录。按体系和项目记录 active UUID、名称代次、退役 UUID，改名沿用身份，名称复用获得新身份。两文件不一致或分类集合与已记录身份不一致时拒绝分类写入。完整备份保留配对文件。只读查询不会初始化身份文件。

`category_write_grants` schema1 仅允许具体体系、项目、名称与操作。创建许可绑定空缺名称、配置摘要和代次。现有分类许可绑定 UUID 和代次。持久格式门槛为 registry8、授权9、管理日志9、transport2、proposal3/manifest3、`category_mutation@1`/execution7。业务前后原字节与完整扫描摘要存原操作目录，客户端迁移计划存私人凭据目录。单原文件 1 MiB，活动文档或概念图清单 4096 个文件、32 MiB，完整 UTF-8 JSON 预览 2 MiB。
