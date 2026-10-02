# 新对话启动提示

在当前工作区开启新对话，将下面整段复制过去。业务已确认；先完成实际二次开发与本地验证，部署阶段再使用用户自行配置的凭据联调。

```text
请开始实际开发 ArxivDaily，先读 HANDOFF.md、docs/SPEC.md 和 docs/IMPLEMENTATION-PLAN.md，并沿交接索引读取需求、术语和 ADR。
业务已确认，不重新 grilling 已确定事项；常规实现细节由你处理并给可配置默认值。
检查适用 AGENTS.md；根目录不是 Git 仓库，默认把 X-PG13/paper-digest 固定提交 8906f9a12309956913eab29dade75c01cb7d0771 clone 到 app/ 作为基线，保留 MIT LICENSE 和规划文档；已有 app/ 先保留其修改。
所有临时文件留当前工作区。按 SPEC 实现 Python/arxiv、摘要规则与 LLM 终筛、全文/必要图表总结、Server酱免费日报、公开 Markdown、持久状态和 Actions。
DeepSeek 官方 Flash 两角色采用 high/max，显式启用思考；这是“中等/极高”的参数映射，medium/xhigh 实际均映射 high。
先完成代码、适当测试、代表 ID 回放、离线或模拟 dry-run 与部署配置；缺 Secrets 时完成全部不依赖凭据的工作，并区别已验证与待联网验证。
我之后自行填 Secrets，不从其他配置搜密钥、不要求聊天粘贴凭据；配置后按本会话授权和实际工具权限联调。
适合时优先委派子代理并验收。完成后报告变更、验证结果、Secrets/Actions 设置与最终联网验收步骤。
```
