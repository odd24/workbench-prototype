# 数据格式

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

## JSON

- `config/*.json`：工作流、标签、分类和排序。状态/标签删除与重命名必须经过仓储迁移使用方。
- `concept-maps/CMAP-*.json`：版本、稳定节点/边 ID、节点类型、样式、箭头和视口；最多 500 个节点和 1000 条边。
- `.trash/index.json`：回收站令牌、原路径、回收路径和删除时间；恢复和永久删除都会重新验证路径。
- 项目附件索引与记录附件元数据是两套索引，不能混用。

所有覆盖式 Markdown/JSON 写入使用原子替换。流式附件只写新的唯一文件；上传中断会删除半成品。

## 历史、删除和兼容

记录更新前的版本写入 `history/<record-id>/`。项目、记录、文档和概念图删除默认移动到 `.trash`，只有明确永久删除才不可恢复。

旧文件采用兼容读取，不要求批量原地迁移。读取异常旧项时应跳过或降级，而不是清空整个配置。任何格式变更都必须增加旧格式与写入后重读测试。

## 本机设置与可移植备份

`config/settings.json` 保存当前绝对数据目录，只供本机运行使用；仓库根目录的 `.workbench-location.json`、`.workbench-export.json` 和 `.workbench-editor.json` 也属于本机配置。这些文件不得提交，也不进入可移植 ZIP。

完整 ZIP 包含业务 Markdown、概念图、可移植配置、附件和历史，但排除 `.trash`、符号链接及本机路径设置。项目 ZIP 只包含该项目目录。当前没有 ZIP 一键导入；恢复完整备份时解压到新目录并以 `--data-dir` 打开。
