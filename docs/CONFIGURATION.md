# 配置说明

唯一日常入口是根目录 `config.toml`。本地 CLI 按应用位置寻找它，不依赖当前目录；Actions 读取同一文件。`--config PATH` 指定另一份配置，命令行覆盖只影响当次运行。提示目录相对路径以配置文件所在目录为基准。

修改后运行 `app/scripts/run-local.ps1 config` 检查；加 `--show` 查看实际配置。没有外部请求。缺键使用内部默认值；未知键、无效数值或缺失/空提示文件明确报错。

## 工作流与额度

```toml
[workflow]
mode = "summary" # translation = 标题和摘要双语，不读取正文
```

summary 使用模型终筛、必要正文复审、完整档五段中文总结。general_reasoning 只出轻量清单，完整档名额溢出也为轻量。translation 沿用关键词和终筛，将 select 与 uncertain 候选双语翻译；uncertain 标注未全文确认，reject 不推送。translation 不下载正文，不受完整总结篇数限制。

`limits.full_daily_limit` 默认 5、最多 10；`review_daily_limit` 控制 uncertain 正文复审篇数。`llm.max_run_cost` 取消注释后提供单次费用保护，是配置价格估算而非账单。切换模式不会重发已确认论文。

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

medical_reasoning 对应 `MED AND SEG AND (REASON OR VLM)`。忽略大小写，统一连字符/空格，缩写使用完整词边界，避免 CT/RL 匹配到其他单词内部。

组与初筛路线名可自定义。配置按名称覆盖默认组/路线；缺失名称仍使用默认值，所以禁用默认路线要设 `[]`，不要只删那一行。THEORY_HINT 不作为初筛必要条件，理论和迁移交给模型判断。

```powershell
& ./app/scripts/run-local.ps1 config --abstract 'Medical spatial reasoning segmentation with DPO.' --categories cs.CV
```

预览只显示初筛命中，不代表模型入选。增加关键词扩大候选范围；语义兴趣和拒绝标准同步调整 `app/prompts/selection.md`。

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

`translation.provider` 可选 llm、deepl、libretranslate。

- llm 复用终筛模型/端点/密钥并关闭思考，可编辑翻译提示。
- deepl 使用官方免费 API 端点，密钥环境变量为 TRANSLATION_API_KEY。这只是引用名称，项目不创建密钥；需在自己的 [DeepL API 账户](https://support.deepl.com/hc/en-us/articles/360020695820-API-key-for-DeepL-API) 创建 key，再配置同名环境变量或 Actions Secret。provider=llm 时不使用这个端点/密钥引用。
- libretranslate 需配置自己的实例，Actions localhost 是 runner 自己。机器翻译不使用 LLM 提示，失败不会自动切收费 LLM。

抓取、模型/重试、正文、推送等高级设置位于配置后半部分。更换模型、端点或价格时核实费用并将 `llm.pricing.policy` 改为 custom。

凭证字段只填环境变量名称。`archive.state_branch` 由 Actions 读取，现有分支 arxivdaily-state；public_base_url 需匹配实际公开归档。定时调度由 `.github/workflows/daily-digest.yml` 管理。
