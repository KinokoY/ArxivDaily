# 部署与恢复（准备稿）

项目已定向导入 `X-PG13/paper-digest@8906f9a12309956913eab29dade75c01cb7d0771` 上游，保留原 MIT 许可与归属；上游定向 67 个基线测试通过。真实 DeepSeek 小样本联调与本机 live CLI 的 GitHub/微信贯通已完成，累计本轮发送一条正常合并简报；原模型输出、失败尝试和早期人工审阅样例分别记录。Ubuntu Actions 因账户锁未启动，本地结果不能代替 hosted runner 验收。

最新部署在 [KinokoY/ArxivDaily](https://github.com/KinokoY/ArxivDaily)：代码、公开 config.toml、原生两个 Secrets、正式 arxivdaily-state 已就绪。本机同一 CLI 完成真实两 ID 贯通及一次微信发送/查询，公开归档验证通过；手机详情待确认。首次 hosted Actions 在步骤开始前被 GitHub 账户 billing issue 拒绝，需要用户在 [Billing](https://github.com/settings/billing) 解除账户锁；不要靠改业务门禁或反复重跑来处理该账户问题。解锁后再验证 Ubuntu，已有送达记录和总结会复用，普通重跑不会重发这两篇。

## 准备

1. 将根工作区作为**公开** GitHub 仓库发布；可执行应用在 `app/`，实际 workflow 在仓库根 `.github/workflows/daily-digest.yml`。首个定时或显式 `send` 运行会自动创建仅含初始 `state.json` 的独立 `arxivdaily-state` 根提交；若同名远端分支已存在，直接使用它。不要从默认分支复制整份代码来初始化状态，也不要手工覆盖状态文件。手动 dry-run 不创建状态分支。
2. workflow 使用仓库里已有的公开 `app/config.toml`；若没有该文件，才从 `app/config.example.toml` 生成。它仅在 `[archive].public_base_url` 为空时自动填入 `https://raw.githubusercontent.com/OWNER/REPO/arxivdaily-state`，不覆盖已有自定义配置。本地运行可以自行复制示例配置并填写公开兴趣与参数；应用会在根地址后拼接 `archive/YYYY/MM/DD/<digest-id>.md`。配置里的 `sendkey_env` 与 `api_key_env` 仅写环境变量名称，不写密钥。
3. 在仓库 Actions Secrets 中设置 `DEEPSEEK_API_KEY` 和 `SERVERCHAN_SENDKEY`。请用户在自己的账户页面创建并填写；不要把凭据贴进聊天、提交、日志、Actions artifact 或公共状态。Server酱使用 Turbo `SCT` SendKey 和免费微信服务号通道，手机需关注对应服务号。免费卡片可能只显示标题；点击详情读 Markdown，长期历史以公开存档为准。[官方发送接口](https://sct.ftqq.com/docs/integrations/python/)及[免费额度与详情期限](https://sct.ftqq.com/docs/getting-started/faq/)可供部署时复核。
4. 在仓库 Settings → Actions 中允许 workflow 运行，并允许工作流使用具备仓库内容写入权限的 `GITHUB_TOKEN`。对 fork，先确认其 Actions 已启用；长期无活动时检查 schedule 是否被自动停用。workflow 自身只请求 `contents: write`，不申请 Pages 或 OIDC 权限。真实运行会先确认仓库可匿名公开读取，并扫描已提交文件中的凭据形态；不通过则在付费调用和发送前停机。

根目录的 `daily-digest.yml` 使用 GitHub Actions 官方支持的 `timezone: Asia/Shanghai`，每天北京时间 **15:17** 调度，另可手工运行。调度可能延迟。所有运行共享 `arxivdaily-state` concurrency 组且不取消正在运行的任务。workflow 从默认分支读取 `app/`，从状态分支 checkout 到 `app/.state`，安装 Python 3.12 的锁定依赖，在 `app/` 工作目录以显式 `--send` 运行定时日报，并通过 `--checkpoint-command` 在付费模型调用与推送等副作用前提交检查点。pip 缓存与应用运行临时文件使用工作区内的 `app/tmp/`。手工运行可选 `daily`、带 ID 的 `replay`、带起止日期的 `backfill`，以及对已有状态按 `retry_stage` 和 ID 执行的 `retry`。手工 `send` 默认关闭，此时以 `--live` 获取真实论文并调用已配置的付费分析接口，但在 `app/runs/` 隔离空间 dry-run，不推送、不修改正常游标和送达登记。只有明确打开 `send` 才调用带发布检查点的实发路径。若分支尚不存在，普通 dry-run 从空状态启动；`retry` dry-run 因缺历史状态而明确失败。报告仅上传脱敏的 `app/reports/run.json`，artifact 保留 3 天；job summary 不列论文内容或 Secrets。专用状态分支的 push 不会触发这个仅有 `schedule`、`workflow_dispatch` 的 workflow。

手工 `retry` 只针对状态分支里**已有**的基础 arXiv ID，必须选择先前尝试过的阶段：`selection` 重试终筛，`body` 重试正文质量门禁，`review` 重试不确定项核查，`summary` 重试正文总结，`delivery` 只恢复已有 `pending_digest` 的投递。前四类仍遵守阶段超时、费用和正文证据门禁；`delivery` 复用已验证总结，不重付总结费用。默认关闭 `send` 时，CLI 从 `.state/state.json` 复制到隔离目录检查恢复路径；如果该状态文件不存在，任务明确失败。打开 `send` 后才修改共享状态并可能发送，未知投递补发仍可能重复，且与日报和告警共享免费 5 条/日预算。人工恢复记录原尝试次数；投递链的原次数不被清零，单次人工授权只扩展有限尝试。

`--promote` 是另一种显式操作：它针对**已送轻量档**的入选论文新增完整档事件，需要正文门禁和验证总结，不等于重试失败阶段，也不会由修订或配置变化自动触发。当前 workflow 没有晋升输入；在配置好公开归档和同步 publisher 后，可通过 CLI 指定 `run --promote <基础 arXiv ID> --send --checkpoint-command <发布命令>`。先在隔离环境核查目标记录和成本，再进行实发；不要求在聊天中提供凭据。

## 免费发送预算与结果

正常每日只发一份合并 Markdown 简报。应用按 `Asia/Shanghai` 配置日界，将日报、告警、补发共享计算，每天最多 **5 次发送尝试**；POST 超时也占一次尝试，不在同一次调用中盲目重发。一次 POST 返回业务成功只代表进入队列。状态查询最多 3 次，`readkey` 仅在当次内存中使用；公开状态只留非敏感 pushid、`queued` / `confirmed` / `failed` / `unknown` 与尝试记录。查询是否也占用服务额度尚待真实账号核查，可将 `query_counts_quota` 设为保守模式或调低 `poll_limit`。当前文档所述免费 5 条及详情约 1 天仍需在实际账号部署时复核。

正文默认不超过 30,000 UTF-8 bytes。过长时先缩短轻量标题清单，再以完整论文边界将已总结的完整档改为存档链接呈现；对应业务档位和已验证总结仍保留。发送前必须先有不可变快照，并由 publisher 检查该快照在公开远端可读取且字节一致。详情页的短期保留不能作为历史存档。

## 状态冲突与故障恢复

`scripts/publish_state.py` 只暂存 `state.json`、`archive/**` 下的 Markdown/JSON 和可选根 `.gitignore`；运行锁、原子写临时文件、PDF、图片和原始 provider 数据不会进入公开状态提交。它使用 `.state` checkout 的 HEAD 作为期望远端版本。每次发布先 fetch 并比对；远端提前改变就中止，保留本地文件供排查，不自动覆盖别人的提交。推送后再确认远端 OID，并对新增的 `archive/YYYY/MM/DD/<digest-id>.md` 等快照检查公开 raw URL 是否可访问、内容是否一致。若仓库或归档不可公开读取，发送步骤应停止。网络短暂不可见时稍后手动重跑；先拉取并核对最新状态，不直接 force push。

如果状态显示 `attempt_started/sending` 而无确认，上一轮可能已完成 POST。恢复将它视为 `unknown`，保留已消耗的额度和累计尝试。下次运行在剩余额度内有限补发时，应使用旧的已验证内容，建立标注“补发，上一轮投递未确认”的**新**快照，并通过 `recovery_of` 关联旧 digest；旧快照不得改写。平台确认失败可在有限次数内恢复；成功确认的基础 arXiv ID 不因修订、配置变化或模型变化自动重发。真实送达与微信已读均无法从该接口保证。

首次真实联调应小规模进行：核对 arXiv 分页/日期覆盖、DeepSeek 实际参数与费用、Server酱真实响应结构、免费账号过试用后的额度与日界、`wxstatus` 形态、微信详情阅读、公开归档链接。离线测试通过不等于上述端到端检查通过。真实服务返回未认识的状态时记录 `unknown`，按现场观察调整解析器，不能将顶层 `code=0` 写成确认送达。
