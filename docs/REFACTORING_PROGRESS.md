# 本地工作台重构进度台账

> 本文件是重构实施状态的唯一记录来源。  
> 执行方案：[REFACTORING_PLAN.md](./REFACTORING_PLAN.md)  
> 执行规范：[../AGENTS.md](../AGENTS.md)  
> 最后更新：2026-09-17

## 1. 使用规则

- 每次实施重构前，先把对应工作项从 `待开始` 更新为 `进行中`。
- 工作项状态变化、范围调整、验证结果、阻塞、风险和关键决策必须在同一次变更中写入本文件。
- `已完成` 必须有验证证据，不能只依据代码已提交。
- 一个工作项拆成多个提交时，在执行日志中逐次追加，不覆盖历史记录。
- 发现计划外工作时先登记到“待评估事项”，评估后再创建或调整工作项。
- 日期使用 `YYYY-MM-DD`；命令记录实际结果，不写“预计通过”。

状态定义：

| 状态 | 含义 |
| --- | --- |
| 待开始 | 范围已定义，尚未实施 |
| 进行中 | 正在实施，验收尚未完成 |
| 受阻 | 存在明确阻塞条件，需记录原因和解除条件 |
| 已完成 | 产物、自动检查和必要手工验收均已完成 |
| 已取消 | 经决策确认不再实施，必须填写决策编号 |

## 2. 当前摘要

| 项目 | 当前值 |
| --- | --- |
| 当前阶段 | 阶段 5：可靠性、性能和收尾 |
| 当前工作项 | 无（RF-504 已完成） |
| 最近完成 | RF-504 大数据性能验收 |
| 下一工作项 | RF-505 文档和发布收尾 |
| 已知阻塞 | 无 |
| 后端测试基线 | 90 项通过 |
| 下一阶段门禁 | RF-501 至 RF-505 全部完成 |

## 3. 工作项状态

### 阶段 0：治理与基线

| ID | 工作项 | 状态 | 开始 | 完成 | 负责人/执行者 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| RF-000 | 建立执行方案与进度台账 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 建立计划、台账和执行规范 |
| RF-001 | 建立行为基线和固定样本 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 固定数据样本、复制验证与视觉基线清单 |
| RF-002 | 增加 HTTP 集成测试框架 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 临时端口、临时仓储、HTTP/字节流与错误状态测试 |
| RF-003 | 增加 Markdown 契约测试 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 标量、列表、旧格式、Unicode、多行、空正文及失败路径 |

### 阶段 1：后端基础设施拆分

| ID | 工作项 | 状态 | 开始 | 完成 | 负责人/执行者 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| RF-101 | 提取 Markdown 与时间/slug 工具 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 提取 `workbench/markdown_io.py`，保留 `server.py` 兼容导入 |
| RF-102 | 提取路径和外部编辑器能力 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 提取路径/迁移/导出与外部编辑器模块，保留兼容门面 |
| RF-103 | 提取概念图仓储 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 提取归一化、分类、原子写入和 CRUD，保留仓储门面 |
| RF-104 | 提取附件仓储 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 提取记录/项目附件、分类、批量操作和孤儿扫描 |
| RF-105 | 提取知识库与配置仓储 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 组合仓储提取完成，旧排序和空分类重载验证通过 |
| RF-106 | 提取项目与记录仓储 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 组合仓储提取完成，缓存、并发、历史和回收站验证通过 |
| RF-107 | 分离 HTTP 路由 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | HTTP Server、响应工具和资源路由移入独立模块 |
| RF-108 | 精简服务启动文件 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | Repository 门面已提取，启动文件收敛至 CLI 与生命周期 |

### 阶段 2：共享编辑器内核

| ID | 工作项 | 状态 | 开始 | 完成 | 负责人/执行者 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| RF-201 | 提取纯 Markdown 与引用能力 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 纯模块与无浏览器契约测试已落地 |
| RF-202 | 提取统一文档模型 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 统一模型模块、稳定接口和浏览器契约矩阵已落地 |
| RF-203 | 提取结构块与选区操作 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 选区与结构块模块、双编辑器适配和浏览器契约已落地 |
| RF-204 | 统一记录与知识库编辑器 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 共享 editor host 已统一渲染、模型、选区与结构操作入口 |
| RF-205 | 完善编辑器契约验证 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 固定契约、真实浏览器保存/草稿/历史/外部修改与冲突矩阵全部通过 |

### 阶段 3：前端模块拆分

| ID | 工作项 | 状态 | 开始 | 完成 | 负责人/执行者 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| RF-301 | 提取核心 DOM、API 和对话框模块 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 核心 DOM、统一 JSON API、通知与通用对话框模块已落地 |
| RF-302 | 建立状态边界和异步竞态保护 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 四类状态边界和记录、文档、附件请求身份保护已落地 |
| RF-303 | 拆分管理、搜索和回收站 | 已完成 | 2026-09-16 | 2026-09-16 | Codex | 搜索、回收站和使用统计控制器已独立并使用稳定事件委托 |
| RF-304 | 拆分首页和项目视图 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 首页布局与项目视图数据模型、筛选排序及顺序写回边界已独立 |
| RF-305 | 拆分记录和知识库功能 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 共享编辑会话、记录冲突及知识库分类/传输模型已独立 |
| RF-306 | 显式化概念图前端依赖 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | `Workbench.conceptMap` 显式注入核心服务和状态边界 |
| RF-307 | 精简前端入口 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 导航状态、单次启动和窗口生命周期完成显式装配 |

### 阶段 4：CSS 整理

| ID | 工作项 | 状态 | 开始 | 完成 | 负责人/执行者 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| RF-401 | 建立视觉基线 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 四套环境、关键页面、交互状态和空数据基线已记录 |
| RF-402 | 合并设计令牌和基础组件 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 全局/主题令牌及按钮、字段、对话框基础规则已收敛，视觉与交互契约通过 |
| RF-403 | 按功能拆分样式 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 十个目标样式文件已落地，加载顺序、规则完整性和动态类名均有契约保护 |
| RF-404 | 合并响应式覆盖 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 82 个媒体块收敛为 19 个有序断点，关键宽度与空/多数据视觉门禁通过 |

### 阶段 5：可靠性、性能和收尾

| ID | 工作项 | 状态 | 开始 | 完成 | 负责人/执行者 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| RF-501 | 增量刷新和竞态治理 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 记录/文档按签名增量拉取，刷新与轮询共享竞态通道 |
| RF-502 | 统一原子写入 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 单一原子写工具覆盖 Markdown、JSON 配置/索引和导出包 |
| RF-503 | 加固导入导出和路径安全 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 共享校验器覆盖 ZIP、上传名、分类、导出、HTTP 请求、回收站与附件路径边界 |
| RF-504 | 大数据性能验收 | 已完成 | 2026-09-17 | 2026-09-17 | Codex | 1200 记录、160 文档、120 附件、长 Markdown 和 500 节点图通过 |
| RF-505 | 文档和发布收尾 | 待开始 |  |  |  | 最终工作项 |

## 4. 执行日志

每次工作项变更都在表尾追加记录。一个工作项可以有多条记录。

