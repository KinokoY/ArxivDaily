# 二次开发基础项目调研

核查日期：2026-10-02（Asia/Shanghai）。范围：只读访问公开仓库原始代码、GitHub API 的提交和完整文件树；没有 clone、fork、执行仓库代码、运行测试或创建 PR。以下“已实现”均指静态代码中存在实现，不代表运行验证通过。研究止于用户指定项目及三个候选。

## 建议

**优先以 [X-PG13/paper-digest](https://github.com/X-PG13/paper-digest) 的固定提交 `8906f9a12309956913eab29dade75c01cb7d0771` 作为二次开发基础。** 原因是 MIT 许可明确，已有配置、规则筛选、状态去重、每日 GitHub Actions、中文 Markdown/JSON 产物和多种推送适配器；这些外围工作比直接改造用户指定的论文目录脚本更完整。其核心缺口也明确：没有 arxiv Python 库、没有低成本 LLM 终筛、没有全文总结，需要新增或替换。

**推荐是工程判断，尚未作为用户决策。** 如果用户要求最小单脚本、极少改动，则这不是最轻的仓库；它包含多文献源、反馈、归档网站及大量维护工作流。MVP 应关闭不需要的功能，只围绕 arXiv 与一个推送渠道改造运行路径，避免把上游所有运营功能带入需求。

## 固定版本对比

| 项目 | 默认分支 / 当次 HEAD | 许可核查 | 对需求的匹配 | 判断 |
|---|---|---|---|---|
| Xuchen-Li/llm-arxiv-daily | main / `2ad958490868d5b678b22b84f2c234070c04c2a1` | API license 为 null；该提交完整 tree 没有 LICENSE，README 为生成的论文目录 | Python + arxiv 库 +关键词 + Actions + JSON/Pages；无 LLM、全文、个人推送 | 可参考产品形式；默认不建议直接复制代码做二次开发基础 |
| X-PG13/paper-digest | main / `8906f9a12309956913eab29dade75c01cb7d0771` | 原始 LICENSE 为 MIT | 规则初筛、状态、Actions、中文产物、多渠道；arXiv API 是自写 XML 客户端；LLM 仅分析摘要 | **优先基础**，替换客户端和 LLM 主流程 |
| ASLP-lab/ArxivWatcher | main / `6922ceb7f8355558d7a6bab0aa64767d66f37e0d` | LICENSE 明确写 CC BY 4.0；API spdx 为 NOASSERTION，不能据此认定无许可 | PDF 全文提取 + 中文深读 + SMTP；带 Flask/Docker/账号/知识库；tree 无 Actions 工作流，不使用 arxiv py | 全文相关实现可作为设计参考，整体偏重 |
| LucaJiang/DailyPaper | master / `e1c76f3191c6a11f5ea250c898d0d18c9ea55b5f` | 原始 LICENSE 为 MIT | DeepSeek 中文总结 + Server 酱 + history；来源为 Semantic Scholar 推荐；LLM 只收标题/摘要/TLDR；schedule 被注释 | 推送示例参考，核心收集/筛选/全文均不匹配 |

HEAD 从当次 GitHub API `commits/<default_branch>` 现场读取，不依赖网页抓取缓存。后续开发可以重新核查上游，但应在交接中保留这些 SHA。自动提交使仓库近期活动不能直接当成核心代码维护质量证据。

## 用户指定项目：实际实现与缺口

1. `daily_arxiv.py` 的 `arxiv.Search` 按 SubmittedDate 获取每个主题最多 100 条，使用旧式 `search_engine.results()`；主题配置拼接 OR 关键词，没有独立标题/摘要/分类字段的配置语义，也没有按上次成功运行位置补抓的逻辑。`paper_abstract` 和 `primary_category` 被取出，但未用于本文处理或总结。没有 LLM 调用、PDF 下载或全文解析。
2. 论文 ID 去掉版本后作为每主题 JSON 字典的 key，后续运行合并；它是论文目录的归档去重，不是“筛选 / 总结 / 推送成功”三阶段的事务状态。版本更新覆盖原条目，没有新版本是否重推的明确策略。
3. 原始 `main.yml` 每 6 小时运行，不是每天一次；Python 3.10，安装未锁版本的 arxiv / requests / pyyaml，生成 README、docs/index.md 与 JSON，并经第三方 commit action 写回。`update.yml` 每周补查代码链接。
4. `requests.get(code_url).json()` 位于生成输出的 try 内；外部代码链接服务失败会使该篇论文没有输出，且没有显式超时。PapersWithCode 应改为可选增强，失败不应影响论文筛选和推送。此处只评审耦合关系，未核查当前 PapersWithCode 服务可用性。
5. 该固定提交未发现明确许可。GitHub 官方说明公开可查看 / fork 与源代码复制、分发、衍生授权不是同一问题，因此不应把“公开仓库”当作授权证明。若用户坚持此基础，应先取得或核实上游授权；改选许可清晰候选可避免这一前置问题。[GitHub 官方许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)

固定来源：

- [主程序](https://github.com/Xuchen-Li/llm-arxiv-daily/blob/2ad958490868d5b678b22b84f2c234070c04c2a1/daily_arxiv.py)
- [配置](https://github.com/Xuchen-Li/llm-arxiv-daily/blob/2ad958490868d5b678b22b84f2c234070c04c2a1/config.yaml)
- [六小时主工作流](https://github.com/Xuchen-Li/llm-arxiv-daily/blob/2ad958490868d5b678b22b84f2c234070c04c2a1/.github/workflows/main.yml)
- [每周代码链接工作流](https://github.com/Xuchen-Li/llm-arxiv-daily/blob/2ad958490868d5b678b22b84f2c234070c04c2a1/.github/workflows/update.yml)
- [该提交完整 tree API](https://api.github.com/repos/Xuchen-Li/llm-arxiv-daily/git/trees/2ad958490868d5b678b22b84f2c234070c04c2a1?recursive=1)

## 推荐基础：可复用与必须改造

| 模块 | 上游当前行为 / 可复用部分 | 为本需求必须改变 |
|---|---|---|
| `paper_digest/config.py` / `config.example.toml` | TOML 配置和类型检查；多个 feed、类别、include/exclude、上限、时区、通知配置 | 增加独立标题 / 摘要 / 正文规则、AND/OR/排除语义、两阶段模型与预算配置；敏感凭证仍放 Secrets |
| `paper_digest/arxiv_client.py` | Paper 数据模型、规范化 ID、category / 元数据转换、重试相关参数 | 将获取实现替换为 `arxiv.Client` / `arxiv.Search`；用户明确要求 arxiv Python 库。设计日期窗口、分页、断点 / 补抓，保留 version |
| `paper_digest/digest.py` | `filter_papers` 使用标题 / 摘要关键词及排除词，记录命中理由、按发表日期截断、排序后 `max_items` | 当前关键词是标题或摘要任一命中；不能直接表示字段独立规则。不要在低成本 LLM 决策前过早套用最终推送上限；正文关键词需先取得正文 |
| `paper_digest/openai_analysis.py` / `analysis.py` | 结构化 JSON schema、响应解析与中文渲染基础 | 明确只以 title / metadata / abstract 为模型输入；需新增低成本相关性判定与正文理解总结，分别配置 provider / endpoint / model。当前 Responses API 格式不能假定所有 OpenAI-compatible 提供方直接支持 |
| 新增正文获取模块 | 上游没有正文抓取 / 提取实现 | HTML 可用性探测或 PDF 获取、解析质量检查、段落 / 页码出处、长文分段聚合。禁止把正文失败静默退化成摘要总结；失败策略由用户决定 |
| `paper_digest/state.py` | UTF-8 JSON 状态、canonical ID、保留期、去重；CLI 先推送成功再保存 state | 状态需区别 fetched / rejected / selected / summarized / sent、模型与规则版本、文章版本；失败重跑不重复付费和推送。跨渠道部分成功应逐渠道确认 |
| `paper_digest/*_delivery.py` | SMTP、飞书、企业微信、Slack、Discord、Telegram；企业微信检查 errcode | 选定 MVP 渠道。企业微信现实现将 Markdown 截断为 4096 bytes，应做分条 / 摘要链接，避免后面论文直接丢失；个人微信第三方服务需新增适配器 |
| `.github/workflows/daily-digest.yml` | 每日 cron、手动运行、concurrency、30 分钟 timeout、状态 / 归档 cache、产物上传 | 重设北京时间推送时刻；禁用不需要的离线翻译模型 / Pages 构建，缩短运行；设计可靠状态持久化，cache 不作为唯一可靠数据库。锁定依赖和 Actions 版本 |

状态细节：当前 CLI 调用 `generate_digest(..., state=state)`，成功 `send_configured_deliveries` 后才 `save_state`（`cli.py:454–467`）。`dedupe_papers` 在内存提前标 seen，但 CLI 的正常失败路径不保存；这点可复用。直接调用 `generate_digest` 不传 state 会在生成阶段保存，因此新主流程应明确状态提交边界。通知发送成功后进程崩溃、状态 cache 丢失或多渠道部分失败仍可导致重推，需在交接中说明预期保证。

固定来源：

- [MIT LICENSE](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/LICENSE)
- [Python / 依赖 / 工具配置](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/pyproject.toml)
- [arXiv API 自写客户端](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/paper_digest/arxiv_client.py)
- [规则和 Markdown 渲染](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/paper_digest/digest.py#L195)
- [LLM 只使用摘要的限制](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/paper_digest/openai_analysis.py#L79)
- [主服务流程](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/paper_digest/service.py#L111)
- [推送后保存状态](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/paper_digest/cli.py#L447)
- [JSON 状态模块](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/paper_digest/state.py)
- [企业微信适配器](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/paper_digest/wecom_delivery.py)
- [每日工作流](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/.github/workflows/daily-digest.yml)
- [配置示例](https://github.com/X-PG13/paper-digest/blob/8906f9a12309956913eab29dade75c01cb7d0771/config.example.toml)
- [核心测试目录](https://github.com/X-PG13/paper-digest/tree/8906f9a12309956913eab29dade75c01cb7d0771/tests)

## 两个其他候选的核心证据

ArxivWatcher：`send.py` 下载 PDF 后用 pypdf 抽取全文（953 起）；`analyze_paper_with_llm` 使用全文，但仅保留开头至 MAX_TEXT_LENGTH，正文为空时换成摘要（1015–1036）。`_process_single_paper` 先解读，再分类评分（2075–2078），与“便宜模型先筛、贵模型仅总结选中文章”的成本顺序相反。使用同一 llm_config。仓库带网页、多用户等功能，完整 tree 未见 `.github/workflows`，依赖也没有 arxiv。

- [许可文件：CC BY 4.0](https://github.com/ASLP-lab/ArxivWatcher/blob/6922ceb7f8355558d7a6bab0aa64767d66f37e0d/LICENSE)
- [全文与摘要降级行为](https://github.com/ASLP-lab/ArxivWatcher/blob/6922ceb7f8355558d7a6bab0aa64767d66f37e0d/send.py#L1015)
- [总结后再筛选的流程](https://github.com/ASLP-lab/ArxivWatcher/blob/6922ceb7f8355558d7a6bab0aa64767d66f37e0d/send.py#L2055)
- [依赖](https://github.com/ASLP-lab/ArxivWatcher/blob/6922ceb7f8355558d7a6bab0aa64767d66f37e0d/requirements.txt)
- [完整 tree API](https://api.github.com/repos/ASLP-lab/ArxivWatcher/git/trees/6922ceb7f8355558d7a6bab0aa64767d66f37e0d?recursive=1)

DailyPaper：`get_paper_recommendations` 依赖 Semantic Scholar seed 正 / 负例推荐，筛未推送、venue 黑名单、摘要非空，并取最新 10 篇；总结 prompt 仅给标题、TLDR 与摘要，无正文，使用单一 deepseek-chat。Server 酱 POST 没有检查 HTTP / 业务响应，就追加 seen history；需要更改，否则推送失败也可能被记作成功。工作流实际仅 workflow_dispatch，schedule 注释掉；历史 git commit 提供了可参考的状态保存方式。

- [MIT LICENSE](https://github.com/LucaJiang/DailyPaper/blob/e1c76f3191c6a11f5ea250c898d0d18c9ea55b5f/LICENSE)
- [来源、总结、推送与 history 主程序](https://github.com/LucaJiang/DailyPaper/blob/e1c76f3191c6a11f5ea250c898d0d18c9ea55b5f/paper_tracker.py)
- [实际工作流](https://github.com/LucaJiang/DailyPaper/blob/e1c76f3191c6a11f5ea250c898d0d18c9ea55b5f/.github/workflows/daily_tracker.yaml)

## 真正需要用户决定的项目相关问题

1. 是否接受以推荐 MIT 项目为基础，在保留外围模块的情况下更换 arxiv 客户端并新增两阶段 LLM / 全文模块？若最优先的是单脚本易读，则需明确此偏好；不要把现有项目误当作几处 prompt 修改就能满足要求。
2. 需要仅 Actions + 配置 + 每日通知的工具，还是也需要归档网页？MVP 可只保留 JSON / Markdown 日报与一个推送渠道。
3. 个人兴趣、历史文章、筛选理由是否可以在公开 repo / Pages 可见？若不可，应关闭 Pages 并设计私有状态保存。
4. MVP 选择哪一种单一通知渠道、需要全文短报直接可读还是通知链接到完整日报？这影响上游适配器复用和超长消息处理。
5. 新版本、失败重跑、规则 / 模型变更后是否重新筛选和重推？这是状态 schema 的用户语义，不能照搬上游 seen 字典。

其他需求问题（研究兴趣、全文匹配逻辑、数量 / 预算、时刻、失败降级、质量验收样例）由主代理汇总，避免让用户回答已经能从来源核查的事实。
