# 固定行为样本

`baseline-data/` 是不含个人数据的只读测试基线，用于重构前后比较仓储和 UI 行为。

使用时必须先复制到一次性目录，禁止直接启动或修改本目录中的样本：

```powershell
$testData = Join-Path $env:TEMP ("workbench-baseline-" + [guid]::NewGuid())
Copy-Item -Recurse test-fixtures/baseline-data $testData
python server.py --data-dir $testData --port 4174
```

样本有意覆盖以下兼容契约：

- 项目、问题、待办、历史 `idea` 和结构化信息；
- 旧版 Python 字典字符串形式的 `info_fields`，包含多行、引号和空格；
- 记录到记录、记录到知识库文档的稳定 `[[ID]]` 引用；
- 知识库分类顺序、分类内顺序和一个持久化空分类；
- 概念图版本、概念节点、连接短语、箭头和视口；
- Unicode 标题、标签和正文。

`config/settings.json`、`.workbench-*.json`、历史、回收站和附件均不纳入固定样本，避免机器路径、运行时写入或个人内容进入 Git。