| 日期 | 工作项 | 状态变化 | 修改范围 | 验证结果 | 遗留/下一步 |
| --- | --- | --- | --- | --- | --- |
| 2026-09-17 | RF-306 | 待开始 → 进行中 | 计划把 `concept-map.js` 收口为 `Workbench.conceptMap`，通过初始化参数注入 DOM、API、对话框和 `appState`，由 `app.js` 显式装配并移除概念图可变词法全局；预计修改 `concept-map.js`、`app.js`、`index.html`、新增概念图前端契约测试并同步本台账 | 计划运行概念图模块契约、现有全部 Node 契约、真实浏览器工作流、Python 完整回归、全部语法检查与 `git diff --check` | 风险：自动保存/关闭 flush、撤销重做、分类排序、节点/边交互及页面切换必须保持；数据/API/本地存储键不变，不调整脚本先后顺序以外的加载语义 |
| 2026-09-17 | RF-306 | 进行中 → 已完成 | `concept-map.js` 收口为工厂模块，DOM/API/对话框/应用状态均由 `app.js` 显式注入；共享概念图状态只经 `appState` 访问；页面入口改用公开控制器；新增独立依赖契约并扩展真实浏览器保存验证；更新脚本加载顺序和缓存版本 | 概念图专项、全部 10 个 Node 契约、真实浏览器图库/打开/修改/flush/服务端重读及既有编辑器矩阵、71 项 Python 测试、全部 Python/JavaScript 语法检查和 `git diff --check` 均通过 | 数据格式、API、localStorage 键、自动保存、撤销重做和视觉结构无变化；DEC-020 记录显式工厂边界；下一步 RF-307 精简前端入口 |
| 2026-09-17 | RF-307 | 待开始 → 进行中 | 计划新增导航与应用生命周期模块，提取导航状态兼容读取/持久化、页面和项目标签合法化、单次启动及 `beforeunload`/`pagehide` 绑定；`app.js` 保留 DOM 渲染适配和跨模块回调装配；预计修改 `js/core/`、`app.js`、`index.html`、新增入口契约并同步本台账 | 计划运行新增模块契约、全部 Node 契约、真实浏览器工作流、71 项 Python 回归、全部语法检查和 `git diff --check` | 风险：旧 `workbench-navigation-state`、`mixed → overview` 迁移、无效项目回退、草稿持久化和离开提醒必须保持；不改变页面 DOM、业务 API 或数据格式 |
| 2026-09-17 | RF-307 | 进行中 → 已完成 | 新增 `Workbench.navigation` 管理导航读取、写入、旧标签迁移、页面合法化和 hash 清理；新增 `Workbench.application` 保证启动及窗口生命周期只装配一次；`app.js` 改为注入状态与业务回调，删除重复的存储/监听器基础设施；更新资源缓存版本并新增入口契约 | 新入口专项、全部 11 个 Node 契约、真实浏览器保存/刷新/冲突/导航恢复工作流、71 项 Python 测试、全部 Python/JavaScript 语法检查和 `git diff --check` 均通过 | 数据/API/DOM/localStorage 键无变化；`mixed → overview` 和无效项目回退保持；DEC-021 记录入口控制器边界；阶段 3 门禁完成，下一步 RF-401 |
| 2026-09-17 | RF-401 | 待开始 → 进行中 | 使用固定基线样本的一次性副本，在浅色/深色 × 1440×1000/390×844 四套环境检查首页、项目、知识库、编辑器、概念图、搜索、空状态及主要交互状态；截图仅保存为本地 `preview*.png` 并在结束前移除；预计更新 `docs/BASELINE_CHECKLIST.md` 与本台账 | 计划运行四套浏览器视觉验收、空数据环境检查、基础自动门禁及 `git diff --check` | 风险：浏览器窗口外框会影响可用内容区，验收以页面 viewport 为准；不修改 CSS 或业务代码，发现差异只记录，不在本项混入修复 |
| 2026-09-17 | RF-401 | 进行中 → 已完成 | 新增可重复执行的 `visual_baseline.js`，通过临时固定样本和系统 Edge DevTools 生成浅色/深色 × 桌面/窄屏的首页、项目、记录、交互状态、知识库、文档、概念图和搜索截图，并为全新空目录生成四套空状态截图；评审结果和响应式关注项写入基线清单 | 32 张固定样本截图、4 张空数据截图及 DOM 内容断言通过；主要页面、对话框、hover/focus/disabled/error 状态完成目视检查；保存/刷新/竞态/外部修改继续由真实浏览器工作流通过；基础自动门禁通过 | 截图只写入系统临时目录，Git 不含 `preview*.png`；无数据/API/CSS 变化；窄屏文档大纲占宽登记给 RF-404；Computer Use 连接失败后按技能规则使用既有 Edge DevTools 路径；下一步 RF-402 |
| 2026-09-17 | RF-402 | 待开始 → 进行中 | 将分散的 `:root` 与深色主题变量收敛到文件首部，合并基础按钮、字段和对话框的重复级联；仅做等价整理，不调整功能区布局、响应式规则或用户文案；预计修改 `styles.css`、`index.html`、样式契约测试和本台账 | 计划运行样式契约、修改前后四套固定样本截图对比、真实浏览器工作流、全部 Node/Python 检查及 `git diff --check` | 风险：后置规则承担现有最终样式，移动声明必须保持相同特异性与最终计算值；焦点、禁用、hover、浅色/深色和桌面/窄屏均纳入验收 |
| 2026-09-17 | RF-402 | 进行中 → 已完成 | 将浅色/深色主题和全局字号令牌合并到文件首部；新增控件高度、圆角、对话框圆角和焦点环令牌；合并按钮、图标按钮、创建表单及通用对话框的重复基础声明；新增 `test_styles.js` 锁定单一令牌块、焦点/禁用状态和资源版本，更新 CSS 缓存版本 | 12 个 Node 契约（含真实浏览器工作流）、71 项 Python 测试、22 个 Python 与 34 个 JavaScript 语法检查、修改前后四套固定样本截图及 `git diff --check` 均通过 | 无数据、API、DOM、文案或响应式行为变化；19/32 张稳定截图像素完全一致，其余截图差异来自提示层/滚动等时序状态，成对目视检查未发现非预期视觉差异；DEC-022 固化基础样式令牌边界；下一步 RF-403 |
| 2026-09-17 | RF-403 | 待开始 → 进行中 | 将 `styles.css` 按目标结构拆为令牌、基础、布局、组件、编辑器、记录、知识库、概念图、管理和响应式十个文件；保持各功能规则原有相对顺序，媒体查询按原序集中；更新 `index.html`、样式契约和动态类名审计 | 计划运行加载顺序/选择器契约、JS 动态类名与模板引用审计、修改前后四套视觉基线、真实浏览器工作流、全部 Node/Python 检查及 `git diff --check` | 风险：跨功能后置覆盖在重新分组后可能改变同特异性规则胜序；先用固定样本记录拆分前结果，发现差异时以不改变最终计算样式为准调整归档或选择器 |
| 2026-09-17 | RF-403 | 进行中 → 已完成 | 删除旧 `styles.css`，新增 `css/tokens.css`、`base.css`、`components.css`、`layout.css`、`records.css`、`management.css`、`editor.css`、`knowledge-base.css`、`concept-map.css` 和 `responsive.css`；按首次级联依赖确定显式加载顺序；扩展 `test_styles.js` 检查文件存在/顺序、块平衡、动态类名和纯行为钩子 | 拆分前后各 32 张四套环境截图及结构断言通过；全部 12 个 Node 契约、真实浏览器工作流、71 项 Python 测试、22 个 Python 与 34 个 JavaScript 语法检查和 `git diff --check` 均通过；原/新样式各 633 条非空规则且集合差异为 0 | 无数据、API、DOM 或用户文案变化；桌面/窄屏、浅色/深色主要页面与交互态目视无回归；混在组件行内的少量媒体查询保留原位，交由 RF-404 统一整理；DEC-023 固化加载顺序与行为钩子审计；下一步 RF-404 |
| 2026-09-17 | RF-404 | 待开始 → 进行中 | 提取功能文件中的行内媒体查询，按断点从宽到窄合并到 `responsive.css`；去除重复后置补丁，保持桌面样式不变；重点处理 RF-401 登记的窄屏文档大纲占宽，并检查 1050、920、760、620、390 等关键宽度 | 计划运行响应式结构契约、固定样本与空数据四套视觉基线、关键宽度横向溢出/长中文 DOM 断言、真实浏览器工作流、全部 Node/Python 检查及 `git diff --check` | 风险：同一元素在多个 max-width 断点的胜序依赖源码位置；合并时按宽到窄排列，并以最终计算样式和浏览器截图验证，不借机重设计桌面布局 |
| 2026-09-17 | RF-404 | 进行中 → 已完成 | 从 `components.css`、`records.css`、`management.css`、`editor.css` 和 `knowledge-base.css` 提取全部媒体查询到 `responsive.css`，将 82 个媒体块合并为 19 个唯一条件并按宽到窄排序；为窄屏文档弹窗、大纲和工作区补充同级特异性及溢出约束；更新 CSS 缓存版本、样式契约与可选关键宽度视觉矩阵 | 全部 12 个 Node 契约、真实浏览器保存/刷新/冲突工作流、71 项 Python 测试、22 个 Python 与 34 个 JavaScript 语法检查及 `git diff --check` 通过；四套固定样本 32 张、四套空数据 4 张和 1050/920/760/620/390 五档 40 张截图均通过 DOM 横向溢出断言，并完成代表性窄屏截图目视检查 | 无数据、API、DOM、localStorage 或文案变化；长中文、空分类、空数据和多记录样本保持正常，RF-401 的窄屏文档大纲问题解除；DEC-024 固化唯一响应式入口和断点顺序，阶段 4 门禁完成；下一步 RF-501 |
| 2026-09-17 | RF-501 | 待开始 → 进行中 | 计划为记录和知识库文档建立统一签名差异/合并边界；轮询只拉取签名变化的条目并移除已删除条目，刷新请求与轮询共享竞态通道；保留脏编辑冲突提示及无脏编辑自动重载；预计修改前后端仓储/API、`app.js`、资源加载入口、新增专项契约与浏览器工作流并同步本台账 | 计划运行新增增量刷新与 HTTP 契约、全部 Node 契约、真实浏览器外部修改/竞态工作流、Python 完整回归、全部语法检查及 `git diff --check` | 风险：新增/修改/删除签名集合、请求交错、打开记录/文档、保存中的本地状态必须分别处理；数据格式、现有 API 返回语义和 15 秒失败重试策略保持兼容 |
| 2026-09-17 | RF-501 | 进行中 → 已完成 | 新增 `Workbench.resourceRefresh` 统一签名差异、ID 查询与有序合并；记录摘要支持按 ID 筛选，知识库新增轻量签名接口；15 秒轮询只请求新增/修改条目并移除已删除条目，手动刷新与轮询共享请求代次，保存期间暂停对应轮询；更新资源版本并扩展 HTTP、纯模块和真实浏览器契约 | 全部 13 个 Node 契约、真实浏览器保存/草稿/历史/请求竞态/记录与文档外部修改矩阵、72 项 Python 测试、22 个 Python 与 36 个 JavaScript 语法检查及 `git diff --check` 均通过；浏览器网络断言确认变化轮询不再请求全量记录摘要或全量文档正文 | 无磁盘数据格式、现有 API 返回、DOM、localStorage 或 15 秒失败重试语义变化；新增接口向后兼容，脏编辑继续提示冲突且不静默覆盖；DEC-025 固化签名差异与共享刷新通道；下一步 RF-502 统一原子写入 |
| 2026-09-17 | RF-502 | 待开始 → 进行中 | 计划新增单一持久化工具，以目标文件同目录的唯一临时文件完成 UTF-8 文本、Markdown 与 JSON 的 flush/fsync 后原子替换，并在失败时清理临时文件；迁移项目、记录、文档、配置、概念图、附件索引、回收站索引及机器配置写点；流式附件上传继续写入新文件，不改变大文件路径 | 计划运行新增失败注入/重读契约、仓储与 HTTP 完整回归、全部 Node 契约、真实浏览器保存工作流、全文件语法检查及 `git diff --check` | 风险：Windows 打开文件替换、临时文件残留、缓存失效、JSON 缩进和 Markdown 字节格式必须保持；不改变数据格式、路径、时间字段、回收站或导入导出语义 |
| 2026-09-17 | RF-502 | 进行中 → 已完成 | 新增 `workbench.persistence`，统一字节、UTF-8 文本和 JSON 的同目录唯一临时文件写入、flush/fsync、`os.replace` 与失败清理；项目/记录/历史/文档 Markdown，配置、排序、分类、概念图、附件与回收站 JSON 索引，机器路径配置和导出 ZIP 均切换到该边界；流式附件仍直接写入唯一新文件 | 原子写专项覆盖精确字节、JSON 往返、并发写入、fsync/replace 失败、记录与配置失败重读和生产写点审计；79 项 Python、全部 13 个 Node 契约、真实浏览器保存/重开/外部修改矩阵、24 个 Python 与 36 个 JavaScript 语法检查及 `git diff --check` 均通过 | 无数据格式、API、路径、时间字段或 UI 变化；失败保留旧目标且清理临时文件，未产生缓存回归；DEC-026 完成 EVAL-004，下一步 RF-503 加固导入导出和路径安全 |
| 2026-09-17 | RF-503 | 待开始 → 进行中 | 计划新增共享文件名/分类/归档成员校验与 ZIP 中央目录验证；上传和 Markdown 导入拒绝路径、控制字符及不可移植名称；完整备份排除逃逸符号链接；附件读取/删除限定到各自附件根；回收站恢复目标限定在数据目录；HTTP JSON 请求增加适合 Markdown 的明确上限；预计修改安全辅助、仓储、HTTP 与专项/集成测试 | 计划运行恶意 ZIP 路径和损坏归档、上传名、篡改索引、回收站逃逸、符号链接、超限/截断请求测试，随后执行全部 Python/Node/真实浏览器门禁与语法检查 | 风险：旧附件和分类兼容、跨平台路径分隔符、Windows 保留名、导出大文件和现有流式上传必须保持；项目当前没有 ZIP 导入，不借本项新增恢复功能，生产 ZIP 校验器用于所有导出边界 |
| 2026-09-17 | RF-503 | 进行中 → 已完成 | 新增 `workbench.security`，统一可移植文件名、分类、ZIP 成员和归档结构校验；Markdown 导入、附件上传和导出文件名拒绝路径、控制字符、Windows 保留名及错误扩展名；完整/知识库导出验证 ZIP 且不跟随符号链接，数据迁移拒绝符号链接；记录附件、项目附件、孤儿清理及回收站恢复均限定可信根；HTTP JSON 请求验证长度、完整读取及对象形状，流式上传继续不限总大小 | 新增安全专项覆盖恶意/重复/损坏 ZIP、归档逃逸、非法导入名和分类；附件专项覆盖非法名称、篡改索引及孤儿识别；回收站和 HTTP 集成覆盖越界恢复/删除、异常/负数/超限长度、截断正文及错误 JSON 形状；90 项 Python、全部 13 个 Node 契约（含真实浏览器工作流）、26 个 Python 与 36 个 JavaScript 语法检查均通过 | 无磁盘数据格式或正常 API 变化，不执行迁移；旧合法文件继续可读，损坏的旧分类项在读取时跳过；过去会取 basename 的路径式上传名现在返回 400；流式大附件行为保持；项目仍不提供 ZIP 导入；DEC-027 固化共享不可信输入边界，下一步 RF-504 大数据性能验收 |
| 2026-09-17 | RF-504 | 待开始 → 进行中 | 计划新增可重复、只使用系统临时目录的大数据验收脚本，生成大量项目记录与附件、长 Markdown、知识库文档及 500 节点概念图；分别测量仓储重载/签名/搜索/导出、HTTP 增量端点与真实浏览器首页/项目/知识库/概念图响应，并从磁盘重新实例化校验数量、正文、附件和图数据 | 计划运行性能专项脚本并记录测试机器、样本规模、分阶段耗时、浏览器长任务/交互探针和重载校验；随后运行 90 项 Python、全部 Node 契约、全文件语法检查及 `git diff --check` | 风险：样本生成不能污染真实数据或提交生成物；指标以防冻结和发现数量级回退为主，不建立依赖机器速度的脆弱毫秒断言；若发现瓶颈，只做能独立验证且不改变数据/API 的针对性修复 |
| 2026-09-17 | RF-504 | 进行中 → 已完成 | 新增 `performance_acceptance.py` 和 `performance_browser.js`：生产仓储链路在系统临时目录生成 12 项目/1200 记录/160 文档/120 附件、目标 1 MiB 长 Markdown及 500 节点/499 边概念图；重新实例化校验数量、正文 SHA-256、附件、ZIP CRC 与概念图；独立 HTTP 服务和无头 Edge 测量首页、项目、知识库、长文档、概念图库/画布及增量端点；新增性能基线文档 | Windows 11、8 逻辑 CPU、Python 3.14.3：页面数据就绪 4.70 秒，长文档打开 1.68 秒，500 节点图打开 257.40 毫秒，完整导出 3.45 秒；所有浏览器视图操作小于 30 秒，重操作后继续响应；磁盘重读、1621 个 ZIP 条目、1200 条签名、正文哈希、120 附件和 500/499 图数据全部一致 | 无生产数据格式、API、UI 或运行时依赖变化；脚本不进入快速单元测试发现，避免每次回归承担约 4 分钟真实 fsync 样本生成；长 Markdown 的 1.61 秒单次主线程延迟记录为后续可选优化，不在本项扩大编辑器边界；下一步 RF-505 文档和发布收尾 |
| 2026-09-16 | RF-000 | 待开始 → 已完成 | 新建执行方案与进度台账；重写 `AGENTS.md` 并建立强制记录流程 | 38 个后端测试通过；Python 与两个 JavaScript 文件语法检查通过；`git diff --check` 通过 | 下一步启动 RF-001，建立无个人数据的固定样本和视觉基线清单 |
| 2026-09-16 | RF-001 | 待开始 → 进行中 | 计划新增可复制的无个人数据固定样本、仓储加载测试和浅色/深色 × 桌面/窄屏视觉基线清单；预计修改 `test-fixtures/`、`test_server.py`、`docs/BASELINE_CHECKLIST.md` 与本台账 | 计划运行完整基础门禁，并用临时目录验证固定样本可独立复制和加载 | 风险：旧字典格式、多行字段、空分类、稳定引用和概念图语义必须同时保留；不修改生产数据格式或业务实现 |
| 2026-09-16 | RF-001 | 进行中 → 已完成 | 新增 `test-fixtures/baseline-data/`、样本说明、`docs/BASELINE_CHECKLIST.md` 和复制加载测试；实际修改 `test_server.py` 与本台账，未修改生产代码 | 固定样本从临时目录加载成功；完整 39 项测试、Python/JavaScript 语法检查及 `git diff --check` 全部通过 | 数据/API 无变化；截图不入库，后续 UI/CSS 工作项按清单记录四套环境；下一步 RF-002 |
| 2026-09-16 | RF-002 | 待开始 → 进行中 | 计划新增 `test_http.py`，在临时目录创建仓储并通过端口 `0` 启动进程内 HTTP 服务；覆盖健康检查、静态文件、JSON 请求、ZIP 字节流及错误状态；预计同步本台账 | 计划运行新增 HTTP 测试、完整单元测试与全部基础门禁；新增 Python 文件纳入语法检查 | 风险：处理器仓储为类属性，测试必须串行隔离并在每例结束时关闭服务线程；不改 API 或生产启动方式 |
| 2026-09-16 | RF-002 | 进行中 → 已完成 | 新增 `test_http.py`，实现临时仓储、系统分配端口、进程内服务线程及统一 HTTP 请求辅助；覆盖健康检查、静态文件、JSON 创建/读取、ZIP 字节流和 `400`/`404`/`500` | HTTP 测试 5 项、完整测试 44 项、Python/JavaScript 语法检查和 `git diff --check` 全部通过；每例关闭服务器并清理临时目录 | 数据/API 无变化；HTTP 保护层已建立，下一步 RF-003 Markdown 契约测试 |
| 2026-09-16 | RF-003 | 待开始 → 进行中 | 计划新增 `test_markdown.py`，为轻量 front matter 解析、序列化和磁盘重读建立独立契约；覆盖标量、列表、旧字典、Unicode、多行信息字段、空正文及无效/缺失文件 | 计划运行 Markdown 专项测试、完整测试与全部基础门禁；新增 Python 文件纳入语法检查 | 风险：测试必须固定当前兼容语义，不把轻量解析器误当完整 YAML；不修改生产数据格式或解析行为 |
| 2026-09-16 | RF-003 | 进行中 → 已完成 | 新增 `test_markdown.py`，覆盖 front matter 标量和混合列表、固定旧字典样本、Unicode、多行信息字段、空正文、磁盘写入重读、无 front matter、缺失分隔线、缺失文件和非 UTF-8 文件 | Markdown 专项 6 项、完整测试 50 项、Python/JavaScript 语法检查和 `git diff --check` 全部通过；阶段 0 门禁完成 | 数据/API 无变化；RISK-001 已有契约测试缓解但继续开放；下一步 RF-101 |
| 2026-09-16 | RF-101 | 待开始 → 进行中 | 计划新增 `workbench/__init__.py` 与 `workbench/markdown_io.py`，从 `server.py` 纯移动时间、slug、front matter、Markdown I/O 和信息字段归一化函数，并通过兼容导入保留原公开名称 | 计划运行 Markdown 专项、仓储、HTTP、完整门禁；新增 Python 模块纳入语法检查 | 风险：测试会继续 patch `server.load_markdown`；兼容导入必须保留该名称，且不得改变序列化字节、旧字典读取或异常语义 |
| 2026-09-16 | RF-101 | 进行中 → 已完成 | 新增 `workbench/__init__.py` 和 `workbench/markdown_io.py`；从 `server.py` 纯移动时间、slug、标量、front matter、Markdown I/O 与信息字段归一化函数；`test_markdown.py` 改为直接验证新模块并锁定兼容导出 | Markdown 专项 7 项、完整测试 51 项、全部 Python 模块语法检查、两个 JavaScript 语法检查和 `git diff --check` 通过 | 数据/API/序列化无变化；DEC-006 保留 `server.py` 同名兼容导出；下一步 RF-102 |
| 2026-09-16 | RF-102 | 待开始 → 进行中 | 计划新增 `workbench/paths.py` 与 `workbench/external_editor.py`，提取数据目录选择/迁移、导出位置、目录浏览、导出写入和外部编辑器发现/配置/启动；`server.py` 保留兼容名称及可 patch 的编辑器门面 | 计划补充自定义/系统编辑器启动参数、无效路径和兼容导出测试，并运行路径专项、仓储、HTTP及完整门禁 | 风险：模块不得反向导入 `server.Repository`；迁移通过当前仓储类型构造新实例，外部程序继续使用参数数组且禁止 shell 字符串 |
| 2026-09-16 | RF-102 | 进行中 → 已完成 | 新增 `workbench/paths.py`、`workbench/external_editor.py` 和 `test_paths.py`；从 `server.py` 提取数据/导出目录、迁移、目录浏览、导出写入及编辑器发现/配置/启动；保留路径兼容导出和可 patch 的编辑器门面 | 路径与编辑器专项 5 项、完整测试 56 项、新增模块语法检查、两个 JavaScript 语法检查和 `git diff --check` 全部通过 | 数据/API/机器配置位置无变化；DEC-007 使用仓储类型构造和检测器注入避免反向依赖；下一步 RF-103 |
| 2026-09-16 | RF-103 | 待开始 → 进行中 | 计划新增 `workbench/concept_maps.py`，以组合仓储提取概念图归一化、分类、原子写入和 CRUD；主 `Repository` 保留同名委托方法及现有目录属性 | 计划运行概念图专项、固定样本、回收站、HTTP 和完整门禁；新增模块纳入语法检查 | 风险：保持 500 节点/1000 边、文本/坐标/尺寸/颜色/缩放约束、连接短语箭头规则、稳定 ID、分类迁移和 `.trash` 语义 |
| 2026-09-16 | RF-103 | 进行中 → 已完成 | 新增 `workbench/concept_maps.py` 和 `test_concept_maps.py`；归一化、分类、原子 JSON 写入及 CRUD 移入 `ConceptMapRepository`；主 `Repository` 通过同名方法委托并保留常量、目录和私有入口兼容 | 概念图边界/重载 2 项、既有概念图专项 4 项、固定旧 JSON、完整测试 58 项及全部语法/差异检查通过 | JSON 版本、ID、限制、箭头、视口、分类与回收站语义无变化；DEC-008 使用组合仓储；下一步 RF-104 |
| 2026-09-16 | RF-104 | 待开始 → 进行中 | 计划新增 `workbench/assets.py`，以组合仓储提取记录附件、项目独立附件索引、分类、批量操作、流式上传和孤儿扫描；主 `Repository` 保留同名委托方法 | 计划运行附件专项、大文件流、重名/路径、批量分类删除、孤儿扫描、导出、HTTP 和完整门禁；新增模块纳入语法检查 | 风险：记录附件与项目附件索引不得混用；流式上传保持分块读取；所有解析路径继续限制在数据根或项目根；失败上传必须清理部分文件 |
| 2026-09-16 | RF-104 | 进行中 → 已完成 | 新增 `workbench/assets.py` 和 `test_assets.py`；记录/项目附件、分类、批量操作、流式上传、路径解析和孤儿扫描移入 `AttachmentRepository`；主 `Repository` 保留公共与私有委托入口 | 附件边界专项 3 项、既有附件/引用专项 6 项、完整测试 61 项及全部语法/差异检查通过；10MB+ 流仍分块读取 | 数据/API/索引格式无变化；记录与项目附件继续独立，路径保持根目录约束，中断上传清理部分文件；下一步 RF-105 |
| 2026-09-16 | RF-105 | 待开始 → 进行中 | 计划新增 `workbench/configuration.py`、`workbench/documents.py` 和边界测试；提取项目/文档排序、文档分类、标签、状态、工作流配置及知识库文档 CRUD、导入导出、引用目标和反向链接；主 `Repository` 保留同名委托入口 | 计划运行知识库与配置专项、固定旧配置、分类与排序、标签/状态迁移、反向链接、HTTP 和完整门禁；新增模块纳入语法检查 | 风险：空分类与旧排序格式必须保留；分类重命名/删除和标签/状态重命名必须同步使用方；外部编辑器 patch 兼容及文档 ID、Markdown 字节/API 结构不得变化 |
| 2026-09-16 | RF-105 | 进行中 → 已完成 | 新增 `workbench/configuration.py`、`workbench/documents.py` 和 `test_documents.py`；配置迁移规则及知识库文档持久化、引用和导入导出移入组合仓储；`server.py` 保留全部兼容委托入口 | 知识库边界/旧排序重载 2 项、分类/排序/状态/反向链接/外部编辑器专项 6 项、完整测试 63 项及全部语法/差异检查通过 | 数据格式、API、文档 ID、Markdown 和外部编辑器 patch 路径无变化；DEC-008 组合仓储模式继续适用；无 UI 修改，下一步 RF-106 |
| 2026-09-16 | RF-106 | 待开始 → 进行中 | 计划新增 `workbench/projects.py`、`workbench/records.py` 和边界测试；提取项目 CRUD、记录 CRUD/类型转换、搜索、缓存、历史及 Markdown 导入；共享回收站与整库导出仍由兼容门面协调 | 计划运行项目/记录边界、并发编号、缓存与外部修改、信息字段、历史、转换、回收站、附件联动、HTTP 和完整门禁；新增模块纳入语法检查 | 风险：配置、附件、文档反向链接与项目/记录仓储存在双向协作；通过回调注入保持无反向导入，并保留 `server.load_markdown`、外部编辑器和缓存字段兼容入口 |
| 2026-09-16 | RF-106 | 进行中 → 已完成 | 新增 `workbench/projects.py`、`workbench/records.py` 和 `test_records.py`；项目 CRUD 与记录持久化、搜索、缓存、历史、类型转换及 Markdown 导入移入组合仓储；共享回收站和整库导出继续由 `Repository` 协调 | 项目/记录边界与重载 2 项、并发/缓存/外部修改/信息字段/转换/历史/回收站/附件引用专项 10 项、完整测试 65 项及全部语法/差异检查通过 | 数据格式、API、ID、缓存失效、历史和可恢复删除语义无变化；保留 `server.load_markdown`、编辑器和缓存字段兼容路径；DEC-008 继续适用；下一步 RF-107 |
| 2026-09-16 | RF-107 | 待开始 → 进行中 | 计划新增 `workbench/http_api.py`，移动 `WorkbenchHTTPServer`、`WorkbenchHandler`、响应工具与 HTTP 动词入口，并按资源拆分内部路由；`server.py` 保留兼容导出和启动装配 | 计划扩展 HTTP 集成测试覆盖独立模块、成功、400、404、409、500、静态文件和流式/字节响应；运行完整门禁 | 风险：处理器类级仓储切换、静态目录、数据目录迁移、可 patch 配置/编辑器函数和错误映射均为兼容接口；通过依赖回调和兼容子类保持现有调用路径 |
| 2026-09-16 | RF-107 | 进行中 → 已完成 | 新增 `workbench/http_api.py`，移动独占端口 Server、Handler、JSON/字节响应和全部动词路由；GET 按文档、概念图、项目附件和记录资源拆分；`server.py` 兼容导出原类和版本号 | HTTP 集成测试扩展至 8 项，覆盖模块兼容、成功、400/404/409/500、静态缓存头、ZIP 字节流和约 1MB 原始流上传/内联下载；完整测试 68 项及全部语法/差异检查通过 | URL 与成功响应结构无变化；新增 `FileExistsError → 409` 和 PUT/PATCH/DELETE 未处理异常 → 500 映射；类级仓储切换支持处理器子类；无数据/UI 影响；下一步 RF-108 |
| 2026-09-16 | RF-108 | 待开始 → 进行中 | 计划新增 `workbench/repository.py`，移动兼容 `Repository` 门面、仓储装配、回收站、整库导出和演示数据；`server.py` 仅保留兼容导出、CLI 参数、旧进程替换和服务生命周期 | 计划新增启动文件边界与 CLI 参数测试，并运行仓储、HTTP、`--seed-demo`/自定义目录相关专项和完整门禁 | 风险：现有测试和本地调用可能 patch `server.load_markdown`、`server.open_markdown_external` 或从 `server` 导入常量/辅助函数；通过轻量装配子类与兼容再导出维持入口，不改变启动命令 |
| 2026-09-16 | RF-108 | 进行中 → 已完成 | 新增 `workbench/repository.py` 和 `test_startup.py`；组合仓储门面、初始化、回收站、整库导出和演示数据移出启动文件；`server.py` 以轻量子类保留旧 patch 点，并新增可测试的 `build_argument_parser()`/`main(argv)` | 启动边界 3 项与兼容专项 4 项通过；完整测试 71 项、全部 Python/JavaScript 语法检查、`python server.py --help` 和差异检查通过；`server.py` 从约 658 行降至约 160 行 | 数据/API/启动命令无变化；`--seed-demo`、`--replace`、`--open`、自定义目录、主机和端口均由测试锁定；DEC-009 保留轻量兼容装配子类；阶段 1 门禁完成，下一步 RF-201 |
| 2026-09-16 | RF-201 | 待开始 → 进行中 | 计划新增 `js/editor/markdown.js` 和无浏览器纯函数测试；提取 HTML 转义、Markdown/表格渲染、引用解析、代码语言/高亮和颜色规范化；状态相关的引用目标与附件解析通过回调注入 | 计划运行固定 Markdown 输出、安全转义、表格、引用、语言/颜色专项，完整后端回归、全部 JavaScript 语法检查与临时数据浏览器验收；同步 `index.html` 加载顺序和缓存版本 | 风险：现有渲染器隐式读取 `currentRecord`、`referenceTargets`、文档和记录状态；纯模块不得读取 DOM、当前对象或固定 ID，`app.js` 仅保留状态适配器 |
| 2026-09-16 | RF-201 | 进行中 → 已完成 | 新增 `js/editor/markdown.js` 和 `test_markdown_core.js`；HTML/颜色、Markdown/表格、引用、代码语言/高亮及纯文本能力移入 `Workbench.markdown`；`app.js` 保留状态适配器，`index.html` 在主应用前加载模块并更新缓存版本 | 纯函数固定输出与安全转义专项通过；完整后端 71 项、全部 Python/JavaScript 语法和差异检查通过；临时数据浏览器中完成记录与知识库、浅色/深色、桌面/窄屏验收且无控制台错误 | 数据、API、Markdown 输出和脚本先后契约不变；引用目标、引用 HTML 和图片 HTML 由回调注入，纯模块不读取当前记录、文档或 DOM；DEC-010；下一步 RF-202 |
| 2026-09-16 | RF-202 | 待开始 → 进行中 | 计划新增 `js/editor/document-model.js`，移动 block type/ID、hydrate、行内与表格/代码序列化、DOM → model、model → Markdown 和编辑器 render；提供稳定 `render`、`serialize`、`normalize` 接口，`app.js` 保留薄适配器 | 计划覆盖段落、标题、列表、任务列表、引用、代码块、分隔线、表格和对齐块的 Markdown → DOM → model → Markdown 往返；运行完整回归、全部语法检查与临时数据浏览器验收；更新加载顺序和缓存版本 | 风险：模块依赖浏览器 DOM、编辑器块 ID 和 `Workbench.markdown`；不得读取 `currentRecord`、`currentDocument` 或固定 DOM ID，不提前迁移 RF-203 的选区/结构操作 |
| 2026-09-16 | RF-202 | 进行中 → 已完成 | 新增 `js/editor/document-model.js`、`test_document_model.js` 和浏览器契约页；提取行内/代码/表格序列化、块类型与 ID、hydrate、DOM → model、model → Markdown；稳定导出 `render`、`serialize`、`normalize`，`app.js` 仅装配引用和图片回调 | 浏览器契约覆盖段落、标题、普通/任务/编号列表、引用、代码、分隔线、表格及对齐块并显示 PASS；记录和知识库编辑器临时数据验收正常且无控制台错误；Node 契约、完整后端 71 项、全部语法与差异检查通过 | 数据/API/已有 Markdown 兼容不变；补齐分隔线渲染与保存往返，避免原有 `<hr>` 保存丢失；模块不读取当前记录、当前文档或固定 DOM ID；DEC-011；下一步 RF-203 |
| 2026-09-16 | RF-203 | 待开始 → 进行中 | 计划新增 `js/editor/editor-selection.js` 与 `js/editor/editor-blocks.js`；提取选区检测/捕获/恢复、光标、文本插入，以及任务项、引用、代码块、引用块、表格和分隔线的创建/插入/Enter 行为；共享操作均接收 editor、selection/range 和 onChange | 计划扩展浏览器契约验证两个编辑器可复用相同操作，并运行记录/知识库临时数据交互、完整后端回归、全部 JavaScript/Python 语法和差异检查；同步脚本加载顺序与缓存版本 | 风险：现有函数分散维护 `lastEditorRange`/`documentLastRange`，并混合工具栏、状态和保存回调；模块不得读取当前记录、当前文档、固定编辑器 ID 或具体按钮，应用层只保留状态适配 |
| 2026-09-16 | RF-203 | 进行中 → 已完成 | 新增 `js/editor/editor-selection.js`、`js/editor/editor-blocks.js`、`test_editor_blocks.js` 和浏览器契约页；选区捕获/恢复、光标、文本粘贴，以及普通/任务列表、引用、代码、引用块、表格、分隔线和 Enter 行为移入共享模块；记录/知识库差异仅由参数和 `onChange` 适配 | 浏览器契约显示 PASS，覆盖 selection/caret 与全部目标结构块；临时数据中记录任务项插入、知识库引用块切换及保存状态正常，控制台无错误；Node 契约、完整后端 71 项、全部语法与差异检查通过 | 数据/API/Markdown 无变化；共享模块不读取当前记录、当前文档、固定编辑器 ID 或具体按钮；`app.js` 删除约 376 行重复实现；DEC-012；RISK-002 已缓解；下一步 RF-204 |
| 2026-09-16 | RF-204 | 待开始 → 进行中 | 计划新增 `js/editor/editor-host.js`，由记录和知识库各自创建同类宿主实例；统一 render/normalize/serialize、选区缓存、结构块命令和结构键盘事件；业务层保留元数据、保存/草稿、阅读模式与工具栏文案 | 计划增加双宿主同 Markdown 输出一致及保存重开往返浏览器契约，并在临时数据中分别完成记录和知识库编辑、保存、关闭、重开；运行完整自动门禁并更新缓存版本 | 风险：`lastEditorRange`、`documentLastRange` 还被颜色、浮动工具栏和引用插入使用；迁移到实例内选区状态时必须保持选择文本和恢复光标语义，不得合并两个业务保存状态 |
| 2026-09-16 | RF-204 | 进行中 → 已完成 | 新增 `js/editor/editor-host.js`，记录与知识库各创建独立宿主实例，共享渲染、序列化、选区缓存、结构命令和结构键盘事件；删除两套全局 range 状态；修改 `app.js`、`index.html`、`js/editor/document-model.js`、编辑器契约页及本台账 | 双宿主契约和表格后输入回归显示 PASS；临时数据中两类编辑器对同一 Markdown 完成编辑、自动保存、关闭重开，磁盘正文完全一致且控制台无错误；Node 契约、完整后端 71 项、全部 Python/JavaScript 语法与差异检查通过 | 数据/API/Markdown 契约无变化；记录与文档仍保留独立 dirty、草稿、保存和阅读模式；DEC-013；RF-205 继续扩充完整编辑器行为矩阵 |
| 2026-09-16 | RF-205 | 待开始 → 进行中 | 计划扩充浏览器契约固定样本，覆盖全部结构块、代码语言、任务状态、表格对齐与受控 HTML 扩展；新增可执行验收矩阵文档，实际验证记录草稿恢复、历史恢复、外部修改刷新和三类冲突处理；预计修改 `test_editor_blocks.js`、`docs/EDITOR_ACCEPTANCE_MATRIX.md` 与本台账 | 计划运行三个 Node 契约、浏览器契约页、完整 Python 回归、全部语法/差异检查，并使用一次性数据目录完成真实保存与重开验证 | 风险：浏览器契约依赖原生 DOM；手工冲突验证不得触碰真实 `workbench-data/`，不得把外部编辑器进程或本机路径写入仓库；不修改生产数据/API/业务行为 |
| 2026-09-16 | RF-205 | 进行中 → 已完成 | 新增 `test_editor_workflows.js`，以 Node 标准库启动临时服务和 Edge，通过 DevTools 驱动真实应用；修复外部修改冲突读取摘要缺少正文，以及冲突决策后旧草稿重新覆盖所选版本；实际修改 `app.js`、`index.html`、浏览器测试、验收矩阵和本台账 | 保存重开、刷新草稿恢复、历史恢复、无 dirty 外部刷新、dirty 冲突、磁盘版/工作台版/合并版、文档外部修改保护全部通过；完整 71 项 Python 回归及全部语法/差异检查通过 | 数据格式和 API 无变化；记录冲突现在按 ID 获取完整正文，明确冲突决策后清理对应草稿；DEC-014；RISK-005 已缓解；阶段 2 完成，下一步 RF-301 |
| 2026-09-16 | RF-301 | 待开始 → 进行中 | 计划新增 `js/core/dom.js`、`js/core/api.js`、`js/core/dialogs.js` 和核心契约测试；从 `app.js` 纯移动 DOM 查询、安全转义/颜色适配、JSON API、toast 通知和通用确认/输入对话框，并保留现有词法别名供主应用与概念图使用 | 计划运行核心 Node 契约、真实浏览器工作流、完整 Python 回归、全部 JavaScript/Python 语法及差异检查；更新 `index.html` 加载顺序和缓存版本 | 风险：`concept-map.js` 当前依赖 `app.js` 的全局词法名称；新模块必须先于 `app.js` 加载，但 `app.js` 继续声明兼容别名，不提前迁移业务状态或概念图依赖 |
| 2026-09-16 | RF-301 | 进行中 → 已完成 | 新增 `js/core/dom.js`、`js/core/api.js`、`js/core/dialogs.js` 和 `test_app_core.js`；`app.js` 改为从 `window.Workbench` 核心命名空间建立兼容别名，移除本地 API、通知和通用对话框实现；更新脚本加载顺序、缓存版本、浏览器工作流测试及本台账 | 核心契约覆盖 DOM、安全适配、API 成功/409/无效 JSON 和导出接口；真实浏览器覆盖别名同一性、toast、输入选项转义、概念图库及完整编辑器流程；71 项 Python 回归、全部语法和差异检查通过 | 数据/API/文案/视觉无变化；HTML 与颜色安全规则继续复用 RF-201 的纯 Markdown 契约，不创建平行实现；DEC-015；下一步 RF-302 |
| 2026-09-16 | RF-302 | 待开始 → 进行中 | 计划新增 `js/core/state.js` 与状态契约测试，把服务端数据、界面选择、编辑器会话和草稿/保存状态分为 `serverData`、`uiState`、`editorState`、`draftState`；为记录详情、项目附件、文档保存/轮询和附件上传增加请求身份校验；预计修改 `app.js`、`index.html`、浏览器工作流测试及本台账 | 计划运行状态 Node 契约、真实浏览器快速切换竞态场景、既有编辑器契约、完整 Python 回归、全部语法和差异检查 | 风险：经典脚本仍共享词法名称；本项只建立单一状态边界和保护高风险异步落点，不提前拆分 RF-303～RF-306 的功能模块，也不改变 API、数据格式、草稿键或 UI 文案 |
| 2026-09-16 | RF-302 | 进行中 → 已完成 | 新增 `js/core/state.js` 和 `test_state.js`；`app.js` 通过访问器把现有变量归入四类状态边界，并以统一请求注册表保护记录详情/轮询、文档保存/反向链接/轮询、记录附件上传、项目附件加载/上传/分类/删除；更新脚本缓存版本、真实浏览器竞态场景及本台账 | 状态契约和全部既有 Node 契约通过；真实浏览器人为延迟先发请求后，记录、项目附件和文档均保持后发对象；完整编辑器工作流和 71 项 Python 回归通过；22 个 Python、17 个 JavaScript 文件语法检查及差异检查通过 | 数据格式、HTTP API、草稿键、文案和视觉无变化；经典脚本兼容变量由 `Workbench.appState` 访问器暴露，后续功能模块只依赖四类显式状态；DEC-016；下一步 RF-303 |
| 2026-09-16 | RF-303 | 待开始 → 进行中 | 计划新增管理、搜索和回收站前端模块及纯契约测试；把低耦合渲染、筛选/选择状态和稳定祖先上的委托事件移出 `app.js`，保留标签、工作流、设置、时间线、归档、文档与概念图等既有管理页编排入口 | 计划运行模块 Node 契约、真实浏览器重复渲染/使用统计导航/搜索/回收站流程、完整 Python 回归、全部语法和差异检查；更新 `index.html` 加载顺序和缓存版本 | 风险：管理页包含多个高耦合子页面；本项优先提取共用外壳与独立搜索/回收站，不提前拆分 RF-304～RF-306；事件必须委托到稳定祖先，重复渲染不得重复注册 |
| 2026-09-16 | RF-303 | 进行中 → 已完成 | 新增 `js/features/search.js`、`js/features/trash.js`、`js/features/manage.js` 和 `test_management_features.js`；搜索筛选与请求落点、回收站选择/恢复/永久删除、标签/状态使用统计导航及其事件绑定移出 `app.js`；更新脚本加载顺序、缓存版本、浏览器工作流和 Windows 临时浏览器目录清理重试 | 模块契约与全部既有 Node 契约通过；真实浏览器连续重绘管理页后三个控制器监听器均保持 1 份，搜索可打开，回收站选择只触发一次，使用统计可打开记录并返回明细和总览；完整编辑器工作流、71 项 Python 回归、22 个 Python/21 个 JavaScript 文件语法及差异检查通过 | 数据格式、HTTP API、文案和视觉无变化；标签、工作流、设置、时间线等高耦合业务仍由主应用编排，后续按 RF-304～RF-306 拆分；DEC-017；下一步 RF-304 |
| 2026-09-17 | RF-304 | 待开始 → 进行中 | 计划新增首页/项目视图模块和契约测试，提取首页布局规范化与存储、项目记录筛选/排序、手动顺序计算及稳定容器拖放协调；预计修改 `app.js`、`index.html`、浏览器工作流测试和本台账 | 计划运行模块 Node 契约、真实浏览器拖放/排序写回与刷新重载、既有编辑器工作流、完整 Python 回归、全部语法和差异检查 | 风险：首页和项目视图与记录/附件渲染共享大量 HTML 辅助函数；本项提取状态与持久化边界，不提前搬迁 RF-305 的编辑器和附件业务；旧 `localStorage` 键、配置字段及手动排序语义必须保持 |
| 2026-09-17 | RF-304 | 进行中 → 已完成 | 新增 `js/features/home.js`、`js/features/project-view.js` 和 `test_home_project_features.js`；首页旧键读取、布局归一化/保存/DOM 顺序回收，以及项目标签页筛选、记录排序、附件筛选和可见顺序合并移出 `app.js`；既有拖放处理通过模块结果写回原 `localStorage` 和项目配置字段；更新脚本缓存版本、浏览器验收和本台账 | 模块契约与全部既有 Node 契约通过；真实浏览器调整首页分栏、项目记录和状态列顺序后，重新读取本地存储并刷新项目数据仍保持顺序；完整编辑器工作流、71 项 Python 回归、22 个 Python/24 个 JavaScript 文件语法及差异检查通过 | `workbench-home-layout-v1/v2`、项目排序字段、HTTP API、数据格式、文案和视觉均无变化；HTML 渲染保留为 `app.js` 适配层，RF-307 再精简入口；DEC-018；下一步 RF-305 |
| 2026-09-17 | RF-305 | 待开始 → 进行中 | 计划新增共享编辑会话、记录冲突和知识库视图/传输模块及契约测试；让记录与知识库复用草稿存储和保存状态边界，提取冲突展示状态、分类排序与 Markdown 导入解析；预计修改 `app.js`、`index.html`、真实浏览器工作流和本台账 | 计划运行新增 Node 契约、真实浏览器关闭/切页/刷新/草稿恢复/外部修改/冲突/保存失败重试矩阵、完整 Python 回归、全部语法和差异检查 | 风险：两个编辑器必须继续拥有独立 dirty/saving/timer/草稿状态；不移动共享 editor host 或改变 API、localStorage 键、分类排序字段、Markdown 内容和冲突三种选择语义 |
| 2026-09-17 | RF-305 | 进行中 → 已完成 | 新增 `js/features/editor-session.js`、`record-conflict.js`、`knowledge.js` 和 `test_record_knowledge_features.js`；记录与知识库编辑器改由独立会话实例持有 dirty/saving/timer 和原草稿键，冲突差异/弹窗状态、分类与文档排序、旧 `mode` 兼容、Markdown 导入解析和安全导出名移出 `app.js`；更新脚本缓存版本、浏览器工作流和本台账 | 9 个 Node 契约通过；真实浏览器验证记录关闭/切换、文档关闭、刷新草稿恢复、网络失败保留草稿并成功重试、历史、外部刷新、记录三种冲突选择和文档外部修改保护；71 项 Python 回归、22 个 Python/28 个 JavaScript 文件语法及差异检查通过 | 数据格式、HTTP API、`workbench-editor-draft:*`/`workbench-document-draft:*`、分类排序字段、文案和视觉无变化；共享 editor host 保持唯一；DEC-019；下一步 RF-306 |

