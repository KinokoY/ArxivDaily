param([Parameter(ValueFromRemainingArguments = $true)][string[]]$DigestArgs)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
$mlPython = Join-Path $env:USERPROFILE 'anaconda3\envs\ml\python.exe'
if (-not (Test-Path -LiteralPath $mlPython)) { throw '找不到 conda ml 的 Python；请在已激活的 Python 3.12 环境中使用 python -m arxivdaily.cli。' }
if (-not (Test-Path -LiteralPath (Join-Path $appRoot '.runtime\arxiv\__init__.py'))) { throw '缺少工作区依赖；请按 README 安装 requirements.lock 到 app/.runtime。' }
$env:PYTHONPATH = "$appRoot\.runtime;$appRoot"
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $appRoot 'tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
Push-Location -LiteralPath $appRoot
try { & $mlPython -m arxivdaily.cli @DigestArgs; $digestExit = $LASTEXITCODE }
finally { Pop-Location }
exit $digestExit
