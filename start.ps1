# Spoteye one-command start: builds the web UI if needed, then serves UI + API on
# http://127.0.0.1:8000. Any extra arguments are passed on to `python cli.py serve`.
$ErrorActionPreference = 'Stop'

Set-Location (Join-Path $PSScriptRoot 'backend')
. .\.venv\Scripts\Activate.ps1

if (-not (Test-Path '..\frontend\dist\index.html')) {
    Write-Host 'Building the web UI (first run)...'
    npm --prefix ..\frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed (try: cd ..\frontend; npm install).' }
}

python cli.py serve @args