## 5. 验证记录

| 日期 | 工作项 | 检查 | 结果 | 备注 |
| --- | --- | --- | --- | --- |
| 2026-09-16 | RF-000 | `python -m unittest -v` | 通过，38 项 | 重构前后端测试基线 |
| 2026-09-16 | RF-000 | `python -m py_compile server.py test_server.py` | 通过 | 无输出 |
| 2026-09-16 | RF-000 | `node --check app.js` | 通过 | 无输出 |
| 2026-09-16 | RF-000 | `node --check concept-map.js` | 通过 | 无输出 |
| 2026-09-16 | RF-000 | `git diff --check` | 通过 | Windows 工作区可能显示 LF/CRLF 提示，不属于内容错误 |
| 2026-09-16 | RF-001 | `python -m unittest -v test_server.RepositoryTests.test_fixed_baseline_data_can_be_copied_and_loaded_independently` | 通过，1 项 | 样本复制到临时目录后由新仓储实例读取；验证旧字典字段、引用、空分类、排序与概念图语义 |
| 2026-09-16 | RF-001 | `python -m unittest -v` | 通过，39 项 | 包含新增固定样本测试 |
| 2026-09-16 | RF-001 | `python -m py_compile server.py test_server.py` | 通过 | 无输出 |
| 2026-09-16 | RF-001 | `node --check app.js` | 通过 | 无输出；本工作项未修改前端代码 |
| 2026-09-16 | RF-001 | `node --check concept-map.js` | 通过 | 无输出；概念图固定 JSON 由仓储加载测试覆盖 |
| 2026-09-16 | RF-001 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-002 | `python -m unittest -v test_http` | 通过，5 项 | 临时端口与目录；覆盖健康、静态、JSON、ZIP 字节流及错误状态 |
| 2026-09-16 | RF-002 | `python -m unittest -v` | 通过，44 项 | 39 项仓储测试与 5 项 HTTP 集成测试 |
| 2026-09-16 | RF-002 | `python -m py_compile server.py test_server.py test_http.py` | 通过 | 新增 HTTP 测试文件已纳入 |
| 2026-09-16 | RF-002 | `node --check app.js` | 通过 | 无输出；本工作项未修改前端代码 |
| 2026-09-16 | RF-002 | `node --check concept-map.js` | 通过 | 无输出；本工作项未修改前端代码 |
| 2026-09-16 | RF-002 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-003 | `python -m unittest -v test_markdown` | 通过，6 项 | 覆盖固定样本、往返和失败路径 |
| 2026-09-16 | RF-003 | `python -m unittest -v` | 通过，50 项 | 阶段 0 完整测试门禁 |
| 2026-09-16 | RF-003 | `python -m py_compile server.py test_server.py test_http.py test_markdown.py` | 通过 | 全部 Python 源文件与测试文件 |
| 2026-09-16 | RF-003 | `node --check app.js` | 通过 | 无输出；本工作项未修改前端代码 |
| 2026-09-16 | RF-003 | `node --check concept-map.js` | 通过 | 无输出；本工作项未修改前端代码 |
| 2026-09-16 | RF-003 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-101 | `python -m unittest -v test_markdown` | 通过，7 项 | 直接验证新模块及 `server.py` 兼容导出 |
| 2026-09-16 | RF-101 | `python -m unittest -v` | 通过，51 项 | 仓储与 HTTP 行为保持 |
| 2026-09-16 | RF-101 | `python -m py_compile server.py workbench/__init__.py workbench/markdown_io.py test_server.py test_http.py test_markdown.py` | 通过 | 新模块已纳入语法检查 |
| 2026-09-16 | RF-101 | `node --check app.js` | 通过 | 无输出；本工作项未修改前端代码 |
| 2026-09-16 | RF-101 | `node --check concept-map.js` | 通过 | 无输出；本工作项未修改前端代码 |
| 2026-09-16 | RF-101 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-102 | `python -m unittest -v test_paths` | 通过，5 项 | 覆盖兼容导出、无效/嵌套路径、自定义/系统编辑器和参数数组启动 |
| 2026-09-16 | RF-102 | `python -m unittest -v` | 通过，56 项 | 包含现有迁移、导出、编辑器选择及 HTTP 测试 |
| 2026-09-16 | RF-102 | `python -m py_compile server.py workbench/__init__.py workbench/markdown_io.py workbench/paths.py workbench/external_editor.py test_server.py test_http.py test_markdown.py test_paths.py` | 通过 | 新模块与测试已纳入 |
| 2026-09-16 | RF-102 | `node --check app.js` | 通过 | 无输出；本工作项未修改前端代码 |
| 2026-09-16 | RF-102 | `node --check concept-map.js` | 通过 | 无输出；本工作项未修改前端代码 |
| 2026-09-16 | RF-102 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-103 | `python -m unittest -v test_concept_maps` | 通过，2 项 | 验证组合仓储门面、原子写入和重新实例化读取 |
| 2026-09-16 | RF-103 | `python -m unittest -v test_server.RepositoryTests.test_concept_map_create_update_and_trash test_server.RepositoryTests.test_concept_map_categories_can_be_created_assigned_and_renamed test_server.RepositoryTests.test_concept_map_category_delete_moves_maps_to_uncategorized test_server.RepositoryTests.test_concept_map_rejects_invalid_or_oversized_data test_server.RepositoryTests.test_fixed_baseline_data_can_be_copied_and_loaded_independently` | 通过，5 项 | 既有约束、分类、回收站及旧 JSON 样本 |
| 2026-09-16 | RF-103 | `python -m unittest -v` | 通过，58 项 | 完整回归 |
| 2026-09-16 | RF-103 | `python -m py_compile server.py workbench/__init__.py workbench/markdown_io.py workbench/paths.py workbench/external_editor.py workbench/concept_maps.py test_server.py test_http.py test_markdown.py test_paths.py test_concept_maps.py` | 通过 | 新仓储模块与测试已纳入 |
| 2026-09-16 | RF-103 | `node --check app.js`、`node --check concept-map.js` | 通过 | 无输出；前端未修改 |
| 2026-09-16 | RF-103 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-104 | `python -m unittest -v test_assets` | 通过，3 项 | 组合仓储、索引隔离、重名/路径和中断流清理 |
| 2026-09-16 | RF-104 | `python -m unittest -v test_server.RepositoryTests.test_project_record_search_update_and_trash test_server.RepositoryTests.test_global_idea_is_allowed test_server.RepositoryTests.test_project_independent_assets_can_be_uploaded_and_categorized test_server.RepositoryTests.test_assets_support_unlimited_stream_batch_category_and_confirmable_delete_backend test_server.RepositoryTests.test_pasted_image_upload_can_register_without_replacing_unsaved_body test_server.RepositoryTests.test_reference_targets_include_documents_record_bodies_and_attachments` | 通过，6 项 | 记录/项目附件、10MB+ 流、批量、孤儿、引用和导出 |
| 2026-09-16 | RF-104 | `python -m unittest -v` | 通过，61 项 | 完整回归 |
| 2026-09-16 | RF-104 | `python -m py_compile server.py workbench/__init__.py workbench/markdown_io.py workbench/paths.py workbench/external_editor.py workbench/concept_maps.py workbench/assets.py test_server.py test_http.py test_markdown.py test_paths.py test_concept_maps.py test_assets.py` | 通过 | 新附件模块与测试已纳入 |
| 2026-09-16 | RF-104 | `node --check app.js`、`node --check concept-map.js` | 通过 | 无输出；前端未修改 |
| 2026-09-16 | RF-104 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-105 | `python -m unittest -v test_documents` | 通过，2 项 | 验证组合仓储门面、旧版 `mode/order` 排序兼容迁移、空分类和重新实例化读取 |
| 2026-09-16 | RF-105 | `python -m unittest -v test_server.RepositoryTests.test_status_templates_and_workflows test_server.RepositoryTests.test_used_workflow_status_cannot_be_removed_and_rename_migrates_status test_server.RepositoryTests.test_document_backlinks_include_referencing_records_and_projects test_server.RepositoryTests.test_document_category_rename_migrates_documents_and_sorting test_server.RepositoryTests.test_document_category_delete_moves_documents_to_uncategorized test_server.RepositoryTests.test_document_can_open_in_external_markdown_editor` | 通过，6 项 | 状态/工作流、分类同步、反向链接和兼容 patch 路径 |
| 2026-09-16 | RF-105 | `python -m unittest -v` | 通过，63 项 | 完整回归，包含 HTTP 集成测试 |
| 2026-09-16 | RF-105 | `python -m py_compile`（根目录及 `workbench/` 全部 Python 文件） | 通过 | 新配置、文档仓储及测试已纳入 |
| 2026-09-16 | RF-105 | `node --check app.js`、`node --check concept-map.js` | 通过 | 无输出；前端未修改 |
| 2026-09-16 | RF-105 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-106 | `python -m unittest -v test_records` | 通过，2 项 | 验证项目/记录组合仓储、缓存兼容别名、信息字段与历史重载、项目和记录可恢复删除 |
| 2026-09-16 | RF-106 | `python -m unittest -v test_server.RepositoryTests.test_project_record_search_update_and_trash test_server.RepositoryTests.test_record_cache_reuses_parse_and_detects_external_edits test_server.RepositoryTests.test_record_ids_stay_unique_during_concurrent_creation test_server.RepositoryTests.test_information_record_uses_structured_fields_without_status test_server.RepositoryTests.test_information_fields_store_multiple_multiline_commands test_server.RepositoryTests.test_convert_record_moves_type_without_resetting_status test_server.RepositoryTests.test_record_can_open_in_external_markdown_editor test_server.RepositoryTests.test_trash_restore_and_permanent_delete test_server.RepositoryTests.test_trash_batch_restore_and_permanent_delete test_server.RepositoryTests.test_reference_targets_include_documents_record_bodies_and_attachments` | 通过，10 项 | 覆盖 `server.load_markdown` 动态 patch、外部修改、附件引用和编辑器兼容路径 |
| 2026-09-16 | RF-106 | `python -m unittest -v` | 通过，65 项 | 完整回归，包含 HTTP 集成测试 |
| 2026-09-16 | RF-106 | `python -m py_compile`（根目录及 `workbench/` 全部 Python 文件） | 通过 | 新项目、记录仓储及测试已纳入 |
| 2026-09-16 | RF-106 | `node --check app.js`、`node --check concept-map.js` | 通过 | 无输出；前端未修改 |
| 2026-09-16 | RF-106 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-107 | `python -m unittest -v test_http` | 通过，8 项 | 独立模块兼容、成功、400/404/409/500、静态文件、ZIP 和原始流上传/下载 |
| 2026-09-16 | RF-107 | `python -m unittest -v` | 通过，68 项 | 完整仓储与 HTTP 回归 |
| 2026-09-16 | RF-107 | `python -m py_compile`（根目录及 `workbench/` 全部 Python 文件） | 通过 | 新 HTTP 模块已纳入 |
| 2026-09-16 | RF-107 | `node --check app.js`、`node --check concept-map.js` | 通过 | 无输出；前端未修改 |
| 2026-09-16 | RF-107 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-108 | `python -m unittest -v test_startup` | 通过，3 项 | 独立仓储入口、完整 CLI 参数和自定义目录/演示数据/替换/打开装配 |
| 2026-09-16 | RF-108 | `python -m unittest -v test_markdown.MarkdownContractTests.test_server_keeps_compatible_markdown_helper_exports test_server.RepositoryTests.test_record_cache_reuses_parse_and_detects_external_edits test_server.RepositoryTests.test_record_can_open_in_external_markdown_editor test_http.HTTPIntegrationTests.test_server_keeps_compatible_extracted_http_exports` | 通过，4 项 | 旧 `server` 导入与动态 patch 点保持有效 |
| 2026-09-16 | RF-108 | `python -m unittest -v` | 通过，71 项 | 阶段 1 完整门禁 |
| 2026-09-16 | RF-108 | `python -m py_compile`（根目录及 `workbench/` 全部 Python 文件） | 通过 | 新仓储门面与启动测试已纳入 |
| 2026-09-16 | RF-108 | `python server.py --help` | 通过 | 原主机、端口、数据目录、演示数据、打开和替换参数均存在 |
| 2026-09-16 | RF-108 | `node --check app.js`、`node --check concept-map.js` | 通过 | 无输出；前端未修改 |
| 2026-09-16 | RF-108 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-201 | `node test_markdown_core.js` | 通过 | 固定标题/表格输出、转义管道、引用解析与转义、语言别名、颜色、代码高亮及纯文本解析 |
| 2026-09-16 | RF-201 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-16 | RF-201 | `python -m py_compile`（根目录及 `workbench/` 全部 Python 文件） | 通过 | 无输出 |
| 2026-09-16 | RF-201 | `node --check`（根目录及 `js/` 全部 JavaScript 文件） | 通过 | 新纯模块、主应用、概念图与专项测试均无语法错误 |
| 2026-09-16 | RF-201 | 临时数据浏览器验收 | 通过 | 记录与知识库渲染正常；表格对齐和引用块正常；浅色/深色、桌面/480px 窄屏无控制台错误 |
| 2026-09-16 | RF-201 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-202 | `node test_document_model.js`、`node test_markdown_core.js` | 通过 | 稳定接口、model → Markdown、分隔线渲染与纯 Markdown 契约通过 |
| 2026-09-16 | RF-202 | 浏览器打开 `test_document_model.html` | 通过 | 页面显示 PASS；Markdown → DOM → model → Markdown 覆盖全部既有结构块，任务字段和块 ID 校验通过 |
| 2026-09-16 | RF-202 | 临时数据浏览器验收 | 通过 | 记录可视化编辑器与知识库阅读/编辑模式均正常加载，分隔线和任务列表保留，控制台无错误 |
| 2026-09-16 | RF-202 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-16 | RF-202 | `python -m py_compile`（根目录及 `workbench/` 全部 Python 文件） | 通过 | 无输出 |
| 2026-09-16 | RF-202 | `node --check`（根目录及 `js/` 全部 JavaScript 文件） | 通过 | 新文档模型模块和契约测试均纳入 |
| 2026-09-16 | RF-202 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-203 | `node test_editor_blocks.js`、既有两个 Node 契约 | 通过 | 无浏览器入口、文档模型和 Markdown 契约均通过 |
| 2026-09-16 | RF-203 | 浏览器打开 `test_editor_blocks.html` | 通过 | 页面显示 PASS；覆盖选区/光标、普通/编号/任务列表、引用、代码、引用块、表格和分隔线 |
| 2026-09-16 | RF-203 | 临时数据浏览器验收 | 通过 | 记录编辑器插入任务项、知识库编辑器切换引用块并进入 dirty/保存链路；控制台无错误 |
| 2026-09-16 | RF-203 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-16 | RF-203 | `python -m py_compile`（根目录及 `workbench/` 全部 Python 文件） | 通过 | 无输出 |
| 2026-09-16 | RF-203 | `node --check`（根目录及 `js/` 全部 JavaScript 文件） | 通过 | 新选区、结构块和浏览器契约脚本均纳入 |
| 2026-09-16 | RF-203 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-204 | `node test_editor_blocks.js`、既有两个 Node 契约 | 通过 | 共享宿主接口、文档模型和 Markdown 契约均通过 |
| 2026-09-16 | RF-204 | 浏览器打开 `test_editor_blocks.html` | 通过 | 页面显示 `PASS shared-host,round-trip,table-tail,...`；两个宿主输出一致，保存重开无损，表格后输入不会丢失 |
| 2026-09-16 | RF-204 | 临时数据浏览器验收 | 通过 | 记录与知识库对同一 Markdown 分别追加内容、自动保存、关闭并重开；API 重读正文完全一致，控制台无错误 |
| 2026-09-16 | RF-204 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-16 | RF-204 | `python -m py_compile`（根目录及 `workbench/` 全部 Python 文件） | 通过 | 无输出 |
| 2026-09-16 | RF-204 | `node --check`（根目录及 `js/` 全部 JavaScript 文件） | 通过 | 新共享宿主、主应用及全部契约脚本均纳入 |
| 2026-09-16 | RF-204 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-205 | 三个 Node 契约与两个 Edge DOM 契约页 | 通过 | 固定样本覆盖结构块、行内格式、受控 HTML、JavaScript/Python/Shell、任务状态、三向表格对齐、转义与双宿主往返；两个页面均显示 `data-test-result="passed"` |
| 2026-09-16 | RF-205 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-16 | RF-205 | `python -m py_compile`（全部 Python 文件）与 `node --check`（全部 JavaScript 文件） | 通过 | 无语法错误 |
| 2026-09-16 | RF-205 | `git diff --check` | 通过 | 仅有 Windows LF/CRLF 提示，无内容错误 |
| 2026-09-16 | RF-205 | 临时数据可视化保存/外部修改矩阵 | 未执行 | Computer Use 浏览器服务连续重试和重置后仍返回 `nodeRepl.fetch request failed`；未把未验证项目记为通过，工作项保持进行中 |
| 2026-09-16 | RF-205 | `node test_editor_workflows.js` | 通过 | 临时服务、临时数据和独立浏览器配置；覆盖记录/文档保存重开、刷新草稿、历史、两类外部修改、三类冲突决策和草稿清理，退出时清理全部临时目录 |
| 2026-09-16 | RF-301 | `node test_app_core.js` | 通过 | DOM 查询、安全转义/颜色适配、统一 API 成功与错误映射、对话框模块导出均通过 |
| 2026-09-16 | RF-301 | `node test_editor_workflows.js` | 通过 | 核心别名均指向 `window.Workbench` 唯一实现；toast、输入选项安全转义、概念图库和既有保存/冲突流程通过 |
| 2026-09-16 | RF-301 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-16 | RF-301 | `python -m py_compile`（全部 Python 文件）与 `node --check`（全部 JavaScript 文件） | 通过 | 三个核心模块及新增契约测试已纳入 |
| 2026-09-16 | RF-301 | 三个既有 Node 编辑器契约与 `git diff --check` | 通过 | Markdown、文档模型、编辑器宿主及差异检查无回归 |
| 2026-09-16 | RF-302 | `node test_state.js`、`node test_app_core.js` 及三个既有 Node 编辑器契约 | 通过 | 四类状态访问器、独立请求通道、失效令牌和全部核心/编辑器契约无回归 |
| 2026-09-16 | RF-302 | `node test_editor_workflows.js` | 通过 | 人为延迟先发响应验证记录详情、项目附件和文档保存均由后发请求胜出；既有保存、重开、草稿、历史、外部修改与冲突流程继续通过 |
| 2026-09-16 | RF-302 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-16 | RF-302 | `python -m py_compile`（22 个 Python 文件）、`node --check`（17 个 JavaScript 文件）与 `git diff --check` | 通过 | 新状态模块、主应用和测试全部纳入；仅有 Git 行尾转换提示 |
| 2026-09-16 | RF-303 | `node test_management_features.js` 及五个既有 Node 契约 | 通过 | 搜索组合筛选、模块导出、状态边界、核心服务和编辑器契约无回归 |
| 2026-09-16 | RF-303 | `node test_editor_workflows.js` | 通过 | 连续重绘后搜索/回收站/使用统计各保持单一监听器；回收站单次选择、搜索打开、使用统计明细/记录/返回总览及全部既有编辑器流程通过；临时目录清理重试后退出正常 |
| 2026-09-16 | RF-303 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-16 | RF-303 | `python -m py_compile`（22 个 Python 文件）、`node --check`（21 个 JavaScript 文件）与 `git diff --check` | 通过 | 三个功能模块、模块契约、主应用及浏览器测试全部纳入；仅有 Git 行尾转换提示 |
| 2026-09-17 | RF-304 | `node test_home_project_features.js` 及六个既有 Node 契约 | 通过 | 旧首页布局迁移、归一化/保存、分栏回收、标签页筛选、六种排序、手动顺序合并和附件筛选通过；核心与编辑器契约无回归 |
| 2026-09-17 | RF-304 | `node test_editor_workflows.js` | 通过 | 首页分栏写入后重读保持；记录与状态列顺序写入服务端后刷新仍保持；RF-302/303 竞态、单监听器、使用统计导航及全部编辑器流程继续通过 |
| 2026-09-17 | RF-304 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-17 | RF-304 | `python -m py_compile`（22 个 Python 文件）、`node --check`（24 个 JavaScript 文件）与 `git diff --check` | 通过 | 两个功能模块、模块契约、主应用和浏览器测试全部纳入；仅有 Git 行尾转换提示 |
| 2026-09-17 | RF-305 | `node test_record_knowledge_features.js` 及八个既有 Node 契约 | 通过 | 草稿存储容错、会话状态、差异合并、空分类、分类/文档排序、旧排序格式、导入解析和安全导出名通过；核心与编辑器契约无回归 |
| 2026-09-17 | RF-305 | `node test_editor_workflows.js` | 通过 | 记录关闭/切换、文档关闭、保存失败重试、刷新恢复、历史、外部修改、冲突选择、异步竞态和既有管理/首页/项目流程均通过 |
| 2026-09-17 | RF-305 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-17 | RF-305 | `python -m py_compile`（22 个 Python 文件）、`node --check`（28 个 JavaScript 文件）与 `git diff --check` | 通过 | 三个功能模块、模块契约、主应用和浏览器测试全部纳入；仅有 Git 行尾转换提示 |
| 2026-09-17 | RF-306 | `node test_concept_map_frontend.js` 及其余九个 Node 契约 | 通过 | 模块独立加载、依赖接口校验、状态边界、图库渲染及全部既有前端契约无回归 |
| 2026-09-17 | RF-306 | `node test_editor_workflows.js` | 通过 | 概念图库加载、打开、标题修改、自动保存 flush 和服务端重读通过；记录/文档保存、草稿、历史、外部修改、冲突及既有功能矩阵继续通过 |
| 2026-09-17 | RF-306 | `python -m unittest -v` | 通过，71 项 | 后端数据、概念图仓储、HTTP 和启动行为完整回归 |
| 2026-09-17 | RF-306 | `python -m py_compile`（全部 Python 文件）、`node --check`（全部 JavaScript 文件）与 `git diff --check` | 通过 | 新契约测试、模块脚本、装配入口和缓存版本均纳入；仅有 Git 行尾转换提示 |
| 2026-09-17 | RF-307 | `node test_frontend_entry.js` 及其余十个 Node 契约 | 通过 | 导航兼容、页面解析、单次启动、生命周期绑定及全部现有前端契约无回归 |
| 2026-09-17 | RF-307 | `node test_editor_workflows.js` | 通过 | 页面启动后完整保存、失败重试、关闭/切换、刷新草稿、历史、外部修改、冲突和概念图流程继续通过 |
| 2026-09-17 | RF-307 | `python -m unittest -v` | 通过，71 项 | 后端数据、仓储、HTTP 和启动行为完整回归 |
| 2026-09-17 | RF-307 | `python -m py_compile`（全部 Python 文件）、`node --check`（全部 JavaScript 文件）与 `git diff --check` | 通过 | 两个核心模块、新入口契约、装配代码和缓存版本均纳入；仅有 Git 行尾转换提示 |
| 2026-09-17 | RF-401 | `node visual_baseline.js`（固定样本） | 通过，32 张本地截图 | 四套环境各覆盖首页、项目、记录、交互状态、知识库、文档、概念图和搜索，关键文本/结构断言通过 |
| 2026-09-17 | RF-401 | `WORKBENCH_BASELINE_EMPTY=1 node visual_baseline.js` | 通过，4 张本地截图 | 全新临时目录的浅色/深色 × 桌面/窄屏空状态和主要创建入口可用 |
| 2026-09-17 | RF-401 | `node test_editor_workflows.js`、`python -m unittest -v`、全部语法检查和 `git diff --check` | 通过 | 真实浏览器交互矩阵、71 项后端测试和基础门禁无回归；截图清理后无生成物入库 |
| 2026-09-17 | RF-402 | `node visual_baseline.js`（修改前后固定样本） | 通过，各 32 张本地截图 | 四套环境的页面、对话框、hover/focus/disabled/error 状态结构断言通过；稳定截图像素一致，时序差异图目视无回归 |
| 2026-09-17 | RF-402 | 全部 12 个 `test*.js` | 通过 | 新增样式令牌/基础组件契约；真实浏览器保存、刷新、草稿、历史、外部修改和冲突矩阵继续通过 |
| 2026-09-17 | RF-402 | `python -m unittest -v`、全部 Python/JavaScript 语法检查与 `git diff --check` | 通过 | 71 项后端测试、22 个 Python 文件和 34 个 JavaScript 文件无回归；仅有 Git 行尾转换提示 |
| 2026-09-17 | RF-403 | 原 `styles.css` 与十个新文件规则集合对比 | 通过，633/633 条 | 忽略空行和 RF-403 文件头后无缺失、重复或额外规则；各文件保持所归档规则的原始相对顺序 |
| 2026-09-17 | RF-403 | `node visual_baseline.js`（拆分前后固定样本） | 通过，各 32 张本地截图 | 浅色/深色 × 桌面/窄屏关键页面、对话框、编辑器和交互态结构断言通过，成对目视无非预期级联差异 |
| 2026-09-17 | RF-403 | 全部 12 个 `test*.js`、`python -m unittest -v`、全部语法检查与 `git diff --check` | 通过 | 加载顺序、块平衡、动态类名/模板引用审计、真实浏览器工作流、71 项后端测试、22 个 Python 和 34 个 JavaScript 文件无回归 |
| 2026-09-17 | RF-501 | `node test_resource_refresh.js`、`python -m unittest -v test_http` | 通过 | 新增/修改/删除差异、有序合并、记录按 ID 摘要与知识库签名接口通过；完整后端回归共 72 项 |
| 2026-09-17 | RF-501 | 全部 13 个 `test*.js`（含 `test_editor_workflows.js`） | 通过 | 真实浏览器确认记录/文档仅下载签名变化条目，干净编辑自动同步，脏编辑保留并提示冲突；既有保存、草稿、历史和竞态矩阵无回归 |
| 2026-09-17 | RF-501 | `python -m py_compile`（22 个 Python 文件）、`node --check`（36 个 JavaScript 文件）与 `git diff --check` | 通过 | 新仓储/API、刷新模块、装配入口和测试全部纳入；仅有 Git 行尾转换提示 |
| 2026-09-17 | RF-502 | `python -m unittest -v test_persistence` | 通过，7 项 | 精确内容、并发写入、fsync/replace 失败清理、记录/配置旧文件保留与重读、生产代码直接覆盖审计均通过 |
| 2026-09-17 | RF-502 | `python -m unittest -v`、全部 13 个 `test*.js` | 通过，79 项 Python | 仓储、HTTP、路径、导出与真实浏览器保存/重开/草稿/外部修改矩阵无回归 |
| 2026-09-17 | RF-502 | `python -m py_compile`（24 个 Python 文件）、`node --check`（36 个 JavaScript 文件）与 `git diff --check` | 通过 | 新持久化模块、全部迁移调用方和专项测试均纳入；仅有 Git 行尾转换提示 |
| 2026-09-17 | RF-503 | `python -m unittest -v test_security test_assets test_records test_http test_documents test_paths` | 通过，32 项 | 恶意/重复/损坏 ZIP、路径式/保留文件名、导入扩展名、分类控制字符、附件和回收站篡改、HTTP 长度/截断正文与 JSON 形状均被拒绝；合法字节流与重名附件保持 |
| 2026-09-17 | RF-503 | `python -m unittest -v`、全部 13 个 `test*.js` | 通过，90 项 Python | 仓储、HTTP、导入导出与真实浏览器保存/刷新/草稿/外部修改矩阵无回归；本项无前端或视觉变化，无需新增视觉验收 |
| 2026-09-17 | RF-503 | `python -m py_compile`（26 个 Python 文件）、`node --check`（36 个 JavaScript 文件）与 `git diff --check` | 通过 | 新安全模块、专项测试及所有调用方均纳入；仅有 Git 行尾转换提示 |
| 2026-09-17 | RF-504 | `python performance_acceptance.py` | 通过 | 系统临时目录内完成 12 项目、1200 记录、160 文档、120 附件、长 Markdown、500 节点/499 边图的生成、磁盘重读、ZIP CRC、HTTP 和无头 Edge 验收；结果详见 `docs/PERFORMANCE_ACCEPTANCE.md` |
| 2026-09-17 | RF-504 | `python -m unittest -v`、全部 13 个 `test*.js` | 通过，90 项 Python | 全部仓储/HTTP 回归及真实浏览器保存、草稿、历史、增量刷新、外部修改和冲突矩阵无回归 |
| 2026-09-17 | RF-504 | `python -m py_compile`（27 个 Python 文件）、`node --check`（37 个 JavaScript 文件）与 `git diff --check` | 通过 | 性能编排、浏览器探针和现有全部源文件均纳入；仅有 Git 行尾转换提示 |

