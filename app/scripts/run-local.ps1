param([Parameter(ValueFromRemainingArguments = $true)][string[]]$DigestArgs)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
$mlPython = $null
if ($env:CONDA_DEFAULT_ENV -eq 'ml' -and $env:CONDA_PREFIX) {
    $mlPython = Join-Path $env:CONDA_PREFIX 'python.exe'
} else {
    $conda = Get-Command conda -ErrorAction SilentlyContinue
    if ($conda) {
        $environments = & conda env list --json | ConvertFrom-Json
        $mlEnvironment = $environments.envs | Where-Object { (Split-Path -Leaf $_) -eq 'ml' } | Select-Object -First 1
        if ($mlEnvironment) { $mlPython = Join-Path $mlEnvironment 'python.exe' }
    }
    if (-not $mlPython) {
        foreach ($candidate in @('D:\Anaconda3\envs\ml\python.exe', (Join-Path $env:USERPROFILE 'anaconda3\envs\ml\python.exe'))) {
            if (Test-Path -LiteralPath $candidate) { $mlPython = $candidate; break }
        }
    }
}
if (-not $mlPython -or -not (Test-Path -LiteralPath $mlPython)) { throw '找不到 conda ml 的 Python；请先 conda activate ml 后再运行。' }
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
