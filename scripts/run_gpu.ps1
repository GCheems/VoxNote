$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $projectRoot

$pythonPath = $env:VOXNOTE_PYTHON
if (-not $pythonPath -and (Test-Path -LiteralPath ".env")) {
    $configLine = Get-Content -LiteralPath ".env" |
        Where-Object { $_ -match "^\s*VOXNOTE_PYTHON\s*=" } |
        Select-Object -First 1
    if ($configLine) {
        $pythonPath = ($configLine -split "=", 2)[1].Trim().Trim('"').Trim("'")
    }
}
if (-not $pythonPath) {
    $pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "找不到 Python 环境：$pythonPath。请设置 VOXNOTE_PYTHON 指向 GPU Python。"
}

& $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
