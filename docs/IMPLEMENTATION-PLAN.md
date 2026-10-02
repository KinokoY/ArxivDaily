# ArxivDaily 实施计划

编制：2026-10-02（Asia/Shanghai）。这是原实施顺序；现有 `app/` 已实现，2026-10-03 根 Git 与上游元数据集成、Actions 适配已推进，详见 [开发状态](../DEVELOPMENT-STATUS.md)。保留下文原阶段说明以记录计划，不能据此覆盖现有代码。业务以 [SPEC.md](SPEC.md) 为准，研究报告不覆盖用户决定。

## 1. 建立隔离的二次开发基线

在当前非空、非 Git 工作区下创建 `app/` checkout，从 `X-PG13/paper-digest` 固定 SHA `8906f9a12309956913eab29dade75c01cb7d0771` 开始；保留 MIT LICENSE、归属与 upstream 信息。不覆盖根目录文档 / skills，不在本对话执行 clone、初始化或推送。

开发第一步检查 app 内说明 / AGENTS、配置及测试，记录已有基线测试结果；没有验证上游测试通过前不作已通过宣称。Python 3.12、arxiv 4.0.1 是工程兼容起点，版本重新核查并锁定；其他依赖按实际功能和许可证选取，避免未经评估引入 AGPL 组件。所有临时 fixtures、提取文件、回放与报告均在工作区子目录。

代码模块和测试可以拆给子代理并行；定义共享状态、Paper 数据模型和输出契约后再并行，避免多代理同时改同一文件。根代理负责接口契约、审阅与验收。不要为这些内部子任务另建用户聊天。

## 2. 模块复用与改造边界

| 上游模块 / 新模块 | 工作 | 必须解决的差异 |
| --- | --- | --- |
| `config.py`、TOML 示例 | 复用类型 / 参数解析，新增可独立两角色、摘要布尔组、档位与恢复配置 | 关键词默认只摘要；分类任一交叉命中；Secret 仅 env 引用；不硬设50元 |
| `arxiv_client.py`、`sources.py` | 复用 Paper 元数据、基础 ID 规范化，替换获取为 arxiv 4 Client | 完整分页、UTC窗口、3秒单连接、迟到可见；不走其他文献源 |
| `digest.py` | 保留 Markdown / JSON 产物基础，改规则、排序和两档渲染 | 不在终筛前套最终完整上限；轻量只有英文标题+链接；消息缩短不改变完整身份 |
| `openai_analysis.py`、`analysis.py` | 替换 / 适配官方 DeepSeek 的任务契约 | 同 Flash，筛选high、总结max；三态与JSON完成校验；原摘要分析不能充当全文总结 |
| 新正文 / 证据模块 | 结构化HTML、PDF fallback、阅读顺序检查、章节 / 页码、表格 / 图注、必要图像 | 来源与版本可追溯；长文分段；全文门禁、不可摘要降级或前缀截断 |
| 新全文核查模块或总结角色任务 | 传统loss uncertain的有限核查，明确理论/迁移证据 | 不把摘要关键词当证明；review预算与失败队列和入选超额分别管理 |
| `state.py`、`service.py`、`cli.py` | 替换只 seen 字典为版本化阶段状态，保留部分成功和显式晋升事件 | 已选档位 / 已生成总结 / 实际通知呈现 / 投递结果独立；失败只重试对应阶段 |
| 新 Server酱 Turbo adapter | 借鉴 delivery 接口，新增发送、限次查询、配额、业务响应、脱敏 | 免费账号、每日1逻辑简报；unknown/readkey语义；不能复用无确认POST即成功示例 |
| 归档 / Git state adapter | 专用状态分支持久化JSON、验证总结、日期索引与不可变发送快照 | 提交成功后再副作用；不cacheonly；并发/冲突/失败恢复；无秘密或原始全文大文件 |
| `.github/workflows/daily-digest.yml` | 精简成每日/手动/回放工作流、15:17 Shanghai、标准Ubuntu、concurrency | state写所需contents权限；关闭Pages/id-token、离线translation和维护/反馈同步工作流 |

上游其他发送器、网页、反馈、多源可以保留代码以降低删改面，但不能在首版配置 / workflow 中自动执行。不要把“已复用函数”当作业务正确的证据，重点验证新行为。

## 3. 先固定契约，再做最小贯通

先定义基础 ID / 版本、selection 三态、intended tier、summary quality、delivery / render status、run覆盖、重试事件、配置指纹与成本记录。给状态 schema 版本和迁移方式；默认分支代码与专用状态分支由单run读取最新版本，不用独立函数自动提前mark sent。

第一条贯通路径用本地固定 metadata / body fixtures：规则 → select/light 或 select/full → 门禁 → 验证总结 → Markdown / JSON → mock投递 → stage checkpoints。三种业务输出都跑通：完整、轻量、拒绝；处理失败保持失败，不能转成拒绝。过程中只需用外部I/O边界 fake/mock，不写镜像实现的细碎测试。

阶段退出条件：可从任意已持久阶段恢复；失败投递不再调用总结；light已送不自动变full；同 ID 多路线只记录一次；dry-run不能影响正常状态。

## 4. 采集与恢复

