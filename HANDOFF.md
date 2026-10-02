# ArxivDaily 开发交接

> 当前开发进展已更新到 [DEVELOPMENT-STATUS.md](DEVELOPMENT-STATUS.md)。下面保留原规划交接记录；当前 `app/` 已有本地实现，不能按“尚未开发”覆盖它。上游固定源码导入、Git/GitHub及真实凭证联调仍未执行。

日期：2026-10-02（Asia/Shanghai）。供用户自行开启的新对话实际开发。需求确认已结束，Q13–Q18 已接受；最新覆盖为 DeepSeek“中等 / 极高”思考与 Server酱免费账号。请先读规格，不重复盘问已确定业务。

## 当前工作区与完成状态

当前目录 `C:\Users\24252\Desktop\ArxivDaily` 是规划工作区，根目录不是 Git 仓库，现有内容为文档与技能。本对话只完成调研、确认与文档；未 clone/fork、开发、运行第三方应用或应用测试，未调用付费 LLM、操作账号或实际推送。静态核查不等于运行验收。

用户要求所有临时文件放在当前目录内，覆盖 [handoff 技能](C:/Users/24252/Desktop/ArxivDaily/.codex/skills/handoff/SKILL.md) 的系统临时目录约定；下载、渲染、测试产物也放本工作区子目录。保留现有文档与技能。

未提供 API key、SendKey 或 readkey；用户在部署时自行填 Secrets，不从其他配置搜密钥，不要求聊天粘贴凭据。凭据是待部署材料，业务已达成共识。

## 阅读顺序与权威来源

| 顺序 | 文件 | 用途 |
| --- | --- | --- |
| 1 | [最终规格](C:/Users/24252/Desktop/ArxivDaily/docs/SPEC.md) | 已确认行为、边界、输出、恢复与验收；实现的主要依据 |
| 2 | [实施计划](C:/Users/24252/Desktop/ArxivDaily/docs/IMPLEMENTATION-PLAN.md) | 上游改造、阶段顺序、检查和交付 |
| 3 | [需求记录](C:/Users/24252/Desktop/ArxivDaily/docs/requirements.md)、[设计树](C:/Users/24252/Desktop/ArxivDaily/docs/decision-tree.md) | 用户决定及其来源，避免重新开启已关闭的前沿 |
| 4 | [术语表](C:/Users/24252/Desktop/ArxivDaily/GLOSSARY.md) | 任务、候选、入选、总结、投递等统一语义 |
| 5 | [基线 ADR](C:/Users/24252/Desktop/ArxivDaily/docs/adr/0001-mit-upstream-baseline.md)、[两档内容 ADR](C:/Users/24252/Desktop/ArxivDaily/docs/adr/0002-content-tiers-and-fulltext-gate.md)、[状态与送达 ADR](C:/Users/24252/Desktop/ArxivDaily/docs/adr/0003-public-git-state-and-delivery-tradeoff.md) | 难以逆转的取舍及依据 |

历史调研保留 proposed 建议；差异以最新用户决定、最终规格与 ADR 为准。代码组织、依赖、超时和容量等常规参数由开发给可配置默认值，不再询问用户。

## 二次开发入口

已接受基础为 [X-PG13/paper-digest](https://github.com/X-PG13/paper-digest)，核查固定提交 `8906f9a12309956913eab29dade75c01cb7d0771`，MIT 许可。详情及固定源码链接见 [基础项目调研](C:/Users/24252/Desktop/ArxivDaily/docs/research/base-projects.md)。

先检查适用 `AGENTS.md` 与文件。没有应用 checkout 时，默认 clone 到 `app/`，以固定提交建立可审阅基线并保留 LICENSE；已有 `app/` 则先检查 Git 状态与用户修改。不要覆盖根规划文档。

复用配置、日报、通知、Actions，替换自写 arXiv 客户端和摘要分析，新增全文/图表、两角色 LLM、Server酱与持久状态。上游不需要的多来源/网站/维护流程关闭；具体模块边界见实施计划，不能照搬其标题匹配、提前截断或 cache-only 状态。

## 最新覆盖提醒

- 官方 `https://api.deepseek.com` / `deepseek-flash` 两角色：终筛 `high`、总结 `max`，均 `thinking.type=enabled`。这是“中等 / 极高”的 provider 映射；`medium`、`xhigh` 实际都映射 `high`，最高预算须用 `max`，原 `none/low` 提议已覆盖。见 [规格模型章节](C:/Users/24252/Desktop/ArxivDaily/docs/SPEC.md#5-deepseek-两角色与内容质量)；[官方依据](https://api-docs.deepseek.com/api/create-chat-completion/)。图片接口不是原生 PDF 输入。
- Server酱首版用免费账号（当前 5 条/日、详情 1 天），试用/付费不能成为依赖；unknown 跨 run 按少漏优先有限恢复、接受极端重复，不保存明文 readkey。见 [规格微信章节](C:/Users/24252/Desktop/ArxivDaily/docs/SPEC.md#7-免费微信交付容量与-unknown-恢复)。固定 50 元月预算未采纳。
- 两档交付事件需区分，但正常共用基础 ID 已送登记；轻量升级仅显式人工操作，修订不重推。见 [规格生命周期](C:/Users/24252/Desktop/ArxivDaily/docs/SPEC.md#4-三态终筛有限核查与两档去重)。15:17、首次 7 天、自动补采 14 天及覆盖完整性见 [采集章节](C:/Users/24252/Desktop/ArxivDaily/docs/SPEC.md#3-采集与规则初筛)。

公开事实报告及直接 URLs 统一从 [需求记录的事实来源](C:/Users/24252/Desktop/ArxivDaily/docs/requirements.md#事实来源与工作边界) 进入。接口集成前复核上游版本、arxiv 4.x、DeepSeek 能力/参数/价格和 Server酱实际返回；事实复核不重开业务盘问，未实测行为不能写成验收通过。

## 建议技能

- 常规 Python 开发按 `AGENTS.md`、规格和计划，无须重新调用 grilling。
- 读 PDF、渲染页和核查图表证据时调用 `pdf:pdf`（[SKILL.md](C:/Users/24252/.codex/plugins/cache/openai-primary-runtime/pdf/26.909.12148/skills/pdf/SKILL.md)），临时产物仍留当前工作区。
- 用户主动改变关键业务时才按需调用 [grill-with-docs](C:/Users/24252/Desktop/ArxivDaily/.codex/skills/grill-with-docs/SKILL.md)；再转交开发时调用 [handoff](C:/Users/24252/Desktop/ArxivDaily/.codex/skills/handoff/SKILL.md)，引用产物、剔除秘密。

## 下一步与交付

按计划完成代码、适当测试、代表 ID 回放、离线/模拟 dry-run、配置和 Secrets/Actions 设置说明；缺 Secrets 仍完成所有可独立验证工作，凭据配置后联调，外部操作依新会话授权及工具权限执行。用户自行开新聊天，复制 [START-HERE.md](C:/Users/24252/Desktop/ArxivDaily/START-HERE.md) 即可。
