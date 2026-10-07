# 开发维护

在项目根目录运行，使用 conda ml / Python 3.12。工作区依赖在 app/.runtime，临时输出统一放 app/tmp。

```powershell
conda activate ml
$env:PYTHONPATH = "$PWD\app\.runtime;$PWD\app"
$env:PYTHONUTF8 = '1'
python -m pytest app/tests -q
python app/scripts/check_public_files.py
```

按修改范围做回归；配置/提示入口涉及 CLI、规则、模型、流水线与部署路径。保留固定上游的原许可和来源，不降低门禁、伪造确认或清空正式状态来通过测试。

## 安装

```powershell
conda activate ml
$env:TEMP = "$PWD\app\tmp\pip"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pip install --target app/.runtime --cache-dir app/tmp/pipcache -r app/requirements.lock
```

无需修改 conda 全局依赖。Actions 读取锁定文件再 editable 安装 app。wheel 包含提示文件与上游许可；独立安装需 --config 指定配置，未指定提示目录时用包内提示。

## 工具

| 位置 | 用途 |
| --- | --- |
| app/scripts/run-local.ps1 | 自动选择 conda ml，启动 CLI |
| app/scripts/publish_state.py | 正式同步发布与公开快照校验 |
| app/scripts/check_public_files.py | 公开候选的凭据/私有文件检查 |
| app/tools/build_demo.py | 生成合成样本，无外部请求 |
| app/tools/prepare_replay.py | 下载固定回放来源，有网络，无模型/推送 |
| app/tools/audit_representatives.py | 固定来源解析/离线证据检查 |
| app/tools/check_isolated_runtime.py | Python -I -S 检查依赖和离线回放 |
| app/tools/check_live_api.py | 少量真实模型检查，可能收费，不推送，缓存成功结果 |
| app/notebooks/arxiv_rules_debug.ipynb / app/tools/debug_rules.py | 分类元数据缓存、关键词召回与差异分析，不读取正式状态或调用模型 |

工具报告在 app/tmp/tools，CLI 报告在 app/tmp/reports。固定原文不提交；manifest.json 和 representative.json 固定来源哈希，不能随意修改以绕过失败。

普通测试多数使用模拟输入；真实固定来源解析回归与代表 replay 需要本地来源，缺失先运行 prepare_replay。哈希变化明确失败并核查。

```powershell
python app/tools/prepare_replay.py --timeout 90 --attempts 3
python app/tools/audit_representatives.py
python -I -S app/tools/check_isolated_runtime.py
```

真实模型工具默认复用成功阶段，--retry-failed 允许失败阶段再次付费，--refresh-summary 明确刷新总结。提示/模型/来源变化使用独立指纹目录，不覆盖旧检查。任意新提示也可用 CLI 指定 ID 的 replay --live 评估，结果与正式状态分离。
