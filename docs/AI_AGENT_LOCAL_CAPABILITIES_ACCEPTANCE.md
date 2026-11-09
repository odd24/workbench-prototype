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
