# ArxivDaily

每日筛选 arXiv 论文，提供中文正文总结、独立轻量标题清单，或标题与摘要双语简报，并用免费 Server酱推送。正常无新增也发送通知，每日归档之外维护单文件论文索引。兴趣配置、阶段状态和 Markdown 历史可公开；运行秘钥使用 GitHub Actions Secrets。

应用位于 [`app/`](app/README.md)，实际 GitHub Actions 入口位于 [`.github/workflows/daily-digest.yml`](.github/workflows/daily-digest.yml)。每日北京时间 15:17 调度，手工运行默认不发送；真实发送前必须完成状态检查点和公开归档验证。

- [当前开发状态](DEVELOPMENT-STATUS.md)与[下一会话交接](HANDOFF-NEXT.md)
- [规格](docs/SPEC.md)、[实施计划](docs/IMPLEMENTATION-PLAN.md)与[术语](GLOSSARY.md)
- [部署](app/docs/DEPLOYMENT.md)、[恢复操作](app/docs/OPERATIONS.md)与[分层验收](app/reports/ACCEPTANCE.md)
- [双语工作流与免费翻译选型](app/docs/TRANSLATION.md)：`--workflow translation`，长期索引位于状态分支的 `archive/papers.md`
- [固定上游与实际复用边界](app/UPSTREAM.md)

本机优先使用 conda `ml`，依赖和临时产物放工作区。无需凭证的代表回放：

```powershell
& ./app/scripts/run-local.ps1 replay --ids 2308.00692v3 2504.11008v2 2505.11872v4 2603.19169v1
```

公开文件检查：

```powershell
& "$env:USERPROFILE\anaconda3\envs\ml\python.exe" app/scripts/check_public_files.py
```

检查 Git 的已跟踪和未忽略候选文件，发现秘钥形态或误加入的私有运行目录时退出失败，输出仅含文件名。`.secrets/`、`.env*`、依赖、运行状态、临时文件、构建产物和原始论文均不进入代码仓库；正式状态由专用 `arxivdaily-state` 分支保存。

新增应用代码采用 [MIT](LICENSE)。复用的 Paper Digest 固定源码保留其[原 MIT 许可](app/arxivdaily/_vendor/paper_digest/LICENSE)及逐文件来源哈希；没有启用上游 Pages、翻译模型或维护工作流。
