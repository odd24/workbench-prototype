# 数据格式

## Agent 本机启动偏好（AG-107）

私人凭据根目录下的 `<workspace_id>/runtime.json` 保存 `schema_version: 1`、`workspace_id` 与布尔 `startup_enabled`。它不是业务数据，不进入可移植 ZIP 或 Git。缺失默认关闭；损坏或未知版本保留原文件，禁止自动启用并在管理状态返回提示。读取未初始化空间不创建身份。`--enable-agent`/`--disable-agent` 只覆盖本次运行，不写偏好；自定义 `--agent-config-dir` 对偏好和凭据使用同一根目录。

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

正式条目链接使用 `/?item=issue|document&itemId=<稳定ID>`，不包含正文、令牌或磁盘路径。回执保存相对 web_path；web_url 在 HTTP 返回时根据当前可信本机地址生成。旧回执缺少该字段时兼容展示链接，不重写其提交内容。
