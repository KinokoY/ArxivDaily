# ArxivDaily 分层验收

## 2026-10-03 增量验收

根 Git 已成功初始化为 main，提交身份/远端尚未配置，未创建根提交或发布 GitHub。本轮在 conda ml / Python 3.12.9 下推进既有应用，不覆盖既有成功路径。

| 层级 | 实际证据与结果 |
| --- | --- |
| 应用测试 | 最终全套 124 主测试 + 38 子测试通过，JUnit 合计 162，失败/错误 0；本地记录 final-2026-10-03.xml。最后提示措辞精简后，test_llm 21 项定向通过。 |
| 固定上游 | SHA 8906f9a12309956913eab29dade75c01cb7d0771 已核对，原 MIT notice 和五个必要源文件逐字节哈希匹配。arxiv_client/config/digest 定向基线共 67 项通过；不是整个上游 suite。基础 ID、作者/分类与重复元数据处理已实际接入 collector。 |
| 打包 | 最终 wheel 包含最新 parser/提示、vendored 源码、LICENSE/README/ORIGIN，隔离安装后无需源码 checkout 即可加载适配器；见 package-check-2026-10-03.json。原许可和源码按固定提交 Git blob 校验，换行规则保护这些原始字节。 |
| Git 状态事务 | 在工作区内 bare remote 真实验证独立 state.json 根提交、commit/push、远端 OID、冲突停止和快照不可变；公网 raw URL 在该测试中模拟，未运行 GitHub Ubuntu。 |
| Actions | 移到根 .github；app 工作目录、15:17 上海、同 concurrency、最小 contents 写权限；自动补公开配置/URL，保留已有配置，首次实发自动 bootstrap。YAML、8 个 Bash block 语法与配置生成通过本地检查。 |
| 来源/解析 | 四篇固定源未重新下载；重新审计 HTML/PDF 门禁及人工 fixture 回放仍为 3 full + 1 light、错误 0。修正 LaTeXML 方程 table 的伪表号；MediSee 实际 Table 1–6，方法定位保留公式。 |
| 真实终筛 | 两次 high 请求正常 stop，LISA select/light、MediSee select/full，均非 RL/DPO；不是全部路线精度验证。 |
| 真实正文与图像 | MediSee max 使用合格固定版 HTML 与同版 PDF 物理 3、4 页两张图。三次总结响应中，首次应用校验失败；第二次结构通过但漏关键数字；第三次保留表格数值。没有隐藏 reasoning 或原始 provider envelope 落盘。 |
| 数值审阅 | 根代理实际查看同版 PDF 物理第 6 页 Table 1，核实 val/overall Dice 59.4（MediSee ft）与 31.6（LISA-7B）。可读样例经记录的人工精简；原模型结果保持独立。不能声称 image-only 数字精度已通过。 |
| 秘密 | 本地秘钥和全部运行/原文产物被 Git 忽略；公共候选文件检查和误强制暂存秘钥 canary 测试通过；状态 publisher 在无匹配运行秘钥时也阻断凭据形态。 |
| 微信 | 本轮发送 0 次。用户官网测试已收到微信；应用真实发送/查询、免费详情与公开归档入口没有验收。 |

真实请求、usage、失败审计和原模型输出见 [live-api-smoke.json](live-api-smoke.json)，经来源核对的可读简报见 [live-sample-digest.md](live-sample-digest.md)。五次服务端正常响应按配置高峰价估计合计 **0.43453 CNY**，不是账单；初次沙箱阻止请求的 unknown-usage 记录仍保留。

当前提示 v4 只在 v3 基础上补充少量、带明确指标标签的数值表达，未再付费测试措辞精简。最后实际响应是 v3；样例实验段精简由根代理核对原 PDF 后完成，记录在 manual_review_result，不能描述为模型未经修改的输出。

尚需用户指定 GitHub 目标公开仓库及相应授权、配置提交身份和原生 Actions Secrets，然后验证真实 Ubuntu、公开 raw 快照、状态检查点与一次有界免费微信合并简报。后续不重复付费生成已成功阶段，不使用本地 mock 状态建立正式已送登记。

发布前暂存 98 个公共文件，逐文件确认不含两把真实秘钥；六份原始上游文件与固定提交 blob 一致，来源清单在 Git 中仍满足 fixture 精确哈希，暂存格式检查通过。Windows Git 目录所有权已修复；没有改变用户全局 Git 信任或身份。

## 2026-10-02 原本地验收记录

日期：2026-10-02（Asia/Shanghai）。本机 conda ml / Python 3.12.9。范围为不使用 Git/GitHub 的本地开发、公开来源准备、离线/模拟测试及部署文件。

## 实际验证

- pytest：109 个主测试、38 个参数子测试通过（JUnit 合计 147）；失败 0、错误 0。机器记录见 tests.xml。
- 四篇代表论文的真实 arXiv 元数据和八份固定版本 HTML/PDF 已下载，记录来源、时间、字节数与 SHA-256；四份 HTML 和四份 PDF 均通过当前结构/顺序门禁。
- 同版本 PDF 关键页已渲染核查；HTML 优先路径向总结角色提供必要图表图片，按物理页去重。实际 HTML→PDF 图表定位、图片输入 payload、PDF 回退及 Windows 文件关闭/删除均有测试。
- 代表回放：完整档 3、轻量档 1、错误 0；四次脚本化终筛、三次脚本化总结。校准 fixture 为人工依据正文编写，不能称为 DeepSeek 实测通过。
- 隔离检查（ml Python -I -S）关闭继承 site-packages，仅从 app/.runtime 导入所需依赖；代表回放 3 full + 1 light、无错误。Pillow 与 tzdata 已显式锁定，避免本机环境掩盖部署缺项。
- 构建和本地安装 wheel 通过；GitHub Actions YAML、专用状态 publisher 的冲突、不可变快照、白名单与 canary 通过静态或 mocked 验证。未执行任何真实 Git/GitHub 操作。

