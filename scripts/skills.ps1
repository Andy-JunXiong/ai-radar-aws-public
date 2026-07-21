$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (Get-Command python -ErrorAction SilentlyContinue) {
    python -m app.prompts.export_skills @args
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m app.prompts.export_skills @args
    exit $LASTEXITCODE
}

throw "Python is not available on PATH. Install Python or run from an environment that exposes python/py."
