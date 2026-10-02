# ArxivDaily 下一开发会话交接

更新：2026-10-03（Asia/Shanghai）。本轮完成根 Git 初始化、固定上游元数据复用、Actions 适配和有限真实 DeepSeek 联调。下一阶段是实际 GitHub 部署与免费微信端到端验证。

业务已确认，常规技术细节自主处理。全部临时文件留当前工作区，本地优先 conda ml / Python 3.12.9 + app/.runtime。适合的独立工作优先委派 GPT-6 Sol high/xhigh，约定文件所有权，由根代理审阅验收。

## 阅读索引

1. 本文、[开发状态](DEVELOPMENT-STATUS.md)、[分层验收](app/reports/ACCEPTANCE.md)。
2. [SPEC](docs/SPEC.md)、[实施计划](docs/IMPLEMENTATION-PLAN.md)、[术语](GLOSSARY.md)；[基线 ADR](docs/adr/0001-mit-upstream-baseline.md)、[两档 ADR](docs/adr/0002-content-tiers-and-fulltext-gate.md)、[状态 ADR](docs/adr/0003-public-git-state-and-delivery-tradeoff.md)。
3. [应用运行](app/README.md)、[部署](app/docs/DEPLOYMENT.md)、[恢复](app/docs/OPERATIONS.md)、[上游](app/UPSTREAM.md)、[接口](app/INTERFACES.md)、[API 事实](app/docs/API-VERIFICATION.md)、[第三方许可](app/docs/THIRD-PARTY.md)。
4. 原 [HANDOFF](HANDOFF.md) 保留需求/调研来源，旧“尚未开发”描述不覆盖当前状态。

## 当前实现与 Git

- 根 main Git 仓库已初始化；尚未创建根提交、配置根提交身份、添加远端或推送 GitHub。Git 可用，gh 未安装。临时 Git 测试使用命令局部身份，没有改用户全局配置。
- 已暂存 98 个公共文件供审阅，未提交。暂存区逐文件核对无两把真实秘钥；原始上游 blob 和 fixture 所引用来源清单的精确哈希均成立，git diff --cached --check 通过。来源清单需保持 -text，不能自动换行后使 fixture 哈希失效。
- 本轮创建的 .git 目录所有者已恢复为正常 Windows 用户；普通用户 Git 可用。离线沙箱若因不同执行身份出现 dubious ownership，可只在该命令用 git -c safe.directory=<当前工作区>，不必更改全局信任配置。
- 固定 paper-digest@8906f9a12309956913eab29dade75c01cb7d0771 已取得并验证，暂存 checkout 在 tmp/upstream-staging。必要源码在 app/arxivdaily/_vendor/paper_digest，原 MIT LICENSE 与五个源文件 byte-for-byte 匹配，哈希在 ORIGIN.json。
- arxivdaily.upstream 实际复用上游 Paper 的基础 ID、作者/交叉分类规范化与重复合并；collector 接入，仍使用 arxiv 4 的完整分页、摘要规则和严格版本契约。不能声称整个上游应用都启用；外围接口的实际取舍见 UPSTREAM。
- 最终 wheel 已纳入最新 parser/提示、vendored 源码、原许可和来源哈希，经构建和隔离安装验证。来源与 Git 暂存内容按原始提交 blob 校验，.gitattributes 防止 Windows 自动换行改变 vendored 字节。
- Actions 入口是根 .github/workflows/daily-digest.yml；旧 app/.github workflow 已移除。工作目录 app，15:17 上海，标准 Ubuntu，contents:write，同一 concurrency、不取消运行，手工默认 dry-run（仍收费，只是不发送）。
- workflow 保留已有公开 config.toml，缺失时从示例生成，仅为空时填 raw archive URL；首次定时/显式 send 用仅 state.json 的独立根提交创建 arxivdaily-state。dry-run 不创建分支；不得把本地模拟状态复制为正式状态。
- publisher 已用本地 bare remote 验证 bootstrap、commit/push/OID、冲突和不可变快照。测试中的公网 HTTP raw URL 校验是模拟，不代表 GitHub/Ubuntu 验收。