## 验收矩阵

| 规格场景 | 本地证据与结果 |
| --- | --- |
| 仅标题命中、交叉分类、缩写/连字符、路线 OR | rules/collection 测试通过；标题默认不产生候选 |
| 250 条跨页、重复 ID、第三页中断 | 实际 arxiv 4 Client + 合成 feed 通过；保留已发现条目、不推进不完整窗口 |
| 迟到可见、7/14 天、漏跑 10/20 天 | 窗口和缺口测试通过，提供日期补采；达到候选容量后继续扫描未发现 ID，旧记录不阻塞恢复 |
| 2/8/13 入选、5/10 完整额度 | 数量矩阵通过；超额 light，不形成次日自动总结队列 |
| 通用无 RL、医学监督、DPO/PPO、传统 loss | 人工校准回放/负例通过；LISA light、MediSee/PRS-Med full且非RL、ARIADNE医疗结构DPO+RL；真实终筛精度待联调 |
| 三态、不确定有限核查、API坏JSON/截断 | 保持处理失败或 uncertain，不伪造 reject；正文理论/迁移证据校验有测试 |
| 全文404、关键结构缺失、空白/乱序PDF | 保持失败待恢复，不用摘要替代；可恢复的清晰双栏/跨宽图布局通过 |
| 长文后部/附录、图表证据、数字 | 分块全覆盖、块缓存、精确定位/数字/来源校验通过；摘要唯一证据被拒绝；image-only数值准确性待真实模型验证 |
| 修订/改配置、已light、显式晋升/重投 | 去重与事件测试通过；显式 promote只light→full，resend复用已验证内容 |
| 已总结推送失败、unknown/崩溃、混合恢复 | 复用总结、新快照关联旧快照、原链累计次数；发送前意图与额度写入，通过故障注入 |
| 免费预算、午夜、长度 | 日报/告警/恢复统一≤5；查询独立有界；慢publisher跨午夜暂缓POST并释放未用额度；UTF-8整篇裁剪通过 |
| 秘密、异常/HTTP日志、public artifacts | 模拟canary未进入公共状态、Markdown、结果或HTTP日志；readkey仅运行时内存，恶意收据不能展平成pushid |
| 无结果/部分失败/失败、dry-run | 分层报告、合并告警、持久未完成阶段；默认隔离，不改正常游标/配额/已送登记 |
| 超界人工恢复、缺少凭据 | 指定ID有限重试保留历史；投递专用恢复不要求DeepSeek key；不具备实发前置条件时提前失败 |

## 可复现入口

参见 ../README.md。离线命令不调用真实模型或微信；报告里的 confirmed 来自 mock。

```powershell
& ./app/scripts/run-local.ps1 replay --ids 2308.00692v3 2504.11008v2 2505.11872v4 2603.19169v1 --now 2026-10-02T07:17:00+00:00 --report reports/representative-run.json
$env:PYTHONPATH = "$PWD\app\.runtime;$PWD\app"
& "$env:USERPROFILE\anaconda3\envs\ml\python.exe" -m pytest app/tests -q
```

sample-digest.md 是同次回放的完整可读产物，原发送快照仍不可变；representative-source-audit.json 为可复现的来源/门禁审计。unknown-first.json 与 unknown-recovery.json 展示下一轮补发复用总结。

## 原阶段未执行项（最新进展见上方增量验收）

1. 固定 paper-digest SHA 的真实导入、原 MIT notice 保留、外围接口复用/对齐与上游基线测试。当前 app 是独立应用层，不能声称已经完成上游二次开发；见 ../UPSTREAM.md。
2. Git/GitHub 公开代码库、状态分支真实事务、冲突网络条件、Ubuntu runner 与 Actions 的运行验证。
3. 真实 DeepSeek 的参数、返回、费用、终筛精度、全文解释与视觉质量；四篇真实模型回放后按正文复核。
4. Server酱免费账号过试用后的真实 wxstatus、查询计数/平台日界、微信详情长度、投递与归档入口。

任意 PDF 版式和图像专属数值未作普遍保证；不确定/缺失/损坏材料仍应失败待恢复。微信受理不等于已读，发送与远程状态不存在跨服务事务；不可消除的极端重复边界已保留 unknown 与有限恢复。

## 原阶段用户配置说明

复制 config.example.toml 为 config.toml，配置 archive.public_base_url；只在运行环境/Actions Secrets 填 DEEPSEEK_API_KEY 和 SERVERCHAN_SENDKEY，不在聊天或配置文件写明文。允许 Git/GitHub 阶段后按 ../docs/DEPLOYMENT.md 完成上游、状态分支与 Actions，再小规模真实联调。当前没有收费接口调用或真实微信发送。
