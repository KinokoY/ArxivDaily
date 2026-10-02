# 需求设计树

状态：**需求共识已达成；文档交接已完成并验收；尚未开发**。日期：2026-10-02（Asia/Shanghai）。第一轮 Q1–Q12 已回答，第二轮 Q13–Q18 已全部接受；用户对 Q15 思考等级、Q16 免费账号的最新覆盖已记录。

## 设计前沿

**为空。** 已遍历本轮关键业务取舍，不再为常规实现参数、部署凭证和实际测试开启新一轮问询。定稿约束见 [requirements](requirements.md) 与 [SPEC](SPEC.md)，工程顺序见 [IMPLEMENTATION-PLAN](IMPLEMENTATION-PLAN.md)，交接入口见 [HANDOFF](../HANDOFF.md)。交接文件均在当前工作目录完成并验收。

## 已确定的根节点

- Python + arxiv Python 库；在 MIT `paper-digest` 基础上二次开发。
- 摘要规则宽初筛 → Flash 中等思考严格终筛 → 合格全文/必要图表与 Flash 极高思考总结 → 免费 Server酱微信日报。
- 独立标题+链接轻量档位，用于通用无 RL/DPO 推理分割；不自动进入全文总结。
- GitHub Actions 每日 15:17；单用户配置批处理；代码、兴趣和历史公开，状态专用分支，所有凭据保密。
- 新文一次、修订不重推、首回溯 7 天；少漏优先、极端情况偶尔重复、最多 14 天自动补采。
- 所有文件与临时文件位于当前工作目录；实际开发由用户自行开启新对话。

## 已结案的第二轮分支

| 问题 | 状态 | 用户最终决定 |
| --- | --- | --- |
| Q13 | accepted | 四类兴趣 + 有限全文核查；独立轻量标题/链接档位采纳 |
| Q14 | accepted | 关键词只摘要；标题展示/LLM 输入；分类可扩展与交叉命中，无正文关键词规则 |
| Q15 | accepted with user override | 官方 Flash 两角色；终筛中等、总结极高；原 none/low 与 high 推荐被覆盖，自管余额，不设 50 元/月 |
| Q16 | accepted with user override | 免费 Turbo 微信详情 + 公开 GitHub Markdown 存档；首版不依赖会员/试用，之后按体验迭代 |
| Q17 | accepted | MIT paper-digest 二次开发 + arxiv 库 + 公开状态专用分支 + 15:17 |
| Q18 | accepted | 少漏优先、极端重复、最多 14 天补采、有限重试与原提议验收 |

[第一轮历史](clarification-round-1.md)与[第二轮历史](clarification-round-2.md)保留原问题/推荐，附最新用户回答；历史推荐不能覆盖定稿。

## 留给工程交接的工作

- API 等级映射已由主代理与 DeepSeek 代理复核：中等 `high`、极高 `max`，两角色显式 `thinking.type=enabled`；用户自然语言意图与工程映射由 SPEC 明确，不将两种预算静默合并。实际端点行为由部署测试验证。
- 参数默认值、依赖锁定、全文提取与长文处理、排序/限额、状态 schema、并发/重试与验收实现，依 SPEC/IMPLEMENTATION-PLAN 交新开发对话。
- Secret 配置与实际 API/投递测试由部署阶段完成；目前没有密钥或外部账号动作。
- 免费版测试不使用付费/试用权益。公开 state 不保存 SendKey/readkey 或带凭据 URL；只保留非敏感结果/未知标记，明确未知状态恢复，不扩外部服务或要求用户选加密算法。

## 文档交接状态

需求已结案，文档交接已完成并验收：

- [SPEC](SPEC.md)：最终约束、行为与验收。
- [IMPLEMENTATION-PLAN](IMPLEMENTATION-PLAN.md)：下一开发对话的实施顺序。
- [基线 ADR](adr/0001-mit-upstream-baseline.md)、[两档内容 ADR](adr/0002-content-tiers-and-fulltext-gate.md)、[状态与投递 ADR](adr/0003-public-git-state-and-delivery-tradeoff.md)：必要决策依据。
- [HANDOFF](../HANDOFF.md)：新对话入口与最新覆盖。

尚未开发。事实来源索引在 requirements；研究报告记录当时事实与建议，最新选择以用户回答和 SPEC 为准。

不自动创建新的开发聊天；主代理最终提供可复制的启动代码块。原始临时抓取文件已清理，保留必要研究报告和公开套餐 JSON 证据。