## 真实模型与质量修复

- high 终筛两篇：LISA select/light、MediSee select/full，均非 RL/DPO，与预期一致。不扩展成全量精度测试。
- max 总结使用固定 MediSee HTML 与两张同版 PDF 图表页（物理 3、4）。三次总结响应：首次应用校验失败；第二次结构与证据通过但实验过于笼统；第三次保留表格数值。结果、usage、失败审计在 app/reports/live-api-smoke.json，没有 provider envelope 或隐藏推理。
- 首次请求被网络沙箱 PermissionError 阻止；授权工具网络权限后正常，不能据此判断 key 无效。保留该记录，没有冒充零费用的成功响应。
- 修复最后一次请求丢失安全验证错误码的问题；总结提示强调句数、精确引文、数值、比较对象和范围。最后真实响应来自 v3；当前 v4 额外强调少量带标签指标，没有再付费测试措辞精简，test_llm 离线通过。
- 修复 LaTeXML 公式布局 table 被误计为数据表：表号取父 figure caption，MediSee 为 Table 1–6；公式仍在方法定位，无编号表用 HTML ID/local marker。
- 根代理看过同版 PDF 第 6 物理页 Table 1，核对 val/overall Dice：MediSee(ft) 59.4、LISA-7B 31.6。可读样例精简模型数值行，并恢复“超过 200K”限定；审阅版和原模型结果分开保存，不能把人工精简说成模型原始输出。样例是 app/reports/live-sample-digest.md。
- 五个服务端正常响应（两次终筛、三次总结）的已返回 usage 按配置高峰价估计合计 0.43453 CNY，不是精确账单。不要为重复验收再生成成功阶段。
- Server酱本轮发送 0 次。用户官网测试已在微信收到；应用 queued/wxstatus、查询扣额、平台日界、免费详情及公开历史仍待部署验证。

## 验证与公开边界

- 最终 pytest：124 主测试 + 38 参数子测试 = JUnit 162，失败/错误 0；本地记录 app/reports/final-2026-10-03.xml 已忽略。最后措辞精简后 test_llm 21 项通过。
- 上游定向基线 arxiv_client 15、config 26、digest 26，共 67 通过；没有宣称整个上游 suite 通过。
- 四篇来源重新审计及人工 fixture 回放仍 3 full + 1 light、错误 0，不是四篇真实模型总结。原始材料没有重新下载。
- 根 .gitignore 忽略 .secrets、.env*、runtime、state、runs、tmp、build、原始 HTML/PDF/图像；scripts/check_public_files.py 检查公共 Git 候选和误强制暂存的私有路径，输出仅文件名。状态发布也阻断秘钥形态与配置值。
- 运行凭证仅在 Git 忽略的本地文件；不复制进公共文档、提交、日志或 artifact。部署用原生 Actions Secrets，readkey 仅同轮内存。
- 任意 PDF 版式、图像专属数字准确率、全部兴趣路线真实精度未作普遍保证。样例数字来自 HTML 表格并经 PDF 核对，不能声称图像 OCR 准确性已测完。

## 下一步与用户配置

1. 指定 GitHub 账号/目标公开仓库（owner/repo）、推送或创建授权与提交身份；不虚构用户身份，不搜索机器其他凭据配置。
2. 在授权目标仓库发布代码，设置两个原生 Actions Secrets。归档 URL 自动生成；无需另装 Python、手工建状态 JSON或重新确认需求。
3. 进行一次有界手工联调，核实真实状态提交先于模型/发送、raw 快照公开可读、Ubuntu 锁定依赖和恢复。不能以 mock confirmed 建正式已送登记。
4. 用一份合并简报验证免费 Server酱发送/有限查询，考虑用户官网已用配额，控制最多 5/日；用户手机确认详情和公开历史链接。无目标仓库时不发缺长期链接的测试简报。
5. 更新分层验收；不清空 state、伪造 confirmed、摘要降级、降低门禁或改 high/max 让检查通过。

已授权范围和凭据在本会话持续有效；新会话以用户给出的目标/授权为准，不把交接待办当成额外发布授权。
