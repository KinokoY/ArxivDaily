# arXiv 与 GitHub Actions 调研

核查日期：2026-10-02（Asia/Shanghai）。本文件仅记录官方文档、维护者源代码和由这些事实推导的设计建议；没有开发应用或创建工作流。

## arXiv 检索与采集事实

| 项目 | 已核查事实 | 对设计的影响 |
| --- | --- | --- |
| 查询字段 | `ti` 标题、`abs` 摘要、`cat` 分类等；`all` 是文档列出的元数据字段并集，**不包含论文正文**。 | 全文关键词需要候选全文下载与本地匹配，不能写成 `all:keyword` 后声称检索全文。 |
| 逻辑 | 支持 `AND`、`OR`、`ANDNOT`、括号、双引号短语。 | 配置必须明确字段间逻辑与同字段关键词逻辑。 |
| 日期 | 文档提供 `submittedDate:[YYYYMMDDHHMM TO YYYYMMDDHHMM]`，日期查询使用 GMT；可按 `submittedDate` 或 `lastUpdatedDate` 排序。 | 用户日历使用北京时间；API 窗口统一转换为 UTC。 |
| 分页 | `start` 为零起点，`max_results` 控制数量；官方说明至多 30,000 条、每片最多 2,000，并建议缩小大结果查询。 | 固定只取最新 100 条会漏论文；达到容量上限须报警或按日期/主题拆分。 |
| 版本 | `published` 为首版提交处理日期；`updated` 为取得版本的提交处理日期；不指定版本取得最新版。 | 同时存基础 ID 与版本 ID，避免交叉分类重复；新版本是否重新推送属于用户决策。 |