## 6. 决策记录

关键架构选择使用 `DEC-*` 编号。修改已有决策时追加新记录，不覆盖原记录。

| ID | 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- | --- |
| DEC-001 | 2026-09-16 | 采用渐进式重构，不推倒重写 | 当前功能和数据契约已经复杂，全面重写的数据兼容风险过高 | 所有阶段保持可运行、可回滚 |
| DEC-002 | 2026-09-16 | 第一轮不引入框架、打包器或第三方后端框架 | 先解决职责和测试问题，避免同时改变技术栈 | 继续使用 Python 标准库和原生浏览器 API |
| DEC-003 | 2026-09-16 | `Repository` 在后端拆分期间作为兼容门面 | 降低 HTTP、测试和领域模块同时变化的风险 | 领域实现可移动，但公开行为先保持稳定 |
| DEC-004 | 2026-09-16 | 重构状态只以本台账为准 | 防止计划、提交说明和实际完成情况相互矛盾 | 每个工作项开始和结束都必须更新本文件 |
| DEC-005 | 2026-09-16 | 前端先使用 `window.Workbench` 显式命名空间 | 当前脚本依赖全局加载顺序，直接切 ES Modules 会扩大变更面 | 模块边界稳定后再单独评估 ESM |
| DEC-006 | 2026-09-16 | 后端提取期间由 `server.py` 兼容导出已移动的公共辅助函数 | 现有测试和潜在本地调用方可能仍从 `server` 导入或 patch 这些名称 | 新模块成为实现位置，旧导入路径在相关调用方迁移前继续有效 |
| DEC-007 | 2026-09-16 | 路径模块通过当前仓储实例的类型创建迁移后仓储，编辑器模块通过检测器参数接受环境能力 | `paths.py` 和 `external_editor.py` 不应反向导入集中式 `server.py`，同时旧 patch 路径需要继续工作 | 消除循环依赖；`server.py` 编辑器兼容门面仍可注入测试检测结果 |
| DEC-008 | 2026-09-16 | 领域仓储拆分采用组合对象，`Repository` 保留委托门面 | 避免新模块继承集中式仓储或反向导入 `server.py`，同时维持 HTTP 和现有测试调用 | 概念图实现独立，外部仍使用原 `Repository` 契约；后续领域拆分沿用此模式 |
| DEC-009 | 2026-09-16 | `server.Repository` 作为提取后门面的轻量装配子类保留 | 既要让 `workbench.repository.Repository` 可独立使用，又要兼容本地调用和测试对 `server.load_markdown`、外部编辑器入口的动态 patch | 启动文件不再承载仓储实现；旧入口继续有效，移除兼容层需另行评估 |
| DEC-010 | 2026-09-16 | 纯 Markdown 模块通过回调接收引用目标、引用渲染和图片渲染能力 | 引用与附件 URL 依赖当前应用状态，直接读取全局对象会破坏纯函数边界并妨碍无浏览器测试 | `js/editor/markdown.js` 可独立测试和复用；`app.js` 负责把当前状态适配为回调，现有输出保持不变 |
| DEC-011 | 2026-09-16 | 文档模型以 `render(editor, markdown, options)`、`normalize(editor)` 和 `serialize(editor)` 作为稳定入口 | 后续结构块操作和两个编辑器需要共享同一 DOM/模型边界，同时保留引用与附件的应用状态适配 | RF-203～RF-204 依赖统一入口，不再各自实现 DOM 序列化；底层辅助函数仅用于专项测试和渐进迁移 |
| DEC-012 | 2026-09-16 | 结构块与选区模块只接收 editor、selection/range、配置和 `onChange` | 记录与知识库分别维护保存、草稿和工具栏状态，共享模块若读取这些全局状态会重新形成隐式耦合 | 两个编辑器复用同一操作实现；应用层负责保存 range、选择语言和触发各自保存链路，RF-204 可在此边界上统一控制器 |
| DEC-013 | 2026-09-16 | 记录和知识库各持有一个 `editorHost` 实例，共享行为但不共享业务状态 | 两类编辑器需要相同的渲染、模型、选区和结构操作，同时必须保留各自的草稿、保存、冲突、元数据和阅读模式 | `app.js` 只为宿主注入 editor、渲染回调和对应 `onChange`；后续编辑器能力从宿主扩展，不再新增平行实现 |
| DEC-014 | 2026-09-16 | 编辑器工作流验收使用 Node 标准库和系统 Edge DevTools 协议 | Computer Use 服务不可用，纯 DOM 契约又无法覆盖刷新、轮询、API 和 `localStorage` 的组合行为；项目禁止引入运行时依赖和构建链 | 新测试可重复执行真实浏览器流程且不增加第三方包；缺少 Edge/Chrome 时可用 `WORKBENCH_BROWSER_PATH` 指定兼容浏览器 |
| DEC-015 | 2026-09-16 | 前端核心能力分别暴露为 `Workbench.dom`、`Workbench.api` 和 `Workbench.dialogs`，`app.js` 只保留兼容词法别名 | 主应用与概念图仍通过经典脚本共享名称，直接改为 ES Modules 或一次性迁移概念图会扩大 RF-301 范围 | API 和对话框各只有一个实现；后续模块可直接依赖显式命名空间，RF-306 再移除概念图的隐式依赖 |
| DEC-016 | 2026-09-16 | `Workbench.appState` 以访问器把现有词法变量分组，并由单一请求注册表按通道和身份判定异步结果是否仍有效 | 一次性把大型 `app.js` 的全部读写点改为属性访问会把 RF-303～RF-306 混入当前工作项；只增加零同步的镜像对象又无法成为可靠边界 | 现有代码和数据行为保持不变，后续模块可直接读写 `serverData`、`uiState`、`editorState`、`draftState`；异步落点统一拒绝过期响应，待入口精简时再移除兼容变量 |
| DEC-017 | 2026-09-16 | 搜索、回收站和使用统计分别以单实例控制器绑定稳定容器，主应用只注入 API、状态查询和导航回调 | 三块功能拥有独立状态且页面内容会反复替换，继续在全局事件分支中维护会增加重复绑定和跨功能状态污染风险 | 重绘只替换内容，不重新注册监听器；搜索和回收站状态不再占用 `app.js` 全局变量，使用统计的返回上下文由管理控制器持有 |
| DEC-018 | 2026-09-17 | 首页和项目视图先提取纯数据模型与持久化顺序边界，HTML 生成继续由主应用适配共享记录组件 | 首页卡片、看板、信息卡和附件仍依赖记录/编辑器共享辅助函数，一次性搬迁渲染会与 RF-305 重叠；布局兼容和排序写回可先独立验证 | `Workbench.home` 成为首页布局事实入口，`Workbench.projectView` 统一标签页/附件筛选、排序与可见顺序合并；RF-307 可在稳定边界上继续精简渲染入口 |
| DEC-019 | 2026-09-17 | 记录和知识库各使用一个共享会话工厂创建的独立会话，冲突与知识库数据模型通过注入的 DOM/API 适配继续由主应用编排 | 两类编辑器需要复用草稿容错和计时规则，但 dirty、saving、草稿键和并发身份不能互相污染；分类渲染和冲突按钮仍依赖现有页面骨架 | 会话状态不再由 `app.js` 松散变量持有；原 localStorage/API/DOM 契约保持，RF-307 可基于显式模块继续精简入口 |
| DEC-020 | 2026-09-17 | 概念图以 `Workbench.conceptMap.create(...)` 工厂接收 DOM、API、对话框和 `appState`，只公开图库渲染、打开和保存 flush 控制器 | 经典脚本原先直接读取 `app.js` 的可变词法名称，加载顺序和隐式共享状态使模块无法独立验证 | 概念图实现不再依赖未声明的应用变量；共享状态仍由现有 `appState` 访问器保持单一事实源，RF-307 可继续收敛应用装配入口 |
| DEC-021 | 2026-09-17 | 导航持久化与应用生命周期分别由 `Workbench.navigation` 和 `Workbench.application` 控制器负责，`app.js` 注入浏览器能力和业务回调 | 导航兼容规则、窗口监听器与业务渲染混在入口中，既难独立验证，也可能在后续重装配时重复绑定 | `app.js` 保留 DOM 适配和跨功能协调；导航键兼容、页面合法化和启动幂等具有独立契约，后续功能模块不再自行绑定窗口生命周期 |
| DEC-022 | 2026-09-17 | 全局主题、字号和基础控件令牌只在 `styles.css` 文件首部定义，功能组件只保留自身差异声明 | 后置补丁重复定义最终值会让后续拆分依赖隐含级联顺序，且焦点和禁用状态容易在移动规则时丢失 | RF-403 拆分时可按明确令牌边界移动功能样式；`test_styles.js` 持续检查单一全局/深色令牌块和基础交互状态 |
| DEC-023 | 2026-09-17 | 拆分后的样式按“令牌 → 基础 → 通用组件 → 布局 → 记录 → 管理 → 编辑器 → 知识库 → 概念图 → 响应式”加载，并由契约锁定 | 文件名的展示顺序不能替代真实级联依赖；按规则首次依赖和最终计算样式调整顺序，才能在功能归档后保持现有视觉 | `index.html` 是唯一加载入口；新增功能样式进入对应文件，纯行为类名必须在 `test_styles.js` 显式登记；RF-404 在末尾响应式边界内继续整理 |
| DEC-024 | 2026-09-17 | 所有媒体查询只保存在 `css/responsive.css`，`max-width` 条件按数值从宽到窄且每个条件只出现一次 | 分散在功能文件和后置补丁中的同断点规则会隐藏真实胜序，增加拆分后回归风险 | 样式契约拒绝功能文件内媒体查询、重复条件和断点乱序；视觉脚本可按关键宽度矩阵检查页面与文档工作区的横向溢出 |
| DEC-025 | 2026-09-17 | 记录和知识库文档轮询先读取轻量签名，由 `Workbench.resourceRefresh` 计算变化集合并按签名顺序合并；同一资源的全量刷新与轮询共用请求通道 | 全量正文/摘要传输随数据规模增长，独立轮询通道又可能让旧响应覆盖较新的手动刷新；编辑器本地状态仍需独立于列表数据保护 | 未变化资源保留原对象且不重新下载，删除项及时移除，旧响应无法落地；打开资源仅在自身签名变化时重载或进入冲突流程 |
| DEC-026 | 2026-09-17 | 所有覆盖式持久化统一经 `workbench.persistence` 在目标同目录创建唯一临时文件，完成 flush/fsync 后使用 `os.replace`；流式上传只写唯一新文件，因此保留流式实现 | 静态 `.tmp` 名称无法安全并发，多处直接覆盖在中断时可能留下半写文件；附件上传若改为内存字节写会破坏大文件流式契约 | Markdown、JSON、机器配置和导出包失败时保留旧文件并清理临时文件；生产代码直接 `write_text` 由契约拒绝，后续新增覆盖写必须复用统一工具 |
| DEC-027 | 2026-09-17 | 文件名、分类、ZIP 成员和归档结构统一由 `workbench.security` 校验，磁盘索引中的路径在每次读取、删除或恢复前仍须重新限定到领域根目录 | 仅在上传入口取 basename 或依赖前端限制不能防止篡改索引、跨平台保留名、归档逃逸和符号链接越界；导出也需要验证生成结果 | 正常文件和数据格式不变；非法新输入明确失败，损坏旧索引不会访问领域根外文件；没有 ZIP 导入能力，若未来新增必须复用归档校验并设置条目/解压大小限制 |
| DEC-028 | 2026-09-17 | 大数据验收采用显式运行的临时样本编排，并记录耗时而不把机器相关毫秒数写成单元测试阈值；仅对 30 秒内完成、事件循环恢复和磁盘数据完整性设硬门禁 | 真实原子写/fsync 的 1200 条样本生成约需数分钟，挂入快速回归会降低日常测试可用性；不同机器绝对耗时不可直接比较 | 发布前可重复运行同一规模并观察数量级回退；脚本结束清理样本，不接触真实数据，也不增加运行时依赖 |

