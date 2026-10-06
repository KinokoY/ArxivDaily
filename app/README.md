# ArxivDaily

摘要规则宽初筛 → DeepSeek Flash 终筛（high）→ 合格正文与必要图表总结（max）→ 一条免费 Server酱微信日报，完整历史与持久状态放专用公开分支。

本地应用层、离线与模拟验证已完成。2026-10-03 已导入并实际复用固定上游元数据、保留原 MIT 许可，并发布到 [KinokoY/ArxivDaily](https://github.com/KinokoY/ArxivDaily)。同一 CLI 的本机真实两 ID 贯通、公开 Git 状态/归档和一次微信发送已通过；GitHub hosted runner 因账户 billing issue 未启动，Ubuntu 尚待验证。实际复用边界见 [UPSTREAM.md](UPSTREAM.md)；本目录 LICENSE 覆盖新增代码。

## 本机运行

已经使用本机 conda `ml` 的 Python 3.12.9，将锁定依赖安装在 `app/.runtime/`。以下命令在工作区根目录 PowerShell 执行，不需要 Secrets。

```powershell
& ./app/scripts/run-local.ps1 run --fixture fixtures/demo.json --now 2026-10-02T07:17:00+00:00 --report reports/demo-run.json
& ./app/scripts/run-local.ps1 replay --ids 2308.00692v3 2504.11008v2 2505.11872v4 2603.19169v1 --now 2026-10-02T07:17:00+00:00 --report reports/representative-run.json
```

`run` 与 `replay` 默认使用隔离的 `app/runs/dry-*/`，不会修改部署状态或实际送达登记。离线终筛响应是明确标记的人工校准 fixture，不能视作 DeepSeek 真实质量验收。代表论文摘要、HTML、PDF 是固定版本的实际公开来源；下载清单与 SHA-256 在 `fixtures/sources/manifest.json`。fixture 只使用合格正文作完整档证据。

持久模拟用于复现跨运行 unknown，必须放 `app/runs/`：

```powershell
& ./app/scripts/run-local.ps1 simulate --state-dir runs/unknown-demo --mock-status unknown --now 2026-10-02T07:17:00+00:00 --report reports/unknown-first.json
& ./app/scripts/run-local.ps1 simulate --state-dir runs/unknown-demo --mock-status confirmed --now 2026-10-03T07:17:00+00:00 --report reports/unknown-recovery.json
```

报告 JSON 列出档位、失败阶段和状态位置；日报在对应状态位置的 `archive/`。返回码 0 表示本次可执行工作成功，1 表示可恢复问题或部分失败，2 表示配置、持久化等运行错误。正常检查完成且没有新增可推送论文时，也生成日报并发送“今天未发现新增工作”；抓取不完整或处理失败会报告问题，不伪装成无新增。

## 标题与摘要双语模式（2026-10-07）

默认 `workflow.mode = "summary"` 保留原全文工作流。设为 `"translation"` 后，沿用摘要规则和 LLM 摘要终筛，仅推送英文标题、中文标题、原始摘要、完整中文摘要与论文链接。此模式不下载正文，不做全文复审，也不受完整总结的每日篇数上限限制。终筛 `uncertain` 的候选一并提供原文和译文，并在日报备注中说明尚未进行全文确认；`reject` 不推送。

单次运行可用 `--workflow translation` 覆盖；GitHub Actions 手动运行选 `content_workflow=translation`。定时任务使用 `config.toml` 中的 `workflow.mode`。同一状态中已确认推送的论文不会因为切换模式而重新发送；未确认推送沿用已保存的内容和原投递链。

```powershell
# 在项目根目录、已激活 conda ml 环境中运行。
$env:PYTHONPATH = "$PWD\app\.runtime;$PWD\app"
python -m arxivdaily.cli run --workflow translation --report app/tmp/translation-demo.json
# 真实分析但不发送（仍使用隔离状态）：
python -m arxivdaily.cli run --config app/config.toml --workflow translation --live --report app/tmp/translation-live.json
```

`translation.provider` 可选 `llm`、`deepl`、`libretranslate`。LLM 翻译复用 `llm.filter` 的模型、端点和密钥，关闭思考，只提交标题和摘要，按原 usage 机制记录费用。DeepL 使用官方 `https://api-free.deepl.com`，密钥放 `TRANSLATION_API_KEY` 环境变量或同名 Actions Secret。LibreTranslate 必须将 `translation.base_url` 改成自己的实例地址，如 `http://localhost:5000`（Actions 中的 localhost 指 runner 自己）；公开远程实例使用 HTTPS，密钥由实例配置决定。机器翻译失败不会自动改用收费 LLM。离线模拟始终使用标注为离线的译文，不调用机器翻译接口。

双语摘要超过 Server酱长度限制时，按整篇移到公开日报，用链接承接，存档中保留完整原文和译文。短总结和双语内容都有持久缓存，失败补发不会重新翻译。

长期单文件索引在状态目录的 **`archive/papers.md`**，发布到 `arxivdaily-state` 同一路径。表格列为“首次收集日期（北京时间）—英文标题—中文标题—链接”，覆盖所有规则命中并保存的候选（含未通过终筛者），按 base arXiv ID 去重；索引不是已经推送的论文列表。既有状态在下一次运行自动生成索引，已有正文总结和投递记录保持原样；缺少的中文标题单独翻译一次。翻译未成功时写“待翻译”，不丢弃索引行。原每日归档和不可变快照继续保留，日报备注提供索引入口。

免费额度、术语质量及选型建议见 [TRANSLATION.md](docs/TRANSLATION.md)。

`reports/sample-digest.md` 是固定代表回放生成的可读示例。报告中的 `real_delivery` 指运行模式，具体结果看 `delivery_status`（prepared/deferred/confirmed/failed/unknown/none）；离线 confirmed 仅来自 mock，不代表微信已送达。

## 测试与重新安装

```powershell
$env:PYTHONPATH = "$PWD\app\.runtime;$PWD\app"
& "$env:USERPROFILE\anaconda3\envs\ml\python.exe" -m pytest app/tests -q
```

测试默认将全部临时产物放 `app/tmp/`。锁定文件 `requirements.lock` 包含实际安装版本。重新安装时使用以下方式，仍不修改 ml 环境：

```powershell
$env:TEMP = "$PWD\app\tmp\pip"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
& "$env:USERPROFILE\anaconda3\envs\ml\python.exe" -m pip install --target app/.runtime --cache-dir app/tmp/pipcache -r app/requirements.lock
```

无需凭证的公开来源补全：

```powershell
$env:PYTHONPATH = "$PWD\app\.runtime;$PWD\app"
& "$env:USERPROFILE\anaconda3\envs\ml\python.exe" app/scripts/prepare_replay.py --timeout 90 --attempts 3
```

脚本会复用已校验材料、在每个下载后保存清单，并明确报告不完整下载；不调用模型或发送接口。

## 部署与真实联调

先按 [DEPLOYMENT.md](docs/DEPLOYMENT.md) 完成上游固定基线导入、公开代码库、状态分支和 Actions 配置。复制 `config.example.toml` 为 `config.toml`，填写 `archive.public_base_url`（状态分支根地址，不带 `/archive`）。只在运行环境或 Actions Secrets 配置 `DEEPSEEK_API_KEY` 和 `SERVERCHAN_SENDKEY`，不把凭证写入配置、日志或聊天。

`--live` 启用真实元数据/正文/收费模型，但默认仍不发送；`--send` 才启用真实发送，并强制要求同步发布检查点及可验证的公开存档。历史日期补采使用 `run --start YYYY-MM-DD --end YYYY-MM-DD --live`；独立回放用 `replay --ids ... --live`。二者未加 `--send` 时不会写正常游标、配额或已送登记。已轻量送达论文只有显式 `--send --promote ID` 才能晋升，并保留原轻量事件。

已完整送达内容若确需重投，使用显式 `--send --resend ID`，复用原档位、总结与证据，新增 resend 事件；`--promote` 只接受此前仅确认轻量的论文。正常重跑和配置变化不会触发这两种操作。仅恢复投递或重投时只需要 Server酱凭据，不要求 DeepSeek key。

自动恢复已超界时，显式使用 `run --retry-stage selection|body|review|summary|delivery --retry-ids ID...`。默认从 `--state-dir` 的现有状态复制到隔离空间做 dry-run；`--live` 可验证真实接口，只有再加 `--send` 和发布检查点才修改正常状态/实际发送。人工恢复仅处理指定 ID，记录授权事件与旧尝试，不修改首次发现时间。delivery 恢复保留原累计次数，仅给指定论文增加有限的人工重试额度，不重新生成已有总结。缺少运行凭据的 `--send` 会在外部调用前报错。

此前小规模 DeepSeek 联调见 `reports/live-api-smoke.json`，可读审阅样例见 `reports/live-sample-digest.md`。最新真实 GitHub 状态+免费微信有界贯通见 `reports/live-e2e-2026-10-03.json`：一次发送、一次查询得到已识别平台成功；Ubuntu 被账户锁阻止，手机详情待用户确认。默认价格使用官方高峰单价的保守上界，不是账单精确值；不默认设置月预算。

公开简报和微信正文只展示论文链接及便于快速判断是否要阅读全文的总结，不展示证据定位列表。来源版本和段落、图表定位仍保存在内部总结状态，供质量校验与追查。

`scripts/check_live_api.py` 只读取环境中的 `DEEPSEEK_API_KEY`，复用已下载的校验来源，不发送微信或修改生产状态。默认成功阶段直接复用；失败阶段只有显式 `--retry-failed` 才再付费，提示或解析修复后的总结复核需显式 `--refresh-summary`，原结果保留在历史中。`--prepare-only` 不调用 API。它是有限联调入口，不用于每日生产运行。

重新核查已下载代表材料的门禁、物理页、图表读取需求和校准短报，可运行 `app/scripts/audit_representatives.py`。脚本检查来源 SHA-256 并实际执行隔离的离线 pipeline，无下载、付费或投递。验收分层与剩余工作见 `reports/ACCEPTANCE.md`。
