# ArxivDaily

每天抓取 arXiv 论文，经关键词规则和模型筛选后，用 Server酱发送微信简报。支持通过配置自由组合标题、译文、摘要、LLM 总结、证据链、来源和初筛路径；没有新增时也发送通知。项目由 GitHub Actions 定时运行，本机使用 conda `ml` 环境调试。

## 日常只需调整两个入口

| 想调整什么 | 修改哪里 |
| --- | --- |
| 内容模块、分类、关键词与组合、路线优先级、篇数/费用限制、模型和翻译服务 | 根 [config.toml](config.toml)，参见 [配置说明](docs/CONFIGURATION.md) |
| 研究兴趣、模型判断标准、总结详略、翻译术语 | [app/prompts/](app/prompts/selection.md)，参见 [提示说明](docs/PROMPTS.md) |

修改后提交到 `main`，下一次 Actions 使用新版本。本地立即读取当前文件。已成功生成和已推送的内容继续复用，不因修改配置或提示自动重做或重发。

## 阅读论文与历史

- [总论文索引](../../blob/arxivdaily-state/archive/papers.md)：英文/中文标题、链接与首次收集日期。包含规则命中的候选，也包含未通过模型终筛的论文。
- [每日简报归档](../../tree/arxivdaily-state/archive)：打开 `YYYY-MM-DD.md` 阅读当天内容；`YYYY/MM/DD/` 下是每次发送的独立快照。
- [Actions 运行记录](../../actions/workflows/daily-digest.yml)：查看运行结果、错误及脱敏报告。

索引、简报和机器状态由程序自动更新到 `arxivdaily-state`，无需手工编辑。自动更新步骤见 [运行与恢复](docs/OPERATIONS.md)。

这些链接在 GitHub 上指向当前仓库，fork 后会指向自己的归档与 Actions。`archive.public_base_url` 默认留空，Actions 按当前仓库自动生成；首次运行前归档链接可能尚不存在。fork 建议只复制 main 分支，避免继承上游的去重和投递状态，并在自己的仓库配置 Secrets、启用 Actions。已有 fork 请同步 main；旧配置中的固定归档地址需改为空字符串。

## 本机检查和试跑

在项目根目录的 PowerShell 执行，启动脚本使用 conda `ml` 的 Python 和工作区依赖。

```powershell
# 检查配置与六个提示文件，无外部请求。
& ./app/scripts/run-local.ps1 config
# 查看完整生效配置。
& ./app/scripts/run-local.ps1 config --show
# 预览摘要的关键词命中，不调用模型。
& ./app/scripts/run-local.ps1 config --abstract 'Medical spatial reasoning segmentation with DPO.' --categories cs.CV
# 合成样本离线试跑，不修改正式状态。
& ./app/scripts/run-local.ps1 run
```

`run` 默认离线；`--live` 使用真实论文和模型，可能产生费用但不发送；`--send` 才更新正式状态并推送，还需同步发布命令。参数见 [运行说明](docs/OPERATIONS.md)。离线样本的判断、总结和翻译是模拟结果。

要查看最近 14 天的规则初筛结果，打开 [初筛调试 notebook](app/notebooks/arxiv_rules_debug.ipynb)，选择 conda ml 内核。它只抓 arXiv 元数据，支持缓存、规则对比、命中依据和 CSV 导出；不调用模型或使用正式去重记录。见 [主动调试说明](docs/DEBUGGING.md)。

## 项目结构

```text
config.toml              唯一日常配置入口
.github/workflows/       定时/手工运行
docs/                    配置、提示、运行、架构与维护
app/
  prompts/               六项模型任务的中文提示
  notebooks/             主动调试入口
  arxivdaily/            核心代码
  scripts/               本地启动、状态发布、公开文件检查
  tools/                 可选开发工具
  tests/                 回归测试
  fixtures/              离线样本与固定来源清单
  pyproject.toml         Python 包与运行依赖
  requirements.lock     锁定依赖
```

本机依赖 `.runtime/`、正式状态 `.state/`、隔离试跑 `runs/`、临时输出 `tmp/` 位于 `app/`，不进入代码仓库。凭证只通过环境变量或 Actions Secrets 提供。

参见 [维护说明](docs/DEVELOPMENT.md)、[架构与行为](docs/ARCHITECTURE.md)、[第三方来源](docs/THIRD-PARTY.md)。新增代码采用 [MIT](LICENSE)。
