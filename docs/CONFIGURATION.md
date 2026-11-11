# 配置说明

唯一日常入口是根目录 `config.toml`。本地 CLI 按应用位置寻找它，不依赖当前目录；Actions 读取同一文件。`--config PATH` 指定另一份配置，命令行覆盖只影响当次运行。提示目录相对路径以配置文件所在目录为基准。

修改后运行 `app/scripts/run-local.ps1 config` 检查；加 `--show` 查看实际配置。没有外部请求。缺键使用内部默认值；未知键、无效数值或缺失/空提示文件明确报错。

## 内容模块与额度

只使用 `[presentation]` 选择每篇论文的内容，原 `workflow.mode`、CLI `--workflow` 和 Actions `content_workflow` 已删除。旧配置会报未知键，需要改用下面的模块开关。

```toml
[presentation]
title = true
title_translation = true
abstract = true
abstract_translation = true
llm_summary = false
evidence = false
source = true
screening_routes = true
```

上面是默认配置。`true` 勾选，`false` 关闭；各模块独立选择，至少启用一个。固定顺序为：标题 → 标题翻译 → 摘要 → 摘要翻译 → LLM 总结 → 证据链 → 来源 → 初筛路径。关闭标题时以 arXiv ID 作为条目标识；关闭来源时不显示论文来源链接。

例如只显示双语标题和总结：将 `title`、`title_translation`、`llm_summary` 设为 true，其余全部 false。总结与摘要翻译也可以同时启用；证据链可单独启用而不显示五段总结。

`screening_routes` 使用 arXiv 关键词初筛保存的全部命中路径，包括自定义路径，放在每篇最后；不使用 LLM 终筛选出的单一路线。现在同时展示每个命中的 AND 组合、组内所有实际命中的词/短语，以及来自标题还是摘要。同组内 `/` 为 OR，不同组间 `＋` 为 AND。没有历史命中记录时明确显示“无初筛命中记录”。

`rule_trace` 随论文及发送快照保存，包含规则指纹、论文版本、组合与词级命中证据；修改配置不会重写既有反馈的命中依据。尚未处理的旧记录若缺少词级证据，会明确标注“按当前规则补算”，与原始历史证据分开统计；不改写旧简报。

未启用总结和证据链时不下载正文、不复审、不占用完整档名额，select 与 uncertain 候选按所选模块呈现，uncertain 标注待确认，reject 不推送。不勾选译文模块就不为该模块调用翻译；关闭标题翻译也停止自动补译索引，尚无译文时索引显示“待翻译”。摘要翻译调用同时返回标题译文，仍只展示勾选的字段。例外是正式运行启用反馈时：为保证反馈 Issue 的中英文标题，会为实际待推送论文补译缺失中文标题，不额外翻译摘要。

启用总结或证据链时使用正文，uncertain 有限复审；完整档名额默认 5、最多 10，由 `limits.full_daily_limit` 控制。general_reasoning 和名额溢出仍进入轻量档，呈现其余勾选模块，并明确标注未生成总结/证据。`review_daily_limit` 控制 uncertain 正文复审名额。

`evidence=false` 时直接基于合格正文生成五段总结，evidence 返回空数组，不执行长文证据提取或逐条引文/数字核验。正文超出 `llm.summary.input_chars` 时明确失败，不截断正文、不自动增加提取调用；可提高输入容量或启用证据链。`evidence=true` 时生成并展示定位、原文引文与来源，同时启用原有引文和数字核验，长文按需分片提取证据。终筛/正文复审所需的判定依据仍保留。

每篇开始内容处理时保存模块选择，失败恢复、补发和重投复用该选择及成功内容；修改配置只影响新的内容处理，不自动重发已确认论文。旧状态与不可变历史快照仍可读取。状态中的 `translation` 档位沿用为元数据条目标记，不要求启用翻译。

`llm.max_run_cost` 可提供单次费用保护，是配置价格估算而非账单。

## arXiv 初筛

1. `rules.categories` 中任一分类出现在论文任一交叉分类即可；空数组表示不限分类。
2. 默认只匹配摘要，`title_enabled = true` 后标题也参与；`exclude` 任一短语命中则排除。
3. `rules.groups` 同组词是 OR；每个路线内层列表是 AND，多个内层列表是 OR，各路线也为 OR。

```toml
[rules.groups]
CUSTOM = ["pixel inference", "anatomical reasoning"]
[rules.routes]
medical_reasoning = [["MED", "SEG", "REASON"], ["MED", "SEG", "VLM"]]
custom_route = [["SEG", "CUSTOM"]]
general_reasoning = [] # 明确禁用此初筛路线
```

