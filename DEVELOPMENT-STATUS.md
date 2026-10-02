# ArxivDaily 当前开发状态

更新：2026-10-03（Asia/Shanghai）。应用在 `app/`，实际 Actions 在根 `.github/`，原规划文档、ADR、术语表与技能保留。

本轮用户已授权 Git 初始化、Actions 适配及少量真实 DeepSeek 调用。根仓库已初始化为 `main`，Git 可用；没有设置根/全局提交身份、创建根提交、配置远端或推送 GitHub。仅临时测试仓库使用局部测试身份。本地秘钥文件在 Git 忽略目录，公开文件检查不含秘钥值。

98 个公共文件已暂存供审阅，暂存区无两把真实秘钥，原始上游文件与来源清单哈希保持一致，暂存格式检查通过。已修复本轮沙箱创建 Git 目录造成的普通 Windows 用户所有权检查，无需用户设置全局信任例外。

- 可运行模块：摘要初筛、arxiv 4 分页与窗口恢复、两角色 DeepSeek、三态判断、全文/图表门禁、五段总结与证据、轻量档、持久阶段状态、免费 Server酱 adapter、不可变归档、人工恢复/晋升/重投。
- 已有本机 conda `ml` Python 3.12.9，工作区依赖在 `app/.runtime/`；全部新临时与回放产物留本工作区。`app/scripts/run-local.ps1` 是本机入口。
- 四篇固定版本代表论文元数据和八份 HTML/PDF 保持原来源。人工回放仍是 mock；另外已使用真实 DeepSeek 做 LISA/MediSee 两次终筛与 MediSee 正文/图像总结的小规模联调，记录成功和失败尝试。原文/PDF/图像不进入公开仓库。
- 固定 `paper-digest@8906f9a12309956913eab29dade75c01cb7d0771` 的必要源码已导入 `app/arxivdaily/_vendor/paper_digest/`，原许可与源码逐字节哈希匹配；上游定向基线 67 项通过。实际复用基础 ID、作者/交叉分类规范化与重复元数据合并，保持本应用的严格版本契约。wheel 已包含这些源码及原 MIT notice，并经隔离安装验证。
- 根 Actions 自动准备公开配置和归档 URL，首次实发只用空 `state.json` 初始化独立状态分支；手工默认 dry-run。publisher 已在本地 bare Git remote 验证提交、推送、远端 OID、冲突保护和不可变快照；公开 URL HTTP 校验在测试中模拟，真实 GitHub/Ubuntu runner 尚未运行。
- 新增 Git 候选文件检查、工作区私有秘钥忽略与发布时秘钥形态阻断；本轮 Server酱发送 **0 次**。用户官网测试已收到微信，应用发送/查询、真实免费详情和公开历史链接尚待验证。

最新结果以 [验收报告](app/reports/ACCEPTANCE.md)、[运行说明](app/README.md)、[部署说明](app/docs/DEPLOYMENT.md) 和 `app/reports/*.json` 为准。继续开发前读本文件及上述报告，再沿原 HANDOFF/SPEC/ADR 索引核对业务，避免覆盖当前 app。

下一阶段需要用户指定 GitHub 账号/目标公开仓库及相应推送授权、填写提交身份与仓库 Secrets；随后验证真实状态分支、Ubuntu Actions、免费微信发送/查询和手机详情。当前本地开发无需用户额外配置。只使用明确提供的运行凭证，不搜索其他配置；不重复付费生成已有成功结果。