## 7. 风险记录

| ID | 风险 | 可能影响 | 缓解措施 | 状态 |
| --- | --- | --- | --- | --- |
| RISK-001 | Markdown 轻量解析器不是完整 YAML | 新字段可能无法无损往返 | 先完成 RF-003；新增类型必须提供兼容样本 | 开放 |
| RISK-002 | 编辑器依赖浏览器生成的 DOM | 拆分后可能出现结构块嵌套或丢格式 | RF-201～RF-203 已完成；固定往返与结构操作浏览器契约持续作为门禁 | 已缓解 |
| RISK-003 | `app.js` 大量全局状态和集中事件 | 移动代码可能产生重复绑定或异步覆盖 | 先建立状态边界和请求身份保护 | 开放 |
| RISK-004 | CSS 存在后置覆盖 | 拆分顺序变化可能产生视觉回归 | RF-401 四套基线、RF-402 样式契约和修改前后截图对比持续作为门禁 | 开放 |
| RISK-005 | 自动测试集中在仓储层 | HTTP 和浏览器回归可能漏检 | RF-002 HTTP 集成测试和 RF-205 真实浏览器工作流现已成为门禁 | 已缓解 |
| RISK-006 | 真实数据包含不可预期旧格式 | 固定测试样本不能覆盖全部用户文件 | 保持宽松兼容读取，禁止强制批量迁移 | 开放 |

