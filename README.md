# 本地工作台

本地工作台是一个零运行时依赖、单用户、本地优先的项目与知识管理应用。Python 标准库提供 HTTP 服务，浏览器端使用原生 HTML、CSS 和 JavaScript；项目、记录和知识库正文以 Markdown 为事实源。

## 快速开始

需要 Python 3.11 或更高版本，以及现代 Edge、Chrome 或其他兼容浏览器。在仓库目录运行：

```powershell
python server.py --seed-demo --open
```

默认地址为 `http://127.0.0.1:4173`。`--seed-demo` 只在没有项目时创建演示数据，后续可直接运行 `python server.py`。Windows 也可以双击 `start-workbench.cmd`。

```text
--host <地址>       默认 127.0.0.1
--port <端口>       默认 4173
--data-dir <目录>   本次使用指定数据目录
--seed-demo         空目录时创建演示数据
--open              启动后打开浏览器
--replace           安全替换使用相同数据目录的旧服务
```

## 数据与备份

默认数据位于仓库下的 `workbench-data/`，可在设置中迁移，也可临时指定：

```powershell
$env:WORKBENCH_DATA_DIR = 'D:\MyWorkbenchData'
python server.py
```

主要数据包括项目 README、问题、待办、结构化信息、知识库文档、概念图、附件、历史和回收站。删除默认移入 `.trash`；永久删除不可恢复。完整目录和兼容契约见 [数据格式](docs/DATA_FORMAT.md)。

工作台支持项目或完整 ZIP 备份。完整备份不会携带本机绝对路径设置；恢复时应解压到新目录，再通过 `--data-dir` 或设置页打开。当前应用不提供 ZIP 一键导入。

## 主要能力

- 项目、问题、待办及无状态结构化信息；旧 `idea` 文件兼容读取，但不再从 UI 新建。
- 自定义工作流、状态、标签、排序、归档、回收站、历史版本和全局搜索。
- 记录与知识库共享的可视化/Markdown 编辑器，支持草稿恢复、外部修改检测和三种冲突处理。
- 稳定 `[[ID]]` 引用、反向链接、附件拖放/粘贴、流式大附件上传与孤儿清理。
- 独立知识库分类、分类内排序、批量 Markdown 导入和选择性 ZIP 导出。
- JSON 概念图，支持 500 个节点、撤销重做、自动保存、视口和导出。
- 浅色/深色主题与桌面/窄屏响应式布局。

## 开发与维护

项目没有包管理器或构建步骤。架构和模块职责见 [架构说明](docs/ARCHITECTURE.md)，日常修改、测试和发布步骤见 [维护说明](docs/MAINTENANCE.md)。重构执行事实记录在 [进度台账](docs/REFACTORING_PROGRESS.md)。

```powershell
python -m unittest -v
node test_editor_workflows.js
python performance_acceptance.py
```

性能脚本只使用系统临时目录。默认规模与机器基线见 [大数据性能验收](docs/PERFORMANCE_ACCEPTANCE.md)。任何手工验收也应使用一次性目录，不要在真实 `workbench-data/` 上执行迁移、清理或压力测试。
