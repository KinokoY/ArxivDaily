---
status: accepted
---

# 以 MIT Paper Digest 为二次开发基线

用户要求基于现有项目开发；指定的 llm-arxiv-daily 实际只生成论文目录且固定提交没有明确许可，而 MIT 的 paper-digest 已具备配置、通知、归档和自动运行外围模块。采用 `X-PG13/paper-digest@8906f9a12309956913eab29dade75c01cb7d0771`，保留许可与归属并替换 arXiv 客户端、LLM与正文路径，接受其比单脚本更复杂的基线成本；后续改换基础会牵涉模块、测试及历史维护来源，故记录该取舍。

[核查证据](../research/base-projects.md)，[实现范围](../SPEC.md)。
