# 维护与发布

## 修改入口

- 领域或持久化规则：修改对应 `workbench/*.py` 仓储，HTTP Handler 只做协议转换。
- 新增 API：同步仓储、`workbench/http_api.py`、前端调用、错误提示和 HTTP 测试。
- Markdown/编辑器：同时覆盖记录与知识库的渲染、模型、序列化、保存重开和阅读模式。
- 前端状态或请求：复用 `Workbench.appState` 与请求注册表，不新增平行全局状态。
- CSS：进入对应 `css/*.css`；媒体查询只进入 `responsive.css`，并更新 `index.html` 缓存版本。

兼容导出、旧格式读取、`localStorage` 键和 `window.Workbench` 名称都是接口。没有迁移方案和测试时不要删除或重命名。

## 自动检查

```powershell
python -m unittest -v

$pyFiles = @(Get-ChildItem -Recurse -File -Filter *.py | ForEach-Object FullName)
python -m py_compile @pyFiles

$jsFiles = @(Get-ChildItem -Recurse -File -Filter *.js | ForEach-Object FullName)
foreach ($file in $jsFiles) { node --check $file; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }

git diff --check
```

全部 Node 契约（其中编辑器工作流会启动临时服务和真实浏览器）：

```powershell
$tests = Get-ChildItem -File test*.js | Sort-Object Name
foreach ($test in $tests) { node $test.FullName; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
```

视觉验收使用 `visual_baseline.js`，清单见 [BASELINE_CHECKLIST.md](BASELINE_CHECKLIST.md)。编辑器矩阵见 [EDITOR_ACCEPTANCE_MATRIX.md](EDITOR_ACCEPTANCE_MATRIX.md)。大数据验收运行 `python performance_acceptance.py`，基线见 [PERFORMANCE_ACCEPTANCE.md](PERFORMANCE_ACCEPTANCE.md)。

## 安全的手工环境

```powershell
$testData = Join-Path $env:TEMP ("workbench-agent-" + [guid]::NewGuid())
python server.py --data-dir $testData --seed-demo --port 4174
```

不要对真实 `workbench-data/` 执行迁移、清理、删除、压力测试或视觉样本替换。测试完成后停止服务，再删除一次性目录。

## 发布检查

1. 查看 `git status --short`，确认没有用户数据、`.workbench-*.json`、日志、缓存、截图或导出包。
2. 运行完整 Python、Node、语法和差异门禁。
3. 涉及 UI 时完成浅色/深色、桌面/窄屏、空/多数据与交互状态验收。
4. 涉及编辑器时完成记录和知识库的可视化 → Markdown → 保存 → 重开，以及失败、草稿、外部修改和冲突路径。
5. 涉及数据时用新仓储实例重新读取；涉及导出时验证 ZIP CRC 和成员路径。
6. 确认 `index.html` 资源版本、README、架构/数据文档和进度台账同步。
7. 形成一笔可独立回滚、验证通过的本地提交。

## 已知后续方向

- `app.js` 仍包含页面 DOM 模板和跨功能适配；继续拆分应移动一个完整边界，不能复制渲染或编辑器实现。
- 是否切换 ES Modules、是否把根目录测试迁入 `tests/`，均是独立治理工作，不属于已完成重构的兼容性修补。
- 大数据基线中长 Markdown 打开是最明显的单次主线程阻塞点；若实际数据继续增长，可单独评估分块渲染或虚拟化。