## 8. 待评估事项

以下内容尚未进入正式工作项，实施前需要决策：

| ID | 事项 | 触发条件 | 处理状态 |
| --- | --- | --- | --- |
| EVAL-001 | 是否在模块稳定后切换原生 ES Modules | RF-307 完成后 | 待评估 |
| EVAL-002 | 是否引入浏览器自动化测试依赖 | RF-205 手工矩阵维护成本过高时 | 已评估：采用 Node 标准库 + 系统浏览器 DevTools，不引入第三方依赖 |
| EVAL-003 | 是否把测试移动到 `tests/` 包 | 新增多个测试文件后发现根目录难以维护 | 待评估 |
| EVAL-004 | 是否统一所有 Markdown/JSON 原子写工具 | RF-502 实施前 | 已评估：采用同目录唯一临时文件、fsync 与 `os.replace` 的单一工具，流式新文件上传除外 |

## 9. 工作项记录模板

新增执行日志时复制以下字段，不需要为每个工作项创建单独文件：

```text
工作项：RF-XXX
状态：待开始 / 进行中 / 受阻 / 已完成 / 已取消
开始日期：YYYY-MM-DD
完成日期：YYYY-MM-DD
范围：
修改文件：
数据/API兼容影响：
自动验证：
手工验证：
关键决策：DEC-XXX（如有）
风险变化：RISK-XXX（如有）
遗留问题：
下一步：
```