medical_reasoning 对应 `MED AND SEG AND (REASON OR VLM)`。忽略大小写，统一连字符/空格，缩写使用完整词边界，避免 CT/RL 匹配到其他单词内部。一个短语必须在标题或摘要内部完整出现，不跨字段拼接匹配。

组与初筛路线名可自定义。配置按名称覆盖默认组/路线；缺失名称仍使用默认值，所以禁用默认路线要设 `[]`，不要只删那一行。THEORY_HINT 不作为初筛必要条件，理论和迁移交给模型判断。

```powershell
& ./app/scripts/run-local.ps1 config --abstract 'Medical spatial reasoning segmentation with DPO.' --categories cs.CV
```

预览显示路线及 `rule_trace` 具体关键词证据，不代表模型入选。增加关键词扩大候选范围；语义兴趣和拒绝标准同步调整 `app/prompts/selection.md`。

检查实际日期范围会召回哪些文章，使用 [初筛 notebook](../app/notebooks/arxiv_rules_debug.ipynb)。它缓存分类元数据，让关键词/组合调整在本地反复比较；详见 [主动调试说明](DEBUGGING.md)。

## 模型路线优先级

`selection.route_priority` 控制全文名额分配，需恰好列出五条路线：

| 路线 | 用途 |
| --- | --- |
| medical_reasoning | 医学推理分割 |
| medical_objective | 医学分割的 RL/DPO、结构或优化目标 |
| general_rl | 通用推理分割，RL/DPO 为本研究方法 |
| transferable_objective | 有理论及迁移依据的分割目标 |
| general_reasoning | 通用推理分割轻量清单 |

同一路线按模型分数排序。自定义关键词路线只是召回标记，不自动新增模型类别。禁用一个关键词路线不保证排除某类论文，因为其他路线可能召回；语义排除写到 selection 提示。

现有程序约束：general_reasoning 入选为 light；general_rl 需 RL/DPO 方法标记；transferable_objective 需理论与迁移证据。改变这些判定结构属于代码迭代。

## 翻译与高级设置

`[feedback]` 控制每日反馈。根配置启用此功能；不含该表的旧配置默认关闭，保持兼容。

```toml
[feedback]
enabled = true
repository = "" # Actions 自动取当前仓库；本地正式运行需填 owner/repo 或设置 GITHUB_REPOSITORY。
max_wait_days = 14
cleanup_action = "close" # close 关闭并保留历史链接；delete 永久删除。
token_env = "GITHUB_TOKEN"
delete_token_env = "FEEDBACK_DELETE_TOKEN"
```

等待时间从该期反馈创建意图记录的时间开始计算，范围 1–365 天。只有 `--send` 会访问反馈接口；离线和 `--live` 试跑均不创建、读取或清理 Issue。每次正式运行都会同步已评价的部分，不受清理条件影响。当日 Issue 保留到次日，便于当日补发追加论文；次日起全部已评价或超过等待时间才清理。`cleanup_action` 默认 `close`，也可设为 `delete`；旧配置缺少此项时默认关闭。权限与统计口径见 [论文反馈](OPERATIONS.md#论文反馈)。

`translation.provider` 可选 llm、deepl、libretranslate。

- llm 复用终筛模型/端点/密钥并关闭思考，可编辑翻译提示。
- deepl 使用官方免费 API 端点，密钥环境变量为 TRANSLATION_API_KEY。这只是引用名称，项目不创建密钥；需在自己的 [DeepL API 账户](https://support.deepl.com/hc/en-us/articles/360020695820-API-key-for-DeepL-API) 创建 key，再配置同名环境变量或 Actions Secret。provider=llm 时不使用这个端点/密钥引用。
- libretranslate 需配置自己的实例，Actions localhost 是 runner 自己。机器翻译不使用 LLM 提示，失败不会自动切收费 LLM。

抓取、模型/重试、正文、推送等高级设置位于配置后半部分。更换模型、端点或价格时核实费用并将 `llm.pricing.policy` 改为 custom。

凭证字段只填环境变量名称。`archive.state_branch` 由 Actions 读取，现有分支 arxivdaily-state。`archive.public_base_url` 默认留空，Actions 在当次工作副本中按 `${{ github.repository }}` 和状态分支生成 `https://raw.githubusercontent.com/<owner>/<repo>/<state_branch>`，不把生成值提交回 main；fork 自动使用自己的仓库。显式填写时保留原值，需匹配实际公开归档；已有 fork 若还填着上游地址，请改为空字符串。本地 `--send` 不执行 Actions 准备步骤，需通过自己的配置文件提供完整地址。定时调度由 `.github/workflows/daily-digest.yml` 管理。