实现 initial7d、后续最多14d滚动覆盖、交叉分类与摘要路线；保存覆盖完整性、API分片/页进度。arxiv库请求序列不并发；日期/分类拆分应避免API结果上限漏文。

用带第3页有效文章、重复ID、分页中断、API迟到可见、20天漏跑的 fixtures 验证；校准上游客户端的异常空页和重试，避免外层与内层重试倍增。到容量/时间保护时明确剩余覆盖，而不是mark no-results。

阶段退出条件：跨页候选完整、迟到文章发现、首轮下界正确、14天超界有人工恢复信息，检查点推进与模型/通知独立。

## 5. 正文、图表和总结质量

用固定版本代表论文实际阅读材料建立来源 fixtures：LISA做通用轻量样例，MediSee、PRS-Med v4与ARIADNE做正文理解和任务归类样例；不把论文名称当日常必要词。用传统loss摘要不足、纯理论无实验、图表唯一实验数字、双栏乱序、关键附录位于后部作为边界样本。

先完成正文门禁和定位，再加入 DeepSeek adapter。采用已确认 high/max 工程映射，单独控制输出和思考容量；开发时核查官方 schema、图像/JSON/完成状态。仅有图像输入能力文档不代表质量通过；图表数字与附近文本、表号/页码对应后才进最终总结。

长文按章节证据抽取/聚合；不完整覆盖不声称阅读全文。限制缓存内容和公开状态，避免把raw全文、图像、provider reasoning trace提交进public分支。首次有效总结写检查点后，不因推送失败重复付费。

阶段退出条件：五段总结保留关键方法/数字、出处真实、不编未报告内容；失败正文不摘要替代，损坏或截断JSON不推送；传统loss不确定有限全文核实，核实后才完整。

## 6. 两档与历史行为

工程默认full_daily_limit5，上限10；入选超额转title/link轻量，不自动明日补总结。light结果与内部理由分开保存。用于回放的历史ID默认dry-run，覆盖日期窗口但不重置正常去重。

实现已light_sent的显式人工晋升：沿同ID记录事件，不自动启动；默认配置/模型/prompt变更与论文修订不重推。区分 full business tier、validated summary 和 archive_link_only通知呈现，避免消息容量裁剪把完整记录降成无总结轻量。

阶段退出条件：2/8/13入选测试不同可配置额度；拒绝不混轻量，不确定不冒充入选；状态恢复不损害档位与一次推送原则。

## 7. 免费微信投递与归档

先以服务公开结构的 fixtures 验证接收、业务失败、queued、空wxstatus、已确认/unknown、返回损坏、超时与state写失败。POST前先持久化attempt_started/sending意图、快照关联与额度预留；sending不等于平台queued，崩溃后据此恢复unknown并保留尝试计数。发送预算统一覆盖正常日报、告警和补发，≤5/配置日界；最多3同run查询，部署核查查询是否也占配额与真实日界。readkey仅同run内存；下一run unknown复用旧验证内容/证据加入当日恢复分组，生成带recovery_of的新不可变快照，不覆写旧hash、不重调总结，并按实际条目保存送达与沿原交付链累计有限次数；无新结果也可只恢复旧简报。接受偶尔重复，不构建虚假的 exactly-once。

正文30,000UTF-8 bytes工程默认；按SPEC优先缩非必要字段和轻量清单，再按完整篇边界只给存档入口。先提交不可变快照并检查可访问URL，再发送。Secret canary验公共JSON、Markdown、日志、artifact和git提交；异常对象与签名URL不原样日志。

阶段退出条件：试用结束的免费账号仍能正常一条合并日报、点击详情读完整段落；容量例外诚实说明且完整存档可读；发送失败能复用总结恢复，配额/查询限制有界，unknown无凭据泄漏。

真实投递验证留到代码准备完成、用户配置Secrets的开发阶段。当前不注册账户、不付款、不调用付费LLM或推送接口。

## 8. GitHub Actions 部署与最终验收

新增精简workflow，用当前官方schedule timezone支持明确Asia/Shanghai 15:17；保留workflow_dispatch。标准Ubuntu runner，不使用付费larger runner。同组concurrency不取消正在保存状态的run；合理job timeout、依赖锁定、cache仅加速；artifact最小且有保留期。

将上游Pages部署、translation模型准备、feedback/state secret同步、发布/社区/季度维护等多余自动workflow停用。写权限仅为专用分支持久化所需contents，job不需要pages或id-token写权限。防止state push触发循环，记录fork启用Actions与长期无活动停用的运维步骤。

最终以 [SPEC验收矩阵](SPEC.md#9-验收矩阵) 给出离线 / 集成 / 真正免费账号端到端的分层报告。验证依赖安装、分页、多个恢复阶段、午夜额度边界、secret脱敏和档位行为；已通过的检查不无理由反复扩大测试。可交付物：可运行app、示例无Secret配置、部署说明、状态/归档结构、代表回放命令、验收报告及故障恢复说明。

离线验收通过后提供运行与Secret配置步骤，用户配置后按新开发对话的授权进行真实联调与部署，再完成端到端验收。若接口能力或服务配额与调研变化，先报告事实并调整适配，不擅自放宽正文质量、依赖会员试用或抹去思考差异。