来源：[arXiv API User Manual](https://info.arxiv.org/help/api/user-manual.html)。

分类标识应使用 `cs.CV`，而不是 `CS/CV`；还有 `cs.LG`、`cs.AI`、`cs.CL` 等。应由具体主题决定涵盖哪些分类，并决定是否接受交叉分类。来源：[Category Taxonomy](https://arxiv.org/category_taxonomy)。

API 限速是受控机器合计每三秒最多一次请求，且一次只使用一个连接。API client 的并行化不能通过多个 runner 绕开限速。来源：[API Terms of Use](https://info.arxiv.org/help/api/tou.html)。

arXiv 按美国东部时间周日至周四晚间公布文章；审核通常需要一至四天，也可能更长，节日会顺延。API 手册描述查询结果按日更新，并建议缓存。**提交日期、公布日期、API 可见日期并非同一概念**，只查“北京时间昨天”不是可靠采集边界。来源：[Availability of submissions](https://info.arxiv.org/help/availability.html)、[API User Manual](https://info.arxiv.org/help/api/user-manual.html)。

## Python 库兼容性

当前 PyPI 最新包为 `arxiv 4.0.1`，2026-07-31 发布，需要 Python >= 3.10。开发时必须核查基项目版本并锁定兼容依赖。来源：[arxiv on PyPI](https://pypi.org/project/arxiv/)。

维护者当前 API 为 `arxiv.Client(...).results(search)`；默认 `page_size=100`、`delay_seconds=3.0`、`num_retries=3`，客户端迭代分页并重试 HTTP/异常空页等。`Result` 提供标题、摘要、作者、分类、发布日期/更新日期和 `pdf_url`，并可构造 `source_url()`。来源：[arxiv.py API/source](https://lukasschwab.me/arxiv.py/arxiv.html)、[source repository](https://github.com/lukasschwab/arxiv.py/blob/master/arxiv/__init__.py)。

4.0.0 已移除 `Search.results()`、`Result.download_pdf()` 与 `Result.download_source()`；无限结果用 `max_results=None`，不能沿用 `math.inf`。因此旧项目示例不宜原样复制。来源：[arxiv.py 4.0.0 release notes](https://github.com/lukasschwab/arxiv.py/releases/tag/4.0.0)。

## 全文获取与质量

arXiv 提供 PDF、源文件以及部分论文的 HTML；HTML 正在回填历史论文，但并非所有论文能成功转换，而且转换仍可能有错误。因此不能将 HTML 作为唯一来源。来源：[HTML as an accessible format](https://info.arxiv.org/about/accessible_HTML.html)、[Viewing submissions](https://info.arxiv.org/help/view.html)。

PDF 可用纯 Python 工具抽取文本，但阅读顺序、断行、双栏、表格结构并不天然可靠；`pypdf` 不提供 OCR，也不能读取图片中的文字。PyMuPDF 支持块/词及坐标、排序和表格抽取等，但也明确说明普通文本抽取顺序可能不符合阅读顺序。来源：[pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)、[PyMuPDF text recipes](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)。

PyMuPDF/MuPDF 采用 AGPL 与商业协议双许可；若将 PyMuPDF 选作依赖，开发阶段应核查其许可与项目使用、发布方式的兼容性，不能只按提取功能等同于其他 PDF 库作取舍。来源：[PyMuPDF License and Copyright](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)。

由以上事实推导的建议（尚未获用户确认）：

1. 优先获取有结构的 HTML；失败或质量不足时用 PDF 文本抽取。保留正文的章节/页码、表格与图注信息供总结引用，记录提取方式和质量状态。
2. 全文关键词尽量排除参考文献、页眉页脚；明确是否包含附录、图注、表格。仅在参考文献中出现关键词，往往不足以代表研究主题。
3. 对抽取异常设阈值；无法取得合格全文时可跳过并提醒，或保留“待处理”，不能静默用摘要代替全文总结。OCR 或视觉模型兜底会增加依赖、执行时间和模型费用，应由用户选择。
4. 论文超出模型上下文时，按章节处理再汇总，并保留方法与实验的证据；只截取前若干页会损害用户所要求的“理解全文后总结”。
5. 若规则是“标题/摘要命中 **或** 正文命中”，API 必须先取得足够宽的分类/日期候选集合。先要求标题命中会永久漏掉仅在正文命中的文章。若规则是“标题/摘要命中 **且** 正文命中”，则可先用元数据缩小下载量。

## GitHub Actions 免费额度与调度事实

| 项目 | 当前官方说明 | 对设计的影响 |
| --- | --- | --- |
| Public 仓库 | standard GitHub-hosted runner 免费；larger runner 即使 public 仍收费。 | 选择标准 Ubuntu runner 可满足免费计算要求；不能据此承诺 LLM、推送服务也免费。 |
| Private / GitHub Free | 每月含 2,000 runner 分钟、500 MB artifact 存储；缓存为每仓库 10 GB；额度按账户/组织共享。 | 月预算必须计入安装、下载、失败重试和该账户的其他项目。 |
| 超额 | 无有效付款方式时额度耗尽会被阻止；有付款方式可能计费。 | 配置 Actions 预算及到限停止，控制 artifact 保留期，保持默认缓存容量。 |
| 单任务时限 | GitHub-hosted job 最多六小时。 | 设置比该上限更小的任务超时和模型请求超时。 |

来源：[Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)、[Actions limits](https://docs.github.com/en/actions/reference/limits)、[Budgets](https://docs.github.com/en/billing/how-tos/set-up-budgets)。

`schedule` 可能延迟，高负载时排队任务可能被丢弃；整点尤其繁忙。工作流文件须位于默认分支，而且定时任务只在默认分支执行。public 仓库六十天无活动会停用定时任务。当前文档：默认 UTC，**已可指定 IANA `timezone`**（如 `Asia/Shanghai`），不应沿用“GitHub cron 只能 UTC”的旧说法。来源：[Events: schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

public 仓库 fork 后定时工作流默认停用，部署说明需要包含启用 Actions、启用工作流和设置 secrets。来源：[Disable and enable workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)。

## 持久化与漏跑补采建议

事实：标准 GitHub-hosted job 使用新 runner 实例，不能把本地工作目录当成下一天仍存在的数据库。来源：[GitHub-hosted runners](https://docs.github.com/en/actions/concepts/runners/github-hosted-runners)。

事实：cache 会淘汰超过七天未访问的条目，并受容量淘汰约束；artifact 有保留期限，读取其他 run 的 artifact 需要相应 token 和 run ID。两者可作临时缓存/调试留档，但不是天然永久状态存储。来源：[Caching reference](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)、[Store and share data](https://docs.github.com/en/actions/tutorials/store-and-share-data)。

建议将少量状态放在专用 Git 分支或持久存储：最后成功采集窗口、基础 ID/版本、规则与模型版本、筛选结果、总结、推送确认、待重试记录；缓存只放可重建依赖/提取结果。状态存储应当先设计，再决定依赖现有项目哪一部分。

建议每次从上次成功采集时间前的重叠窗口补采；时间范围分页完整、成功保存采集结果后才推进游标。额外保留滚动回看窗口以覆盖文章延迟可见，并用 ID 去重。有限回看窗口无法绝对覆盖无限期审核延迟，需配置最长补采范围和超界提示，不能承诺任意故障后绝不漏文。

候选数量达到应用上限、API 分页中途失败、补采跨度超出允许范围时，应记录本轮为不完整/待恢复，并展示未覆盖范围；不能静默标记“采集成功”或把成功游标推进到当前时间。模型费用上限可以停止继续总结，但不得把尚未处理的候选永久丢弃。

建议独立记录“已总结”与“已推送”，推送失败只重试推送，避免重复花模型费用。若推送 API 不支持幂等键，发送成功但确认/状态写入失败的边界场景，严格恰好一次无法仅靠本地状态保证；用户应决定优先少漏推还是少重复。

建议提供手动运行和日期范围重放，并通过 concurrency 约束避免两个 run 同时修改状态。日程选择非整点，北京时间下午执行可为 arXiv 当天公告及 API 更新留余量；准确到分钟的送达保证超出 schedule 的官方保证范围。

## 尚需用户做出的业务决策

- 分类/关键词/排除词与布尔逻辑；全文规则是否是 MVP 硬需求，以及愿意为召回承担多少下载量。
- 只看新论文还是也看新版；第一次运行是否回溯历史、回溯天数。
- 可接受推送时间窗口和迟到时间；无结果日是否静默。
- public 或 private 仓库；个人配置/筛选理由/摘要的可见性；状态是否可保存到 Git 专用分支。
- 每日最多总结多少篇、候选和 token 限额；总预算需另外包括 LLM 与推送费用。
- 全文提取失败、超长论文、图表关键信息的处理策略；筛选不确定时跳过、补读还是进入总结。
- 故障恢复优先少漏推还是少重复，最长自动补采天数。
